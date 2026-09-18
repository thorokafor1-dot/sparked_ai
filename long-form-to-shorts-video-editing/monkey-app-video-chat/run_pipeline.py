"""End-to-end: source video + one or more girl segments (start:end seconds) ->
finished captioned Shorts in output/. This is the test entrypoint for running
just the first 2 girls, per --segment.

Usage:
    python run_pipeline.py --video input/X.mp4 --segment 0:45 --segment 45:110
"""
import argparse
import json
from pathlib import Path

from analyze_hooks import find_best_hook
from render_short import render
from transcribe import transcribe

WORK_DIR = Path(__file__).parent / "work"
OUTPUT_DIR = Path(__file__).parent / "output"


def parse_segment(s: str) -> tuple[float, float]:
    start, end = s.split(":")
    return float(start), float(end)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the full long-form -> Shorts pipeline for a test set of segments.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--segment", action="append", required=True, help="start:end in seconds, repeatable")
    parser.add_argument("--hook-window", type=float, default=3.0, help="seconds to scan for the strongest hook")
    parser.add_argument("--duration", type=float, default=30.0, help="length of each finished short")
    parser.add_argument("--model-size", default="small")
    parser.add_argument(
        "--keep-source", action="store_true",
        help="Keep the downloaded source video in input/ after rendering (default: delete it once shorts are rendered, so ~1GB Drive downloads don't pile up)",
    )
    args = parser.parse_args()

    video_path = Path(args.video)
    WORK_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    segments = [parse_segment(s) for s in args.segment]

    transcript_path = WORK_DIR / f"{video_path.stem}_transcript.json"
    if not transcript_path.exists():
        words = transcribe(str(video_path), args.model_size, clip_ranges=segments)
        transcript_path.write_text(json.dumps(words, indent=2), encoding="utf-8")
    else:
        print(f"Reusing existing transcript: {transcript_path}")

    for i, (seg_start, seg_end) in enumerate(segments, start=1):
        words = json.loads(transcript_path.read_text(encoding="utf-8"))
        hook_start = find_best_hook(words, str(video_path), seg_start, seg_end, window=args.hook_window)
        out_path = OUTPUT_DIR / f"short_{i}.mp4"
        print(f"Segment {i}: [{seg_start}-{seg_end}] -> hook at {hook_start:.2f}s -> {out_path}")
        render(str(video_path), hook_start, args.duration, str(transcript_path), str(out_path))

    print(f"Done. {len(args.segment)} short(s) in {OUTPUT_DIR}")

    input_dir = Path(__file__).parent / "input"
    if not args.keep_source and input_dir in video_path.resolve().parents:
        video_path.unlink(missing_ok=True)
        print(f"Deleted downloaded source video ({video_path.name}) -- pass --keep-source to retain it")


if __name__ == "__main__":
    main()
