"""Shared YouTube API + JSON-output helpers used across every outlier-tracking script:
the niche long-form/short-form tracker (via niche-long-form/, niche-short-form/) and
the general long-form/short-form finders and writers (via general-long-form/,
general-short-form/). Format-specific thresholds live in their own subfolder instead
of here, this module only holds what's genuinely shared.

Each script writes its own data.json into its own subfolder (committed to the repo by
its GitHub Actions workflow) rather than to Google Sheets, YOUTUBE_API_KEY is the only
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
# raising, GitHub Actions' Ubuntu runners already default to UTF-8, so this only
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
    # Widened for volume in the Shorts Outliers tab, the original 13 terms
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
    # Bar/nightgame widening 2026-09, the original 3 terms above barely surface
    # bar/club content since the rest of KEYWORDS skews toward daygame/street
    # vocabulary; the user specifically films weekly bar approaches and needs
    # In-Person reference material from that venue, not just daygame.
    "bar game infield,nightclub approach,night game infield,bar pickup,"
    "approaching women at bars,approaching women at the club,bar flirting,"
    "club flirting,night game breakdown,bar approach infield,"
    "picking up girls at the bar,picking up girls at the club,night game tips,"
    "approaching her at the bar,cold approach at night,nightlife approach,"
    "bar approach compilation,club approach infield,night game rejection,"
    # Second widening pass, the first widening (13 -> 48 terms) plus a direct
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
# Video chat is a related but distinct format the user also uploads, different
# vocabulary/keywords than in-person infield, tracked separately via the Format column.
VIDEO_CHAT_KEYWORDS = [k.strip() for k in os.getenv(
    "YOUTUBE_VIDEO_CHAT_KEYWORDS",
    "omegle flirting,monkey app flirting,chatroulette flirting,"
    "random video chat girls,azar app flirting,holla app flirting,"
    "emerald chat flirting,video chat rizz,getting numbers on video chat,"
    "video chat approach,omegle rizz,monkey app girls,video call with strangers,"
    "stranger video chat girls,flirting on video chat,video chat pickup,"
    # Added 2026-09-26 -- "baddie" is this genre's actual vocabulary (Jameer, Jay
    # Throck, ItsMP3 etc all use it) and wasn't covered before.
    "monkey app baddies,rizzing up baddies monkey app,monkey app best moments,"
    "making girls fold monkey app"
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
    "psychology of attraction women,why she's testing you,dating advice for men explained,"
    # Widened 2026-09, the original 18 terms yielded only 8 qualifying long-form
    # outliers (vs. 58 for In-Person on a smaller keyword list), well short of the
    # ~30 needed for real hook research. Paired with the PRECISE_SEARCH_KEYWORDS
    # fix below (these terms were previously getting silently rejected by the
    # relevance filter unless a title happened to match one of 9 fixed phrases).
    "she's attracted to you signs,female interest signals,psychology of female attraction,"
    "hidden signs she likes you,female flirting signals explained,reading women's interest level,"
    "signs she wants you to approach,female body language flirting,how women flirt without saying it,"
    "subconscious attraction signals,signs she's into you body language,female dating psychology explained,"
    "understanding women attraction,why she acts distant test,decoding female body language,"
    "attraction triggers in women explained,hidden attraction signals women,"
    "female psychology dating advice,signs she's flirting with you,"
    "how to read a woman's body language,why is she testing me,signs of female interest"
).split(",") if k.strip()]
# Texting / text game (user request 2026-10-09, planned series): how to text women, DM and
# dating-app messaging. Tagged Format "Texting". Thin niche, so it uses EXTENDED_LOOKBACK_DAYS.
TEXTING_KEYWORDS = [k.strip() for k in os.getenv(
    "YOUTUBE_TEXTING_KEYWORDS",
    "how to text a girl,how to text women,text game,texting girls,texting tips for men,"
    "what to text a girl,how to text a girl you like,texting a girl after getting her number,"
    "first text to a girl,how to flirt over text,texting mistakes men make,"
    "how to text your crush,how to get a girl to text back,reacting to my texts with girls,"
    "rating texts with girls,texting game breakdown,how to dm a girl on instagram,"
    "tinder conversation tips,hinge messages that work,dating app openers,"
    "how to ask a girl out over text,texting a girl you met in person"
).split(",") if k.strip()]
# Content check (like is_video_chat_content): a title counts as Texting only when it's about
# HOW to text/DM/message women, not just any title with "text" in it. First scan (2026-10-09)
# showed the loose version pulls in murder trials ("flirty texts"), celebrity DM gossip,
# texting advice aimed at women, and generic dating videos found via a texting search term.
TEXTING_CONTENT_TERMS = [
    "how to text", "how i text", "how you text", "you text", "want you to text", "text her",
    "text a girl", "text a woman", "text women", "text girls", "texting women", "texting girls",
    "texting a girl", "texting her", "text game", "texting game", "texting tips", "texting mistake",
    "texting secret", "texting rule", "texting method", "texting advice", "laws of texting",
    "understand texting", "texting trick", "texts from men", "texts to get her", "over text",
    "through texting", "using texts", "only using texts", "left on read", "dm girls", "her dms",
    "girls dms", "dms (instagram", "first message", "opener", "tinder", "hinge", "bumble",
    "dating app", "text breakdown",
]
TEXTING_EXCLUDED_TERMS = [
    # Texting advice aimed at women, not the men's audience
    "man lose interest", "men lose interest", "lose interest in you", "your crush",
    # News, crime, celebrity and relationship drama
    "murder", "trial", "police", "court", "perjury", "cnn", "dr. phil", "husband", "boyfriend",
    "coworker", "celeb", "lizzo", "caught", "cheating", "musical", "song", "catfish",
    "mukbang", "flirty text",
]


# Governs the search's publishedAfter cutoff for both In-Person and Video Chat keywords
# (one shared scan). Shorts get an additional, separately-bounded post-filter via
# SHORTS_LOOKBACK_DAYS in short_form_tracker.py, so raising this doesn't widen Shorts'
# effective window. Set to 200 (~March) per explicit request to reach further back for
# in-person long-form coverage.
LOOKBACK_DAYS = int(os.getenv("LOOKBACK_DAYS", "200"))
MAX_RESULTS_PER_KEYWORD = int(os.getenv("MAX_RESULTS_PER_KEYWORD", "50"))

# Video chat platform names, a video mentioning one of these in its title/tags is video
# chat content regardless of which keyword LIST (in-person vs. video-chat) actually found
# it during search (a video chat video can surface via a shared/ambiguous in-person term).
# Used both as part of the relevance filter below and to override the Format tag in
# youtube_outliers.py so content-based signal wins over search-origin signal.
VIDEO_CHAT_PLATFORM_TERMS = [
    "video chat", "omegle", "monkey app", "chatroulette", "azar", "holla",
    "emerald chat", "camsurf",
]

# YouTube category IDs that are never dating/pickup content, regardless of how a video
# is worded, a much more reliable signal than keyword-guessing (e.g. blocks song uploads
# like "Pinky Up" that a fuzzy search match let through).
EXCLUDED_CATEGORY_IDS = {"10", "20", "17"}  # Music, Gaming, Sports

# Search terms specific enough to this niche that we trust whatever YouTube's search
# returns for them. Broader/ambiguous terms below are NOT trusted blindly, since
# YouTube's fuzzy search matching can surface unrelated content for them (e.g.
# "picking up girls" surfacing a video about picking up kids from school, or
# "street approach" surfacing street photography videos).
#
# EXPLAINER_KEYWORDS is deliberately NOT folded in here (tried once, reverted),
# unlike "cold approach"/"daygame"/"infield", generic-sounding explainer phrases
# like "signs she likes you" pull in a lot of fuzzy-matched noise from YouTube's
# search (ASMR roleplay, prank/reaction channels reusing the same surface
# vocabulary for a completely different genre). Trusting the search query alone
# let those through wholesale. The real fix for explainer's low yield is below:
# relevant_keywords now covers the full EXPLAINER_KEYWORDS list, so a video still
# needs an actual on-topic phrase in its own title/tags, a content-based check
# that isn't fooled by fuzzy search matching the way query-origin trust is.
PRECISE_SEARCH_KEYWORDS = {
    "cold approach", "daygame", "day game", "infield",
    # Bar/nightgame terms are just as specific/unambiguous as "daygame", "bar
    # approach women", "night game approach" etc. don't collide with unrelated
    # content the way a bare "approach women" would.
    "night game approach", "bar approach women", "club approach women",
    "bar game infield", "nightclub approach", "night game infield", "bar pickup",
    "bar approach infield", "night game tips", "cold approach at night",
    "nightlife approach", "bar approach compilation", "club approach infield",
    "night game rejection",
}


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


# Thin sub-niches (Video Chat, Explainer, bar/nightgame) peak in bursts and then go quiet,
# so their best outliers are often 1-3 years old. The default 200-day window silently
# excluded them (Jameer, Jay Throck, ItsMP3, most nightgame). Found 2026-09-28: a manual
# extended-lookback scan fixed the dashboard but the weekly Actions run rebuilds
# data.json from scratch and wiped it, so these lists get the long window in the weekly
# scan itself. Same number of searches, just a wider publishedAfter.
EXTENDED_LOOKBACK_DAYS = int(os.getenv("EXTENDED_LOOKBACK_DAYS", "1095"))
NIGHTGAME_KEYWORDS = {
    "night game approach", "bar approach women", "club approach women", "bar game infield",
    "nightclub approach", "night game infield", "bar pickup", "approaching women at bars",
    "approaching women at the club", "bar flirting", "club flirting", "night game breakdown",
    "bar approach infield", "picking up girls at the bar", "picking up girls at the club",
    "night game tips", "approaching her at the bar", "cold approach at night",
    "nightlife approach", "bar approach compilation", "club approach infield",
    "night game rejection",
    # Folded in 2026-09-28 from a one-off scratchpad scan that found real results but
    # never got merged here, so the weekly rebuild kept wiping them (same bug as the
    # Video Chat gap). Keep this set as the single source of truth going forward.
    "nightgame infield", "bar game breakdown", "club infield", "nightclub game",
    "bar rizz", "night rizz", "getting her number at a bar", "escalation at the bar",
    "nightgame pickup", "bar seduction", "club seduction", "vegas nightgame",
    "miami nightgame", "la nightgame", "bar hopping approach", "flirting at the club",
    "flirting at a bar", "how to approach a girl at a bar", "how to talk to a girl at a bar",
    "how to get a girls number at a bar", "approaching a girl at a party",
    "party approach girls", "house party flirting", "college party approach",
    "flirting at a party", "drunk girl approach", "girls night out approach",
    "nightclub flirting", "vegas nightlife approach", "miami nightlife approach",
    "singles night approach", "club game infield", "bar approach breakdown",
    "kiss close infield", "instant date bar", "nightgame tips infield",
    "club approach breakdown", "bar conversation girl",
}


def search_videos(youtube, keyword: str, lookback_days: int = None) -> List[Dict[str, Any]]:
    published_after = (datetime.now(timezone.utc) - timedelta(days=lookback_days or LOOKBACK_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
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
        part="statistics,snippet,contentDetails,player,status",
        id=video_id,
        maxHeight=720,
        maxWidth=720,
        fields="items(id,statistics/viewCount,statistics/likeCount,snippet/title,snippet/tags,snippet/categoryId,snippet/channelId,snippet/channelTitle,snippet/publishedAt,snippet/thumbnails,snippet/defaultAudioLanguage,snippet/defaultLanguage,contentDetails/duration,player/embedWidth,player/embedHeight,status/madeForKids,status/selfDeclaredMadeForKids)",
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
    only trying "medium", some videos (older uploads, certain Shorts) don't have every
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
    minutes, YouTube's current Shorts length cap, older code assumed 60s): a #shorts
    hashtag or vertical thumbnail used to be treated as an override that could mark a
    video Short regardless of length, which let long videos with either signal (a
    leftover #shorts tag, or just a portrait thumbnail image) slip into the Shorts
    bucket despite running well past 3 minutes. Those signals are now only consulted
    as a fallback when duration is unavailable."""
    if duration_str:
        return parse_duration_seconds(duration_str) < 180

    # No duration available, fall back to the weaker signals.
    if title and "#shorts" in title.lower():
        return True
    if tags:
        for tag in tags:
            if "#shorts" in tag.lower() or tag.lower() == "shorts":
                return True
    if thumbnail_width and thumbnail_height and thumbnail_height > thumbnail_width:
        return True
    return False


