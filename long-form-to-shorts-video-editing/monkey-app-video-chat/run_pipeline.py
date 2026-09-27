"""End-to-end: source video + one or more girl segments (start:end seconds) ->
finished captioned Shorts in output/. This is the test entrypoint for running
just the first 2 girls, per --segment.

Usage:
    python run_pipeline.py --video input/X.mp4 --segment 0:45 --segment 45:110
    python run_pipeline.py --video input/X.mp4 --auto 6   # Claude picks the 6 best moments (find_moments.py)
"""
import argparse
import json
import re
from pathlib import Path

from analyze_hooks import find_best_hook
from find_moments import find_moments
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
    parser.add_argument("--segment", action="append", help="start:end in seconds, repeatable")
    parser.add_argument("--auto", type=int, metavar="N", help="transcribe the whole call and render Claude's N best moments")
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

    if not (args.auto or args.segment):
        parser.error("pass --segment start:end (repeatable) or --auto N")
    segments = [parse_segment(s) for s in args.segment or []]

    # a manual run's transcript only covers its segments, so --auto keeps its own whole-call transcript
    transcript_path = WORK_DIR / f"{video_path.stem}{'_full' if args.auto else ''}_transcript.json"
    if not transcript_path.exists():
        # --auto needs the whole call; a manual run only decodes the requested segments
        words = transcribe(str(video_path), args.model_size, clip_ranges=None if args.auto else segments)
        transcript_path.write_text(json.dumps(words, indent=2), encoding="utf-8")
    else:
        print(f"Reusing existing transcript: {transcript_path}")

    if args.auto:
        moments = find_moments(json.loads(transcript_path.read_text(encoding="utf-8")), args.auto)
        (WORK_DIR / f"{video_path.stem}_moments.json").write_text(json.dumps(moments, indent=1), encoding="utf-8")
        # number after the existing shorts so an auto run never overwrites earlier work
        first = 1 + max((int(m.group(1)) for f in OUTPUT_DIR.glob("short_*.mp4") if (m := re.match(r"short_(\d+)", f.stem))), default=0)
        for i, m in enumerate(moments, start=first):
            out_path = OUTPUT_DIR / f"short_{i}_v1.mp4"
            print(f"Moment {i} (score {m['score']}): [{m['start']}-{m['end']}] {m['why']} -> {out_path}")
            # the moment already starts on its hook and ends on its payoff, so no hook re-scan or fixed duration
            render(str(video_path), m["start"], m["end"] - m["start"], str(transcript_path), str(out_path))

    for i, (seg_start, seg_end) in enumerate(segments, start=1):
        words = json.loads(transcript_path.read_text(encoding="utf-8"))
        hook_start = find_best_hook(words, str(video_path), seg_start, seg_end, window=args.hook_window)
        out_path = OUTPUT_DIR / f"short_{i}.mp4"
        print(f"Segment {i}: [{seg_start}-{seg_end}] -> hook at {hook_start:.2f}s -> {out_path}")
        render(str(video_path), hook_start, args.duration, str(transcript_path), str(out_path))

    print(f"Done. {len(segments) + (len(moments) if args.auto else 0)} short(s) in {OUTPUT_DIR}")

    input_dir = Path(__file__).parent / "input"
    if not args.keep_source and input_dir in video_path.resolve().parents:
        video_path.unlink(missing_ok=True)
        print(f"Deleted downloaded source video ({video_path.name}) -- pass --keep-source to retain it")


if __name__ == "__main__":
    main()
