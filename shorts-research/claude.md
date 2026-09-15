# Shorts Hook Research

Single job of this folder: research what makes Shorts go viral — hooks, openers, thumbnails — and collect it as reference material, separate from the long-form outlier tracker.

## Contents
- `general_shorts_finder.py` — scans for ultra-viral cross-niche Shorts candidates. Reads `YOUTUBE_API_KEY` from env.
- `general_shorts_swipe_file.py` — writes the "General Shorts Outliers" tab from candidates found above.
- `ideation_10_openers.md` — hook/opener ideation notes.
- `thumbnail_comparison.png` — thumbnail research reference image.

## Scope rules
- This folder is research/ideation for Shorts hooks and thumbnails — it doesn't post anything and doesn't track long-form outliers. Posting lives in `ig-automation/`, long-form tracking in `outlier-tracking/`.
- The corresponding CI workflows (`general_shorts_finder.yml`, `general_shorts_swipe_file.yml`) invoke these scripts by path from the repo root — update the workflow's `run:` line if a script here is renamed or moved.
