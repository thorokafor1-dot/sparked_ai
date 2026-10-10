"""Sparked-branded vertical (9:16) endscreen for shorts: glowing bolt mark + "Follow for more" pill,
on the same ember background used by the long-form brand graphics. Reuses the long-form module's fonts,
logo and gradient helpers directly (same brand look) rather than redrawing them -- only the composition
is new, since the long-form endscreen is a hand-made 16:9 asset that would crop badly at 9:16.

Usage:
    python make_endscreen.py
Writes work/endscreen_vertical.png.
"""
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

LONGFORM = Path(__file__).parent.parent.parent / "long-form-video-editing" / "talking-head-infield"
sys.path.insert(0, str(LONGFORM))
from brand_graphics import AMBER, BG, BG_DEEP, EMBER, GOLD, TEXT, font, gradient, gradient_text, logo  # noqa: E402

W, H = 1080, 1920
WORK_DIR = Path(__file__).parent / "work"


def ember_background_vertical(seed: int = 7) -> Image.Image:
    """Same recipe as brand_graphics.ember_background, just sized for a 9:16 card."""
    rnd = random.Random(seed)
    bg = Image.new("RGB", (W, H), BG)
    glow = Image.new("L", (W, H))
    ImageDraw.Draw(glow).ellipse((W * -0.3, H * 0.05, W * 1.3, H * 0.75), fill=255)
    glow = glow.filter(ImageFilter.GaussianBlur(220))
    bg = Image.composite(Image.new("RGB", (W, H), BG_DEEP), bg, glow)
    out = bg.convert("RGBA")
    for color in (AMBER, EMBER, GOLD):
        mask = Image.new("L", (W, H))
        d = ImageDraw.Draw(mask)
        for _ in range(7):
            r = rnd.randint(30, 100)
            x = rnd.randint(-40, W + 40)
            y = rnd.choice([rnd.randint(-40, 420), rnd.randint(H - 420, H + 40)])
            d.ellipse((x - r, y - r, x + r, y + r), fill=rnd.randint(25, 70))
        layer = Image.new("RGBA", (W, H), color + (0,))
        layer.putalpha(mask.filter(ImageFilter.GaussianBlur(16)))
        out.alpha_composite(layer)
    grain = Image.effect_noise((W, H), 18).convert("RGBA")
    grain.putalpha(22)
    out.alpha_composite(grain)
    return out.convert("RGB")


def follow_button() -> Image.Image:
    """Ember-gradient pill, white bold label + a small bolt glyph -- matches the reference clip's
    "Follow for more" card (shorts use "Follow", not "Subscribe": that's a YouTube-watch-page action,
    Shorts surfaces the channel's Follow prompt instead)."""
    bw, bh = 620, 150
    pad = 30
    img = Image.new("RGBA", (bw + pad * 2, bh + pad * 2))
    fill = gradient((bw, bh)).convert("RGBA")
    mask = Image.new("L", (bw, bh))
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, bw, bh), bh // 2, fill=255)
    fill.putalpha(mask)
    halo = Image.new("RGBA", img.size, EMBER + (0,))
    halo_mask = Image.new("L", img.size)
    ImageDraw.Draw(halo_mask).rounded_rectangle((pad, pad, pad + bw, pad + bh), bh // 2, fill=140)
    halo.putalpha(halo_mask.filter(ImageFilter.GaussianBlur(22)))
    img.alpha_composite(halo)
    img.alpha_composite(fill, (pad, pad))
    d = ImageDraw.Draw(img)
    label = "Follow for more"
    fnt = font("grotesk_600.ttf", 52)
    tb = d.textbbox((0, 0), label, font=fnt)
    tw = tb[2] - tb[0]
    mark = logo(58)
    total_w = tw + 18 + mark.width
    tx = pad + (bw - total_w) / 2
    ty = pad + bh / 2
    d.text((tx, ty), label, font=fnt, fill=(255, 255, 255), anchor="lm")
    img.alpha_composite(mark, (int(tx + tw + 18), int(ty - mark.height / 2)))
    return img


def endscreen_vertical() -> Image.Image:
    card = ember_background_vertical().convert("RGBA")
    mark = logo(440)
    card.alpha_composite(mark, ((W - mark.width) // 2, int(H * 0.34) - mark.height // 2))
    name = gradient_text("Sparked", font("playfair_800.ttf", 92), glow=24)
    card.alpha_composite(name, ((W - name.width) // 2, int(H * 0.34) + mark.height // 2 + 20))
    btn = follow_button()
    card.alpha_composite(btn, ((W - btn.width) // 2, int(H * 0.34) + mark.height // 2 + 20 + name.height + 50))
    return card.convert("RGB")


def main() -> None:
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    out = WORK_DIR / "endscreen_vertical.png"
    endscreen_vertical().save(out)
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
