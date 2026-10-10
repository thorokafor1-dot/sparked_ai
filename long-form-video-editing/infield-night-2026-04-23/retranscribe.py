"""Re-transcribe only the source ranges used in edit.json with a larger model, for caption accuracy.

Replaces the small.en words inside those ranges in work/transcript.json (backup kept as
work/transcript_small.json).
"""
import json
import shutil
import wave

import numpy as np
from faster_whisper import WhisperModel

PAD, SR = 0.6, 16000
edit = json.load(open("edit.json", encoding="utf-8"))
rngs = sorted((p["in"] - PAD, p["out"] + PAD) for p in edit["pieces"] if p["type"] == "clip")
merged = []
for a, b in rngs:
    if merged and a - merged[-1][1] < 2.0:
        merged[-1][1] = max(merged[-1][1], b)
    else:
        merged.append([a, b])

with wave.open("work/audio16k.wav") as w:
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768

if not __import__("os").path.exists("work/transcript_small.json"):
    shutil.copy("work/transcript.json", "work/transcript_small.json")
segs = json.load(open("work/transcript_small.json", encoding="utf-8"))

model = WhisperModel("medium.en", device="cpu", compute_type="int8", cpu_threads=8)
new_segs = []
for i, (a, b) in enumerate(merged):
    audio = x[int(max(a, 0) * SR):int(b * SR)]
    out, _ = model.transcribe(audio, word_timestamps=True, beam_size=5, condition_on_previous_text=False)
    for s in out:
        ws = [{"w": w.word, "s": a + w.start, "e": a + w.end, "p": w.probability} for w in s.words]
        ws = [w for w in ws if a + 0.3 <= (w["s"] + w["e"]) / 2 < b - 0.3]   # drop edge words cut mid-way
        if ws:
            new_segs.append({"start": ws[0]["s"], "end": ws[-1]["e"], "text": s.text.strip(), "words": ws, "hq": True})
    print(f"{i + 1}/{len(merged)} {a:.1f}-{b:.1f}", flush=True)


def inside(t):
    return any(a + 0.3 <= t < b - 0.3 for a, b in merged)


for s in segs:
    s["words"] = [w for w in s["words"] if not inside((w["s"] + w["e"]) / 2)]
segs = [s for s in segs if s["words"]] + new_segs
segs.sort(key=lambda s: s["words"][0]["s"])
json.dump(segs, open("work/transcript.json", "w", encoding="utf-8"), indent=1)
print("DONE", len(merged), "ranges")
