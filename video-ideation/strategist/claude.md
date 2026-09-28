# Video Idea Strategist

Single job of this folder: turn outlier-tracking data into ranked, sourced video ideas (title, thumbnail plan, footage needs) for this channel, and build the Idea Desk dashboard from them. Run the `.claude/skills/video-idea-dashboard/SKILL.md` playbook to refresh, don't hand-edit `ideas.json`.

## Contents
- `extract_patterns.py`: mechanical pass over `outlier-tracking/niche-long-form/` and `general-long-form/`. Buckets rows into daygame, bargame, video-chat-edates, explainer (from the tracker's own `format` field, In-Person split into bar vs daygame by venue words) and general (cross-niche). Tags recurring title structures with their real scores. `--json` writes `report.json`.
- `ideas_source.py` + `ideas_revisions.py`: the authored ideas (title, hook, thumbnail brief, Grok prompt, evidence). Evidence rows are looked up from the real outlier data by title substring so scores and URLs are never hand-typed. Writes `ideas.json`. Rewrite the idea list each refresh, it is a judgment call. `ideas_revisions.py` holds the changes made after the last critic review.
- `ideas.json`: the ranked ideas plus a `parked` list of cut ideas. Read by the MCP server (`outlier-tracking/mcp-server/`) so Grok sees the same ideas.
- `build_dashboard.py` + `dashboard_template.html`: builds the Idea Desk page into `dashboard/` (gitignored: `idea_desk.html` and downloaded reference `thumbs/`). Publish it as a Claude Artifact with `thumbs/` as supporting files.
- `report.json`: last `extract_patterns.py --json` output, regenerate rather than hand-edit.

## Evidence rules
- Label an idea `proven` only when at least two niche outliers above about 20x support the same format. One outlier or a cross-niche source is `adapted`.
- Bar data is thin (about 11 videos). Say so on any bar idea instead of implying proof.
- Never promise a result in a title (a number, a yes, a second date). Never write words for a woman. Video chat titles say "e-dates" and never name the app.

## Scope rules
- Doesn't post, edit, or track outliers, reads `outlier-tracking/*/data.json` as the source of truth.
- Doesn't generate thumbnail images. The dashboard gives a woman-focused brief and prompt per idea, images are made in Grok Imagine (free with SuperGrok) or `thumbnail-creation/generate_concept_mockup.py` (paid API).
