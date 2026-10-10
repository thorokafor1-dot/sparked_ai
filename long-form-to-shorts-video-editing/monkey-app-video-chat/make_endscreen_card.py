"""Builds the shorts endscreen card (assets/endscreen_card.png) from the channel's own endscreen.

The only copy of the card is a frame lifted from a compressed screen recording of a published short
(assets/endscreen_ref_frame.png), with its 8x8 codec blocks plainly visible on a phone. This restores
that exact frame (deblock at both block sizes, non-local-means denoise, then a light sharpen) so the
design stays pixel-for-pixel the user's own.

Tried first and rejected by the user: redrawing it (clean landing-page logo + vector pill + real text).
It was sharp but "not quite like the original": the landing-page logo is a different version (more
orange, thicker ring, less haze) and the pill's glints, text weight and bolt glyph never matched. Keep
the original pixels; only clean them.

Usage:
    python make_endscreen_card.py   (builds both the card and the YouTube endscreen clip)
"""
import subprocess
from pathlib import Path

HERE = Path(__file__).parent
REF = HERE / "assets" / "endscreen_ref_frame.png"
OUT = HERE / "assets" / "endscreen_card.png"
RESTORE = ("deblock=filter=strong:block=8,deblock=filter=strong:block=4,"
           "nlmeans=s=5:p=7:r=21,unsharp=5:5:0.9:5:5:0.0,cas=0.5")


# YouTube Shorts get the channel's subscribe endscreen instead ("Learn to spark attraction." + SUBSCRIBE),
# lifted from the user's own published short (assets/youtube_endscreen_ref.mp4, Drive 1NobkZtD...). It starts
# on frame 1315 (43.833s, the hard cut in from the last meme) and runs to the end, push-in and fade included
# (2.4s). Same restore chain as the card (its text was visibly stair-stepped); its audio is silent (-66 dB),
# so it gets a silent track. Encoded with render_short.VIDEO_ENC so it joins a render by stream copy.
YT_REF = HERE / "assets" / "youtube_endscreen_ref.mp4"
YT_OUT = HERE / "assets" / "endscreen_youtube.mp4"
YT_START = 1315 / 30


def build_youtube() -> None:
    from render_short import VIDEO_ENC
    subprocess.run([
        "ffmpeg", "-v", "error", "-y", "-ss", f"{YT_START:.4f}", "-i", str(YT_REF),
        "-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo",
        "-vf", RESTORE + ",format=yuv420p,setsar=1", "-map", "0:v", "-map", "1:a",
        *VIDEO_ENC, "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-shortest", str(YT_OUT),
    ], check=True)
    print(f"Wrote {YT_OUT}")


def main() -> None:
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(REF), "-vf", RESTORE, str(OUT)], check=True)
    print(f"Wrote {OUT}")
    build_youtube()


if __name__ == "__main__":
    main()
