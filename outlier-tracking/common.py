"""Shared YouTube API + JSON-output helpers used across every outlier-tracking script:
the niche long-form/short-form tracker (via niche-long-form/, niche-short-form/) and
the general long-form/short-form finders and writers (via general-long-form/,
general-short-form/). Format-specific thresholds live in their own subfolder instead
of here — this module only holds what's genuinely shared.

Each script writes its own data.json into its own subfolder (committed to the repo by
its GitHub Actions workflow) rather than to Google Sheets — YOUTUBE_API_KEY is the only
credential this pipeline needs.
"""
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

from googleapiclient.discovery import build

# Windows' default console encoding (cp1252) can't represent some characters that show
# up in real video titles (emoji, uncommon symbols), which crashed the whole scan
# mid-run on a plain print(). Reconfigure to UTF-8 with a safe fallback instead of
# raising — GitHub Actions' Ubuntu runners already default to UTF-8, so this only
# matters for local runs, but should never crash either way.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
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
    "bar approach women,club approach women,"
    # Second widening pass — the first widening (13 -> 48 terms) plus a direct
    # channel-name exclusion for Kiriakos Spanos/Always Abroad still left the
    # count short of 40 once that channel's entries were removed.
    "approaching strangers experiment,flirting infield,girl reaction compilation,"
    "walking up to strangers,cold approach fails,cold approach wins,"
    "daygame breakdown,infield breakdown,talking to random women,"
    "flirty response compilation,asking her out compilation,street pickup shorts,"
    "picking up women shorts,his approach worked,her honest reaction to approach,"
    "does she like me shorts,reading her body language approach,she smiled at me shorts,"
    "cold approach tips shorts,daygame tips shorts,street approach compilation,"
    "she gave me her number shorts,approaching her at the coffee shop"
).split(",") if k.strip()]
# Video chat is a related but distinct format the user also uploads — different
# vocabulary/keywords than in-person infield, tracked separately via the Format column.
VIDEO_CHAT_KEYWORDS = [k.strip() for k in os.getenv(
    "YOUTUBE_VIDEO_CHAT_KEYWORDS",
    "omegle flirting,monkey app flirting,chatroulette flirting,"
    "random video chat girls,azar app flirting,holla app flirting,"
    "emerald chat flirting,video chat rizz,getting numbers on video chat,"
    "video chat approach,omegle rizz,monkey app girls,video call with strangers,"
    "stranger video chat girls,flirting on video chat,video chat pickup"
).split(",") if k.strip()]
# Explainer/analysis is a third format the user also uploads (talking-head, no footage,
# e.g. "signs she likes you" or attraction-psychology breakdowns), distinct vocabulary
# from both in-person and video-chat above. The original 26-term KEYWORDS list barely
# surfaces this style (it's tuned for action/footage terms like "cold approach"), which
# left explainer content almost entirely absent from niche outlier tracking until now.
EXPLAINER_KEYWORDS = [k.strip() for k in os.getenv(
    "YOUTUBE_EXPLAINER_KEYWORDS",
    "signs she likes you,signs of attraction,female psychology explained,"
    "attraction psychology,body language attraction signs,reading body language women,"
    "female attraction triggers,why women like confident men,how women test men,"
    "dating psychology explained,what women want explained,signs a girl is interested,"
    "female body language signs,how to know if she likes you,attraction signs from women,"
    "psychology of attraction women,why she's testing you,dating advice for men explained"
).split(",") if k.strip()]
# Governs the search's publishedAfter cutoff for both In-Person and Video Chat keywords
# (one shared scan). Shorts get an additional, separately-bounded post-filter via
# SHORTS_LOOKBACK_DAYS in short_form_tracker.py, so raising this doesn't widen Shorts'
# effective window. Set to 200 (~March) per explicit request to reach further back for
# in-person long-form coverage.
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "200"))
MAX_RESULTS_PER_KEYWORD = int(os.getenv("MAX_RESULTS_PER_KEYWORD", "50"))

