"""One-off writer for the "General Outlier Models" tab: a curated swipe file of viral
YouTube packaging (title + thumbnail psychology) from outside the cold-approach niche,
each translated into a cold-approach-ready title and thumbnail concept.

Entries here must be real, statistically verified outliers — 100x+ a channel's own
average views, published in the last 90 days — found by general_outlier_finder.py
(run via GitHub Actions, since computing that multiplier needs live channel stats from
the YouTube API). That script only surfaces candidates; picking which ones cleanly
translate into a cold-approach idea and writing the analysis below is a manual step.
This file is not a live API pull itself — run it manually whenever new entries are added.
"""
import os

import gspread

from youtube_outliers import GOOGLE_SPREADSHEET_ID, build_google_sheets_client

SHEET_NAME = os.getenv("GENERAL_OUTLIER_SHEET_NAME", "General Outlier Models")

HEADERS = [
    "Original Video Title",
    "Original Channel",
    "Video URL",
    "Original Niche",
    "Views",
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
        "title": "Alone, Broke, Over 60… I Sold Everything to Start Over (My Real Story)",
        "channel": "Offended Outcast",
        "url": "https://www.youtube.com/watch?v=RndUKvYAhHs",
        "niche": "Personal Reinvention/Redemption Documentary (Vlog)",
        "views": "3,005,620 (channel averages ~26,046/video — a verified 115.4x outlier, published 2026-04-11, within the last 90 days)",
        "pattern": "A raw, unstyled \"diary\" visual (a plain selfie shot, zero graphics/text) paired with a title that does 100% of the emotional heavy lifting — the plainness of the image itself signals \"this is real, not produced,\" building trust and curiosity at once.",
        "trigger": "Vulnerability/empathy (a man exposing failure at a life stage where reinvention feels impossible) + authenticity signal (unpolished visual = \"this can't be staged\") + a stacked-adjective vulnerability hit (\"alone,\" \"broke,\" \"over 60\" — each independently painful, devastating together).",
        "thumbnail": "A plain, close-cropped selfie-style shot of a man in his 60s (ballcap, glasses, plaid flannel shirt) standing alone on a rural dirt road surrounded by forest, looking directly into the camera with a tired, resigned expression, natural overcast daylight, muted green/earth tones, zero text overlay, zero graphic design — the total absence of typical thumbnail polish is itself the authenticity signal.",
        "formula": "[Stacked vulnerable adjectives, comma-separated] + [age/life-stage marker] + \"… I \" + [drastic action taken] + \" (My Real Story)\"",
        "why": "Each word in the opening stack (\"Alone,\" \"Broke,\" \"Over 60\") is independently a strong emotional hook, and stacking three compounds the stakes before the sentence even finishes; \"My Real Story\" explicitly promises non-fiction, and the deliberately unpolished thumbnail backs that promise visually instead of contradicting it with slick production.",
        "translation": "Reframe the \"stacked vulnerable stats + drastic action + authenticity\" mechanic around social isolation instead of financial/life-stage failure — the same raw, unproduced visual style, the same title structure staking out real, specific vulnerability before revealing the turnaround.",
        "ca_title": "Shy, Friendless, 30 Years Old… I Walked Up To A Stranger To Change My Life (My Real Story)",
        "ca_thumbnail": "Plain, close-cropped selfie-style shot of the creator alone on an ordinary sidewalk or park path, looking directly into the camera with a tired, vulnerable expression (not smiling, not performing), natural daylight, muted/neutral colors, zero text overlay and zero graphic polish — the visual should look like a real diary entry, not a produced thumbnail, so the plainness itself signals honesty.",
        "notes": "Verified via general_outlier_finder.py: 115.4x the channel's own average views, published 2026-04-11 (within the 90-day window). A fundamentally different packaging style than flashy/high-production examples — no graphic design needed, low cost to produce, relies entirely on emotional authenticity. Worth testing as a low-effort, high-frequency format.",
        "status": "Not Adapted",
    },
    {
        "title": "I Surprised a Random Subscriber With $10,000",
        "channel": "MrBeast",
        "url": "https://www.youtube.com/watch?v=y1UVAtHALaA",
        "niche": "Reward/Surprise Philanthropy",
        "views": "250,853,135 (506M subscribers; qualifies via the 1M+ absolute view floor)",
        "pattern": "Random selection + an instant, visible cash reward + a literal on-screen proof of legitimacy (a screenshot of the actual subscribe/channel page), making an almost-too-good-to-be-true premise feel verifiably real.",
        "trigger": "Aspirational \"this could be me\" lottery-hope + reward/surprise dopamine + authenticity-proof (the screenshot) defusing skepticism before it forms.",
        "thumbnail": "Three-panel split: left panel shows MrBeast and the recipient together holding an open briefcase stacked with cash, bold \"$10,000\" text; right panel shows a phone screen displaying a YouTube subscribe/channel page as literal proof of the \"random subscriber\" premise. Bright, high-saturation colors, both faces open-mouthed and genuinely happy.",
        "formula": "\"I Surprised a Random [Category] With $[Amount]\"",
        "why": "The premise (\"I randomly picked YOU\") is inherently aspirational for every viewer, and showing the literal proof-of-selection (the phone screen) heads off the \"this is staged\" objection before it forms — trust plus reward in one frame.",
        "translation": "Reframe \"random subscriber gets picked for a cash reward\" as \"random stranger gets picked for a genuine compliment/connection\" — the same visible, verifiable \"here's proof this is really happening\" panel, applied to a social rather than financial reward.",
        "ca_title": "I Walked Up To A Random Stranger And Told Her Exactly Why I Noticed Her",
        "ca_thumbnail": "Two-panel split: left panel shows creator and the woman mid-conversation, both smiling genuinely, warm daylight; right panel shows a phone/notes screen displaying what looks like a \"reason I noticed you\" list as literal proof of the premise, mirroring the subscribe-screenshot device. Bright, warm color grade, both faces open and expressive.",
        "notes": "The \"literal on-screen proof\" panel is a transferable device — anything that visually verifies \"this wasn't staged\" defuses skepticism fast.",
        "status": "Not Adapted",
    },
    {
        "title": "This Trick Shot Almost Made Him QUIT",
        "channel": "Dude Perfect",
        "url": "https://www.youtube.com/watch?v=tJNjuyeRPGg",
        "niche": "Sports Entertainment/Trick Shots",
        "views": "69,607,374 (62.3M subscribers; qualifies via the 1M+ absolute view floor)",
        "pattern": "Title and thumbnail run two different hooks instead of repeating each other — the thumbnail sells the impossible-looking apparatus itself (\"what is this bright orange wall thing?\"), the title sells a separate emotional stake (\"this almost broke him\") not visible in the image at all.",
        "trigger": "Visual disbelief at the apparatus + a completely separate emotional-stakes hook in the title — two independent reasons to click instead of one.",
        "thumbnail": "Two men flanking a large bright-orange wall apparatus with a circular target cutout, both mid-toss with a ball, bold white block text \"IMPOSSIBLE PICKLEBALL WALL,\" bright red/blue accent colors on either side, energetic action-frozen framing.",
        "formula": "[Bold apparatus/spectacle label shown on the thumbnail] + [a separate emotional-stakes claim in the title]",
        "why": "A viewer can be pulled in by either hook independently — the visual mystery of the apparatus, or the emotional promise of the title — which roughly doubles who finds a reason to click, and neither hook spoils the other.",
        "translation": "Reframe \"apparatus + separate emotional title\" as \"a visible social prop that raises its own question + a separate emotional stakes claim in the title\" — a physical prop the image makes you wonder about, paired with an emotional near-quit claim the image doesn't reveal.",
        "ca_title": "This Rejection Almost Made Me Quit Approaching For Good",
        "ca_thumbnail": "Creator holding up a hand-written sign or card reading something cryptic like \"APPROACH #47\" mid-street, a woman visible mid-frame walking past in the background, bold white block text unrelated to the sign (\"ALMOST QUIT\"), bright contrast lighting — the sign creates one curiosity hook, the text creates a second, separate one.",
        "notes": "Reusing two independent hooks in one thumbnail/title pair, rather than one redundant hook, is a genuinely underused technique worth testing.",
        "status": "Not Adapted",
    },
    {
        "title": "Survive 30 Days Chained To A Stranger, Win $250,000",
        "channel": "MrBeast",
        "url": "https://www.youtube.com/watch?v=iYlODtkyw_I",
        "niche": "Stunt/Challenge Entertainment",
        "views": "62,474,338 (506M subscribers; qualifies via the 1M+ absolute view floor)",
        "pattern": "A high-concept forced-pairing premise made instantly graspable in one image (literal handcuffs linking two mismatched people) plus a day-counter implying a long, escalating endurance arc already in progress.",
        "trigger": "Novelty of forced intimacy between strangers (an odd-couple pairing: young man + elderly woman) + \"Day 29\" implying real, sustained stakes rather than a one-off stunt.",
        "thumbnail": "A young man and an elderly woman sitting together on a couch, wrists literally cuffed together with a metal chain, \"DAY 29\" badge in the corner, vintage-framed photos on the wall behind them, warm domestic lighting, his expression mildly pained/resigned, hers content/amused — the mismatch in expressions does a lot of the storytelling.",
        "formula": "\"Survive [Duration] Chained To A Stranger, Win $[Amount]\"",
        "why": "The literal chain makes an abstract premise (\"forced to coexist with a stranger\") instantly, viscerally legible in one glance, the day-counter implies a whole story already unfolding, and the mismatched-pair casting maximizes odd-couple tension.",
        "translation": "Reframe \"physically chained to a stranger\" as \"committed to talking to a stranger no matter what for an extended stretch\" — same instantly-legible visual shorthand for something that can't be escaped, same day-counter implying sustained stakes, same mismatched-pair tension.",
        "ca_title": "I Couldn't Leave Until A Stranger Said Yes - Day 29",
        "ca_thumbnail": "Creator and a woman standing together on a street corner, his wrist visibly zip-tied to a nearby signpost or bench (a clear, literal \"can't leave\" visual), \"DAY 29\" badge in the corner, warm evening lighting, his expression tired but determined, her expression curious/amused.",
        "notes": "A literal, physical visual metaphor for an abstract commitment (chained = \"can't back out\") is highly transferable and doesn't require the literal high concept, just a visible stand-in prop.",
        "status": "Not Adapted",
    },
    {
        "title": "They Convinced A Stranger He Was INVISIBLE",
        "channel": "MotivationSeedz",
        "url": "https://www.youtube.com/watch?v=-2_4Y4X0DhM",
        "niche": "Hidden-Camera Prank/Social Experiment",
        "views": "11,276,941 (98.2K subscribers — 114.8x their own average, a genuine breakout for this small channel)",
        "pattern": "Shows the actual trick mechanic mid-demonstration in the thumbnail (a specific action, captioned) rather than a generic \"prank face\" reaction shot, pre-selling the cleverness of the method itself.",
        "trigger": "Curiosity about a specific, nameable mechanic (\"how do you even convince someone of that?\") + small-channel-breakout energy — raw, unpolished footage reads as more real than a produced prank.",
        "thumbnail": "Two men outdoors in a park-like setting, one gesturing toward the other mid-explanation, bold caption text \"GRAB THE CAN\" pinned to the moment — a specific, concrete instruction caught on camera rather than an abstract reaction shot.",
        "formula": "\"They Convinced A Stranger He Was [Absurd/Specific Claim]\"",
        "why": "Naming the exact, absurd claim in the title creates a specific curiosity gap (\"how do you convince someone of THAT, specifically?\"), and showing the actual mechanic being demonstrated in the thumbnail proves there's a real, teachable method underneath the prank.",
        "translation": "Reframe \"convinced a stranger he was invisible\" as \"convinced a stranger of something specific and absurd about themselves/the situation\" as a way into a real conversation — same \"show the specific mechanic, not just a generic reaction\" thumbnail principle.",
        "ca_title": "I Convinced A Stranger She Already Knew Me From Somewhere",
        "ca_thumbnail": "Creator mid-gesture explaining something to a woman on a street, bold caption text pinned to the exact moment (e.g. \"SAY THIS FIRST\"), casual daylight outdoor setting, unpolished/candid framing rather than a posed reaction shot.",
        "notes": "Small-channel breakout (114.8x average) confirms this doesn't need production value — the specificity of the claim and showing the real mechanic did the work.",
        "status": "Not Adapted",
    },
    {
        "title": "Can YOU convince a STRANGER you're OLD BEST FRIENDS?",
        "channel": "Eric Suerez",
        "url": "https://www.youtube.com/watch?v=UgiYEUfpmyM",
        "niche": "Street Social Experiment/Dare",
        "views": "3,020,380 (1M subscribers; qualifies via the 1M+ absolute view floor)",
        "pattern": "A timer and dollar stakes overlaid directly onto real, candid street footage turns an ordinary interaction into a legible mini-game, while a caption bubble mimics live commentary on what's being said.",
        "trigger": "Direct-address challenge in the title (\"Can YOU...\") invites the viewer to imagine attempting it themselves + gamified stakes (timer + dollar figure) + a voyeuristic feeling of watching an unscripted moment live.",
        "thumbnail": "A man in sunglasses and a cap on a city sidewalk, a stopwatch reading \"20.53s\" and \"$60\" overlaid top-left, a speech-bubble caption \"you good?\" pinned near his face implying his real-time confused reaction, unpolished handheld framing.",
        "formula": "\"Can YOU Convince A Stranger You're [Absurd Relationship Claim]?\"",
        "why": "The direct-address title makes the premise feel like an open challenge to the viewer rather than just a story about the creator, and the overlaid timer/dollar/caption bubble turn a single street moment into a legible mini-game with visible stakes and a live-commentary feel.",
        "translation": "This is already extremely close to a cold-approach premise as-is — the format barely needs to change, just the specific claim/goal being tested.",
        "ca_title": "Can YOU Get A Stranger's Number In Under 30 Seconds?",
        "ca_thumbnail": "Creator mid-conversation with a woman on a city sidewalk, a stopwatch reading \"0:27\" and a phone icon overlaid top-left, a speech-bubble caption capturing her real reaction (e.g. \"wait, really?\"), unpolished handheld framing to preserve the candid, unscripted feel.",
        "notes": "One of the cleanest 1:1 translations found — the underlying format is already a cold-approach video, just aimed at a different specific claim.",
        "status": "Not Adapted",
    },
    {
        "title": "Strangers Witness Bullying – Do They Step Up to Help? (Kindness Test) #kindness",
        "channel": "respect.w",
        "url": "https://www.youtube.com/watch?v=hwYfRcI9cDM",
        "niche": "Social Experiment/Kindness Test",
        "views": "4,471,297 (32.4K subscribers — 138x their own average, a genuine breakout for a small channel)",
        "pattern": "A plain genre-label (\"Social Experiment\") stamped directly on real, unstaged-looking street footage, with the entire premise framed as a moral test of onlookers rather than of the creator.",
        "trigger": "Moral curiosity (\"would people actually help, or just watch?\") + the viewer's own self-assessment (\"would I have stepped in?\") + the authenticity read of visibly candid, non-produced footage.",
        "thumbnail": "Two people on a street corner mid-interaction (one appears distressed, another moving toward them), several passersby visible in the background, bold yellow \"Social Experiment\" banner stamped across the top, muted overcast lighting, unpolished handheld framing.",
        "formula": "\"[Strangers/Subjects] + [Moral Test Scenario] – Do They [Verb]? (Kindness/Test Label)\"",
        "why": "Framing the video as a test of bystanders rather than a story about the creator makes every viewer implicitly grade themselves against the outcome, and the plain \"Social Experiment\" label functions as a genre-trust stamp the same way \"TRUE\" does for horror stories.",
        "translation": "Reframe \"do strangers step up to help a stranger in distress\" as \"do strangers react warmly or coldly to an approach\" — same plain genre-label + candid unstaged-street-footage formula, testing social warmth instead of moral courage.",
        "ca_title": "Strangers Watched Me Get Rejected - Here's What They Did Next (Social Experiment)",
        "ca_thumbnail": "Creator mid-conversation with a woman who's walking away, several passersby visible in the background clearly reacting/watching, bold yellow \"Social Experiment\" banner across the top, muted natural daylight, unpolished handheld framing to preserve the candid feel.",
        "notes": "The plain genre-label stamp (\"Social Experiment,\" like \"TRUE\" for horror) is a reusable trust device across many different specific premises.",
        "status": "Not Adapted",
    },
    {
        "title": "His Teammates Bullied Him So He joined Their Rivals For Revenge | Roger Guedes",
        "channel": "impetus",
        "url": "https://www.youtube.com/watch?v=ATMXOkCm2vE",
        "niche": "Sports Narrative/Underdog Revenge (narrated true-story edit)",
        "views": "8,590,220 (7,570 subscribers — 1,134.8x their own average, an extreme breakout for a tiny channel)",
        "pattern": "A real athlete's documented career story is re-cut and re-captioned into a revenge-arc narrative, with a single emotionally-raw real photo doing all the thumbnail work.",
        "trigger": "Vicarious vindication (watching someone who was wronged \"win\" against the people who wronged them) + the authenticity of a real, unstaged emotional photo rather than a produced shot.",
        "thumbnail": "A real photo of a soccer player sitting on the grass, head down, clearly emotionally raw, a bold red arrow pointing at him, white caption text \"WAS CRYING\" stamped directly over the moment, muted natural stadium lighting.",
        "formula": "\"His [Group] [Wronged Him] So He [Took A Specific Retaliatory Action] For Revenge | [Real Name]\"",
        "why": "This channel didn't create original footage — it found a real, emotionally raw moment and wrapped a revenge narrative around it, proving a strong true-story arc plus one powerful authentic image can outperform original production entirely, even on a tiny channel with almost no baseline audience.",
        "translation": "Reframe \"athlete gets revenge on the team that wronged him\" as \"someone who got rejected/ignored comes back transformed and gets a completely different reaction\" — same real-raw-photo + retaliation-arc caption formula, applied to a real cold-approach moment instead of a repurposed sports photo.",
        "ca_title": "She Rejected Him In High School, So He Came Back Like This",
        "ca_thumbnail": "A real, candid photo of the creator looking visibly down/dejected in an earlier, less put-together state, a bold red arrow pointing at his own past self, white caption text \"GOT REJECTED\" stamped over the moment, muted natural lighting — sets up an implied before/after the video itself resolves.",
        "notes": "Proof a swipe-file entry doesn't need original high production — a real photo plus a sharp narrative caption is enough, especially valuable for a channel just starting out.",
        "status": "Not Adapted",
    },
    {
        "title": "I Fake Married a Stranger to Trick My Family",
        "channel": "Hunter Williams",
        "url": "https://www.youtube.com/watch?v=cXeZ8hkyGHY",
        "niche": "Elaborate Social Deception/Prank",
        "views": "1,474,552 (859K subscribers; qualifies via the 1M+ absolute view floor)",
        "pattern": "The thumbnail openly reveals the twist (\"actor\") rather than hiding it, trading a reveal-based curiosity gap for a dramatic-irony one — the question shifts from \"is this real?\" to \"how did he pull this off, and what happens when the truth comes out?\"",
        "trigger": "Dramatic irony (we're told upfront it's staged, so the tension becomes about the family's reaction and the mechanics of the deception) + the inherent high-stakes taboo of faking a wedding.",
        "thumbnail": "A full wedding ceremony scene — a bride mid-aisle, seated guests — with the creator in a tuxedo in the foreground, an arrow and the label \"actor\" pointing directly at him, clean bright outdoor lighting.",
        "formula": "\"I Fake [High-Stakes Life Event] a Stranger to Trick My [Group]\"",
        "why": "Labeling the twist directly in the thumbnail removes \"is this staged\" skepticism before it can form and replaces it with a stronger hook — dramatic irony — since now the viewer needs to see how the deception unfolds and how the family reacts.",
        "translation": "Reframe \"faked marrying a stranger to trick my family\" as \"asked a stranger to pretend to already know me, to trick my friend group\" — same upfront dramatic-irony labeling device, same taboo-adjacent high-stakes social deception.",
        "ca_title": "I Paid A Stranger To Pretend She Was My Girlfriend At My Family Reunion",
        "ca_thumbnail": "A family gathering scene in the background, creator and a woman standing close together in the foreground looking like a couple, an arrow and the label \"actress\" pointing directly at her, warm natural outdoor lighting.",
        "notes": "Labeling the twist directly in the thumbnail (dramatic irony over mystery) is a strong, underused alternative to the more common \"hide the twist\" approach.",
        "status": "Not Adapted",
    },
    {
        "title": "How to Tell If Your Crush Likes You 🤫 (Psychologically Proven) #shorts #psychology",
        "channel": "Subconscious Code",
        "url": "https://www.youtube.com/watch?v=w1w-K7d45hA",
        "niche": "Relationship Psychology/Listicle",
        "views": "271,037 (3,120 subscribers — 86.9x their own average, a genuine breakout for a tiny channel)",
        "pattern": "Animated, faceless characters illustrate a specific behavioral \"tell,\" paired with an authority-borrowing claim (\"Psychologically Proven\") that lends credibility without needing any real footage or a real face at all.",
        "trigger": "Practical, personally-applicable curiosity (\"does this apply to MY situation right now?\") + borrowed scientific authority + zero production barrier (fully animated, no filming required).",
        "thumbnail": "Simple 3D-animated characters — a blue figure and a red-haired figure — in a hallway-like setting, on-screen caption text \"or if she smiles\" as one item in an implied checklist, flat bright colors, minimal detail.",
        "formula": "\"How To Tell If [Relationship Signal] (Psychologically Proven)\"",
        "why": "\"Psychologically Proven\" borrows scientific authority to make a subjective claim feel objective and trustworthy, and the fully-animated, faceless format means the video can be produced with zero filming, camera-shyness, or location constraints at all.",
        "translation": "This is already squarely in the cold-approach/dating advice niche — the direct translation is a format lesson (animated, checklist-style, authority-claim) rather than a content reframe.",
        "ca_title": "How To Tell If She Wants You To Approach Her (Psychologically Proven)",
        "ca_thumbnail": "Simple animated characters in a public setting (café or street), on-screen caption text listing one specific signal (e.g. \"or if she glances back twice\"), flat bright colors, minimal detail, no real faces needed.",
        "notes": "A genuinely zero-cost format (fully animated, no filming) that could run as a low-effort, high-frequency companion series to in-field approach footage.",
        "status": "Not Adapted",
    },
    {
        "title": "Confronting Axe Murderer at Haunted Magnolia Hotel",
        "channel": "Sam and Colby",
        "url": "https://www.youtube.com/watch?v=CFUSTfuodjg",
        "niche": "Horror Investigation/Paranormal",
        "views": "7,972,345 (15.9M subscribers; qualifies via the 1M+ absolute view floor)",
        "pattern": "A real, specific, named location plus a named historical threat anchors the fear in something researchable/real, while a red arrow points to an ambiguous ghostly figure in the thumbnail that's never fully explained.",
        "trigger": "Fear + specificity (a named place and named killer feel more real than generic \"haunted house\" content) + the ambiguity trigger (a barely-visible figure the arrow insists is there, daring you to look closer).",
        "thumbnail": "A dark, moody night shot of an ornate old hotel with lit windows, a translucent, ghostly face barely visible in one upper window, a bold red arrow pointing directly at it, the creator's serious/unsettled face in the foreground.",
        "formula": "\"Confronting [Named Threat] at Haunted [Named, Specific Location]\"",
        "why": "Naming a real, specific location and a specific historical threat makes the premise feel grounded and researchable rather than generic, and the arrow pointing at an ambiguous figure forces active scrutiny — the viewer has to click through just to decide for themselves whether they see it too.",
        "translation": "Reframe \"confronting a named historical threat at a named haunted location\" as \"confronting a named, specific type of rejection/social fear at a named, real, high-difficulty location\" — same grounding-in-specificity device, same arrow-pointing-at-ambiguity trick.",
        "ca_title": "Approaching The Most Intimidating Group At The Scariest Bar In Miami",
        "ca_thumbnail": "A dark, moody bar exterior shot, a red arrow pointing at a specific intimidating-looking group barely visible through a window or doorway, creator's serious/nervous expression in the foreground, similar moody nighttime lighting.",
        "notes": "Naming real specifics (a real place, a real threat/difficulty) instead of staying generic is a strong, easy device to reuse for approach-difficulty framing.",
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
            row["title"], row["channel"], row["url"], row["niche"], row["views"],
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
