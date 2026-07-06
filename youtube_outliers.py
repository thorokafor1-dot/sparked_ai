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
# Absolute view count that alone qualifies a video as an outlier, regardless of channel size.
HIGH_VIEW_THRESHOLD = int(os.getenv("HIGH_VIEW_THRESHOLD", "30000"))
# Minimum views a video must have before the ratio-based signals below are allowed to
# trigger, so a video with a handful of views can't qualify just from a huge ratio.
MIN_VIEW_THRESHOLD = int(os.getenv("MIN_VIEW_THRESHOLD", "5000"))
# Minimum subscribers before the views-vs-subscribers signal applies, so new/tiny
# channels don't produce inflated ratios from a near-zero denominator.
MIN_SUBSCRIBER_THRESHOLD = int(os.getenv("MIN_SUBSCRIBER_THRESHOLD", "100"))
# How many times a channel's own average views a video must clear to be an outlier.
AVERAGE_MULTIPLIER_THRESHOLD = float(os.getenv("OUTLIER_MULTIPLIER_THRESHOLD", "8"))
# How many times a channel's subscriber count a video's views must clear — signals the
# video pulled in viewers well beyond the channel's existing audience.
SUBSCRIBER_MULTIPLIER_THRESHOLD = float(os.getenv("SUBSCRIBER_MULTIPLIER_THRESHOLD", "3"))
# Cap how many outliers from the same channel land in the sheet, to keep results diverse.
PER_CHANNEL_CAP = int(os.getenv("PER_CHANNEL_CAP", "3"))

# YouTube category IDs that are never dating/pickup content, regardless of how a video
# is worded — a much more reliable signal than keyword-guessing (e.g. blocks song uploads
# like "Pinky Up" that a fuzzy search match let through).
EXCLUDED_CATEGORY_IDS = {"10", "20", "17"}  # Music, Gaming, Sports

# Search terms specific enough to this niche that we trust whatever YouTube's search
# returns for them. Broader/ambiguous terms below are NOT trusted blindly, since
# YouTube's fuzzy search matching can surface unrelated content for them (e.g.
# "picking up girls" surfacing a video about picking up kids from school).
PRECISE_SEARCH_KEYWORDS = {"cold approach", "daygame", "day game", "street approach", "infield"}

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
    "Outlier Score",
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
        fields="items(id,statistics/viewCount,statistics/likeCount,snippet/title,snippet/tags,snippet/categoryId,snippet/channelId,snippet/channelTitle,snippet/publishedAt,snippet/thumbnails/medium/url,contentDetails/duration)",
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


def is_relevant_tags(tags: list, title: str = "", category_id: str = "", search_keyword: str = "") -> bool:
    """Check if a video's tags/title/category indicate it's relevant to cold approach/pickup dating content."""
    import re

    # Hard category exclusion — catches things keyword-matching can't, like songs
    # or gameplay videos that a fuzzy search match let through.
    if category_id in EXCLUDED_CATEGORY_IDS:
        return False

    # Hard exclusions — whole-word match against title and tags
    # Only include terms that are UNAMBIGUOUSLY non-dating content
    exclusion_keywords = [
        # Baseball specific
        # Note: "infield" and "outfield" are deliberately NOT excluded here —
        # "infield" is core cold-approach/pickup terminology (live footage of
        # street approaches), not a baseball reference in this niche.
        "baseball", "softball", "pitcher", "batter", "batting",
        "home run", "strikeout", "mlb", "little league",
        # Other sports leagues/orgs (very specific, won't appear in pickup content)
        "nfl", "nba", "nhl", "fifa", "cricket",
        # Unambiguous sports plays
        "field goal", "touchdown", "slam dunk",
        # Specific video games
        "minecraft", "fortnite", "roblox", "call of duty", "warzone", "valorant",
        "video game", "gameplay",
        # Unambiguous dev/tech
        "programming", "javascript", "python tutorial", "react.js", "machine learning",
    ]

    combined_text = (title + " " + " ".join(tags or [])).lower()
    for term in exclusion_keywords:
        # Use word boundary matching so "coding" won't match "coaching"
        if re.search(r'\b' + re.escape(term) + r'\b', combined_text):
            return False

    # Specific dating/pickup phrases only — deliberately excludes generic standalone
    # words like "girls", "women", "date", "relationship", "confidence", "approach"
    # that are common enough in off-topic content (e.g. a video about picking up
    # kids from school, or an unrelated self-help video) to produce false positives.
    relevant_keywords = [
        "cold approach", "approach women", "picking up girls", "pick up girls",
        "pickup artist", "pick up artist", "pua",
        "flirt", "flirting", "daygame", "day game", "street approach", "infield",
        "how to approach", "how to approach women", "dating tips", "dating advice",
        "seduction", "rizz",
        "how to get girls", "get girls", "attract women", "attract girls",
        "talking to girls", "talking to women", "meeting women", "meet women",
        "talk to women", "get a girlfriend",
        "andrew tate",
    ]

    # Check tags
    if tags:
        tags_lower = [t.lower() for t in tags]
        for tag in tags_lower:
            for keyword in relevant_keywords:
                if keyword in tag:
                    return True

    # Fallback: check title
    if title:
        title_lower = title.lower()
        for keyword in relevant_keywords:
            if keyword in title_lower:
                return True

    # If no positive match, only trust the search query for precise/unambiguous
    # search terms. Broader terms (e.g. "picking up girls", "approach women") can
    # surface unrelated fuzzy matches from YouTube's own search, so those require
    # an actual positive tag/title match above instead of a blind pass-through.
    return search_keyword.lower() in PRECISE_SEARCH_KEYWORDS


