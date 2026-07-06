import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


API_KEY = os.getenv("YOUTUBE_API_KEY", "")
KEYWORDS = [k.strip() for k in os.getenv("YOUTUBE_KEYWORDS", "picking up girls,cold approach,approach women,daygame,street approach").split(",") if k.strip()]
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "90"))
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_SPREADSHEET_ID = os.getenv("GOOGLE_SPREADSHEET_ID", "").strip()
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Outliers")
MAX_RESULTS_PER_KEYWORD = int(os.getenv("MAX_RESULTS_PER_KEYWORD", "50"))
MIN_VIEW_THRESHOLD = int(os.getenv("MIN_VIEW_THRESHOLD", "50000"))
MIN_SUBSCRIBER_THRESHOLD = int(os.getenv("MIN_SUBSCRIBER_THRESHOLD", "50000"))
HIGH_VIEW_THRESHOLD = int(os.getenv("HIGH_VIEW_THRESHOLD", "50000"))
OUTLIER_MULTIPLIER_THRESHOLD = int(os.getenv("OUTLIER_MULTIPLIER_THRESHOLD", "1000"))

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
HEADERS = [
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
        order="viewCount",
        publishedAfter=published_after,
        fields="items(id/videoId,snippet/title,snippet/channelTitle,snippet/publishedAt,snippet/thumbnails/default/url)",
    )
    response = execute_request(request)
    if not response:
        return []
    return response.get("items", [])


def get_video_stats(youtube, video_id: str) -> Dict[str, Any]:
    request = youtube.videos().list(
        part="statistics,snippet,contentDetails",
        id=video_id,
        fields="items(id,statistics/viewCount,statistics/likeCount,snippet/title,snippet/tags,snippet/channelId,snippet/channelTitle,snippet/thumbnails/medium/url,contentDetails/duration)",
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
        fields="items(id,statistics/subscriberCount,statistics/viewCount,statistics/videoCount)",
    )
    response = execute_request(request)
    if not response:
        return {}
    items = response.get("items", [])
    if not items:
        return {}
    return items[0]


def is_short_video(duration_str: str, title: str = "", tags: list = None) -> bool:
    """Check if a video is a short based on duration (<60s) or #shorts in title/tags."""
    # Check for #shorts in title
    if title and "#shorts" in title.lower():
        return True

    # Check for #shorts in tags
    if tags:
        for tag in tags:
            if "#shorts" in tag.lower() or tag.lower() == "shorts":
                return True

    if not duration_str:
        return False

    try:
        import re
        pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
        match = re.match(pattern, duration_str)
        if not match:
            return False

        hours = int(match.group(1)) if match.group(1) else 0
        minutes = int(match.group(2)) if match.group(2) else 0
        seconds = int(match.group(3)) if match.group(3) else 0

        total_seconds = hours * 3600 + minutes * 60 + seconds
        return total_seconds < 60
    except:
        return False


def is_relevant_tags(tags: list) -> bool:
    """Check if a video's tags indicate it's relevant to cold approach/pickup dating content."""
    if not tags:
        return False
    
    tags_lower = [t.lower() for t in tags]
    
    relevant_keywords = [
        "cold approach", "approach women", "picking up girls", "pickup", "pick up",
        "flirt", "flirting", "daygame", "day game",
        "street approach", "meet women", "talk to women",
        "attraction", "dating", "how to approach", "dating tips",
        "seduction", "pua", "pick up artist", "rizz", "game",
        "women", "girls", "girl", "approach"
    ]
    
    for tag in tags_lower:
        for keyword in relevant_keywords:
            if keyword in tag:
                return True
    
    return False


def is_outlier(view_count: int, subscriber_count: int, channel_total_views: int = 0, channel_video_count: int = 0) -> tuple[bool, str]:
    # Qualify if views exceed the minimum threshold
    if view_count >= HIGH_VIEW_THRESHOLD:
        return True, f"Over {HIGH_VIEW_THRESHOLD:,} views"

    # Qualify if views are 100x or more the channel's average views per video
    if channel_video_count > 0 and channel_total_views > 0:
        avg_views = channel_total_views / channel_video_count
        if avg_views > 0 and view_count >= avg_views * 100:
            multiplier = int(view_count / avg_views)
            return True, f"{multiplier}x channel average views"

    return False, ""


