"""Recover quiet lines (mostly the women: the lav is on him) that medium.en skipped in the kept clips.

Each kept clip is re-transcribed with medium.en on level-evened audio (ffmpeg dynaudnorm, vad off). Only words that
land in a gap of the existing transcript (no existing word within 0.15 s) and that the model is reasonably sure of
(probability >= MIN_P) are added, marked "fill": true. Prints every added run for review before rendering.

Usage: python fill_quiet.py   (after build_edit.py; rewrites work/transcript.json, backup work/transcript_prefill.json)
"""
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).parent
MIN_P = 0.6


def main():
    from faster_whisper import WhisperModel
    tp = ROOT / "work/transcript.json"
    backup = ROOT / "work/transcript_prefill.json"
    if not backup.exists():
        shutil.copy(tp, backup)
    segs = [sg for sg in json.load(open(backup, encoding="utf-8"))]
    have = sorted((w["s"], w["e"]) for sg in segs for w in sg["words"])
    edit = json.load(open(ROOT / "edit.json", encoding="utf-8"))
    clips = [p for p in edit["pieces"] if p["type"] == "clip"]
    model = WhisperModel("medium.en", device="cpu", compute_type="int8", cpu_threads=8)

    def free(a, b):
        return not any(s < b + 0.15 and e > a - 0.15 for s, e in have)

    added = []
    for p in clips:
        a, b = p["in"] - 0.3, p["out"] + 0.3
        raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(a, 0):.3f}", "-t", f"{b - a:.3f}", "-i",
                              str(ROOT / "raw/raw.mkv"), "-vn", "-af", "dynaudnorm=f=150:g=15:p=0.9",
                              "-ac", "1", "-ar", "16000", "-f", "f32le", "-"], capture_output=True).stdout
        x = np.frombuffer(raw, np.float32)
        out, _ = model.transcribe(x, word_timestamps=True, vad_filter=False, beam_size=5,
                                  condition_on_previous_text=False)
        run = []
        for sg in out:
            for w in sg.words:
                ws, we = a + w.start, a + w.end
                ok = p["in"] <= (ws + we) / 2 < p["out"] and w.probability >= MIN_P and free(ws, we)
                if ok:
                    run.append({"w": w.word, "s": ws, "e": we, "p": w.probability, "fill": True})
                elif run:
                    added.append(run)
                    run = []
        if run:
            added.append(run)
    # single stray words are usually noise read as speech; keep runs of 2+ words
    added = [r for r in added if len(r) >= 2]
    for r in added:
        segs.append({"start": r[0]["s"], "end": r[-1]["e"], "text": "".join(w["w"] for w in r).strip(), "words": r,
                     "fill": True})
        print(f"{r[0]['s']:8.2f} +{''.join(w['w'] for w in r)}")
    segs.sort(key=lambda sg: sg["words"][0]["s"])
    json.dump(segs, open(tp, "w", encoding="utf-8"), indent=1)
    print(f"added {sum(len(r) for r in added)} words in {len(added)} runs")


if __name__ == "__main__":
    main()
