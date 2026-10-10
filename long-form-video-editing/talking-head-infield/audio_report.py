"""Objective voice-recording quality report, to compare mic takes.

Usage:
    python audio_report.py <file> [<file> ...]
Measures what you'd otherwise judge by ear: noise floor / signal-to-noise, loudness and
dynamics, clipping, tonal balance (rumble, mud, presence, sibilance), mains hum, how
aggressive the noise gate is, and the usable bandwidth (a ~4kHz ceiling = phone-quality capture path).
"""

import json
import subprocess
import sys

import numpy as np

SR = 48000
FRAME = 0.05  # seconds per analysis frame


def decode(path: str) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.float32)


def loudness(path: str) -> dict:
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", path, "-af", "loudnorm=print_format=json",
                          "-f", "null", "-"], capture_output=True, text=True).stderr
    j = json.loads(err[err.rindex("{"):err.rindex("}") + 1])
    return {"lufs": float(j["input_i"]), "lra": float(j["input_lra"]), "true_peak": float(j["input_tp"])}


def report(path: str) -> dict:
    x = decode(path)
    n = int(SR * FRAME)
    frames = x[:len(x) // n * n].reshape(-1, n)
    rms_db = 20 * np.log10(np.sqrt((frames ** 2).mean(1)) + 1e-10)
    zcr = (np.abs(np.diff(np.sign(frames), axis=1)) > 0).mean(1)

    gated = rms_db < -120  # true digital silence: the recorder's noise gate/suppression closed
    speech = rms_db > np.percentile(rms_db[~gated], 60) if (~gated).any() else rms_db > -40
    live = ~gated & ~speech
    noise_floor = float(np.percentile(rms_db[live], 20)) if live.any() else float("nan")
    speech_level = float(np.percentile(rms_db[speech], 50))

    # tonal balance on speech frames, dB relative to the 300-1k core of the voice
    spec = np.zeros(n // 2 + 1)
    for f in frames[speech][:: max(1, speech.sum() // 2000)]:
        spec += np.abs(np.fft.rfft(f * np.hanning(n))) ** 2
    freqs = np.fft.rfftfreq(n, 1 / SR)

    def band(lo, hi):
        return 10 * np.log10(spec[(freqs >= lo) & (freqs < hi)].sum() + 1e-12)

    core = band(300, 1000)
    bands = {name: round(band(lo, hi) - core, 1) for name, (lo, hi) in {
        "rumble <80Hz": (20, 80), "body/mud 100-300": (100, 300), "presence 2-5k": (2000, 5000),
        "sibilance 5-9k": (5000, 9000), "air 9-16k": (9000, 16000)}.items()}

    # mains hum: 60/120/180Hz vs their neighbourhood in the non-speech frames
    hum = None
    if live.any():
        nspec = sum(np.abs(np.fft.rfft(f * np.hanning(n))) ** 2 for f in frames[live][:400])
        ratios = []
        for h in (60, 120, 180):
            k = np.argmin(abs(freqs - h))
            ratios.append(10 * np.log10(nspec[k] / (np.median(nspec[k - 8:k + 9]) + 1e-12)))
        hum = round(float(max(ratios)), 1)

    clip = float((np.abs(x) >= 0.999).mean() * 100)
    peak = 10 * np.log10(spec[(freqs > 200) & (freqs < 2000)].max() + 1e-12)
    spec_db = 10 * np.log10(spec + 1e-12)
    bandwidth = int(next((freqs[i] for i in range(len(freqs) - 1, 0, -1) if spec_db[i] > peak - 60), 0))
    return {"file": path, "minutes": round(len(x) / SR / 60, 1), **loudness(path),
            "speech_level_db": round(speech_level, 1), "noise_floor_db": round(noise_floor, 1),
            "snr_db": round(speech_level - noise_floor, 1), "gated_pct": round(float(gated.mean() * 100), 1),
            "clipped_pct": round(clip, 4), "usable_bandwidth_hz": bandwidth, "tonal_balance_vs_300_1k": bands, "hum_peak_db": hum}


if __name__ == "__main__":
    for p in sys.argv[1:]:
        print(json.dumps(report(p), indent=1))
