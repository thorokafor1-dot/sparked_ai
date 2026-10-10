"""EDL for take 2 (practice two-angle take, 2026-09-30): main Lumix + iPhone 3/4 angle, external mic.

Hand-built from work/take2_mic.txt. Times are written in MIC time (what the transcript shows) and
converted to main-camera time with m(), so they can be checked against the transcript directly.
Take 2 is paraphrased, not a re-read of take 1, and differs in structure:
  - the opener lines themselves were never spoken (silent gaps where they'd go), so each item is
    "Number X" + explanation, with the title card and the clip carrying the line
  - #4 (friend assisted) was never recorded, so it is missing from this take
  - #6 trails off ("instead of"), cut after "to a group"
  - the subscribe ask is the contextual one after #7 ("subscribe if you want tips on how to isolate the girl")
render: python render.py --edl edl_take2 --out output/ten_openers_take2_v1.mp4
"""

import json

import sync_mic
from pathlib import Path

from edl import CLIPS_DIR, QR_PNG, clip, th  # noqa: F401

HERE = Path(__file__).parent
TAKE_PREFIX = "take2_"
TALKING_HEAD = HERE / "input" / "rerecord" / "P1040024.MP4"
MIC = HERE / "input" / "rerecord" / "10 Conversations Starters Remake.m4a"
SYNC = HERE / "work" / "take2_main_sync.json"
ANGLE2 = HERE / "input" / "rerecord" / "angle2_iphone.mp4"
ANGLE2_SYNC = HERE / "work" / "take2_iphone_sync.json"
CAPTION_WORDS = HERE / "work" / "take2_caption_words.json"  # transcript in main-camera time (retarget_edl.py writes it)
# this mic was not noise-gated: its floor sits around -55 dB (take 1's gated to digital silence, -60 worked)
SILENCE_DB = -46
QUIET_VOICE_DB = -46

_sync = json.loads(SYNC.read_text())


def m(t: float) -> float:
    """Mic time -> main-camera time (sync_mic.py: camera = mic + offset, plus drift)."""
    return round(sync_mic.mic_to_cam(t, _sync), 3)


def tm(start, end, **kw):
    """th() with mic-time arguments."""
    return th(m(start), m(end), **kw)


SUBSCRIBE_AT = [m(617.9), m(1052.5)]  # "you're gonna want to subscribe" after #7, "subscribe to this channel" in the close

CARD = {
    10: (10, "Acknowledge busy", "You kind of look super busy, but for some\nreason I feel like I still have to say hi."),
    9: (9, "Situational guess", "Look at you, you just came\nfrom the gym or something?"),
    8: (8, "Outfit compliment", "I like the outfit,\nit kind of caught my attention."),
    7: (7, "Group energy", "You guys are vibing way too\nhard not to say hello."),
    6: (6, "Group style", "You guys have a very good style,\nthat's why I wanted to say hello."),
    5: (5, "Vibe read", "You look like you're having\nthe most chill walk of your life."),
    3: (3, "Specific compliment", "I like the jacket."),
    2: (2, "Playful bit", "You kinda walk like you're\nalways on a catwalk."),
    1: (1, "The go-to", "You kind of caught my attention,\nso I had to come say hi."),
}

# misspeaks to cut (main-camera time): "all the conversations artists, I'm gonna be giving you, I've actually
# used myself" (stumbled "conversation starters"), so the intro runs "...ten lines I've actually used in a real
# situation. I have footage of me using it, recorded on camera."
CUT_OUT = [(187.20, 191.36)]  # starts before the "And" that leads into the misspeak

