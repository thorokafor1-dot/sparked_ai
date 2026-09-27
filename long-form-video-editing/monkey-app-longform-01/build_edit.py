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
TEXT_MAP = {"SHE'S COOKING": "SHE CAME PREPARED", "HOLD ON 🤨": None, "LOVE LANGUAGES 💀": "THE FIVE LOVE LANGUAGES",
            "PHYSICAL TOUCH?!": "PHYSICAL TOUCH.", "NICE. NICE. GREAT. 😏": None, "SAME LINE AGAIN 💀": "SAME LINE. NEW GIRL.",
            "SHE SAID KIDS?! 😳": "SHE BROUGHT UP KIDS", "SHE CALLED ME BABY 😳": "SHE CALLED ME BABY",
            "WE'RE COMING BACK TO ANNA 👀": "WE'LL COME BACK TO ANNA", "THOR-NS?! ⚡": "THOR-NS", "98% 📈": None,
            "W": None, "BACK TO ANNA 👀": "BACK TO ANNA", "WAIT... 🤨": "WAIT A SECOND...",
            "SAME LINE ON ALEJANDRA 💀": "SAME LINE. DIFFERENT GIRL.", "EMOTIONAL DAMAGE 💀": None,
            "SUBSCRIBE FOR PART 2 ⚡": "PART 2 SOON. SUBSCRIBE.", "FIRST CALL 👀": "E-DATE #1"}


def fx(at, sfx=None, vol=0.75, **kw):
    if "emoji" in kw:                      # emoji pops retired for a more mature look
        for k in ("emoji", "pos", "w", "rot"):
            kw.pop(k, None)
    if "meme" in kw or "clip" in kw:       # reactions are full-screen cutaways now (CUTAWAYS), not overlays
        kw.pop("meme", None); kw.pop("clip", None)
        if "text" not in kw:
            kw.pop("dur", None)
    if "text" in kw:
        t = TEXT_MAP.get(kw["text"], kw["text"])
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
# 3 clips max (user): the strongest beats, building to the "I'm Thor" payoff, then the title card.
# teaser=True: no cutaways inserted here, and music drops stay on the full moments later.
section("cold")
T = {"teaser": True}
clip(2537.70, 2539.72, z=ALE, **T)                                     # "You're too flirty, buddy."
clip(2147.30, 2150.05, fx(2147.4, "rizz", 0.4), z=ME, **T)             # "All over my neck, all over my face."
clip(2185.80, 2189.30, fx(2188.4, "impact", 0.8),                     # "Who do you think you are?" "I'm Thor."
     zooms=[(2185.80, 2187.05, ANNA), (2188.30, 2189.30, ME)], **T)
freeze(2189.25, 1.6, rel(0.05, "whoosh", 0.7, text="MONKEY APP\\NE-DATES", dur=1.5, color="white"), z=ME)

# ================================================================= GIRL 1+2: India besties
section("india")
clip(237.70, 240.60, fx(237.75, "whoosh", 0.6, text="FIRST CALL 👀", style="banner", dur=1.6),
     fx(240.45, "rizz", 0.8), fx(240.5, emoji="1f60f"), zooms=[(239.7, 240.6, ME)])
clip(248.30, 251.70)
clip(252.50, 255.75, fx(255.6, ["crowd"], 0.6), z=INDIA)
clip(256.65, 258.50, fx(256.7, text="SHE'S COOKING", color="yellow", dur=1.3),
     fx(256.75, emoji="1f9d1-200d-1f373", pos=(1520, 520)))
clip(282.55, 284.30, z=INDIA)
clip(286.60, 287.90)
clip(289.25, 289.80)
clip(291.25, 292.95, fx(292.9, "impact", 0.8, meme="cinema", dur=1.4), z=INDIA)
clip(297.40, 301.15, fx(297.5, "pop", 0.5), fx(299.8, emoji="1f440"), zooms=[(297.4, 301.15, ME)])
clip(400.50, 404.00, z=INDIA)  # "We did our masters in cyber security."
clip(404.60, 414.00, fx(407.75, "rizz", 0.7), fx(413.5, "whistle", 0.6, emoji="1f60f", pos=(560, 330)),
     zooms=[(410.0, 414.0, ME)])
