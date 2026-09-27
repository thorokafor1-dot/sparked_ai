"""Generates a concept thumbnail mockup for a video idea that has no footage shot
yet. Reuses the exact same masked-edit approach as openai_regenerate.py (protect
the real person via mask_composite's face/body-column mask, let gpt-image-1 fill in
everything else) but generalized: takes a real reference photo of the creator and a
per-idea scenario prompt instead of one hardcoded frame and one hardcoded prompt.

This exists because video-ideation/strategist/ideas.json proposes titles for videos
that haven't been shot, there is no real frame to pull a thumbnail from yet. Per the
channel's standing rule (mask_composite.py's docstring), no generative pass may
touch a real person's likeness, only the scene around them, so the creator's real
face/body from the reference photo stays untouched and only the background/setting
changes to match the idea.

Requires OPENAI_API_KEY in thumbnail-creation/.env (gitignored).

Usage:
    python generate_concept_mockup.py --reference reference/self/thor_1.jpg \
        --scenario "college campus quad between classes, daytime, casual talking-head pose" \
        --out output/strategist/college_campus_mockup.png
"""
import argparse
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image

load_dotenv(Path(__file__).parent / ".env")

from mask_composite import _person_columns_mask  # reuse the same protect-mask logic
import cv2
import numpy as np

# OpenAI's edit endpoint only accepts these output sizes.
API_SIZE = (1024, 1536)  # portrait, closest available to a 9:16-ish crop; caller crops to 16:9 after


def _build_mask(photo_path: str, pad_factor: float, face_pad: float, text_band: float) -> Image.Image:
    img = Image.open(photo_path).convert("RGB")
    bgr = cv2.cvtColor(np.asarray(img), cv2.COLOR_RGB2BGR)
    alpha = _person_columns_mask(bgr, pad_factor=pad_factor, face_pad=face_pad, text_band=text_band)
    if not alpha.getbbox():
        raise RuntimeError(
            f"No face detected in {photo_path}, refusing to generate: without a "
            "detected face, the protect-mask would be empty and the edit could "
            "alter the creator's real likeness instead of just the background."
        )
    rgba = img.convert("RGBA")
    rgba.putalpha(alpha)
    return rgba


def generate(
    reference_path: str,
    scenario: str,
    out_path: str,
    pad_factor: float = 1.0,
    face_pad: float = 0.25,
    text_band: float = 0.0,
    quality: str = "high",
) -> Path:
    from openai import OpenAI
    client = OpenAI()

    orig = Image.open(reference_path).convert("RGB")
    mask = _build_mask(reference_path, pad_factor, face_pad, text_band)

    api_img = orig.resize(API_SIZE, Image.LANCZOS)
    api_mask = mask.resize(API_SIZE, Image.LANCZOS)

    stem = Path(reference_path).stem
    img_bytes_path = Path(reference_path).with_name(f"{stem}_api_in.png")
    mask_bytes_path = Path(reference_path).with_name(f"{stem}_api_mask.png")
    api_img.save(img_bytes_path)
    api_mask.save(mask_bytes_path)

    prompt = (
        f"Photo taken with a modern smartphone camera. Scene: {scenario}. "
        "Sharp focus, fine detail, photorealistic. Fill in the transparent area "
        "to naturally continue the existing scene, matching lighting and "
        "perspective to the real person already in frame. Do not add any new "
        "people, do not add any text."
    )

    with open(img_bytes_path, "rb") as img_f, open(mask_bytes_path, "rb") as mask_f:
        result = client.images.edit(
            image=img_f,
            mask=mask_f,
            prompt=prompt,
            model="gpt-image-1",
            size=f"{API_SIZE[0]}x{API_SIZE[1]}",
            quality=quality,
            input_fidelity="high",  # keep the untouched (protected) region faithful to the reference photo
            n=1,
        )

    import base64
    import io
    b64 = result.data[0].b64_json
    out_img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
    out_img = out_img.resize(orig.size, Image.LANCZOS)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out_img.save(out)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference", required=True, help="real photo of the creator, clear face visible")
    parser.add_argument("--scenario", required=True, help="text description of the video idea's setting/mood")
    parser.add_argument("--out", required=True)
    parser.add_argument("--pad-factor", type=float, default=1.0)
    parser.add_argument("--face-pad", type=float, default=0.25)
    parser.add_argument("--quality", default="high", choices=["low", "medium", "high"])
    args = parser.parse_args()

    out = generate(args.reference, args.scenario, args.out, args.pad_factor, args.face_pad, quality=args.quality)
    print(f"Wrote {out}")
    print("Next: run through make_thumbnail.py for final crop/caption, then qa/checks_image.py thumbnail-specs, then critic.")


if __name__ == "__main__":
    main()
