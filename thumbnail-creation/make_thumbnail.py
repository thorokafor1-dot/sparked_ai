"""Composites a thumbnail from one or two chosen source frames, following the
style actually observed in the genuine in-person/infield cold-approach outliers
(Alex Leon, John Savvy, Marvin Goodly, Coach Kyle, Todd V, Dating With Nishant --
see claude.md): natural lighting left mostly alone (just enough exposure lift to
read on a dark night source), medium/wide framing that keeps body language in
frame rather than a tight face crop, and minimal or no caption text. This is
deliberately NOT the heavier produced look (vignette, warm color-cast, big bold
caption) seen on compilation-style channels -- that pattern doesn't fit this
niche's authenticity branding.

Single frame:
    python make_thumbnail.py --frame work/frames/f.jpg --caption "HI" --out output/thumb.png

Two frames side by side (e.g. two different girls from one vertical-source video,
since one portrait crop alone can't fill a 16:9 thumbnail without heavy upscaling):
    python make_thumbnail.py --frame work/frames/girl1.jpg --focus-x 428 --focus-y 320 \
        --frame2 work/frames/girl2.jpg --focus2-x 300 --focus2-y 400 \
        --caption "1 NIGHT. 2 GIRLS." --out output/thumb.png
"""
import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter, ImageFont

OUTPUT_DIR = Path(__file__).parent / "output"
TARGET_SIZE = (1280, 720)
# Below this mean luminance (0-255), a source frame reads as "dark" (night infield
# footage) and needs an exposure lift before anything else, or it composites to
# near-black.
DARK_MEAN_THRESHOLD = 70


def lift_exposure(img: Image.Image, denoise: bool = True) -> Image.Image:
    """CLAHE (tried first) does local contrast stretching, which is exactly
    the wrong tool for a genuinely soft/motion-blurred phone frame: it digs
    into the shadows and drags real compression noise and blur up into
    visibility, so the more you correct, the worse -- not better -- it reads.
    A single flat, global brightness multiply lifts the whole frame the same
    amount without amplifying local (i.e. noise/blur) detail, so a soft frame
    stays soft-but-legible instead of becoming soft-and-artifacted.

    denoise=False skips the bilateral filter below -- use this for a frame
    that already went through restore_faces.py (GFPGAN/Real-ESRGAN already
    denoised it; filtering again just softens real restored detail back out)."""
    arr = np.asarray(img).astype(np.float32)
    mean = arr.mean()
    if mean >= DARK_MEAN_THRESHOLD:
        return img
    target_mean = 95.0
    factor = min(3.0, target_mean / max(mean, 8.0))
    lifted = np.clip(arr * factor, 0, 255).astype(np.uint8)
    if not denoise:
        return Image.fromarray(lifted)
    # A flat multiply lifts sensor/compression noise right along with the
    # signal -- the brighter the lift, the more that noise shows. A bilateral
    # filter smooths flat noisy regions while leaving real edges alone, so it
    # cuts the noise without adding the softness a normal blur would.
    bgr = cv2.cvtColor(lifted, cv2.COLOR_RGB2BGR)
    smoothed = cv2.bilateralFilter(bgr, d=7, sigmaColor=45, sigmaSpace=45)
    return Image.fromarray(cv2.cvtColor(smoothed, cv2.COLOR_BGR2RGB))


def crop_to_ratio(img: Image.Image, target_w: int, target_h: int, focus_xy: tuple[float, float] | None = None) -> Image.Image:
    """"Cover" fit: crops to fill the target exactly. On a soft/motion-blurred
    frame this magnifies whatever blur is there -- fine for a sharp source,
    a bad idea for a soft one (see fit_to_ratio below)."""
    w, h = img.size
    target_ratio = target_w / target_h
    if w / h > target_ratio:
        new_w = int(h * target_ratio)
        cx = focus_xy[0] if focus_xy else w / 2
        left = max(0, min(w - new_w, int(cx - new_w / 2)))
        img = img.crop((left, 0, left + new_w, h))
    else:
        new_h = int(w / target_ratio)
        cy = focus_xy[1] if focus_xy else h / 2
        top = max(0, min(h - new_h, int(cy - new_h / 2)))
        img = img.crop((0, top, w, top + new_h))
    return img.resize((target_w, target_h), Image.LANCZOS)


