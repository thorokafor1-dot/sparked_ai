---
name: script-research
description: Refresh the full-script retention research (niche + big-channel general outliers, full transcripts, pacing metrics, retention playbook). Use when the user wants script-writing data, retention patterns beyond the hook, or to update what the script-writer learns from.
---

# Refresh script retention research

Folder: `long-form-script-research/` (read its `claude.md` for scope and gotchas).

## Steps
1. **Candidates:** `python long-form-script-research/find_general_outliers.py` (all groups, about 10 min) or `--group <name>` to rescan one group. No API quota.
2. **Transcripts:** `python long-form-script-research/pull_full_transcripts.py --source all`. It resumes, so if it hits a 429, rerun later. Add `--whisper` only if captions stay blocked.
3. **Metrics + beat maps:** `python long-form-script-research/analyze_retention.py` (also rebuilds `beat_maps/`). If it prints UNMAPPED, add the group to `CATEGORY`.
4. **Playbook:** update `retention_playbook.md` from `retention_metrics.json` (bucket medians) and `skeletons.md` (read the skeletons for the top 3-4 videos per bucket, not all of them). Keep niche and general findings separate, then the "Apply to Sparked" section translates the general findings for an adult-male cold-approach audience.
5. **Validate:** `python qa/run_checks.py long-form-script-research/retention_playbook.md`.

## Gotchas
- Don't run step 1 and step 2 at the same time, because YouTube rate-limits the combined traffic (seen 2026-10-01).
- Third-party tools (vidIQ, 1of10, ViewStats) only add outlier discovery, which this pipeline already does free. None expose competitor retention. Don't pay for one for this purpose.
- The playbook is outlier-only. Never feed own-channel analytics into it (user: their channel is not model data). `retention-report` stays a separate diagnostic.
- Python heredocs that write `"\n".join(...)` into a file can land as a literal line break and break the file (hit twice 2026-10-01). Use the Edit tool for code containing `
`.
- Some handles in `channels.json` may not resolve. The scan prints SKIP lines for those; fix the handle or drop it.
