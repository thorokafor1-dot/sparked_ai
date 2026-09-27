"""Sparked-branded overlay graphics (title cards, number badges, CTA panel, endscreen).

Theme pulled from landing-page/styles.css: ember background (#0f0705 -> #4a120a),
gold -> amber -> ember gradient, Playfair Display headlines, Space Grotesk body,
letter-spaced JetBrains Mono labels, the glowing bolt logo.

Usage:
    python brand_graphics.py
Writes PNGs to work/brand/. render.py overlays them.
"""

import math
import random
from pathlib import Path

from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

from edl import EDL, QR_PNG

HERE = Path(__file__).parent
REPO = HERE.parent.parent
FONT_DIR = HERE / "work" / "fonts"
OUT = HERE / "work" / "brand"
LOGO = REPO / "landing-page" / "assets" / "logo-256.png"
ENDSCREEN = HERE / "input" / "endscreen.png"

W, H = 1920, 1080
BG, BG_DEEP = (15, 7, 5), (74, 18, 10)
TEXT, TEXT_DIM = (246, 236, 227), (199, 171, 156)
GOLD, AMBER, EMBER = (255, 216, 115), (255, 157, 61), (255, 90, 31)

# static instances cut from the variable brand fonts: (source, output, weight)
STATIC = [
    ("PlayfairDisplay.ttf", "playfair_800.ttf", 800),
    ("PlayfairDisplay-Italic.ttf", "playfair_italic_600.ttf", 600),
    ("SpaceGrotesk.ttf", "grotesk_600.ttf", 600),
    ("SpaceGrotesk.ttf", "grotesk_500.ttf", 500),
    ("JetBrainsMono.ttf", "mono_500.ttf", 500),
]


def make_static_fonts() -> None:
    for src, out, weight in STATIC:
        if not (FONT_DIR / out).exists():
            font = instantiateVariableFont(TTFont(FONT_DIR / src), {"wght": weight})
            font.save(FONT_DIR / out)