EDL = [
    # HOOK: a real opener from the list (#7), she turns around smiling
    clip("UmJOTFiqEa0", 0.0, 4.45, label="hook", repeats="#7"),
{"src": "sting"},  # "Sparked Thor" brand sting, same intro transition as the video-chat long-forms

    # INTRO
    tm(100.54, 106.40, label="intro"),  # "The number one thing holding guys back ... is not knowing what to say"
    tm(137.22, 144.92),  # "So here's exactly what to say. I'm gonna give you ten lines ... cold approaching women"
    tm(200.92, 211.20),  # "...I've actually used myself. I have footage ... real examples. It's not just theory"
    tm(215.80, 218.98),  # "And I'm gonna be ranking them from solid to some of my go-to's"
    tm(258.02, 260.10),  # "All right, let's start at number ten"

    # 10 acknowledge busy
    tm(274.12, 280.08, num=10, card=CARD[10], label="#10"),  # "You might be hesitating ... let's play with that"
    clip("fPDiHlzGt_M", 11.25, 16.4, num=10),
    tm(327.76, 340.10, num=10),  # "So this actually does a couple things ... taking the power away from that excuse"

    # 9 situational guess
    tm(382.30, 393.22, num=9, card=CARD[9], label="#9"),  # "For number nine I've got a situational guess ... just came from the gym"
    clip("fPDiHlzGt_M", 23.1, 26.65, num=9),
    tm(397.62, 403.54, num=9),  # "You can use that as an opener, making that assumption..."
    tm(415.86, 422.10, num=9),  # "If your assumption is not right, she'll just correct you..."

    # 8 outfit compliment
    tm(431.56, 432.52, num=8, card=CARD[8], label="#8"),  # "Number eight"
    tm(448.70, 453.42, num=8),  # "This is a classic, complimenting her outfit as opposed to her looks"
    tm(457.30, 475.74, num=8),  # "I personally prefer complimenting her outfit ... put some thought into"
    clip("fPDiHlzGt_M", 0.0, 3.14, num=8),

    # 7 group energy
    tm(505.38, 517.52, num=7, card=CARD[7], label="#7", exact_end=True),  # "Number seven. Oftentimes ... all alone"
    tm(532.60, 546.50, num=7),  # "We have very little information ... what's their vibe like, that can literally be your opener"
    clip("UmJOTFiqEa0", 0.0, 7.6, num=7),
    tm(561.62, 577.76, num=7),  # "So it's actually doing a couple things, showing social intelligence ... the one girl you like the most"
    tm(583.08, 590.64, num=7, exact_end=True),  # "Because then the other people ... not gonna want to stay in that conversation"
    tm(602.70, 611.86, num=7, exact_start=True),  # "so you want to engage all of them ... focus on that girl that you like"

    # MID-ROLL SUBSCRIBE: contextual, sets up a future video, right after the group item it refers to
    tm(617.54, 624.94, label="midroll subscribe"),  # "And you're gonna want to subscribe if you want tips on how to isolate the girl..."

    # 6 group style
    tm(642.36, 657.14, num=6, card=CARD[6], label="#6", exact_end=True),  # "Number six ... say the same conversation starter to a group"
    clip("2sEWBsOFFZA", 282.95, 288.4, num=6),

    # 5 vibe read
    tm(685.62, 706.32, num=5, card=CARD[5], label="#5", exact_end=True),  # "Number five ... we don't have much to go off of"
    clip("UmJOTFiqEa0", 178.2, 184.0, num=5),
    tm(712.84, 722.70, num=5),  # "I on purpose say 'the most chill walk of their life' just to make it more dramatic..."

    # 4 friend assisted: not recorded in this take (see docstring)

    # 3 specific compliment
    tm(753.78, 764.12, num=3, card=CARD[3], label="#3", exact_end=True),  # "specific" runs straight into "It's"  # "Number three. If you can get more specific ... but it's more specific"
    clip("fPDiHlzGt_M", 56.7, 62.4, num=3),
    tm(764.12, 776.44, num=3, exact_start=True),  # "It's about the jacket in particular ... the more personalized it'll feel"

    # 2 playful bit
    tm(794.60, 807.98, num=2, card=CARD[2], label="#2"),  # "Number two, going back to the way she's walking ... make it into a joke"
    tm(816.34, 821.52, num=2),  # "it's essentially a joke that I'm making to get her laughing"
    clip("fPDiHlzGt_M", 7.6, 10.2, num=2),
    tm(842.02, 846.24, num=2, exact_end=True),  # "It still kind of sets the tone ... a light-hearted fun conversation"
    tm(873.36, 880.10, num=2),  # "And when you get someone laughing, their guard goes down..."

    # 1 go-to line
    tm(893.26, 895.56, num=1, card=CARD[1], label="#1"),  # "All right, number one"
    tm(896.94, 912.98, num=1),  # "This is one of my go-to lines ... my biggest clutches whenever I don't know what to say"
    clip("hHRg3bU-Jf8", 121.45, 124.45, num=1),
    clip("hHRg3bU-Jf8", 131.8, 133.4, num=1),  # jump to her asking his name
    clip("2sEWBsOFFZA", 443.5, 450.1, num=1, top_label="Same line. Different day.",
         delogo=(462, 36, 152, 86)),  # the upload's burned-in "8/10" rating badge (user: remove it)
    tm(950.66, 957.60, num=1),  # "It's the truth. That's exactly why I'm talking to this person..."
    tm(969.30, 976.50, num=1),  # "And it's also setting the agenda. You're letting them know you wanted to come meet them"
    tm(990.82, 997.48, num=1, exact_start=True),  # "but with this line it's simple ... used in any location"

    # CLOSE / CTA
    tm(1025.82, 1035.28, label="close"),  # "All right, that's all ten. Now you've got exactly what to say..."
    tm(1041.26, 1057.02),  # "these are gonna get you into a conversation ... subscribe ... breakdown videos like this"
    tm(1057.02, 1073.20, cta=True),  # "But if you want a more personalized plan ... one-on-one to work out a strategy"
    tm(1251.73, 1259.61, cta=True),  # "I'm running a free spark strategy call ... scan the QR code on the screen"
    tm(1272.05, 1276.35, exact_end=True),  # "And as always, thank you guys for watching ... see you in the next one"

    {"src": "endscreen"},
]
