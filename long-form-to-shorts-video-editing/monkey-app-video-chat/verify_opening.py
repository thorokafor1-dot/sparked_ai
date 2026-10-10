"""The first 2 seconds of a short must show HER (user, 2026-10-06: "first 2 seconds are the most crucial
so it has to be woman shown first"). Identity comes from OpenCV's SFace recogniser compared against a
reference frame of the host (assets/host_face_ref.png, him full-screen): calibrated on short_3_v8 and
short_5_v2, his face scored 0.52-0.78 cosine, hers and meme faces 0.21 or lower (SFace's own same-person
threshold is 0.363). Needs models/face_recognition_sface.onnx (opencv_zoo, gitignored like YuNet).

    python verify_opening.py output/short_N_vK.mp4
"""
import sys
from pathlib import Path

import cv2

from reframe import MIN_FACE_PX, _get_detector

HERE = Path(__file__).parent
SFACE = HERE / "models" / "face_recognition_sface.onnx"
HOST_REF = HERE / "assets" / "host_face_ref.png"
SAME_PERSON = 0.363
INFIELD_MIN_FACE = 64
OPENING_SECS = 2.0
STEP = 0.25


def _faces(det, img, min_w=None):
    h, w = img.shape[:2]
    det.setInputSize((w, h))
    _, f = det.detect(img)
    # her badge avatar icon detects as a face; never count it as "her" (see reframe.MIN_FACE_PX)
    return [] if f is None else [x for x in f if x[2] >= (min_w or 2 * MIN_FACE_PX)]  # renders zoom ~1.8x: avatar ~52px, real faces 200px+


def opening_problems(video: str, memes: list | None = None, min_face: int | None = None) -> list[str]:
    """min_face: smallest face width (px) that counts. Default 2 x MIN_FACE_PX skips the Monkey avatar icon;
    phone POV infield footage has no UI icons and opens on her mid walk-up at ~65-85 px (amanda_v1), so
    the infield shorts pass INFIELD_MIN_FACE."""
    if not (SFACE.exists() and HOST_REF.exists()):
        return [f"can't verify the opening: missing {SFACE.name} or {HOST_REF.name}"]
    det = _get_detector()
    rec = cv2.FaceRecognizerSF_create(str(SFACE), "")
    ref = cv2.imread(str(HOST_REF))
    ref_faces = _faces(det, ref)
    him = rec.feature(rec.alignCrop(ref, max(ref_faces, key=lambda f: f[2] * f[3])))
    cap = cv2.VideoCapture(video)
    bad = []
    t = 0.0
    while t < OPENING_SECS:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if ok:
            if any(lo <= t < hi for lo, hi in (memes or [])):
                bad.append((t, "a meme"))
            else:
                faces = _faces(det, frame, min_face)
                sims = [rec.match(him, rec.feature(rec.alignCrop(frame, f)), cv2.FaceRecognizerSF_FR_COSINE) for f in faces]
                if not faces:
                    bad.append((t, "no face"))
                elif max(sims) >= SAME_PERSON:
                    bad.append((t, "him"))
        t += STEP
    # a single faceless sample is a blink/blur (short_3_v8 0.5s); only a 0.5s+ hole counts. Him or a meme
    # counts on any sample.
    nf = [t for t, what in bad if what == "no face"]
    lone = {t for t in nf if t - STEP not in nf and t + STEP not in nf}
    bad = [(t, what) for t, what in bad if not (what == "no face" and t in lone)]
    return [f"opening {t:.2f}s shows {what}, not her; the first {OPENING_SECS:.0f}s must show the woman "
            f"(start the clip where she is on screen)" for t, what in bad]


if __name__ == "__main__":
    for p in opening_problems(sys.argv[1]):
        print(p)
