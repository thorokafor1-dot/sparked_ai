"""Find where the external mic recording lines up with the camera audio.

Usage:
    python sync_mic.py
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


def best_lag(cam: np.ndarray, mic_win: np.ndarray) -> tuple[int, float]:
    corr = fftconvolve(cam, mic_win[::-1], mode="valid")
    i = int(np.argmax(corr))
    return i, float(corr[i] / (np.linalg.norm(mic_win) * np.linalg.norm(cam[i:i + len(mic_win)]) + 1e-9))


def main() -> None:
    cam, mic = envelope(decode(TALKING_HEAD)), envelope(decode(MIC))
    results = []
    for mic_start in range(30, int(len(mic) / SR) - 60, 120):
        win = mic[mic_start * SR:(mic_start + 30) * SR]
        lag, score = best_lag(cam, win)
        offset = lag / SR - mic_start
        results.append((mic_start, offset, score))
        print(f"mic {mic_start:4d}s -> offset {offset:+.3f}s (match {score:.2f})")

    good = [(t, o) for t, o, s in results if s > 0.3]
    t, o = np.array(good).T
    # offset(t) = offset + drift_per_sec * t, fitted so drift is corrected everywhere
    drift, intercept = np.polyfit(t, o, 1) if len(good) > 2 else (0.0, float(np.median(o)))
    sync = {"offset": float(intercept), "drift_per_sec": float(drift), "windows": len(good)}
    (HERE / "work" / "mic_sync.json").write_text(json.dumps(sync, indent=1))
    print(sync)


if __name__ == "__main__":
    main()