clip(416.75, 417.75, z=INDIA)  # "And also you can hack."
clip(418.55, 422.60, fx(421.9, "stun", 0.8, meme="monkeypuppet", dur=1.5), zooms=[(421.85, 422.6, ME)], cap_src="small")
clip(446.70, 448.45, fx(446.8, text="HOLD ON 🤨", style="banner", dur=1.2), z=INDIA)
clip(450.10, 452.70)
clip(452.60, 457.25, fx(457.1, ["impact", "crowd"], 0.8, meme="pikachu", dur=1.5), z=INDIA)
clip(460.50, 462.30, fx(460.6, text="SHE GOT ME", color="pink", dur=1.4), z=ME, cap_src="small")
clip(596.30, 598.95, z=INDIA)  # "Kind of like three and a half."
clip(603.10, 605.80, fx(605.6, "rizz", 0.7), fx(605.7, emoji="1f60d", pos=(560, 330)))
clip(612.90, 615.95)
clip(619.35, 621.35, z=INDIA)  # "Obviously English."
clip(622.60, 623.50, z=INDIA)  # "Maybe four?"
clip(627.00, 632.75, fx(629.95, "tension", 0.5))
clip(633.90, 635.40, nocap=True)
clip(637.20, 638.55, fx(638.2, "pop", 0.6, text="LOVE LANGUAGES 💀", color="yellow", dur=1.4))
clip(665.85, 670.45, zooms=[(668.5, 670.45, ME)], cap_src="small")
clip(673.70, 676.10, fx(674.75, "heart", 0.8), fx(674.8, emoji="1f633", pos=(1500, 330), w=210),
     fx(675.3, text="PHYSICAL TOUCH?!", color="pink", dur=1.3), zooms=[(675.15, 676.1, ME)])
clip(678.85, 683.40)  # "Do you do anything like dancing?" "We both are dancers."
clip(684.00, 685.40)
clip(686.70, 688.95)
clip(697.30, 699.15)
clip(704.15, 706.90, fx(706.8, "rizz", 0.7), fx(706.8, emoji="1f525", pos=(560, 330), w=210), zooms=[(704.15, 706.9, ME)])
clip(753.50, 755.90, z=INDIA)  # "You'll meet once or twice and then you get married."
clip(760.10, 765.15, fx(764.3, "tension", 0.45))
clip(767.95, 770.80, fx(770.7, "ding", 0.7), z=INDIA, cap_src="small")
clip(771.40, 772.50, fx(771.5, "ding", 0.6), fx(772.0, "ding", 0.6), fx(771.5, text="NICE. NICE. GREAT. 😏", color="green", dur=1.3), z=ME)
clip(829.45, 831.65)  # "What does a relationship look like for you?"
clip(835.55, 837.55, z=INDIA)  # "I don't have an answer for that."
clip(841.60, 844.60, fx(844.5, ["glitch", "fail"], 0.8, meme="harold", dur=1.5), fx(843.6, emoji="1f480", pos=(560, 330)), zooms=[(843.6, 844.6, ME)])

# ================================================================= GIRL 3: Anna part 1
section("anna1")
clip(910.90, 911.95, fx(910.95, "whoosh", 0.7, text="E-DATE #2", style="banner", dur=1.2))
clip(914.60, 917.35, fx(917.2, "rizz", 0.6), fx(917.25, text="SAME LINE AGAIN 💀", color="yellow", dur=1.5),
     zooms=[(916.2, 917.35, ME)])
clip(918.45, 923.70)
clip(924.30, 926.15, z=ANNA)
clip(933.10, 935.45, fx(935.3, "stun", 0.8, meme="pikachu", dur=1.3), z=ANNA)
clip(1071.05, 1074.05)  # "Let's introduce ourselves. I didn't catch your name."
clip(1076.25, 1083.00, fx(1082.8, "rizz", 0.8), fx(1082.85, emoji="1f60f", pos=(560, 330)), zooms=[(1080.4, 1083.0, ME)])
clip(1083.90, 1087.80, fx(1087.1, "impact", 0.5), fx(1087.3, emoji="26a1", pos=(560, 330), w=200))
clip(1089.00, 1091.60)
clip(1094.45, 1097.30, zooms=[(1096.8, 1097.3, ME)])
clip(1107.55, 1119.00, fx(1109.4, "tension", 0.45), fx(1118.8, ["crowd", "stun"], 0.7, text="SHE SAID KIDS?! 😳", color="pink", dur=1.6),
     zooms=[(1115.8, 1119.0, ANNA)])