def fit_to_ratio(img: Image.Image, target_w: int, target_h: int, bg=(0, 0, 0)) -> Image.Image:
    """"Contain" fit: scales the *whole* frame down to fit inside the target,
    letterboxed, with no cropping at all -- so nothing gets zoomed in and any
    blur in the source reads at its true, unmagnified size instead of blown up."""
    w, h = img.size
    scale = min(target_w / w, target_h / h)
    new_w, new_h = max(1, int(w * scale)), max(1, int(h * scale))
    resized = img.resize((new_w, new_h), Image.LANCZOS)
    canvas = Image.new("RGB", (target_w, target_h), bg)
    canvas.paste(resized, ((target_w - new_w) // 2, (target_h - new_h) // 2))
    return canvas


def light_touch_up(img: Image.Image) -> Image.Image:
    """Mild contrast/color nudge only -- no vignette, no color-cast overlay.
    The genuine in-person infield outliers leave lighting alone; this should
    read as "the raw clip, legible" not "a produced graphic"."""
    img = ImageEnhance.Contrast(img).enhance(1.08)
    img = ImageEnhance.Color(img).enhance(1.08)
    return img


def final_sharpen(img: Image.Image) -> Image.Image:
    """A light touch only -- sharpening can't recover detail a blurry source
    frame never captured, and pushing it strong just turns grain into crunchy
    halos, which reads as *more* processed, not less blurry. This is a small
    edge nudge for legibility, not a fix for real motion blur (that needs a
    different source frame, not a filter)."""
    return img.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=3))


def warm_grade(img: Image.Image) -> Image.Image:
    """Heavier produced look (vignette + warm color-cast) -- matches compilation
    -style channels, not the in-person/infield ones. Opt in with --produced-grade."""
    img = ImageEnhance.Color(img).enhance(1.25)
    img = ImageEnhance.Contrast(img).enhance(1.15)
    overlay = Image.new("RGB", img.size, (255, 150, 40))
    img = Image.blend(img, overlay, 0.06)
    vignette = Image.new("L", img.size, 0)
    vd = ImageDraw.Draw(vignette)
    vd.ellipse((-img.width * 0.2, -img.height * 0.2, img.width * 1.2, img.height * 1.2), fill=255)
    vignette = vignette.filter(ImageFilter.GaussianBlur(120))
    black = Image.new("RGB", img.size, (0, 0, 0))
    img = Image.composite(img, black, vignette).convert("RGB")
    return img


