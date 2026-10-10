"""Build edit.json: the cut list, fx cues and music for the Monkey app long-form.

Times are source timestamps in raw/raw.mkv. SFX are named by category and rotated so the
same sound never plays twice in a row. Run: python build_edit.py && python render.py
"""
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
CAT_REMAP = {"heart": None, "crowd": None, "joke": None, "fail": "impact", "stun": "impact", "whistle": "rizz",
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
ME = (1.45, 0.72, 0.47)          # punch-in on me
ANNA = (1.45, 0.30, 0.47)
ALE = (1.45, 0.25, 0.50)
INDIA = (1.35, 0.27, 0.60)

pieces = []
sections = []                    # (name, first piece index) for music layout


WORDS = sorted((w for sg in json.load(open(ROOT / "work/transcript.json", encoding="utf-8")) for w in sg["words"]),
               key=lambda w: w["s"])


def snap(a, b):
    """Nudge cut points so no word is chopped mid-way (max 0.6s either side)."""
    for i, w in enumerate(WORDS):
        if w["s"] < a < w["e"] - 0.08 and a - w["s"] < 0.6:
            prev_e = WORDS[i - 1]["e"] if i else 0
            a = max(w["s"] - 0.04, prev_e + 0.01)
        if w["s"] < b - 0.08 and w["e"] > b and w["e"] - b < 0.6:
            nxt = WORDS[i + 1]["s"] if i + 1 < len(WORDS) else w["e"] + 1
            b = min(w["e"] + 0.08, max(nxt - 0.02, w["e"]))
    return round(a, 3), round(b, 3)


def clip(a, b, *fx, z=None, zooms=None, **kw):
    a0, b0 = a, b
    a, b = snap(a, b)
    if zooms:
        zooms = [(a if za == a0 else za, b if zb == b0 else zb, zz) for za, zb, zz in zooms]
    p = {"type": "clip", "in": a, "out": b, "fx": list(fx), **kw}
    if z:
        p["zoom"] = list(z)
    if zooms:
        p["zooms"] = [[za, zb, *zz] for za, zb, zz in zooms]
    pieces.append(p)
    return p


def freeze(at, dur, *fx, z=None, dim=True):
    p = {"type": "freeze", "at": at, "dur": dur, "dim": dim, "fx": list(fx)}
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
# 3 clips max, 3 different girls, each woman clearly visible in every frame (no zooms here), Alejandra first (user), building to the "I'm Thor" payoff, then the title card.
# teaser=True: no cutaways inserted here, and music drops stay on the full moments later.
section("cold")
T = {"teaser": True}
clip(2537.70, 2539.72, **T)                                     # Alejandra: "You're too flirty, buddy."
clip(452.60, 457.25, fx(457.1, "rizz", 0.4), **T)       # India friends, both clearly on camera: "are you alone? because you got my interest"            # India friends: "No pen, no paper..."
clip(2185.80, 2189.30, fx(2188.4, "impact", 0.8), **T)   # "Who do you think you are?" "I'm Thor." (no zoom: she stays in frame)

# Pacing matched to Jameer / the user's own edit (measured 2026-09-28): short girls ~30s, standouts 60-90s,
# never 2+ minutes on one girl. Alejandra opens (user: not the blonde first), strongest payoff closes.

# ================================================================= E-DATE #1: Alejandra (opens: strongest hook, user 2026-09-28)
section("ale")
clip(2297.95, 2300.00, fx(2298.0, "whoosh", 0.7, text="E-DATE #1", style="banner", dur=1.2), cap_src="small")
clip(2302.40, 2303.30, z=ALE)
clip(2304.30, 2307.40, zooms=[(2305.1, 2307.4, ME)])
clip(2309.15, 2309.75, z=ALE)
clip(2324.50, 2325.40)
clip(2327.20, 2330.75, fx(2330.0, "rizz", 0.7), zooms=[(2329.1, 2330.75, ME)])                   # "that's why you're glowing"
clip(2333.45, 2334.20, z=ALE)
clip(2351.60, 2358.20)                                                                              # anniversaries, honeymoons
clip(2361.50, 2362.25, z=ALE, cap_src="small")                                                     # "You're crazy"
clip(2366.05, 2367.95)                                                                              # "Let's take it back, what's your name?"
clip(2370.55, 2371.15, z=ALE, nocap=True)                                                        # her name (both models mishear it, so no caption)
clip(2372.60, 2374.00, zooms=[(2372.6, 2374.0, ME)])                                             # "I like how you said that."
clip(2537.70, 2539.72, z=ALE)                                                                       # "You're too flirty, buddy"
clip(2542.25, 2543.60, fx(2543.4, "rizz", 0.7), z=ME, cap_src="small", cap_map={"EAT": ""})      # (starts after her "...to eat")
clip(2545.40, 2549.85)                                                                              # "the way you said Alejandra"
clip(2675.30, 2677.60)                                                                              # "so I can plan our first date"
clip(2680.90, 2683.95, z=ALE)
clip(2685.95, 2688.70, zooms=[(2685.95, 2688.7, ME)])                                             # "started with the honeymoon"
clip(2693.40, 2698.60, z=ALE)                                                                       # "I like both calm and crazy." (setup)
clip(2732.50, 2734.70)                                                                              # "I gotta be careful with you"
clip(2754.50, 2760.40, fx(2757.7, "impact", 0.6, text="THOR-NS?! ⚡", color="yellow", dur=1.6), z=ALE)
clip(2761.90, 2764.85, zooms=[(2763.6, 2764.85, ME)])
clip(2766.10, 2767.90, z=ALE)
clip(2768.60, 2769.15)                                                                              # "Oh, dang." (trailing 'You' trimmed)
clip(3432.00, 3433.70, z=ALE)                                                                       # touching my hair
clip(3438.40, 3439.70, zooms=[(3438.4, 3439.7, ME)])
clip(3441.80, 3445.55, fx(3445.4, "rizz", 0.6), zooms=[(3444.2, 3445.55, ME)])
clip(3447.20, 3450.70, z=ALE)
clip(3451.90, 3453.10, z=ME)                                                                        # "I already know."
# getting her Instagram, played out to how it ended (user: don't cut how it ended). Spelled parts fully bleeped.
clip(3083.85, 3090.90, cap_map={"BELIEVE": "LEAVE", "IN": ""})   # "I can't leave this call without your Instagram..." (models mishear "leave")
clip(3119.30, 3121.95, zooms=[(3119.3, 3121.95, ME)])                                             # "I want you to say it. I like your voice."
clip(3123.20, 3124.50, z=ALE)                                                                       # "Oh my God."
clip(3141.90, 3145.50)                                                                              # "What's your tag?" "Wait... okay."
clip(3145.55, 3147.85, z=ALE, nocap=True, bleep_all=True)                                         # handle, part 1: bleeped
clip(3153.75, 3156.10, nocap=True, bleep_all=True)                                                # "And A lowercase" / "A lowercase": bleeped
clip(3156.10, 3160.80)                                                                              # "uh-huh" "That's it?" "Uh-huh."
clip(3161.95, 3164.90, fx(3164.7, "rizz", 0.6), zooms=[(3162.3, 3164.9, ME)])                   # "gotta save that, put a little heart around it"
clip(3168.45, 3176.40, z=ALE)                                                                       # "Oh my God... nice meeting you for sure. You have a good vibe."

# ================================================================= E-DATE #3: quick hit (Samantha, 22, badge-verified adult)
section("quick1")
clip(196.70, 198.05, fx(196.75, "whoosh", 0.6, text="E-DATE #3", style="banner", dur=1.2), zooms=[(196.7, 198.05, ME)])  # "what are you guys looking good for?"
clip(198.05, 200.40, nocap=True)                                                                   # her friend turns away

# ================================================================= E-DATE #4: India besties (quick one)
section("india")
clip(237.70, 240.60, fx(237.75, "whoosh", 0.6, text="E-DATE #4", style="banner", dur=1.4),
     fx(240.45, "rizz", 0.8), zooms=[(239.7, 240.6, ME)])                                         # "I'm from your heart"
clip(248.30, 251.70)
clip(252.50, 255.75, z=INDIA, cap_src="small")   # "No pen, no paper..."
clip(256.65, 258.50, fx(256.7, text="SHE'S COOKING", color="yellow", dur=1.3))
clip(282.55, 284.30, z=INDIA, cap_src="small")   # airport line
clip(286.60, 287.90, cap_src="small")
clip(289.25, 289.80, cap_src="small")
clip(291.25, 292.95, z=INDIA, cap_src="small")
clip(297.40, 301.15, zooms=[(297.4, 301.15, ME)])                                                 # "you got all the lines ready"
clip(446.70, 448.45, z=INDIA, cap_src="small")   # "are you alone?"
clip(450.10, 452.70)
clip(452.60, 457.25, z=INDIA, cap_src="small")   # "because you got my interest"
clip(460.50, 462.30, fx(460.6, text="SHE GOT ME", color="pink", dur=1.4), z=ME, cap_src="small")

# ================================================================= E-DATE #5: quick hit (TOCH, 27, badge-verified adult)
section("quick2")
clip(3551.00, 3553.50, fx(3551.05, "whoosh", 0.6, text="E-DATE #5", style="banner", dur=1.2))     # "How's it going?" "Good."
clip(3554.70, 3557.20, fx(3556.2, "rizz", 0.6), zooms=[(3556.0, 3557.2, (1.45, 0.25, 0.5))])      # "glad to see you doing how you're looking" + her smile

# ================================================================= Anna (single finale, ~90s)
# User: "the blonde girl is taking up way too much of the video" -> one tight section, best beats only.
section("anna")
clip(1071.05, 1074.05)                                                                              # "Let's introduce ourselves"
clip(1076.25, 1083.00, fx(1082.8, "rizz", 0.8), zooms=[(1080.4, 1083.0, ME)])                   # "My name is Love"
clip(1083.90, 1087.80)                                                                              # "What is your name?" "It's Thor"
clip(1472.50, 1485.75, z=ANNA)                                                                      # "I want someone to do everything... all the crazes... scared to do with the love of my life"
clip(1487.70, 1496.40, fx(1496.2, "rizz", 0.8), zooms=[(1493.8, 1496.4, ME)], cap_src="small")   # "so you can fall for me"
clip(1644.80, 1654.35, fx(1654.2, "glitch", 0.8), zooms=[(1649.0, 1654.35, ME)])                # Paris
freeze(1654.30, 1.1, rel(0.0, "glitch", 0.7, text="WAIT... 🤨", style="banner", dur=1.05), z=ME)
clip(2412.10, 2418.35, fx(2412.15, text="SAME LINE ON ALEJANDRA 💀", style="banner", dur=2.2),
     zooms=[(2416.2, 2418.35, ME)], flashback=True)                                               # the earlier line, styled as a memory
clip(2113.40, 2114.60)                                                                              # "you just put makeup on?"
clip(2115.90, 2116.80, z=ANNA, cap_src="small")
clip(2120.50, 2121.90, zooms=[(2120.5, 2121.9, ME)], cap_src="small")                                              # "felt like kissing you"
clip(2144.10, 2150.10, zooms=[(2147.3, 2150.1, ME)])                                              # lipstick
clip(2152.05, 2155.50, z=ANNA)
clip(2162.25, 2164.15)                                                                              # "I'm just making you want to rap or something."
clip(2165.85, 2166.70, z=ANNA)                                                                      # "No, I don't rap."
clip(2167.85, 2169.35, fx(2169.2, "tension", 0.5), z=ME)                                          # "making you want to do other things"
clip(2170.90, 2171.40, z=ANNA)
clip(2173.95, 2176.00, z=ANNA)
clip(2178.20, 2180.10)
clip(2182.00, 2183.85, z=ANNA)
clip(2185.80, 2187.05, fx(2185.9, "tension", 0.6), z=ANNA)
clip(2188.30, 2189.30, fx(2188.4, "impact", 0.9), z=ME)                                           # "I'm Thor."
clip(2190.85, 2193.55, fx(2193.4, "rizz", 0.7))
section("end")

# ---------------------------------------------------------------- Jameer-style cutaways
# Full-screen reaction clips with their own audio, cut in right after the line (the call pauses), about
# one every 30-40s, plus a TV color-bar glitch at every call change. Library: memeclips/ (from the
# user's own published edit), see memeclips/library.json. (source time of the moment, clip, [start, end])
CUTAWAYS = [
    (292.9, "face_in_hands", None), (421.9, "athlete_facepalm", None), (457.1, "kid_reaction", None),
    (844.5, "face_in_hands", None), (1118.8, "idris_laugh", None), (1180.3, "suit_thats_it", None),
    (1403.2, "doctor_youre_dying", None), (1496.3, "el_risitas_laugh", None), (1561.9, "goofy_face", None),
    (1742.35, "chicago_cap_guy", None), (2418.2, "law_and_order", None), (2688.6, "studio_laugh", (0.45, 1.14)),
    # v5: higher frequency (user: "use a higher frequency of funny gif esque clips")
    (240.6, "denzel_my_man", None), (255.75, "khaled_you_smart", None), (638.55, "michael_scott_no", None),
    (676.1, "lying_down", None), (706.9, "dicaprio_laugh", None), (772.5, "suit_thats_it", None),
    (917.35, "kevin_hart_stare", None), (935.45, "red_hoodie", (0.5, 2.5)), (1712.6, "athlete_facepalm", None),
    (2155.5, "lying_down", None), (2171.4, "kevin_hart_stare", None), (2493.0, "why_are_you_running", None),
    (2539.72, "steve_harvey_shocked", None), (2769.3, "dicaprio_laugh", None), (3062.45, "khaled_you_smart", None),
    (3296.9, "kid_reaction", None), (3176.35, "imma_head_out", (2.5, 4.5)),
    (200.40, "why_are_you_running", None),   # quick hit: her friend turns away
]
LIB = json.load(open(ROOT / "memeclips/library.json", encoding="utf-8"))
out_pieces, sec_starts = [], {i for _, i in sections}
new_sections = []
for i, p in enumerate(pieces):
    for name, idx in sections:
        if idx == i:
            new_sections.append((name, len(out_pieces)))
            if name not in ("cold", "end"):
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
out_pieces.append({"type": "cut", "clip": "brand_outro", "start": 0, "dur": LIB["brand_outro"]["dur"], "fx": []})
for name, idx in sections:
    if idx >= len(pieces):
        new_sections.append((name, len(out_pieces)))
used = {c for _, c, _ in CUTAWAYS}
placed = sum(1 for p in out_pieces if p["type"] == "cut" and p["clip"] != "tv_glitch")
print(f"cutaways placed: {placed} (moments not in this cut are skipped)")
pieces, sections = out_pieces, new_sections

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

tracks = {"ale": "music/babe.mp3", "quick1": "music/chillbro.mp3", "india": "music/greenchair.mp3", "quick2": "music/chillbro.mp3", "anna": "music/sensual.mp3"}
music = [{"file": "music/breezy.mp3", "start": 0.0, "end": bounds["cold"][1], "vol": 0.08}]
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
for src, d in [(1082.7, 1.2), (1174.7, 1.3), (1496.1, 1.2), (2188.3, 3.0), (3453.0, 1.4), (1742.3, 1.5)]:
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
        if t - last_sfx < 4.0 and not f["sfx"][0].startswith("whoosh"):
            del f["sfx"], f["vol"]
        else:
            last_sfx = t

edit = {
    "name": "monkey_longform_v19",
    "pieces": pieces,
    "music": music,
    "key_words": ["LOVE", "BABY", "KISS", "KISSING", "HEART", "DATE", "SPARKS", "MAGIC", "GLOWING", "FALL",
                  "PARIS", "SPECIAL", "LIPSTICK", "MODEL", "TOUCH", "SPICY", "INTEREST", "THOR", "HONEYMOON",
                  "HONEYMOONS", "BEAUTIFUL", "FLIRTY", "VOICE", "TOGETHER"],
    "caption_fixes": {"DENVER": "DENMARK", "SATISFIED": "CERTIFIED", "VACHATA": "BACHATA", "LEARY": "LYRIC"},
}
json.dump(edit, open(ROOT / "edit.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
print(f"{len(pieces)} pieces, {total / 60:.2f} min")
for n in order:
    a, b = bounds[n]
    print(f"  {n:6} {a / 60:5.2f} -> {b / 60:5.2f}  ({b - a:5.1f}s)")
