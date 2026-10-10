"""Build edit.json: the cut list, fx cues and music for the infield night long-form (2026-04-17).

Times are source timestamps in raw/raw.mkv. SFX are named by category and rotated so the
same sound never plays twice in a row. Run: python build_edit.py && python render.py
"""
import bisect
import itertools
import json
import random
from pathlib import Path

ROOT = Path(__file__).parent
random.seed(7)

# ---------------------------------------------------------------- sfx rotation
_pools = {}
for f in sorted((ROOT / "sfx").glob("*.mp3")):
    _pools.setdefault(f.stem.split("_")[0], []).append(f.stem)
_cycles, _last = {}, {}


# Sparked brand = cool, smooth, mature: cartoon/crowd/arcade categories were retired (user feedback).
CAT_REMAP = {"rizz": None, "tension": None, "impact": None, "heart": None, "crowd": None, "joke": None, "fail": "impact", "stun": "impact", "whistle": "rizz",
             "kiss": "rizz", "pop": "whoosh", "ding": "rizz"}


def S(cat):
    """Next sound in a category, shuffled, never the same file twice running."""
    cat = CAT_REMAP.get(cat, cat)
    if cat is None:
        return None
    if cat not in _cycles:
        pool = _pools[cat][:]
        random.shuffle(pool)
        _cycles[cat] = itertools.cycle(pool)
    name = next(_cycles[cat])
    if name == _last.get(cat) and len(_pools[cat]) > 1:
        name = next(_cycles[cat])
    _last[cat] = name
    return name


pieces = []
sections = []                    # (name, first piece index) for music layout


WORDS = sorted((w for f in ("work/transcript.json", "work/transcript_small.json") if (ROOT / f).exists()
                for sg in json.load(open(ROOT / f, encoding="utf-8")) for w in sg["words"]), key=lambda w: w["s"])


import wave as _wave
import numpy as _np

_AUDIO = _wave.open(str(ROOT / "work/audio16k.wav"))
_SR16 = _AUDIO.getframerate()
SPEECH_DB = -44.0      # current "someone is talking" level; set per venue by speech_db() (bar noise varies a lot)
_SEGS = json.load(open(ROOT / "raw/segments.json"))


