"""Transcribes a video with local faster-whisper, producing word-level
timestamps used both for hook scoring (analyze_hooks.py) and for burning in
captions (captions.py). No API key needed -- runs entirely on-device.

Usage:
    python transcribe.py --video input/XXXX.mp4 --out work/XXXX_transcript.json
"""
import argparse
import json
from pathlib import Path

WORK_DIR = Path(__file__).parent / "work"


def transcribe(video_path: str, model_size: str = "small", clip_ranges: list[tuple[float, float]] | None = None) -> list[dict]:
    from faster_whisper import WhisperModel

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    kwargs = {}
    if clip_ranges:
        # Restricts decoding to just these windows (e.g. the segments we actually
        # need), so we don't burn time transcribing untouched parts of a long video.
        flat: list[float] = []
        for start, end in clip_ranges:
            flat += [start, end]
        kwargs["clip_timestamps"] = flat
    segments, _info = model.transcribe(video_path, word_timestamps=True, **kwargs)

    words = []
    for segment in segments:
        for word in segment.words:
            words.append({"text": word.word.strip(), "start": word.start, "end": word.end})
    return words


def main() -> None:
    parser = argparse.ArgumentParser(description="Transcribe a video with word-level timestamps.")
    parser.add_argument("--video", required=True, help="Path to the video file")
    parser.add_argument("--out", default=None, help="Output JSON path (default: work/<stem>_transcript.json)")
    parser.add_argument(
        "--model-size", default="small", help="faster-whisper model size (tiny/base/small/medium/large-v3)"
    )
    args = parser.parse_args()

    video_path = Path(args.video)
    out_path = Path(args.out) if args.out else WORK_DIR / f"{video_path.stem}_transcript.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"Transcribing {video_path} with faster-whisper ({args.model_size})...")
    words = transcribe(str(video_path), args.model_size)
    out_path.write_text(json.dumps(words, indent=2), encoding="utf-8")
    print(f"Wrote {len(words)} words to {out_path}")


if __name__ == "__main__":
    main()
