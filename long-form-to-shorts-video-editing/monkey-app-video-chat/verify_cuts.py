"""Cut-rhythm check for a rendered short: finds the hard cuts and flags the ones that read as
jumpy (a shot that flashes by, or a burst of cuts in a couple of seconds).

A hard cut is a frame whose pixels differ sharply from the previous frame; a smooth pan or a
person moving never does. Usage: python verify_cuts.py output/short_1_v33.mp4
"""
import argparse

import cv2
import numpy as np

CUT_DIFF = 10.0        # mean abs gray difference between consecutive frames that counts as a cut...
CUT_RATIO = 2.5        # ...when it is also this many times bigger than the frames either side of it
MIN_SHOT = 0.5         # seconds; a shot shorter than this is a flash
BURST_WINDOW = 2.0     # seconds
BURST_MAX_CUTS = 3     # more cuts than this inside BURST_WINDOW reads as jumpy


def find_cuts(video_path: str) -> tuple[list[float], float]:
    """Returns (cut times in seconds, total duration).

    Real motion (a hand sweeping the frame, a head turn) changes frames gradually; a hard cut is ONE
    big jump between two calm stretches. The calm stretches are measured 2 frames apart (not 1)
    because the source footage is 15fps doubled to 30, so every other frame is an exact duplicate."""
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    g = []
    while True:
        ok, frame = cap.read()
        if not ok:
            break
        g.append(cv2.cvtColor(cv2.resize(frame, (108, 192)), cv2.COLOR_BGR2GRAY).astype(np.float32))
    cap.release()
    n = len(g)

    def d(i: int, j: int) -> float:
        return float(np.mean(np.abs(g[i] - g[j]))) if 0 <= i < n and 0 <= j < n else 0.0

    cuts = []
    for i in range(1, n):
        jump = d(i, i - 1)
        if jump <= CUT_DIFF:
            continue
        calm = max(d(i - 1, i - 3), d(i + 2, i), 1.0)
        if jump > CUT_RATIO * calm and (not cuts or i / fps - cuts[-1] > 2.5 / fps):
            cuts.append(i / fps)
    return cuts, n / fps


def check_cut_rhythm(video_path: str, ignore_spans: list | None = None) -> dict:
    """ignore_spans: [(start, end)] clip-relative; cuts inside them (a meme's own edit) are not counted."""
    cuts, dur = find_cuts(video_path)
    cuts = [c for c in cuts if not any(a - 0.05 <= c <= b + 0.05 for a, b in (ignore_spans or []))]
    edges = [0.0] + cuts + [dur]
    short = [(edges[k], edges[k + 1]) for k in range(len(edges) - 1) if edges[k + 1] - edges[k] < MIN_SHOT]
    bursts = []
    for c in cuts:
        n = sum(1 for d in cuts if c <= d < c + BURST_WINDOW)
        if n > BURST_MAX_CUTS and not (bursts and c < bursts[-1][1]):
            bursts.append((c, c + BURST_WINDOW, n))
    return {"cuts": cuts, "duration": dur, "short_shots": short, "bursts": bursts}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    r = check_cut_rhythm(ap.parse_args().video)
    print(f"{len(r['cuts'])} hard cuts in {r['duration']:.1f}s: " + ", ".join(f"{c:.1f}" for c in r["cuts"]))
    for a, b in r["short_shots"]:
        print(f"  flash shot {a:.2f}-{b:.2f}s ({b - a:.2f}s)")
    for a, b, n in r["bursts"]:
        print(f"  burst of {n} cuts in {a:.1f}-{b:.1f}s")


if __name__ == "__main__":
    main()
