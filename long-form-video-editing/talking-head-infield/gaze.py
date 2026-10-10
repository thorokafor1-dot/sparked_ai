"""Head-direction track for a talking-head camera: is he facing the lens or looking off (e.g. reading the script)?

Usage:
    python gaze.py <video> [--fps 10]        writes work/gaze_<video stem>.json and prints the distribution
Uses the YuNet face model (5 landmarks). Yaw/pitch are proxies from the nose position relative to the
eyes, normalised by eye distance, and measured as deviation from his own median (his "facing the lens" pose).
"""
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).parent
MODEL = HERE.parent.parent / "long-form-to-shorts-video-editing" / "monkey-app-video-chat" / "models" / "face_detection_yunet.onnx"
W, H = 640, 360


def track(video: Path, fps: float = 10.0) -> dict:
    out = HERE / "work" / f"gaze_{video.stem}.json"
    if out.exists():
        return json.loads(out.read_text())
    det = cv2.FaceDetectorYN.create(str(MODEL), "", (W, H), 0.6)
    proc = subprocess.Popen(["ffmpeg", "-v", "error", "-i", str(video), "-vf", f"fps={fps},scale={W}:{H}",
                             "-f", "rawvideo", "-pix_fmt", "bgr24", "-"], stdout=subprocess.PIPE)
    yaw, pitch = [], []
    while True:
        buf = proc.stdout.read(W * H * 3)
        if len(buf) < W * H * 3:
            break
        _, faces = det.detect(np.frombuffer(buf, np.uint8).reshape(H, W, 3))
        if faces is None:
            yaw.append(None), pitch.append(None)
            continue
        f = max(faces, key=lambda r: r[2] * r[3])
        (rex, rey), (lex, ley), (nx, ny) = f[4:6], f[6:8], f[8:10]
        eye_d = max(np.hypot(lex - rex, ley - rey), 1e-3)
        yaw.append(float((nx - (rex + lex) / 2) / eye_d))
        pitch.append(float((ny - (rey + ley) / 2) / eye_d))
    proc.wait()
    data = {"fps": fps, "yaw": yaw, "pitch": pitch}
    out.write_text(json.dumps(data))
    return data


class Gaze:
    """Answers 'is he looking off-camera at time t (camera seconds)?' for one video."""

    def __init__(self, video: Path, yaw_thr: float = 0.16, pitch_thr: float = 0.14, fps: float = 10.0):
        d = track(video, fps)
        self.fps = d["fps"]
        y = np.array([np.nan if v is None else v for v in d["yaw"]])
        p = np.array([np.nan if v is None else v for v in d["pitch"]])
        self.dy, self.dp = np.abs(y - np.nanmedian(y)), np.abs(p - np.nanmedian(p))
        self.yaw_thr, self.pitch_thr = yaw_thr, pitch_thr

    def away(self, t: float) -> bool:
        i = int(round(t * self.fps))
        if not 0 <= i < len(self.dy) or np.isnan(self.dy[i]):
            return True  # no face found: turned well away (or out of frame)
        return bool(self.dy[i] > self.yaw_thr or self.dp[i] > self.pitch_thr)

    def away_fraction(self, t0: float, t1: float) -> float:
        ts = np.arange(t0, t1, 1 / self.fps)
        return float(np.mean([self.away(t) for t in ts])) if len(ts) else 0.0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--fps", type=float, default=10.0)
    a = ap.parse_args()
    d = track(Path(a.video), a.fps)
    y = np.array([v for v in d["yaw"] if v is not None])
    p = np.array([v for v in d["pitch"] if v is not None])
    print(f"{len(d['yaw'])} frames, face found in {len(y)}")
    print("yaw dev pct 50/75/90/97:", np.round(np.percentile(np.abs(y - np.median(y)), [50, 75, 90, 97]), 3))
    print("pitch dev pct 50/75/90/97:", np.round(np.percentile(np.abs(p - np.median(p)), [50, 75, 90, 97]), 3))
