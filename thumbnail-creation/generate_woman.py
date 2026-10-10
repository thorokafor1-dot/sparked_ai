"""Generate a photoreal AI woman (not any real person) for the left panel of a
Monkey App / video-chat compilation thumbnail, via OpenAI gpt-image-1.

Output is a portrait PNG meant for compose_videochat_thumb.py.

Usage:
    python generate_woman.py --pose shoulder --out work/woman_shoulder.png
    python generate_woman.py --pose selfie --look latina --out work/woman_selfie.png

Requires OPENAI_API_KEY in thumbnail-creation/.env (gitignored).
"""
import argparse
import base64
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

BASE = (
    "Candid unedited screenshot from a live phone video chat, taken with an "
    "iPhone front camera in a dim room, slight digital noise and softness like "
    "a real video call frame, not a professional photo. A strikingly "
    "beautiful real woman in her early 20s, the kind of girl with a big "
    "Instagram following, {look}, high cheekbones, full lips with lip liner "
    "and gloss, lash extensions, sculpted brows, long styled blowout hair. "
    "Real skin: visible pores, a few tiny "
    "blemishes, slight shine on the nose and forehead, natural uneven skin "
    "tone, baby hairs and flyaways, makeup that is done but sits on real "
    "skin texture, not airbrushed. {pose} "
    "Lived-in bedroom behind her: unmade bed, clothes on a chair, a cheap pink "
    "LED strip on the wall casting uneven color, mixed with warm lamp light. "
    "Slightly off-centre framing, a little wide-angle lens distortion. "
    "No beauty filter, no retouching, no text, no logos, no phone UI, "
    "no picture-in-picture inset, no second person in frame."
)

LOOKS = {
    "latina": "tan skin, dark brown hair, full lips, Latina features",
    "brunette": "light olive skin, long dark brunette waves, hazel eyes",
    "blonde": "sun-kissed skin, long honey blonde hair, blue-green eyes",
    "black": "deep brown skin, long sleek black hair, striking features",
}

POSES = {
    "shoulder": (
        "She is turned away and glancing back over her shoulder at the camera "
        "with a playful smirk, wearing a fitted pink satin slip dress, "
        "her hourglass silhouette in frame, medium shot from the hips up."
    ),
    "selfie": (
        "She is holding the phone at arm's length, chin slightly down, giving "
        "a confident flirty look straight into the lens with lips slightly "
        "parted, wearing a fitted white ribbed tank top and gold necklace, "
        "framed from the waist up."
    ),
    "screen": (
        "She is mid video call, holding the phone at arm's length, her head "
        "turned a little to her left (toward the right edge of the image), eyes "
        "clearly looking off to the side at the screen, not at the camera "
        "lens, three-quarter view of her face, with a "
        "flirty half smile like she is enjoying what he just said, wearing a "
        "fitted white ribbed tank top and gold necklace, framed from the "
        "waist up."
    ),
    "lying": (
        "She is lying on her stomach on the bed propped on her elbows, feet "
        "kicked up behind her, smiling flirtatiously at the camera, wearing a "
        "fitted red lounge set, "
        "camera slightly above her."
    ),
}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pose", choices=POSES, default="shoulder")
    ap.add_argument("--look", choices=LOOKS, default="latina")
    ap.add_argument("--extra", default="", help="extra prompt detail appended")
    ap.add_argument("--quality", default="high", choices=["low", "medium", "high"])
    ap.add_argument("--out", required=True)
    a = ap.parse_args()

    from openai import OpenAI

    prompt = BASE.format(look=LOOKS[a.look], pose=POSES[a.pose]) + (" " + a.extra if a.extra else "")
    res = OpenAI().images.generate(
        model="gpt-image-1", prompt=prompt, size="1024x1536", quality=a.quality,
        moderation="low", n=1,
    )
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(base64.b64decode(res.data[0].b64_json))
    print(f"saved {out}")


if __name__ == "__main__":
    main()
