---
name: ctr-ranking
description: Rank our own YouTube videos by thumbnail click-through rate (CTR) and impressions. Use when the user asks which videos or thumbnails get clicked most, wants a CTR ranking, or wants to compare thumbnail/title performance.
---

# Own-channel CTR ranking

Details live in `channel-analytics/claude.md`. Script: `channel-analytics/ctr.py`.

## Steps
1. **Run:** `python channel-analytics/ctr.py` (add `--min-impressions 500` to hide low-sample videos). It syncs any new daily report files, then ranks.
2. **Read** `channel-analytics/reports/ctr_<date>.md` and give the user the ranking: top and bottom by CTR, with impressions next to each so they can see how much to trust it. Split shorts and long-form when comparing, since shorts CTR comes mostly from the feed and isn't comparable.
3. **Feed lessons forward:** what the top-CTR thumbnails and titles have in common goes to the thumbnail and title guidance (`make-thumbnail` skill, video-ideation docs). Own channel is diagnostic only, never model data (see memory).

## Gotchas (keep this list updated)
- CTR is NOT in the YouTube Analytics API (`impressions` is "Unknown identifier", `videoThumbnailImpressions*` is "query not supported"). It only comes from the **Reporting API** report `channel_reach_basic_a1`.
- Reporting job `229a9d71-72b1-4244-8b18-615893c1dc5c` was created 2026-10-04. YouTube produces one report file per data day about 24 to 48h behind, so the ranking only covers days since the job started (plus whatever backfill YouTube adds). It grows on its own; old files are cached in `reports/reach_raw/`.
- Reporting files expire on Google's side after a while, so run the script at least every couple of weeks or the cache gets gaps.
- Needs the YouTube Reporting API enabled on Cloud project 777575800011 (done 2026-10-04).