def is_vertical_format(duration_str: str, embed_width=None, embed_height=None) -> bool:
    """True for a real long-form video (over 3 minutes) filmed in vertical/portrait
    orientation, like a phone selfie-cam recording (e.g. Steph Speaks). The API's
    thumbnail dimensions can NOT be used for this: YouTube reports every thumbnail as
    320x180 even for vertical Shorts (verified 2026-09-28), so the old thumbnail check
    never fired. The player's embed size (part=player with maxHeight/maxWidth) does
    follow the video's real aspect ratio (vertical Shorts come back 405x720)."""
    try:
        w, h = int(embed_width or 0), int(embed_height or 0)
    except (TypeError, ValueError):
        return False
    if not w or not h or h <= w:
        return False
    if duration_str and parse_duration_seconds(duration_str) <= 180:
        return False  # a Short (up to 3 minutes), not a vertical long-form video
    return True


def confirm_is_short(video_id: str) -> Any:
    """Confirm a duration-based Short classification against YouTube's own routing:
    youtube.com/shorts/<id> stays on that URL (200) if YouTube itself treats the video
    as a Short, or redirects to /watch if not, catches a video under 3 minutes that
    YouTube doesn't actually classify as a Short. Not part of the documented Data API,
    so treat it as a confirmation signal only (call it for videos is_short_video()
    already flagged True, not as a standalone classifier), and only every override
    that flag to False on a confirmed non-Short, never fail the pipeline on it.
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


# Unicode ranges for scripts that are unambiguously non-English when present in a title,
# catches Arabic, Hebrew, Korean, CJK, Devanagari (Hindi), Thai, Cyrillic, plus accented
# Latin script (Latin-1 Supplement + Latin Extended-A/B: U+00C0-024F), which catches Polish,
# French, German, Spanish, Portuguese, Czech, Turkish, Vietnamese, Scandinavian languages,
# etc. without a real language-detection model. A statistical model (langdetect) was tried
# and rejected, it misclassified short, slang-heavy niche titles with high false confidence
# (e.g. "rizz in public compilation" -> Italian, "AI glasses on Omegle! | Panki" -> Estonian,
# both >99.99% confidence), which would have blocked genuine English content. This diacritic
# range is a narrower but far more precise signal for this niche's short titles. Still doesn't
# catch a non-English language written in plain, unaccented Latin script (e.g. Indonesian,
# Malay), that still needs a human read during curation.
_NON_ENGLISH_SCRIPT_PATTERN = None


def is_english_title(title: str) -> bool:
    """Reject titles containing non-Latin script or accented Latin characters, a cheap
    first-pass language filter for the niche/cross-niche finders, which have no other
    signal to scope results to English."""
    global _NON_ENGLISH_SCRIPT_PATTERN
    if _NON_ENGLISH_SCRIPT_PATTERN is None:
        import re
        _NON_ENGLISH_SCRIPT_PATTERN = re.compile(
            r'[؀-ۿ֐-׿가-힯一-鿿぀-ヿ'
            r'ऀ-෿฀-๿Ѐ-ӿ'
            r'À-ɏ]'
        )
    if not title:
        return True
    return not _NON_ENGLISH_SCRIPT_PATTERN.search(title)


# Channels excluded by name rather than keyword, these produce content that keeps
# resurfacing through the niche's shared vocabulary (e.g. "street flirting") but isn't
# the target niche (male-approaching-women): Kiriakos Spanos is a woman interviewing/
# flirting with men on the street (gender-reversed format, no LGBT/ladyboy keywords to
# catch it), and Always Abroad's "Ladyboy Street Approach" series. Keyword-based
# exclusion already failed twice for Kiriakos Spanos via two different mechanisms, so
# this is a direct, reliable backstop per explicit user request.
EXCLUDED_CHANNELS = {"kiriakos spanos", "always abroad"}


# Indian/Pakistani/Nepali creators whose videos are in Hindi/Urdu/Hinglish (user request
# 2026-10-09: exclude from Video Chat outliers). is_english_title() can't catch them, their
# titles are plain Latin script. Three signals, any one rejects: YouTube's own language
# fields (snippet.defaultAudioLanguage / defaultLanguage), a channel blocklist of creators
# confirmed by hand, and Hinglish/South Asian marker words in the title or channel name.
SOUTH_ASIAN_LANGS = {"hi", "pa", "bn", "ur", "ne", "mr", "gu", "ta", "te", "kn", "ml", "or", "as", "si"}
SOUTH_ASIAN_CHANNELS = {
    "adarshuc", "ramesh maity", "adrishya", "inspire hub story", "cliptuber", "justabhix",
    "omegle flex", "its kunal", "uzii", "godl highlights", "monkey ke diwane", "monkey chats",
    "monkey chat", "uneasy darpan", "panki streams", "panki shorts 07", "nihaan bhatt",
    "pratham uncut", "desi meme creator", "allen magicツ", "dilip rana shorts", "kalki",
    "call prank", "mr_akki9795", "adios clips hub", "unick", "scroll with me", "minivlog",
    "chillbro videos", "rahul omegle", "np clip", "suraz speaks", "jixson ray",
}
SOUTH_ASIAN_MARKERS = [
    "bhabhi", "desi", "hindi", "punjabi", "indian", "pakistani", "bengali", "nepali", "delhi",
    "mumbai", "begam", "mummy", "kr", "liya", "dia", "hai", "konsi", "yaar", "bhai", "kya",
    "nahi", "cringistaan", "dhruv rathee", "kohli", "prankur", "panki",
]
_SOUTH_ASIAN_MARKER_PATTERN = None


def is_south_asian_content(title: str = "", channel_title: str = "", tags: list = None,
                           snippet: Dict[str, Any] = None) -> bool:
    """True for Hindi/Urdu/Hinglish creator content (see SOUTH_ASIAN_* above)."""
    import re
    global _SOUTH_ASIAN_MARKER_PATTERN
    snippet = snippet or {}
    for field in ("defaultAudioLanguage", "defaultLanguage"):
        lang = (snippet.get(field) or "").lower()
        if lang.split("-")[0] in SOUTH_ASIAN_LANGS or lang == "en-in":
            return True
    chan = (channel_title or "").strip().lower()
    if chan in SOUTH_ASIAN_CHANNELS:
        return True
    if _SOUTH_ASIAN_MARKER_PATTERN is None:
        _SOUTH_ASIAN_MARKER_PATTERN = re.compile(
            r"\b(" + "|".join(re.escape(m) for m in SOUTH_ASIAN_MARKERS) + r")\b")
    text = " ".join([title or "", chan, " ".join(tags or [])]).lower()
    return bool(_SOUTH_ASIAN_MARKER_PATTERN.search(text))


def is_texting_content(title: str, tags: list = None) -> bool:
    """True when the title is about how to text/DM/message women (Format "Texting"). Title only,
    tags are too loose (a #texts tag on a song short)."""
    import re
    text = (title or "").lower()
    if any(t in text for t in TEXTING_EXCLUDED_TERMS):
        return False
    return any(re.search(r'\b' + re.escape(t), text) for t in TEXTING_CONTENT_TERMS)


def is_video_chat_content(title: str, tags: list = None) -> bool:
    """Content-based check for whether a title/tags mention a video-chat platform,
    used to override the Format tag when a video-chat video surfaces via an ambiguous
    in-person search term, so the platform mentioned in the video wins over which
    keyword list happened to find it."""
    import re
    combined_text = (title + " " + " ".join(tags or [])).lower()
    return any(
        re.search(r'\b' + re.escape(term) + r'\b', combined_text)
        for term in VIDEO_CHAT_PLATFORM_TERMS
    )


# Curation decisions made by hand during 2026-09 review, encoded so the weekly rebuild
# stops re-adding them (it rebuilds data.json from scratch every Sunday). Substring match
# on lowercased title + channel name.
EXCLUDED_PHRASES = [
    # Kids/sports/comedy/skit content that surfaces through shared vocabulary
    "peppa pig", "dude perfect", "dhar mann", "standup comedy", "stand up comedy", "modiji",
    # App-review listicles, not flirting content
    "free video call", "video call app", "video calling app", "omegle alternatives",
    "how to use umingle",
    # Not the target niche (male approaching women) or off-format
    "lgbtq", "languages to strangers", "to fall asleep",
    # Societal-commentary videos with no technique to adapt
    "refusing to approach", "refuse to approach", "don't approach women", "do not approach women",
    "not *approaching women*", "not approaching women", "begging men to approach",
    "men won't approach", "“terrified” to approach", "meta glasses", "harass women",
    "skyrocketing as men", "men refuse to date", "crashing out",
    # Added 2026-09-28 (nightgame/bar scan curation) -- scripted/acted content, not real footage
    "seduction scene", "babysitter's seduction", "deadly seduction", "seduction protocol",
    "nightclub line", "knight club", "queer movie clip", "movie scene", "heated rivalry",
    "shortdrama", "short drama", "dared approach cold", "digital circus", "pomni",
    "tadc", "rotten tomatoes", "spectacular spider-man", "mafs dinner party", "netflix philippines",
    # Espionage podcasts/interviews, not dating content despite "seduction" in the title
    "sex spy", "russian spy", "honeytrap", "kgb secret", "seduction manipulation tactics",
    # Sex-tourism/nightlife-guide travel vlogs (Pattaya, Bangkok, Bali, Goa etc.), not technique content
    "nightlife district", "pattaya nightlife", "bangkok nightlife", "bali nightlife",
    "goa nightlife", "nightlife guide", "nightlife prices", "nightlife tips: approaching girls",
    "working girls", "freelancers 2025", "beach club exposed",
    # Reality TV / prank / vlog drama, not adaptable technique
    "caught me and monty", "flirting for 1 hour", "flirting under the table", "office party",
    "dinner party (scene)", "caught flirting with both",
]


# Channels that make family/kids content, for the General Long/Short Form tabs specifically
# (user preference 2026-09-28: not made-for-kids). These slipped through before because
# madeForKids wasn't fetched from the API at all; get_video_stats now requests part=status
# so is_made_for_kids() below can use the real field going forward. This name list is a
# text-based backstop for channels already found to publish kids content, in case the API
# field is ever missing or a borderline case doesn't self-declare accurately.
KIDS_CHANNEL_NAMES = {
    "dhar mann", "dhar mann studios", "royalty family", "the royalty family",
    "ninja fam", "the ninja fam!", "unspeakable", "unspeakable studios",
}


def is_made_for_kids(stats: Dict[str, Any], channel_title: str = "") -> bool:
    """True if YouTube's own madeForKids flag says so, or the channel is a known
    kids/family creator. Only meaningful for the General tabs, the niche tabs aren't
    kids-adjacent content to begin with."""
    status = stats.get("status", {}) if stats else {}
    if status.get("madeForKids") or status.get("selfDeclaredMadeForKids"):
        return True
    return (channel_title or "").strip().lower() in KIDS_CHANNEL_NAMES


def is_excluded_content(title: str = "", channel_title: str = "") -> bool:
    """Hard, cheap exclusions: ASMR channels (the title/tag check misses them because
    'asmr' is often only in the channel name) and the curated phrase list above."""
    text = (title or "").lower()
    chan = (channel_title or "").lower()
    if "asmr" in chan:
        return True
    return any(p in text or p in chan for p in EXCLUDED_PHRASES)


def is_relevant_tags(tags: list, title: str = "", category_id: str = "", search_keyword: str = "",
                      channel_title: str = "") -> bool:
    """Check if a video's tags/title/category indicate it's relevant to cold approach/pickup dating content."""
    import re

    if channel_title and channel_title.strip().lower() in EXCLUDED_CHANNELS:
        return False

    if is_excluded_content(title, channel_title):
        return False

    # Hard category exclusion, catches things keyword-matching can't, like songs
    # or gameplay videos that a fuzzy search match let through.
    if category_id in EXCLUDED_CATEGORY_IDS:
        return False

    # Hard exclusions, whole-word match against title and tags
    # Only include terms that are UNAMBIGUOUSLY non-dating content
    exclusion_keywords = [
        # Baseball specific
        # Note: "infield" and "outfield" are deliberately NOT excluded here,
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
        # but it's also a substring of unrelated phrases YouTube's fuzzy search surfaces,
        # a safari "game drive" and a Roblox-style "Game World" fashion video both slipped
        # through on this exact keyword per explicit user report.
        "game drive", "safari", "wildlife",
        # Unambiguous dev/tech
        "programming", "javascript", "python tutorial", "react.js", "machine learning",
        # Photography, "street" overlaps with cold-approach vocabulary, but street/candid
        # photography content is unambiguously not dating/pickup content
        "photography", "photographer", "photo walk",
        # Niche mismatch, this tracker is for male-approaching-women content; "street
        # flirting"/"street approach" search terms also surface LGBT and ladyboy content
        # that shares the same vocabulary but isn't the target niche (e.g. Kiriakos Spanos,
        # Always Abroad's "Ladyboy Street Approach" videos).
        "lgbt", "ladyboy",
        # Scripted drama/edit clips, matching on "flirt"/"flirting" alone (see
        # relevant_keywords below) lets K-drama and similar scripted-romance clip
        # compilations through, since that match short-circuits the PRECISE_SEARCH_KEYWORDS
        # gate regardless of which search term actually found the video.
        "kdrama", "k-drama", "korean drama", "chinese drama", "cdrama", "c-drama",
        "thai drama", "japanese drama", "jdrama", "j-drama", "drama edit", "drama scene",
        "kiss scene", "drama clip", "movie scene", "film scene", "webtoon", "manhwa",
        "eng sub", "engsub", "eng dub", "engdub",
        # Roleplay/fantasy audio content, widening EXPLAINER_KEYWORDS (2026-09) to catch
        # more genuine attraction-psychology content also let in a flood of ASMR roleplay
        # ("Your New Neighbor Is a Demon... and She Likes You") that shares surface
        # vocabulary ("she likes you") with real explainer titles but is a completely
        # different, non-analytical genre with no hook-research value for this niche.
        "asmr", "roleplay", "role play",
        # Scripted micro-drama apps (ReelShort/DramaBox/GoodShort-style vertical episodic
        # romance), not channel-name based (per explicit user feedback), since the giveaway
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

    # Specific dating/pickup phrases only, deliberately excludes generic standalone
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
        # Bar/nightgame vocabulary, content-based check so a bar/club video found
        # via a broader search term still passes even without an exact PRECISE_
        # SEARCH_KEYWORDS match.
        "bar game", "night game", "nightgame", "bar approach", "club approach",
        "nightclub", "bar pickup", "night approach",
        # Explainer/analysis phrasing, talking-head content about attraction/psychology
        # rather than footage of an approach, distinct vocabulary from the action terms
        # above. Deliberately kept as a content-based check (title/tags must actually
        # contain one of these) rather than trusting search-query origin the way
        # cold approach/daygame/infield are, see PRECISE_SEARCH_KEYWORDS above for why.
    ] + EXPLAINER_KEYWORDS + TEXTING_CONTENT_TERMS + [
        "attraction signs", "female interest", "interested in you signs",
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
    Replaces the old Google Sheets writer, each script's own data.json is committed to
    the repo by its GitHub Actions workflow, so the dashboard can read it directly."""
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rows, f, indent=2, ensure_ascii=False)
    return path


def cap_format_total(rows: List[Dict[str, Any]], format_caps: Dict[str, int]) -> List[Dict[str, Any]]:
    """Cap the total number of rows per format (e.g. Video Chat max 100, user request
    2026-09-28), keeping the highest-scoring rows for each capped format. Formats not
    listed in format_caps are left untouched."""
    by_format: Dict[str, List[Dict[str, Any]]] = {}
    for row in rows:
        by_format.setdefault(row.get("format", ""), []).append(row)
    out: List[Dict[str, Any]] = []
    for fmt, group in by_format.items():
        cap = format_caps.get(fmt)
        if cap is not None:
            group = sorted(group, key=lambda r: r.get("score", 0), reverse=True)[:cap]
        out.extend(group)
    return out


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
