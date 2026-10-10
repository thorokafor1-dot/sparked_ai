"""Zero-cost concept mocks for video-chat title ideas: no image generation. Reuses
AI women already generated (work/real_*.png, work/screen_*.png ...) and the creator's
reference photos, then draws each idea's mechanic (bingo card, scorecard, VS split,
skip spinner, move tags, comment fix, name guess, mask) with PIL.

Usage:
    python mock_videochat_thumbs.py --spec mocks.json --out output/mocks
spec = list of {"slug", "woman" (a path, or "pool:<look>" / "pool:any"), "me", "grade": "amber|teal|red|sunset|none",
                "bubble", "emoji", "widgets": [{"type": ..., ...}]}
Mock text is placeholder: finals take real lines from the transcript.
"""
import argparse
import json
import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

from compose_videochat_thumb import EMOJI, FONT, H, W, badge, bubble, cover, emoji, find_face, pop

GRADES = {"amber": (255, 150, 40), "teal": (0, 170, 190), "red": (230, 30, 50), "sunset": (255, 90, 60)}
LW = W // 2


def font(size):
    return ImageFont.truetype(FONT, size)


def grade(img, name, k=0.16):
    return img if name in (None, "none") else Image.blend(img, Image.new("RGB", img.size, GRADES[name]), k)


def label(d, xy, text, size=64, fill="white", bg=(0, 0, 0), anchor="mm", pad=18):
    f = font(size)
    l, t, r, b = d.textbbox(xy, text, font=f, anchor=anchor)
    d.rounded_rectangle((l - pad, t - pad * 0.6, r + pad, b + pad * 0.6), radius=14, fill=bg)
    d.text(xy, text, font=f, fill=fill, anchor=anchor)


def arrow(d, p0, p1, color=(230, 30, 40), width=22):
    """Curved arrow p0 -> p1 with a triangular head."""
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2 - abs(p1[0] - p0[0]) * 0.35
    pts = [((1 - t) ** 2 * p0[0] + 2 * (1 - t) * t * mx + t * t * p1[0],
            (1 - t) ** 2 * p0[1] + 2 * (1 - t) * t * my + t * t * p1[1]) for t in [i / 30 for i in range(31)]]
    d.line(pts[:-3], fill="white", width=width + 10, joint="curve")
    d.line(pts[:-3], fill=color, width=width, joint="curve")
    a = math.atan2(p1[1] - pts[-4][1], p1[0] - pts[-4][0])
    s = width * 2.4
    head = [p1, (p1[0] - s * math.cos(a - 0.5), p1[1] - s * math.sin(a - 0.5)),
            (p1[0] - s * math.cos(a + 0.5), p1[1] - s * math.sin(a + 0.5))]
    d.polygon(head, fill=color, outline="white")


