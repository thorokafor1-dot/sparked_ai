# QA (project-wide self-checks)

This is the automated quality gate for the whole Sparked AI project. Its job is to catch mistakes before the user sees them. The "Self-Verification" section in the root `CLAUDE.md` explains how the agent must use it.

## Contents
- `checks.py`: the check registry plus the generic checks (no em dash, valid JSON/Python/YAML, no merge markers, no hardcoded secrets, imports resolve). Each check has a level:
  - `fast`: runs after every edit
  - `full`: runs before a turn can end
- `checks_<area>.py`: folder-specific checks. `load_all()` picks these up automatically, they register with `from checks import check`, and a module that fails to import is itself reported as a failure.
  - `checks_video.py`: render specs, black/frozen/silent stretches, loudness, and face-on-screen for the Monkey App shorts.
  - `checks_image.py`: thumbnail size/format, main-face sharpness and exposure.
  - `checks_text.py`: script timeline, pacing and dialogue rules, concept-doc sections, caption safe zone, hook-pattern docs.
  - `checks_data.py`: outlier `data.json` integrity plus the general-tab 500K/90-day bar, and English-only hook transcripts.
  - `checks_web.py`: landing-page local links and assets.
- `media.py`: ffprobe/ffmpeg helpers (one decode pass per video). Slow checks use `cache=True`, so an unchanged file is never re-analyzed (cache in `.claude/qa_state/cache.json`).
- `preflight_post.py`: caption, video and thumbnail pre-flight that every posting script calls before uploading. It exits with code 2 on any problem.
- `OUTPUT_GLOBS` in `checks.py`: gitignored output folders (renders, thumbnails, captions) that the stop gate checks when they appear during one of this session's commands. Add a folder here when a new workflow starts producing outputs.
- `run_checks.py`: the command line interface.
  - `python qa/run_checks.py [--level full] <paths>` checks specific files.
  - `--changed` checks every git-modified file.
  - `--list` shows every registered check.
- `hooks/`: Claude Code hooks, registered in `.claude/settings.json`:
  - `session_start.py` records when the session began.
  - `post_edit.py` runs the fast checks on each Write/Edit and hands any failures straight back to the agent (exit 2).
  - `command_window.py` (Pre/PostToolUse on Bash|PowerShell) records outputs and changed files that appeared while this session's command ran, so parallel sessions never block each other.
  - `stop_gate.py` runs the full checks on everything this session wrote or produced (newest `_vN` only) and blocks the turn from ending until they pass. After 3 blocked attempts it lets the turn end and shows the leftover problems to the user.
- Per-session state lives in `.claude/qa_state/` (gitignored).

## Adding a check
1. Write a function that takes a `Path` and returns a list of problem strings. Each string must say what is wrong, where, and how to fix it.
2. Decorate it with `@check(name, level=..., exts=..., paths=[repo-relative globs], exclude=[...])`.
3. Test that it fails on a bad example and passes on a good one before relying on it.

## Scope rules
- Checks must be deterministic and cheap enough for their level. Anything slow (ffprobe, image analysis) goes in `full`.
- Taste judgments (tone, hook strength) belong to the `critic` subagent, not here. If the critic suggests a mechanical rule, it becomes a check here.
- External or scraped data (raw inputs, `*_dump.txt`, transcripts, `data.json` titles) is not our copy. Exclude it from the copy-style checks rather than editing it.
