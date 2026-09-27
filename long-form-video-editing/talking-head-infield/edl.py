"""Edit decision list for "10 Conversation Starters (That Actually Work)".

Talking-head times are best takes from work/talking_head.txt (P1040005.MP4).
Infield times are from work/infield_<id>.txt. Note the script's UmJOTFiqEa0
timestamps were 2:00 early (#5 is really 2:58, #4 is really 4:12) and the #1
line in hHRg3bU-Jf8 lands at 2:01.7, not 1:58.
"""

# Clips end right after her first positive response; brush-offs (all in the fPDi rejection
# compilation) are cut out so the video never shows an opener failing.

from pathlib import Path

HERE = Path(__file__).parent
TALKING_HEAD = HERE / "input" / "talking_head" / "P1040005.MP4"
MIC = HERE / "input" / "talking_head" / "mic.m4a"  # external mic, replaces camera audio (see sync_mic.py)
CLIPS_DIR = HERE / "input" / "infield"
QR_PNG = HERE.parent.parent / "video-ideation" / "spark_strategy_call_qr.png"

END_PAD = 0.15  # talking-head word ends from whisper run slightly early


def th(start, end, **kw):
    # exact_start/exact_end: a hand-picked word boundary where the speaker runs on with no pause
    s = start if kw.get("exact_start") else start - 0.08
    e = end if kw.get("exact_end") else end + END_PAD
    return {"src": "th", "start": s, "end": e, **kw}


def clip(src, start, end, caption=None, **kw):
    return {"src": src, "start": start, "end": end, "caption": caption, **kw}


# cam-time of each spoken "subscribe" that survives the cut; render.py drops the animation there
SUBSCRIBE_AT = [110.72, 900.96]


EDL = [
    # HOOK: a real opener from the list (#7), close-up at sunset, she turns around smiling
    clip("UmJOTFiqEa0", 0.0, 4.45, label="hook", repeats="#7"),  # ends on her "Oh, hi!"

    # INTRO
    th(24.5, 29.96, label="intro"),  # skips the stumbled first "the number one thing"
    th(39.6, 41.8),
    th(81.4, 85.56),
    th(89.0, 91.92),
    th(130.3, 131.44),

    # 10 acknowledge busy
    th(142.5, 149.56, num=10, card=(10, "Acknowledge busy", "You kind of look super busy, but for some\nreason I feel like I still have to say hi."), label="#10"),
    clip("fPDiHlzGt_M", 11.25, 16.4, num=10),
    th(158.6, 164.86, num=10),

    # 9 situational guess
    th(181.3, 182.08, num=9, card=(9, "Situational guess", "Look at you, you just came\nfrom the gym or something?"), label="#9"),
    th(211.6, 225.9, num=9),
    clip("fPDiHlzGt_M", 23.1, 26.65, num=9),
    th(237.4, 242.98, num=9),

    # 8 outfit compliment
    th(309.0, 311.26, num=8, card=(8, "Outfit compliment", "I like the outfit,\nit kind of caught my attention."), label="#8"),  # "Number eight. This one's super simple."
    th(322.0, 329.26, num=8),
    clip("fPDiHlzGt_M", 0.0, 3.14, num=8),

    # 7 group energy
    th(356.4, 381.62, num=7, card=(7, "Group energy", "You guys are vibing way too\nhard not to say hello."), label="#7"),
    clip("UmJOTFiqEa0", 0.0, 7.6, num=7),
    th(403.3, 417.42, num=7, exact_end=True),

    # 6 group style
    th(467.4, 482.62, num=6, card=(6, "Group style", "You guys have a very good style,\nthat's why I wanted to say hello."), label="#6"),
    clip("2sEWBsOFFZA", 282.95, 288.4, num=6),

    # MID-ROLL SUBSCRIBE: moved here from the intro so the ask comes after value is delivered
    th(109.95, 115.94, label="midroll subscribe", exact_start=True),

    # 5 vibe read
    th(499.0, 509.62, num=5, card=(5, "Vibe read", "You look like you're having\nthe most chill walk of your life."), label="#5"),
    th(513.6, 523.74, num=5),
    th(530.7, 533.6, num=5, exact_end=True),
    clip("UmJOTFiqEa0", 178.2, 184.0, num=5),
    th(544.6, 548.26, num=5),

    # 4 friend assisted
    th(555.6, 567.94, num=4, card=(4, "Friend assisted", "My friend has something\nhe wants to say to you."), label="#4"),
    clip("UmJOTFiqEa0", 251.8, 257.2, num=4),
    th(584.2, 598.95, num=4, exact_end=True),

    # 3 specific compliment
    th(639.6, 650.0, num=3, card=(3, "Specific compliment", "I like the jacket."), label="#3"),
    clip("fPDiHlzGt_M", 56.7, 62.4, num=3),
    th(659.2, 675.22, num=3),

    # 2 playful bit
    th(692.4, 695.92, num=2, card=(2, "Playful bit", "You kinda walk like you're\nalways on a catwalk."), label="#2"),
    th(698.95, 706.06, num=2),
    th(706.8, 707.9, num=2),
    clip("fPDiHlzGt_M", 7.6, 10.2, num=2),
    th(717.1, 732.66, num=2),

    # 1 go-to line
    th(740.9, 753.76, num=1, card=(1, "The go-to", "You kind of caught my attention,\nso I had to come say hi."), label="#1"),
    clip("hHRg3bU-Jf8", 121.45, 124.45, num=1),
    clip("hHRg3bU-Jf8", 131.8, 133.4, num=1),  # jump to her asking his name
    clip("2sEWBsOFFZA", 443.5, 450.1, num=1, top_label="Same line. Different day."),
    th(764.3, 773.72, num=1),

    # CLOSE / CTA
    th(810.5, 818.48, label="close"),
    th(826.7, 829.44),
    th(830.1, 843.45, cta=True, exact_end=True),
    th(855.7, 858.54, cta=True),
    th(885.9, 887.62, cta=True),
    th(895.35, 904.02, exact_end=True),

    # ENDSCREEN: the channel's standard "Learn to spark attraction / Subscribe" card
    {"src": "endscreen"},
]
