"""Flag kept clips where the girl can't be seen (user, first_video v17: "don't use clips where the girl can't even
be seen"). Runs YuNet (the shorts pipeline's face detector) on her pane of the raw call, every 0.2 s of each kept
clip, and also flags punch-ins on the guys' pane (zoom cx > 0.5), which take her off screen entirely.

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
PANE = (0, 72, 640, 614)        # her half of the call view in the raw frame (x, y, w, h)
STEP = 0.2
MIN_FACE_W = 0.08               # of pane width: a real face on camera, not a poster or a speck
LOOSE_SCORE, NORMAL_SCORE = 0.4, 0.6
MAX_GAP = 0.6                   # seconds without her face before it counts (a turn of the head is fine)


def face_in(frame, det):
    x, y, w, h = PANE
    pane = frame[y:y + h, x:x + w]
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
        zooms = [(z[0], z[1], z[3]) for z in p.get("zooms") or []] + ([(a, b, p["zoom"][1])] if p.get("zoom") else [])
        for za, zb, cx in zooms:
            if cx > 0.5 and zb - za > 0.05:
                flagged.append((za, zb, "punch-in on the guys hides her"))
        t, gap0 = a, None
        while t < b:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            got, frame = cap.read()
            seen = got and face_in(frame, det)
            if not seen and gap0 is None:
                gap0 = t
            if (seen or t + STEP >= b) and gap0 is not None:
                end = t if seen else b
                if end - gap0 >= MAX_GAP and not any(s <= gap0 and end <= e for s, e in ok_spans):
                    flagged.append((gap0, end, "no face in her pane"))
                gap0 = None
            t += STEP
    for a, b, why in flagged:
        print(f"  {a:9.2f}-{b:9.2f}  ({b - a:4.1f}s)  {why}")
    print(f"{len(flagged)} stretch(es) where she can't be seen")
    sys.exit(1 if flagged else 0)


if __name__ == "__main__":
    main()
