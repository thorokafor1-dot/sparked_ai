"""Transcribes every .wav in input/<session>/ to work/<session>/<stem>.json
as a list of {start, end, text} segments. Segment-level (not word-level) is
enough for reading back a conversation for coaching review -- faster than
word-level timestamps.

Usage:
    python transcribe_all.py [--model-size small]
"""
import argparse
import json
from pathlib import Path

INPUT_DIR = Path(__file__).parent / "input"
WORK_DIR = Path(__file__).parent / "work"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-size", default="small")
    args = parser.parse_args()

    from faster_whisper import WhisperModel

    model = WhisperModel(args.model_size, device="cpu", compute_type="int8")

    wav_files = sorted(INPUT_DIR.glob("*/*.wav"))
    for wav_path in wav_files:
        session = wav_path.parent.name
        out_dir = WORK_DIR / session
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / f"{wav_path.stem}.json"
        if out_path.exists():
            print(f"Skipping (already transcribed): {out_path}")
            continue

        print(f"Transcribing {wav_path} ...")
        segments, _info = model.transcribe(str(wav_path), vad_filter=True)
        result = [
            {"start": round(seg.start, 2), "end": round(seg.end, 2), "text": seg.text.strip()}
            for seg in segments
        ]
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"Wrote {len(result)} segments to {out_path}")

    print("All done.")


if __name__ == "__main__":
    main()
