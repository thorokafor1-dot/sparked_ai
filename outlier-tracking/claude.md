# Outlier Tracking

Single job of this folder: find YouTube videos that are outperforming their channel/niche baseline ("outliers") and write the results as JSON committed to the repo, across 4 distinct categories — each with its own subfolder and its own tunable metrics.

Credentials: `YOUTUBE_API_KEY` is the **only** credential this pipeline needs (set it in a local, gitignored `outlier-tracking/.env` for local runs, or as a `YOUTUBE_API_KEY` GitHub Actions secret for scheduled runs). Google Sheets was removed from the pipeline entirely — each script writes its own `data.json` straight into its own subfolder instead, and the GitHub Actions workflow commits + pushes it back to the repo.

## Structure

- `common.py` — shared helpers used by every script below: YouTube API client/fetchers, the English-title filter, the cold-approach/pickup relevance filter (`is_relevant_tags`), `write_rows_to_json` (writes a rows list to a path, creating parent dirs as needed), and per-channel capping. Also holds the shared `KEYWORDS`/`VIDEO_CHAT_KEYWORDS` niche keyword lists.
- `youtube_outliers.py` — entry point for the two **niche-specific** outputs. Does one shared YouTube search pass (in-person + video-chat keywords), classifies each result long-form vs. Shorts, and delegates scoring/writing to the two folders below — kept as a single scan rather than two independent scripts to avoid ~doubling YouTube API quota usage for the same underlying results. Tags each row with a `Format` column ("In-Person" / "Video Chat"), and writes each of its two outputs already shaped for the published dashboard (camelCase keys: `publishedAt`, `videoUrl`, `vid`, `thumbnailUrl`, etc.).
- `trigger_workflow.py` / `trigger_workflow.ps1` — manually dispatch the `youtube_outlier_tracker.yml` GitHub Actions workflow via the API (needs `GITHUB_TOKEN`).

### niche-long-form/
- `long_form_tracker.py` — thresholds and `is_outlier()` for the niche long-form output. Imported by `youtube_outliers.py`, which writes its result to `niche-long-form/data.json`.

### niche-short-form/
- `short_form_tracker.py` — Shorts-specific thresholds, `SHORTS_LOOKBACK_DAYS`, `is_outlier_short()`. Imported by `youtube_outliers.py`, which writes its result to `niche-short-form/data.json`.

### general-long-form/
- `general_outlier_finder.py` — scans for cross-niche (adjacent-niche) long-form outlier candidates, independent of the cold-approach keyword list. Prints `CANDIDATE` log lines for manual curation. Needs `YOUTUBE_API_KEY` only.
- `general_outlier_swipe_file.py` — writes `general-long-form/data.json` from its hardcoded, manually-curated `SWIPE_FILE` list (candidates found above), each with a cold-approach title/thumbnail translation. Needs no credentials at all — just dumps its own Python data to JSON.

### general-short-form/
- `general_shorts_finder.py` — the Shorts-only sibling of the long-form finder above; scans for ultra-viral cross-niche Shorts. Imports `KEYWORDS` from `general-long-form/general_outlier_finder.py`. Needs `YOUTUBE_API_KEY` only.
- `general_shorts_swipe_file.py` — writes `general-short-form/data.json` from its hardcoded `SWIPE_FILE` list. Needs no credentials.

## Cross-folder imports

Folder names use hyphens (not valid in Python identifiers), so scripts don't use package-style imports. Each script that needs code from a sibling/parent folder inserts that folder onto `sys.path` via `os.path.dirname(__file__)` before importing — e.g. `general-short-form/general_shorts_finder.py` inserts both the `outlier-tracking/` root (for `common.py`) and `general-long-form/` (for `general_outlier_finder.py`'s `KEYWORDS`). Follow this same pattern for any new cross-folder import here.

## Dashboard sync

The published "Outlier Field Log" dashboard reads its own bundled `data.json` (shape: `{outliers, shorts, generalOutliers, generalShorts}`), which is a manual merge of these 4 subfolders' `data.json` files plus locally-fetched thumbnail images (`thumbs/<vid>.jpg`, niche tabs only — the general tabs' cards are text-only). Syncing the dashboard to the latest repo data is a manual/Claude-driven step done on request, not automatic — the repo's `data.json` files are the source of truth, the dashboard is a snapshot of them.

## Scope rules
- Keep this folder about *finding and recording outliers* only. Shorts hook/opener/thumbnail *ideation* research and Instagram posting live in their own folders — don't cross-import from here (`shorts-hook-research/` is pure ideation notes now; the Shorts outlier finder/writer moved into `general-short-form/` above).
- Corresponding CI workflows live in `.github/workflows/` (`youtube_outlier_tracker.yml`, `general_outlier_finder.yml`, `general_outlier_swipe_file.yml`, `general_shorts_finder.yml`, `general_shorts_swipe_file.yml`) and invoke these scripts by path from the repo root — if you rename or move a script here, update the matching workflow's `run:` line too. The 3 that write data (`youtube_outlier_tracker.yml`, `general_outlier_swipe_file.yml`, `general_shorts_swipe_file.yml`) each have a "Commit updated data" step after the script runs — needs `permissions: contents: write` (already set).
