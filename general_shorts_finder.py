"""Searches YouTube Shorts across niches outside cold-approach for viral, short-form
packaging published in the last 90 days — a shorts-only sibling of
general_outlier_finder.py.

First pass used the long-form KEYWORDS list verbatim with much higher bars (5M views,
20x subs, 50x avg). That returned nearly the same ~40 candidates on a re-scan days
later — the pool was tapped out, and most were duplicates of General Outlier Models
entries or low-value edit-clip channels (Roblox/k-drama/manhwa recuts). Two fixes:
  1. Added SHORTS_NATIVE_KEYWORDS — formats that skew short-form specifically
     (satisfying reveals, before/after transformations, plot-twist storytimes, POV
     moments) that the long-form-oriented list doesn't reach.
  2. Lowered the bars (2M views / 10x subs / 25x avg, from 5M / 20x / 50x) — still well
     above the main cold-approach Shorts tab's bars (300K / 5x / 10x), so "ultra viral"
     is preserved relative to that tab, just not so strict the candidate pool starves.

Like general_outlier_finder.py, this only surfaces candidates as SHORTCANDIDATE log
lines — picking which ones cleanly translate to cold approach and writing the analysis
is a manual/Claude curation step, done afterward in general_shorts_swipe_file.py.
"""
import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from youtube_outliers import (
    build_youtube_client,
    execute_request,
    get_video_stats,
    get_channel_stats,
    is_short_video,
    is_english_title,
)
from general_outlier_finder import KEYWORDS as LONG_FORM_KEYWORDS

SHORTS_NATIVE_KEYWORDS = [
    "satisfying transformation reveal shorts",
    "before and after transformation shorts",
    "plot twist storytime shorts",
    "unexpected reaction shorts",
    "relatable pov shorts",
    "wholesome surprise shorts",
    "green screen reveal shorts",
    "life hack viral shorts",
    "glow up reveal shorts",
    "shocking reveal shorts",
    "comedy sketch viral shorts",
    "real reaction shorts",
]
KEYWORDS = LONG_FORM_KEYWORDS + SHORTS_NATIVE_KEYWORDS

LOOKBACK_DAYS = int(os.getenv("SHORTS_GENERAL_LOOKBACK_DAYS", "90"))
ABSOLUTE_VIEW_THRESHOLD = int(os.getenv("SHORTS_GENERAL_ABSOLUTE_VIEW_THRESHOLD", "2000000"))
SUBSCRIBER_MULTIPLIER_THRESHOLD = float(os.getenv("SHORTS_GENERAL_SUBSCRIBER_MULTIPLIER_THRESHOLD", "10"))
AVERAGE_MULTIPLIER_THRESHOLD = float(os.getenv("SHORTS_GENERAL_AVERAGE_MULTIPLIER_THRESHOLD", "25"))
MIN_VIEW_THRESHOLD = int(os.getenv("SHORTS_GENERAL_MIN_VIEW_THRESHOLD", "250000"))
MAX_RESULTS_PER_KEYWORD = int(os.getenv("SHORTS_GENERAL_MAX_RESULTS_PER_KEYWORD", "50"))


def search_videos(youtube, keyword: str) -> List[Dict[str, Any]]:
    published_after = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    request = youtube.search().list(
        q=keyword,
        part="snippet",
        type="video",
        maxResults=MAX_RESULTS_PER_KEYWORD,
        order="viewCount",
        publishedAfter=published_after,
        fields="items(id/videoId,snippet/title,snippet/channelTitle,snippet/publishedAt)",
    )
    response = execute_request(request)
    if not response:
        return []
    return response.get("items", [])


