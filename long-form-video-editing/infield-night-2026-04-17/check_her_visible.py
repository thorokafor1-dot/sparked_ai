"""Flag kept clips where nobody's face can be seen (Monkey rule, user first_video v17: "don't use clips where the
girl can't even be seen"). Infield version: YuNet on the whole vertical frame every 0.2 s of each kept clip; handheld
footage swings, so only gaps over MAX_GAP count.

Usage: python check_her_visible.py [edit.json]     exit code 1 if anything is flagged
"""
import json
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT.parents[1] / "long-form-to-shorts-video-editing" / "monkey-app-video-chat"))
from reframe import _get_detector  # noqa: E402

RAW = str(ROOT / "raw" / "raw.mkv")
PANE = (0, 0, 1080, 1920)       # the whole vertical phone frame (x, y, w, h)
STEP = 0.2
MIN_FACE_W = 0.05               # of frame width: a real face on camera, not a poster or a speck
LOOSE_SCORE, NORMAL_SCORE = 0.4, 0.6
LUT = __import__("numpy").array([min(255, round(255 * (i / 255) ** (1 / 1.6))) for i in range(256)], dtype="uint8")
MAX_GAP = 2.0                   # seconds with no face before it counts (handheld swings, turned heads are fine)


def face_in(frame, det, zoom=None, lift=False):
    # check what the viewer actually sees: the zoomed window of the vertical frame, brightened if the render lifts it
    x, y, w, h = PANE
    if zoom:
        z, cx, cy = zoom
        w, h = round(w / z), round(h / z)
        x = int(min(max(cx * PANE[2] - w / 2, 0), PANE[2] - w))
        y = int(min(max(cy * PANE[3] - h / 2, 0), PANE[3] - h))
    pane = frame[y:y + h, x:x + w]
    if lift:
        pane = cv2.LUT(pane, LUT)
    if pane.shape[1] > 540:   # detect at 540 wide (full 1080x1920 frames made the check take 18 min); ratios unchanged
        k = 540 / pane.shape[1]
        pane = cv2.resize(pane, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
    h, w = pane.shape[:2]
    det.setInputSize((w, h))
    for score in (NORMAL_SCORE, LOOSE_SCORE):
        det.setScoreThreshold(score)
        _, faces = det.detect(pane)
        if faces is not None and any(f[2] >= w * MIN_FACE_W for f in faces):
            det.setScoreThreshold(NORMAL_SCORE)
            return True
    det.setScoreThreshold(NORMAL_SCORE)
    return False


def main():
    edit = json.load(open(ROOT / (sys.argv[1] if len(sys.argv) > 1 else "edit.json"), encoding="utf-8"))
    ok_spans = edit.get("her_offscreen_ok", [])
    det, cap = _get_detector(), cv2.VideoCapture(RAW)
    flagged = []
    for p in edit["pieces"]:
        if p["type"] != "clip":
            continue
        a, b = p["in"], p["out"]
        # one seek per clip, then read forward: a seek per sample decodes from the last keyframe every time
        # (on the 1080x1920 infield source that took over an hour for one cut)
        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        cap.set(cv2.CAP_PROP_POS_MSEC, a * 1000)
        pos = a
        t, gap0 = a, None
        while t < b:
            while pos < t - 0.5 / fps:
                cap.grab()
                pos += 1 / fps
            got, frame = cap.read()
            pos += 1 / fps
            zm = next((z[2:] for z in p.get("zooms") or [] if z[0] <= t < z[1]), p.get("zoom"))
            seen = got and face_in(frame, det, zm, p.get("lift"))
            if not seen and gap0 is None:
                gap0 = t
            if (seen or t + STEP >= b) and gap0 is not None:
                end = t if seen else b
                if end - gap0 >= MAX_GAP and not any(s <= gap0 and end <= e for s, e in ok_spans):
                    flagged.append((gap0, end, "no face in frame"))
                gap0 = None
            t += STEP
    for a, b, why in flagged:
        print(f"  {a:9.2f}-{b:9.2f}  ({b - a:4.1f}s)  {why}")
    print(f"{len(flagged)} stretch(es) with no visible face")
    sys.exit(1 if flagged else 0)


if __name__ == "__main__":
    main()
