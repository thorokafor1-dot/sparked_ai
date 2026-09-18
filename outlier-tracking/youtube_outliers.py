"""Entry point for the niche-specific tracker: one shared YouTube search pass across
both in-person and video-chat keywords (common.py), classified into long-form vs Shorts
and scored/written via niche-long-form/long_form_tracker.py and
niche-short-form/short_form_tracker.py respectively. Kept as a single scan (rather than
two independent per-format scripts) to avoid roughly doubling YouTube API quota usage
for the same underlying search results.
"""
import os
import sys
from datetime import datetime, timezone
from typing import Any, Dict, List

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "niche-long-form"))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "niche-short-form"))

import common
import long_form_tracker
import short_form_tracker


def to_dashboard_row(row: Dict[str, Any]) -> Dict[str, Any]:
    """Map internal row field names to the shape the dashboard's data.json expects."""
    return {
        "title": row["title"],
        "channel": row["channel"],
        "publishedAt": row["published_at"],
        "duration": row["duration"],
        "views": row["views"],
        "subscribers": row["subscribers"],
        "keyword": row["keyword"],
        "format": row["format"],
        "videoUrl": row["video_url"],
        "vid": row["vid"],
        "thumbnailUrl": row["thumbnail_url"],
        "reason": row["reason"],
        "score": row["score"],
    }


