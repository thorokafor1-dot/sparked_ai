"""Runs a Stable Diffusion img2img pass over a frame to regenerate coherent,
crisp photographic detail in place of the smeared/painterly texture Real-ESRGAN
produces on flat surfaces under blown highlights (tent fabric, string-light
bloom), or in place of genuine motion blur no restoration model can recover.

This is generative, not restorative: it can and does alter faces/clothing, so
callers MUST run mask_composite.py afterward to paste the real people back in
from the original frame -- never show raw output from this script for anything
containing an identifiable real person. Because masking discards whatever
this script does to people anyway, there is no reason to keep strength low
for their sake; push strength and steps as high as needed for a genuinely
sharp, richly-detailed background -- the only cost of going too far is on
pixels that get thrown away.

Usage:
    python regenerate_scene.py --frame work/frames/f.png --out work/frames/f_regen.png \
        --strength 0.6 --steps 30
"""
import argparse
from pathlib import Path

import torch
from PIL import Image

PROMPT = (
    "photo taken at night with a modern iPhone camera, outdoor bar patio, "
    "string lights, canvas tent canopy, crisp sharp focus, fine detail, "
    "photorealistic, candid night photography, high resolution"
)
NEGATIVE_PROMPT = (
    "blurry, out of focus, motion blur, painting, illustration, watercolor, "
    "smeared, low quality, low detail, deformed, artifacts, oversaturated"
)

_pipe = None
_model_id = None


def _get_pipe(model_id: str):
    global _pipe, _model_id
    if _pipe is None or _model_id != model_id:
        if model_id == "stabilityai/sd-turbo":
            from diffusers import AutoPipelineForImage2Image
            _pipe = AutoPipelineForImage2Image.from_pretrained(model_id, torch_dtype=torch.float32)
        else:
            from diffusers import StableDiffusionImg2ImgPipeline
            _pipe = StableDiffusionImg2ImgPipeline.from_pretrained(model_id, torch_dtype=torch.float32, safety_checker=None)
        _pipe.to("cpu")
        _model_id = model_id
    return _pipe


def regenerate(
    frame_path: str,
    out_path: str,
    strength: float = 0.55,
    steps: int = 30,
    guidance_scale: float = 7.5,
    model_id: str = "runwayml/stable-diffusion-v1-5",
    work_res: int = 640,
) -> Path:
    pipe = _get_pipe(model_id)
    img = Image.open(frame_path).convert("RGB")
    orig_size = img.size
    w, h = orig_size
    # Area-based scaling to work_res^2 total pixels, whatever the aspect ratio,
    # rounded to a multiple of 8 (required by the SD VAE).
    scale = (work_res * work_res / (w * h)) ** 0.5
    work_w, work_h = max(8, int(round(w * scale / 8) * 8)), max(8, int(round(h * scale / 8) * 8))
    small = img.resize((work_w, work_h), Image.LANCZOS)

    kwargs = dict(prompt=PROMPT, image=small, strength=strength, num_inference_steps=steps)
    if model_id == "stabilityai/sd-turbo":
        kwargs["guidance_scale"] = 0.0  # distilled model, no CFG
    else:
        kwargs["guidance_scale"] = guidance_scale
        kwargs["negative_prompt"] = NEGATIVE_PROMPT

    result = pipe(**kwargs).images[0]
    result = result.resize(orig_size, Image.LANCZOS)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    result.save(out)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Regenerate a frame's detail with a Stable Diffusion img2img pass.")
    parser.add_argument("--frame", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--strength", type=float, default=0.55)
    parser.add_argument("--steps", type=int, default=30)
    parser.add_argument("--guidance-scale", type=float, default=7.5)
    parser.add_argument("--model", default="runwayml/stable-diffusion-v1-5")
    parser.add_argument("--work-res", type=int, default=640)
    args = parser.parse_args()
    result = regenerate(args.frame, args.out, args.strength, args.steps, args.guidance_scale, args.model, args.work_res)
    print(f"Saved: {result}")


if __name__ == "__main__":
    main()
