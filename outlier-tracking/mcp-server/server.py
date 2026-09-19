"""Remote MCP server exposing the outlier tracker's data.json files as live tools for
Grok's custom connector (grok.com/connectors -> New Connector -> Custom -> this
server's URL). Replaces the manual grok_swipe_pack.py export/drag-and-drop flow with
Grok querying the data directly, on demand, in chat.

Reads the same 4 data.json files the dashboard reads (see ../claude.md) straight off
this deployment's filesystem -- Render redeploys automatically whenever main updates,
so this stays in sync with the weekly tracker refresh without any extra wiring.

Protected by GitHub OAuth (via FastMCP's GitHubProvider) rather than a static bearer
token -- Grok's Custom Connector does manual OAuth client registration and won't accept
a plain pasted token, so this server acts as a full OAuth proxy in front of GitHub's
login. Every tool call is additionally gated to OWNER_GITHUB_LOGIN so a stolen/guessed
client_id alone can't read the data -- the caller must actually complete GitHub login
as the owner's account.
"""
import json
import os

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.auth.providers.github import GitHubProvider
from fastmcp.server.dependencies import get_access_token
from starlette.requests import Request
from starlette.responses import PlainTextResponse

OWNER_GITHUB_LOGIN = os.environ.get("OWNER_GITHUB_LOGIN", "thorokafor1-dot")

OUTLIER_TRACKING_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TABS = {
    "outliers": {
        "path": "niche-long-form/data.json",
        "score_key": "score",
        "niche_key": "keyword",
        "description": "Niche-specific long-form cold-approach/dating outliers.",
    },
    "shorts": {
        "path": "niche-short-form/data.json",
        "score_key": "score",
        "niche_key": "keyword",
        "description": "Niche-specific Shorts cold-approach/dating outliers.",
    },
    "generalOutliers": {
        "path": "general-long-form/data.json",
        "score_key": "scoreNum",
        "niche_key": "niche",
        "description": "Cross-niche long-form packaging outliers, curated with cold-approach translations.",
    },
    "generalShorts": {
        "path": "general-short-form/data.json",
        "score_key": "scoreNum",
        "niche_key": "niche",
        "description": "Cross-niche Shorts packaging outliers, curated with cold-approach translations.",
    },
}

github_client_id = os.environ.get("GITHUB_CLIENT_ID")
github_client_secret = os.environ.get("GITHUB_CLIENT_SECRET")
render_base_url = os.environ.get("RENDER_EXTERNAL_URL")  # Render sets this automatically

auth = None
if github_client_id and github_client_secret and render_base_url:
    auth = GitHubProvider(
        client_id=github_client_id,
        client_secret=github_client_secret,
        base_url=render_base_url,
        required_scopes=["read:user"],
    )

mcp = FastMCP(name="Outlier Tracker", auth=auth)


def _require_owner() -> None:
    """Reject any tool call that isn't the owner's own GitHub login, even though
    they've completed a valid OAuth handshake against this server's client_id."""
    token = get_access_token()
    if token is None:
        return  # auth disabled locally (no GitHub credentials configured)
    login = (token.claims or {}).get("login")
    if login != OWNER_GITHUB_LOGIN:
        raise ToolError(f"Access denied: this connector is restricted to {OWNER_GITHUB_LOGIN}.")


def _load_tab(tab: str) -> list:
    if tab not in TABS:
        raise ValueError(f"Unknown tab '{tab}'. Valid tabs: {', '.join(TABS)}")
    path = os.path.join(OUTLIER_TRACKING_DIR, TABS[tab]["path"])
    with open(path, encoding="utf-8") as f:
        return json.load(f)


@mcp.custom_route("/health", methods=["GET"])
async def health_check(request: Request) -> PlainTextResponse:
    return PlainTextResponse("OK")


@mcp.tool
def list_tabs() -> dict:
    """List the 4 available outlier-tracker tabs, each tab's row count, and what it contains."""
    _require_owner()
    result = {}
    for tab, cfg in TABS.items():
        rows = _load_tab(tab)
        result[tab] = {"count": len(rows), "description": cfg["description"]}
    return result


@mcp.tool
def get_top_outliers(tab: str = "outliers", count: int = 8, keyword: str = "") -> list:
    """Get the top-scoring outlier videos from one tab, sorted by outlier score descending.

    Args:
        tab: One of "outliers" (niche long-form), "shorts" (niche Shorts),
            "generalOutliers" (cross-niche long-form), "generalShorts" (cross-niche Shorts).
        count: How many rows to return (default 8).
        keyword: Optional case-insensitive substring to filter by niche/keyword/title before ranking.
    """
    _require_owner()
    cfg = TABS[tab] if tab in TABS else TABS["outliers"]
    rows = _load_tab(tab if tab in TABS else "outliers")

    if keyword:
        kw = keyword.lower()
        rows = [
            r for r in rows
            if kw in r.get(cfg["niche_key"], "").lower() or kw in r.get("title", "").lower()
        ]

    rows.sort(key=lambda r: r[cfg["score_key"]], reverse=True)
    top = rows[: max(1, min(count, len(rows)))]

    return [
        {
            "youtubeUrl": r["videoUrl"],
            "outlierScore": f"{r[cfg['score_key']]}x",
            "title": r["title"],
            "niche": r.get(cfg["niche_key"], ""),
            "thumbnailUrl": r["thumbnailUrl"],
            "vid": r["vid"],
        }
        for r in top
    ]


@mcp.tool
def get_video_details(tab: str, vid: str) -> dict:
    """Get every field the tracker has for one specific video (full packaging analysis
    for general tabs: pattern, psychological trigger, title formula, and its
    cold-approach translation/working title/thumbnail concept).

    Args:
        tab: One of "outliers", "shorts", "generalOutliers", "generalShorts".
        vid: The YouTube video ID (the "vid" field from get_top_outliers).
    """
    _require_owner()
    rows = _load_tab(tab)
    for r in rows:
        if r.get("vid") == vid:
            return r
    return {"error": f"No video with id '{vid}' found in tab '{tab}'."}


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    mcp.run(transport="http", host="0.0.0.0", port=port)
