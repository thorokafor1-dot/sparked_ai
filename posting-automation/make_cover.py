"""Builds the 1080x1920 IG/FB/TikTok cover for a short from a clean source frame (no burned captions).

Default (user, 2026-10-02): a clean frame from the video, her filling the whole 9:16 cover, no text,
no padding. Optional --line1/--line2 add a hook in brand fonts (Playfair bold, then an italic
gold-gradient accent line) like the older cover_short_1_v73.png. When her face sits at
the very top of the source pane (common on video-chat footage), --top-pad pushes the frame down and fills
the band above with a blurred, darkened copy of the frame, so the text has room and her face lands inside
Instagram's 3:4 profile-grid crop (y 240-1680).

  python make_cover.py --video <src.mp4> --time 355.3 --center-x 300 \
      --line1 "Keep a straight face" --line2 "for 10 seconds." --top-pad 420 --out <cover.png>
"""
import argparse
import sys
from pathlib import Path

import cv2
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "long-form-video-editing" / "talking-head-infield"))
import brand_graphics as bg  # noqa: E402

W, H = 1080, 1920
CREAM = (245, 238, 230)


def grab(video: str, t: float) -> Image.Image:
    cap = cv2.VideoCapture(video)
    cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
    ok, frame = cap.read()
    if not ok:
        sys.exit(f"could not read a frame at {t}s from {video}")
    return Image.fromarray(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))


MAX_TEXT_W = 960  # 60px margin each side; long hook lines shrink instead of running off the frame


def _fit(name: str, text: str, size: int):
    while size > 48:
        f = bg.font(name, size)
        box = f.getbbox(text)
        if box[2] - box[0] <= MAX_TEXT_W:
            return f
        size -= 4
    return bg.font(name, size)


def build(src: Image.Image, center_x: int, top_pad: int, line1: str, line2: str, lift: float = 1.0) -> Image.Image:
    sw, sh = src.size
    body_h = H - top_pad
    crop_w = round(sh * W / body_h) if top_pad else round(sh * W / H)
    x0 = min(max(center_x - crop_w // 2, 0), sw - crop_w)
    body = src.crop((x0, 0, x0 + crop_w, sh)).resize((W, body_h), Image.LANCZOS)
    body = body.filter(ImageFilter.UnsharpMask(radius=2, percent=60, threshold=3))
    if lift != 1.0:
        # dim webcam rooms read murky at thumbnail size (critic on short_3): gamma lift brightens the face
        # and midtones without clipping highlights the way a flat brightness gain would
        body = body.point(lambda v: round(255 * (v / 255) ** (1 / lift)))
    canvas = Image.new("RGB", (W, H))
    if top_pad:
        # backdrop: the whole frame, blurred and dimmed, so the band above her head is the same room
        back = src.crop((x0, 0, x0 + crop_w, sh)).resize((W, H), Image.LANCZOS).filter(ImageFilter.GaussianBlur(40))
        canvas.paste(ImageEnhance.Brightness(back).enhance(0.55))
        fade = Image.linear_gradient("L").resize((W, 220))  # soft seam where the sharp frame starts
        mask = Image.new("L", (W, body_h), 255)
        mask.paste(fade, (0, 0))
        canvas.paste(body, (0, top_pad), mask)
    else:
        canvas.paste(body)
    if not line1:
        return canvas  # default: a clean full-bleed frame, no text (user, 2026-10-02)
    canvas = canvas.convert("RGBA")

    # text: shadowed cream bold line, gold-gradient italic accent line underneath
    f1, f2 = _fit("playfair_800.ttf", line1, 104), _fit("playfair_italic_600.ttf", line2, 112)
    y = max(top_pad - 250, 260)  # inside the IG 3:4 grid crop (y 240-1680)
    shadow = Image.new("RGBA", (W, H))
    ImageDraw.Draw(shadow).text((W / 2, y), line1, font=f1, fill=(0, 0, 0, 200), anchor="ma")
    canvas.alpha_composite(shadow.filter(ImageFilter.GaussianBlur(10)))
    ImageDraw.Draw(canvas).text((W / 2, y), line1, font=f1, fill=CREAM, anchor="ma")
    accent = bg.gradient_text(line2, f2, glow=18)
    canvas.alpha_composite(accent, ((W - accent.width) // 2, y + f1.size - 18 * 2 + 10))
    return canvas.convert("RGB")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--time", type=float, required=True, help="source timestamp (s) of the cover frame")
    ap.add_argument("--center-x", type=int, required=True, help="source x of her face")
    ap.add_argument("--line1", default="", help="optional hook text; the user's default is NO text on covers")
    ap.add_argument("--line2", default="")
    ap.add_argument("--top-pad", type=int, default=0, help="px of blurred band above the frame for the text")
    ap.add_argument("--lift", type=float, default=1.0, help="gamma lift on the frame (1.3 for a dim room)")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    build(grab(a.video, a.time), a.center_x, a.top_pad, a.line1, a.line2, a.lift).save(a.out)
    print(f"Wrote {a.out}")


if __name__ == "__main__":
    main()
