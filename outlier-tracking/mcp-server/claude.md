# Outlier Tracker MCP Server

Single job of this folder: expose `outlier-tracking`'s data.json files and `video-ideation/strategist`'s idea-dashboard output as live tools for Grok's custom connector (grok.com/connectors), so the owner can query real outlier/idea data directly in a SuperGrok chat instead of manually exporting files.

## Deployment
Deployed on Render (`render.yaml`), free plan. Render redeploys automatically whenever `main` updates, so any file this server reads must actually be committed and pushed, not just present locally, before Grok can see it. Health check at `/health`.

## Auth
Protected by GitHub OAuth (`GitHubProvider`), not a static bearer token, Grok's Custom Connector does its own OAuth client registration and won't accept a pasted token. Every tool call is additionally gated to `OWNER_GITHUB_LOGIN` (`_require_owner()`), so a stolen/guessed client_id alone can't read the data, the caller must complete GitHub login as the owner's real account. Auth is skipped entirely when `GITHUB_CLIENT_ID`/`GITHUB_CLIENT_SECRET`/`RENDER_EXTERNAL_URL` aren't set (local dev only, never deploy without them).

## Tools
- `list_tabs`, `get_top_outliers`, `get_video_details`: the 4 outlier-tracker tabs (niche/general x long/short form), same data the dashboard reads.
- `list_idea_categories`, `get_ideas`, `get_title_patterns`: `video-ideation/strategist`'s ranked video ideas and the mechanical title-pattern evidence behind them (see `.claude/skills/video-idea-dashboard/SKILL.md`). Reads `ideas.json` and `report.json` from that folder, both untracked/gitignored-by-convention local outputs today, they must be committed for this deployment to see them.

## Scope rules
- Read-only, this server never writes to any data file or triggers a refresh, it only serves what's already on disk at deploy time.
- Doesn't replace `grok_swipe_pack.py`'s manual export, that stays useful for a one-off drag-and-drop pack, this is for live querying in chat.
