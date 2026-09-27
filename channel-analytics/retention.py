"""Where do viewers leave (and rewatch) our own videos? Retention report from the YouTube Analytics API.

Curve-shape logic adapted from github.com/tanphat235/YouTube_Analyzer (steep early drop, mid drop,
strong ending, rewatch spikes; medians over means). Per video it pulls the 100-point audience
retention curve plus YouTube's relative retention (vs. similar-length videos on the platform),
finds the biggest drop-off windows and rewatch spikes, and for long-form quotes what was being
said at each one from the video's captions, so the report says *which moment* lost people.

    python retention.py                 # newest 25 uploads
    python retention.py --limit 50
    python retention.py --video VIDEO_ID [--video ID2]

Writes reports/retention_<date>.md (read this) and reports/retention_<date>.json (raw curves).
Needs token.json from oauth_setup.py. Analytics lag ~2-3 days, so brand-new uploads may be empty.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
from pathlib import Path
from statistics import median

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

HERE = Path(__file__).parent
TOKEN_PATH = HERE / "token.json"
REPORTS = HERE / "reports"
SHORT_MAX_SECS = 180
SUMMARY_METRICS = "views,estimatedMinutesWatched,averageViewDuration,averageViewPercentage,subscribersGained,likes,shares,comments"


def services():
    if not TOKEN_PATH.exists():
        raise SystemExit("No token.json yet. Run: python channel-analytics/oauth_setup.py (one browser login).")
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH))
    if not creds.valid:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())
    return build("youtube", "v3", credentials=creds), build("youtubeAnalytics", "v2", credentials=creds)


def iso_secs(d: str) -> int:
    h, m, s = (int(x or 0) for x in re.fullmatch(r"P(?:\d+D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", d).groups())
    return h * 3600 + m * 60 + s


def list_videos(yt, limit: int, ids: list[str]) -> tuple[list[dict], str]:
    ch = yt.channels().list(part="contentDetails,snippet", mine=True).execute()["items"][0]
    if not ids:
        uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
        req = yt.playlistItems().list(part="contentDetails", playlistId=uploads, maxResults=50)
        while req and len(ids) < limit:
            resp = req.execute()
            ids += [i["contentDetails"]["videoId"] for i in resp["items"]]
            req = yt.playlistItems().list_next(req, resp)
        ids = ids[:limit]
    videos = []
    for i in range(0, len(ids), 50):
        for v in yt.videos().list(part="snippet,contentDetails,liveStreamingDetails", id=",".join(ids[i:i + 50])).execute()["items"]:
            secs = iso_secs(v["contentDetails"]["duration"])
            if "liveStreamingDetails" in v or not secs:
                continue  # streams and test streams aren't edited videos, their curves would skew the medians
            videos.append({"id": v["id"], "title": v["snippet"]["title"], "published": v["snippet"]["publishedAt"][:10],
                           "secs": secs, "short": secs <= SHORT_MAX_SECS})
    return videos, ch["snippet"]["publishedAt"][:10]


def query(yta, **kw) -> list[list]:
    return yta.reports().query(ids="channel==MINE", **kw).execute().get("rows", [])


def captions(yt, video_id: str) -> list[tuple[float, float, str]]:
    """(start, end, text) cues from the video's own captions (manual track preferred over auto)."""
    try:
        tracks = yt.captions().list(part="snippet", videoId=video_id).execute()["items"]
        tracks = sorted(tracks, key=lambda t: (t["snippet"]["trackKind"] == "asr", not t["snippet"]["language"].startswith("en")))
        if not tracks:
            return []
        srt = yt.captions().download(id=tracks[0]["id"], tfmt="srt").execute().decode("utf-8", "replace")
    except HttpError:
        return []
    cues = []
    for block in srt.strip().split("\n\n"):
        lines = block.splitlines()
        m = len(lines) >= 3 and re.match(r"(\d+):(\d+):(\d+),(\d+) --> (\d+):(\d+):(\d+),(\d+)", lines[1])
        if m:
            g = [int(x) for x in m.groups()]
            cues.append((g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000, g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000,
                         " ".join(lines[2:])))
    return cues


def quote(cues, t0: float, t1: float) -> str:
    text = " ".join(c[2] for c in cues if c[1] >= t0 - 1 and c[0] <= t1 + 1)
    return (text[:160] + "...") if len(text) > 160 else text


