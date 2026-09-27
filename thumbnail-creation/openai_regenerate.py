"""Uses OpenAI's gpt-image-1 edit endpoint (proper mask-based inpainting) to
regenerate the background of a frame while leaving a masked-out region (the
real people) completely untouched. This replaces the manual Stable Diffusion
+ face-detection-column approach in regenerate_scene.py / mask_composite.py --
same idea (protect real likeness, regenerate everything else), but using the
API's actual mask parameter instead of a hand-built post-hoc alpha composite,
and a model with much stronger photorealism/anatomy than base SD1.5.

Requires OPENAI_API_KEY in thumbnail-creation/.env (gitignored).

Usage:
    python openai_regenerate.py --frame work/girl2_panel_1080.png --out work/girl2_openai.png \
        --mask-from work/girl2_panel_1080.png  # builds the protect-mask itself via face detection
"""
import argparse
import base64
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image

load_dotenv(Path(__file__).parent / ".env")

from mask_composite import _person_columns_mask  # reuse the same protect-mask logic
import cv2
import numpy as np

PROMPT = (
    "Photo taken at night with a modern smartphone camera on an outdoor bar patio. "
    "String lights, canvas tent canopy overhead, other patrons in the background. "
    "Sharp focus, fine detail, photorealistic night photography. "
    "Fill in the transparent area to naturally continue the existing scene -- "
    "same lighting, same setting -- do not add any new people or text."
)

# OpenAI's edit endpoint only accepts these output sizes.
API_SIZE = (1024, 1536)  # portrait, closest available to our ~0.89 panel ratio


def _build_mask(panel_path: str, pad_factor: float, face_pad: float, text_band: float, extra_rects) -> Image.Image:
    img = Image.open(panel_path).convert("RGB")
    bgr = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)
    alpha = _person_columns_mask(bgr, pad_factor=pad_factor, face_pad=face_pad, text_band=text_band, extra_rects=extra_rects)
    # OpenAI's mask convention: fully transparent = edit/regenerate, opaque = keep.
    # Our protect-mask is already 255=protect/keep, 0=open/regenerate -- same
    # polarity as alpha (255=opaque=keep), so it maps straight across.
    rgba = img.convert("RGBA")
    rgba.putalpha(alpha)
    return rgba


def regenerate(
    panel_path: str,
    out_path: str,
    pad_factor: float = 1.0,
    face_pad: float = 0.25,
    text_band: float = 0.2,
    extra_rects=None,
    quality: str = "high",
) -> Path:
    from openai import OpenAI
    client = OpenAI()

    orig = Image.open(panel_path).convert("RGB")
    mask = _build_mask(panel_path, pad_factor, face_pad, text_band, extra_rects)

    api_img = orig.resize(API_SIZE, Image.LANCZOS)
    api_mask = mask.resize(API_SIZE, Image.LANCZOS)

    img_bytes_path = Path(panel_path).with_name(Path(panel_path).stem + "_api_in.png")
    mask_bytes_path = Path(panel_path).with_name(Path(panel_path).stem + "_api_mask.png")
    api_img.save(img_bytes_path)
    api_mask.save(mask_bytes_path)

    with open(img_bytes_path, "rb") as img_f, open(mask_bytes_path, "rb") as mask_f:
        result = client.images.edit(
            image=img_f,
            mask=mask_f,
            prompt=PROMPT,
            model="gpt-image-1",
            size=f"{API_SIZE[0]}x{API_SIZE[1]}",
            quality=quality,
            input_fidelity="high",  # keep the untouched (masked-protected) region faithful to the input
            n=1,
        )

    b64 = result.data[0].b64_json
    out_img = Image.open(__import__("io").BytesIO(base64.b64decode(b64))).convert("RGB")
    out_img = out_img.resize(orig.size, Image.LANCZOS)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out_img.save(out)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate a frame's background via OpenAI gpt-image-1 edit (masked).")
    parser.add_argument("--frame", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--pad-factor", type=float, default=1.0)
    parser.add_argument("--face-pad", type=float, default=0.25)
    parser.add_argument("--text-band", type=float, default=0.2)
    parser.add_argument("--extra-rect", action="append", default=[])
    parser.add_argument("--quality", default="high", choices=["low", "medium", "high", "auto"])
    args = parser.parse_args()
    extra_rects = [tuple(float(v) for v in r.split(",")) for r in args.extra_rect]
    result = regenerate(args.frame, args.out, args.pad_factor, args.face_pad, args.text_band, extra_rects, args.quality)
    print(f"Saved: {result}")


if __name__ == "__main__":
    main()
