"""Self-review helper: every real bug found this session was hiding in a
sub-second window right at a crop-plan state transition (a cutaway ending, a
settle window resolving, a split starting/ending) -- never in the steady
middle of a chunk. A coarse 1-2fps contact sheet of the whole clip missed
all of them; they only ever surfaced by densely extracting frames around one
specific boundary after being pointed at it. This makes that the default,
automatic first check instead of a manual step that's easy to skip.

Re-derives the same crop plan render() used (same source video/start/
duration/transcript-independent detection logic), finds every boundary
between consecutive plan entries, and dumps a tiled contact sheet of dense
(1/10s) frames spanning each one, saved next to the rendered output.

Usage:
    python verify_transitions.py --video OUT.mp4 --src input/X.mp4 \
        --start 104.0 --duration 30.0 --out-dir work/verify
"""
import argparse
import subprocess
from pathlib import Path

from PIL import Image

from reframe import detect_regions_over_time, smooth_positions, smooth_states
from render_short import _build_crop_plan


def _extract_frame(video_path: str, t: float, out_path: Path) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-ss", f"{t:.3f}", "-i", video_path, "-frames:v", "1", str(out_path)],
        check=True,
        capture_output=True,
    )


def _tile(frame_paths: list[Path], out_path: Path, thumb_w: int = 140) -> None:
    thumbs = []
    for p in frame_paths:
        img = Image.open(p)
        h = int(thumb_w * img.height / img.width)
        thumbs.append(img.resize((thumb_w, h)))
    if not thumbs:
        return
    cols = len(thumbs)
    h = thumbs[0].height
    sheet = Image.new("RGB", (thumb_w * cols, h))
    for i, t in enumerate(thumbs):
        sheet.paste(t, (i * thumb_w, 0))
    sheet.save(out_path)


def verify_transitions(
    rendered_video: str, source_video: str, start: float, duration: float, out_dir: str, window: float = 0.6
) -> list[str]:
    """Dumps one contact sheet per plan boundary. Returns the list of
    written contact-sheet paths for the caller to open and actually look
    at -- this only prepares the frames, it doesn't replace looking."""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    samples, _, _ = detect_regions_over_time(source_video, start, duration)
    samples = smooth_states(samples)
    samples = smooth_positions(samples)
    opening_end = start + 3.0
    plan = _build_crop_plan(samples, clip_start=start, clip_end=start + duration, opening_end=opening_end)

    sheets = []
    for i in range(1, len(plan)):
        boundary = plan[i][0] - start  # clip-relative
        prev_state, next_state = plan[i - 1][2], plan[i][2]
        t0 = max(0.0, boundary - window / 2)
        frame_paths = []
        n_steps = int(window / 0.1) + 1
        for step in range(n_steps):
            t = t0 + step * 0.1
            fp = out / f"b{i:02d}_{prev_state}_to_{next_state}_{step:02d}.png"
            _extract_frame(rendered_video, t, fp)
            frame_paths.append(fp)
        sheet_path = out / f"boundary_{i:02d}_{prev_state}_to_{next_state}.png"
        _tile(frame_paths, sheet_path)
        sheets.append(str(sheet_path))
        for fp in frame_paths:
            fp.unlink()

    return sheets


def main() -> None:
    parser = argparse.ArgumentParser(description="Dense contact sheets at every crop-plan transition boundary.")
    parser.add_argument("--video", required=True, help="the rendered short to sample frames from")
    parser.add_argument("--src", required=True, help="the original source video (for re-deriving the crop plan)")
    parser.add_argument("--start", type=float, required=True)
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()
    sheets = verify_transitions(args.video, args.src, args.start, args.duration, args.out_dir)
    print(f"Wrote {len(sheets)} boundary contact sheets:")
    for s in sheets:
        print(f"  {s}")


if __name__ == "__main__":
    main()
