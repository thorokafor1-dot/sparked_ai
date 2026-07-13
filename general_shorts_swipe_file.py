"""One-off writer for the "General Shorts Models" tab: a curated swipe file of
ultra-viral, cross-niche YouTube Shorts packaging, each translated into a
cold-approach-ready title and thumbnail concept.

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

import gspread

from youtube_outliers import GOOGLE_SPREADSHEET_ID, build_google_sheets_client

SHEET_NAME = os.getenv("GENERAL_SHORTS_SHEET_NAME", "General Shorts Models")

HEADERS = [
    "Original Video Title",
    "Original Channel",
    "Video URL",
    "Original Niche",
    "Views",
    "Subscribers",
    "Outlier Score",
    "Core Packaging Pattern",
    "Psychological Trigger",
    "Thumbnail Breakdown",
    "Title Formula",
    "Why It Worked",
    "Cold Approach Translation (Concept)",
    "Cold Approach Title",
    "Cold Approach Thumbnail Concept",
    "Notes",
    "Status",
]

SWIPE_FILE = [
    {
        "title": "When a Delivery Driver Outsmarts a Porch Pirate…",
        "channel": "Patrol POV",
        "url": "https://www.youtube.com/watch?v=Sm80NMnoqTY",
        "niche": "Raw Security-Cam Justice/POV",
        "views": "39,315,165",
        "views_num": 39315165,
        "subscribers": 117000,
        "score": "336.0x subs",
        "pattern": "Raw, unproduced security-camera footage framed as \"gotcha\" justice content, with a plain caption labeling exactly what's happening rather than describing the twist — letting the reveal do the work.",
        "trigger": "Curiosity about how the \"outsmarting\" happens (an open loop, no visual spoiler) + the voyeuristic pull of real surveillance footage feeling more authentic than staged content + a satisfying justice payoff implied by the title.",
        "thumbnail": "A security-camera/doorbell-cam style POV shot of a delivery person opening a gate, an on-screen caption \"Delivery Driver 'OPENS GATE'\" in a plain chat-label style, muted outdoor daylight colors, raw unproduced surveillance-footage aesthetic.",
        "formula": "\"When A [Underdog Role] Outsmarts A [Wrongdoer]…\"",
        "why": "The trailing \"…\" withholds the actual twist, the plain surveillance-camera aesthetic (no visible editing or music cues) reads as unquestionably real, and \"outsmarts\" promises a satisfying reversal without revealing how.",
        "translation": "Reframe \"delivery driver outsmarts a porch pirate\" as \"guy outsmarts a dismissive reaction and turns the interaction around\" — same raw, unproduced POV aesthetic and withheld-twist title structure.",
        "ca_title": "When A Guy Outsmarts A Girl's \"I Have A Boyfriend\"…",
        "ca_thumbnail": "Raw, handheld POV shot of the creator mid-conversation with a woman on a sidewalk, an on-screen caption labeling the moment plainly (e.g. \"'I Have A Boyfriend'\") in a chat-bubble style, muted natural daylight, unproduced candid framing matching the surveillance-footage aesthetic.",
        "notes": "The \"plain caption labeling the moment, not describing the twist\" device works because it trusts the raw footage to carry authenticity — over-producing this would undercut it.",
        "status": "Not Adapted",
    },
    {
        "title": "Parents Surprise Bride During Father-Daughter Dance",
        "channel": "David Micklos",
        "url": "https://www.youtube.com/watch?v=MhHVR_0WYgY",
        "niche": "Real Emotional Milestone Moment",
        "views": "10,389,410",
        "views_num": 10389410,
        "subscribers": 38200,
        "score": "272.0x subs",
        "pattern": "A real, unscripted emotional milestone moment captured with the actual spoken words overlaid as on-screen text, letting the sentimentality come from genuine dialogue rather than a title's summary.",
        "trigger": "Universal emotional resonance (parent/child milestone moments) + the caption functioning as an emotional preview that makes viewers want to hear the rest + the bride as the clear, warm visual focal point.",
        "thumbnail": "A real wedding reception scene, father and bride mid-dance, wedding guests visible in soft-focus background, on-screen caption text quoting the actual spoken line over the moment, warm string-light ballroom lighting.",
        "formula": "\"[Family Members] Surprise [Person] During [Milestone Moment]\"",
        "why": "Captioning the actual spoken words (not a generic description) gives viewers an emotional preview strong enough to click for the full context, and the milestone framing taps into a nearly universal emotional trigger.",
        "translation": "Reframe \"parents surprise the bride during a milestone dance\" as \"a genuine, unscripted emotional moment during a real interaction with a woman\" — same real-spoken-words-as-caption device, same warm, sincere tone instead of a flashy hook.",
        "ca_title": "I Told Her Something That Made Her Tear Up On The First Date",
        "ca_thumbnail": "Creator and a woman together at a warmly lit table, her visibly moved and emotional expression as the clear focal point, on-screen caption text quoting the actual line said (e.g. \"'You remind me that people like you still exist...'\"), soft warm lighting.",
        "notes": "Quoting the actual words spoken (not summarizing them) is the transferable device — it works because it's a genuine preview of the emotional payoff, not a vague tease.",
        "status": "Not Adapted",
    },
    {
        "title": "A Hidden Camera Revealed True Kindness",
        "channel": "Grandma Blessing",
        "url": "https://www.youtube.com/watch?v=lZ8oRd0j-c8",
        "niche": "Candid Chivalry/Kindness",
        "views": "854,996",
        "views_num": 854996,
        "subscribers": 15400,
        "score": "55.5x subs",
        "pattern": "A small, genuine act of chivalry caught candidly on a \"hidden camera,\" with the visual itself doing all the emotional work without needing a caption to explain it.",
        "trigger": "Warm, wholesome social proof of good character (a faith-in-humanity payoff) + the \"hidden camera\" framing implying total authenticity, since nobody knew they were being filmed + a simple, instantly-readable visual story.",
        "thumbnail": "A candid street scene, a man kneeling down helping a woman with her belongings, both genuinely engaged in the moment without posing for camera, natural park/outdoor setting, soft daylight.",
        "formula": "\"A Hidden Camera Revealed [Virtue] [Person/Place]\"",
        "why": "The thumbnail needs zero caption to explain what's happening — a person helping a stranger is immediately legible — and \"hidden camera\" as a framing device pre-empts any \"was this staged\" skepticism.",
        "translation": "This is already extremely close to dating/cold-approach content as-is — a genuine, unprompted act of chivalry toward a woman is directly relevant, not a metaphor requiring translation.",
        "ca_title": "A Hidden Camera Caught Him Helping A Stranger Before Ever Talking To Her",
        "ca_thumbnail": "Candid street scene, creator genuinely helping a woman with something small (picking up a dropped item, holding a door), both naturally engaged without posing for camera, soft natural daylight, unstaged framing.",
        "notes": "One of the cleanest possible translations found — the mechanic (genuine chivalry, caught candidly) IS the cold-approach content, not an analogy for it.",
        "status": "Not Adapted",
    },
    {
        "title": "Delivery Guy Was NOT Expecting a Porch Pirate Like This",
        "channel": "Camera Drama",
        "url": "https://www.youtube.com/watch?v=I5bGHUrwo0Y",
        "niche": "Raw Security-Cam Justice/POV",
        "views": "29,892,483",
        "views_num": 29892483,
        "subscribers": 13100,
        "score": "2281.9x subs",
        "pattern": "The same raw security-cam \"gotcha\" genre as Patrol POV's porch-pirate video — an independent channel hitting a massive breakout with the near-identical format confirms this is a proven, repeatable structure, not a one-off fluke.",
        "trigger": "Same as the format's other example: an open-loop twist withheld from the thumbnail, plus the authenticity of raw, unproduced camera footage — reinforced here by a genuinely enormous subscriber multiplier (2281.9x, one of the largest found in this entire project).",
        "thumbnail": "A doorbell/security-cam style POV shot of a delivery person on a porch, an on-screen caption \"Delivery Guy 'Deliver Package'\" labeling the moment plainly, muted daylight residential setting, raw unproduced framing.",
        "formula": "\"[Role] Was NOT Expecting a [Wrongdoer/Twist] Like This\"",
        "why": "Two different channels independently hit huge numbers with the identical raw-security-cam-plus-plain-caption format, which is strong evidence the mechanic itself (not the specific creator or story) is what's driving performance.",
        "translation": "Same translation as the format's other example — reframe the raw POV/plain-caption justice reveal around a social interaction instead of a package theft.",
        "ca_title": "She Was NOT Expecting Me To Say This Back",
        "ca_thumbnail": "Raw, handheld POV shot of the creator mid-conversation with a woman, an on-screen caption labeling the moment plainly (e.g. her exact dismissive line), muted natural daylight, unproduced candid framing.",
        "notes": "Included alongside Patrol POV's entry deliberately — two independent channels succeeding with the same mechanic is stronger proof of a repeatable format than either alone.",
        "status": "Not Adapted",
    },
    {
        "title": "A Blind Man Asked for Help... Most People Walked Away",
        "channel": "Mascal Universe",
        "url": "https://www.youtube.com/watch?v=k4d5_y4AN6I",
        "niche": "Candid Social Experiment/Kindness Test",
        "views": "763,151",
        "views_num": 763151,
        "subscribers": 19700,
        "score": "38.7x subs",
        "pattern": "A vulnerable stranger's real, unscripted request for help captured candidly, with the title stating the discouraging outcome upfront (most walked away) to set up the moment someone doesn't.",
        "trigger": "Moral tension (the viewer wants to know who, if anyone, helps) + protective/empathetic instinct toward a vulnerable person + the \"most people walked away\" framing creating suspense around the exceptions.",
        "thumbnail": "A real street scene, a blind man with a cane standing near a small group of people including a woman, candid unposed body language, a caption reading \"HE ASKED STRANGERS FOR HELP,\" natural daylight.",
        "formula": "\"A [Vulnerable Person] Asked for Help... [Discouraging Outcome/Twist]\"",
        "why": "Stating the discouraging outcome in the title (most walked away) before the viewer even sees the footage creates a moral stake — you watch specifically to see who breaks the pattern.",
        "translation": "Reframe \"a vulnerable stranger asks for help and most ignore him\" as \"a woman gives a guy a real chance when everyone before her didn't\" — same \"most people did X, then...\" suspense structure, applied to social/dating rejection patterns instead of a kindness test.",
        "ca_title": "I Approached 10 Women, Most Walked Away... Then She Didn't",
        "ca_thumbnail": "A real street scene, creator mid-approach near a small group, one woman clearly pausing to engage as the visual focal point (contrasted with others walking past in the background), candid unposed framing, natural daylight.",
        "notes": "The \"most people did X, then this one didn't\" structure is a strong, reusable suspense device independent of the specific scenario.",
        "status": "Not Adapted",
    },
]


def main() -> None:
    client = build_google_sheets_client()
    if not client:
        print("No Google Sheets output was created.")
        return

    if GOOGLE_SPREADSHEET_ID:
        spreadsheet = client.open_by_key(GOOGLE_SPREADSHEET_ID)
    else:
        spreadsheet = client.create("YouTube Outlier Tracker")

    try:
        worksheet = spreadsheet.worksheet(SHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows=100, cols=20)

    worksheet.clear()
    worksheet.append_row(HEADERS)

    values = [
        [
            row["title"], row["channel"], row["url"], row["niche"], row["views"], row["subscribers"], row["score"],
            row["pattern"], row["trigger"], row["thumbnail"], row["formula"], row["why"],
            row["translation"], row["ca_title"], row["ca_thumbnail"], row["notes"], row["status"],
        ]
        for row in SWIPE_FILE
    ]
    worksheet.append_rows(values, value_input_option="USER_ENTERED")
    worksheet.set_basic_filter()

    print(f"Wrote {len(SWIPE_FILE)} swipe file entries to {spreadsheet.url} ({SHEET_NAME})")


if __name__ == "__main__":
    main()
