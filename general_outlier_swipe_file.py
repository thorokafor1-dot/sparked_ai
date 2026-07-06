"""One-off writer for the "General Outlier Models" tab: a curated swipe file of viral
YouTube packaging (title + thumbnail psychology) from outside the cold-approach niche,
each translated into a cold-approach-ready title and thumbnail concept.

This is a hand-curated reference document, not a live API pull like youtube_outliers.py —
run manually whenever the swipe file needs new entries.
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
        "title": "$456,000 Squid Game In Real Life!",
        "channel": "MrBeast",
        "url": "https://www.youtube.com/watch?v=0e3GPea1Tyg",
        "niche": "Stunt/Challenge Entertainment",
        "views": "~400,000,000 (100M in first 3 days; est., still climbing)",
        "pattern": "Extreme stakes + real-world recreation of a globally-known fictional premise, visualized entirely in the thumbnail via facial shock + huge dollar figure.",
        "trigger": "Curiosity gap + FOMO + cultural-reference recognition (instant familiarity from Squid Game) + a concrete stakes anchor.",
        "thumbnail": "Wide shot of the actual Squid Game set (instant recognition), MrBeast in the iconic green tracksuit with an exaggerated shocked/intense expression, huge bold yellow text \"$456,000\", high color contrast (pink/teal set vs. plain text), one clear focal point (his face) surrounded by the crowd of contestants.",
        "formula": "[Exact Dollar Amount] + [Recognizable Cultural Reference] + \"In Real Life\"",
        "why": "It borrowed pre-built curiosity from a global phenomenon and answered an unspoken question — \"could this actually happen to real people, for real money?\" — while the dollar figure made the stakes concrete and screenshot-able.",
        "translation": "Take a well-known cultural \"impossible challenge\" premise and reframe it around social risk instead of physical elimination — a real-world \"final boss\" of rejection, escalating in stakes, until only one method of approaching works.",
        "ca_title": "I Turned Getting Rejected Into A $10,000 Game",
        "ca_thumbnail": "Wide shot of a busy street corner styled like a competition set (rope barriers, a giant scoreboard reading \"0/50 Approached\"), creator front-and-center with a shocked/intense grin, arms out mid-gesture, one woman mid-frame looking back over her shoulder with a curious expression, bold yellow text \"$10,000\" in the corner, high-contrast lighting (warm street lights vs. cool blue shadows).",
        "notes": "Borrow the \"concrete stakes + cultural recognition\" mechanic, not the literal show.",
        "status": "Not Adapted",
    },
    {
        "title": "EXPLODING Glitter Bomb 4.0 vs. Package Thieves",
        "channel": "Mark Rober",
        "url": "https://www.youtube.com/watch?v=3c584TGG7jQ",
        "niche": "Engineering/Revenge Prank",
        "views": "~40,000,000 (est.; series has repeatedly hit 50-100M per installment)",
        "pattern": "Poetic justice — build an elaborate device that punishes a wrongdoer, then show their shocked reaction as the payoff.",
        "trigger": "Schadenfreude / moral satisfaction (watching a \"bad guy\" get what's coming) + anticipation of an unseen payoff.",
        "thumbnail": "Freeze-frame of a porch pirate's face mid-explosion, covered in glitter, pure shock, glitter cloud frozen mid-air, bold text \"4.0\" implying an ongoing saga, bright colors against a dark porch/night setting for contrast.",
        "formula": "[Escalating Version Number] + [Device/Weapon Name] + \"vs.\" + [The Wrongdoer]",
        "why": "It promises a deserved consequence for a universally-hated act, the \"vs.\" framing turns an inanimate device into a character the audience roots for, and the version number implies a whole saga worth binging.",
        "translation": "Reframe \"the device that exposes wrongdoing\" as \"the approach method that exposes fake confidence\" — build a whole tested \"system\" version that reveals whether someone's excuse for not approaching holds up, and show the satisfying moment it collapses.",
        "ca_title": "I Built A Rejection-Proof Approach (Guys Couldn't Believe It Worked)",
        "ca_thumbnail": "Split-second reaction shot of a skeptical friend's face mid-disbelief (mouth open, eyebrows raised) watching from the background, creator mid-conversation with a woman who's laughing/smiling in the foreground, bold text \"V4.0\" in the corner signaling a tested system, warm daylight with a blurred urban backdrop, one clear focal point on the friend's shocked face.",
        "notes": "The \"version number\" framing (1.0, 2.0, 3.0...) is a strong recurring-series hook worth reusing across multiple videos.",
        "status": "Not Adapted",
    },
    {
        "title": "Scammers Wanted $17,000 - They Watch Me Waste It All",
        "channel": "Kitboga",
        "url": "https://www.youtube.com/watch?v=hp6OJXSA3NI",
        "niche": "Scam-Baiting/Justice Content",
        "views": "~5,000,000 (est.)",
        "pattern": "Turn the tables on a predator in real time, with the audience watching the villain slowly realize they've lost.",
        "trigger": "Justice/karma satisfaction + suspense (will he get caught?) + a specific dollar stakes anchor.",
        "thumbnail": "Kitboga's exaggerated bait-persona shown mid-laugh next to a phone, bold dollar figure \"$17,000\" in red/white for urgency, high contrast between his amused expression and the implied threat.",
        "formula": "[Wrongdoer] + \"Wanted\" + [Dollar Amount] + \"- They Watch Me Waste It All\"",
        "why": "The dollar amount anchors the stakes instantly, \"they watch me\" implies a real-time con-artist perspective flip, and \"waste it all\" promises a complete, satisfying resolution rather than a partial win.",
        "translation": "Reframe \"scammers trying to con me\" as \"excuses/limiting beliefs trying to stop me\" — personify the internal obstacle (approach anxiety) as an opponent being defeated on camera in real time.",
        "ca_title": "My Anxiety Bet Me I'd Chicken Out - I Wasted It All On Camera",
        "ca_thumbnail": "Split-screen/double-exposure style: creator looking nervous and sweaty on one side fading into a confident, laughing version of himself mid-conversation with a woman on the other, bold red text \"0 Chickened Out\" in the corner, high contrast red vs. cool blue color grade to visualize the internal battle.",
        "notes": "The \"dollar amount as stakes\" trick can be swapped for \"number of times I almost bailed\" as an internal-stakes equivalent.",
        "status": "Not Adapted",
    },
    {
        "title": "The interior of this abandoned MEGA MANSION will leave you SPEECHLESS!",
        "channel": "Exploring the Unbeaten Path",
        "url": "https://www.youtube.com/watch?v=NAf3UCCXugU",
        "niche": "Urban Exploration/Mystery",
        "views": "~2,000,000 (est.)",
        "pattern": "Peek behind a forbidden/hidden door into a world of wealth left frozen in time, with the mystery of \"why was this abandoned?\" left unanswered.",
        "trigger": "Forbidden curiosity (voyeurism into a private, hidden space) + status envy/awe + an unresolved open loop.",
        "thumbnail": "Wide, dramatically-lit shot of an opulent room (chandelier, decayed luxury furniture), one small human silhouette (the explorer) dwarfed by the scale of the space, bold text \"SPEECHLESS\" as an emotional promise, natural light beams cutting through dust for atmosphere.",
        "formula": "\"The [Adjective] of this [Forbidden/Hidden Place]\" + \"will leave you [Emotional Promise]\"",
        "why": "It promises access to something the viewer could never see themselves, pairs a strong visual with a bold emotional promise instead of describing the content, and leaves the \"why was it abandoned\" question open.",
        "translation": "Reframe \"hidden mansion\" as \"the hidden reason a specific type of woman keeps saying no\" or \"what actually happens in her head during an approach\" — access to a normally-invisible perspective.",
        "ca_title": "What Actually Goes Through Her Head In The First 3 Seconds Will Leave You SPEECHLESS",
        "ca_thumbnail": "Close, dramatically-lit shot of a woman's face mid-thought (eyes slightly averted, subtle smile, contemplative), creator blurred in the background approaching, bold text \"SPEECHLESS\" bottom third, warm cinematic lighting with shallow depth of field so her expression is the single clear focal point.",
        "notes": "The \"forbidden access\" mechanic pairs well with a curiosity-gap title that promises insight rather than footage.",
        "status": "Not Adapted",
    },
    {
        "title": "3 Genuinely Scary TRUE Horror Stories",
        "channel": "Mr. Nightmare",
        "url": "https://www.youtube.com/watch?v=z4M6_hOuBts",
        "niche": "Horror Storytelling",
        "views": "~3,000,000 (est.)",
        "pattern": "Anthology framing (\"3 stories\") + a claim of authenticity (\"TRUE\") to raise stakes above fiction.",
        "trigger": "Fear + the \"this could happen to me\" realism trigger + anthology completionism (you want all 3, not just 1).",
        "thumbnail": "Dark, grainy first-person-style image (POV through a window or car mirror at night), a barely-visible shadow/figure just out of clear focus, bold white/red text \"TRUE\" as an authenticity stamp, near-monochrome color for dread.",
        "formula": "[Number] + \"Genuinely/Truly\" + \"Scary TRUE\" + [Content Type] + \"Stories\"",
        "why": "\"TRUE\" removes the safety net of \"it's just fiction,\" the number promises a complete anthology, and the ambiguous, barely-visible thumbnail figure creates dread through what's NOT shown.",
        "translation": "Reframe \"true scary stories\" as \"true rejection stories\" — raw, first-person accounts of the worst approaches gone wrong, using the same anthology + authenticity stamp.",
        "ca_title": "3 Genuinely Brutal TRUE Rejection Stories",
        "ca_thumbnail": "Dim, moody nighttime street shot, creator's face half in shadow with a wincing/uncomfortable expression, a woman's back turned and walking away barely in frame (not fully shown), bold white text \"TRUE\" stamped in the corner, desaturated color grade for a serious, authentic tone.",
        "notes": "The \"ambiguity over full reveal\" thumbnail principle — showing just enough to suggest, not confirm — transfers directly.",
        "status": "Not Adapted",
    },
    {
        "title": "THE RISE TO THE UFC: Michael Chandler Documentary | Against All Odds",
        "channel": "Combat sports documentary channel (verify via link)",
        "url": "https://www.youtube.com/watch?v=uRP_WvPJJ7A",
        "niche": "Combat Sports Underdog Documentary",
        "views": "~1,000,000 (est.)",
        "pattern": "Underdog-to-elite arc framed as a documentary, not a highlight reel — \"against all odds\" promises a full transformation story, not just a win.",
        "trigger": "Aspiration/inspiration + a respect-earning narrative (from nobody to somebody) + stakes tied to a real, known outcome.",
        "thumbnail": "Intense, determined close-up of the fighter's face (sweat, focus, slight snarl), dramatic low-angle framing, bold text \"AGAINST ALL ODDS\" as the emotional thesis, high-contrast dark background making the face pop.",
        "formula": "\"THE RISE TO [Elite Destination]\": [Name] Documentary | Against All Odds",
        "why": "It packages a career (which could be dry) as a hero's-journey documentary, \"Against All Odds\" pre-loads the emotional stakes before a single frame plays, and naming the elite destination gives the story a concrete finish line.",
        "translation": "Reframe \"rise to elite fighter\" as \"rise from someone who couldn't talk to women to someone who does it fearlessly\" — same hero's-journey documentary structure, same emotional thesis.",
        "ca_title": "THE RISE FROM INVISIBLE TO UNIGNORABLE: My Documentary | Against All Odds",
        "ca_thumbnail": "Intense close-up of creator's determined face, slight low-angle for power, one hand adjusting a jacket collar (a confidence gesture), bold text \"AGAINST ALL ODDS\" across the bottom, dark moody background with a single warm rim light outlining his silhouette.",
        "notes": "\"Against All Odds\" as a modular subtitle works as a reusable branding device across a whole documentary-style series.",
        "status": "Not Adapted",
    },
    {
        "title": "I Convinced a Stranger to Rob a Bank",
        "channel": "Mack",
        "url": "https://www.youtube.com/watch?v=hh3JCjOHG_E",
        "niche": "Elaborate Social Experiment/Prank",
        "views": "~5,200,000",
        "pattern": "An escalating, elaborate deception with real moral stakes — the audience knows the twist, the subject doesn't, creating dramatic irony.",
        "trigger": "Dramatic irony (viewer knows more than the subject) + moral tension (is this going too far?) + disbelief the setup could be pulled off.",
        "thumbnail": "The unsuspecting subject's tense, serious face mid-conversation, creator half-turned toward camera with a knowing/mischievous look, background hints at the elaborate set (blurred lights/signage), bold minimal text implying stakes, cool blue-toned lighting for tension.",
        "formula": "\"I Convinced [Someone] To [Escalating/Unbelievable Action]\"",
        "why": "\"I Convinced\" implies total control over an unbelievable outcome, the specific high-stakes action creates immediate moral tension, and the dramatic irony (we know it's staged, the subject doesn't) makes viewers need to see how it unravels.",
        "translation": "Reframe \"convinced a stranger to rob a bank\" as \"convinced a stranger's friend group I was already someone they knew\" — an elaborate social-engineering approach where the audience knows the setup and the target doesn't.",
        "ca_title": "I Convinced An Entire Friend Group I Was Already Invited",
        "ca_thumbnail": "Tense, half-suspicious face of one group member looking directly at the creator, creator mid-frame giving a subtle knowing smirk toward the camera (breaking the fourth wall), background shows a blurred group of people at a table/bar, minimal bold text \"ALREADY INVITED\", warm ambient bar lighting with one sharp highlight on the suspicious face.",
        "notes": "Dramatic irony (a camera-aware knowing look) is a strong, underused device for cold approach packaging.",
        "status": "Not Adapted",
    },
    {
        "title": "Ping Pong Trick Shots 4 | Dude Perfect",
        "channel": "Dude Perfect",
        "url": "https://www.youtube.com/watch?v=DkW87-Z9FAY",
        "niche": "Sports Entertainment/Trick Shots",
        "views": "~30,000,000 (est.)",
        "pattern": "Impossible-looking feat shown mid-action at its most visually absurd moment, with a sequel number implying a whole trusted franchise.",
        "trigger": "Disbelief (\"how is that possible?\") + franchise trust (numbered sequel implies proven quality) + pure spectacle.",
        "thumbnail": "Freeze-frame at the peak/most absurd moment of a trick shot (ball mid-air in an impossible trajectory), exaggerated celebratory reactions from the group in the background, bright saturated colors, bold number \"4\" signaling franchise depth.",
        "formula": "[Trick/Feat Type] + \"Trick Shots\" + [Sequel Number] + \"| \" + [Trusted Brand Name]",
        "why": "The freeze-frame captures a physically-impossible-looking moment that demands explanation, the sequel number signals \"this franchise has already proven itself,\" and the brand name acts as a trust/quality stamp.",
        "translation": "Reframe \"impossible trick shot\" as \"impossible social read/save\" — a moment where a conversation looked completely dead and got flipped, captured at its most dramatic beat, branded as a numbered recurring series.",
        "ca_title": "Impossible Approach Saves 4",
        "ca_thumbnail": "Freeze-frame at the exact turnaround moment — woman mid-laugh with her hand covering her mouth in surprise, creator mid-gesture like he just said something bold, small group of onlookers in the background reacting, bright warm-toned color grade, bold number \"4\" in the corner as a franchise marker.",
        "notes": "The \"trusted numbered franchise\" branding device works well as a recurring cold approach series format, not just a one-off.",
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
