# Video Idea Strategist

Single job of this folder: turn outlier-tracking data into ranked, sourced video ideas (title + thumbnail scenario) for this channel, then hand off to thumbnail generation and the Claude Artifact dashboard. Built from `.claude/skills/video-idea-dashboard/SKILL.md`, run that skill to refresh this folder's output rather than editing `ideas.json` by hand.

## Contents
- `extract_patterns.py`: mechanical pass over `outlier-tracking/niche-long-form/` and `outlier-tracking/general-long-form/` data.json files. Buckets entries into this channel's content categories (mirrors `video-ideation/video-ideas/`'s folders: bar, monkey-app-video-chat, street-daytime-pov, explainer, general) and tags recurring title structures (TIER LIST, "I Tested X", "Her Reaction", POV:, numbered list, etc.) with their real scores. Does not invent ideas, only surfaces what is actually in the data. Run with `--json` for the dashboard step, plain for a human-readable report.
- `report.json`: last `extract_patterns.py --json` output, regenerate rather than hand-edit.
- `ideas.json`: the actual ranked idea proposals, each with a title, thumbnail scenario description, source outlier citation, and rationale. This is Claude's creative synthesis on top of `report.json`'s mechanical findings, redo this step each refresh rather than scripting it, turning a pattern into a concrete title is a judgment call.

## Category coverage caveat
Per `feedback_wider_lookback_for_thin_niches`, thin categories (currently: bar and street-daytime-pov relative to monkey-app-video-chat's much larger volume) mean their ideas are adjacent-adapted from nearby patterns, not directly outlier-proven. `extract_patterns.py`'s output states each category's real entry count, always report that alongside any idea pulled from a thin category.

## Scope rules
- Doesn't post, edit, or track outliers itself, reads `outlier-tracking/*/data.json` as the source of truth.
- Doesn't generate thumbnail images itself, that's `thumbnail-creation/generate_concept_mockup.py`.
- Doesn't publish the dashboard itself, that's a Claude Artifact published/refreshed by the skill, not a file in this repo.
