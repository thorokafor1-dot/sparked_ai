"""Word-level transcription of the raw footage (faster-whisper, CPU)."""
import json, sys, time
from faster_whisper import WhisperModel

model = WhisperModel("small.en", device="cpu", compute_type="int8", cpu_threads=8)
segs, info = model.transcribe("work/audio16k.wav", word_timestamps=True, vad_filter=True,
                              vad_parameters={"min_silence_duration_ms": 400}, beam_size=5)
out, t0 = [], time.time()
for s in segs:
    out.append({"start": s.start, "end": s.end, "text": s.text.strip(),
                "words": [{"w": w.word, "s": w.start, "e": w.end, "p": w.probability} for w in s.words]})
    print(f"{s.start:7.1f} {s.text.strip()[:80]}", flush=True)
json.dump(out, open("work/transcript.json", "w"), indent=1)
print("DONE", len(out), "segments", round(time.time() - t0), "s")
