---
name: refresh-outliers
description: Refresh the outlier-tracking dashboards (niche and general, long and short form) and validate the data. Use when the user wants fresh outliers, a dashboard update, or new swipe-file material.
---

# Refresh outlier data

These run weekly on GitHub Actions on Sundays: the niche tracker at 6AM Central, then general curation at 7AM. **Don't run them locally unless the data is stale or the user asks now**, because a local run burns YouTube API quota.

## Steps
1. **Check freshness first:** `git fetch` and look at `git log origin/main -1 -- outlier-tracking/<tab>/data.json`. If the scheduled run already covered it, just `git pull`.
2. **To run it now:** `python outlier-tracking/trigger_workflow.py` triggers the **niche** tracker on Actions (preferred, since secrets live there). There's no trigger script for general curation yet. It would be the same dispatch call against `general_outlier_curation.yml`, so add a `--workflow` flag to `trigger_workflow.py` the first time it's needed. Only use a local run (`youtube_outliers.py` / `curate_general_with_claude.py --tab long-form|short-form`) if Actions is down.
3. **Validate:** `python qa/run_checks.py outlier-tracking/*/data.json`. The `outlier-data` gate covers structure, duplicates and the general tabs' 500K/90-day bar.
4. **Check the Actions result** through the GitHub API (`gh` isn't installed): `curl -s https://api.github.com/repos/thorokafor1-dot/sparked_ai/actions/workflows/<file>.yml/runs?per_page=3`.
5. **Hook research** only needs re-pulling if new high-scoring entries appeared in a content type (`long-form-hook-research/<type>/pull_hook_transcripts.py`).

## Gotchas (keep this list updated)
- **General curation** first runs 2026-09-27. Until then, `general-short-form` holds 58 stale entries, and that run should prune them. Verify with step 3.
- **Date formats differ:** niche tabs use "Mar 28, 2026" and general tabs use ISO dates.
