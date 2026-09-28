# Executed by ideas_source.py (shares its namespace: IDEAS, prompt).
DROP = {"dg-60-min", "dg-remember-me", "bg-worst", "vc-speed", "ex-body-lang", "ex-3-signs"}
PARKED = [
    {"title": "I Ran Into A Girl I Approached A Year Ago. Her Reaction", "why": "Needs a real, consented reunion, and the evidence is a cross-niche reunion format. Revisit only if it happens naturally."},
    {"title": "My 5 Worst Bar Approaches Of The Year (And What I'd Change)", "why": "Evidence is faceless Reddit-style reading, and it can read as mocking rejections. Revisit with a respectful framing."},
    {"title": "Speed E-Dating 10 Strangers", "why": "Same video as the 10 e-dates idea, repackaged."},
    {"title": "12 Subtle Body Language Signs / 3 Signs She Wants You To Talk To Her", "why": "Same topic as the 7 signs idea. Test one signs video first."},
    {"title": "60 Real Minutes Of Approaching Women (Uncut)", "why": "Folded into the 100 women idea as a scaled-down version."},
]
OVERRIDES = {
    "dg-100-women": dict(
        strength="adapted",
        why="A hard number plus 'uncut' gives viewers a scoreboard to follow. Niche precedent exists for both halves (a 100-approach challenge and a 12-hour marathon), but each has one channel behind it, so treat it as adapted.",
        footage="A full day of approaches with a running tally on screen. If 100 is unrealistic, use 50 and change the number. A scaled-down version is 60 uncut minutes.",
    ),
    "dg-intimidating": dict(strength="adapted"),
    "dg-places-tier": dict(
        potential="Medium", strength="adapted",
        evidence=[("Signs She Likes You (TIER LIST)", "The only tier-list title in the tracked niche data, at a low score, so treat the format as unproven here."),
                  ("How to talk to Any woman", "Broad how-to-approach demand exists, which is the topic this tier list ranks.")],
        why="Tier-list titles are live in dating on YouTube right now (Coach Knox's channel), but the tracker holds just one tier-list video in this niche and it scored low, so this rests on live search rather than tracked proof. Already scripted.",
    ),
    "bg-10-lines": dict(
        title="I Tested 10 Openers At The Bar (Ranked By Her Reaction)",
        hook="Ten openers, ten different women. I'm ranking them by what actually happened, not by what I hoped.",
        footage="Ten approaches with a distinct opener each, clean audio of your opener, her reaction visible.",
    ),
    "bg-pov": dict(
        strength="adapted",
        prompt=prompt("turning toward the camera with a warm smile", "crowded bar, warm ambient lighting"),
        why="POV framing puts the viewer in your seat, and 'uncut' is the trust signal. Only one bar POV outlier backs it (a 750-subscriber channel), so treat it as adapted.",
    ),
    "vc-10-edates": dict(
        title="I Went On 10 Video Chat E-Dates In One Night (Ranked By Conversation)",
        hook="Ten e-dates in one night. I'm ranking them by how the conversation actually went.",
        footage="A new shoot: ten e-dates, each with a clear moment and permission to show it. Blur usernames and personal info.",
    ),
    "vc-3am": dict(
        title="3 AM E-Dates: The Conversations That Actually Went Somewhere",
        hook="It's 3 AM and I'm going on e-dates until I find the conversations worth showing you.",
        thumbnail="A woman on a late-night video call, lit warmly by a lamp and the screen, curious smile, medium framing.",
        prompt=prompt("warmly lit by a lamp and a laptop screen, curious and playful smile", "lamp-lit living room in the evening, seen over the man's shoulder toward the laptop"),
    ),
    "vc-tier": dict(
        footage="Uses your existing library, no new shoot: the best clip from each of many past e-dates, with consent, PII blurred.",
        why="You already own the biggest footage library in this category, and a tier list turns a pile of clips into a debate viewers comment on. Unlike the 10 e-dates idea, this needs no new shoot.",
    ),
    "ex-not-interested": dict(
        title="Interested Or Just Polite? How To Tell (And When To Let It Go)",
        pattern="The 'is she interested' doubt moment, taken the respectful way",
        hook="Some women are warming up. Some are just being kind. Here's how I tell the difference.",
        why="The moment a viewer wonders whether she is interested is the most searched-for doubt in the explainer data (400x on one video). This version teaches reading the signal and respecting a no, which also fits the brand.",
        footage="Two kinds of clips: a conversation that warms up, and a polite one where you let it go. End each at her first clear response and describe it directionally.",
        risk="Never frame it as persistence past a no. The lesson is reading the signal and leaving well.",
        thumbnail="A woman with a polite, neutral-to-friendly expression mid-conversation, medium-wide, creator at a respectful distance.",
        prompt=prompt("polite and friendly, expression neither clearly warm nor cold", "quiet street with soft daylight"),
    ),
    "ex-10-seconds": dict(strength="adapted"),
    "ex-7-signs": dict(
        why="'Signs she likes you' is the strongest demand cluster in the data. The 594x figure comes from a 2,240-subscriber channel and most winners are faceless voiceover, so on-camera proof from your own footage is the difference.",
    ),
}
NEW = [
    dict(
        id="dg-ask-women", category="daygame", potential="Medium",
        title="I Asked 10 Women How They Want To Be Approached (Then Tried It)",
        pattern="Ask strangers for advice, then apply it",
        strength="adapted",
        evidence=[("100 Married Couples for Dating Advice", "Sprouht: ask-real-people-for-advice format at 32x channel average."),
                  ("Asking Strangers How to Approach a Girl", "Benjamin Seda: the same 'ask strangers' premise applied to approaching."),
                  ("Asking Miami Gym Girls", "RemellGains: a public-question format on approaching.")],
        why="Real women answering on camera puts a woman front and center by design, and applying their advice gives the video a second half instead of ending at the interviews.",
        hook="I'm going to ask ten women how they actually want to be approached, then do exactly what they say.",
        thumbnail="A woman answering a question on the street with a thoughtful, amused expression, medium-wide, creator holding the conversation at the edge of frame.",
        prompt=prompt("thoughtful and amused, mid-answer to a question", "sunny public plaza, casual passersby softly blurred"),
        footage="Ten short consented street interviews, then the approaches where you apply the advice. Use only what each woman actually said, never write words for her.",
        risk="Needs consent from every woman on camera. Evidence is adapted from general dating-advice formats.",
    ),
    dict(
        id="vc-guess", category="video-chat-edates", potential="Medium",
        title="Guessing Strangers' Names On Video Chat: How Many Can I Get Right?",
        pattern="Game challenge with a visible score",
        strength="adapted",
        evidence=[("Guessing People's Names 1-20", "Peter Prankster: 132x channel average, 3.96M views, a game with a counting score.")],
        why="A simple game with a visible score is easy to follow and easy to clip. It shows charm without depending on an outcome.",
        hook="Twenty strangers. I get one guess each at their name. Let's see my score.",
        thumbnail="A woman on a video call laughing as she reveals whether the guess was right, medium framing, soft lamp lighting.",
        prompt=prompt("laughing warmly on a video call, seen on a laptop screen", "lamp-lit room in the evening"),
        footage="Twenty short video chat clips with a running score, permission to show each person, PII blurred.",
        risk="One outlier from a large channel and a different audience, so this is adapted. Keep it warm, never mocking.",
    ),
    dict(
        id="ex-how-women-flirt", category="explainer", potential="Medium",
        title="How Women Actually Flirt (The Science Plus Real Footage)",
        pattern="'How women flirt' explainer with proof",
        strength="proven",
        evidence=[("Ways To Flirt Subtly", "Psych2Go: 33x channel average on a 13M channel."),
                  ("The Science Behind How Women Flirt", "Zoomology: 25x, 734K views."),
                  ("4 Ways Women Are Flirting With You", "Kimberly Hill: 19x, 561K views.")],
        why="Three separate channels hit the same topic, and all are talking heads or animation. Real clips of the signals in your own footage is the gap.",
        hook="Women flirt in ways most guys walk right past. I'll show you real examples of each.",
        thumbnail="A woman mid-flirt, a playful look and slight head tilt, medium-wide, creator engaged.",
        prompt=prompt("playful look with a slight head tilt and a small smile", "cafe patio in soft daylight"),
        footage="Four or five short clips, each isolating one way she flirted, described directionally.",
        risk="Broad topic with strong competition. Keep claims modest.",
    ),
]

IDEAS = [i for i in IDEAS if i["id"] not in DROP]
for _i in IDEAS:
    if _i["id"] in OVERRIDES:
        _i.update(OVERRIDES[_i["id"]])
IDEAS += NEW