def main() -> None:
    youtube = build_youtube_client()
    if not youtube:
        print("No YouTube API key found. Skipping search.")
        return

    print(f"Scanning {len(KEYWORDS)} keywords for ULTRA-VIRAL SHORTS, lookback={LOOKBACK_DAYS} days. "
          f"Qualifies if: views>={ABSOLUTE_VIEW_THRESHOLD:,} OR "
          f"views>={SUBSCRIBER_MULTIPLIER_THRESHOLD}x subscribers OR "
          f"views>={AVERAGE_MULTIPLIER_THRESHOLD}x channel avg (min views={MIN_VIEW_THRESHOLD:,})")

    seen_video_ids = set()
    candidates: List[Dict[str, Any]] = []

    for keyword in KEYWORDS:
        for item in search_videos(youtube, keyword):
            video_id = item.get("id", {}).get("videoId")
            if not video_id or video_id in seen_video_ids:
                continue

            stats = get_video_stats(youtube, video_id)
            if not stats:
                continue

            view_count = int(stats.get("statistics", {}).get("viewCount", 0) or 0)
            if view_count < MIN_VIEW_THRESHOLD:
                continue

            title = stats.get("snippet", {}).get("title", "")
            if not is_english_title(title):
                continue

            tags = stats.get("snippet", {}).get("tags", []) or []
            duration = stats.get("contentDetails", {}).get("duration", "")
            medium_thumbnail = (stats.get("snippet", {}).get("thumbnails", {}) or {}).get("medium", {}) or {}
            thumbnail_width = medium_thumbnail.get("width")
            thumbnail_height = medium_thumbnail.get("height")

            if not is_short_video(duration, title, tags, thumbnail_width, thumbnail_height):
                continue

            channel_id = stats.get("snippet", {}).get("channelId")
            channel_title = stats.get("snippet", {}).get("channelTitle", "")
            thumbnail_url = medium_thumbnail.get("url", "")
            published_at = stats.get("snippet", {}).get("publishedAt", "")

            if not channel_id:
                continue

            channel_stats = get_channel_stats(youtube, channel_id)
            ch_statistics = channel_stats.get("statistics", {})
            subscriber_count = int(ch_statistics.get("subscriberCount", 0) or 0)
            channel_total_views = int(ch_statistics.get("viewCount", 0) or 0)
            channel_video_count = int(ch_statistics.get("videoCount", 0) or 0)

            if channel_video_count <= 0 or channel_total_views <= 0:
                continue

            avg_views = channel_total_views / channel_video_count
            avg_multiplier = (view_count / avg_views) if avg_views > 0 else 0
            sub_multiplier = (view_count / subscriber_count) if subscriber_count > 0 else 0

            reasons = []
            if view_count >= ABSOLUTE_VIEW_THRESHOLD:
                reasons.append(f"{view_count/1_000_000:.1f}M views")
            if sub_multiplier >= SUBSCRIBER_MULTIPLIER_THRESHOLD:
                reasons.append(f"{sub_multiplier:.1f}x subscribers")
            if avg_multiplier >= AVERAGE_MULTIPLIER_THRESHOLD:
                reasons.append(f"{avg_multiplier:.1f}x channel avg")

            print(f"Checked SHORT: '{title}' ({channel_title}) - {view_count:,} views, "
                  f"{sub_multiplier:.1f}x subs, {avg_multiplier:.1f}x avg")

            if not reasons:
                continue

            seen_video_ids.add(video_id)
            candidate = {
                "title": title,
                "channel": channel_title,
                "video_url": f"https://www.youtube.com/watch?v={video_id}",
                "niche_keyword": keyword,
                "views": view_count,
                "subscribers": subscriber_count,
                "channel_avg_views": round(avg_views),
                "sub_multiplier": round(sub_multiplier, 1),
                "avg_multiplier": round(avg_multiplier, 1),
                "reasons": reasons,
                "published_at": published_at,
                "thumbnail_url": thumbnail_url,
            }
            candidates.append(candidate)
            # Marker line so the run log can be grepped for structured results.
            print(f"SHORTCANDIDATE: {json.dumps(candidate)}")

    candidates.sort(key=lambda c: c["views"], reverse=True)
    print(f"\nFound {len(candidates)} ultra-viral short candidates in the last {LOOKBACK_DAYS} days.")


if __name__ == "__main__":
    main()
