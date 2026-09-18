"""Runs AI restoration on a source frame before it goes into make_thumbnail.py:
GFPGAN for faces (a learned face prior that reconstructs plausible sharp detail
-- eyes, teeth, skin texture -- instead of just sharpening existing pixels) plus
Real-ESRGAN as its background upsampler, so the *whole* frame (not just the
face crop) gets denoised and upscaled coherently. Face-only restoration left
the background around the face still grainy; this fixes that.

Only reach for this on a frame that's otherwise the right moment (best
expression) but too soft/blurry/noisy to use as-is -- it's slow (CPU-only
here, well under a minute per frame at these frame sizes, but not instant)
and unnecessary on a frame that's already clean.

Usage:
    python restore_faces.py --frame work/frames/f.jpg --out work/frames/f_restored.jpg
"""
import argparse
from pathlib import Path

import cv2

MODEL_DIR = Path(__file__).parent / "models"
GFPGAN_MODEL = MODEL_DIR / "GFPGANv1.4.pth"
GFPGAN_URL = "https://github.com/TencentARC/GFPGAN/releases/download/v1.3.0/GFPGANv1.4.pth"
ESRGAN_MODEL = MODEL_DIR / "RealESRGAN_x4plus.pth"
ESRGAN_URL = "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.1.0/RealESRGAN_x4plus.pth"


def _ensure(path: Path, url: str) -> None:
    if path.exists():
        return
    import urllib.request
    path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {path.name} ...")
    urllib.request.urlretrieve(url, str(path))


def _bg_upsampler(scale: int):
    from basicsr.archs.rrdbnet_arch import RRDBNet
    from realesrgan import RealESRGANer

    _ensure(ESRGAN_MODEL, ESRGAN_URL)
    model = RRDBNet(num_in_ch=3, num_out_ch=3, num_feat=64, num_block=23, num_grow_ch=32, scale=4)
    return RealESRGANer(
        scale=4,
        model_path=str(ESRGAN_MODEL),
        model=model,
        tile=400,  # keeps CPU memory/time bounded on a full night-shot frame
        tile_pad=10,
        pre_pad=0,
        half=False,  # no GPU here -- fp16 needs CUDA
    )


def restore_faces(frame_path: str, out_path: str, upscale: int = 2, restore_background: bool = True) -> Path:
    _ensure(GFPGAN_MODEL, GFPGAN_URL)
    from gfpgan import GFPGANer

    restorer = GFPGANer(
        model_path=str(GFPGAN_MODEL),
        upscale=upscale,
        arch="clean",
        channel_multiplier=2,
        bg_upsampler=_bg_upsampler(upscale) if restore_background else None,
    )
    img = cv2.imread(frame_path)
    _, _, restored = restorer.enhance(img, has_aligned=False, only_center_face=False, paste_back=True)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), restored)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Restore a blurry/noisy frame (faces + background) with GFPGAN + Real-ESRGAN.")
    parser.add_argument("--frame", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--upscale", type=int, default=2)
    parser.add_argument("--faces-only", action="store_true", help="Skip the Real-ESRGAN background pass (faster, but leaves background grain untouched)")
    args = parser.parse_args()
    result = restore_faces(args.frame, args.out, args.upscale, restore_background=not args.faces_only)
    print(f"Saved: {result}")


if __name__ == "__main__":
    main()