clip(1150.10, 1154.45)
clip(1165.45, 1168.90, z=ANNA)
clip(1170.05, 1174.90, fx(1174.8, "rizz", 0.8), zooms=[(1172.0, 1174.9, ME)])
clip(1178.05, 1180.40, fx(1180.3, "impact", 0.6, meme="cheers", dur=1.5))
clip(1191.60, 1195.70, fx(1195.5, "ding", 0.6))
clip(1212.60, 1215.15, z=ANNA)  # "I like to do things that are exhilarating."
clip(1256.65, 1258.60, z=ANNA)
clip(1260.55, 1262.20)
clip(1268.05, 1272.50, zooms=[(1268.05, 1272.5, ME)])
clip(1288.45, 1296.40, fx(1295.7, "rizz", 0.8), fx(1295.8, emoji="2728", pos=(560, 330), w=200))
clip(1304.45, 1306.90, fx(1306.7, "whistle", 0.6), z=ANNA)
clip(1308.60, 1311.10)
clip(1315.65, 1316.85, z=ANNA)
clip(1345.75, 1348.00, z=ANNA)  # "We have the same lights going on."
clip(1350.80, 1354.30)
clip(1354.95, 1356.95, fx(1356.4, "heart", 0.8), z=ANNA)
clip(1358.95, 1361.95, fx(1359.2, "kiss", 0.6, clip="coy", dur=1.7), fx(1359.3, text="SHE CALLED ME BABY 😳", color="pink", dur=1.8), zooms=[(1358.95, 1361.95, ME)])
clip(1369.55, 1371.55)  # "What's your type of a guy?"
clip(1373.30, 1378.55)
clip(1382.10, 1385.50, fx(1385.3, "tension", 0.5), z=ANNA)
clip(1400.45, 1403.30, fx(1403.2, "fail", 0.8, meme="harold", dur=1.6), zooms=[(1400.45, 1403.3, ME)])
freeze(1403.25, 1.8, rel(0.05, "glitch", 0.7, text="WE'RE COMING BACK TO ANNA 👀", style="banner", dur=1.75), z=ANNA)

# ================================================================= GIRL 4: Alejandra
section("ale")
clip(2297.95, 2300.00, fx(2298.0, "whoosh", 0.7, text="E-DATE #3", style="banner", dur=1.2))
clip(2302.40, 2303.30, z=ALE)
clip(2304.30, 2307.40, zooms=[(2305.1, 2307.4, ME)])
clip(2309.15, 2309.75, fx(2309.6, "pop", 0.5), z=ALE)
clip(2324.50, 2325.40)
clip(2327.20, 2330.75, fx(2330.0, "rizz", 0.7), fx(2330.0, emoji="2728", pos=(560, 330), w=200), zooms=[(2329.1, 2330.75, ME)])
clip(2333.45, 2334.20, z=ALE)
clip(2345.55, 2350.55, z=ALE)  # "Oh, you said 25. I have short memory."
clip(2351.60, 2358.20, fx(2357.8, "joke", 0.7))
clip(2361.50, 2362.25, fx(2362.0, "pop", 0.5, emoji="1f602", pos=(1500, 330)), z=ALE, cap_src="small")
clip(2463.35, 2468.00, fx(2467.7, "rizz", 0.7), zooms=[(2466.7, 2468.0, ME)])
clip(2472.50, 2474.60, z=ALE)
clip(2477.80, 2480.65)
clip(2491.30, 2493.00, fx(2492.9, "tension", 0.4), z=ALE, cap_src="small")
clip(2537.70, 2539.72, fx(2539.6, "crowd", 0.5), z=ALE)
clip(2542.10, 2543.60, fx(2543.4, "rizz", 0.7), z=ME, cap_src="small")
clip(2545.40, 2549.85, fx(2549.7, "heart", 0.6))
clip(2675.30, 2677.60)
clip(2680.90, 2683.95, z=ALE)
clip(2685.95, 2688.70, fx(2688.6, ["joke"], 0.7, meme="rollsafe", dur=1.5), zooms=[(2685.95, 2688.7, ME)])
clip(2720.35, 2724.35)  # "Is that part of your personality?"
clip(2729.15, 2731.65, z=ALE)  # "A little bit."
clip(2732.50, 2734.70)
clip(2754.50, 2760.40, fx(2757.7, "impact", 0.6, text="THOR-NS?! ⚡", color="yellow", dur=1.6), z=ALE)
clip(2761.90, 2764.85, zooms=[(2763.6, 2764.85, ME)])
clip(2766.10, 2767.90, fx(2767.8, "rizz", 0.7), z=ALE)
clip(2768.60, 2769.30)
clip(3002.20, 3004.95)  # "You got some trust issues?"
clip(3006.95, 3009.30, z=ALE)  # "Yeah, real bad."
clip(3035.70, 3037.35)
clip(3042.80, 3045.00, z=ALE)
clip(3048.90, 3050.90, fx(3050.7, "tension", 0.4), z=ALE)
clip(3052.00, 3062.45, fx(3062.3, "impact", 0.7, meme="cheers", dur=1.5), fx(3057.5, text="98% 📈", color="green", dur=1.3),
     zooms=[(3056.7, 3062.45, ME)])
