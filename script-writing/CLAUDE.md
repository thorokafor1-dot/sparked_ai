# Script Writing

Single job of this folder: hold full, word-for-word, production-ready scripts for planned videos, written by the `script-writer` subagent (`.claude/agents/script-writer.md`).

## Contents
- `script_<name>.md` — one script per video, matching the `ideation_<name>.md` it was written from in `video-ideation/`.

## Scope rules
- Scripts here are written from a video's already-decided concept, hook plan, and swipe file in `video-ideation/` — this folder doesn't decide concept, title, or hook structure itself (that's `video-ideation/` and the `hook-researcher` subagent).
- Doesn't post, edit, or track outliers — feeds into `long-form-to-shorts-video-editing/` once a script is locked.