def font(name: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(str(FONT_DIR / name), size)


def gradient(size: tuple[int, int]) -> Image.Image:
    """The landing page's 120deg gold -> amber -> ember gradient."""
    w, h = size
    grad = Image.new("RGB", size)
    px = grad.load()
    for x in range(w):
        for y in range(0, h, 4):
            t = min(max((x / w) * 0.85 + (y / h) * 0.15, 0), 1)
            a, b, u = (GOLD, AMBER, t / 0.55) if t < 0.55 else (AMBER, EMBER, (t - 0.55) / 0.45)
            c = tuple(int(a[i] + (b[i] - a[i]) * u) for i in range(3))
            for dy in range(4):
                if y + dy < h:
                    px[x, y + dy] = c
    return grad


def gradient_text(text: str, fnt, glow: int = 28) -> Image.Image:
    box = fnt.getbbox(text)
    w, h = box[2] - box[0] + glow * 4, box[3] - box[1] + glow * 4
    mask = Image.new("L", (w, h))
    ImageDraw.Draw(mask).text((glow * 2 - box[0], glow * 2 - box[1]), text, font=fnt, fill=255)
    fill = gradient((w, h))
    out = Image.new("RGBA", (w, h))
    halo = Image.new("RGBA", (w, h), AMBER + (0,))
    halo.putalpha(mask.filter(ImageFilter.GaussianBlur(glow)).point(lambda v: int(v * 0.55)))
    out.alpha_composite(halo)
    fill.putalpha(mask)
    out.alpha_composite(fill.convert("RGBA"))
    return out


def spaced(draw, xy, text, fnt, fill, spacing, anchor_center=True):
    """Letter-spaced text (the landing page's mono labels use 0.18em)."""
    widths = [fnt.getlength(ch) for ch in text]
    total = sum(widths) + spacing * (len(text) - 1)
    x, y = xy
    if anchor_center:
        x -= total / 2
    for ch, cw in zip(text, widths):
        draw.text((x, y), ch, font=fnt, fill=fill)
        x += cw + spacing


def ember_background(alpha: int = 255, seed: int = 7) -> Image.Image:
    """Radial ember glow + soft bokeh + grain, like the endscreen and hero section."""
    rnd = random.Random(seed)
    bg = Image.new("RGB", (W, H), BG)
    glow = Image.new("L", (W, H))
    ImageDraw.Draw(glow).ellipse((W * 0.1, -H * 0.45, W * 0.9, H * 0.75), fill=255)
    glow = glow.filter(ImageFilter.GaussianBlur(260))
    bg = Image.composite(Image.new("RGB", (W, H), BG_DEEP), bg, glow)
    out = bg.convert("RGBA")
    # one blurred alpha mask per color, so blur never mixes in transparent black (muddy olive dots)
    for color in (AMBER, EMBER, GOLD):
        mask = Image.new("L", (W, H))
        d = ImageDraw.Draw(mask)
        for _ in range(9):
            r = rnd.randint(30, 110)
            x = rnd.choice([rnd.randint(-40, 520), rnd.randint(1400, 1960)])
            y = rnd.randint(-40, H + 40)
            d.ellipse((x - r, y - r, x + r, y + r), fill=rnd.randint(25, 70))
        layer = Image.new("RGBA", (W, H), color + (0,))
        layer.putalpha(mask.filter(ImageFilter.GaussianBlur(18)))
        out.alpha_composite(layer)
    grain = Image.effect_noise((W, H), 18).convert("RGBA")
    grain.putalpha(10)
    out.alpha_composite(grain)
    out.putalpha(alpha)
    return out


def glow_line(width: int) -> Image.Image:
    img = Image.new("RGBA", (width + 80, 60))
    line = Image.new("L", img.size)
    ImageDraw.Draw(line).ellipse((40, 27, width + 40, 33), fill=255)
    halo = Image.new("RGBA", img.size, AMBER + (0,))
    halo.putalpha(line.filter(ImageFilter.GaussianBlur(10)))
    img.alpha_composite(halo)
    core = gradient(img.size).convert("RGBA")
    core.putalpha(line)
    img.alpha_composite(core)
    return img


def logo(size: int) -> Image.Image:
    img = Image.open(LOGO).convert("RGBA").resize((size, size), Image.LANCZOS)
    # the logo sits on a dark square; screen-blend-style mask keeps only the glow
    lum = img.convert("L").point(lambda v: 0 if v < 40 else min(255, (v - 40) * 2))
    img.putalpha(ImageChops.multiply(img.getchannel("A"), lum))
    return img


def title_card(num: int, name: str, line: str) -> Image.Image:
    """Transition card: just the opener line, big, on the ember background (user: 'just show the line')."""
    card = ember_background(alpha=255, seed=num)
    d = ImageDraw.Draw(card)
    q = font("playfair_italic_600.ttf", 84)
    text = f"\u201c{line}\u201d"
    d.multiline_text((W / 2, H / 2), text, font=q, fill=TEXT, anchor="mm", align="center", spacing=26)
    return card


def wrap(text: str, fnt, max_w: int) -> str:
    lines, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if cur and fnt.getlength(trial) > max_w:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    return "\n".join(lines + [cur])


def corner(num: int, line: str) -> Image.Image:
    """Stays top-left for the rest of the item: 'OPENER 10' label + the line, on a soft dark panel."""
    q = font("playfair_italic_600.ttf", 34)
    text = wrap(f"\u201c{line.replace(chr(10), ' ')}\u201d", q, 540)
    probe = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
    tb = probe.multiline_textbbox((0, 0), text, font=q, spacing=8)
    pw, ph = max(tb[2] - tb[0], 200) + 76, tb[3] - tb[1] + 92
    img = Image.new("RGBA", (pw + 40, ph + 40))
    mask = Image.new("L", img.size)
    ImageDraw.Draw(mask).rounded_rectangle((20, 20, 20 + pw, 20 + ph), 18, fill=175)
    panel = Image.new("RGBA", img.size, BG + (0,))
    panel.putalpha(mask.filter(ImageFilter.GaussianBlur(2)))
    img.alpha_composite(panel)
    bar = gradient((6, ph - 36)).convert("RGBA")
    img.alpha_composite(bar, (20 + 22, 20 + 18))
    d = ImageDraw.Draw(img)
    spaced(d, (20 + 44, 20 + 18), f"OPENER {num}", font("mono_500.ttf", 20), GOLD, 6, anchor_center=False)
    d.multiline_text((20 + 44, 20 + 54), text, font=q, fill=TEXT, spacing=8)
    return img


def badge(num: int) -> Image.Image:
    img = Image.new("RGBA", (300, 170))
    # soft dark pool behind the badge so it stays legible on bright walls
    shade = Image.new("L", img.size)
    ImageDraw.Draw(shade).ellipse((0, 0, 230, 170), fill=150)
    pool = Image.new("RGBA", img.size, BG + (0,))
    pool.putalpha(shade.filter(ImageFilter.GaussianBlur(28)))
    img.alpha_composite(pool)
    d = ImageDraw.Draw(img)
    spaced(d, (44, 22), "OPENER", font("mono_500.ttf", 20), TEXT_DIM, 6, anchor_center=False)
    num_img = gradient_text(str(num), font("playfair_800.ttf", 96), glow=14)
    img.alpha_composite(num_img, (40 - 28, 56 - 28))
    return img


def cta_panel() -> Image.Image:
    pw, ph = 470, 640
    panel = Image.new("RGBA", (pw, ph))
    body = Image.new("RGBA", (pw, ph), BG + (225,))
    mask = Image.new("L", (pw, ph))
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, pw - 1, ph - 1), 28, fill=255)
    panel.paste(body, (0, 0), mask)
    border = Image.new("L", (pw, ph))
    ImageDraw.Draw(border).rounded_rectangle((0, 0, pw - 1, ph - 1), 28, outline=255, width=3)
    edge = gradient((pw, ph)).convert("RGBA")
    edge.putalpha(border)
    panel.alpha_composite(edge)
    d = ImageDraw.Draw(panel)
    spaced(d, (pw / 2, 34), "FREE 1:1 CALL", font("mono_500.ttf", 22), TEXT_DIM, 7)
    title = gradient_text("Spark Strategy", font("playfair_800.ttf", 50), glow=10)
    panel.alpha_composite(title, ((pw - title.width) // 2, 70 - 20))
    qr = Image.open(QR_PNG).convert("RGBA").resize((330, 330), Image.NEAREST)
    frame = Image.new("RGBA", (360, 360), (255, 255, 255, 255))
    frame.alpha_composite(qr, (15, 15))
    panel.alpha_composite(frame, ((pw - 360) // 2, 160))
    d.text((pw / 2, 548), "Scan or tap the link", font=font("grotesk_500.ttf", 30), fill=TEXT, anchor="ma")
    d.text((pw / 2, 588), "in the description", font=font("grotesk_500.ttf", 30), fill=TEXT_DIM, anchor="ma")
    return panel


SUB_FPS, SUB_SECS = 30, 2.6
SUB_CLICK_AT, SUB_BELL_AT = 1.15, 1.55  # seconds into the animation; render.py syncs SFX to these
YT_RED, YT_GRAY = (255, 0, 51), (60, 52, 48)


def ease_out(t: float) -> float:
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def overshoot(t: float) -> float:
    """Back-ease: pops slightly past full size, then settles."""
    t = min(max(t, 0.0), 1.0)
    c = 1.9
    return 1 + (c + 1) * (t - 1) ** 3 + c * (t - 1) ** 2


def cursor_icon(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size))
    d = ImageDraw.Draw(img)
    s = size / 24
    pts = [(2, 1), (2, 19), (7, 14.5), (10.5, 22), (13.5, 20.6), (10, 13.2), (16.5, 13.2)]
    d.polygon([(x * s, y * s) for x, y in pts], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=max(2, int(s)))
    return img


def bell_icon(size: int, angle: float) -> Image.Image:
    img = Image.new("RGBA", (size, size))
    d = ImageDraw.Draw(img)
    s = size / 24
    d.pieslice((5 * s, 3 * s, 19 * s, 17 * s), 180, 360, fill=TEXT)
    d.rectangle((5 * s, 10 * s, 19 * s, 17 * s), fill=TEXT)
    d.polygon([(3 * s, 18 * s), (21 * s, 18 * s), (19 * s, 15 * s), (5 * s, 15 * s)], fill=TEXT)
    d.ellipse((10 * s, 18 * s, 14 * s, 22 * s), fill=TEXT)
    return img.rotate(angle, resample=Image.BICUBIC, center=(size / 2, 3 * s))


def subscribe_frame(t: float) -> Image.Image:
    """One frame of the branded subscribe pop-up: logo + button, cursor click, SUBSCRIBED, bell ring."""
    cw, ch = 1000, 260
    canvas = Image.new("RGBA", (cw, ch))
    appear = overshoot(t / 0.35)
    fade = 1.0 if t < SUB_SECS - 0.35 else max((SUB_SECS - t) / 0.35, 0)
    clicked = t >= SUB_CLICK_AT

    group = Image.new("RGBA", (cw, ch))
    # pill backdrop in the ember palette with a gradient hairline edge
    pw, ph = 800, 150
    px, py = (cw - pw) // 2, (ch - ph) // 2
    pill = Image.new("L", (cw, ch))
    ImageDraw.Draw(pill).rounded_rectangle((px, py, px + pw, py + ph), ph // 2, fill=235)
    body = Image.new("RGBA", (cw, ch), BG + (0,))
    body.putalpha(pill)
    group.alpha_composite(body)
    edge = Image.new("L", (cw, ch))
    ImageDraw.Draw(edge).rounded_rectangle((px, py, px + pw, py + ph), ph // 2, outline=255, width=3)
    rim = gradient((cw, ch)).convert("RGBA")
    rim.putalpha(edge)
    group.alpha_composite(rim)

    mark = logo(118)
    group.alpha_composite(mark, (px + 18, py + (ph - 118) // 2))
    d = ImageDraw.Draw(group)
    d.text((px + 150, py + 34), "Sparked", font=font("playfair_800.ttf", 40), fill=TEXT)
    spaced(d, (px + 152, py + 92), "LEARN TO SPARK ATTRACTION", font("mono_500.ttf", 14), TEXT_DIM, 2, anchor_center=False)

    # button squishes on click, then flips to SUBSCRIBED
    squish = 1 - 0.08 * max(0.0, 1 - abs(t - SUB_CLICK_AT) / 0.08)
    bw, bh = int(250 * squish), int(76 * squish)
    bx, by = px + pw - 290 + (250 - bw) // 2, py + (ph - bh) // 2
    d.rounded_rectangle((bx, by, bx + bw, by + bh), 14, fill=YT_GRAY if clicked else YT_RED)
    if clicked:
        # Space Grotesk has no check glyph, so draw the tick by hand
        d.text((bx + bw / 2 + 14, by + bh / 2), "SUBSCRIBED", font=font("grotesk_600.ttf", 26), fill=TEXT_DIM, anchor="mm")
        kx, ky = bx + 22, by + bh / 2
        d.line([(kx, ky), (kx + 8, ky + 8), (kx + 22, ky - 10)], fill=GOLD, width=5, joint="curve")
    else:
        d.text((bx + bw / 2, by + bh / 2), "SUBSCRIBE", font=font("grotesk_600.ttf", 30), fill=(255, 255, 255), anchor="mm")

    if t >= SUB_BELL_AT:
        bt = t - SUB_BELL_AT
        ring = 22 * math.sin(bt * 38) * math.exp(-bt * 5)
        scale = overshoot(bt / 0.25)
        size = max(int(56 * scale), 1)
        group.alpha_composite(bell_icon(size, ring), (px + pw + 14 + (56 - size) // 2, py + (ph - size) // 2))

    # whole group pops from 70% scale, anchored at center
    gs = 0.7 + 0.3 * appear
    gw, gh = int(cw * gs), int(ch * gs)
    scaled = group.resize((gw, gh), Image.LANCZOS)
    canvas.alpha_composite(scaled, ((cw - gw) // 2, (ch - gh) // 2))

    # cursor glides in from bottom-right, taps the button, then drifts off
    if 0.55 <= t < SUB_SECS - 0.35:
        travel = ease_out((t - 0.55) / (SUB_CLICK_AT - 0.1 - 0.55))
        tx, ty = bx + bw * 0.6, by + bh * 0.55
        cx = tx + (1 - travel) * 260
        cy = ty + (1 - travel) * 140
        tap = 0.85 if abs(t - SUB_CLICK_AT) < 0.07 else 1.0
        cur = cursor_icon(int(46 * tap))
        canvas.alpha_composite(cur, (int(cx), int(cy)))

    if fade < 1:
        canvas.putalpha(canvas.getchannel("A").point(lambda v: int(v * fade)))
    return canvas


def subscribe_frames() -> None:
    out = OUT / "subscribe"
    out.mkdir(parents=True, exist_ok=True)
    for i in range(int(SUB_SECS * SUB_FPS)):
        subscribe_frame(i / SUB_FPS).save(out / f"f_{i:03d}.png")


def endscreen() -> Image.Image:
    img = Image.open(ENDSCREEN).convert("RGB")
    scale = W / img.width
    img = img.resize((W, round(img.height * scale)), Image.LANCZOS)
    top = (img.height - H) // 2
    return img.crop((0, top, W, top + H))


def main() -> None:
    make_static_fonts()
    OUT.mkdir(parents=True, exist_ok=True)
    for seg in EDL:
        if seg.get("card"):
            num, name, line = seg["card"]
            title_card(num, name, line).save(OUT / f"card_{num}.png")
            corner(num, line).save(OUT / f"corner_{num}.png")
    cta_panel().save(OUT / "cta.png")
    endscreen().save(OUT / "endscreen.png")
    subscribe_frames()
    print(f"Wrote brand graphics to {OUT}")


if __name__ == "__main__":
    main()
