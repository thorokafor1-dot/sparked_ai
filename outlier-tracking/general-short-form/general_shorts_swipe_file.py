"""One-off writer for the "General Short Form Outliers" output
(outlier-tracking/general-short-form/data.json): a curated swipe file of ultra-viral,
cross-niche YouTube Shorts packaging, each translated into a cold-approach-ready title
and thumbnail concept.

Entries here must be real, statistically verified outliers found by
general_shorts_finder.py (run via GitHub Actions) — genuinely exceptional Shorts
(5M+ views, or 50x+ channel average, or 20x+ subscriber breakout in the last 90 days),
not merely good ones. That script only surfaces candidates; picking which ones cleanly
translate into a cold-approach idea and writing the analysis below is a manual step.
Cold-approach thumbnail concepts should put a woman front and center as the visual
star, per the channel's packaging convention. This file is not a live API pull itself —
run it manually whenever new entries are added.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from common import write_rows_to_json

SWIPE_FILE = [
    {
        "title": "The Wedding Stopped When She Revealed His Biggest Secret...",
        "channel": "Good Vibes Stories",
        "url": "https://www.youtube.com/watch?v=ddDkIrcZZ4Q",
        "published_at": "2026-06-30",
        "duration": "0:16",
        "niche": "Dramatized Wedding-Reveal Story",
        "views": "1,322,822",
        "views_num": 1322822,
        "subscribers": 12800,
        "score": "103.3x subs",
        "pattern": "A dramatized wedding-ceremony scene interrupted at its most emotionally charged possible moment, with the bride's raw reaction as the clear visual and emotional center of the frame.",
        "trigger": "Maximum-stakes curiosity (a secret big enough to stop a wedding) + the universal emotional weight of a wedding setting + the bride's genuine-looking distress making the stakes feel real regardless of production style.",
        "thumbnail": "A real wedding ceremony scene, the bride in her dress visibly emotional/crying, a groom or family member gesturing, an on-screen caption capturing a spoken line (\"Get this crazy woman off\"), warm ceremony lighting.",
        "formula": "\"The [Major Event] Stopped When [Person] Revealed [His/Her] Biggest Secret...\"",
        "why": "Interrupting the single highest-stakes moment in a wedding (not a random point in the story) maximizes the emotional charge, and capturing the bride's raw reaction as the focal point makes the stakes legible without needing to understand the full story yet.",
        "translation": "Reframe \"a wedding secret reveal\" as \"a moment during a date/approach where everything suddenly changes\" — same maximum-stakes-interruption structure, same real-reaction-as-focal-point thumbnail.",
        "ca_title": "The Date Stopped When She Found Out The Truth About Why I Approached Her",
        "ca_thumbnail": "A real date/café setting, a woman with a genuine, emotionally charged expression as the clear focal point, an on-screen caption capturing a spoken line, warm natural lighting.",
        "notes": "Likely a dramatized/scripted format rather than a spontaneous real event — still a legitimate packaging lesson (the interruption-at-peak-stakes structure), just worth knowing it's probably staged before modeling the production style.",
        "status": "Not Adapted",
    },
    {
        "title": "She Called for Water… But Reached the Police!",
        "channel": "Speader News",
        "url": "https://www.youtube.com/watch?v=Ho-rgBL2HAA",
        "published_at": "2026-07-04",
        "duration": "2:42",
        "niche": "Real Investigative/Kindness Story",
        "views": "445,637",
        "views_num": 445637,
        "subscribers": 8270,
        "score": "53.9x subs",
        "pattern": "A real, documentary-style moment framed around an unexpected mismatch between what someone asked for and what actually happened, with a woman as the clear subject of the story.",
        "trigger": "Curiosity about the mismatch in the title (why would asking for water reach the police?) + the documentary/news-style visual credibility + a real person's genuine situation making the stakes feel consequential.",
        "thumbnail": "A real, candid documentary-style shot, a woman in a tracksuit among a small group of people, on-screen caption text, natural indoor daylight, unproduced news-style framing.",
        "formula": "\"[Someone] [Asked/Called] For [Small Ordinary Thing]… But [Unexpected Escalation]!\"",
        "why": "Naming a specific, small, ordinary request (water) and pairing it with a specific, surprising escalation (police) creates a concrete curiosity gap that a vague \"you won't believe what happened\" title can't match.",
        "translation": "Reframe \"asked for something small, got an unexpected escalation\" as \"asked for something small during an approach, got an unexpectedly bigger response\" — same small-ask-vs-big-escalation contrast, applied to a real social interaction.",
        "ca_title": "I Asked Her For The Time… She Ended Up Giving Me Her Number",
        "ca_thumbnail": "A real, candid documentary-style shot of the creator and a woman mid-conversation on the street, on-screen caption text, natural daylight, unproduced framing.",
        "notes": "The \"specific small ask vs. specific surprising escalation\" title contrast is a clean, concrete alternative to vague curiosity-bait phrasing.",
        "status": "Not Adapted",
    },
    {
        "title": "Viral Video | Russian Couple Arrested After Surprise Proposal Atop Empire State Building Tower",
        "channel": "India Today",
        "url": "https://www.youtube.com/watch?v=96kCnXdQeQQ",
        "published_at": "2026-07-03",
        "duration": "0:47",
        "niche": "Real News Story/Proposal Twist",
        "views": "428,372",
        "views_num": 428372,
        "subscribers": 11200000,
        "score": "25.1x avg",
        "pattern": "A real news story where the proposal itself succeeded but led to an unexpected, headline-worthy consequence (arrest), subverting the usual \"proposal goes right\" narrative with a genuinely surprising real-world twist.",
        "trigger": "Novelty of an unexpected real-world consequence to an otherwise-familiar event type + the news-credibility of a real, reported incident rather than a produced content piece.",
        "thumbnail": "A real news photo, two people on an elevated platform/crane against a city skyline, dramatic red arrow/highlight.",
        "formula": "\"Viral Video | [Subject] [Unexpected Consequence] After [Familiar Event Type]\"",
        "why": "Familiar event types are usually safe, low-curiosity premises — attaching a genuinely unexpected consequence to one makes it newsworthy and shareable in a way a normal version wouldn't be.",
        "translation": "Reframe \"a proposal that led to an unexpected real consequence\" as \"an approach that led to an unexpected real consequence\" — same familiar-premise-plus-genuinely-surprising-twist device.",
        "ca_title": "Viral Video | Guy Gets Banned From The Mall After This Approach",
        "ca_thumbnail": "A real documentary-style photo, the creator and a woman in a public setting, a dramatic highlight/arrow drawing attention to the unexpected element, matching the news-photo authenticity of the original.",
        "notes": "This entry qualified purely via channel-average multiplier (25.1x) on a massive 11.2M-subscriber news channel — proof a single unusually newsworthy clip can outperform a channel's own normal baseline regardless of its size.",
        "status": "Not Adapted",
    },
    {
        "title": "Soldier's homecoming surprise goes completely wrong 💔#shorts #emotional #reality",
        "channel": "Nati-c",
        "url": "https://www.youtube.com/watch?v=YQ-f1f28Qak",
        "published_at": "2026-06-30",
        "duration": "0:50",
        "niche": "Military Homecoming Subversion",
        "views": "927,887",
        "views_num": 927887,
        "subscribers": 1570,
        "score": "591.0x subs",
        "pattern": "Subverts the entire genre's usual happy-ending expectation, explicitly promising the reunion \"goes completely wrong,\" with a single quiet word doing more emotional work than a dramatic caption would.",
        "trigger": "Genre-subversion curiosity (every other reunion video in this format promises joy; this one promises the opposite) + the emotional restraint of a single quiet word creating more unease than an explanatory caption would.",
        "thumbnail": "A real, dim indoor scene, a soldier on crutches, a woman in a red dress reacting, small caption \"sorry.\"",
        "formula": "\"[Event Type] Surprise Goes Completely Wrong 💔#shorts #emotional #reality\"",
        "why": "After dozens of nearly identical \"happy reunion\" videos flood this format, explicitly promising the opposite outcome stands out purely through contrast, and understatement reads as more emotionally real than an explained catastrophe.",
        "translation": "Reframe \"a reunion surprise that goes wrong\" as \"an approach that goes somewhere completely unexpected, for better or worse\" — same genre-subversion + quiet-understated-caption device.",
        "ca_title": "I Tried To Surprise Her... It Went Completely Wrong",
        "ca_thumbnail": "A real, dim intimate setting, the creator and a woman with a subdued, ambiguous emotional tone, a single quiet caption word, muted lighting matching the original's restraint.",
        "notes": "In a swipe file with many \"happy reunion\" entries, this is the one deliberate genre-subversion — worth testing precisely because it stands out from the pattern rather than repeating it.",
        "status": "Not Adapted",
    },
    {
        "title": "The Viral Gift 🎁✨ [Kindzilla] # kindzilla #funny #shorts #hero #kindness #justice",
        "channel": "Kindzilla",
        "url": "https://www.youtube.com/watch?v=DLhAVf99DC8",
        "published_at": "2026-07-07",
        "duration": "0:32",
        "niche": "Kindness/Small-Gesture Reveal (Kids)",
        "views": "12,700,072 (391K subscribers — 32.5x its subscriber count in views, a genuine breakout)",
        "views_num": 12700072,
        "subscribers": 391000,
        "score": "32.5x subs",
        "pattern": "A small, specific, kid-scale act of kindness (a bracelet exchange) captured candidly and framed with the channel's recurring branded name as a trust signal for the genre.",
        "trigger": "Warmth from witnessing an unprompted, small generous gesture + brand-name recognition for viewers already familiar with the channel's format.",
        "thumbnail": "Two boys facing each other indoors, one handing over a small item (bracelet), candid unposed framing, natural indoor lighting.",
        "formula": "\"The Viral [Object] 🎁✨ [Channel Branding] #kindness\"",
        "why": "Keeping the act small and specific makes it feel achievable and real, and consistent branding across entries builds a recognizable, trusted \"kindness content\" identity.",
        "translation": "Reframe \"kids exchanging a small gift\" as \"a small, specific generous gesture between a guy and a woman he's just met\" — same small-scale-specific-kindness framing.",
        "ca_title": "I Gave Her Something Small — Her Reaction Went Viral",
        "ca_thumbnail": "The creator and a woman facing each other outdoors, mid-handoff of a small item, candid unposed framing, natural daylight.",
        "notes": "A recurring branded \"kindness series\" identity is a reusable device for building trust and repeat viewership across many individually low-stakes moments.",
        "status": "Not Adapted",
    },
    {
        "title": "The Most Unreal Proposal Ever 🥹💍 #trending #trend #shorts",
        "channel": "Aesthetic_Lyrixx",
        "url": "https://www.youtube.com/watch?v=EIkIgK0wPGI",
        "published_at": "2026-07-04",
        "duration": "0:14",
        "niche": "Proposal Reaction",
        "views": "3,829,494 (2.91K subscribers — 1,316.0x its subscriber count in views, and 140.0x its own channel average, an extreme breakout on a tiny channel)",
        "views_num": 3829494,
        "subscribers": 2910,
        "score": "1316.0x subs, 140.0x avg",
        "pattern": "A cinematic black-and-white treatment of a real proposal moment, paired with a quote-style caption that frames the moment as legendary rather than just describing it.",
        "trigger": "Aesthetic/emotional elevation of an ordinary event-type into something that feels timeless and shareable + curiosity about what makes this one specifically \"unreal.\"",
        "thumbnail": "A black-and-white candid photo of a couple on an elevated urban structure mid-proposal, a stylized quote-style caption (\"A proposal the world will never forget\") overlaid, dramatic monochrome grade.",
        "formula": "\"The Most Unreal [Event Type] Ever\"",
        "why": "Stripping color and adding a quote-style caption elevates an otherwise-common event type into something that reads as artistically significant, likely why a sub-3,000-subscriber channel cleared over 1,300x its own base.",
        "translation": "Reframe \"the most unreal proposal ever\" as \"the most unreal reaction to an approach ever\" — same monochrome-cinematic-treatment + quote-style-caption elevation device.",
        "ca_title": "The Most Unreal Reaction To An Approach Ever",
        "ca_thumbnail": "A black-and-white candid photo of the creator and a woman mid-genuine-reaction in an urban setting, a stylized quote-style caption overlaid, dramatic monochrome grade.",
        "notes": "A second extreme (1,000x+) breakout from a near-zero-subscriber channel in this batch — further evidence packaging, not audience size, is the deciding factor.",
        "status": "Not Adapted",
    },
    {
        "title": "He Handed Strangers Money and Drove Away",
        "channel": "True Tales",
        "url": "https://www.youtube.com/watch?v=K_As0VX-Gfw",
        "published_at": "2026-07-02",
        "duration": "0:07",
        "niche": "Narrated True Story (Zero-Filming Format)",
        "views": "181,410 (8,170 subscribers — 22.2x its subscriber count in views, a genuine breakout)",
        "views_num": 181410,
        "subscribers": 8170,
        "score": "22.2x subs",
        "pattern": "A real story narrated over on-screen text and a simple visual, naming a real person — proof that a compelling true story alone, without any original filming, can still break out.",
        "trigger": "Curiosity about a real, named generous stranger's story + the \"who was this person and why\" mystery + the wholesome payoff of an anonymous act of generosity.",
        "thumbnail": "On-screen text reciting the narrated story over a simple background image, minimal graphic design, small heart emoji branding in the corner.",
        "formula": "\"He/She [Did A Generous Anonymous Act] and [Left/Drove Away]\"",
        "why": "This format requires zero original footage — just a compelling true story and text-to-screen narration — proving the story itself, not the production, is what's carrying the video.",
        "translation": "Reframe \"an anonymous stranger's generous act, narrated\" as \"a real, narrated story about a moment of connection with a woman\" — same zero-filming, narrated-text-over-simple-visual format.",
        "ca_title": "He Told Her One Sentence Then Walked Away Forever",
        "ca_thumbnail": "On-screen text reciting the story over a simple, moody background image, minimal graphic design, small branding element in the corner.",
        "notes": "A genuinely zero-production format — worth testing as an extremely low-effort companion series alongside in-field footage.",
        "status": "Not Adapted",
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
