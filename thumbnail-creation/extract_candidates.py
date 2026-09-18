"""Samples frames across a long-form source video and scores them for thumbnail
potential: face presence/size (closer face = stronger candidate) + a smile-detection
bonus as a rough proxy for visible reaction/expression, reusing the OpenCV approach
from long-form-to-shorts-video-editing/analyze_hooks.py. Writes the top-N distinct
candidates (spaced apart so they aren't all the same moment) to work/frames/.

Usage:
    python extract_candidates.py --video input/raw.mp4 --interval 2 --top-n 12
"""
import argparse
from pathlib import Path

import cv2

WORK_DIR = Path(__file__).parent / "work" / "frames"

FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
SMILE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_smile.xml")


def score_frame(frame) -> tuple[float, int]:
    """Returns (score, face_count). Score rewards a large, prominent face plus
    a visible smile/expression -- a small distant face scores near zero."""
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = FACE_CASCADE.detectMultiScale(gray, 1.3, 5)
    if len(faces) == 0:
        return 0.0, 0
    frame_area = frame.shape[0] * frame.shape[1]
    score = 0.0
    for (x, y, w, h) in faces:
        score += (w * h) / frame_area  # bigger face -> bigger share of score
        roi = gray[y : y + h, x : x + w]
        if len(SMILE_CASCADE.detectMultiScale(roi, 1.7, 20)) > 0:
            score += 0.5
    return score, len(faces)


def extract_candidates(video_path: str, interval: float, top_n: int, min_gap: float) -> list[Path]:
    cap = cv2.VideoCapture(video_path)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    duration = cap.get(cv2.CAP_PROP_FRAME_COUNT) / fps
    cap.release()

    scored = []
    t = 0.0
    while t < duration:
        cap = cv2.VideoCapture(video_path)
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        cap.release()
        if ok:
            score, face_count = score_frame(frame)
            if score > 0:
                scored.append((score, t, frame))
        t += interval

    scored.sort(key=lambda s: -s[0])
    chosen = []
    for score, t, frame in scored:
        if any(abs(t - c[1]) < min_gap for c in chosen):
            continue
        chosen.append((score, t, frame))
        if len(chosen) >= top_n:
            break

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    paths = []
    for score, t, frame in chosen:
        # PNG, not JPEG -- these frames get brightened significantly downstream
        # (dark night footage), and JPEG's block quantization noise becomes
        # very visible once lifted, especially after re-encoding at each
        # pipeline stage. Lossless here costs disk space, not quality.
        out_path = WORK_DIR / f"t{t:07.1f}_s{score:.2f}.png"
        cv2.imwrite(str(out_path), frame)
        paths.append(out_path)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract thumbnail-candidate frames from a video.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--interval", type=float, default=2.0, help="Seconds between sampled frames")
    parser.add_argument("--top-n", type=int, default=12)
    parser.add_argument("--min-gap", type=float, default=5.0, help="Minimum seconds between two chosen candidates")
    args = parser.parse_args()

    paths = extract_candidates(args.video, args.interval, args.top_n, args.min_gap)
    for p in paths:
        print(p)


if __name__ == "__main__":
    main()
