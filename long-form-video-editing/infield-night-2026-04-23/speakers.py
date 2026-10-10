"""Tag who says each caption phrase (ME = the creator on the lav mic, HER = the women), for split-colour captions.

The lav records everyone close by, so loudness can't tell speakers apart and pitch alone was right ~70% of the time.
Each phrase (words split at pauses > 0.3 s) is scored on two signals:
  - voice similarity to his profile (Resemblyzer embedding, profile = mean of his clearly low-pitched sentences)
  - median pitch (his voice ~100-165 Hz, theirs ~170-300 Hz)
Writes work/speakers.json: [[start, end, "ME"|"HER", score, text], ...] for every phrase in the kept clips.
SPEAKER_FIX in build_edit.py overrides phrases by start time after review.

Usage: python speakers.py   (after build_edit.py; reads edit.json and work/transcript.json)
"""
import json
from pathlib import Path

import numpy as np

import diarize as d

ROOT = Path(__file__).parent
GAP = 0.3


def main():
    from resemblyzer import VoiceEncoder
    x = d.load()
    enc = VoiceEncoder("cpu", verbose=False)
    words = sorted((w for s in json.load(open(ROOT / "work/transcript.json", encoding="utf-8")) for w in s["words"]),
                   key=lambda w: w["s"])
    edit = json.load(open(ROOT / "edit.json", encoding="utf-8"))
    clips = [p for p in edit["pieces"] if p["type"] == "clip"]

    def emb(a, b):
        s = x[int(a * 16000):int(b * 16000)]
        return enc.embed_utterance(s.astype(np.float32)) if len(s) >= 16000 * 0.45 else None

    def f0(ws):
        f = [v for v in (d.pitch(x, w["s"], w["e"]) for w in ws) if v]
        return float(np.median(f)) if f else 0.0

    phrases = []
    for p in clips:
        ws = [w for w in words if p["in"] - 0.06 <= w["s"] < p["out"] - 0.05]
        cur = []
        for w in ws:
            if cur and (w["s"] - cur[-1]["e"] > GAP or cur[-1]["w"].strip()[-1:] in ".?!"):
                phrases.append(cur)
                cur = []
            cur.append(w)
        if cur:
            phrases.append(cur)
    # his voice profile: long phrases that are clearly low-pitched
    feats = [(ph, f0(ph), emb(ph[0]["s"], ph[-1]["e"])) for ph in phrases]
    seed = [e for ph, f, e in feats if e is not None and 0 < f < 155 and ph[-1]["e"] - ph[0]["s"] > 1.0]
    me = np.mean(seed, axis=0)
    me /= np.linalg.norm(me)
    out = []
    for ph, f, e in feats:
        sim = float(e @ me) if e is not None else None
        score = 0.0
        if sim is not None:
            score += (sim - 0.70) * 5          # 0.80 sim -> +0.5, 0.60 -> -0.5
        if f:
            score += (172 - f) / 40            # 132 Hz -> +1, 212 Hz -> -1
        out.append([round(ph[0]["s"], 2), round(ph[-1]["e"], 2), "ME" if score > 0 else "HER", round(score, 2),
                    " ".join(w["w"].strip() for w in ph)])
    (ROOT / "work/speakers.json").write_text(json.dumps(out, indent=0), encoding="utf-8")
    print(f"{len(out)} phrases, profile from {len(seed)} of his phrases")
    for a, b, spk, sc, t in out:
        print(f"{a:8.2f} {spk:3} {sc:+5.2f} {t}")


if __name__ == "__main__":
    main()
