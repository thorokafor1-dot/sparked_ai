"""One-off writer for the "General Shorts Outliers" tab: a curated swipe file of
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

SHEET_NAME = os.getenv("GENERAL_SHORTS_SHEET_NAME", "General Shorts Outliers")

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
    {
        "title": "Simple Girl To Princess Look 👸 Amazing Glow Up #shorts",
        "channel": "Happy Wife",
        "url": "https://www.youtube.com/watch?v=GXmlXosvg3k",
        "niche": "Transformation Reveal/Glow Up",
        "views": "14,982,516",
        "views_num": 14982516,
        "subscribers": 45900,
        "score": "326.4x subs",
        "pattern": "A dramatic before/after transformation reveal where the thumbnail shows only the polished \"after\" — an elegant, glamorous result — with the title's contrast (\"Simple Girl\" vs \"Princess\") supplying the transformation arc the image doesn't show.",
        "trigger": "Aspirational curiosity (\"how did she get from A to B?\") + the visual reward of an already-impressive \"after\" shot pulling viewers in on looks alone + a relatable starting point (\"simple girl\") making the outcome feel attainable, not just for celebrities.",
        "thumbnail": "A woman in an elegant pink dress in an ornate, upscale interior (grand ceiling, warm gold lighting), a man partially visible beside her, polished and glamorous styling, warm high-end color grade.",
        "formula": "\"[Ordinary Starting Point] To [Aspirational Outcome] Look\"",
        "why": "Showing only the impressive \"after\" in the thumbnail (not a split before/after) makes the image itself aspirational enough to click on, while the title's stated contrast promises a satisfying transformation story underneath.",
        "translation": "Reframe \"ordinary girl to princess look\" as \"overlooked to unforgettable\" — same relatable-starting-point-to-aspirational-outcome contrast, applied to how a woman is perceived/responded to rather than a styling makeover.",
        "ca_title": "Invisible To Unforgettable: How She Changed The Way Every Room Reacted To Her",
        "ca_thumbnail": "A woman looking confident and radiant in an elevated real-world setting (a nice restaurant or event), warm flattering lighting, polished styling, positioned as the clear visual star of the frame.",
        "notes": "A 326x subscriber breakout confirms the \"aspirational after-shot only\" thumbnail approach travels far beyond a beauty-niche audience.",
        "status": "Not Adapted",
    },
    {
        "title": "The Wedding Stopped When She Revealed His Biggest Secret...",
        "channel": "Good Vibes Stories",
        "url": "https://www.youtube.com/watch?v=ddDkIrcZZ4Q",
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
        "title": "₹500 vs ₹50 #skincare #glowup",
        "channel": "Uneven Glow",
        "url": "https://www.youtube.com/watch?v=ohnvRiMi-rY",
        "niche": "Budget vs. Premium Comparison",
        "views": "393,288",
        "views_num": 393288,
        "subscribers": 914,
        "score": "430.3x subs",
        "pattern": "A real, unpolished selfie-style comparison between a cheap and expensive version of the same product, with the price contrast alone doing the entire hook — no dramatic claim needed.",
        "trigger": "Practical, money-relevant curiosity (\"is the expensive one actually worth it?\") + the concrete, specific price contrast being instantly legible + zero-production authenticity (a real person testing on themselves).",
        "thumbnail": "A real, plain selfie-style shot of a woman applying a skincare product to her own face, casual home setting, on-screen price labels visible, unproduced handheld framing.",
        "formula": "\"₹/$[Low Price] vs ₹/$[High Price] #[category]\"",
        "why": "A concrete price-vs-price contrast is a self-explanatory hook that needs no additional claim or drama, and testing on a real, unpolished self (not a produced beauty shot) makes the comparison feel trustworthy rather than sponsored.",
        "translation": "Reframe \"cheap vs. expensive skincare\" as \"free advice vs. paid coaching\" or \"a scripted opener vs. genuine curiosity\" — same concrete side-by-side contrast format, applied to comparing two approaches instead of two products.",
        "ca_title": "Free Advice vs $500 Coaching: Which One Actually Gets You A Number?",
        "ca_thumbnail": "A real, plain selfie-style or handheld shot of the creator testing two approaches side by side, on-screen labels for each side, casual unproduced setting matching the authenticity of the original.",
        "notes": "A massive 430x subscriber breakout on a tiny channel (under 1,000 subscribers) shows a concrete price-contrast hook alone can travel very far with zero production value.",
        "status": "Not Adapted",
    },
    {
        "title": "Inside Michael Jackson's abandoned school",
        "channel": "LordExplores",
        "url": "https://www.youtube.com/watch?v=atNiWdHNPNU",
        "niche": "Forbidden Access/Urban Exploration",
        "views": "3,829,903",
        "views_num": 3829903,
        "subscribers": 258000,
        "score": "46.3x channel avg",
        "pattern": "The same forbidden-access exploration format seen elsewhere in this project, here anchored to a globally famous named celebrity for maximum grounded specificity — the first example of this proven format in the Shorts-specific tab.",
        "trigger": "Forbidden curiosity (seeing inside a real, famous person's abandoned property) + the specificity of a world-famous name making the premise instantly recognizable + decay/mystery visuals reinforcing the \"frozen in time\" feeling.",
        "thumbnail": "A real exterior shot of a plain suburban house with a white picket fence, on-screen caption \"Part 1\" and \"Michael Jackson's childhood home,\" overcast daylight, unproduced documentary-style framing.",
        "formula": "\"Inside [World-Famous Name]'s Abandoned [Place]\"",
        "why": "Naming a globally recognizable person (rather than a regional celebrity) maximizes how many viewers instantly understand the premise's significance without any further explanation needed.",
        "translation": "Reframe \"inside a world-famous person's abandoned property\" as \"approaching at a real, world-famous, extremely difficult venue\" — same maximum-name-recognition-for-instant-stakes device.",
        "ca_title": "Approaching Women At The World's Most Exclusive Nightclub",
        "ca_thumbnail": "A real venue exterior shot, a globally recognizable location name visible on-screen, creator approaching a specific real group, unproduced documentary-style framing.",
        "notes": "Same proven mechanic as the long-form exploration entries, included here specifically because the Shorts tab didn't have an example of it yet.",
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
