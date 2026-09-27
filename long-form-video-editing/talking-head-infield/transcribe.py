"""Word-level transcript of a talking-head or infield video, for cut planning.

Usage:
    python transcribe.py input/talking_head/P1040005.MP4 --out work/talking_head
Writes <out>_words.json (every word with start/end) and <out>.txt
(one timestamped line per segment, easy to read against the script).
"""

import argparse
import json
from pathlib import Path

HERE = Path(__file__).parent


def fmt(t: float) -> str:
    return f"{int(t // 60):02d}:{t % 60:05.2f}"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("video")
    parser.add_argument("--out", required=True, help="Output path prefix, relative to this folder")
    parser.add_argument("--model-size", default="small")
    args = parser.parse_args()

    from faster_whisper import WhisperModel

    model = WhisperModel(args.model_size, device="cpu", compute_type="int8")
    segments, _info = model.transcribe(str(HERE / args.video), word_timestamps=True, language="en")

    words, lines = [], []
    for seg in segments:
        lines.append(f"[{fmt(seg.start)} - {fmt(seg.end)}] {seg.text.strip()}")
        for w in seg.words:
            words.append({"text": w.word.strip(), "start": w.start, "end": w.end})
        print(lines[-1], flush=True)

    out = HERE / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.with_name(out.name + "_words.json").write_text(json.dumps(words, indent=1), encoding="utf-8")
    out.with_name(out.name + ".txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(words)} words, {len(lines)} segments to {out}*")


if __name__ == "__main__":
    main()
