"""Self-review check: finds a single frame that doesn't belong to either the shot before or after it --
"one frame where the cut wasn't adjusted yet" (the user's own description, confirmed on three separate
bugs this session: a stale crop playing over already-changed content, a blank background frame, a sliver
of the source app's own UI chrome). All three shared one signature in the RENDERED output: two large
frame-to-frame jumps back to back (into the bad frame, then out of it again), instead of the one jump a
real hard cut makes. A real cut's content is stable again by the very next frame; a lone bad frame isn't.

This catches it from the final render directly, independent of which code path produced the mismatched
boundary (today's three bugs were three different causes) -- the generic prevention is watching the
output for the shape of the defect, not enumerating every place a boundary gets computed.

Usage:
    python verify_lone_frames.py output/short_1_v67.mp4
"""
import argparse

import cv2
import numpy as np

DIFF_THRESH = 30.0  # mean abs gray diff between consecutive frames that counts as "a real jump" -- every
# confirmed lone-frame bug this session scored 41-83 here; ordinary talking-head motion (a head bob, a
# hand gesture) scored 12-23 on both sides and would false-positive at a lower threshold
HANDHELD_K = 2.5   # handheld only: both jumps must also clear this x the local median diff


def find_lone_frames(video_path: str, handheld: bool = False) -> list[tuple[float, float, float]]:
    """Returns [(time, diff_in, diff_out), ...] for every frame with a large jump on BOTH sides -- the
    shape of a frame that belongs to neither its predecessor's shot nor its successor's.

    handheld: walking phone footage (infield shorts) shakes at 30-34 frame-to-frame for whole seconds,
    over the fixed threshold calibrated on static webcam calls (amanda_v1: 15 hits, none a real glitch).
    There a lone frame must also stand out from its own surroundings: both jumps over HANDHELD_K x the
    median diff of the half second around it."""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    grays = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        grays.append(cv2.cvtColor(cv2.resize(frame, (108, 192)), cv2.COLOR_BGR2GRAY).astype(np.float32))
    cap.release()
    diffs = [float(np.mean(np.abs(grays[i - 1] - grays[i]))) for i in range(1, len(grays))]
    def floor(i):
        if not handheld:
            return DIFF_THRESH
        ctx = diffs[max(0, i - 8):i - 1] + diffs[i + 1:i + 9]
        return max(DIFF_THRESH, HANDHELD_K * float(np.median(ctx))) if ctx else DIFF_THRESH
    return [
        (i / fps, round(diffs[i - 1], 1), round(diffs[i], 1))
        for i in range(1, len(diffs)) if diffs[i - 1] > floor(i) and diffs[i] > floor(i)
    ]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    args = ap.parse_args()
    found = find_lone_frames(args.video)
    if not found:
        print("No lone-frame anomalies found.")
        return
    print(f"{len(found)} lone-frame candidate(s) (not all are real -- check the ones outside a meme cutaway):")
    for t, a, b in found:
        print(f"  {t:.2f}s  in={a} out={b}")


if __name__ == "__main__":
    main()