clip(3284.70, 3285.45)  # "Do you model?"
clip(3287.15, 3291.00, z=ALE)  # "Hell no. I could, but no."
clip(3291.90, 3293.20)
clip(3295.00, 3296.90, fx(3296.7, "rizz", 0.8, text="W", color="green", dur=1.2), z=ALE)
clip(3432.00, 3433.70, z=ALE)
clip(3438.40, 3439.70, zooms=[(3438.4, 3439.7, ME)])
clip(3441.80, 3445.55, fx(3445.4, "rizz", 0.6), zooms=[(3444.2, 3445.55, ME)])
clip(3447.20, 3450.70, z=ALE)
clip(3451.90, 3453.10, fx(3453.0, ["impact", "crowd"], 0.8, meme="cinema", dur=1.5), z=ME)

# ================================================================= GIRL 3: Anna part 2 (finale)
section("anna2")
clip(1433.30, 1434.30, z=ANNA)  # "Are you ready for this?"
clip(1437.95, 1439.20, fx(1438.0, "whoosh", 0.7, text="BACK TO ANNA 👀", style="banner", dur=1.3))
clip(1443.45, 1447.10, z=ANNA)
clip(1447.15, 1449.00, zooms=[(1447.15, 1449.0, ME)])
clip(1450.90, 1451.60, fx(1451.5, "joke", 0.7, emoji="1f602", pos=(1500, 330)))
clip(1481.10, 1485.75, z=ANNA)  # "Something I'm scared to do with the love of my life."
clip(1487.70, 1496.40, fx(1496.2, ["rizz", "crowd"], 0.8), fx(1496.3, meme="cheers", dur=1.4), zooms=[(1493.8, 1496.4, ME)], cap_src="small")
clip(1537.40, 1541.00, fx(1540.9, "whistle", 0.6))
clip(1544.45, 1547.00, z=ANNA)
clip(1549.05, 1550.05, z=ME)
clip(1557.40, 1562.10, fx(1561.95, "fail", 0.8, meme="monkeypuppet", dur=1.5))
clip(1644.80, 1654.35, fx(1654.2, "glitch", 0.8), zooms=[(1649.0, 1654.35, ME)])
freeze(1654.30, 1.1, rel(0.0, "glitch", 0.7, text="WAIT... 🤨", style="banner", dur=1.05), z=ME)
clip(2412.10, 2418.35, fx(2412.15, text="SAME LINE ON ALEJANDRA 💀", style="banner", dur=2.2),
     fx(2418.2, "fail", 0.8, meme="skeptical", dur=1.6), zooms=[(2416.2, 2418.35, ME)])
