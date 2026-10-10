"""Transcribe extra raw parts and merge them into work/transcript.json on the combined raw/raw.mkv timeline.

Usage: python transcribe_parts.py   (reads raw/parts.txt; part 1's transcript is reused from work/transcript_part1.json)
Multi-file videos: the user sometimes sends 2-3 raw recordings; they're concatenated into raw/raw.mkv so every
other script works on one timeline.
"""
import json
import subprocess
from pathlib import Path

from faster_whisper import WhisperModel

parts = [l.split("'")[1] for l in open("raw/parts.txt") if l.strip()]
offset, merged = 0.0, []
model = None
for i, name in enumerate(parts, 1):
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                f"raw/{name}"], capture_output=True, text=True).stdout)
    cache = Path(f"work/transcript_part{i}.json")
    if cache.exists():
        segs = json.load(open(cache, encoding="utf-8"))
        if i > 1:   # cached parts are stored on their own timeline
            segs = [{**s, "start": s["start"] + offset, "end": s["end"] + offset,
                     "words": [{**w, "s": w["s"] + offset, "e": w["e"] + offset} for w in s["words"]]} for s in segs]
    else:
        wav = f"work/part{i}_16k.wav"
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"raw/{name}", "-vn", "-ac", "1", "-ar", "16000", wav], check=True)
        model = model or WhisperModel("small.en", device="cpu", compute_type="int8", cpu_threads=8)
        out, _ = model.transcribe(wav, word_timestamps=True, vad_filter=True,
                                  vad_parameters={"min_silence_duration_ms": 400}, beam_size=5)
        own = [{"start": s.start, "end": s.end, "text": s.text.strip(),
                "words": [{"w": w.word, "s": w.start, "e": w.end, "p": w.probability} for w in s.words]} for s in out]
        json.dump(own, open(cache, "w", encoding="utf-8"), indent=1)
        segs = [{**s, "start": s["start"] + offset, "end": s["end"] + offset,
                 "words": [{**w, "s": w["s"] + offset, "e": w["e"] + offset} for w in s["words"]]} for s in own]
        print(f"part {i}: {len(own)} segments", flush=True)
    merged += segs
    offset += dur
json.dump(merged, open("work/transcript.json", "w", encoding="utf-8"), indent=1)
print("DONE", len(merged), "segments, combined", round(offset, 1), "s")
