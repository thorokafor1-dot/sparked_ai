"""Build edit.json: the cut list, fx cues and music for the Monkey app long-form.

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


# ---------------------------------------------------------------- helpers
ME = (1.45, 0.80, 0.55)          # punch-in on Thor (right of the two guys)
HER = (1.45, 0.25, 0.50)         # punch-in on her pane

pieces = []
sections = []                    # (name, first piece index) for music layout


WORDS = sorted((w for f in ("work/transcript.json", "work/transcript_small.json") if (ROOT / f).exists()
                for sg in json.load(open(ROOT / f, encoding="utf-8")) for w in sg["words"]), key=lambda w: w["s"])


import wave as _wave
import numpy as _np

_AUDIO = _wave.open(str(ROOT / "work/audio16k.wav"))
_SR16 = _AUDIO.getframerate()
SPEECH_DB = -44.0      # 50 ms RMS above this = someone is still talking (room floor ~-54; his speech ~-33)
TAIL_MAX = 0.8         # how far a clip end may be pushed to let a sentence finish


def _rms_db(t, dur=0.05):
    _AUDIO.setpos(max(int(t * _SR16), 0))
    x = _np.frombuffer(_AUDIO.readframes(int(dur * _SR16)), dtype=_np.int16).astype(float) / 32768
    return 20 * _np.log10(_np.sqrt((x ** 2).mean()) + 1e-9) if len(x) else -120.0


def snap(a, b):
    """Nudge cut points so no word or sentence is chopped.

    Word timings alone weren't enough ("I'm Filipi-" got cut: the model ended the word 0.3 s early), so the end is
    also checked against the real audio: while speech is still sounding at the cut, extend (up to TAIL_MAX).
    """
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
    if abs(a - a0) > 0.03 or abs(b - b0) > 0.03:
        SNAP_LOG.append((a0, b0, a, b))
    if zooms:
        zooms = [(a if za == a0 else za, b if zb == b0 else zb, zz) for za, zb, zz in zooms]
    # punch-ins on the guys' pane (cx > 0.5) took her off screen (user, v17: she must be visible in every frame), but
    # dropping them left highlight lines with no camera move (user, v35). They become a centred push-in instead:
    # the camera still moves on the line and both panes stay in frame.
    PUSH = (1.18, 0.5, 0.5)
    if z and z[1] > 0.5:
        z = PUSH
    zooms = [(za, zb, PUSH if zz[1] > 0.5 else zz) for za, zb, zz in (zooms or [])] or None
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


# ================================================================= HIGHLIGHT TEASER (cold open)
# 3 clips, 3 different girls, each clearly visible (no zooms), building to the payoff (user rules).
section("cold")
T = {"teaser": True}
# strong start (looking into camera), flirty lines, each ending on a cliffhanger; the LAST teaser girl must not be the
# girl the main video opens with (user: no teaser-then-same-person-right-after)
# Energy (user, v13 "feels flat"): the music hits loud from frame one (see music below), each cut lands on a soft
# whoosh with a gentle push-in on her, three different flavours (compliment -> her pushback -> her offer), then the
# music cuts out under the payoff line and the last frame freezes on a low hit before the glitch into e-date 1.
TZ = (1.2, 0.25, 0.50)    # teaser push-in: her pane only, so she stays the whole frame
# no whoosh on the teaser cuts (user, v35: "I keep hearing a sound effect for each clip in the intro teaser")
# (Nikole's "beautiful name" opener dropped: user didn't like it, v17)
clip(6134.30, 6136.80, **T)                                                 # Grace (into the lens): "you look like one of the teachers I had a crush on in school"
clip(6138.60, 6139.95, z=TZ, **T)                                           # Grace: "Are you telling me I'm old?" (cut before the answer)
clip(1860.25, 1862.55, cap_src="medium", **T)                  # Lexi & friend: "have you guys ever kissed?" + their straight-faced stare (user: good for the intro)
# ender: Madie, close to the lens, "Oh my gosh, fine [bleep]" (user, v31: use this, not the hand-over-mouth "Oh").
# Cut inside the bleep, right before "It's a YouTuber flag", so the line stays a tease. Earlier rejected: "I'll fly
# down" (low energy), the guys rating (gave away who), "please do" (phones), the "Oh-" reaction.
# no freeze frame on her face (user, v35: "looks weird"): the live clip fades to black into the brand card
_end = clip(2977.12, 2979.08, cap_src="medium", snap_cuts=False, fout=0.3, **T)   # Madie: "Oh my gosh, fine [bleep]"

# ================================================================= Grace (Filipino teacher) -- best girl first
section("grace")
# The video "starts" on the app's real connecting card (her photo, "She's 22 from Newark... Connecting..."), the way
# Jay Throck's outlier opens, so the teaser before it reads as a preview without text or speed tricks (user, v27:
# no banner, no sped-up rewind). The card is muted (the guys' chatter under it), then she connects.
clip(6033.00, 6033.90, mute=True, snap_cuts=False, fin=0.25)                # connecting card, fading up from the brand card
# tight on the lines (user, v28: "very slow paced"). The cousin (left guy, in the centred frame) greets her in Spanish.
# snapped with natural tails: the hand-tight cuts chopped "Bien" to "Bie-" and felt rushed (user, v35)
clip(6044.20, 6048.00)                                                      # "Can't tell if you're Spanish or Filipino" "I'm Filipino"
# Thor's Tagalog greeting: the old cut started at 6050.2 and clipped his whole line, leaving only her reply zoomed on
# her (user, v31). Window panned right so Thor (far right edge) is in frame. Words patched (medium + prompt, user-confirmed).
clip(6049.05, 6052.92, pan="right", cap_src="medium", snap_cuts=False)       # Thor: "Kumusta ka?" Grace: "Mabuti naman."
clip(6054.50, 6062.90)                                                      # "You spoke Tagalog" "Tagalog is my first language... English is my third"
clip(6063.80, 6068.50, fx(6066.0, "rizz", 0.7), zooms=[(6063.8, 6066.1, ME)])   # "learn some Tagalog so I could speak to cute girls like you" "Oh, whatever"
clip(6098.30, 6104.00, cap_map={"COLD": "CALL"})                                                      # cousin: "are you in a call center?" "that's kind of racist, bro"
clip(6120.00, 6125.10, z=HER)                                               # "I'm not a nurse. I'm a teacher."
clip(6134.40, 6139.90, zooms=[(6134.4, 6137.0, ME)])                      # crush on a teacher / "telling me I'm old?"
clip(6141.70, 6143.85)                                                      # "you got to be a teacher, don't you?"
clip(6144.95, 6150.30, fx(6149.85, "rizz_2353", 0.6, img="memes/badge_grace.png", w=560, pos=(480, 190), dur=2.0))                          # "How old do you think I am?" ... "Twenty-two."
clip(6155.50, 6161.20, z=HER)                                               # "blow him a kiss for that one" "He got it right"
clip(6201.10, 6203.40)                                                      # "on here looking for your husband?"
clip(6204.60, 6209.80, z=HER)                                               # "killing time... I go to bed at 11"
clip(6213.10, 6214.40, fx(6214.2, "rizz", 0.5))                            # "That means you got 40 minutes left."
clip(6216.30, 6217.80)                                                      # "We won't hold you up."

# ================================================================= Lexi & friend (dentist)
section("lexi")
clip(1798.10, 1803.30, cap_src="medium")                                                      # "looking comfy on that bed" "you look like a dentist"
clip(1804.30, 1813.30, zooms=[(1810.7, 1813.3, ME)], cap_src="medium")    # "second time we got that today" "Really?" "Yeah." "he actually is a dentist... sleeping on his couch" (medium words patched in)
clip(1840.40, 1841.70, fx(1841.70, "impact_2303", 0.8, keep=True), z=HER)  # "Are you all together?" + the low drop hit (user, v26)
# the whole together/kissed exchange (user: "you cut the clip short ... where I ask if they ever kissed"); small.en
# missed these lines, so their captions are medium.en words patched into work/transcript.json
M = {"cap_src": "medium"}
clip(1843.00, 1844.00, cap_map={"HE": "", "COULDN'T": ""}, **M)                                               # "He's my cousin."
clip(1847.20, 1850.20, **M)                                                 # "We know it's 2025, but we don't swing that way."
clip(1851.50, 1853.30, **M)                                                 # "We're together." "Really?"
clip(1854.35, 1858.25, z=HER, **M)                                          # "No. We're like best friends." "We are."
# kept whole through their answer (user, v26: "it's cut out what they actually said"); their mumbled reply is too
# quiet for either model, so it plays uncaptioned rather than guessed
clip(1858.90, 1870.90, zooms=[(1861.3, 1867.0, HER)], **M)                  # "ever kissed?" -> their answer -> "I don't believe you guys... straight face"

# (Anna cut: she's off camera for the whole call, only hair and a shoulder in frame. User, v17: "don't use clips
#  where the girl can't even be seen"; check_her_visible.py now gates it)

# ================================================================= Ohio friends (Madie, 25)
section("ohio")
# opens on the flag (user, v18: "madie clip still isn't starting with the comment about the danny duncan flag");
# "Do you have a charger?" (an aside off-camera) is cut between the two lines. Medium words patched in.
# the cousin's line that prompts it (user, v26), played straight through the beat before her correction
# one uncut take from the flag through "which one?": her not paying attention, then turning to them with "Oh my
# gosh, fine [bleep]" is the moment (user, v35: "I don't want cuts in the brief moment before she says that"), and the
# cousin's "which one?" sets up her rating (user: "it's cut out when my cousin asks: which one?")
clip(2970.05, 2983.62, cap_src="medium", snap_cuts=False)                  # "Y'all are patriots" "Danny Duncan flag" ... "fine [bleep]" ... "which one?"
clip(2989.60, 2991.65, cap_src="medium")                                   # cousin: "Nah, nah, you said fine [bleep]. We want to know which one."
clip(2993.60, 3009.95, cap_src="medium", cap_map={"BRO": "", "WHAT": "", "A": ""})               # rating the guys: "fine one on the left, funny one on the right"
clip(3012.80, 3020.60, fx(3020.4, "rizz", 0.7))                            # "where you from?" "Texas" "Ohio. We'll fly down to see you"
clip(3025.90, 3027.30)                                                      # "what's your gram?"
clip(3038.25, 3039.50)                                                      # "what's your gram?... I'll look you up right now"
clip(3087.20, 3100.60, fx(3098.0, "rizz", 0.6), zooms=[(3094.8, 3098.2, ME)])   # "nothing to do in Ohio" "you just gotta come out here" "Please do"

# (Mia cut: her whole call is ~20 s of small talk, "where's that" / "Illinois" / "what's your name", no flirt beat.
#  User, v21: "does anything even happen?")

# ================================================================= Nikole (finale)
section("nikole")
clip(9053.80, 9059.00)                                                      # "a chicken your mama made?" "No, I made it"
clip(9059.50, 9064.10, zooms=[(9059.5, 9062.6, ME)])                      # "cooking your own food now, you're a grown-up" "I'm a grown person"
clip(9076.80, 9079.40)                                                      # "I like the bandana" "Thank you"
clip(9100.70, 9104.50, z=HER)                                               # "what do you got on it? roses?" "some kind of flowers"
clip(9107.50, 9112.30, zooms=[(9107.5, 9110.3, ME)])                      # "What's your name? ...something to do with those flowers" "It's Nicole"
clip(9112.80, 9119.10, fx(9118.9, "rizz", 0.7))                            # "That match you. A beautiful name for a beautiful girl."
clip(9120.70, 9127.50, z=HER)                                               # "Thank you" "nice smile" "You have a beautiful smile, sir"
clip(9128.60, 9129.70)                                                      # "Is this your gay best friend?"
section("end")

# Two guys talking over each other: the medium model drops whole lines here, so small-model captions are the
# default for this video; clips marked cap_src="medium" are the few where medium reads better.
for _p in pieces:
    if _p["type"] == "clip":
        _p.setdefault("cap_src", "small")

# ---------------------------------------------------------------- Jameer-style cutaways
# Full-screen reaction clips with their own audio, cut in right after the line (the call pauses), about
# one every 30-40s, plus a TV color-bar glitch at every call change. Library: memeclips/ (from the
# user's own published edit), see memeclips/library.json. (source time of the moment, clip, [start, end])
CUTAWAYS = [
    (6068.5, "denzel_my_man", None), (6104.0, "athlete_facepalm", None), (6139.9, "steve_harvey_shocked", None),
    (6161.2, "khaled_you_smart", None), (6217.8, "imma_head_out", (2.5, 4.5)),
    (1803.3, "nick_young_confused", None), (1813.3, "studio_laugh", (0.45, 1.14)), (1841.7, "jontron_what", None), (1870.9, "kevin_hart_stare", None),
    (3009.95, "jim_smirk", None), (3020.6, "gatsby_toast", None), (3100.6, "leo_pointing", None),
    (9127.5, "suit_thats_it", None), (9129.7, "lying_down", None),
]
LIB = json.load(open(ROOT / "memeclips/library.json", encoding="utf-8"))
_first_main = next(n for n, _ in sections if n != "cold")
for _p in pieces[:dict(sections)[_first_main]]:
    _p["badge_y"] = 132 + 26
out_pieces, sec_starts = [], {i for _, i in sections}
new_sections = []
for i, p in enumerate(pieces):
    for name, idx in sections:
        if idx == i:
            new_sections.append((name, len(out_pieces)))
            if name == _first_main:
                # teaser -> branded "Sparked Thor" card (make_brand_sting.py) -> connecting card, all through black
                # (user, v33: "a brief branded screen", "goes from intro into main video too abruptly")
                out_pieces.append({"type": "cut", "clip": "brand_sting", "start": 0, "dur": LIB["brand_sting"]["dur"], "fx": []})
            elif name not in ("cold", "end"):
                out_pieces.append({"type": "cut", "clip": "tv_glitch", "start": 0, "dur": LIB["tv_glitch"]["dur"], "fx": []})
    out_pieces.append(p)
    if p["type"] == "clip" and not p.get("teaser"):
        for at, name, rng in CUTAWAYS:
            if p["in"] <= at <= p["out"] + 0.05:
                a, b = rng or (0, LIB[name]["dur"])
                # a text pop at the end of this line must finish before the cutaway covers it
                for f in p["fx"]:
                    if "text" in f and "at" in f:
                        f["at"] = max(p["in"], min(f["at"], p["out"] - f.get("dur", 1.4)))
                out_pieces.append({"type": "cut", "clip": name, "start": a, "dur": round(b - a, 2), "fx": []})
# Sparked branded outro ("Learn to spark attraction." + subscribe click), lifted from the user's own
# upload mGdLijMC6_s @394.23s. Replaces the old SUBSCRIBE freeze card (user, 2026-09-28).
out_pieces.append({"type": "cut", "clip": "brand_outro_end", "start": 0, "dur": LIB["brand_outro_end"]["dur"], "fx": []})
for name, idx in sections:
    if idx >= len(pieces):
        new_sections.append((name, len(out_pieces)))
used = {c for _, c, _ in CUTAWAYS}
placed = sum(1 for p in out_pieces if p["type"] == "cut" and p["clip"] != "tv_glitch")
print(f"cutaways placed: {placed} (moments not in this cut are skipped)")
pieces, sections = out_pieces, new_sections

# guard: the teaser's last clip may not come from the section that opens the video
_main = [(n, i) for n, i in sections if n not in ("cold", "end")]
if _main:
    _first_name, _first_i = _main[0]
    _first_end = next((i for n, i in sections if i > _first_i), len(pieces))
    _first_srcs = [p["in"] for p in pieces[_first_i:_first_end] if p["type"] == "clip"]
    _last_teaser = [p for p in pieces if p.get("teaser")][-1]
    assert not any(abs(_last_teaser["in"] - t) < 300 for t in _first_srcs),         f"teaser ends on the same girl that opens the video ({_first_name}); reorder the teaser"

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

tracks = {"grace": "music/greenchair.mp3","lexi": "music/chillbro.mp3", "ohio": "music/babe.mp3", "nikole": "music/rnb.mp3"}
# teaser bed: breezy's punchiest stretch (from 1 s), hitting from the first frame and loud enough to survive the duck
music = [{"file": "music/breezy.mp3", "start": 0.0, "end": bounds["cold"][1], "vol": 0.22, "seek": 1.0, "fade_in": 0.03}]
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
# teaser: the music stops dead under "fine [bleep]", so the payoff lands dry into the freeze
for p, st in zip(pieces, starts):
    if p.get("teaser") and p["in"] <= 2978.35 < p["out"]:
        music[0]["drops"].append([st + 2978.35 - p["in"] - 0.05, bounds["cold"][1]])
for src, d in [(6066.0, 1.2), (6150.1, 1.5), (3020.4, 1.2), (9118.9, 2.0)]:
    try:
        o = out_at(src)
    except ValueError:
        continue   # that moment isn't in this cut
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

# her Monkey badge (name, age, city) stays visible (user: ages matter, nothing to censor); r = the pill's right
# edge in the raw frame, measured per girl since it depends on name length. (source span, r)
BADGES = [((1790, 1870), 177), ((2900, 3110), 188), ((6033.85, 6225), 145), ((6275, 6350), 152),
          ((6815, 6835), 166), ((9045, 9135), 148)]

edit = {
    "name": "first_video_v37",
    "badges": [{"span": list(sp), "r": r} for sp, r in BADGES],
    # the connecting card has no face by design (reviewed); check_her_visible.py skips it
    "her_offscreen_ok": [[6032.9, 6034.0]],
    # cinematic bars over the teaser that glide open on the connecting card (render.py); badges sit below the bar
    "teaser_bars": {"h": 132, "end": round(bounds["cold"][1], 3)},
    "pieces": pieces,
    "music": music,
    "key_words": ["LOVE", "BABY", "KISS", "KISSING", "HEART", "DATE", "SPARKS", "MAGIC", "GLOWING", "FALL",
                  "PARIS", "SPECIAL", "LIPSTICK", "MODEL", "TOUCH", "SPICY", "INTEREST", "THOR", "HONEYMOON",
                  "HONEYMOONS", "BEAUTIFUL", "FLIRTY", "VOICE", "TOGETHER"],
    "caption_fixes": {"DENVER": "DENMARK", "SATISFIED": "CERTIFIED", "VACHATA": "BACHATA", "LEARY": "LYRIC"},
}
json.dump(edit, open(ROOT / "edit.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(f"{len(pieces)} pieces, {total / 60:.2f} min")
print(f"{len(SNAP_LOG)} clips moved so no sentence is cut mid-word:")
for a0, b0, a, b in SNAP_LOG:
    print(f"   {a0:8.2f}-{b0:8.2f} -> {a:8.2f}-{b:8.2f}")
_still = [(p["in"], p["out"]) for p in pieces if p["type"] == "clip" and _rms_db(p["out"] - 0.0125, 0.025) > SPEECH_DB + 12]
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
HOLES_OK = [6838.6, 2980.6, 2980.9, 3072.3]   # reviewed with medium.en: no words (noise / music)
_holes = [(a, b) for a, b in _holes if not any(abs(a - h) < 1.0 for h in HOLES_OK)]
for a, b in _holes:
    print(f"WARN untranscribed speech near {a:.1f}-{b:.1f}: re-transcribe it (medium.en, vad_filter=False) and check for a missed beat")

# Cutaway audit: print the line each reaction clip follows, and fail on any cutaway whose moment was cut. Re-read
# this every time the cut changes (user, v34: "make sure the clips are still timed right for what moment they are
# tied to").
_M = [w for sg in json.load(open(ROOT / "work/transcript.json", encoding="utf-8")) for w in sg["words"]]
_S = [w for sg in json.load(open(ROOT / "work/transcript_small.json", encoding="utf-8")) for w in sg["words"]]
_prev, _placed = None, set()
print("cutaways (clip <- the line it follows):")
for _p in out_pieces:
    if _p["type"] == "clip":
        _prev = _p
    elif _p["type"] == "cut" and _p["clip"] not in ("tv_glitch", "brand_sting", "brand_outro_end"):
        _W = _M if _prev.get("cap_src") == "medium" else _S
        _ws = [w["w"].strip() for w in _W if _prev["in"] <= w["s"] < _prev["out"]]
        _placed.add(_p["clip"])
        print(f'  {_p["clip"]:22s} <- "...{" ".join(_ws[-8:])}"')
_lost = [c for _, c, _ in CUTAWAYS if c not in _placed]
assert not _lost, f"cutaways whose moment is no longer in the cut: {_lost}"
