# Script Writing

Single job of this folder: hold full, word-for-word, production-ready scripts for planned videos, written by the `script-writer` subagent (`.claude/agents/script-writer.md`).

## Contents
- `script_<name>.md`, one script per video, matching the `ideation_<name>.md` it was written from in `video-ideation/`.

## Quality gates (automatic, see `qa/checks_text.py`)
`script-structure` runs on every save of `script_*.md`:
- It cites the `hook_patterns.md` + archetype it's built on in the first lines.
- Timestamped `## [m:ss-m:ss] NAME` sections start at 0:00, run with no gaps or overlaps, and open on the HOOK, which must land by 0:10.
- Spoken VO/LINE words stay at 3.5 words/sec or less per section, so everything can be delivered naturally.
- No woman's dialogue is written or quoted (describe her reaction directionally), and no TODO/TBD placeholders.
After the checks pass, run the `critic` subagent and revise until it returns PASS before showing the user.

## Scope rules
- Scripts here are written from a video's already-decided concept, hook plan, and swipe file in `video-ideation/`, this folder doesn't decide concept, title, or hook structure itself (that's `video-ideation/` and the `hook-researcher` subagent).
- Doesn't post, edit, or track outliers, feeds into `long-form-to-shorts-video-editing/` once a script is locked.
