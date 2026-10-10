"""Branded "Sparked Thor" sting between the teaser and the main video (user, v33): the Sparked ember background,
Thor's channel avatar in a glowing gold ring, "Sparked Thor" in the brand fonts, a soft shimmer. 2.0 s, fading up from black and dipping back to black (no abrupt cuts).

Reuses the brand look from long-form-video-editing/talking-head-infield/brand_graphics.py.
Avatar: assets/avatar.png (the Sparked Thor YouTube channel picture).

Usage: python make_brand_sting.py   -> memeclips/brand_sting.mkv
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

ROOT = Path(__file__).resolve().parent
BRAND = ROOT.parent / "talking-head-infield"
sys.path.insert(0, str(BRAND))
import brand_graphics as bg  # noqa: E402

W, H, FPS = 1920, 1080, 30
DUR = 2.0
AV = 300                       # avatar diameter
OUT = ROOT / "memeclips" / "brand_sting.mkv"
FRAMES = ROOT / "work" / "sting"


def ease(t):
    t = min(max(t, 0.0), 1.0)
    return 1 - (1 - t) ** 3


def avatar_disc():
    im = Image.open(ROOT / "assets" / "avatar.png").convert("RGB")
    im = im.crop((160, 90, 620, 550)).resize((AV, AV), Image.LANCZOS)   # square on his face
    mask = Image.new("L", (AV * 4, AV * 4))
    ImageDraw.Draw(mask).ellipse((0, 0, AV * 4 - 1, AV * 4 - 1), fill=255)
    disc = im.convert("RGBA")
    disc.putalpha(mask.resize((AV, AV), Image.LANCZOS))
    # gold gradient ring with an amber glow
    pad = 40
    size = AV + pad * 2
    ring_mask = Image.new("L", (size, size))
    d = ImageDraw.Draw(ring_mask)
    d.ellipse((pad - 7, pad - 7, pad + AV + 6, pad + AV + 6), fill=255)
    d.ellipse((pad, pad, pad + AV - 1, pad + AV - 1), fill=0)
    out = Image.new("RGBA", (size, size))
    halo = Image.new("RGBA", (size, size), bg.AMBER + (0,))
    halo.putalpha(ring_mask.filter(ImageFilter.GaussianBlur(14)).point(lambda v: int(v * 0.8)))
    out.alpha_composite(halo)
    ring = bg.gradient((size, size)).convert("RGBA")
    ring.putalpha(ring_mask)
    out.alpha_composite(ring)
    out.alpha_composite(disc, (pad, pad))
    return out


def title():
    bg.make_static_fonts()
    sparked = bg.gradient_text("Sparked", bg.font("playfair_italic_600.ttf", 118), glow=22)
    thor_f = bg.font("playfair_800.ttf", 118)
    box = thor_f.getbbox("Thor")
    thor = Image.new("RGBA", (box[2] - box[0] + 88, sparked.height))
    ImageDraw.Draw(thor).text((44 - box[0], (sparked.height - (box[3] - box[1])) / 2 - box[1] + 4), "Thor",
                              font=thor_f, fill=bg.TEXT)
    gap = -40   # gradient_text pads with glow room; pull the words together
    out = Image.new("RGBA", (sparked.width + thor.width + gap, sparked.height))
    out.alpha_composite(sparked, (0, 0))
    out.alpha_composite(thor, (sparked.width + gap, 0))
    return out


def main():
    FRAMES.mkdir(parents=True, exist_ok=True)
    for f in FRAMES.glob("*.png"):
        f.unlink()
    base = bg.ember_background(seed=11)
    disc, txt, line = avatar_disc(), title(), bg.glow_line(520)
    cy_av, cy_txt = 420, 700
    n = round(DUR * FPS)
    for i in range(n):
        t = i / FPS
        fr = base.copy()
        a = ease(t / 0.35)                          # avatar: scale 0.86 -> 1, fade in
        sc = 0.86 + 0.14 * a
        dd = disc.resize((round(disc.width * sc), round(disc.height * sc)), Image.LANCZOS)
        dd.putalpha(dd.getchannel("A").point(lambda v: int(v * a)))
        fr.alpha_composite(dd, (W // 2 - dd.width // 2, cy_av - dd.height // 2))
        b = ease((t - 0.18) / 0.35)                 # title: rise 24 px, fade in
        tt = txt.copy()
        tt.putalpha(tt.getchannel("A").point(lambda v: int(v * b)))
        fr.alpha_composite(tt, (W // 2 - tt.width // 2, cy_txt - tt.height // 2 + round(24 * (1 - b))))
        c = ease((t - 0.35) / 0.35)                 # glow line under the name
        ll = line.copy()
        ll.putalpha(ll.getchannel("A").point(lambda v: int(v * c)))
        fr.alpha_composite(ll, (W // 2 - ll.width // 2, cy_txt + 92))
        fade = min(1.0, (DUR - t) / 0.25, t / 0.25)  # fade up from black, dip to black at the end
        if fade < 1:
            fr = Image.blend(Image.new("RGBA", (W, H), (0, 0, 0, 255)), fr, fade)
        fr.convert("RGB").save(FRAMES / f"{i:04d}.png")
    ns = round(n / FPS * 48000)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-framerate", str(FPS), "-i", str(FRAMES / "%04d.png"),
                    "-i", str(ROOT / "sfx" / "rizz_2353.mp3"),
                    "-filter_complex", f"[1:a]aresample=48000,aformat=channel_layouts=stereo,apad,atrim=end_sample={ns},"
                                       f"afade=t=out:st={DUR - 0.3:.2f}:d=0.3[a]",
                    "-map", "0:v", "-map", "[a]", "-frames:v", str(n), "-c:v", "libx264", "-crf", "16",
                    "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", str(OUT)], check=True)
    print(f"wrote {OUT} ({n / FPS:.2f}s)")


if __name__ == "__main__":
    main()
