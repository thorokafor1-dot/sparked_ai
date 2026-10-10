"""Compose a Monkey App / video-chat compilation thumbnail in the channel's
classic split layout: woman panel on the left, creator panel on the right,
thin white divider, white speech bubble by her head, Monkey badge bottom-left.

Usage:
    python compose_videochat_thumb.py --woman work/woman_selfie.png \
        --me "reference/self/videochat/2025-11-05_Photo for monkey thumbnail 5.JPG" \
        --bubble "YOU'RE TROUBLE" --out output/videochat_draft1.jpg

--woman-focus / --me-focus are "x,y" fractions of the source to centre the crop on.
--emoji puts one emoji in the top corner of his panel that clears his face, --headline
puts 1-3 words (yellow, black stroke) along the bottom of his panel, --no-badge drops
the app badge, --his-line puts his quoted line (white, black stroke) low on his panel so
the thumbnail reads as his line -> her reaction (bubble). Strategy and when to use
each: videochat_thumbnail_strategy.md.
"""
import argparse
from pathlib import Path

from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

W, H = 1920, 1080
SPLIT = 0.5
FONT = "C:/Windows/Fonts/ariblk.ttf"
EMOJI = "C:/Windows/Fonts/seguiemj.ttf"


def cover(img: Image.Image, w: int, h: int, fx: float, fy: float) -> Image.Image:
    s = max(w / img.width, h / img.height)
    img = img.resize((round(img.width * s), round(img.height * s)), Image.LANCZOS)
    left = min(max(round(img.width * fx - w / 2), 0), img.width - w)
    top = min(max(round(img.height * fy - h / 2), 0), img.height - h)
    return img.crop((left, top, left + w, top + h))


def pop(img: Image.Image) -> Image.Image:
    img = ImageEnhance.Contrast(img).enhance(1.08)
    img = ImageEnhance.Color(img).enhance(1.12)
    return img.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=2))


