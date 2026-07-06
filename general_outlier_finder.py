"""Searches YouTube across niches outside cold-approach for videos with genuinely
strong packaging, published in the last 90 days.

"100x a channel's own average" (the original signal) structurally can only ever
flag a small/mid channel having a fluke breakout — a mega-channel like MrBeast or
Mark Rober can never trigger it, since their own average is already huge, even
though their packaging is often the best in the sample (confirmed: the first scan's
log had 250M/165M/69M-view videos in it that never surfaced because of this). So
three independent signals are used instead, any one of which qualifies:
  1. Absolute reach: 1M+ views regardless of channel size — proves broad appeal on
     its own, and is how a big channel's strong packaging shows up.
  2. Audience breakout: views >= 5x the channel's subscriber count — reached far
     beyond the built-in audience, a direct sign the click came from the
     thumbnail/title, not brand loyalty.
  3. Self-breakout: views >= 20x the channel's own average views per video —
     catches a normally-unremarkable channel nailing packaging once. (Lowered from
     100x based on real data: the highest multipliers actually found in two scans
     were 115x and 44x — 100x is right at the edge of what occurs at all.)

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
ABSOLUTE_VIEW_THRESHOLD = int(os.getenv("GENERAL_ABSOLUTE_VIEW_THRESHOLD", "1000000"))
SUBSCRIBER_MULTIPLIER_THRESHOLD = float(os.getenv("GENERAL_SUBSCRIBER_MULTIPLIER_THRESHOLD", "5"))
AVERAGE_MULTIPLIER_THRESHOLD = float(os.getenv("GENERAL_AVERAGE_MULTIPLIER_THRESHOLD", "20"))
MIN_VIEW_THRESHOLD = int(os.getenv("GENERAL_MIN_VIEW_THRESHOLD", "100000"))
MAX_RESULTS_PER_KEYWORD = int(os.getenv("GENERAL_MAX_RESULTS_PER_KEYWORD", "50"))

# Niches chosen for social/narrative structure that maps onto a cold-approach video:
# stakes & challenge, deception/dramatic irony, transformation, fear, documentary
# underdog arcs, forbidden access/mystery, generosity/karma, social experiments.
# A first pass at 15 keywords found nothing above 44x, so this list is deliberately
# much wider to hunt for the rarer 100x hits the 90-day window allows.
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
    "reading minds street experiment",
    "compliments to strangers reaction",
    "free hugs experiment",
    "handing out cash to strangers",
    "would they help a stranger test",
    "exposing a cheater confrontation",
    "extreme makeover reveal reaction",
    "hardest conversation of my life",
    "telling my crush how I feel",
    "rejected on camera compilation",
    "surprising my parents with news",
    "quitting my job on camera",
    "moving to a new city alone documentary",
    "talking to homeless people stories",
    "first date blind experiment",
    "confessing secret on camera",
    "starting over from nothing documentary",
    "convincing people I'm famous prank",
    "disguise social experiment",
    "asking out strangers reaction",
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

    print(f"Scanning {len(KEYWORDS)} keywords, lookback={LOOKBACK_DAYS} days. "
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
            avg_multiplier = (view_count / avg_views) if avg_views > 0 else 0
            sub_multiplier = (view_count / subscriber_count) if subscriber_count > 0 else 0

            reasons = []
            if view_count >= ABSOLUTE_VIEW_THRESHOLD:
                reasons.append(f"{view_count/1_000_000:.1f}M views")
            if sub_multiplier >= SUBSCRIBER_MULTIPLIER_THRESHOLD:
                reasons.append(f"{sub_multiplier:.1f}x subscribers")
            if avg_multiplier >= AVERAGE_MULTIPLIER_THRESHOLD:
                reasons.append(f"{avg_multiplier:.1f}x channel avg")

            print(f"Checked: '{title}' ({channel_title}) - {view_count:,} views, "
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
            print(f"CANDIDATE: {json.dumps(candidate)}")

    candidates.sort(key=lambda c: c["views"], reverse=True)
    print(f"\nFound {len(candidates)} candidates in the last {LOOKBACK_DAYS} days.")


if __name__ == "__main__":
    main()
