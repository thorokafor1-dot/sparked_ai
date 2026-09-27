"""Self-review check: run face detection directly against the RENDERED
OUTPUT (not the source), at fine time resolution, and flag every stretch
where no face is visible in the final crop. This is the actual bug pattern
reported repeatedly ("no subject in focus") -- it's a property of the
finished frame, not of any one intermediate signal (state, position,
smoothing) upstream of it, and checking it directly here catches the bug
regardless of which upstream mechanism caused it, including ones not
anticipated yet. Complements verify_transitions.py (which checks state
*boundaries*): this checks continuously across the whole clip, dense enough
to catch anything on screen for longer than a few tenths of a second.

Usage:
    python verify_face_presence.py --video output/short_1_v19.mp4
"""
import argparse

import cv2

from reframe import _get_detector


def check_face_presence(video_path: str, sample_interval: float = 0.15, min_face_frac: float = 0.04) -> list[dict]:
    """Returns a list of {start, end, duration} spans where no face at all
    was detected in the rendered frame. min_face_frac is a floor on face
    width relative to frame width -- rejects a tiny/spurious detection
    (e.g. a decorative circular bead on the headboard) that technically
    passes the detector's own confidence threshold but is too small to be
    an actual on-screen subject."""
    detector = _get_detector()
    cap = cv2.VideoCapture(video_path)
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)

    empty_spans = []
    span_start = None
    t = 0.0
    while t < duration:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            t += sample_interval
            continue
        h, w = frame.shape[:2]
        detector.setInputSize((w, h))
        _, faces = detector.detect(frame)
        has_face = faces is not None and any(f[2] >= frame_w * min_face_frac for f in faces)
        if not has_face:
            if span_start is None:
                span_start = t
        else:
            if span_start is not None:
                empty_spans.append({"start": span_start, "end": t, "duration": t - span_start})
                span_start = None
        t += sample_interval
    if span_start is not None:
        empty_spans.append({"start": span_start, "end": duration, "duration": duration - span_start})
    cap.release()
    return empty_spans


def main() -> None:
    parser = argparse.ArgumentParser(description="Flag rendered-output spans with no face on screen.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--sample-interval", type=float, default=0.15)
    parser.add_argument("--min-flag-duration", type=float, default=0.2, help="ignore spans shorter than this")
    args = parser.parse_args()

    spans = check_face_presence(args.video, sample_interval=args.sample_interval)
    flagged = [s for s in spans if s["duration"] >= args.min_flag_duration]
    if not flagged:
        print("No no-face spans found.")
        return
    print(f"{len(flagged)} no-face span(s) >= {args.min_flag_duration}s:")
    for s in flagged:
        print(f"  {s['start']:.2f}s - {s['end']:.2f}s  ({s['duration']:.2f}s)")


if __name__ == "__main__":
    main()
