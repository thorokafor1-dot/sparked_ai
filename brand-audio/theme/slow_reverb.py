"""Slowed + reverb: pitch-and-tempo down, lush hall reverb, loudness-matched MP3.

Usage:  python slow_reverb.py IN.mp3 [OUT.mp3] [--rate 0.88] [--wet 0.4] [--decay 2.6] [--seconds 30]
"""
import argparse
import subprocess

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

SR = 44100


def make_ir(decay, seed=3):
    rng = np.random.default_rng(seed)
    n = int(decay * 1.3 * SR)
    t = np.arange(n) / SR
    ir = rng.standard_normal((n, 2)) * np.exp(-t * 6.9 / decay)[:, None]
    ir = sosfilt(butter(2, 6000, "lowpass", fs=SR, output="sos"), ir, axis=0)
    ir = np.concatenate([np.zeros((int(0.03 * SR), 2)), ir])
    return ir / np.sqrt(np.sum(ir**2) / 2)


def slow_reverb(inp, out, rate=0.88, wet=0.4, decay=2.6, seconds=30.0):
    raw = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", inp, "-af", f"aresample={SR},asetrate={SR}*{rate},aresample={SR}",
                          "-ac", "2", "-f", "f32le", "-"], capture_output=True, check=True).stdout
    x = np.frombuffer(raw, np.float32).reshape(-1, 2).astype(np.float64)
    ir = make_ir(decay)
    rev = np.stack([fftconvolve(x[:, c], ir[:, c])[: len(x)] for c in range(2)], 1)
    rev = sosfilt(butter(2, 200, "highpass", fs=SR, output="sos"), rev, axis=0)  # keep low end tight
    y = x * (1 - wet * 0.5) + rev * wet * np.max(np.abs(x)) / (np.max(np.abs(rev)) + 1e-9)
    y = y / (np.max(np.abs(y)) + 1e-9) * 0.9
    af = f"atrim=0:{seconds},afade=t=out:st={seconds - 3}:d=3,alimiter=limit=0.5:level=false,loudnorm=I=-14:TP=-1"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "f32le", "-ar", str(SR), "-ac", "2", "-i", "-",
                    "-af", af, "-ar", str(SR), "-b:a", "320k", out], input=y.astype(np.float32).tobytes(), check=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("inp")
    ap.add_argument("out", nargs="?")
    ap.add_argument("--rate", type=float, default=0.88)
    ap.add_argument("--wet", type=float, default=0.4)
    ap.add_argument("--decay", type=float, default=2.6)
    ap.add_argument("--seconds", type=float, default=30)
    a = ap.parse_args()
    out = a.out or a.inp.rsplit(".", 1)[0] + "_slowrev.mp3"
    slow_reverb(a.inp, out, a.rate, a.wet, a.decay, a.seconds)
    print("wrote", out)
