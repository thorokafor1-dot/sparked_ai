"""Searches YouTube across niches outside cold-approach for genuine statistical
outliers (100x+ a channel's own average views) published in the last 90 days.

This only surfaces candidates — it does not judge whether a video's packaging
cleanly translates into a cold-approach video idea. That curation step happens
afterward: a human (or Claude) reviews the printed CANDIDATE lines in this run's
log, picks the ones with real translation potential, writes the packaging
analysis + cold-approach translation, and adds them to general_outlier_swipe_file.py.

Deliberately scoped to niches with human/social/narrative dynamics (challenge,
stakes, deception, transformation, fear, documentary, forbidden access,
generosity) rather than truly "any" niche — those are the formats that have a
shot at translating into a cold-approach idea. Tutorial/review/gaming/music
content is excluded from the keyword list for that reason.
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
)

LOOKBACK_DAYS = int(os.getenv("GENERAL_LOOKBACK_DAYS", "90"))
MULTIPLIER_THRESHOLD = float(os.getenv("GENERAL_MULTIPLIER_THRESHOLD", "100"))
MIN_VIEW_THRESHOLD = int(os.getenv("GENERAL_MIN_VIEW_THRESHOLD", "100000"))
MAX_RESULTS_PER_KEYWORD = int(os.getenv("GENERAL_MAX_RESULTS_PER_KEYWORD", "25"))

# Niches chosen for social/narrative structure that maps onto a cold-approach video:
# stakes & challenge, deception/dramatic irony, transformation, fear, documentary
# underdog arcs, forbidden access/mystery, generosity/karma, social experiments.
KEYWORDS = [
    "porch pirate revenge prank",
    "extreme survival challenge",
    "social experiment hidden camera",
    "scam baiting expose",
    "abandoned mansion exploring",
    "true horror story animated",
    "underdog documentary rise",
    "impossible trick shot",
    "convinced stranger prank",
    "giving away money surprise",
    "weight loss transformation documentary",
    "revenge on bully",
    "confronting my fear",
    "asking strangers for help experiment",
    "last to leave challenge",
]


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

    print(f"Scanning {len(KEYWORDS)} keywords, lookback={LOOKBACK_DAYS} days, "
          f"multiplier>={MULTIPLIER_THRESHOLD}x, min views={MIN_VIEW_THRESHOLD:,}")

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

            channel_id = stats.get("snippet", {}).get("channelId")
            channel_title = stats.get("snippet", {}).get("channelTitle", "")
            title = stats.get("snippet", {}).get("title", "")
            thumbnail_url = (stats.get("snippet", {}).get("thumbnails", {}) or {}).get("medium", {}).get("url", "")
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
            if avg_views <= 0:
                continue

            multiplier = view_count / avg_views
            print(f"Checked: '{title}' ({channel_title}) - {view_count:,} views, "
                  f"{multiplier:.1f}x channel avg")

            if multiplier < MULTIPLIER_THRESHOLD:
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
                "multiplier": round(multiplier, 1),
                "published_at": published_at,
                "thumbnail_url": thumbnail_url,
            }
            candidates.append(candidate)
            # Marker line so the run log can be grepped for structured results.
            print(f"CANDIDATE: {json.dumps(candidate)}")

    candidates.sort(key=lambda c: c["multiplier"], reverse=True)
    print(f"\nFound {len(candidates)} candidates at {MULTIPLIER_THRESHOLD}x+ "
          f"in the last {LOOKBACK_DAYS} days.")


if __name__ == "__main__":
    main()
