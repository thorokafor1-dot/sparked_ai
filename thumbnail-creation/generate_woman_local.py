"""Free, unlimited, local (CPU) generation of AI women for concept mocks. No OpenAI.

Uses Realistic Vision (SD 1.5) through diffusers on CPU. Each image takes about 1-3 min on
this laptop, so run batches in the background. Every image gets a random combo of look x
outfit x lighting x pose, so the pool doesn't repeat, and is filed under
reference/women_pool/ai/<look>/ with its tags in reference/women_pool/index.json
(read by mock_videochat_thumbs.py via "woman": "pool:<look>").

Usage:
    python generate_woman_local.py --n 20                 # random looks
    python generate_woman_local.py --n 10 --look latina
"""
import argparse
import json
import random
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
POOL = ROOT / "reference" / "women_pool"
MODEL = "SG161222/Realistic_Vision_V5.1_noVAE"
VAE = "stabilityai/sd-vae-ft-mse"

LOOKS = {
    "latina": "Latina woman, tan skin, dark brown hair",
    "black": "Black woman, deep brown skin, long sleek black hair",
    "blonde": "white woman, honey blonde hair, light eyes",
    "brunette": "white woman, long dark brunette hair, hazel eyes",
    "asian": "East Asian woman, long black hair",
    "mixed": "mixed race woman, light brown skin, curly hair",
    "redhead": "white woman, long copper red hair, freckles",
    "middle_eastern": "Middle Eastern woman, olive skin, long dark wavy hair",
}
OUTFITS = ["black fitted crop top", "cream knit sweater", "white ribbed tank top", "red satin cami top",
           "oversized grey hoodie", "denim jacket over a white tee", "black off-shoulder top", "pastel pink zip-up"]
LIGHTS = ["warm amber sunset light from a window", "cool teal LED strip and a warm lamp", "soft pink ring light",
          "golden hour light", "red neon glow", "soft daylight from a window", "warm string lights"]
# Video-call gaze (user, 2026-10-09): she watches his face on her screen, so her eyes sit slightly
# off the lens, never straight into it. Aimed to the image's right so, in the left panel, she
# looks across the divider at him (flip with --woman-flip in the composer if a seed disagrees).
GAZE = "looking off to the side at her phone screen, eyes not on the camera"
POSES = ["flirty half smile", "chin resting on her hand, playful smile", "laughing", "lying on a bed, soft smile",
         "biting her lip, amused look", "hand in her hair, soft smile"]
# SD 1.5's text encoder reads only ~77 tokens, so the details that must survive (gaze, outfit,
# light) come first and the quality words come last.
PROMPT = ("amateur phone video call screenshot, {look}, 22 years old, {gaze}, wearing a {outfit}, {light}, {pose}, "
          "low quality front camera, slight motion blur, jpeg compression, uneven lighting, messy hair, "
          "real skin texture, no makeup filter, pretty")
# "Slightly too polished" (user, 2026-10-09): push away from editorial/beauty-shot looks.
NEGATIVE = ("looking at camera, eye contact with viewer, staring at lens, professional photo, studio lighting, "
            "beauty retouch, perfect skin, glossy, magazine, bokeh, underwear, lingerie, panties, bikini, "
            "deformed, bad anatomy, extra fingers, cartoon, anime, 3d render, painting, airbrushed, plastic skin, "
            "text, watermark, logo, nsfw, nude, cleavage, child, teen, lowres, blurry")


def load_pipe():
    import torch
    from diffusers import AutoencoderKL, DPMSolverMultistepScheduler, StableDiffusionPipeline
    torch.set_num_threads(max(1, torch.get_num_threads()))
    vae = AutoencoderKL.from_pretrained(VAE, torch_dtype=torch.float32)
    pipe = StableDiffusionPipeline.from_pretrained(MODEL, vae=vae, torch_dtype=torch.float32, safety_checker=None)
    pipe.scheduler = DPMSolverMultistepScheduler.from_config(pipe.scheduler.config, algorithm_type="dpmsolver++",
                                                             use_karras_sigmas=True)  # model config ships "deis"
    pipe.enable_attention_slicing()
    return pipe


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n", type=int, default=10)
    ap.add_argument("--look", choices=list(LOOKS), default=None)
    ap.add_argument("--steps", type=int, default=22)
    ap.add_argument("--seed", type=int, default=None)
    a = ap.parse_args()

    import torch
    pipe = load_pipe()
    idx_path = POOL / "index.json"
    index = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else []
    rng = random.Random(a.seed)
    for _ in range(a.n):
        look = a.look or rng.choice(list(LOOKS))
        tags = {"look": look, "outfit": rng.choice(OUTFITS), "light": rng.choice(LIGHTS), "pose": rng.choice(POSES)}
        seed = rng.randrange(2**31)
        prompt = PROMPT.format(look=LOOKS[look], gaze=GAZE, **{k: tags[k] for k in ("outfit", "light", "pose")})
        t = time.time()
        img = pipe(prompt, negative_prompt=NEGATIVE, width=512, height=768, num_inference_steps=a.steps,
                   guidance_scale=5.0, generator=torch.Generator().manual_seed(seed)).images[0]
        out = POOL / "ai" / look / f"{look}_{seed}.png"
        out.parent.mkdir(parents=True, exist_ok=True)
        img.save(out)
        index.append({"file": str(out.relative_to(ROOT)).replace("\\", "/"), "source": "ai-local", "seed": seed,
                      "mock_only": False, "used_in": [], **tags})
        idx_path.write_text(json.dumps(index, indent=1), encoding="utf-8")
        print(f"{out.name}  {tags['outfit']} / {tags['light']}  {time.time() - t:.0f}s", flush=True)


if __name__ == "__main__":
    main()