def find_face(img: Image.Image):
    """Largest face as (x, y, w, h) in img coords, or None."""
    import cv2
    import numpy as np
    g = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
    det = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = det.detectMultiScale(g, 1.1, 6, minSize=(img.width // 6, img.width // 6))
    return tuple(int(v) for v in max(faces, key=lambda f: f[2] * f[3])) if len(faces) else None


def bubble(canvas: Image.Image, text: str, size: int, panel_w: int, face) -> None:
    """Speech bubble beside her head with the tail aimed at her mouth.
    '|' in text forces a line break; otherwise long text wraps to two lines."""
    d = ImageDraw.Draw(canvas)
    font = ImageFont.truetype(FONT, size)
    words = text.split()
    if "|" in text:
        lines = [l.strip() for l in text.split("|")]
    elif len(words) > 1 and d.textlength(text, font=font) > panel_w * 0.38:
        k = len(words) // 2 + len(words) % 2
        lines = [" ".join(words[:k]), " ".join(words[k:])]
    else:
        lines = [text]
    lh = int(size * 1.05)
    tw = int(max(d.textlength(l, font=font) for l in lines))
    pad_x, pad_y, b = int(size * 0.42), int(size * 0.32), max(6, size // 12)
    bw, bh = tw + 2 * pad_x, lh * len(lines) + 2 * pad_y
    m = 28
    if face:
        fx, fy, fw, fh = face
        mouth = (fx + fw * 0.5, fy + fh * 0.8)
        keep = (fx - fw * 0.15, fy - fh * 0.3, fx + fw * 1.15, fy + fh * 1.1)  # face + hair margin
    else:
        mouth, keep = (W * 0.25, H * 0.5), (0, 0, 0, 0)

    def overlap(bx0, by0):
        ox = max(0, min(bx0 + bw, keep[2]) - max(bx0, keep[0]))
        oy = max(0, min(by0 + bh, keep[3]) - max(by0, keep[1]))
        return ox * oy

    # top corner (right first: she's looking/talking toward him) that clears her face
    x, y = min([(panel_w - m - bw, m), (m, m)], key=lambda c: overlap(*c))
    box = (x, y, x + bw, y + bh)
    # tail: base on the bottom edge nearest her mouth, tip walks toward the
    # mouth and stops just before entering the face area
    bx = min(max(mouth[0] - size * 0.3, box[0] + pad_x * 0.5), box[2] - pad_x * 0.5 - size * 0.6)
    by = box[3]
    cx, cy = bx + size * 0.3, by
    tip = (cx, cy + size * 0.8)
    for t in [i / 40 for i in range(1, 41)]:
        px, py = cx + (mouth[0] - cx) * t, cy + (mouth[1] - cy) * t
        if keep[0] < px < keep[2] and keep[1] < py < keep[3]:
            break
        tip = (px, py)
    d_tip = ((tip[0] - cx) ** 2 + (tip[1] - cy) ** 2) ** 0.5
    if d_tip > size * 1.4:  # no face found: a short tail, not one stretched down the frame
        tip = (cx + (tip[0] - cx) * size * 1.4 / d_tip, cy + (tip[1] - cy) * size * 1.4 / d_tip)
    if ((tip[0] - cx) ** 2 + (tip[1] - cy) ** 2) ** 0.5 < size * 0.7:
        tip = (cx + (mouth[0] - cx) * 0.2, cy + size * 0.8)
    tail = [(bx, by - 2), (bx + size * 0.6, by - 2), tip]

    mask = Image.new("L", canvas.size, 0)
    md = ImageDraw.Draw(mask)
    md.rectangle(box, fill=255)
    md.polygon(tail, fill=255)
    outline = mask.filter(ImageFilter.MaxFilter(2 * b + 1))
    shadow = outline.transform(canvas.size, Image.AFFINE, (1, 0, -b * 2, 0, 1, -b * 2)).filter(ImageFilter.GaussianBlur(b))
    canvas.paste((0, 0, 0, 255), (0, 0), shadow.point(lambda v: v * 0.45))
    canvas.paste((0, 0, 0, 255), (0, 0), outline)
    canvas.paste((255, 255, 255, 255), (0, 0), mask)
    for i, l in enumerate(lines):
        d.text((box[0] + bw / 2, box[1] + pad_y + lh * i + lh / 2), l, font=font, fill="black", anchor="mm")


def badge(canvas: Image.Image, x: int, y: int, s: int) -> None:
    d = ImageDraw.Draw(canvas)
    d.rounded_rectangle((x, y, x + s, y + s), radius=s // 6, fill=(132, 76, 255), outline="white", width=max(3, s // 25))
    try:
        f = ImageFont.truetype(EMOJI, int(s * 0.62))
        d.text((x + s / 2, y + s / 2), "\U0001F435", font=f, embedded_color=True, anchor="mm")
    except OSError:
        pass


def emoji(canvas: Image.Image, ch: str, size: int, x0: int, panel_w: int, face) -> None:
    """One emoji in the top corner of the panel at x0 that overlaps the face least."""
    m = 40
    keep = (face[0] + x0, face[1], face[0] + x0 + face[2], face[1] + face[3]) if face else (0, 0, 0, 0)
    def overlap(x, y):
        return max(0, min(x + size, keep[2]) - max(x, keep[0])) * max(0, min(y + size, keep[3]) - max(y, keep[1]))
    x, y = min([(x0 + panel_w - m - size, m), (x0 + m, m)], key=lambda c: overlap(*c))
    layer = Image.new("RGBA", (size * 2, size * 2), (0, 0, 0, 0))
    ImageDraw.Draw(layer).text((size, size), ch, font=ImageFont.truetype(EMOJI, 109), embedded_color=True, anchor="mm")
    layer = layer.crop(layer.getbbox()).resize((size, size), Image.LANCZOS)
    canvas.alpha_composite(layer, (x, y))


def headline(canvas: Image.Image, text: str, x0: int, panel_w: int) -> None:
    """1-3 word headline, centred along the bottom of the panel at x0."""
    d = ImageDraw.Draw(canvas)
    size = 150
    font = ImageFont.truetype(FONT, size)
    while d.textlength(text, font=font) > panel_w * 0.88 and size > 60:
        size -= 6
        font = ImageFont.truetype(FONT, size)
    d.text((x0 + panel_w / 2, H - 50), text, font=font, fill=(255, 214, 0), anchor="mb",
           stroke_width=max(6, size // 12), stroke_fill="black")


def his_line(canvas: Image.Image, text: str, x0: int, panel_w: int) -> None:
    """His quoted line, centred low on his panel (the cause; her bubble is the effect)."""
    d = ImageDraw.Draw(canvas)
    text = f"“{text}”"
    size = 110
    font = ImageFont.truetype(FONT, size)
    while d.textlength(text, font=font) > panel_w * 0.86 and size > 50:
        size -= 6
        font = ImageFont.truetype(FONT, size)
    d.text((x0 + panel_w / 2, H - 60), text, font=font, fill="white", anchor="mb",
           stroke_width=max(6, size // 11), stroke_fill="black")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--woman", required=True)
    ap.add_argument("--me", required=True)
    ap.add_argument("--bubble", default="")
    ap.add_argument("--bubble-size", type=int, default=74)
    ap.add_argument("--woman-focus", default="0.5,0.4")
    ap.add_argument("--me-focus", default="0.55,0.45")
    ap.add_argument("--me-zoom", type=float, default=1.0, help=">1 crops tighter on the creator")
    ap.add_argument("--woman-flip", action="store_true",
                    help="mirror her so her gaze points across the divider at him")
    ap.add_argument("--me-flip", action="store_true",
                    help="mirror the creator horizontally so he faces her panel (user, 2026-10-07)")
    ap.add_argument("--emoji", default="", help="one emoji on his panel, e.g. a heart-eyes face")
    ap.add_argument("--emoji-size", type=int, default=190)
    ap.add_argument("--headline", default="", help="1-3 words along the bottom of his panel")
    ap.add_argument("--his-line", default="", help="his real line (1-4 words), quoted low on his panel")
    ap.add_argument("--no-badge", action="store_true", help="drop the app badge")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    if a.headline and a.his_line:
        ap.error("--headline and --his-line share the bottom of his panel, use one")

    lw = int(W * SPLIT)
    wf = [float(v) for v in a.woman_focus.split(",")]
    mf = [float(v) for v in a.me_focus.split(",")]
    woman_src = Image.open(a.woman).convert("RGB")
    if a.woman_flip:
        woman_src = woman_src.transpose(Image.FLIP_LEFT_RIGHT)
        wf[0] = 1 - wf[0]
    woman = pop(cover(woman_src, lw, H, *wf))
    me_src = Image.open(a.me).convert("RGB")
    if a.me_flip:   # mirror, and mirror the focus point with it
        me_src = me_src.transpose(Image.FLIP_LEFT_RIGHT)
        mf[0] = 1 - mf[0]
    if a.me_zoom > 1:
        cw, ch = me_src.width / a.me_zoom, me_src.height / a.me_zoom
        cx, cy = me_src.width * mf[0], me_src.height * mf[1]
        l, t = max(0, min(cx - cw / 2, me_src.width - cw)), max(0, min(cy - ch / 2, me_src.height - ch))
        me_src = me_src.crop((int(l), int(t), int(l + cw), int(t + ch)))
        mf = [0.5, 0.5]
    me = pop(cover(me_src, W - lw, H, *mf))

    canvas = Image.new("RGBA", (W, H))
    canvas.paste(woman, (0, 0))
    canvas.paste(me, (lw, 0))
    ImageDraw.Draw(canvas).rectangle((lw - 4, 0, lw + 4, H), fill="white")
    if a.bubble:
        bubble(canvas, a.bubble, a.bubble_size, lw, find_face(woman))
    if a.emoji:
        emoji(canvas, a.emoji, a.emoji_size, lw, W - lw, find_face(me))
    if a.headline:
        headline(canvas, a.headline, lw, W - lw)
    if a.his_line:
        his_line(canvas, a.his_line, lw, W - lw)
    if not a.no_badge:
        badge(canvas, 36, H - 36 - 150, 150)

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    canvas.convert("RGB").save(out, quality=90)
    print(f"saved {out}")


if __name__ == "__main__":
    main()