def analyse(v: dict, curve: list[tuple[float, float, float]]) -> dict:
    """curve: (elapsed ratio, audienceWatchRatio, relativeRetentionPerformance) at 1% steps."""
    r = [c[1] for c in curve]
    at = lambda frac: r[min(len(r) - 1, max(0, round(frac * len(r)) - 1))]
    secs = v["secs"]
    # a drop window spans ~5s of video (at least 2 points) so one noisy bucket isn't called a drop-off
    w = max(2, round(5 / max(secs, 1) * 100))
    hook_frac = min(1.0, (3 if v["short"] else 30) / max(secs, 1))
    skip = max(3, w, round(hook_frac * 100))  # the opening drop is covered by the hook number, not listed as a drop-off
    spikes = [(r[i] - r[i - 1], i) for i in range(skip, len(r)) if r[i] - r[i - 1] > 0.02]
    # after a rewatch spike the curve falls back to its trend; that fall-back isn't people leaving
    after_spike = {j for _, i in spikes for j in range(i - w, i + w + 1)}
    deltas = [(r[i + w] - r[i], i) for i in range(skip, len(r) - w) if i not in after_spike]
    drops = []
    for d, i in sorted(deltas):
        if d > -0.03 or len(drops) == 3:
            break
        if all(abs(i - j) > w for _, j in drops):
            drops.append((d, i))
    hook = at(hook_frac)
    shape = []
    if at(0.10) < (0.6 if v["short"] else 0.45):
        shape.append("steep early drop")
    if drops and 0.25 <= drops[0][1] / 100 <= 0.75 and drops[0][0] < -0.08:
        shape.append("mid drop")
    if at(0.5) and at(0.95) / at(0.5) >= 0.8:
        shape.append("strong ending")
    if spikes:
        shape.append("rewatch spikes")
    if v["short"] and r[-1] >= 0.9:
        shape.append("loops (end retention near/above 100%)")
    rel = [c[2] for c in curve]
    return {
        "hook_label": "3s" if v["short"] else "30s", "hook": hook, "mid": at(0.5), "end": r[-1],
        "relative": median(rel), "relative_intro": median(rel[:10]), "shape": shape or ["gradual decline"],
        "drops": [{"at": i / 100 * secs, "to": (i + w) / 100 * secs, "loss": -d} for d, i in drops],
        "spikes": [{"at": i / 100 * secs, "gain": g} for g, i in sorted(spikes, reverse=True)[:3]],
    }


def mmss(t: float) -> str:
    return f"{int(t // 60)}:{int(t % 60):02d}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--video", action="append", default=[])
    parser.add_argument("--no-quotes", action="store_true", help="Skip caption downloads (saves 250 quota units per long-form)")
    args = parser.parse_args()

    yt, yta = services()
    videos, channel_start = list_videos(yt, args.limit, list(args.video))
    today = dt.date.today().isoformat()
    span = {"startDate": channel_start, "endDate": today}
    summary = {row[0]: dict(zip(SUMMARY_METRICS.split(","), row[1:]))
               for row in query(yta, metrics=SUMMARY_METRICS, dimensions="video",
                                filters="video==" + ",".join(v["id"] for v in videos), **span)}
    for v in videos:
        v["stats"] = summary.get(v["id"], {})
        rows = query(yta, metrics="audienceWatchRatio,relativeRetentionPerformance", dimensions="elapsedVideoTimeRatio",
                     filters=f"video=={v['id']}", sort="elapsedVideoTimeRatio", **span) if v["stats"] else []
        v["curve"] = rows
        v["analysis"] = analyse(v, rows) if len(rows) >= 20 else None
        if v["analysis"] and not v["short"] and not args.no_quotes:
            cues = captions(yt, v["id"])
            for d in v["analysis"]["drops"]:
                d["said"] = quote(cues, d["at"], d["to"])
            for s in v["analysis"]["spikes"]:
                s["said"] = quote(cues, s["at"], s["at"] + 3)
        print(f"{'short' if v['short'] else 'long '} {v['id']} {'ok' if v['analysis'] else 'no data yet'}", flush=True)

    REPORTS.mkdir(exist_ok=True)
    (REPORTS / f"retention_{today}.json").write_text(json.dumps(videos, indent=1), encoding="utf-8")
    md = REPORTS / f"retention_{today}.md"
    md.write_text(render_md(videos, today), encoding="utf-8")
    print(md)


def render_md(videos: list[dict], today: str) -> str:
    out = [f"# Retention report, {today}", "",
           "Relative retention: YouTube's comparison against similar-length videos (0.5 = platform median, "
           "higher is better). Hook = share still watching at 3s (shorts) or 30s (long-form).", ""]
    for kind, is_short in (("Long-form", False), ("Shorts", True)):
        group = [v for v in videos if v["short"] == is_short and v["analysis"]]
        if not group:
            continue
        hooks = [v["analysis"]["hook"] for v in group]
        rels = [v["analysis"]["relative"] for v in group]
        out += [f"## {kind} ({len(group)} with data)", "",
                f"Median hook retention {median(hooks):.0%}, median relative retention {median(rels):.2f}.", "",
                "| Video | Published | Views | Avg % viewed | Hook | Relative | Shape |", "|---|---|---|---|---|---|---|"]
        for v in sorted(group, key=lambda v: -v["analysis"]["relative"]):
            a, s = v["analysis"], v["stats"]
            out.append(f"| [{v['title'][:60]}](https://youtu.be/{v['id']}) | {v['published']} | {s.get('views', 0):,} | "
                       f"{s.get('averageViewPercentage', 0):.0f}% | {a['hook']:.0%} | {a['relative']:.2f} | {', '.join(a['shape'])} |")
        out.append("")
        for v in group:
            a = v["analysis"]
            if not (a["drops"] or a["spikes"]):
                continue
            out += [f"### {v['title']}", ""]
            for d in a["drops"]:
                said = f': "{d["said"]}"' if d.get("said") else ""
                out.append(f"- Drop {mmss(d['at'])}-{mmss(d['to'])}, lost {d['loss']:.0%} of viewers{said}")
            for sp in a["spikes"]:
                said = f': "{sp["said"]}"' if sp.get("said") else ""
                out.append(f"- Rewatch spike {mmss(sp['at'])} (+{sp['gain']:.0%}){said}")
            out.append("")
    missing = [v for v in videos if not v["analysis"]]
    if missing:
        out += ["## No retention data yet", "", *[f"- {v['title']} ({v['published']})" for v in missing], ""]
    return "\n".join(out)


if __name__ == "__main__":
    main()