def build_google_sheets_client():
    if not GOOGLE_SERVICE_ACCOUNT_JSON:
        print("Google Sheets credentials not configured. Set GOOGLE_SERVICE_ACCOUNT_JSON to enable Google Sheets output.")
        return None

    try:
        service_account_info = json.loads(GOOGLE_SERVICE_ACCOUNT_JSON)
    except json.JSONDecodeError as exc:
        print(f"Invalid Google service account JSON: {exc}")
        return None

    credentials = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
    return gspread.authorize(credentials)


def write_rows_to_google_sheets(rows: List[Dict[str, Any]]):
    client = build_google_sheets_client()
    if not client:
        return None

    if GOOGLE_SPREADSHEET_ID:
        spreadsheet = client.open_by_key(GOOGLE_SPREADSHEET_ID)
    else:
        spreadsheet = client.create("YouTube Outlier Tracker")

    try:
        worksheet = spreadsheet.worksheet(GOOGLE_SHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=GOOGLE_SHEET_NAME, rows=1000, cols=20)

    worksheet.clear()
    worksheet.append_row(HEADERS)

    if rows:
        values = [
            [
                row.get("title", ""),
                row.get("channel", ""),
                row.get("published_at", ""),
                row.get("views", ""),
                row.get("subscribers", ""),
                row.get("keyword", ""),
                row.get("video_url", ""),
                f'=IMAGE("{row.get("thumbnail_url", "")}")' if row.get("thumbnail_url") else "",
                row.get("reason", ""),
            ]
            for row in rows
        ]
        worksheet.append_rows(values, value_input_option="USER_ENTERED")

    return spreadsheet.url


def main() -> None:
    rows: List[Dict[str, Any]] = []
    seen_video_ids = set()  # Track videos we've already added to avoid duplicates
    youtube = build_youtube_client()

    if not youtube:
        print("No YouTube API key found. Skipping YouTube search.")
        return

    print(f"Searching for keywords: {', '.join(KEYWORDS)}")
    print(f"Lookback period: {LOOKBACK_DAYS} days")
    print(f"High view threshold: {HIGH_VIEW_THRESHOLD:,}")
    print()

    for keyword in KEYWORDS:
        for item in search_videos(youtube, keyword):
            video_id = item.get("id", {}).get("videoId")
            if not video_id:
                continue

            # Skip if we've already added this video
            if video_id in seen_video_ids:
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
            channel_total_views = 0
            channel_video_count = 0
            if channel_id:
                channel_stats = get_channel_stats(youtube, channel_id)
                ch_statistics = channel_stats.get("statistics", {})
                subscriber_count = int(ch_statistics.get("subscriberCount", 0) or 0)
                channel_total_views = int(ch_statistics.get("viewCount", 0) or 0)
                channel_video_count = int(ch_statistics.get("videoCount", 0) or 0)

            # Debug: Print all found videos
            title = stats.get("snippet", {}).get("title", "")
            print(f"Found video: '{title}' - Views: {view_count:,}, Subscribers: {subscriber_count:,}, Channel: {channel_title}")

            # Filter out shorts (under 60s, or has #shorts in title/tags)
            duration = stats.get("contentDetails", {}).get("duration", "")
            tags = stats.get("snippet", {}).get("tags", []) or []
            if is_short_video(duration, title, tags):
                print(f"  → Skipped (short video or #shorts)")
                continue

            # Filter out unrelated content based on video tags
            if not is_relevant_tags(tags):
                print(f"  → Skipped (tags not relevant to cold approach/pickup niche)")
                continue

            is_flagged, reason = is_outlier(view_count, subscriber_count, channel_total_views, channel_video_count)
            if not is_flagged:
                continue

            seen_video_ids.add(video_id)
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

    sheet_url = write_rows_to_google_sheets(rows)
    if sheet_url:
        print(f"Wrote {len(rows)} outlier videos to {sheet_url}")
    else:
        print("No Google Sheets output was created.")


if __name__ == "__main__":
    main()