# Video chat platform names — a video mentioning one of these in its title/tags is video
# chat content regardless of which keyword LIST (in-person vs. video-chat) actually found
# it during search (a video chat video can surface via a shared/ambiguous in-person term).
# Used both as part of the relevance filter below and to override the Format tag in
# youtube_outliers.py so content-based signal wins over search-origin signal.
VIDEO_CHAT_PLATFORM_TERMS = [
    "video chat", "omegle", "monkey app", "chatroulette", "azar", "holla",
    "emerald chat", "camsurf",
]

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
        fields="items(id,statistics/viewCount,statistics/likeCount,snippet/title,snippet/tags,snippet/categoryId,snippet/channelId,snippet/channelTitle,snippet/publishedAt,snippet/thumbnails,contentDetails/duration)",
    )
    response = execute_request(request)
    if not response:
        return {}
    items = response.get("items", [])
    if not items:
        return {}
    return items[0]


def pick_thumbnail(thumbnails: Dict[str, Any]) -> Dict[str, Any]:
    """Pick the best available thumbnail size, falling back through the list instead of
    only trying "medium" — some videos (older uploads, certain Shorts) don't have every
    size, and requesting/reading just "medium" left those rows with a blank thumbnail."""
    thumbnails = thumbnails or {}
    for size in ("medium", "high", "default", "standard", "maxres"):
        entry = thumbnails.get(size)
        if entry and entry.get("url"):
            return entry
    return {}


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
    """Check if a video is a Short. Duration is authoritative whenever known (under 3
    minutes — YouTube's current Shorts length cap, older code assumed 60s): a #shorts
    hashtag or vertical thumbnail used to be treated as an override that could mark a
    video Short regardless of length, which let long videos with either signal (a
    leftover #shorts tag, or just a portrait thumbnail image) slip into the Shorts
    bucket despite running well past 3 minutes. Those signals are now only consulted
    as a fallback when duration is unavailable."""
    if duration_str:
        return parse_duration_seconds(duration_str) < 180

    # No duration available — fall back to the weaker signals.
    if title and "#shorts" in title.lower():
        return True
    if tags:
        for tag in tags:
            if "#shorts" in tag.lower() or tag.lower() == "shorts":
                return True
    if thumbnail_width and thumbnail_height and thumbnail_height > thumbnail_width:
        return True
    return False


def confirm_is_short(video_id: str) -> Any:
    """Confirm a duration-based Short classification against YouTube's own routing:
    youtube.com/shorts/<id> stays on that URL (200) if YouTube itself treats the video
    as a Short, or redirects to /watch if not — catches a video under 3 minutes that
    YouTube doesn't actually classify as a Short. Not part of the documented Data API,
    so treat it as a confirmation signal only (call it for videos is_short_video()
    already flagged True, not as a standalone classifier), and only every override
    that flag to False on a confirmed non-Short — never fail the pipeline on it.
    Returns True/False when the check succeeds, or None on any request failure so the
    caller can fall back to trusting the duration-based signal."""
    import urllib.request
    url = f"https://www.youtube.com/shorts/{video_id}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}, method="HEAD")
        with urllib.request.urlopen(req, timeout=8) as resp:
            final_url = resp.geturl()
    except Exception:
        return None
    return "/shorts/" in final_url


# Unicode ranges for scripts that are unambiguously non-English when present in a title —
# catches Arabic, Hebrew, Korean, CJK, Devanagari (Hindi), Thai, Cyrillic — plus accented
# Latin script (Latin-1 Supplement + Latin Extended-A/B: U+00C0-024F), which catches Polish,
# French, German, Spanish, Portuguese, Czech, Turkish, Vietnamese, Scandinavian languages,
# etc. without a real language-detection model. A statistical model (langdetect) was tried
# and rejected — it misclassified short, slang-heavy niche titles with high false confidence
# (e.g. "rizz in public compilation" -> Italian, "AI glasses on Omegle! | Panki" -> Estonian,
# both >99.99% confidence), which would have blocked genuine English content. This diacritic
# range is a narrower but far more precise signal for this niche's short titles. Still doesn't
# catch a non-English language written in plain, unaccented Latin script (e.g. Indonesian,
# Malay) — that still needs a human read during curation.
_NON_ENGLISH_SCRIPT_PATTERN = None


def is_english_title(title: str) -> bool:
    """Reject titles containing non-Latin script or accented Latin characters — a cheap
    first-pass language filter for the niche/cross-niche finders, which have no other
    signal to scope results to English."""
    global _NON_ENGLISH_SCRIPT_PATTERN
    if _NON_ENGLISH_SCRIPT_PATTERN is None:
        import re
        _NON_ENGLISH_SCRIPT_PATTERN = re.compile(
            r'[؀-ۿ֐-׿가-힯一-鿿぀-ヿ'
            r'ऀ-ॿ฀-๿Ѐ-ӿ'
            r'À-ɏ]'
        )
    if not title:
        return True
    return not _NON_ENGLISH_SCRIPT_PATTERN.search(title)


