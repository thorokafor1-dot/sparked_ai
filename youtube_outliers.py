import os
import sys
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from openpyxl import Workbook


API_KEY = os.getenv("YOUTUBE_API_KEY", "")
KEYWORDS = [k.strip() for k in os.getenv("YOUTUBE_KEYWORDS", "cold approach,infield").split(",") if k.strip()]
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "90"))
OUTPUT_FILE = os.getenv("OUTPUT_FILE", "youtube_outliers.xlsx")
MAX_RESULTS_PER_KEYWORD = int(os.getenv("MAX_RESULTS_PER_KEYWORD", "10"))
MIN_VIEW_THRESHOLD = int(os.getenv("MIN_VIEW_THRESHOLD", "50000"))
MIN_SUBSCRIBER_THRESHOLD = int(os.getenv("MIN_SUBSCRIBER_THRESHOLD", "50000"))
HIGH_VIEW_THRESHOLD = int(os.getenv("HIGH_VIEW_THRESHOLD", "100000"))


def build_youtube_client():
    if not API_KEY:
        return None
    return build("youtube", "v3", developerKey=API_KEY)


def execute_request(request):
    try:
        return request.execute()
    except HttpError as exc:
        print(f"YouTube API error: {exc}")
        return None
    except Exception as exc:  # pragma: no cover - defensive fallback
        print(f"Unexpected YouTube API failure: {exc}")
        return None


def search_videos(youtube, keyword: str) -> List[Dict[str, Any]]:
    published_after = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    request = youtube.search().list(
        q=keyword,
        part="snippet",
        type="video",
        maxResults=MAX_RESULTS_PER_KEYWORD,
        order="date",
        publishedAfter=published_after,
        fields="items(id/videoId,snippet/title,snippet/channelTitle,snippet/publishedAt,snippet/thumbnails/default/url)",
    )
    response = execute_request(request)
    if not response:
        return []
    return response.get("items", [])


def get_video_stats(youtube, video_id: str) -> Dict[str, Any]:
    request = youtube.videos().list(
        part="statistics,snippet",
        id=video_id,
        fields="items(id,statistics/viewCount,statistics/likeCount,snippet/title,snippet/channelId,snippet/channelTitle,snippet/thumbnails/medium/url)",
    )
    response = execute_request(request)
    if not response:
        return {}
    items = response.get("items", [])
    if not items:
        return {}
    return items[0]


def get_channel_stats(youtube, channel_id: str) -> Dict[str, Any]:
    request = youtube.channels().list(
        part="statistics",
        id=channel_id,
        fields="items(id,statistics/subscriberCount)",
    )
    response = execute_request(request)
    if not response:
        return {}
    items = response.get("items", [])
    if not items:
        return {}
    return items[0]


def is_outlier(view_count: int, subscriber_count: int) -> tuple[bool, str]:
    if view_count > HIGH_VIEW_THRESHOLD:
        return True, f"Over {HIGH_VIEW_THRESHOLD:,} views"
    if view_count > MIN_VIEW_THRESHOLD and subscriber_count < MIN_SUBSCRIBER_THRESHOLD:
        return True, f"{MIN_VIEW_THRESHOLD:,}+ views on a channel under {MIN_SUBSCRIBER_THRESHOLD:,} subscribers"
    return False, ""


def create_workbook(rows: List[Dict[str, Any]]) -> Workbook:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Outliers"
    headers = [
        "Title",
        "Channel",
        "Published At",
        "Views",
        "Subscribers",
        "Keyword",
        "Video URL",
        "Thumbnail URL",
        "Reason",
    ]
    sheet.append(headers)
    for row in rows:
        sheet.append([
            row.get("title", ""),
            row.get("channel", ""),
            row.get("published_at", ""),
            row.get("views", ""),
            row.get("subscribers", ""),
            row.get("keyword", ""),
            row.get("video_url", ""),
            row.get("thumbnail_url", ""),
            row.get("reason", ""),
        ])
    return workbook


def main() -> None:
    rows: List[Dict[str, Any]] = []
    youtube = build_youtube_client()

    if not youtube:
        workbook = create_workbook([])
        workbook.save(OUTPUT_FILE)
        print(f"No YouTube API key found. Created empty workbook at {OUTPUT_FILE}")
        return

    for keyword in KEYWORDS:
        for item in search_videos(youtube, keyword):
            video_id = item.get("id", {}).get("videoId")
            if not video_id:
                continue

            stats = get_video_stats(youtube, video_id)
            if not stats:
                continue

            view_count = int(stats.get("statistics", {}).get("viewCount", 0) or 0)
            channel_id = stats.get("snippet", {}).get("channelId")
            channel_title = stats.get("snippet", {}).get("channelTitle", "")
            thumbnail_url = (stats.get("snippet", {}).get("thumbnails", {}) or {}).get("medium", {}).get("url", "")
            published_at = stats.get("snippet", {}).get("publishedAt", "")

            subscriber_count = 0
            if channel_id:
                channel_stats = get_channel_stats(youtube, channel_id)
                subscriber_count = int(channel_stats.get("statistics", {}).get("subscriberCount", 0) or 0)

            is_flagged, reason = is_outlier(view_count, subscriber_count)
            if not is_flagged:
                continue

            rows.append(
                {
                    "title": stats.get("snippet", {}).get("title", ""),
                    "channel": channel_title,
                    "published_at": published_at,
                    "views": view_count,
                    "subscribers": subscriber_count,
                    "keyword": keyword,
                    "video_url": f"https://www.youtube.com/watch?v={video_id}",
                    "thumbnail_url": thumbnail_url,
                    "reason": reason,
                }
            )

    workbook = create_workbook(rows)
    workbook.save(OUTPUT_FILE)
    print(f"Wrote {len(rows)} outlier videos to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
