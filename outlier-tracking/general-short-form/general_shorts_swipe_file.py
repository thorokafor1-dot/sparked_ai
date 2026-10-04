"""One-off writer for the "General Short Form Outliers" output
(outlier-tracking/general-short-form/data.json): a curated swipe file of ultra-viral,
cross-niche YouTube Shorts packaging, each translated into a cold-approach-ready title
and thumbnail concept.

Entries here must be real, statistically verified outliers found by
general_shorts_finder.py (run via GitHub Actions), genuinely exceptional Shorts
(5M+ views, or 50x+ channel average, or 20x+ subscriber breakout in the last 90 days),
not merely good ones. That script only surfaces candidates; picking which ones cleanly
translate into a cold-approach idea and writing the analysis below is a manual step.
Cold-approach thumbnail concepts should put a woman front and center as the visual
star, per the channel's packaging convention. This file is not a live API pull itself,
run it manually whenever new entries are added.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import write_rows_to_json

SWIPE_FILE = [
    {
        "title": "The Viral Gift 🎁✨ [Kindzilla] # kindzilla #funny #shorts #hero #kindness #justice",
        "channel": "Kindzilla",
        "url": "https://www.youtube.com/watch?v=DLhAVf99DC8",
        "published_at": "2026-07-07",
        "duration": "0:32",
        "niche": "Kindness/Small-Gesture Reveal (Kids)",
        "views": "74,619,981 views (743,000 subscribers) -- a real, high-reach video used here as a proven thumbnail/title/retention example regardless of channel size.",
        "views_num": 74619981,
        "subscribers": 743000,
        "score": "74,619,981 views",
        "pattern": "A small, specific, kid-scale act of kindness (a bracelet exchange) captured candidly and framed with the channel's recurring branded name as a trust signal for the genre.",
        "trigger": "Warmth from witnessing an unprompted, small generous gesture + brand-name recognition for viewers already familiar with the channel's format.",
        "thumbnail": "Two boys facing each other indoors, one handing over a small item (bracelet), candid unposed framing, natural indoor lighting.",
        "formula": "\"The Viral [Object] 🎁✨ [Channel Branding] #kindness\"",
        "why": "Keeping the act small and specific makes it feel achievable and real, and consistent branding across entries builds a recognizable, trusted \"kindness content\" identity.",
        "translation": "Reframe \"kids exchanging a small gift\" as \"a small, specific generous gesture between a guy and a woman he's just met\", same small-scale-specific-kindness framing.",
        "ca_title": "I Gave Her Something Small, Her Reaction Went Viral",
        "ca_thumbnail": "The creator and a woman facing each other outdoors, mid-handoff of a small item, candid unposed framing, natural daylight.",
        "notes": "A recurring branded \"kindness series\" identity is a reusable device for building trust and repeat viewership across many individually low-stakes moments.",
        "status": "Not Adapted",
        "scanned_at": "2026-10-04",
    },
]


def _score_num(score_str: str) -> float:
    """Pull the leading numeric multiplier out of a display string like '336.0x subs'
    so the dashboard can sort by it."""
    match = re.match(r'[\d,.]+', score_str or "")
    if not match:
        return 0.0
    try:
        return float(match.group().replace(",", ""))
    except ValueError:
        return 0.0


def _video_id(url: str) -> str:
    """Extract the video ID from a youtube.com/watch?v=... URL, for building a static
    thumbnail CDN URL (i.ytimg.com/vi/<id>/...) without needing an API key."""
    match = re.search(r'[?&]v=([\w-]{6,})', url or "")
    return match.group(1) if match else ""


def to_dashboard_row(row: dict) -> dict:
    """Map a SWIPE_FILE entry's field names to the shape the dashboard's data.json
    expects for General Long/Short Form Outliers cards."""
    vid = _video_id(row["url"])
    return {
        "title": row["title"],
        "channel": row["channel"],
        "vid": vid,
        "thumbnailUrl": f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg" if vid else "",
        "videoUrl": row["url"],
        "niche": row["niche"],
        "views": row.get("views_num", 0),
        "viewsRaw": row["views"],
        "scoreRaw": row["score"],
        "scoreNum": _score_num(row["score"]),
        "pattern": row["pattern"],
        "trigger": row["trigger"],
        "titleFormula": row["formula"],
        "translation": row["translation"],
        "coldTitle": row["ca_title"],
        "coldThumbnail": row["ca_thumbnail"],
        "notes": row["notes"],
        "status": row["status"],
        "duration": row.get("duration", ""),
        "publishedAt": row.get("published_at", ""),
    }


def main() -> None:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")
    write_rows_to_json(path, [to_dashboard_row(row) for row in SWIPE_FILE])
    print(f"Wrote {len(SWIPE_FILE)} swipe file entries to {path}")


if __name__ == "__main__":
    main()