# Channels excluded by name rather than keyword — these produce content that keeps
# resurfacing through the niche's shared vocabulary (e.g. "street flirting") but isn't
# the target niche (male-approaching-women): Kiriakos Spanos is a woman interviewing/
# flirting with men on the street (gender-reversed format, no LGBT/ladyboy keywords to
# catch it), and Always Abroad's "Ladyboy Street Approach" series. Keyword-based
# exclusion already failed twice for Kiriakos Spanos via two different mechanisms, so
# this is a direct, reliable backstop per explicit user request.
EXCLUDED_CHANNELS = {"kiriakos spanos", "always abroad"}


def is_video_chat_content(title: str, tags: list = None) -> bool:
    """Content-based check for whether a title/tags mention a video-chat platform —
    used to override the Format tag when a video-chat video surfaces via an ambiguous
    in-person search term, so the platform mentioned in the video wins over which
    keyword list happened to find it."""
    import re
    combined_text = (title + " " + " ".join(tags or [])).lower()
    return any(
        re.search(r'\b' + re.escape(term) + r'\b', combined_text)
        for term in VIDEO_CHAT_PLATFORM_TERMS
    )


def is_relevant_tags(tags: list, title: str = "", category_id: str = "", search_keyword: str = "",
                      channel_title: str = "") -> bool:
    """Check if a video's tags/title/category indicate it's relevant to cold approach/pickup dating content."""
    import re

    if channel_title and channel_title.strip().lower() in EXCLUDED_CHANNELS:
        return False

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
        "video game", "gameplay", "game world",
        # "day game"/"daygame" is trusted niche terminology (see PRECISE_SEARCH_KEYWORDS),
        # but it's also a substring of unrelated phrases YouTube's fuzzy search surfaces —
        # a safari "game drive" and a Roblox-style "Game World" fashion video both slipped
        # through on this exact keyword per explicit user report.
        "game drive", "safari", "wildlife",
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
        # Scripted drama/edit clips — matching on "flirt"/"flirting" alone (see
        # relevant_keywords below) lets K-drama and similar scripted-romance clip
        # compilations through, since that match short-circuits the PRECISE_SEARCH_KEYWORDS
        # gate regardless of which search term actually found the video.
        "kdrama", "k-drama", "korean drama", "chinese drama", "cdrama", "c-drama",
        "thai drama", "japanese drama", "jdrama", "j-drama", "drama edit", "drama scene",
        "kiss scene", "drama clip", "movie scene", "film scene", "webtoon", "manhwa",
        "eng sub", "engsub", "eng dub", "engdub",
        # Scripted micro-drama apps (ReelShort/DramaBox/GoodShort-style vertical episodic
        # romance) — not channel-name based (per explicit user feedback), since the giveaway
        # is the title's stacked-trope setup instead: an over-the-top status/identity reveal
        # ("Demon CEO", "Secret Billionaire", "Alpha", "Luna", "Mafia Boss") paired with a
        # "yet/but she adorably..." twist structure. These slip past the relevance check
        # above via a trusted precise search term (e.g. "cold approach") matching the plain
        # word "approach" in an otherwise unrelated fuzzy YouTube search hit.
        "demon ceo", "billionaire ceo", "secret billionaire", "secretly a billionaire",
        "secretly the", "mafia boss", "alpha wolf", "luna wolf", "true luna", "rejected mate",
        "chosen mate", "hidden heiress", "secret heiress", "contract marriage",
        "arranged marriage", "fake marriage", "revenge marriage", "possessive husband",
        "no one dared to", "adorably",
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
        # Explainer/analysis phrasing — talking-head content about attraction/psychology
        # rather than footage of an approach, distinct vocabulary from the action terms above.
        "signs she likes you", "signs of attraction", "female psychology",
        "attraction psychology", "body language attraction", "female attraction",
        "signs a girl is interested", "dating psychology", "attraction signs",
    ] + VIDEO_CHAT_PLATFORM_TERMS

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


def write_rows_to_json(path: str, rows: List[Dict[str, Any]]) -> str:
    """Write rows as pretty-printed JSON to path (creating parent directories as needed).
    Replaces the old Google Sheets writer — each script's own data.json is committed to
    the repo by its GitHub Actions workflow, so the dashboard can read it directly."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    return path


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