def is_outlier(view_count: int, subscriber_count: int, channel_total_views: int = 0, channel_video_count: int = 0) -> tuple[bool, str, float]:
    """Score a video against three independent outlier signals and return the strongest one.

    Any single signal is enough to qualify: a raw view floor (catches big, on-topic hits
    regardless of channel size), views vs. the channel's own average (catches a channel's
    own breakout), and views vs. subscriber count (catches videos that pulled well beyond
    the channel's existing audience — the strongest signal a thumbnail/title did the work).
    """
    candidates: List[tuple[float, str]] = []

    # Signal 1: absolute view floor — always evaluated so every outlier gets a comparable score.
    if view_count >= HIGH_VIEW_THRESHOLD:
        candidates.append((view_count / HIGH_VIEW_THRESHOLD, f"Over {HIGH_VIEW_THRESHOLD:,} views"))

    # Signal 2: views vs. this channel's own average views per video.
    if view_count >= MIN_VIEW_THRESHOLD and channel_video_count > 0 and channel_total_views > 0:
        avg_views = channel_total_views / channel_video_count
        if avg_views > 0:
            multiplier = view_count / avg_views
            if multiplier >= AVERAGE_MULTIPLIER_THRESHOLD:
                candidates.append((multiplier, f"{multiplier:.1f}x channel average views"))

    # Signal 3: views vs. subscriber count — reached far beyond the existing audience.
    if view_count >= MIN_VIEW_THRESHOLD and subscriber_count >= MIN_SUBSCRIBER_THRESHOLD:
        sub_multiplier = view_count / subscriber_count
        if sub_multiplier >= SUBSCRIBER_MULTIPLIER_THRESHOLD:
            candidates.append((sub_multiplier, f"{sub_multiplier:.1f}x subscriber count in views"))

    if not candidates:
        return False, "", 0.0

    score, reason = max(candidates, key=lambda c: c[0])
    return True, reason, round(score, 2)


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
                row.get("score", ""),
            ]
            for row in rows
        ]
        worksheet.append_rows(values, value_input_option="USER_ENTERED")

    # Add filter row so columns can be sorted/filtered by clicking the header arrows
    worksheet.set_basic_filter()

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
            raw_published_at = stats.get("snippet", {}).get("publishedAt", "")
            try:
                published_at = datetime.strptime(raw_published_at, "%Y-%m-%dT%H:%M:%SZ").strftime("%b %d, %Y") if raw_published_at else ""
            except ValueError:
                published_at = raw_published_at

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

            # Filter out unrelated content based on video tags (with title fallback)
            category_id = stats.get("snippet", {}).get("categoryId", "")
            if not is_relevant_tags(tags, title, category_id, keyword):
                print(f"  → Skipped (not relevant to cold approach/pickup niche)")
                continue

            is_flagged, reason, score = is_outlier(view_count, subscriber_count, channel_total_views, channel_video_count)
            if not is_flagged:
                continue

            seen_video_ids.add(video_id)
            rows.append(
                {
                    "title": stats.get("snippet", {}).get("title", ""),
                    "channel": channel_title,
                    "channel_key": channel_id or channel_title,
                    "published_at": published_at,
                    "views": view_count,
                    "subscribers": subscriber_count,
                    "keyword": keyword,
                    "video_url": f"https://www.youtube.com/watch?v={video_id}",
                    "thumbnail_url": thumbnail_url,
                    "reason": reason,
                    "score": score,
                }
            )

    # Cap outliers per channel so a few prolific channels don't crowd out variety,
    # then sort by score so the strongest thumbnail/title wins surface first.
    rows_by_channel: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        rows_by_channel.setdefault(row["channel_key"], []).append(row)

    capped_rows: List[Dict[str, Any]] = []
    for channel_rows in rows_by_channel.values():
        channel_rows.sort(key=lambda r: r["score"], reverse=True)
        capped_rows.extend(channel_rows[:PER_CHANNEL_CAP])

    capped_rows.sort(key=lambda r: r["score"], reverse=True)

    sheet_url = write_rows_to_google_sheets(capped_rows)
    if sheet_url:
        print(f"Wrote {len(capped_rows)} outlier videos to {sheet_url}")
    else:
        print("No Google Sheets output was created.")


if __name__ == "__main__":
    main()
