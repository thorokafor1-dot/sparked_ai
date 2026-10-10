"""Checks for generated music (brand-audio/: theme song, beds).

Catches beats that are painful to listen to before the user hears them: too much
energy in the ear-piercing presence/air range (shrill, hissy, "ear rape") and
loudness outside the streaming range.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

import numpy as np

from checks import check

MUSIC = ["brand-audio/*/out/*.mp3", "brand-audio/*/out/*.wav"]
EXCLUDE = ["brand-audio/*/out/_*"]  # scratch/intermediate files

SR = 32000
MAX_BRIGHT_SHARE = 0.30   # share of spectral energy above 1.5 kHz; good R&B takes measured 10-18%,
                          # the shrill v7 takes the user called "ear rape" measured 31-75%
LUFS_RANGE = (-17.0, -11.0)


def _decode(path: Path) -> np.ndarray:
    pcm = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(path), "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(pcm, np.float32)


def bright_share(x: np.ndarray) -> float:
    """Mean per-frame share of energy above 1.5 kHz, skipping the first 1s and last 2s (fades)."""
    x = x[SR:-2 * SR]
    x = x[: len(x) // 2048 * 2048]
    if len(x) == 0:
        return 0.0
    spec = np.abs(np.fft.rfft(x.reshape(-1, 2048) * np.hanning(2048), axis=1)) ** 2
    freqs = np.fft.rfftfreq(2048, 1 / SR)
    return float((spec[:, freqs > 1500].sum(1) / (spec.sum(1) + 1e-12)).mean())


@check("music-harshness", level="full", exts={".mp3", ".wav"}, paths=MUSIC, exclude=EXCLUDE, cache=True)
def music_harshness(path: Path) -> list[str]:
    share = bright_share(_decode(path))
    if share > MAX_BRIGHT_SHARE:
        return [f"shrill/harsh: {share:.0%} of energy above 1.5 kHz (max {MAX_BRIGHT_SHARE:.0%}); "
                "discard the take, don't EQ-rescue it"]
    return []


@check("music-loudness", level="full", exts={".mp3", ".wav"}, paths=MUSIC, exclude=EXCLUDE, cache=True)
def music_loudness(path: Path) -> list[str]:
    log = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(path), "-af", "ebur128", "-f", "null", "-"],
                         capture_output=True, text=True).stderr
    lines = [ln for ln in log.splitlines() if ln.strip().startswith("I:")]
    if not lines:
        return ["could not measure loudness"]
    lufs = float(lines[-1].split()[1])
    lo, hi = LUFS_RANGE
    if not lo <= lufs <= hi:
        return [f"loudness {lufs:.1f} LUFS outside {lo}..{hi} (target -14)"]
    return []