def main() -> None:
    rows: List[Dict[str, Any]] = []
    shorts_rows: List[Dict[str, Any]] = []
    seen_video_ids = set()  # Track videos we've already added to avoid duplicates
    youtube = common.build_youtube_client()

    if not youtube:
        print("No YouTube API key found. Skipping YouTube search.")
        return

    print(f"Searching In-Person keywords: {', '.join(common.KEYWORDS)}")
    print(f"Searching Video Chat keywords: {', '.join(common.VIDEO_CHAT_KEYWORDS)}")
    print(f"Searching Explainer keywords: {', '.join(common.EXPLAINER_KEYWORDS)}")
    print(f"Lookback period: {common.LOOKBACK_DAYS} days")
    print(f"High view threshold: {long_form_tracker.HIGH_VIEW_THRESHOLD:,}")
    print()

    search_targets = (
        [(k, "In-Person") for k in common.KEYWORDS]
        + [(k, "Video Chat") for k in common.VIDEO_CHAT_KEYWORDS]
        + [(k, "Explainer") for k in common.EXPLAINER_KEYWORDS]
    )

    for keyword, format_label in search_targets:
        for item in common.search_videos(youtube, keyword):
            video_id = item.get("id", {}).get("videoId")
            if not video_id:
                continue

            # Skip if we've already added this video
            if video_id in seen_video_ids:
                continue

            stats = common.get_video_stats(youtube, video_id)
            if not stats:
                continue

            view_count = int(stats.get("statistics", {}).get("viewCount", 0) or 0)
            channel_id = stats.get("snippet", {}).get("channelId")
            channel_title = stats.get("snippet", {}).get("channelTitle", "")
            thumbnail = common.pick_thumbnail(stats.get("snippet", {}).get("thumbnails", {}))
            thumbnail_url = thumbnail.get("url", "")
            thumbnail_width = thumbnail.get("width")
            thumbnail_height = thumbnail.get("height")
            raw_published_at = stats.get("snippet", {}).get("publishedAt", "")
            published_dt = None
            try:
                if raw_published_at:
                    published_dt = datetime.strptime(raw_published_at, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
                    published_at = published_dt.strftime("%b %d, %Y")
                else:
                    published_at = ""
            except ValueError:
                published_at = raw_published_at

            subscriber_count = 0
            channel_total_views = 0
            channel_video_count = 0
            if channel_id:
                channel_stats = common.get_channel_stats(youtube, channel_id)
                ch_statistics = channel_stats.get("statistics", {})
                subscriber_count = int(ch_statistics.get("subscriberCount", 0) or 0)
                channel_total_views = int(ch_statistics.get("viewCount", 0) or 0)
                channel_video_count = int(ch_statistics.get("videoCount", 0) or 0)

            # Debug: Print all found videos
            title = stats.get("snippet", {}).get("title", "")
            print(f"Found video: '{title}' - Views: {view_count:,}, Subscribers: {subscriber_count:,}, Channel: {channel_title}")

            duration = stats.get("contentDetails", {}).get("duration", "")
            tags = stats.get("snippet", {}).get("tags", []) or []
            is_short = common.is_short_video(duration, title, tags, thumbnail_width, thumbnail_height)

            if not common.is_english_title(title):
                print(f"  → Skipped (non-English title)")
                continue

            # Filter out unrelated content based on video tags (with title fallback)
            category_id = stats.get("snippet", {}).get("categoryId", "")
            if not common.is_relevant_tags(tags, title, category_id, keyword, channel_title):
                print(f"  → Skipped (not relevant to cold approach/pickup niche)")
                continue

            # Confirm a duration-based Short flag against YouTube's own /shorts/ routing —
            # catches a video under 3 minutes that YouTube itself doesn't treat as a Short.
            # Unofficial signal, so only ever downgrades a confirmed non-Short; a failed
            # request (None) falls back to trusting the duration-based flag as-is.
            if is_short:
                confirmed = common.confirm_is_short(video_id)
                if confirmed is False:
                    print(f"  → Reclassified as long-form (not a real Short per YouTube)")
                    is_short = False

            # Content wins over search origin: an in-person search term can still surface
            # a video-chat video (e.g. "approaching random girls" matching an Omegle title),
            # so force the Format tag to Video Chat whenever the platform is actually named.
            if common.is_video_chat_content(title, tags):
                format_label = "Video Chat"

            row_data = {
                "title": title,
                "channel": channel_title,
                "channel_key": channel_id or channel_title,
                "published_at": published_at,
                "duration": common.format_duration(duration),
                "views": view_count,
                "subscribers": subscriber_count,
                "keyword": keyword,
                "format": format_label,
                "video_url": f"https://www.youtube.com/watch?v={video_id}",
                "vid": video_id,
                "thumbnail_url": thumbnail_url,
            }

            if is_short:
                if published_dt is None:
                    continue
                days_since_published = (datetime.now(timezone.utc) - published_dt).total_seconds() / 86400
                if days_since_published > short_form_tracker.SHORTS_LOOKBACK_DAYS:
                    print(f"  → Skipped (short older than {short_form_tracker.SHORTS_LOOKBACK_DAYS} days)")
                    continue

                is_flagged, reason, score = short_form_tracker.is_outlier_short(view_count, days_since_published, subscriber_count, channel_total_views, channel_video_count)
                if not is_flagged:
                    continue

                seen_video_ids.add(video_id)
                shorts_rows.append({**row_data, "reason": reason, "score": score})
            else:
                is_flagged, reason, score = long_form_tracker.is_outlier(view_count, subscriber_count, channel_total_views, channel_video_count)
                if not is_flagged:
                    continue

                seen_video_ids.add(video_id)
                rows.append({**row_data, "reason": reason, "score": score})

    # Cap outliers per channel so a few prolific channels don't crowd out variety,
    # then sort by score so the strongest examples surface first. Shorts aren't
    # capped in total count, just kept diverse across channels.
    capped_rows = common.cap_and_sort_by_channel(rows, long_form_tracker.PER_CHANNEL_CAP)
    capped_shorts_rows = common.cap_and_sort_by_channel(shorts_rows, short_form_tracker.SHORTS_PER_CHANNEL_CAP)

    this_dir = os.path.dirname(os.path.abspath(__file__))
    long_form_path = os.path.join(this_dir, "niche-long-form", "data.json")
    short_form_path = os.path.join(this_dir, "niche-short-form", "data.json")

    common.write_rows_to_json(long_form_path, [to_dashboard_row(r) for r in capped_rows])
    print(f"Wrote {len(capped_rows)} outlier videos to {long_form_path}")

    common.write_rows_to_json(short_form_path, [to_dashboard_row(r) for r in capped_shorts_rows])
    print(f"Wrote {len(capped_shorts_rows)} outlier shorts to {short_form_path}")


if __name__ == "__main__":
    main()
