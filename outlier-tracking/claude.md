# Outlier Tracking

Single job of this folder: find YouTube videos that are outperforming their channel/niche baseline ("outliers") and write the results as JSON committed to the repo, across 4 distinct categories — each with its own subfolder and its own tunable metrics.

Credentials: `YOUTUBE_API_KEY` for everything here; `ANTHROPIC_API_KEY` additionally for the automated general-tab curation (`curate_general_with_claude.py`). Both are set in a local, gitignored `outlier-tracking/.env` for local runs, or as GitHub Actions secrets (same names) for scheduled runs. Google Sheets was removed from the pipeline entirely — each script writes its own `data.json` straight into its own subfolder instead, and the GitHub Actions workflows commit + push it back to the repo.

## Structure

- `common.py` — shared helpers used by every script below: YouTube API client/fetchers, the English-title filter, the cold-approach/pickup relevance filter (`is_relevant_tags`), `write_rows_to_json` (writes a rows list to a path, creating parent dirs as needed), and per-channel capping. Also holds the shared `KEYWORDS`/`VIDEO_CHAT_KEYWORDS` niche keyword lists.
- `youtube_outliers.py` — entry point for the two **niche-specific** outputs. Does one shared YouTube search pass (in-person + video-chat keywords), classifies each result long-form vs. Shorts, and delegates scoring/writing to the two folders below — kept as a single scan rather than two independent scripts to avoid ~doubling YouTube API quota usage for the same underlying results. Tags each row with a `Format` column ("In-Person" / "Video Chat"), and writes each of its two outputs already shaped for the published dashboard (camelCase keys: `publishedAt`, `videoUrl`, `vid`, `thumbnailUrl`, etc.).
- `trigger_workflow.py` / `trigger_workflow.ps1` — manually dispatch the `youtube_outlier_tracker.yml` GitHub Actions workflow via the API (needs `GITHUB_TOKEN`).
- `grok_swipe_pack.py` — on-demand export of the top N (default 8) rows from one dashboard tab into a small JSON/CSV + saved-thumbnails pack, sized for handing to an external tool (built for Grok's own requested format: YouTube URL, outlier score, title, niche, thumbnail, 1-line "why it won" note). Only automates the mechanical half — selecting rows and downloading thumbnails; the `note` field is left blank since writing it needs a vision-capable model to actually look at each thumbnail (ask Claude to fill those in after running it). Output goes to `grok-swipe-pack/` (gitignored, regenerated each run). No credentials needed. `python grok_swipe_pack.py --tab outliers --count 8`.

### niche-long-form/
- `long_form_tracker.py` — thresholds and `is_outlier()` for the niche long-form output. Imported by `youtube_outliers.py`, which writes its result to `niche-long-form/data.json`.

### niche-short-form/
- `short_form_tracker.py` — Shorts-specific thresholds, `SHORTS_LOOKBACK_DAYS`, `is_outlier_short()`. Imported by `youtube_outliers.py`, which writes its result to `niche-short-form/data.json`.

Both general tabs' bar is a simple absolute one: **views >= 500,000, published within the last 90 days** — not a relative-to-channel-size outlier multiplier (that's what the niche tabs use). A video only stays in the swipe file as long as it's still within that 90-day window; `curate_general_with_claude.py` prunes anything older on every run. Every entry carries a `published_at` (YYYY-MM-DD) field for exactly this check.

- `curate_general_with_claude.py` (in the `outlier-tracking/` root, shared by both tabs via `--tab long-form|short-form`) — the automated weekly path: scans fresh candidates against the 500K/90-day bar, prunes stale entries, dedupes against what's already in the file, sends survivors (including their actual thumbnail *images*, not just text — Claude needs to see the image to judge whether it's real photography vs. gaming/animation/AI-slop) to the Claude API for selection and full cold-approach writeup, then rewrites the target `SWIPE_FILE` and regenerates `data.json`. Needs `YOUTUBE_API_KEY` and `ANTHROPIC_API_KEY`. Runs via `.github/workflows/general_outlier_curation.yml`, weekly, both tabs as sequential matrix jobs (never parallel, so their commits/pushes can't race).

### general-long-form/
- `general_outlier_finder.py` — the original **manual** discovery tool: scans for cross-niche outlier candidates using a relative-outlier multiplier bar (not the 500K/90-day bar above) and prints `CANDIDATE` log lines for a human/Claude to review by hand. Still useful for one-off manual curation sessions; the weekly automation above doesn't use it. Needs `YOUTUBE_API_KEY` only.
- `general_outlier_swipe_file.py` — writes `general-long-form/data.json` from its `SWIPE_FILE` list (now populated by both manual curation and the weekly automation above), each with a cold-approach title/thumbnail translation. Needs no credentials at all — just dumps its own Python data to JSON.

### general-short-form/
- `general_shorts_finder.py` — the Shorts-only sibling of the manual long-form finder above; scans for ultra-viral cross-niche Shorts using its own relative multiplier bar. Imports `KEYWORDS` from `general-long-form/general_outlier_finder.py`. Manual-curation tool, not used by the weekly automation. Needs `YOUTUBE_API_KEY` only.
- `general_shorts_swipe_file.py` — writes `general-short-form/data.json` from its `SWIPE_FILE` list. Needs no credentials.

## Cross-folder imports

Folder names use hyphens (not valid in Python identifiers), so scripts don't use package-style imports. Each script that needs code from a sibling/parent folder inserts that folder onto `sys.path` via `os.path.dirname(__file__)` before importing — e.g. `general-short-form/general_shorts_finder.py` inserts both the `outlier-tracking/` root (for `common.py`) and `general-long-form/` (for `general_outlier_finder.py`'s `KEYWORDS`). Follow this same pattern for any new cross-folder import here.

## Dashboard sync

The published "Outlier Tracker" dashboard reads its own bundled `data.json` (shape: `{outliers, shorts, generalOutliers, generalShorts}`), which is a manual merge of these 4 subfolders' `data.json` files. All 4 tabs use locally-fetched thumbnail images uploaded to the artifact as `thumbs/<vid>.jpg` — the artifact sandbox's CSP silently blocks hotlinking images from external hosts (YouTube's CDN included), so a thumbnail must be downloaded and uploaded as one of the artifact's own files or it just won't render. Syncing the dashboard to the latest repo data is a manual/Claude-driven step done on request, not automatic — the repo's `data.json` files are the source of truth, the dashboard is a snapshot of them.

## Scope rules
- Keep this folder about *finding and recording outliers* only. Shorts hook/opener/thumbnail *ideation* research and Instagram posting live in their own folders — don't cross-import from here (`shorts-hook-research/` is pure ideation notes now; the Shorts outlier finder/writer moved into `general-short-form/` above).
- Corresponding CI workflows live in `.github/workflows/`: `youtube_outlier_tracker.yml` (niche tabs, weekly, fully automated), `general_outlier_curation.yml` (both general tabs, weekly, fully automated via `curate_general_with_claude.py`), plus the older manual-dispatch-only `general_outlier_finder.yml` / `general_outlier_swipe_file.yml` / `general_shorts_finder.yml` / `general_shorts_swipe_file.yml` for one-off manual curation runs. All invoke these scripts by path from the repo root — if you rename or move a script here, update the matching workflow's `run:` line too. Workflows that write data each have a "Commit updated data" step after the script runs — needs `permissions: contents: write` (already set).