def speech_db(t):
    """Each venue's noise floor (20th pct of 25 ms RMS) + 6 dB: the floor ran from -40 (F) to -26 dB (E), so the
    Monkey room threshold (-44) counted the whole bar as speech."""
    seg = next((g for g in _SEGS if g["start"] <= t < g["end"]), _SEGS[-1])
    if "floor" not in seg:
        _AUDIO.setpos(int(seg["start"] * _SR16))
        x = _np.frombuffer(_AUDIO.readframes(int((seg["end"] - seg["start"]) * _SR16)), dtype=_np.int16).astype(float) / 32768
        hop = _SR16 // 40
        fr = x[:len(x) // hop * hop].reshape(-1, hop)
        seg["floor"] = float(_np.percentile(20 * _np.log10(_np.sqrt((fr ** 2).mean(1)) + 1e-9), 20))
    return seg["floor"] + 6.0
TAIL_MAX = 0.8         # how far a clip end may be pushed to let a sentence finish


def _rms_db(t, dur=0.05):
    if int(t * _SR16) >= _AUDIO.getnframes():   # past the end of the source (scans after the last segment)
        return -120.0
    _AUDIO.setpos(max(int(t * _SR16), 0))
    x = _np.frombuffer(_AUDIO.readframes(int(dur * _SR16)), dtype=_np.int16).astype(float) / 32768
    return 20 * _np.log10(_np.sqrt((x ** 2).mean()) + 1e-9) if len(x) else -120.0


def snap(a, b):
    """Nudge cut points so no word or sentence is chopped.

    Word timings alone weren't enough ("I'm Filipi-" got cut: the model ended the word 0.3 s early), so the end is
    also checked against the real audio: while speech is still sounding at the cut, extend (up to TAIL_MAX).
    """
    global SPEECH_DB
    SPEECH_DB = speech_db(a)
    for i, w in enumerate(WORDS):
        if w["s"] < a < w["e"] - 0.08 and a - w["s"] < 0.6:
            prev_e = WORDS[i - 1]["e"] if i else 0
            a = max(w["s"] - 0.04, prev_e + 0.01)
        if w["s"] < b - 0.08 and w["e"] > b and w["e"] - b < 0.6:
            nxt = WORDS[i + 1]["s"] if i + 1 < len(WORDS) else w["e"] + 1
            b = min(w["e"] + 0.08, max(nxt - 0.02, w["e"]))
    # Land both cuts in a real gap between words: the first silent 25 ms frame, or (if people keep talking) the
    # deepest pause in the search window. Never stretch blindly into the next sentence.
    def frames(t0, t1):
        n = max(int((t1 - t0) / 0.025), 1)
        return [(t0 + k * 0.025, _rms_db(t0 + k * 0.025, 0.025)) for k in range(n)]

    def across(t):   # speech sounding on both sides of t = a word would be chopped here
        return min(_rms_db(t - 0.025, 0.025), _rms_db(t, 0.025))

    def settle(t, back, fwd, prefer_fwd):
        if across(t) <= SPEECH_DB:
            return t
        cands = frames(t - back, t + fwd)
        quiet = [c for c in cands if c[1] <= SPEECH_DB]
        if quiet:   # nearest silent frame, searching in the preferred direction first
            order = sorted(quiet, key=lambda c: (0 if (c[0] >= t) == prefer_fwd else 1, abs(c[0] - t)))
            return order[0][0] + 0.0125
        return min(cands, key=lambda c: c[1])[0] + 0.0125   # deepest pause between words

    # starts only search backward and ends only forward: neither may eat into the line itself
    a = settle(a, 0.5, 0.0, prefer_fwd=False)
    b = settle(b, 0.0, TAIL_MAX, prefer_fwd=True)
    # Natural breathing room: a cut exactly where the audio goes silent still sounds clipped (user, v7). Hold up
    # to 0.15 s of quiet after the last word and 0.08 s before the first, stopping if anyone starts talking.
    for _ in range(6):
        if _rms_db(b, 0.025) > SPEECH_DB:
            break
        b += 0.025
    for _ in range(3):
        if _rms_db(a - 0.025, 0.025) > SPEECH_DB:
            break
        a -= 0.025
    return round(a, 3), round(b, 3)


SNAP_LOG = []


def clip(a, b, *fx, z=None, zooms=None, snap_cuts=True, **kw):
    a0, b0 = a, b
    if snap_cuts:
        a, b = snap(a, b)
    else:   # deliberate cliffhanger cut, both points picked by hand in real silence (QA mid-speech gate skips it)
        kw["cut_ok"] = True
    # never replay audio: a snapped start may not reach back into the previous clip (v35 said "Hey" twice at 3:34)
    if pieces and pieces[-1]["type"] == "clip" and not kw.get("teaser") and not pieces[-1].get("teaser")             and 0 < pieces[-1]["out"] - a < 3:
        a = pieces[-1]["out"]
    # never cut inside a word (either transcript): bar noise hides chops from snap()'s level test ("Hold o|n", v4).
    # A start inside a word moves back to include it; an end inside a word moves on past it. A start that continues
    # straight on from the previous clip is seamless and stays.
    contiguous = pieces and pieces[-1]["type"] == "clip" and abs(pieces[-1]["out"] - a) < 0.05
    for _ in range(4 if snap_cuts else 0):   # hand-picked cuts (snap_cuts=False) are reviewed and stay put
        hit = False
        for w in WORDS:
            if w["e"] - w["s"] > 1.2:
                continue
            if not contiguous and w["s"] < a - 0.06 and w["e"] > a + 0.06:
                a, hit = round(w["s"] - 0.04, 3), True
            if w["s"] < b - 0.06 and w["e"] > b + 0.06:
                b, hit = round(w["e"] + 0.05, 3), True
        if not hit:
            break
    if abs(a - a0) > 0.03 or abs(b - b0) > 0.03:
        SNAP_LOG.append((a0, b0, a, b))
    if zooms:
        zooms = [(a if za == a0 else za, b if zb == b0 else zb, zz) for za, zb, zz in zooms]
    p = {"type": "clip", "in": a, "out": b, "fx": list(fx), **kw}
    if z:
        p["zoom"] = list(z)
    if zooms:
        p["zooms"] = [[za, zb, *zz] for za, zb, zz in zooms]
    pieces.append(p)
    return p


def freeze(at, dur, *fx, z=None, dim=True, **kw):
    p = {"type": "freeze", "at": at, "dur": dur, "dim": dim, "fx": list(fx), **kw}
    if z:
        p["zoom"] = list(z)
    pieces.append(p)


MEME_TO_CLIP = {"cheers": ["toast", "clink", "toast_her"], "cinema": ["sparks", "sparklers"],
                "pikachu": ["surprised"], "monkeypuppet": ["facepalm"], "harold": ["facepalm", "headhands"],
                "rollsafe": ["smug"], "skeptical": ["caught"]}
_clip_cycles = {k: itertools.cycle(v) for k, v in MEME_TO_CLIP.items()}
# Redundant pops (restating what the viewer just heard) and e-date numbering removed (user, 2026-09-28).
TEXT_DROP = {"SHE CALLED ME BABY 😳", "SHE SAID KIDS?! 😳", "SHE GOT ME", "SHE'S COOKING", "E-DATE #1", "E-DATE #2", "E-DATE #3",
             "E-DATE #4", "E-DATE #5", "FIRST CALL 👀"}
TEXT_MAP = {"SHE'S COOKING": "SHE CAME PREPARED", "HOLD ON 🤨": None, "LOVE LANGUAGES 💀": "THE FIVE LOVE LANGUAGES",
            "PHYSICAL TOUCH?!": "PHYSICAL TOUCH.", "NICE. NICE. GREAT. 😏": None, "SAME LINE AGAIN 💀": "SAME LINE. NEW GIRL.",
            "SHE SAID KIDS?! 😳": "SHE BROUGHT UP KIDS", "SHE CALLED ME BABY 😳": "SHE CALLED ME BABY",
            "WE'RE COMING BACK TO ANNA 👀": "WE'LL COME BACK TO ANNA", "THOR-NS?! ⚡": "THOR-NS", "98% 📈": None,
            "W": None, "BACK TO ANNA 👀": "BACK TO ANNA", "WAIT... 🤨": "WAIT A SECOND...",
            "SAME LINE ON ALEJANDRA 💀": "SAME LINE. DIFFERENT GIRL.", "EMOTIONAL DAMAGE 💀": None,
            "SUBSCRIBE FOR PART 2 ⚡": "SUBSCRIBE FOR MORE", "FIRST CALL 👀": "E-DATE #1"}


def fx(at, sfx=None, vol=0.75, **kw):
    if "emoji" in kw:                      # emoji pops retired for a more mature look
        for k in ("emoji", "pos", "w", "rot"):
            kw.pop(k, None)
    if "meme" in kw or "clip" in kw:       # reactions are full-screen cutaways now (CUTAWAYS), not overlays
        kw.pop("meme", None); kw.pop("clip", None)
        if "text" not in kw:
            kw.pop("dur", None)
    if "text" in kw:
        t = None if kw["text"] in TEXT_DROP else TEXT_MAP.get(kw["text"], kw["text"])
        if t is None:
            for k in ("text", "style", "color") + (() if "clip" in kw else ("dur",)):
                kw.pop(k, None)
        else:
            kw["text"] = t
    f = {"at": at, **kw}
    if sfx:
        names = [S(c) if "_" not in c else c for c in (sfx if isinstance(sfx, list) else [sfx])]
        names = [n for n in names if n]
        if names:
            f["sfx"] = names[:1]            # one sound per moment, never stacked
            f["vol"] = vol
    return f


def rel(t, sfx=None, vol=0.75, **kw):      # fx on a freeze (relative time)
    f = fx(0, sfx, vol, **kw)
    del f["at"]
    f["t"] = t
    return f


def section(name):
    sections.append((name, len(pieces)))


# ---------------------------------------------------------------- caption patches
# Words medium.en dropped in the kept ranges, verified 2026-10-04 with a normalized medium.en pass (vad off).
WORD_PATCHES = [("You're", 1238.92, 1239.26), ("very", 1239.28, 1239.48), ("seductive.", 1239.50, 1240.0),
                ("Maricela.", 711.56, 712.2)]
_tp = ROOT / "work/transcript.json"
_tr = json.load(open(_tp, encoding="utf-8"))
_have = {(w["w"].strip(), round(w["s"], 2)) for sg in _tr for w in sg["words"]}
_new = [{"w": " " + t, "s": a, "e": b, "p": 1.0} for t, a, b in WORD_PATCHES if (t, round(a, 2)) not in _have]
if _new:
    _tr.append({"start": _new[0]["s"], "end": _new[-1]["e"], "text": " ".join(w["w"].strip() for w in _new), "words": _new, "hq": True})
    _tr.sort(key=lambda sg: sg["words"][0]["s"])
    json.dump(_tr, open(_tp, "w", encoding="utf-8"), indent=1)
    print("patched", len(_new), "words into the transcript")

# ---------------------------------------------------------------- night-specific framing
# Source = raw/raw.mkv (build_source.py), vertical 1080x1920. Zoom = (z, cx, cy) on the vertical frame.
# A and B were filmed from a phone lying on a nearby table: the group is small at the top, so those
# approaches get a base framing on the group (static), and pushes ease in from it.
A_BASE = (1.6, 0.33, 0.33)
A_PUSH = (2.0, 0.35, 0.30)
# B: no zoom (user, 2026-10-05: at 2.2x "you couldn't even see me"; he sits at the far table, top right)
B_BASE = None
B_PUSH = None
HER_C = (1.3, 0.62, 0.62)       # the teachers' table, close shot
LUMA_DARK = 40.0                # mean luma below this reads as a black screen: lift the clip (render.LIFT)

import subprocess as _sp
import re as _re
_LUMA_CACHE = ROOT / "work" / "luma.json"
_luma = json.loads(_LUMA_CACHE.read_text()) if _LUMA_CACHE.exists() else {}


def luma(a, b):
    k = f"{a:.2f}-{b:.2f}"
    if k not in _luma:
        vals = []
        for f in (0.2, 0.5, 0.8):
            r = _sp.run(["ffmpeg", "-v", "info", "-ss", f"{a + (b - a) * f:.2f}", "-i", str(ROOT / "raw/raw.mkv"),
                         "-frames:v", "1", "-vf", "signalstats,metadata=print:key=lavfi.signalstats.YAVG", "-f", "null", "-"],
                        capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
            vals += [float(x) for x in _re.findall(r"YAVG=([\d.]+)", r)]
        _luma[k] = sum(vals) / max(len(vals), 1)
    return _luma[k]


# ================================================================= HIGHLIGHT TEASER (cold open)
# Raw infield videos have NO intro teaser (user, 2026-10-05): the video opens straight on the first opener.
# Kept switchable for reference; with TEASER = False there's also no brand sting and no teaser bars.
TEASER = False
T = {"teaser": True}
if TEASER:
    section("cold")
    clip(1055.3, 1058.7, z=HER_C, **T)                     # C: "I don't think it relates to me at all, but it means little fiery things"
    clip(668.4, 672.6, z=B_PUSH, **T)                  # B: "If your name is Alejandra, I'm going to lose it. I won't be able to behave"
    clip(2296.6, 2301.6, fout=0.3, **T)                # F: "Jillian, the name means child of the God of Thunder" (cut before "No, it doesn't")

# ================================================================= C: the teachers (opens the video)
section("teachers")
clip(930.8, 944.0, fin=0.25)                           # "Excuse me guys. You guys look like the group to get to know tonight"
clip(946.0, 955.0)                                     # "those are the best nights" "what are we celebrating though"
clip(995.7, 1000.55)                                   # names: "what is your name?" "I'm Andrea" (phone dips to the floor after it)
clip(1007.5, 1012.5)                                   # "I wouldn't have guessed Candace. I was doing more of an Alejandra"
clip(1046.0, 1059.0, zooms=[(1050.0, 1059.0, HER_C)])  # "it might be in the name" ... "it means little fiery"
clip(1130.0, 1137.2)                                   # "never would've guessed you guys are a group of teachers"
clip(1148.5, 1190.5)                                   # "Do the teachers dance?" ... "I'll make it work" -> he brings her up from her chair, first steps (user, 2026-10-05: keep the dancing)
clip(1200.8, 1240.0)                                   # (1191-1194 black: phone covered) the dance: "Under the arm" ... "all the way down" ... "You're very seductive"
clip(1271.4, 1287.6)                                   # "Thank you for the dance" ... "I need a good leader"
clip(1328.0, 1335.2)                                   # "teach you a few other..." "Do you have Instagram?"
clip(1336.2, 1362.2)                                   # "I like the outfit, the black hair" ... "It's certainly striking"
clip(1370.6, 1374.0)                                   # "I'm Thor, by the way"

# ================================================================= A: the bachelorette table
section("bachelorette")
clip(11.2, 18.0, z=A_BASE)                             # walk-up "Alright, I'm going." -> opener "What kind of secret do you guys have going on here?"
clip(21.80, 28.85, z=A_BASE, snap_cuts=False)          # (starts after a misheard fragment, in the gap at 21.74-21.82) "make sure no one's watching" "engagement rings"
clip(30.5, 33.6, z=A_BASE, zooms=[(30.5, 33.6, A_PUSH)])   # "You look like you're a little too young to get married"
clip(43.6, 52.0, z=A_BASE)                             # "pre-bachelorette party?" "Yes" "I don't believe it"
clip(58.0, 71.0, z=A_BASE)                             # "No way your name is Maddie" ... "another wild ride"
clip(136.5, 161.2, z=A_BASE, zooms=[(153.3, 161.2, A_PUSH)])   # "I got a feeling you guys aren't from here" ... "a Dallas vibe" -> her reaction "There we go! How did I know?" (one take: the cut into it chopped her cheer)
clip(165.6, 171.9, z=A_BASE)                           # "give me a high five" "I can read the energies"
clip(172.6, 183.0, z=A_BASE)                           # "people from Dallas are wild" ... "You still got some leftovers"

# ================================================================= B: the name game
section("names")
clip(553.2, 567.6, z=B_BASE)                           # opener (mic before the phone started): "You guys look like the people to know tonight"
clip(568.4, 595.0, z=B_BASE)                           # "friends since childhood" "throw a wrench in the mix" "we go way back... a year ago"
clip(606.9, 619.3, z=B_BASE)                           # "I feel like your name is Sarah" "the little Sarah vibe"
clip(641.0, 656.0, z=B_BASE, cap_map={"ONE": "", "IN": "", "NVIDIA": ""})   # (garbled "one in Nvidia" dropped) "Nowhere near" "We're going to need some hints" "We speak Spanish"
clip(657.5, 683.0, fx(668.4, text="ALEJANDRA. AGAIN.", dur=1.8), z=B_BASE)                   # "If your name is Alejandra, I'm going to lose it" (callback to C)
clip(684.8, 707.6, z=B_BASE)                           # "That's not her name" ... "Maria" "the most basic" "playing my odds"
clip(711.5, 713.7, z=B_BASE)                           # "Maricela"
clip(809.5, 818.2, z=B_BASE)                           # "can you please only speak English?" "too much for me"
clip(832.2, 850.5, z=B_BASE)   # "I like the names too much... what do I want to name my daughter"
clip(897.4, 903.3, z=B_BASE)                           # "We're going to go get a drink" "Mucho gusto"

# ================================================================= E: the traveller
section("traveller")
# (setup line to his friend at 1617.6-1622.7 cut: the phone was covered, a pure black frame)
clip(1628.0, 1634.3)                                   # opener
clip(1658.0, 1667.0)                                   # names: Sia, Sheila, "I like that"
clip(1673.2, 1687.8)                                   # "What are you getting tonight?" "I'm water only"
clip(1692.5, 1708.0)                                   # "I got a feeling you're not from here" ... "that vibe" (her answer unclear: no Dallas text pop)
clip(1842.5, 1848.8)                                   # "I've done Greece, Italy, Paris, Spain" "you've done it all"
clip(1892.6, 1906.4)                                   # "I gotta pause you there" ... "My favorite place is right here"
clip(1914.0, 1928.9)                                   # "take down my Instagram" ... "the Dallas is coming out"

# ================================================================= F: the yellow dress crew (finale)
section("finale")
clip(2469.4, 2494.3, snap_cuts=False)                 # F0 (ends at the source end: raw 2494.4 = 1994.4), one take: walking up ("No gracias"), his friend spots them and goes over first, "I'm Keegan", the girls light up (user, 2026-10-05: keep the setup where the friend notices them)
clip(1994.3, 2006.6, snap_cuts=False)                 # straight on from F0 (raw 2494.4 = 1994.4, same moment): "Did you guys pick up on something?" "He's back on it" ... "That's so American" "I'm Thor"
clip(2016.6, 2036.6)                                   # "I'm from the happiest country on earth" ... "Denmark" "way up north"
clip(2036.7, 2046.0)                                   # "I'm from the most beautiful country" ... "Greece"
clip(2052.4, 2058.11, snap_cuts=False)                 # (cut in the 80 ms gap before her next line) "I came all the way here..." "We don't got people like y'all in Denmark"
clip(2077.0, 2103.3)                                   # "You got some sort of energy" ... "the yellow dress" "can't deny a gorgeous woman"
clip(2138.6, 2147.9)                                   # "How do you keep up with the energy?" "We fuel each other, baby"
clip(2160.30, 2170.56, snap_cuts=False)               # (starts in the gap before "Good question": medium's "question." spans her garbled line) "You're being too smart now, asking my questions back to me"
clip(2174.0, 2179.3)                                   # "You're pushing me to the limit" "Is that the limit?"
clip(2240.6, 2256.2)                                   # "Hotel Vegas! We'll meet y'all there" ... "handstand tour"
clip(2266.8, 2279.5)                                   # "Do any of y'all know how to do the worm?" "special occasions"
clip(2285.2, 2307.85)                                  # "What's your name?" "Jillian" ... "God of Thunder" "No, it doesn't" "missed that lesson"
clip(2376.6, 2412.2)                                   # debrief: "she brought up a date" "I made the plan before I even texted you"
clip(2415.6, 2426.0)                                   # "she lives in Zilker" "let's go together" "That's the move"
section("end")

# dark night footage gets lifted (render.LIFT) so it never reads as a black screen
for _p in pieces:
    if _p["type"] == "clip" and luma(_p["in"], _p["out"]) < LUMA_DARK:
        _p["lift"] = True
_LUMA_CACHE.write_text(json.dumps(_luma))
print("lifted clips:", sum(1 for _p in pieces if _p.get("lift")))

# ---------------------------------------------------------------- Jameer-style cutaways (source time of the line, clip, range)
# Raw infield uses NO meme cutaways (user, 2026-10-05); the list is kept for reference only. Flirty SFX instead (below).
USE_CUTAWAYS = False
DIP = 0.25   # seconds of fade out / fade in between approaches
CUTAWAYS = [] if not USE_CUTAWAYS else [
    (1240.0, "steve_harvey_shocked", None), (1362.2, "leo_pointing", None),
    (71.0, "face_in_hands", None), (171.9, "khaled_you_smart", None), (183.0, "dicaprio_laugh", None),
    (683.0, "peele_sweating", None), (707.6, "studio_laugh", None), (850.5, "kevin_hart_stare", None),
    (1906.4, "jim_smirk", None),
    (2058.11, "gatsby_toast", None), (2170.3, "nicki_excuse_me", None), (2307.85, "kid_reaction", None),
    (2426.0, "denzel_my_man", None),
]
LIB = json.load(open(ROOT / "memeclips/library.json", encoding="utf-8"))
# ---------------------------------------------------------------- flirty SFX (user, 2026-10-05: "flirty sound effects for
# flirty moments absolutely"). Soft sparkles after a smooth line, a single heartbeat on the boldest ones; each lands as the
# line finishes (phrase end from work/speakers.json), never over the talking. No cartoon kisses or whistles (brand).
SPARKLES = itertools.cycle(["rizz_1463", "rizz_2586", "rizz_2999", "rizz_2353"])   # wand sparkle, fairy glow, choir shine, glitter
HEART = "heart_2779"                                                               # single heartbeat
FLIRT_SFX = [   # (start of the phrase in work/speakers.json, sound)
    (1055.43, "sparkle"), (1238.92, "heart"), (1285.93, "sparkle"), (1345.12, "sparkle"), (1360.14, "sparkle"),   # C
    (31.86, "sparkle"), (68.08, "heart"), (169.29, "sparkle"),                                                     # A
    (565.82, "sparkle"), (667.82, "heart"), (705.28, "sparkle"), (845.69, "heart"),                                # B
    (1904.74, "sparkle"),                                                                                          # E
    (2052.52, "sparkle"), (2100.95, "sparkle"), (2169.53, "sparkle"), (2296.98, "heart"), (2305.66, "sparkle"),    # F
]
_phr = json.load(open(ROOT / "work/speakers.json", encoding="utf-8"))
for t0, kind in FLIRT_SFX:
    ph = min(_phr, key=lambda r: abs(r[0] - t0))
    assert abs(ph[0] - t0) < 0.3, f"no phrase starts near {t0}"
    at = ph[1] + 0.05
    host = next((p for p in pieces if p["type"] == "clip" and p["in"] <= at <= p["out"] + 0.3), None)
    assert host, f"flirty SFX at {at:.2f} isn't inside a kept clip"
    host["fx"].append({"at": min(at, host["out"] - 0.05), "sfx": [HEART if kind == "heart" else next(SPARKLES)],
                       "vol": 0.55 if kind == "heart" else 0.6, "keep": True})
print(f"flirty SFX: {len(FLIRT_SFX)}")

_first_main = next(n for n, _ in sections if n != "cold")
out_pieces, new_sections = [], []
for i, p in enumerate(pieces):
    for name, idx in sections:
        if idx == i:
            new_sections.append((name, len(out_pieces)))
            if name == _first_main and TEASER:   # teaser -> branded "Sparked Thor" card -> the first approach, through black
                out_pieces.append({"type": "cut", "clip": "brand_sting", "start": 0, "dur": LIB["brand_sting"]["dur"], "fx": []})
            elif name not in ("cold", "end"):
                # raw infield: a soft dip through black between approaches, no TV glitch (user, 2026-10-05: "this is
                # not monkey app, it's a different format")
                prev = next((q for q in reversed(out_pieces) if q["type"] == "clip"), None)
                if prev and not prev.get("teaser"):
                    prev["fout"] = DIP
                    p["fin"] = DIP
    out_pieces.append(p)
    if p["type"] == "clip" and not p.get("teaser"):
        for at, name, rng in CUTAWAYS:
            if p["in"] <= at <= p["out"] + 0.05:
                a, b = rng or (0, LIB[name]["dur"])
                for f in p["fx"]:
                    if "text" in f and "at" in f:
                        f["at"] = max(p["in"], min(f["at"], p["out"] - f.get("dur", 1.4)))
                out_pieces.append({"type": "cut", "clip": name, "start": a, "dur": round(b - a, 2), "fx": []})
out_pieces.append({"type": "cut", "clip": "brand_outro_end", "start": 0, "dur": LIB["brand_outro_end"]["dur"], "fx": []})
for name, idx in sections:
    if idx >= len(pieces):
        new_sections.append((name, len(out_pieces)))
placed = sum(1 for p in out_pieces if p["type"] == "cut" and p["clip"] not in ("tv_glitch", "brand_sting", "brand_outro_end"))
print(f"cutaways placed: {placed}")
pieces, sections = out_pieces, new_sections

_main = [(n, i) for n, i in sections if n not in ("cold", "end")]
_first_name, _first_i = _main[0]
_first_end = next((i for n, i in sections if i > _first_i), len(pieces))
_first_srcs = [p["in"] for p in pieces[_first_i:_first_end] if p["type"] == "clip"]
_teaser = [p for p in pieces if p.get("teaser")]
assert not _teaser or not any(abs(_teaser[-1]["in"] - t) < 300 for t in _first_srcs), "teaser ends on the girl that opens the video"

# ---------------------------------------------------------------- timing + music
def dur(p):
    return p["out"] - p["in"] if p["type"] == "clip" else p["dur"]   # freeze / cut use "dur"


starts, t = [], 0.0
for p in pieces:
    starts.append(t)
    t += dur(p)
total = t
sec_t = {name: (starts[i] if i < len(pieces) else total) for name, i in sections}
order = [n for n, _ in sections]
bounds = {n: (sec_t[n], sec_t[order[k + 1]] if k + 1 < len(order) else total) for k, n in enumerate(order)}

tracks = {"teachers": "music/greenchair.mp3", "bachelorette": "music/chillbro.mp3", "names": "music/babe.mp3",
          "traveller": "music/sensual.mp3", "finale": "music/rnb.mp3"}
music = ([{"file": "music/breezy.mp3", "start": 0.0, "end": bounds["cold"][1], "vol": 0.22, "seek": 1.0, "fade_in": 0.03}]
         if TEASER else [])
music += [{"file": f, "start": bounds[n][0], "end": bounds[n][1], "vol": 0.08} for n, f in tracks.items()]
# end card has no speech to duck under, so the music swells up to carry it out
outro = starts[-1]
music[-1]["end"] = outro + 0.3
# (the branded outro carries its own audio, so no music swell under it)


def out_at(src):
    """Output time of the first piece containing a source time (for music drops)."""
    for p, s in zip(pieces, starts):
        if p["type"] == "clip" and not p.get("teaser") and p["in"] <= src < p["out"]:
            return s + src - p["in"]
    raise ValueError(src)


# music drops out right before the big punchlines
for m in music:
    m["drops"] = []
# the teaser ender lands dry: music out under "God of Thunder"
if TEASER:
    music[0]["drops"].append([max(bounds["cold"][1] - 2.2, 0), bounds["cold"][1]])
for src, d in [(668.4, 1.6), (1904.6, 1.6), (845.6, 1.4)]:
    try:
        o = out_at(src)
    except ValueError:
        continue
    for m in music:
        if m["start"] <= o < m["end"]:
            m["drops"].append([o - 0.25, o + d])

# smooth vibe: at most one sound every 4s (section-opening whooshes always kept)
last_sfx = -99.0
for p, st in zip(pieces, starts):
    for f in sorted(p.get("fx", []), key=lambda f: f.get("at", f.get("t", 0))):
        if "sfx" not in f:
            continue
        t = st + ((f["at"] - p["in"]) if p["type"] == "clip" else f.get("t", 0))
        if t - last_sfx < 4.0 and not f["sfx"][0].startswith("whoosh") and not f.get("keep"):
            del f["sfx"], f["vol"]
        else:
            last_sfx = t

# Speaker overrides for the split-colour captions (speakers.py tags phrases by voice + pitch; these were reviewed
# against the conversation, 2026-10-05). (start, end, "ME"|"HER"): words whose midpoint falls inside take that tag.
SPEAKER_FIX = [
    (931.0, 932.9, "ME"), (941.0, 944.0, "ME"),                         # C opener is his
    (1050.2, 1051.9, "ME"), (1052.0, 1053.0, "HER"),                    # "Do you remember what it means?" / "I don't know"
    (15.0, 15.9, "ME"), (144.2, 145.7, "ME"),                           # A: his opener, his cold read
    (586.0, 595.0, "HER"),                                              # B: "we go way back... dance class"
    (641.0, 643.3, "HER"), (655.0, 655.6, "ME"), (661.1, 662.6, "ME"), (663.8, 665.0, "HER"),
    (703.1, 707.5, "ME"), (711.4, 712.3, "HER"), (832.2, 840.5, "HER"),
    (1628.0, 1629.4, "ME"), (1680.7, 1682.0, "ME"), (1692.4, 1708.4, "ME"),   # E: opener, "I'm water only", his read
    (1892.5, 1901.0, "ME"), (1925.0, 1929.6, "ME"),                     # "I gotta pause you there" (his debrief confirms)
    (2489.1, 2490.3, "ME"),                                             # the wingman's "I'm Keegan": guys' style
    (2076.9, 2104.0, "HER"), (2138.5, 2145.0, "HER"), (2244.7, 2246.8, "HER"),
    (2376.0, 2427.0, "ME"),                                             # debrief walk: only the two guys
    (1148.5, 1150.0, "ME"), (1160.1, 1161.95, "ME"), (1206.8, 1207.6, "ME"),   # dance: his invite and his lead
    (1994.3, 1997.1, "HER"),                                            # F: "Did you guys pick up on something?" "He's back on it"
    (1373.1, 1374.1, "HER"), (2145.0, 2148.0, "ME"),                    # her "Nice to meet you"; his "We fuel each other, baby"
]

edit = {
    "name": "infield_night_v7",
    # reviewed 2026-10-04: C dance (she's mid-move), E (dark silhouettes, both women in frame), F debrief walk (no
    # women by design, the guys talking over the street)
    "her_offscreen_ok": [[1165.0, 1240.0], [1271.0, 1274.0], [1660.0, 1930.0], [2376.0, 2427.0], [2469.0, 2488.0], [1994.0, 1997.8]],
    **({"teaser_bars": {"h": 132, "end": round(bounds["cold"][1], 3)}} if TEASER else {}),
    "pieces": pieces,
    "music": music,
    "key_words": [],
    "speaker_fix": SPEAKER_FIX,
    # reviewed caption spans that are model noise, not speech: "I'm a very bad dear" stretched over 5.6 s of music
    "caption_drop": [[1181.5, 1187.6], [2478.0, 2481.5]],   # + "Dance going in. She's active until 20..." (garbled, unverifiable)
    "caption_fixes": {"KEGAN": "KEEGAN", "ZILLIO": "ZILKER", "ZILDJIAN": "ZILKER", "ZILLOW": "ZILKER"},
}
json.dump(edit, open(ROOT / "edit.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(f"{len(pieces)} pieces, {total / 60:.2f} min")
print(f"{len(SNAP_LOG)} clips moved so no sentence is cut mid-word:")
for a0, b0, a, b in SNAP_LOG:
    print(f"   {a0:8.2f}-{b0:8.2f} -> {a:8.2f}-{b:8.2f}")
_still = [(p["in"], p["out"]) for p in pieces if p["type"] == "clip" and _rms_db(p["out"] - 0.0125, 0.025) > speech_db(p["out"]) + 12]
if _still:
    print("WARNING loud speech right at the cut (check these by ear):", _still)
for n in order:
    a, b = bounds[n]
    print(f"  {n:6} {a / 60:5.2f} -> {b / 60:5.2f}  ({b - a:5.1f}s)")

# Untranscribed speech between kept clips of the same e-date: small.en leaves holes in fast back-and-forth, and a
# beat the user remembers can sit in one ("have you guys ever kissed?" was lost that way, user on v14). Flags any
# >= 2.5 s stretch of speech-level audio with no words in either transcript, so it gets re-transcribed and reviewed.
_kept = sorted((p["in"], p["out"]) for p in pieces if p["type"] == "clip")
_starts = [w["s"] for w in WORDS]
_holes = []
for (a1, b1), (a2, b2) in zip(_kept, _kept[1:] + [(1e9, 1e9)]):
    a2 = a2 if 0 < a2 - b1 < 40 else b1 + 15   # also the 15 s after a section's last clip (where the kiss line was)
    if a2 <= b1:
        continue
    run_s = None
    SPEECH_DB = speech_db(b1)
    t = b1
    while t < a2:
        i = bisect.bisect_left(_starts, t - 0.3)
        has_word = i < len(_starts) and _starts[i] < t + 0.3
        if _rms_db(t, 0.25) > SPEECH_DB + 6 and not has_word:
            run_s = t if run_s is None else run_s
            if t - run_s >= 2.5:
                _holes.append((run_s, a2)); break
        else:
            run_s = None
        t += 0.25
HOLES_OK = []   # reviewed with medium.en: no words (noise / music)
_holes = [(a, b) for a, b in _holes if not any(abs(a - h) < 1.0 for h in HOLES_OK)]
for a, b in _holes:
    print(f"WARN untranscribed speech near {a:.1f}-{b:.1f}: re-transcribe it (medium.en, vad_filter=False) and check for a missed beat")

# Cutaway audit: print the line each reaction clip follows, and fail on any cutaway whose moment was cut. Re-read
# this every time the cut changes (user, v34: "make sure the clips are still timed right for what moment they are
# tied to").
_M = [w for sg in json.load(open(ROOT / "work/transcript.json", encoding="utf-8")) for w in sg["words"]]
_S = [w for sg in json.load(open(ROOT / ("work/transcript_small.json" if (ROOT / "work/transcript_small.json").exists() else "work/transcript.json"), encoding="utf-8")) for w in sg["words"]]
_prev, _placed = None, set()
print("cutaways (clip <- the line it follows):")
for _p in out_pieces:
    if _p["type"] == "clip":
        _prev = _p
    elif _p["type"] == "cut" and _p["clip"] not in ("tv_glitch", "brand_sting", "brand_outro_end"):
        _W = _S if _prev.get("cap_src") == "small" else _M
        _ws = [w["w"].strip() for w in _W if _prev["in"] <= w["s"] < _prev["out"]]
        _placed.add(_p["clip"])
        print(f'  {_p["clip"]:22s} <- "...{" ".join(_ws[-8:])}"')
_lost = [c for _, c, _ in CUTAWAYS if c not in _placed]
assert not _lost, f"cutaways whose moment is no longer in the cut: {_lost}"
