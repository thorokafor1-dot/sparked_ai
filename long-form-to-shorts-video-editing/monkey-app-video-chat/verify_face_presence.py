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

NORMAL_SCORE = 0.6     # reframe's detector threshold; restored after the loose pass
LOOSE_SCORE = 0.4
LOOSE_MIN_FACE_FRAC = 0.25


def check_face_presence(
    video_path: str, sample_interval: float = 0.15, min_face_frac: float = 0.04, drop_occlusion: bool = True
) -> list[dict]:
    """Returns a list of {start, end, duration} spans where no face at all
    was detected in the rendered frame. min_face_frac is a floor on face
    width relative to frame width -- rejects a tiny/spurious detection
    (e.g. a decorative circular bead on the headboard) that technically
    passes the detector's own confidence threshold but is too small to be
    an actual on-screen subject.

    drop_occlusion: a span where the face is still there but the detector can't see it (a hand over the
    mouth mid-laugh, motion blur) is not a lost crop. Told apart from a real loss by continuity: there is
    no hard cut inside the span AND the face reappears in the same place it left. A real loss changes
    the framing (a cut to a wrong crop) or the face returns somewhere else."""
    detector = _get_detector()
    cap = cv2.VideoCapture(video_path)
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / cap.get(cv2.CAP_PROP_FPS)

    empty_spans = []
    span_start = None
    last_cx = None       # face centre x just before the current empty span
    span_prev_cx = None
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
        big = [f for f in faces if f[2] >= frame_w * min_face_frac] if faces is not None else []
        if not big:
            # A close-up mid-laugh (hand over the mouth, motion blur) drops YuNet's confidence under its
            # normal threshold although the face fills the frame. A second, looser pass only counts a
            # LARGE candidate, so an empty wall or poster still reads as no subject.
            detector.setScoreThreshold(LOOSE_SCORE)
            _, loose = detector.detect(frame)
            detector.setScoreThreshold(NORMAL_SCORE)
            big = [f for f in loose if f[2] >= frame_w * LOOSE_MIN_FACE_FRAC] if loose is not None else []
        if not big:
            if span_start is None:
                span_start, span_prev_cx = t, last_cx
        else:
            cx = float(max(big, key=lambda f: f[2] * f[3])[0] + max(big, key=lambda f: f[2] * f[3])[2] / 2)
            if span_start is not None:
                empty_spans.append({"start": span_start, "end": t, "duration": t - span_start,
                                    "prev_cx": span_prev_cx, "next_cx": cx})
                span_start = None
            last_cx = cx
        t += sample_interval
    if span_start is not None:
        empty_spans.append({"start": span_start, "end": duration, "duration": duration - span_start,
                            "prev_cx": span_prev_cx, "next_cx": None})
    cap.release()
    if drop_occlusion and empty_spans:
        from verify_cuts import find_cuts
        cuts, _ = find_cuts(video_path)
        empty_spans = [
            sp for sp in empty_spans
            if not (sp["prev_cx"] is not None and sp["next_cx"] is not None
                    and abs(sp["prev_cx"] - sp["next_cx"]) < 0.3 * frame_w
                    and not any(sp["start"] - sample_interval <= c <= sp["end"] + sample_interval for c in cuts))
        ]
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