clip(1692.50, 1694.45)  # "You've got to type your Instagram in the chat."
clip(1698.05, 1699.90, fx(1698.1, "whoosh", 0.6), z=ANNA)
clip(1701.25, 1704.20)
clip(1707.80, 1712.60, z=ANNA)
clip(1718.35, 1720.60, zooms=[(1718.35, 1720.6, ME)])
clip(1722.20, 1725.70, z=ANNA)
clip(1739.00, 1742.50, fx(1742.35, ["impact", "stun"], 0.9, text="EMOTIONAL DAMAGE 💀", color="red", dur=1.6), z=ANNA)
clip(1821.30, 1823.00, z=ANNA)  # "Is your name really Thor?"
clip(1831.65, 1832.30)  # "Yeah, it's my name."
clip(1838.80, 1842.90, fx(1842.6, "rizz", 0.8), fx(1842.7, emoji="26a1", pos=(560, 330), w=200), zooms=[(1840.5, 1842.9, ME)])
clip(2028.00, 2030.30)
clip(2035.85, 2037.50, fx(2037.3, "kiss", 0.7))
clip(2042.85, 2043.90, fx(2043.8, "pop", 0.5), z=ANNA)
clip(2113.40, 2114.60)
clip(2115.90, 2116.80, z=ANNA, cap_src="small")
clip(2120.50, 2121.90, fx(2121.75, "heart", 0.8), fx(2121.8, emoji="1f633", pos=(560, 330), w=200), zooms=[(2120.5, 2121.9, ME)])
clip(2144.10, 2150.10, fx(2149.95, ["crowd"], 0.6), fx(2150.0, emoji="1f975", pos=(560, 330), rot=-10), zooms=[(2147.3, 2150.1, ME)])
clip(2152.05, 2155.50, fx(2155.3, "whistle", 0.6), z=ANNA)
clip(2156.65, 2158.00)
clip(2162.25, 2164.15)  # "I'm just making you want to rap or something."
clip(2165.85, 2166.70, z=ANNA)  # "No, I don't rap."
clip(2167.85, 2169.35, fx(2169.2, "tension", 0.5), z=ME)
clip(2170.90, 2171.40, fx(2171.3, "stun", 0.8, meme="pikachu", dur=1.2), z=ANNA)
clip(2173.95, 2176.00, z=ANNA)
clip(2178.20, 2180.10)
clip(2182.00, 2183.85, z=ANNA)
clip(2185.80, 2187.05, fx(2185.9, "tension", 0.6), z=ANNA)
clip(2188.30, 2189.30, fx(2188.4, ["impact", "crowd"], 0.9), fx(2188.7, emoji="26a1", pos=(1500, 300), w=230), z=ME)
freeze(2189.25, 1.3, rel(0.1, meme="cinema", dur=1.2), z=ME)
clip(2190.85, 2193.55, fx(2193.4, "rizz", 0.7))
freeze(2193.50, 2.8, rel(0.1, "ding", 0.7, text="SUBSCRIBE FOR PART 2 ⚡", style="banner", dur=2.6), rel(0.05, "rizz_2999", 0.6))
section("end")

# ---------------------------------------------------------------- Jameer-style cutaways
# Full-screen reaction clips with their own audio, cut in right after the line (the call pauses), about
# one every 30-40s, plus a TV color-bar glitch at every call change. Library: memeclips/ (from the
# user's own published edit), see memeclips/library.json. (source time of the moment, clip, [start, end])
CUTAWAYS = [
    (292.9, "khaled_you_smart", None), (421.9, "athlete_facepalm", None), (457.1, "kid_reaction", None),
    (844.5, "face_in_hands", None), (1118.8, "idris_laugh", None), (1180.3, "suit_thats_it", None),
    (1403.2, "doctor_youre_dying", None), (1496.3, "el_risitas_laugh", None), (1561.9, "goofy_face", None),
    (1742.35, "chicago_cap_guy", None), (2418.2, "law_and_order", None), (2688.6, "studio_laugh", (0.45, 1.14)),
    # v5: higher frequency (user: "use a higher frequency of funny gif esque clips")
    (240.6, "denzel_my_man", None), (255.75, "steve_harvey_shocked", None), (638.55, "michael_scott_no", None),
    (676.1, "lying_down", None), (706.9, "dicaprio_laugh", None), (772.5, "suit_thats_it", None),
    (917.35, "kevin_hart_stare", None), (935.45, "red_hoodie", (0.5, 2.5)), (1712.6, "athlete_facepalm", None),
    (2155.5, "lying_down", None), (2171.4, "kevin_hart_stare", None), (2493.0, "why_are_you_running", None),
    (2539.72, "steve_harvey_shocked", None), (2769.3, "denzel_my_man", None), (3062.45, "khaled_you_smart", None),
    (3296.9, "kid_reaction", None), (3453.1, "imma_head_out", (2.5, 4.5)),
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
for name, idx in sections:
    if idx >= len(pieces):
        new_sections.append((name, len(out_pieces)))
used = {c for _, c, _ in CUTAWAYS}
assert sum(1 for p in out_pieces if p["type"] == "cut" and p["clip"] != "tv_glitch") == len(CUTAWAYS), "a cutaway moment matched no clip"
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

tracks = {"india": "music/greenchair.mp3", "anna1": "music/sensual.mp3", "ale": "music/babe.mp3", "anna2": "music/rnb.mp3"}
music = [{"file": "music/breezy.mp3", "start": 0.0, "end": bounds["cold"][1], "vol": 0.08}]
music += [{"file": f, "start": bounds[n][0], "end": bounds[n][1], "vol": 0.08} for n, f in tracks.items()]
# end card has no speech to duck under, so the music swells up to carry it out
outro = starts[-1]
music[-1]["end"] = outro + 0.6
music.append({"file": "music/rnb.mp3", "start": outro, "end": total, "vol": 0.35})


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
    o = out_at(src)
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
    "name": "monkey_longform_v10",
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
