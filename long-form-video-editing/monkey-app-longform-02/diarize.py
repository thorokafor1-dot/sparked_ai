"""Tag each transcript word as ME (male voice) or HER (female voice) by median pitch.

Monkey records both sides into one mixed track, so pitch is the cheapest reliable split:
the creator's voice sits ~90-160 Hz, the women's ~170-300 Hz.
"""
import json
import sys
import wave

import numpy as np

SR = 16000
SPLIT_HZ = 165


def load():
    with wave.open("work/audio16k.wav") as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768


def f0_track(x, hop=0.01, win=0.04, fmin=70, fmax=400):
    n, h = int(win * SR), int(hop * SR)
    lo, hi = SR // fmax, SR // fmin
    frames = np.lib.stride_tricks.sliding_window_view(x, n)[::h]
    out = np.zeros(len(frames))
    for i, fr in enumerate(frames):
        fr = fr - fr.mean()
        e = fr @ fr
        if e < 1e-4:
            continue
        ac = np.correlate(fr, fr, "full")[n - 1:] / e
        lag = lo + np.argmax(ac[lo:hi])
        if ac[lag] > 0.5:
            out[i] = SR / lag
    return out


def pitch(x, s, e):
    if e - s < 0.06:
        s, e = s - 0.03, e + 0.03
    f = f0_track(x[max(int(s * SR), 0):int(e * SR)])
    f = f[f > 0]
    return float(np.median(f)) if len(f) >= 3 else None


def main():
    x = load()
    if len(sys.argv) > 1:   # quick test: python diarize.py START END
        print(pitch(x, float(sys.argv[1]), float(sys.argv[2])))
        return
    segs = json.load(open("work/transcript.json", encoding="utf-8"))
    for seg in segs:
        for w in seg["words"]:
            w["f0"] = pitch(x, w["s"], w["e"])
        f = [w["f0"] for w in seg["words"] if w["f0"]]
        seg["f0"] = float(np.median(f)) if f else None
        seg["spk"] = "?" if not f else ("ME" if seg["f0"] < SPLIT_HZ else "HER")
    json.dump(segs, open("work/transcript.json", "w", encoding="utf-8"), indent=1)
    with open("work/transcript.txt", "w", encoding="utf-8") as fh:
        for seg in segs:
            fh.write(f"{seg['start']:7.1f}-{seg['end']:6.1f} {seg['spk']:3} {seg['f0'] or 0:4.0f} {seg['text']}\n")
    print("tagged", len(segs))


if __name__ == "__main__":
    main()
