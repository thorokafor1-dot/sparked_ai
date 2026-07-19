import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

import gspread
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError


API_KEY = os.getenv("YOUTUBE_API_KEY", "")
KEYWORDS = [k.strip() for k in os.getenv(
    "YOUTUBE_KEYWORDS",
    "picking up girls,cold approach,approach women,daygame,street approach,"
    "street flirting,rizz in public,asking for her number,asking for instagram,"
    "handling rejection,mall approach,campus approach,girl reaction to approach,"
    # Widened for volume in the Shorts Outliers tab — the original 13 terms
    # only surfaced 21 qualifying shorts; these add more niche-specific phrasing
    # rather than broadening into ambiguous terms that could dilute relevance.
    "cold approach shorts,daygame shorts,street approach shorts,"
    "flirting with strangers,talking to girls in public,approaching random girls,"
    "picking up girls in public,walk up and talk to her,she said yes to my number,"
    "she gave me her number,asking girls out in public,rejected by a girl,"
    "girl says no to date,public rejection compilation,street game infield,"
    "daygame infield,cold approach infield,approaching women in the mall,"
    "approaching women at the gym,approaching women at college,"
    "confidence to approach women,overcoming approach anxiety,"
    "how to talk to strangers women,pickup artist infield,seduction infield,"
    "getting her number in public,asking for her snapchat,flirting experiment public,"
    "social experiment flirting,her reaction to being approached,"
    "approaching girls at the beach,approaching girls downtown,night game approach,"
    "bar approach women,club approach women"
).split(",") if k.strip()]
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
# Separate, more generous per-channel cap for Shorts — the shorts tab needs more volume
# than long-form, and a handful of prolific creators shouldn't crowd it out at the same
# tight cap used for long-form videos.
SHORTS_PER_CHANNEL_CAP = int(os.getenv("SHORTS_PER_CHANNEL_CAP", "5"))

# Shorts get pushed by YouTube's feed algorithm to viewers largely independent of
# subscriber count, so these mirror the long-form three-signal design (absolute floor,
# channel-average breakout, subscriber breakout) rather than requiring reach AND
# engagement simultaneously — that combo was too strict and left the tab too thin.
GOOGLE_SHORTS_SHEET_NAME = os.getenv("GOOGLE_SHORTS_SHEET_NAME", "Shorts Outliers")
SHORTS_LOOKBACK_DAYS = int(os.getenv("SHORTS_LOOKBACK_DAYS", "90"))
# Absolute view count that alone qualifies a short as an outlier.
SHORTS_HIGH_VIEW_THRESHOLD = int(os.getenv("SHORTS_HIGH_VIEW_THRESHOLD", "300000"))
# Minimum views before the ratio-based signals below are allowed to trigger, so a video
# published hours ago with a handful of views can't produce an artificially huge ratio.
SHORTS_MIN_VIEW_THRESHOLD = int(os.getenv("SHORTS_MIN_VIEW_THRESHOLD", "50000"))
# Views per day since publish that alone qualifies a short as an outlier (catches a
# recent viral spike even before it clears the absolute view floor).
SHORTS_VELOCITY_THRESHOLD = float(os.getenv("SHORTS_VELOCITY_THRESHOLD", "15000"))
# How many times a channel's own average views a short must clear to be an outlier.
SHORTS_AVERAGE_MULTIPLIER_THRESHOLD = float(os.getenv("SHORTS_AVERAGE_MULTIPLIER_THRESHOLD", "10"))
# How many times a channel's subscriber count a short's views must clear.
SHORTS_SUBSCRIBER_MULTIPLIER_THRESHOLD = float(os.getenv("SHORTS_SUBSCRIBER_MULTIPLIER_THRESHOLD", "5"))

# YouTube category IDs that are never dating/pickup content, regardless of how a video
# is worded — a much more reliable signal than keyword-guessing (e.g. blocks song uploads
# like "Pinky Up" that a fuzzy search match let through).
EXCLUDED_CATEGORY_IDS = {"10", "20", "17"}  # Music, Gaming, Sports

# Search terms specific enough to this niche that we trust whatever YouTube's search
# returns for them. Broader/ambiguous terms below are NOT trusted blindly, since
# YouTube's fuzzy search matching can surface unrelated content for them (e.g.
# "picking up girls" surfacing a video about picking up kids from school, or
# "street approach" surfacing street photography videos).
PRECISE_SEARCH_KEYWORDS = {"cold approach", "daygame", "day game", "infield"}