def _font(size: int) -> ImageFont.FreeTypeFont:
    for candidate in ("arialbd.ttf", "Arial Bold.ttf", "DejaVuSans-Bold.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            continue
    return ImageFont.load_default()


def draw_caption(
    draw: ImageDraw.ImageDraw,
    text: str,
    xy: tuple[int, int],
    max_width: int,
    size: int = 92,
    center: bool = False,
) -> None:
    x, y = xy
    font = _font(size)
    while size > 32:
        bbox = draw.textbbox((0, 0), text, font=font)
        if bbox[2] - bbox[0] <= max_width:
            break
        size -= 4
        font = _font(size)
    if center:
        bbox = draw.textbbox((0, 0), text, font=font)
        x = x + (max_width - (bbox[2] - bbox[0])) // 2
    shadow_offset = max(2, size // 22)
    for dx, dy in ((shadow_offset, shadow_offset), (-shadow_offset, shadow_offset)):
        draw.text((x + dx, y + dy), text, font=font, fill=(0, 0, 0))
    draw.text((x, y), text, font=font, fill=(255, 255, 255))


def draw_chip(draw: ImageDraw.ImageDraw, text: str, xy: tuple[int, int]) -> None:
    font = _font(28)
    pad = 10
    bbox = draw.textbbox(xy, text, font=font)
    box = (bbox[0] - pad, bbox[1] - pad, bbox[2] + pad, bbox[3] + pad)
    draw.rectangle(box, fill=(15, 15, 15))
    draw.text(xy, text, font=font, fill=(255, 255, 255))


def _prep_panel(frame_path: str, w: int, h: int, focus_xy, produced_grade: bool, fit: str = "cover", ai_restored: bool = False) -> Image.Image:
    img = Image.open(frame_path).convert("RGB")
    img = fit_to_ratio(img, w, h) if fit == "contain" else crop_to_ratio(img, w, h, focus_xy)
    img = lift_exposure(img, denoise=not ai_restored)
    img = warm_grade(img) if produced_grade else light_touch_up(img)
    if not ai_restored:
        img = final_sharpen(img)
    return img


def make_thumbnail(
    frame_path: str,
    caption: str | None,
    out_path: str,
    chip: str | None = None,
    focus_xy: tuple[float, float] | None = None,
    produced_grade: bool = False,
    ai_restored: bool = False,
) -> Path:
    img = _prep_panel(frame_path, TARGET_SIZE[0], TARGET_SIZE[1], focus_xy, produced_grade, ai_restored=ai_restored)
    draw = ImageDraw.Draw(img)
    margin = 50
    if caption:
        draw_caption(draw, caption, (margin, TARGET_SIZE[1] - 170), max_width=TARGET_SIZE[0] - 2 * margin)
    if chip:
        draw_chip(draw, chip, (55, 40))
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = Path(out_path)
    img.save(out)
    return out


def make_split_thumbnail(
    frame1_path: str,
    frame2_path: str,
    caption: str | None,
    out_path: str,
    focus1_xy: tuple[float, float] | None = None,
    focus2_xy: tuple[float, float] | None = None,
    produced_grade: bool = False,
    fit1: str = "cover",
    fit2: str = "cover",
    ai_restored1: bool = False,
    ai_restored2: bool = False,
) -> Path:
    """Two frames side by side -- for a vertically-shot source, this fills a
    16:9 thumbnail with far less upscaling per panel than one portrait crop
    stretched to the full width, and doubles as showing two different people
    from the same video without needing a collage/grid. Pass fit1/fit2="contain"
    for a frame that's soft/motion-blurred -- cropping in tighter only magnifies
    blur that's already there, so a soft frame should be fit whole, not cropped."""
    gap = 6
    panel_w = (TARGET_SIZE[0] - gap) // 2
    panel_h = TARGET_SIZE[1]
    left = _prep_panel(frame1_path, panel_w, panel_h, focus1_xy, produced_grade, fit1, ai_restored1)
    right = _prep_panel(frame2_path, panel_w, panel_h, focus2_xy, produced_grade, fit2, ai_restored2)

    canvas = Image.new("RGB", TARGET_SIZE, (0, 0, 0))
    canvas.paste(left, (0, 0))
    canvas.paste(right, (panel_w + gap, 0))
    draw = ImageDraw.Draw(canvas)
    if caption:
        margin = 40
        draw_caption(
            draw, caption, (margin, TARGET_SIZE[1] - 110),
            max_width=TARGET_SIZE[0] - 2 * margin, size=68, center=True,
        )
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out = Path(out_path)
    canvas.save(out)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Build a thumbnail from one or two source frames.")
    parser.add_argument("--frame", required=True)
    parser.add_argument("--caption", default=None, help="Overlay text, e.g. 'HI' -- keep it short; can be omitted")
    parser.add_argument("--chip", default=None, help="Small context tag (single-frame mode only)")
    parser.add_argument("--focus-x", type=float, default=None)
    parser.add_argument("--focus-y", type=float, default=None)
    parser.add_argument("--frame2", default=None, help="Second frame -- if given, builds a side-by-side thumbnail")
    parser.add_argument("--focus2-x", type=float, default=None)
    parser.add_argument("--focus2-y", type=float, default=None)
    parser.add_argument("--produced-grade", action="store_true", help="Opt into the heavier vignette/warm-cast look instead of the default natural-light touch-up")
    parser.add_argument("--fit1", choices=["cover", "contain"], default="cover", help="'contain' fits the whole frame with no cropping/zoom -- use for a soft/motion-blurred frame")
    parser.add_argument("--fit2", choices=["cover", "contain"], default="cover")
    parser.add_argument("--ai-restored", action="store_true", help="Frame (single-frame mode) already went through restore_faces.py -- skip re-denoising/re-sharpening on top of it")
    parser.add_argument("--ai-restored1", action="store_true", help="Frame 1 already went through restore_faces.py")
    parser.add_argument("--ai-restored2", action="store_true", help="Frame 2 already went through restore_faces.py")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    focus_xy = (args.focus_x, args.focus_y) if args.focus_x is not None and args.focus_y is not None else None
    out_path = args.out or str(OUTPUT_DIR / (Path(args.frame).stem + "_thumb.png"))

    if args.frame2:
        focus2_xy = (args.focus2_x, args.focus2_y) if args.focus2_x is not None and args.focus2_y is not None else None
        result = make_split_thumbnail(
            args.frame, args.frame2, args.caption, out_path, focus_xy, focus2_xy, args.produced_grade,
            args.fit1, args.fit2, args.ai_restored1, args.ai_restored2,
        )
    else:
        result = make_thumbnail(args.frame, args.caption, out_path, args.chip, focus_xy, args.produced_grade, args.ai_restored)
    print(f"Saved: {result}")


if __name__ == "__main__":
    main()
