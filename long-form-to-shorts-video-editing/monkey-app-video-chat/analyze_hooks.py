"""Within a given time window (one 'girl' segment), picks the strongest ~3s
hook to start the short on: text score (direct address, questions, numbers,
bold-claim/curiosity words -- reusing patterns from
shorts-hook-research/ideation_10_openers.md) + a visual score (face present,
smiling, motion) sampled via OpenCV at each candidate start.
"""
import argparse
import json
from pathlib import Path

import cv2

HOOK_WORDS = {
    "you", "your", "never", "secret", "actually", "literally", "worst", "best",
    "rather", "would", "texas", "rizz", "date", "boyfriend", "girlfriend", "crush",
    "kiss", "love", "hate", "wrong", "right", "stop", "wait", "listen", "honestly",
}

FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
SMILE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_smile.xml")


def text_score(words: list[dict]) -> float:
    text = " ".join(w["text"].lower().strip(".,!?") for w in words)
    score = 0.0
    if "?" in "".join(w["text"] for w in words):
        score += 1.0
    for w in text.split():
        if w in HOOK_WORDS:
            score += 0.5
    return score


def visual_score(video_path: str, at_seconds: float) -> float:
    cap = cv2.VideoCapture(video_path)
    cap.set(cv2.CAP_PROP_POS_MSEC, at_seconds * 1000)
    ok, frame = cap.read()
    cap.release()
    if not ok:
        return 0.0
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    faces = FACE_CASCADE.detectMultiScale(gray, 1.3, 5)
    if len(faces) == 0:
        return 0.0
    score = 1.0
    for (x, y, w, h) in faces:
        roi = gray[y : y + h, x : x + w]
        if len(SMILE_CASCADE.detectMultiScale(roi, 1.7, 20)) > 0:
            score += 1.0
    return score


def find_best_hook(
    words: list[dict],
    video_path: str,
    seg_start: float,
    seg_end: float,
    window: float = 3.0,
    stride: float = 1.0,
    clip_duration: float = 30.0,
) -> float:
    """Returns the best start timestamp (seconds) within [seg_start, seg_end),
    leaving room for a full clip_duration-length clip to fit before seg_end."""
    latest_start = seg_end - clip_duration
    if latest_start <= seg_start:
        return seg_start
    candidates = []
    t = seg_start
    while t + window <= seg_end and t <= latest_start:
        window_words = [w for w in words if t <= w["start"] < t + window]
        if window_words:
            score = text_score(window_words) + visual_score(video_path, t)
            candidates.append((score, t))
        t += stride
    if not candidates:
        return seg_start
    # Ties go to the earliest timestamp -- a hook should grab attention right
    # away, not sit near the end of the scored window.
    candidates.sort(key=lambda c: (-c[0], c[1]))
    return candidates[0][1]


def main() -> None:
    parser = argparse.ArgumentParser(description="Find the best hook start point within a segment.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--transcript", required=True, help="Path to word-level transcript JSON")
    parser.add_argument("--seg-start", type=float, required=True)
    parser.add_argument("--seg-end", type=float, required=True)
    args = parser.parse_args()

    words = json.loads(Path(args.transcript).read_text(encoding="utf-8"))
    best = find_best_hook(words, args.video, args.seg_start, args.seg_end)
    print(f"Best hook start: {best:.2f}s")


if __name__ == "__main__":
    main()
