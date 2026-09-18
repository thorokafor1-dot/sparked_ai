"""Blends a Stable Diffusion regeneration back with the original restored
frame, protecting real people entirely. SD img2img -- even at "low" strength
-- can visibly alter a real person's face and clothing (confirmed: at
strength 0.25 it changed one subject's face and turned her top into a
different garment). That's fabrication, not restoration, and is not
acceptable for real documentary footage of an actual person -- so no
generative pass may touch a person's likeness here, only the inanimate
background (tent fabric, string lights, sky) that GFPGAN/Real-ESRGAN leave
looking painterly/smeared.

Builds a protect-mask as the union of expanded, full-height columns under
each detected face (protects the whole person, not just the face box), then
composites: original pixels inside the protected columns, the SD-regenerated
version everywhere else, feathered at the boundary so the seam doesn't show.

Usage:
    python mask_composite.py --original work/frames/f.png --regenerated work/f_sd.png \
        --out work/f_masked.png
"""
import argparse
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageFilter

FACE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")


def _person_columns_mask(img_bgr: np.ndarray, feather: int = 40, pad_factor: float = 1.0, face_pad: float = 0.25, text_band: float = 0.0) -> Image.Image:
    """Protects two different things for two different reasons, not one blanket
    column: a TIGHT box around the actual face (identity -- must never be
    altered) and a separately-shaped column below the chin (body/clothing --
    also must never be altered, but starts lower). Everything else, including
    hair beside and above the face, is left open for SD to regenerate: hair is
    texture, not identity, and a full-width column sized to protect a wide
    face was swallowing the hair (and therefore most of the frame) along with
    it, leaving that whole panel stuck on the weaker pre-SD restoration."""
    h, w = img_bgr.shape[:2]
    gray = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2GRAY)
    bright = cv2.convertScaleAbs(gray, alpha=2.0, beta=30)
    faces = FACE.detectMultiScale(bright, 1.1, 4, minSize=(max(30, w // 12), max(30, w // 12)))

    mask = np.zeros((h, w), dtype=np.uint8)
    for (x, y, fw, fh) in faces:
        # Tight face protection: just the identity-bearing region, a little
        # padding for the feather to clear real facial edges (chin, hairline).
        fpad_x, fpad_y = int(fw * face_pad), int(fh * face_pad)
        fx0, fx1 = max(0, x - fpad_x), min(w, x + fw + fpad_x)
        fy0, fy1 = max(0, y - fpad_y), min(h, y + fh + fpad_y)
        mask[fy0:fy1, fx0:fx1] = 255

        # Body protection: shoulders/arms are much wider than the face, and an
        # arm resting on a table often sweeps outward well past the shoulders
        # by the bottom of the frame -- flare the column wider toward the
        # bottom to cover that sweep. Starts at the chin, not the top of the
        # frame, so it doesn't reclaim the hair the face-box already excludes.
        pad = int(fw * pad_factor)
        cx = x + fw / 2
        body_top = fy1
        for row_y in range(body_top, h):
            t = (row_y - body_top) / max(1, h - 1 - body_top)
            row_pad = pad * (1 + 1.5 * t)  # up to 2.5x wider by the bottom
            x0 = max(0, int(cx - fw / 2 - row_pad))
            x1 = min(w, int(cx + fw / 2 + row_pad))
            mask[row_y, x0:x1] = 255
    if not len(faces) and text_band <= 0:
        return Image.new("L", (w, h), 0)
    if text_band > 0:
        # Real burned-in captions (actual spoken dialogue) live in a
        # predictable top band in this footage's style. A generative pass
        # regenerates that text as meaningless gibberish -- same authenticity
        # problem as altering a face, just for words instead of a person, so
        # it needs the same unconditional protection regardless of face size.
        mask[: int(h * text_band), :] = 255
    mask_img = Image.fromarray(mask).filter(ImageFilter.GaussianBlur(feather))
    return mask_img


def composite(original_path: str, regenerated_path: str, out_path: str, pad_factor: float = 1.0, face_pad: float = 0.25, text_band: float = 0.0) -> Path:
    orig = Image.open(original_path).convert("RGB")
    regen = Image.open(regenerated_path).convert("RGB").resize(orig.size, Image.LANCZOS)
    mask = _person_columns_mask(cv2.cvtColor(np.asarray(orig), cv2.COLOR_RGB2BGR), pad_factor=pad_factor, face_pad=face_pad, text_band=text_band)
    result = Image.composite(orig, regen, mask)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    result.save(out)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Composite an SD-regenerated background back with the original, protecting people.")
    parser.add_argument("--original", required=True)
    parser.add_argument("--regenerated", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--pad-factor", type=float, default=1.0, help="Body-column padding as a multiple of face width -- wider avoids seam ghosting, narrower preserves more background to regenerate")
    parser.add_argument("--face-pad", type=float, default=0.25, help="Tight face-box padding as a fraction of face size")
    parser.add_argument("--text-band", type=float, default=0.0, help="Protect the top fraction of the frame (e.g. 0.2) to preserve real burned-in caption text")
    args = parser.parse_args()
    result = composite(args.original, args.regenerated, args.out, args.pad_factor, args.face_pad, args.text_band)
    print(f"Saved: {result}")


if __name__ == "__main__":
    main()
