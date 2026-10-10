"""Self-review check: flags a stacked (split) half that reads as a frozen/stuck frame -- a real bug
pattern (a forced-split's "held" half rendered with too little motion to look alive), not caught by
verify_cuts.py (which only looks for hard CUTS, not the absence of motion within a shot) or
verify_face_presence.py (a frozen face is still a detected face). Checked directly against the rendered
output, at the actual frame rate a viewer sees, top and bottom half independently.

Usage:
    python verify_freeze.py output/short_1_v44.mp4
"""
import argparse

import cv2
import numpy as np

DIFF_THRESH = 0.15    # mean abs gray difference between consecutive sampled frames below this reads as no motion
MIN_FROZEN_DUR = 0.5  # seconds; a static run shorter than this is just a natural pause, not a freeze
SAMPLE_STEP = 3        # frames between samples (0.1s at 30fps) -- fine enough to catch a freeze, cheap enough to run every render


def check_freeze_spans(video_path: str) -> dict[str, list[tuple[float, float]]]:
    """Returns {"top": [(start, end), ...], "bottom": [...]} -- spans (seconds) where that half of the
    frame barely changed between samples for at least MIN_FROZEN_DUR. Only meaningful on a stacked
    (split-layout) render; a solo short will show real pauses in BOTH halves at once (the whole frame is
    calm), which callers should treat as intentional, not a bug -- see checks_video.py's usage."""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    half = h // 2

    prev_top = prev_bot = None
    samples: list[tuple[float, float, float]] = []
    i = 0
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if i % SAMPLE_STEP == 0:
            top = cv2.cvtColor(cv2.resize(frame[:half], (80, 80)), cv2.COLOR_BGR2GRAY).astype(np.float32)
            bot = cv2.cvtColor(cv2.resize(frame[half:], (80, 80)), cv2.COLOR_BGR2GRAY).astype(np.float32)
            if prev_top is not None:
                samples.append((i / fps, float(np.mean(np.abs(top - prev_top))), float(np.mean(np.abs(bot - prev_bot)))))
            prev_top, prev_bot = top, bot
        i += 1
    cap.release()

    def frozen_spans(idx: int) -> list[tuple[float, float]]:
        spans, start = [], None
        for t, dtop, dbot in samples:
            val = dtop if idx == 1 else dbot
            if val < DIFF_THRESH:
                start = t if start is None else start
            else:
                if start is not None and t - start >= MIN_FROZEN_DUR:
                    spans.append((start, t))
                start = None
        if start is not None and samples and samples[-1][0] - start >= MIN_FROZEN_DUR:
            spans.append((start, samples[-1][0]))
        return spans

    return {"top": frozen_spans(1), "bottom": frozen_spans(2)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    args = ap.parse_args()
    spans = check_freeze_spans(args.video)
    found = False
    for half, hs in spans.items():
        for start, end in hs:
            found = True
            print(f"  {half} half frozen {start:.2f}s-{end:.2f}s ({end - start:.2f}s)")
    if not found:
        print("No frozen spans found.")


if __name__ == "__main__":
    main()
