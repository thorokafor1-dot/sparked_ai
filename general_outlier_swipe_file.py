"""One-off writer for the "General Outlier Models" tab: a curated swipe file of viral
YouTube packaging (title + thumbnail psychology) from outside the cold-approach niche,
each translated into a cold-approach-ready title and thumbnail concept.

Entries here must be real, statistically verified outliers found by
general_outlier_finder.py (run via GitHub Actions, since computing view/subscriber/
channel-average multipliers needs live channel stats from the YouTube API) — and must
be genuine RELATIVE outliers, not just big channels doing normal big-channel numbers.
Concretely: a video only qualifies on raw views (1M+) if the channel has under 100K
subscribers, where 1M+ views is itself remarkable. Channels at or above 100K subscribers
must qualify via a relative signal instead — 5x+ subscriber breakout or 20x+ channel-
average breakout — since 1M views means nothing for a channel whose average video
already clears that. (An earlier batch of entries let big channels like MrBeast qualify
purely on absolute views; those got removed once this rule was tightened.)

That finder script only surfaces candidates; picking which ones cleanly translate into
a cold-approach idea — both the title AND the thumbnail concept — and writing the
analysis below is a manual step. Cold-approach thumbnail concepts should put a woman
front and center as the visual star (per the channel's packaging convention), regardless
of whether the original video's thumbnail did. Entries must also be in English — a
language filter (is_english_title in youtube_outliers.py) now screens the finder's
output, but it only catches non-Latin scripts, not other Latin-script languages, so
still verify by eye. This file is not a live API pull itself — run it manually whenever
new entries are added.
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
        "title": "Alone, Broke, Over 60… I Sold Everything to Start Over (My Real Story)",
        "channel": "Offended Outcast",
        "url": "https://www.youtube.com/watch?v=RndUKvYAhHs",
        "niche": "Personal Reinvention/Redemption Documentary (Vlog)",
        "views": "3,005,620 (channel averages ~26,046/video — a verified 115.4x outlier, published 2026-04-11, within the last 90 days)",
        "views_num": 3005620,
        "subscribers": None,
        "score": "115.4x channel avg",
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
        "title": "They Convinced A Stranger He Was INVISIBLE",
        "channel": "MotivationSeedz",
        "url": "https://www.youtube.com/watch?v=-2_4Y4X0DhM",
        "niche": "Hidden-Camera Prank/Social Experiment",
        "views": "11,276,941 (98.2K subscribers — 114.8x its subscriber count in views, a genuine breakout for this small channel)",
        "views_num": 11276941,
        "subscribers": 98200,
        "score": "114.8x subs",
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
        "title": "Strangers Witness Bullying – Do They Step Up to Help? (Kindness Test) #kindness",
        "channel": "respect.w",
        "url": "https://www.youtube.com/watch?v=hwYfRcI9cDM",
        "niche": "Social Experiment/Kindness Test",
        "views": "4,471,297 (32.4K subscribers — 138x its subscriber count in views, a genuine breakout for a small channel)",
        "views_num": 4471297,
        "subscribers": 32400,
        "score": "138x subs",
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
        "views": "8,590,220 (7,570 subscribers — 1,134.8x its subscriber count in views, an extreme breakout for a tiny channel)",
        "views_num": 8590220,
        "subscribers": 7570,
        "score": "1134.8x subs",
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
        "title": "How to Tell If Your Crush Likes You 🤫 (Psychologically Proven) #shorts #psychology",
        "channel": "Subconscious Code",
        "url": "https://www.youtube.com/watch?v=w1w-K7d45hA",
        "niche": "Relationship Psychology/Listicle",
        "views": "271,037 (3,120 subscribers — 86.9x its subscriber count in views, a genuine breakout for a tiny channel)",
        "views_num": 271037,
        "subscribers": 3120,
        "score": "86.9x subs",
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
        "title": "Millionaire Ignores Man In Need Prank!",
        "channel": "Crime Catchers",
        "url": "https://www.youtube.com/watch?v=Crd2Qr1zSOM",
        "niche": "Status/Wealth-Disguise Social Test",
        "views": "11,510,047 (224K subscribers — 51.4x its subscriber count in views, a genuine breakout)",
        "views_num": 11510047,
        "subscribers": 224000,
        "score": "51.4x subs",
        "pattern": "A social status/wealth-disguise test captured candidly, where the caption spells out the subject's authentic in-the-moment reaction rather than describing the setup.",
        "trigger": "Curiosity about how people treat someone based on perceived status (would they help a \"millionaire\" who looks like they need help, or ignore someone who seems poor?) + the voyeuristic pull of a caught, unscripted reaction.",
        "thumbnail": "A man laughing genuinely inside an elevator, a small \"*LAUGHS*\" caption capturing his real-time reaction, casual candid framing.",
        "formula": "\"[Status Label] [Verb: Ignores/Helps] [Someone] In Need Prank!\"",
        "why": "Framing the test around a status label immediately raises a judgment question the viewer wants answered, and capturing a genuine, specific reaction (not a generic shocked face) makes the moment feel authentically unscripted.",
        "translation": "Reframe \"does a disguised millionaire get ignored\" as \"does she react differently to me depending on how I show up\" — same status-test mechanic, same real-reaction-as-caption device, aimed at social/attraction dynamics instead of wealth perception.",
        "ca_title": "I Approached The Same Girl Twice - Once Looking Rough, Once Looking Sharp",
        "ca_thumbnail": "A woman mid-reaction with a genuine, specific expression (visibly warmer and more interested) as the clear focal point of the frame, a small caption capturing her real reaction in words, candid unstaged framing, casual daylight street setting.",
        "notes": "Using the subject's own real, specific reaction as the caption (not a generic \"SHOCKED\") makes the moment feel authentic rather than staged.",
        "status": "Not Adapted",
    },
    {
        "title": "A Billionaire Watched His Son Beg Strangers for Shoes  Nobody Helped  Then She Appeared",
        "channel": "Afro Seoul — Cinematic Stories",
        "url": "https://www.youtube.com/watch?v=SHq7DfX38vM",
        "niche": "Narrated Moral Story/Social Class Drama",
        "views": "168,316 (4,470 subscribers — 37.7x its subscriber count in views, a genuine breakout for a tiny channel)",
        "views_num": 168316,
        "subscribers": 4470,
        "score": "37.7x subs",
        "pattern": "A staged, narrated moral vignette where a vulnerable child is ignored by everyone until one woman steps in — the thumbnail alone tells the entire emotional arc via a single cinematic image.",
        "trigger": "Moral tension (will anyone help?) + a cinematic, emotionally-loaded visual (a well-dressed woman kneeling to help a barefoot child) + the \"then she appeared\" framing promising a turnaround hero.",
        "thumbnail": "A woman in business attire kneeling on a wet nighttime city street, gently helping a barefoot child put on new shoes, dramatic neon-lit backdrop, cinematic lighting and color grade.",
        "formula": "\"[Powerful Observer] Watched [Vulnerable Person] [Ignored By Everyone]… Then [Hero] Appeared\"",
        "why": "The thumbnail is a complete emotional story in one frame — you don't need the title to understand the stakes — and \"then she appeared\" promises a resolution without revealing it.",
        "translation": "Reframe \"a stranger steps in to help a child when nobody else would\" as \"a woman responds warmly when a guy's approach is being coldly dismissed by everyone else\" — same single-frame emotional-arc thumbnail, same hero-appears structure.",
        "ca_title": "Every Girl Ignored Him… Then She Didn't",
        "ca_thumbnail": "A woman warmly engaging with the creator on a city street at night, other people visible walking past/ignoring him in the background, cinematic moody lighting, her posture and expression clearly the emotional turning point of the frame.",
        "notes": "A single, cinematic frame that tells the whole emotional arc without needing the title is a high-value, if production-intensive, device.",
        "status": "Not Adapted",
    },
    {
        "title": "If Your Crush Starts Flirting With You 🤫 #shorts #psychology",
        "channel": "Decoded Logic",
        "url": "https://www.youtube.com/watch?v=BCbKFnpwR_4",
        "niche": "Relationship Psychology/Listicle (Animated)",
        "views": "2,117,303 (110K subscribers — 19.2x its subscriber count in views, a genuine breakout)",
        "views_num": 2117303,
        "subscribers": 110000,
        "score": "19.2x subs",
        "pattern": "The same zero-filming animated checklist format as the Subconscious Code entry — a second, independent channel succeeding with it confirms it's a repeatable style, not a fluke.",
        "trigger": "Practical, personally-applicable curiosity + zero-friction animated production + borrowed authority via the \"psychology\" framing.",
        "thumbnail": "Simple 3D-animated characters — a red figure labeled \"Crush\" and a blue figure labeled \"You\" — in a hallway setting, \"flirting\" captioned near the interaction.",
        "formula": "\"If Your Crush Starts [Specific Behavior] #psychology\"",
        "why": "Same mechanism as the other animated example — no filming, no face required, a specific relatable behavioral cue as the hook.",
        "translation": "Already squarely in-niche — same format, direct lesson for a low-cost recurring companion series.",
        "ca_title": "If She Does This, She Wants You To Approach",
        "ca_thumbnail": "Simple animated characters in a public setting, on-screen caption naming one specific behavioral signal, flat bright colors, no real faces needed.",
        "notes": "Including a second example of this exact format alongside Subconscious Code's is deliberate — two independent channels succeeding with it is stronger evidence it's worth building a recurring series around.",
        "status": "Not Adapted",
    },
    {
        "title": "Asking strangers for gas in the hood #fypシ゚viral #360video #detroit #bikelife #socialexperiment",
        "channel": "MotorPsycho",
        "url": "https://www.youtube.com/watch?v=pEGdCxg37as",
        "niche": "Street Social Experiment",
        "views": "493,518 (51.6K subscribers — 9.6x its subscriber count in views, a genuine breakout)",
        "views_num": 493518,
        "subscribers": 51600,
        "score": "9.6x subs",
        "pattern": "A real, candid street interaction asking strangers for a small favor, filmed in a specific, characterful location that gives it grounded, unpolished authenticity.",
        "trigger": "Curiosity about how strangers respond to a small, specific ask + the specificity of the real location adding grounded authenticity + the voyeuristic pull of real, unscripted interactions.",
        "thumbnail": "A real street scene, a man in casual clothes handing over cash/items to another man, plain daylight urban backdrop, unproduced handheld framing.",
        "formula": "\"Asking Strangers For [Small Specific Favor] In [Specific Real Location]\"",
        "why": "Naming a specific, real location (not generic \"the city\") grounds the premise, and asking for something small and concrete makes the interaction easy to follow and the outcome easy to judge.",
        "translation": "Reframe \"asking strangers for gas\" as \"asking strangers for directions/a favor as an opener\" — same specific-location grounding and small-concrete-ask structure, aimed at initiating conversation with women instead of testing generosity.",
        "ca_title": "Asking Random Girls For Directions To See Who'd Actually Talk To Me",
        "ca_thumbnail": "A real street scene, creator mid-conversation with a woman, plain daylight urban backdrop, unproduced handheld framing matching the candid aesthetic.",
        "notes": "Naming a specific, real location is a cheap way to make an ordinary premise feel grounded and authentic rather than generic.",
        "status": "Not Adapted",
    },
    {
        "title": "Monkey Prank Ended by One Kind Girl...",
        "channel": "Logan Pierce",
        "url": "https://www.youtube.com/watch?v=CPMI-YuC7-w",
        "niche": "Street Prank/Social Reaction",
        "views": "211,865 (1,460 subscribers — 145.1x its subscriber count in views, a massive breakout for a tiny channel)",
        "views_num": 211865,
        "subscribers": 1460,
        "score": "145.1x subs",
        "pattern": "An escalating public prank interrupted by an unexpected act of kindness from a bystander, with the title naming the resolution (a kind girl) rather than the setup.",
        "trigger": "Curiosity about the twist (how does a random girl end the prank?) + the satisfying, wholesome reversal of an otherwise chaotic-sounding premise + a massive subscriber breakout proving a tiny channel can win with the right moment.",
        "thumbnail": "A real city crosswalk scene, a person in costume with a red circle highlighting them, a bystander visible nearby, \"GUYS\" caption capturing a real reaction, daylight urban setting.",
        "formula": "\"[Chaotic Premise] Ended By [Unexpected Kind Person]...\"",
        "why": "Naming the resolution's cause (a kind girl) instead of the chaotic setup flips the curiosity toward \"how did she factor into this,\" and the trailing \"...\" withholds exactly how.",
        "translation": "Reframe \"a chaotic prank interrupted by a kind stranger\" as \"an awkward public moment saved by a woman's warm reaction\" — same \"name the unexpected resolution, withhold how\" title structure.",
        "ca_title": "My Worst Approach Attempt Ever... Saved By One Girl's Reaction",
        "ca_thumbnail": "A real street scene, creator mid-awkward-moment, a woman visible nearby with a warm/amused expression clearly about to intervene, candid unposed daylight framing.",
        "notes": "A 145x subscriber breakout on a channel with under 1,500 subscribers is strong proof this specific title structure (name the resolution, not the setup) can work regardless of channel size.",
        "status": "Not Adapted",
    },
    {
        "title": "Crazy Glitter Bomb Prank on Stupid Porch Pirate! They get Instant Karma.",
        "channel": "PorchPirateInstantKarma",
        "url": "https://www.youtube.com/watch?v=IpZj5yvf4nI",
        "niche": "Security-Cam Justice/Revenge Prank",
        "views": "423,154 (66.8K subscribers — 6.3x its subscriber count in views, a genuine breakout)",
        "views_num": 423154,
        "subscribers": 66800,
        "score": "6.3x subs",
        "pattern": "Real doorbell-camera footage of a package thief getting caught in a glitter bomb trap, with on-screen labels (\"WRONG HOUSE,\" \"THIEF\") narrating the moment in real time as it unfolds.",
        "trigger": "Justice/karma satisfaction (a wrongdoer visibly and immediately regrets their choice) + real-time on-screen labels heightening the \"gotcha\" moment + authentic security-cam footage feeling unquestionably real.",
        "thumbnail": "A real doorbell-camera POV shot of a person recoiling from an exploding glitter trap, bold captions \"WRONG HOUSE\" and \"THIEF\" labeling the moment, muted daylight porch setting.",
        "formula": "\"Crazy [Device] Prank on Stupid [Wrongdoer]! They Get Instant Karma.\"",
        "why": "The real-time on-screen labels narrate the \"gotcha\" as it happens instead of requiring a summary title, and calling the target \"stupid\" upfront primes the viewer to enjoy their comeuppance without guilt.",
        "translation": "Reframe \"a porch pirate gets an instant-karma glitter surprise\" as \"a guy who disrespects a woman gets an instant social comeuppance\" — same real-time on-screen-label narration and unapologetic \"they had it coming\" framing.",
        "ca_title": "Crazy Comeback When A Guy Disrespected Her! He Got Instant Karma.",
        "ca_thumbnail": "A real street scene, a woman's confident reaction as a disrespectful guy visibly backpedals, bold real-time captions labeling the moment as it happens, natural daylight setting.",
        "notes": "This is the same core mechanic as the porch-pirate Shorts already in the General Shorts Outliers swipe file — a third real example of it succeeding further confirms the format is genuinely repeatable, not a fluke.",
        "status": "Not Adapted",
    },
    {
        "title": "Sneaking Onto Billionaires Estate to Visit Abandoned Mansion Once Owned by Bruce Forsyth!",
        "channel": "SIDE QUEST EXPLORING",
        "url": "https://www.youtube.com/watch?v=a8wqklwE8mU",
        "niche": "Forbidden Access/Urban Exploration",
        "views": "222,901 (20K subscribers — 11.1x its subscriber count in views, a genuine breakout)",
        "views_num": 222901,
        "subscribers": 20000,
        "score": "11.1x subs",
        "pattern": "The same forbidden-access exploration format as elsewhere in this niche, anchored to a real, named former owner for extra grounded specificity.",
        "trigger": "Forbidden curiosity (trespassing onto a real, named billionaire's estate) + the specificity of a real celebrity former owner making the premise feel grounded and researchable + decay/mystery visuals.",
        "thumbnail": "A real exterior shot of a grand, decaying mansion, an inset photo of the named former owner in formal wear, bold caption \"ABANDONED AND LEFT TO ROT,\" daylight setting.",
        "formula": "\"Sneaking Onto [Real Place] to Visit Abandoned [Location] Once Owned by [Named Real Person]!\"",
        "why": "Naming a specific real former owner (not a generic \"mystery mansion\") gives the premise instant grounded credibility, and \"sneaking onto\" adds a forbidden-access thrill on top of the exploration curiosity.",
        "translation": "Reframe \"sneaking into a named celebrity's abandoned estate\" as \"approaching someone at a real, named high-difficulty venue\" — same naming-real-specifics-for-credibility device.",
        "ca_title": "Approaching The Most Exclusive Table At The City's Hardest Club To Get Into",
        "ca_thumbnail": "A real venue exterior/interior shot, creator approaching a specific real group, bold caption naming the difficulty, similar grounded documentary framing.",
        "notes": "A second independent channel succeeding with the same \"named-specifics forbidden access\" format is stronger proof of repeatability than one example alone.",
        "status": "Not Adapted",
    },
    {
        "title": "Survival Challenge in Heavy Snow and Blizzard-21°C Temperature Alone in the Deep Wild, and Cold Jungle",
        "channel": "Wild solo camp",
        "url": "https://www.youtube.com/watch?v=VkO0ZKzW55I",
        "niche": "Extreme Survival Documentary",
        "views": "450,154 (40.8K subscribers — 11.0x its subscriber count in views, a genuine breakout)",
        "views_num": 450154,
        "subscribers": 40800,
        "score": "11.0x subs",
        "pattern": "Real, unnarrated wilderness survival footage in extreme conditions, letting the harsh visual environment alone communicate the stakes without needing a dramatic title.",
        "trigger": "Awe/respect for endurance under extreme conditions + the specificity of a real, extreme temperature (-21°C) making the stakes concrete + atmospheric, cinematic winter visuals.",
        "thumbnail": "A real snowy wilderness scene at night, a person carrying firewood toward a glowing shelter built into a large tree, heavy snowfall, moody atmospheric lighting.",
        "formula": "\"Survival Challenge in [Extreme Specific Condition], Alone in [Location Type]\"",
        "why": "A specific, extreme, concrete number (-21°C) makes the difficulty instantly legible, and the atmospheric visual alone (no text needed) sells the mood.",
        "translation": "Reframe \"surviving alone in extreme cold\" as \"approaching under the most difficult/intimidating real conditions\" — same specific-extreme-difficulty-number framing and atmospheric, minimal-text visual mood.",
        "ca_title": "Approaching Women At -21°C In A Blizzard (Extreme Difficulty Challenge)",
        "ca_thumbnail": "A real snowy street scene at night, creator approaching a woman in harsh winter conditions, moody atmospheric lighting, minimal on-screen text.",
        "notes": "A concrete, extreme specific number (a temperature, a distance, a count) is a cheap and reusable way to make a difficulty claim feel real rather than vague.",
        "status": "Not Adapted",
    },
    {
        "title": "He Handed Strangers Money and Drove Away",
        "channel": "True Tales",
        "url": "https://www.youtube.com/watch?v=K_As0VX-Gfw",
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
    {
        "title": "Japan's TERRIFYING Project to Win the World Cup!!",
        "channel": "Zeyad.",
        "url": "https://www.youtube.com/watch?v=qK6ED0SN-Zc",
        "niche": "Sports Strategy Documentary/Analysis",
        "views": "633,553 (2,790 subscribers — 227.1x its subscriber count in views, a massive breakout for a tiny channel)",
        "views_num": 633553,
        "subscribers": 2790,
        "score": "227.1x subs",
        "pattern": "A tactical/strategic breakdown framed with dramatic, ominous language (\"terrifying\") rather than neutral analysis language, paired with a composed, authoritative portrait thumbnail.",
        "trigger": "Curiosity about what could possibly make a strategy \"terrifying\" rather than just effective + the authority signal of a composed portrait with tactical diagrams + national pride/rivalry undertones.",
        "thumbnail": "A composed portrait of a football manager in formal attire, tactical formation diagrams and national team crest overlaid, bold red-accented \"TERRIFYING\" text, dramatic red/dark color grade.",
        "formula": "\"[Nation/Group]'s TERRIFYING [Plan/Project] to [Ambitious Goal]!!\"",
        "why": "\"Terrifying\" reframes a neutral strategic analysis as something with real stakes and menace, and the composed authority-figure portrait plus diagrams signals serious, credible analysis rather than clickbait speculation.",
        "translation": "Reframe \"a nation's terrifying strategic plan\" as \"a guy's terrifying-effective systematic approach method\" — same ominous-language-on-a-neutral-topic device, same authority-portrait-plus-diagram credibility signal.",
        "ca_title": "The Terrifying System That Gets Her Number Every Time",
        "ca_thumbnail": "A composed portrait of the creator in confident attire, simple diagram/notes overlaid suggesting a systematic method, bold red-accented \"TERRIFYING\" text, dramatic moody color grade.",
        "notes": "A massive 227x breakout on a channel with under 3,000 subscribers shows that dramatic reframing language on an otherwise ordinary analysis topic can travel far beyond a niche audience.",
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
            row["title"], row["channel"], row["url"], row["niche"], row["views"], row.get("subscribers") or "", row["score"],
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
