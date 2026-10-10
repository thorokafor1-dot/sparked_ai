"""Find where the external mic recording lines up with the camera audio.

Usage:
    python sync_mic.py                                   (the edl.py camera + mic)
    python sync_mic.py --cam <video> --mic <audio> --out work/<name>_sync.json   (any pair, e.g. a 2nd angle)
Prints the offset (camera time = mic time + offset) measured in several windows
across the recording, so any clock drift between the two devices shows up.
Writes work/mic_sync.json with the median offset and drift rate.
"""

import json
import subprocess
from pathlib import Path

import numpy as np
from scipy.signal import fftconvolve

from edl import MIC, TALKING_HEAD

HERE = Path(__file__).parent
SR = 4000


def decode(path: Path) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, dtype=np.float32)


def envelope(x: np.ndarray) -> np.ndarray:
    # onset-ish envelope: robust to the two mics having very different tone
    env = np.abs(x)
    env = np.convolve(env, np.ones(40) / 40, mode="same")
    env = np.diff(env, prepend=env[0]).clip(min=0)
    return (env - env.mean()) / (env.std() + 1e-9)


def mic_to_cam(t: float, sync: dict) -> float:
    """Mic time -> camera time. Uses the dense measured map when present: Sound Recorder takes can drop a
    fraction of a second mid-take, so one offset + drift line left take 2 ~0.4s out of sync near the start."""
    if sync.get("points"):
        m, o = np.array(sync["points"]).T
        return float(t + np.interp(t, m, o))
    return t + sync["offset"] + sync["drift_per_sec"] * t


def cam_to_mic(t: float, sync: dict) -> float:
    m = t - sync["offset"]
    for _ in range(4):  # invert mic_to_cam by fixed-point iteration (offset changes slowly)
        m = t - (mic_to_cam(m, sync) - m)
    return float(m)


def dense_points(cam: np.ndarray, mic: np.ndarray, step: int = 20, win: int = 20, search: float = 3.0, guess: float = 0.0):
    """Offset measured every `step` seconds of mic time, searched within +-`search`s of the line fit."""
    pts = []
    for ms in range(0, int(len(mic) / SR) - win, step):
        w = mic[ms * SR:(ms + win) * SR]
        c0 = int((ms + guess - search) * SR)
        lo = max(c0, 0)
        seg = cam[lo:int((ms + guess + search + win) * SR)]
        if len(seg) <= len(w):
            continue
        corr = fftconvolve(seg, w[::-1], mode="valid")
        i = int(np.argmax(corr))
        score = corr[i] / (np.linalg.norm(w) * np.linalg.norm(seg[i:i + len(w)]) + 1e-9)
        if score > 0.2:
            pts.append((ms + win / 2, (lo + i) / SR - ms, float(score)))
    if not pts:
        return []
    o = np.array([p[1] for p in pts])
    smooth = [float(np.median(o[max(0, k - 2):k + 3])) for k in range(len(o))]  # drop lone mismatches
    keep = [(p[0], s) for p, s, raw in zip(pts, smooth, o) if abs(raw - s) < 0.08]
    return keep


def best_lag(cam: np.ndarray, mic_win: np.ndarray) -> tuple[int, float]:
    corr = fftconvolve(cam, mic_win[::-1], mode="valid")
    i = int(np.argmax(corr))
    return i, float(corr[i] / (np.linalg.norm(mic_win) * np.linalg.norm(cam[i:i + len(mic_win)]) + 1e-9))


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--cam", default=str(TALKING_HEAD))
    ap.add_argument("--mic", default=str(MIC))
    ap.add_argument("--out", default="work/mic_sync.json")
    args = ap.parse_args()
    cam, mic = envelope(decode(Path(args.cam))), envelope(decode(Path(args.mic)))
    results = []
    for mic_start in range(30, int(len(mic) / SR) - 60, 120):
        win = mic[mic_start * SR:(mic_start + 30) * SR]
        lag, score = best_lag(cam, win)
        offset = lag / SR - mic_start
        results.append((mic_start, offset, score))
        print(f"mic {mic_start:4d}s -> offset {offset:+.3f}s (match {score:.2f})")

    # windows agree with each other when they're right; a lone outlier (e.g. pre-roll silence that
    # correlates with anything, scoring 0.93) is dropped by distance from the median, not by score
    med = float(np.median([o for _, o, s in results if s > 0.15]))
    good = [(t, o) for t, o, s in results if s > 0.15 and abs(o - med) < 0.5]
    t, o = np.array(good).T
    # offset(t) = offset + drift_per_sec * t, fitted so drift is corrected everywhere
    drift, intercept = np.polyfit(t, o, 1) if len(good) > 2 else (0.0, float(np.median(o)))
    sync = {"offset": float(intercept), "drift_per_sec": float(drift), "windows": len(good)}
    sync["points"] = [[round(m, 2), round(o, 4)] for m, o in dense_points(cam, mic, guess=float(intercept) + float(drift) * 600)]
    (HERE / args.out).write_text(json.dumps(sync, indent=1))
    print({k: v for k, v in sync.items() if k != "points"}, f"{len(sync['points'])} dense points")


if __name__ == "__main__":
    main()