SCOPES = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
HEADERS = [
    "Title",
    "Channel",
    "Published At",
    "Duration",
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
        fields="items(id,statistics/viewCount,statistics/likeCount,snippet/title,snippet/tags,snippet/categoryId,snippet/channelId,snippet/channelTitle,snippet/publishedAt,snippet/thumbnails/medium,contentDetails/duration)",
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


def parse_duration_seconds(duration_str: str) -> int:
    """Convert an ISO 8601 duration (e.g. 'PT1H14M32S') to total seconds."""
    if not duration_str:
        return 0

    import re
    pattern = r'PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?'
    match = re.match(pattern, duration_str)
    if not match:
        return 0

    hours = int(match.group(1)) if match.group(1) else 0
    minutes = int(match.group(2)) if match.group(2) else 0
    seconds = int(match.group(3)) if match.group(3) else 0
    return hours * 3600 + minutes * 60 + seconds


def format_duration(duration_str: str) -> str:
    """Format an ISO 8601 duration as H:MM:SS (or M:SS under an hour)."""
    total_seconds = parse_duration_seconds(duration_str)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    return f"{minutes}:{seconds:02d}"


def is_short_video(duration_str: str, title: str = "", tags: list = None,
                    thumbnail_width: int = None, thumbnail_height: int = None) -> bool:
    """Check if a video is a Short: #shorts in title/tags, a vertical (portrait) thumbnail
    — the clearest visual tell, since Shorts are filmed for phone screens — or duration
    under 3 minutes (YouTube's current Shorts length cap; older code assumed 60s)."""
    # Check for #shorts in title
    if title and "#shorts" in title.lower():
        return True

    # Check for #shorts in tags
    if tags:
        for tag in tags:
            if "#shorts" in tag.lower() or tag.lower() == "shorts":
                return True

    # Vertical/portrait thumbnail (height > width) is a Short regardless of duration.
    if thumbnail_width and thumbnail_height and thumbnail_height > thumbnail_width:
        return True

    return bool(duration_str) and parse_duration_seconds(duration_str) < 180


# Unicode ranges for scripts that are unambiguously non-English when present in a title —
# catches Arabic, Hebrew, Korean, CJK, Devanagari (Hindi), Thai, Cyrillic. Doesn't catch
# other-language content written in Latin script (e.g. Indonesian) — that still needs a
# human read during curation.
_NON_ENGLISH_SCRIPT_PATTERN = None


def is_english_title(title: str) -> bool:
    """Reject titles containing non-Latin script — a cheap first-pass language filter for
    the cross-niche finders, which have no other signal to scope results to English."""
    global _NON_ENGLISH_SCRIPT_PATTERN
    if _NON_ENGLISH_SCRIPT_PATTERN is None:
        import re
        _NON_ENGLISH_SCRIPT_PATTERN = re.compile(
            r'[؀-ۿ֐-׿가-힯一-鿿぀-ヿ'
            r'ऀ-ॿ฀-๿Ѐ-ӿ]'
        )
    if not title:
        return True
    return not _NON_ENGLISH_SCRIPT_PATTERN.search(title)


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
        # Photography — "street" overlaps with cold-approach vocabulary, but street/candid
        # photography content is unambiguously not dating/pickup content
        "photography", "photographer", "photo walk",
        # Niche mismatch — this tracker is for male-approaching-women content; "street
        # flirting"/"street approach" search terms also surface LGBT and ladyboy content
        # that shares the same vocabulary but isn't the target niche (e.g. Kiriakos Spanos,
        # Always Abroad's "Ladyboy Street Approach" videos).
        "lgbt", "ladyboy",
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


def is_outlier_short(view_count: int, days_since_published: float, subscriber_count: int = 0,
                      channel_total_views: int = 0, channel_video_count: int = 0) -> tuple[bool, str, float]:
    """Score a short against four independent signals and return the strongest one.

    Mirrors the long-form design: any one signal qualifies. Velocity catches a recent
    spike even before the absolute floor; the channel-average and subscriber signals
    reuse the long-form logic but with higher bars, since Shorts naturally get more
    algorithmic reach than a channel's typical video.
    """
    candidates: List[tuple[float, str]] = []
    days_since_published = max(days_since_published, 1.0)

    # Signal 1: absolute view floor.
    if view_count >= SHORTS_HIGH_VIEW_THRESHOLD:
        candidates.append((view_count / SHORTS_HIGH_VIEW_THRESHOLD, f"Over {SHORTS_HIGH_VIEW_THRESHOLD:,} views"))

    # Signal 2: view velocity — catches a recent spike even before the absolute floor.
    if view_count >= SHORTS_MIN_VIEW_THRESHOLD:
        velocity = view_count / days_since_published
        if velocity >= SHORTS_VELOCITY_THRESHOLD:
            candidates.append((velocity / SHORTS_VELOCITY_THRESHOLD, f"{velocity:,.0f} views/day"))

    # Signal 3: views vs. this channel's own average views per video.
    if view_count >= SHORTS_MIN_VIEW_THRESHOLD and channel_video_count > 0 and channel_total_views > 0:
        avg_views = channel_total_views / channel_video_count
        if avg_views > 0:
            multiplier = view_count / avg_views
            if multiplier >= SHORTS_AVERAGE_MULTIPLIER_THRESHOLD:
                candidates.append((multiplier, f"{multiplier:.1f}x channel average views"))

    # Signal 4: views vs. subscriber count — reached far beyond the existing audience.
    if view_count >= SHORTS_MIN_VIEW_THRESHOLD and subscriber_count >= MIN_SUBSCRIBER_THRESHOLD:
        sub_multiplier = view_count / subscriber_count
        if sub_multiplier >= SHORTS_SUBSCRIBER_MULTIPLIER_THRESHOLD:
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


def open_spreadsheet():
    client = build_google_sheets_client()
    if not client:
        return None

    if GOOGLE_SPREADSHEET_ID:
        return client.open_by_key(GOOGLE_SPREADSHEET_ID)
    return client.create("YouTube Outlier Tracker")


def write_rows_to_worksheet(spreadsheet, sheet_name: str, rows: List[Dict[str, Any]]):
    try:
        worksheet = spreadsheet.worksheet(sheet_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=20)

    worksheet.clear()
    worksheet.append_row(HEADERS)

    # IMAGE() mode 4 renders at a fixed pixel size instead of shrinking to fit the
    # default (tiny) cell, so thumbnails are actually visible.
    thumbnail_width, thumbnail_height = 160, 90

    if rows:
        values = [
            [
                row.get("title", ""),
                row.get("channel", ""),
                row.get("published_at", ""),
                row.get("duration", ""),
                row.get("views", ""),
                row.get("subscribers", ""),
                row.get("keyword", ""),
                row.get("video_url", ""),
                f'=IMAGE("{row.get("thumbnail_url", "")}", 4, {thumbnail_height}, {thumbnail_width})' if row.get("thumbnail_url") else "",
                row.get("reason", ""),
                row.get("score", ""),
            ]
            for row in rows
        ]
        worksheet.append_rows(values, value_input_option="USER_ENTERED")

    # Widen the thumbnail column and heighten data rows so the fixed-size images
    # (set above) aren't clipped by Google Sheets' default row/column dimensions.
    thumbnail_col_index = HEADERS.index("Thumbnail URL")
    resize_requests = [
        {
            "updateDimensionProperties": {
                "range": {
                    "sheetId": worksheet.id,
                    "dimension": "COLUMNS",
                    "startIndex": thumbnail_col_index,
                    "endIndex": thumbnail_col_index + 1,
                },
                "properties": {"pixelSize": thumbnail_width + 20},
                "fields": "pixelSize",
            }
        },
    ]
    if rows:
        resize_requests.append(
            {
                "updateDimensionProperties": {
                    "range": {
                        "sheetId": worksheet.id,
                        "dimension": "ROWS",
                        "startIndex": 1,
                        "endIndex": 1 + len(rows),
                    },
                    "properties": {"pixelSize": thumbnail_height + 20},
                    "fields": "pixelSize",
                }
            }
        )
    spreadsheet.batch_update({"requests": resize_requests})

    # Add filter row so columns can be sorted/filtered by clicking the header arrows
    worksheet.set_basic_filter()

    return spreadsheet.url


def cap_and_sort_by_channel(rows: List[Dict[str, Any]], per_channel_cap: int = None) -> List[Dict[str, Any]]:
    """Group rows by channel, optionally cap per channel, then sort by score descending."""
    rows_by_channel: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        rows_by_channel.setdefault(row["channel_key"], []).append(row)

    capped: List[Dict[str, Any]] = []
    for channel_rows in rows_by_channel.values():
        channel_rows.sort(key=lambda r: r["score"], reverse=True)
        capped.extend(channel_rows[:per_channel_cap] if per_channel_cap else channel_rows)

    capped.sort(key=lambda r: r["score"], reverse=True)
    return capped


def main() -> None:
    rows: List[Dict[str, Any]] = []
    shorts_rows: List[Dict[str, Any]] = []
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
            medium_thumbnail = (stats.get("snippet", {}).get("thumbnails", {}) or {}).get("medium", {}) or {}
            thumbnail_url = medium_thumbnail.get("url", "")
            thumbnail_width = medium_thumbnail.get("width")
            thumbnail_height = medium_thumbnail.get("height")
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
                channel_stats = get_channel_stats(youtube, channel_id)
                ch_statistics = channel_stats.get("statistics", {})
                subscriber_count = int(ch_statistics.get("subscriberCount", 0) or 0)
                channel_total_views = int(ch_statistics.get("viewCount", 0) or 0)
                channel_video_count = int(ch_statistics.get("videoCount", 0) or 0)

            # Debug: Print all found videos
            title = stats.get("snippet", {}).get("title", "")
            print(f"Found video: '{title}' - Views: {view_count:,}, Subscribers: {subscriber_count:,}, Channel: {channel_title}")

            duration = stats.get("contentDetails", {}).get("duration", "")
            tags = stats.get("snippet", {}).get("tags", []) or []
            is_short = is_short_video(duration, title, tags, thumbnail_width, thumbnail_height)

            # Filter out unrelated content based on video tags (with title fallback)
            category_id = stats.get("snippet", {}).get("categoryId", "")
            if not is_relevant_tags(tags, title, category_id, keyword):
                print(f"  → Skipped (not relevant to cold approach/pickup niche)")
                continue

            row_data = {
                "title": title,
                "channel": channel_title,
                "channel_key": channel_id or channel_title,
                "published_at": published_at,
                "duration": format_duration(duration),
                "views": view_count,
                "subscribers": subscriber_count,
                "keyword": keyword,
                "video_url": f"https://www.youtube.com/watch?v={video_id}",
                "thumbnail_url": thumbnail_url,
            }

            if is_short:
                if published_dt is None:
                    continue
                days_since_published = (datetime.now(timezone.utc) - published_dt).total_seconds() / 86400
                if days_since_published > SHORTS_LOOKBACK_DAYS:
                    print(f"  → Skipped (short older than {SHORTS_LOOKBACK_DAYS} days)")
                    continue

                is_flagged, reason, score = is_outlier_short(view_count, days_since_published, subscriber_count, channel_total_views, channel_video_count)
                if not is_flagged:
                    continue

                seen_video_ids.add(video_id)
                shorts_rows.append({**row_data, "reason": reason, "score": score})
            else:
                is_flagged, reason, score = is_outlier(view_count, subscriber_count, channel_total_views, channel_video_count)
                if not is_flagged:
                    continue

                seen_video_ids.add(video_id)
                rows.append({**row_data, "reason": reason, "score": score})

    # Cap outliers per channel so a few prolific channels don't crowd out variety,
    # then sort by score so the strongest examples surface first. Shorts aren't
    # capped in total count, just kept diverse across channels.
    capped_rows = cap_and_sort_by_channel(rows, PER_CHANNEL_CAP)
    capped_shorts_rows = cap_and_sort_by_channel(shorts_rows, SHORTS_PER_CHANNEL_CAP)

    spreadsheet = open_spreadsheet()
    if not spreadsheet:
        print("No Google Sheets output was created.")
        return

    sheet_url = write_rows_to_worksheet(spreadsheet, GOOGLE_SHEET_NAME, capped_rows)
    print(f"Wrote {len(capped_rows)} outlier videos to {sheet_url} ({GOOGLE_SHEET_NAME})")

    shorts_url = write_rows_to_worksheet(spreadsheet, GOOGLE_SHORTS_SHEET_NAME, capped_shorts_rows)
    print(f"Wrote {len(capped_shorts_rows)} outlier shorts to {shorts_url} ({GOOGLE_SHORTS_SHEET_NAME})")


if __name__ == "__main__":
    main()
