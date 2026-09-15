# Outlier Tracking

Single job of this folder: find YouTube videos that are outperforming their channel/niche baseline ("outliers") and write the results to Google Sheets.

## Scripts
- `youtube_outliers.py` — main cold-approach niche tracker (long-form + Shorts). Reads `YOUTUBE_API_KEY`, `LOOKBACK_DAYS`, `SHORTS_LOOKBACK_DAYS`, `GOOGLE_SERVICE_ACCOUNT_JSON`, `GOOGLE_SPREADSHEET_ID`, `GOOGLE_SHEET_NAME` from env.
- `general_outlier_finder.py` — scans for cross-niche outlier candidates (long-form), independent of the cold-approach niche list.
- `general_outlier_swipe_file.py` — writes the "General Outlier Models" tab from candidates found above.
- `export_sheet_data.py` — exports existing sheet tab data out of the spreadsheet.
- `trigger_workflow.py` / `trigger_workflow.ps1` — manually dispatch the `youtube_outlier_tracker.yml` GitHub Actions workflow via the API (needs `GITHUB_TOKEN`).

## Scope rules
- Keep this folder about *finding and recording outliers* only. Shorts hook/ideation research and Instagram posting live in their own folders — don't cross-import from here.
- Corresponding CI workflows live in `.github/workflows/` (`youtube_outlier_tracker.yml`, `general_outlier_finder.yml`, `general_outlier_swipe_file.yml`, `export_sheet_data.yml`) and invoke these scripts by path from the repo root — if you rename or move a script here, update the matching workflow's `run:` line too.