def w_bingo(c, d, wd):
    n, cell, x0, y0 = 3, 118, W // 2 - 177, 110
    d.rounded_rectangle((x0 - 16, y0 - 70, x0 + n * cell + 16, y0 + n * cell + 16), radius=18, fill="white", outline="black", width=6)
    d.text((W // 2, y0 - 36), "FLIRT BINGO", font=font(44), fill="black", anchor="mm")
    ticks = set(wd.get("ticks", [0, 1, 2, 4, 5, 6, 8]))
    for i in range(n * n):
        x, y = x0 + (i % n) * cell, y0 + (i // n) * cell
        d.rectangle((x + 4, y + 4, x + cell - 4, y + cell - 4), outline="black", width=4)
        if i in ticks:
            d.line([(x + 26, y + 62), (x + 52, y + 90), (x + 96, y + 30)], fill=(20, 170, 60), width=16)
    label(d, (LW + 230, H - 90), wd.get("timer", "02:14.45"), size=90, fill=(60, 255, 110), bg=(0, 0, 0))


def w_before_after(c, d, wd, friend_box=(LW, H // 2, W, H)):
    d.rectangle(friend_box, fill=(70, 70, 78))
    d.text(((friend_box[0] + friend_box[2]) / 2, (friend_box[1] + friend_box[3]) / 2), "[FRIEND]", font=font(70), fill=(170, 170, 180), anchor="mm")
    d.rectangle((LW, H // 2 - 4, W, H // 2 + 4), fill="white")
    label(d, (W - 190, 70), "BEFORE ?/10", size=48, bg=(200, 30, 40))
    label(d, (W - 190, H // 2 + 70), "AFTER ?/10", size=48, bg=(20, 150, 60))


def w_vs(c, d, wd, me_b=None):
    if me_b is not None:
        half = me_b.crop((0, 0, LW // 2, H))
        c.paste(half, (LW, 0))
        c.paste(me_b.crop((LW // 2, 0, LW, H)).transpose(Image.FLIP_LEFT_RIGHT), (LW + LW // 2, 0))
        d.rectangle((LW + LW // 2 - 3, 0, LW + LW // 2 + 3, H), fill="white")
    label(d, (LW + LW // 4, H - 80), wd.get("a", "BEARD"), size=60, bg=(0, 0, 0))
    label(d, (LW + 3 * LW // 4, H - 80), wd.get("b", "CLEAN"), size=60, bg=(0, 0, 0))
    d.text((LW + LW // 2, H // 2 + 120), "VS", font=font(150), fill=(255, 214, 0), anchor="mm", stroke_width=12, stroke_fill="black")


def w_scorecard(c, d, wd):
    x, y = wd.get("xy", (120, 560))
    d.rounded_rectangle((x, y, x + 300, y + 230), radius=20, fill="white", outline="black", width=8)
    d.text((x + 150, y + 60), "HIS FLIRTING", font=font(34), fill="black", anchor="mm")
    d.text((x + 150, y + 150), wd.get("score", "?/10"), font=font(110), fill=(220, 30, 40), anchor="mm")


def w_skip(c, d, wd):
    region = c.crop((LW, 0, W, H)).convert("L").convert("RGB")
    c.paste(Image.blend(region, Image.new("RGB", region.size, (0, 0, 0)), 0.35), (LW, 0))
    cx, cy, r = LW + LW // 2, 300, 90
    for i in range(12):
        a = i / 12 * 2 * math.pi
        x, y = cx + r * math.cos(a), cy + r * math.sin(a)
        d.ellipse((x - 18, y - 18, x + 18, y + 18), fill=(255, 255, 255, 60 + i * 16))
    label(d, (cx, 470), "SKIPPED...", size=64, bg=(0, 0, 0))
    arrow(d, (LW + 120, H - 140), (LW + LW - 140, H - 180))
    label(d, (cx, H - 70), "...THEN CAME BACK", size=52, bg=(200, 30, 40))


def w_tags(c, d, wd):
    for t in wd["tags"]:
        label(d, tuple(t["xy"]), t["text"], size=50, fill="black", bg=(255, 214, 0))


def w_comment(c, d, wd):
    x0, y0, w = LW - 430, 40, 860
    d.rounded_rectangle((x0, y0, x0 + w, y0 + 250), radius=22, fill="white", outline="black", width=6)
    d.ellipse((x0 + 24, y0 + 24, x0 + 84, y0 + 84), fill=(150, 150, 160))
    d.text((x0 + 100, y0 + 34), "@viewer", font=font(32), fill=(90, 90, 90))
    t = wd.get("bad", "\"Are you a parking ticket...\"")
    d.text((x0 + 30, y0 + 140), t, font=font(54), fill="black", anchor="lm")
    tw = d.textlength(t, font=font(54))
    d.line([(x0 + 24, y0 + 140), (x0 + 36 + tw, y0 + 140)], fill=(220, 30, 40), width=10)
    label(d, (x0 + w - 120, y0 + 215), "FIXED", size=50, bg=(20, 150, 60))


def w_buttons(c, d, wd):
    """Dating-app verdict row (Kalogeras speed-date thumbnails)."""
    for cx, col, sym in ((LW // 2 - 130, (235, 60, 70), "x"), (LW // 2 + 130, (255, 70, 120), "heart")):
        cy, r = H - 130, 85
        d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=col, outline="white", width=10)
        if sym == "x":
            d.line([(cx - 35, cy - 35), (cx + 35, cy + 35)], fill="white", width=20)
            d.line([(cx - 35, cy + 35), (cx + 35, cy - 35)], fill="white", width=20)
        else:
            d.ellipse((cx - 42, cy - 34, cx + 2, cy + 8), fill="white")
            d.ellipse((cx - 2, cy - 34, cx + 42, cy + 8), fill="white")
            d.polygon([(cx - 40, cy - 6), (cx + 40, cy - 6), (cx, cy + 44)], fill="white")


def w_mask(c, d, me_box, wd):
    fx, fy, fw, fh = me_box
    x0, y0, x1, y1 = LW + fx - fw * 0.25, fy - fh * 0.35, LW + fx + fw * 1.25, fy + fh * 1.25
    reg = c.crop((int(x0), int(y0), int(x1), int(y1))).filter(ImageFilter.GaussianBlur(28))
    reg = Image.blend(reg.convert("RGB"), Image.new("RGB", reg.size, (200, 20, 30)), 0.75)
    m = Image.new("L", reg.size, 0)
    ImageDraw.Draw(m).ellipse((0, 0, reg.width, reg.height), fill=255)
    c.paste(reg, (int(x0), int(y0)), m)
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    for i in range(10):
        a = i / 10 * 2 * math.pi
        d.line([(cx, cy), (cx + (x1 - x0) / 2 * math.cos(a), cy + (y1 - y0) / 2 * math.sin(a))], fill="black", width=4)
    for k in (0.3, 0.55, 0.8):
        d.ellipse((cx - (x1 - x0) / 2 * k, cy - (y1 - y0) / 2 * k, cx + (x1 - x0) / 2 * k, cy + (y1 - y0) / 2 * k), outline="black", width=4)
    for ex in (-1, 1):  # Spider-Man eye lenses
        ecx, ecy = cx + ex * (x1 - x0) * 0.17, cy - (y1 - y0) * 0.08
        d.polygon([(ecx - ex * 70, ecy - 20), (ecx + ex * 50, ecy - 55), (ecx + ex * 60, ecy + 35)], fill="white", outline="black", width=8)
    if wd.get("text", "MASK ON. WORDS ONLY."):
        label(d, (LW + LW // 2, H - 80), wd.get("text", "MASK ON. WORDS ONLY."), size=56, bg=(200, 20, 30))


POOL_INDEX = Path(__file__).resolve().parent / "reference" / "women_pool" / "index.json"


def resolve_woman(spec, root, final, taken):
    """'pool:<look>' / 'pool:any' picks the least-used pool woman of that archetype (never one
    already used in this run). Pinterest pins are mock_only and refused when --final."""
    w = spec["woman"]
    index = json.loads(POOL_INDEX.read_text(encoding="utf-8")) if POOL_INDEX.exists() else []
    if w.startswith("pool:"):
        look = w[5:]
        cands = [e for e in index if (look == "any" or e.get("look") == look) and e["file"] not in taken
                 and not (final and e.get("mock_only"))]
        if not cands:
            raise SystemExit(f"{spec['slug']}: no unused pool woman for '{look}' (final={final})")
        pick = min(cands, key=lambda e: len(e.get("used_in", [])))
        pick.setdefault("used_in", []).append(spec["slug"])
        POOL_INDEX.write_text(json.dumps(index, indent=1), encoding="utf-8")
        w = pick["file"]
    elif final and any(e["file"] == w and e.get("mock_only") for e in index):
        raise SystemExit(f"{spec['slug']}: {w} is mock-only (a real stranger), never use it in a final")
    if final and "women_pool/pins" in w.replace("\\", "/"):
        raise SystemExit(f"{spec['slug']}: pinned photos are mock-only")
    taken.add(w)
    return w


VISUAL_ONLY = {"mask", "buttons"}  # widgets that carry no words


def render(spec, root, out, final=False, taken=None, notext=False):
    spec = {**spec, "woman": resolve_woman(spec, root, final, taken if taken is not None else set())}
    if notext:  # same frame with every word stripped: the picture alone has to tell the story
        spec = {**spec, "bubble": "", "slug": spec["slug"] + "_notext",
                "widgets": [{**w, "text": ""} for w in spec.get("widgets", []) if w["type"] in VISUAL_ONLY]}
    woman = pop(grade(cover(Image.open(root / spec["woman"]).convert("RGB"), LW, H, *spec.get("woman_focus", (0.5, 0.4))), spec.get("woman_grade", "none"), 0.12))
    me_src = Image.open(root / spec["me"]).convert("RGB")
    if spec.get("me_flip", True):
        me_src = me_src.transpose(Image.FLIP_LEFT_RIGHT)
    me = pop(grade(cover(me_src, W - LW, H, *spec.get("me_focus", (0.5, 0.45))), spec.get("grade", "none")))
    c = Image.new("RGBA", (W, H))
    c.paste(woman, (0, 0))
    c.paste(me, (LW, 0))
    d = ImageDraw.Draw(c)
    d.rectangle((LW - 4, 0, LW + 4, H), fill="white")
    me_face = find_face(me)
    for wd in spec.get("widgets", []):
        t = wd["type"]
        if t == "vs":
            w_vs(c, d, wd, me)
        elif t == "mask":
            if me_face:
                w_mask(c, d, me_face, wd)
        else:
            {"buttons": w_buttons, "bingo": w_bingo, "before_after": w_before_after, "scorecard": w_scorecard,
             "skip": w_skip, "tags": w_tags, "comment": w_comment}[t](c, d, wd)
    if spec.get("bubble"):
        bubble(c, spec["bubble"], 70, LW, find_face(woman))
    if spec.get("emoji"):
        emoji(c, spec["emoji"], 170, LW, W - LW, me_face)
    if spec.get("badge", not any(w["type"] == "buttons" for w in spec.get("widgets", []))):
        badge(c, 36, H - 36 - 130, 130)
    f = out / f"mock_{spec['slug']}.jpg"
    c.convert("RGB").save(f, quality=90)
    return f


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--spec", required=True)
    ap.add_argument("--out", default="output/mocks")
    ap.add_argument("--final", action="store_true", help="refuse mock-only (pinned) women")
    ap.add_argument("--notext", action="store_true", help="also render a no-text variant of every mock")
    a = ap.parse_args()
    root, out = Path(__file__).resolve().parent, Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    taken = set()
    specs = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    files = [render(s, root, out, a.final, taken) for s in specs]
    if a.notext:
        for s in specs:
            render(s, root, out, a.final, set(), notext=True)
    tw, th = 640, 360
    grid = Image.new("RGB", (tw * 2, th * ((len(files) + 1) // 2)), "black")
    for i, f in enumerate(files):
        grid.paste(Image.open(f).resize((tw, th)), ((i % 2) * tw, (i // 2) * th))
    grid.save(out / "mocks_grid.jpg", quality=88)
    print("\n".join(map(str, files)) + f"\n{out / 'mocks_grid.jpg'}")


if __name__ == "__main__":
    main()
