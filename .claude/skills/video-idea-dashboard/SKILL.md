---
name: video-idea-dashboard
description: Refresh the AI-strategist video idea dashboard, ranked, sourced title ideas across all content categories plus AI-generated concept thumbnail mockups, published as a Claude Artifact. Use when the user wants fresh video ideas "with demand", a strategy/idea dashboard refresh, or thumbnail mockups for un-shot ideas.
---

# Video idea strategist dashboard

## Steps
1. **Refresh data if stale:** run the `refresh-outliers` skill first when the outlier data is over a week old.
2. **Pattern pass:** `python video-ideation/strategist/extract_patterns.py --json > video-ideation/strategist/report.json`.
3. **Write the ideas:** edit the `IDEAS` list in `ideas_source.py` (and `ideas_revisions.py` for review fixes), 4 to 6 ideas each for daygame, bargame, video chat e-dates and explainers. Each needs a title, pattern, strength (`proven` or `adapted`, see the folder's Evidence rules), evidence keys that exist in the data, hook, thumbnail brief, Grok prompt, footage and risk. Then `python ideas_source.py` (fails loudly if an evidence row is missing).
4. **Critic:** run the `critic` subagent on `ideas.json` once, apply MUST FIX items, one more round at most. Cut duplicates (one video repackaged three ways counts once), and move weak or filler ideas into `PARKED`.
5. **Build the page:** `python video-ideation/strategist/build_dashboard.py` (downloads reference thumbnails into `dashboard/thumbs/`).
6. **Publish the dashboard:** publish `dashboard/idea_desk.html` with the Artifact tool, passing every file in `dashboard/thumbs/` as supporting `files` (external images are blocked in artifacts, so they must ship with the page). Refresh by republishing to the same URL (read it first if from another conversation).
7. **Thumbnail mockups (on request):** hand the user the idea's Grok prompt, they generate it in Grok Imagine (free with SuperGrok, upload `thumbnail-creation/reference/self/P1030611.JPG`), send it back, then run `make_thumbnail.py`, the `thumbnail-specs` gate and the critic. The scripted paid path is `thumbnail-creation/generate_concept_mockup.py`, confirm spend first.
8. **Report:** the artifact link, the count per category, and which ideas to promote via the `new-video` skill. Push `ideas.json` to `main` when Grok should see the update (Render deploys from main), confirm with the user before pushing.

## Gotchas (keep this list updated)
- **A woman is the thumbnail's main draw, not the creator solo.** Every thumbnail scenario/prompt, manual or scripted, needs a woman as the clear focal subject. `generate_concept_mockup.py` does this by default (`--no-woman` is the deliberate exception, e.g. a tier-list board graphic). When writing manual SuperGrok prompts, always state this explicitly in the prompt text, don't rely on it being implied. each idea's `thumbnail` and `prompt` fields should already say so, since that's also what the MCP connector serves to Grok, see `get_style_rules` below.
- **Never generate a mockup from scratch identity**, always mask-protect a real reference photo of the creator (`generate_concept_mockup.py` already refuses if no face is detected in the reference). This channel is on-camera, not faceless, a synthetic face is not acceptable.
- **Grok connector parity:** the MCP server's `get_style_rules` tool (see `outlier-tracking/mcp-server/claude.md`) is the source of truth for standing content rules Grok needs when it's the one reasoning about ideas/prompts via the connector, since Grok can't see this repo's local memory files. Whenever a standing rule here changes (this file, or a memory feedback entry that affects idea/thumbnail output), update `get_style_rules`' returned text too, and push, so both sides of the connector agree.
- **Spending money:** SuperGrok's $30/month consumer subscription does NOT include xAI API credits, API access is a separate console.x.ai account with its own billing, this is a common mix-up. Default to the manual SuperGrok-app path (no marginal cost) over either provider's paid API. If the scripted OpenAI fallback is used, confirm scope (which/how many ideas) first, don't generate mockups for every idea in `ideas.json` by default.
- **Grok's edit API is prompt-based, not mask-based:** no pixel-exact identity protection like OpenAI's masked edit. Fine for the manual SuperGrok-app path since the user visually checks each result, but don't build an unattended/scripted Grok path without that same human check.
- **No dance-request angle** in titles or thumbnails, and no fabricated dialogue in any title/rationale text (standing channel rules).
- **Category coverage is uneven:** monkey-app-video-chat has the largest real data volume but its top-scoring raw titles lean drama/persona/meme-heavy, which conflicts with this channel's cool/smooth/mature brand vibe, adapt the underlying mechanic, don't copy the aesthetic.
