"""Blur one person's face (e.g. a client or friend who doesn't want to be shown) through an infield source video.

Two passes, so the person to blur is picked by looking, not guessed:
  python blur_faces.py scan  <night>   detects every face (YuNet), fingerprints it (SFace), clusters by identity,
                                       writes work/faces.json and work/face_clusters.png (crops per cluster)
  python blur_faces.py apply <night> --clusters 3,7
                                       blurs those clusters' faces in raw/raw.mkv (original kept as
                                       raw/raw_unblurred.mkv), carrying each box across short detection gaps
                                       (head turns) so the blur never flickers off

Models: YuNet (shorts pipeline) + tools/models/face_recognition_sface_2021dec.onnx (opencv_zoo).
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "long-form-to-shorts-video-editing" / "monkey-app-video-chat"))
from reframe import _get_detector  # noqa: E402

SFACE = ROOT / "tools" / "models" / "face_recognition_sface_2021dec.onnx"
DET_W = 540          # detect at this width (ratios unchanged)
STEP = 2             # detect every 2nd frame; boxes are interpolated in between
SAME = 0.40          # SFace cosine >= this: same person (opencv_zoo suggests 0.363)
HOLD = 1.0           # seconds a box is carried across a detection gap
PAD = 0.45           # box grows by this fraction each side (hair, ears, turned heads)


def scan(night: Path):
    det, rec = _get_detector(), cv2.FaceRecognizerSF.create(str(SFACE), "")
    cap = cv2.VideoCapture(str(night / "raw/raw.mkv"))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    faces, i = [], 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        if i % STEP == 0:
            _, frame = cap.retrieve()
            k = DET_W / frame.shape[1]
            small = cv2.resize(frame, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
            det.setInputSize((small.shape[1], small.shape[0]))
            det.setScoreThreshold(0.55)
            _, found = det.detect(small)
            for f in found if found is not None else []:
                if f[2] < 18:   # too small to matter or to identify
                    continue
                feat = rec.feature(rec.alignCrop(small, f)).flatten()
                x, y, w, h = (f[:4] / k).tolist()
                faces.append({"t": i / fps, "box": [x, y, w, h], "feat": (feat / np.linalg.norm(feat)).tolist()})
        i += 1
    # greedy clustering on the fingerprints
    feats = np.array([f["feat"] for f in faces])
    labels, cents = -np.ones(len(faces), int), []
    for j, v in enumerate(feats):
        sims = [float(v @ c / np.linalg.norm(c)) for c in cents]
        if sims and max(sims) >= SAME:
            labels[j] = int(np.argmax(sims))
            cents[labels[j]] = cents[labels[j]] + v
        else:
            labels[j] = len(cents)
            cents.append(v.copy())
    np.save(night / "work/face_feats.npy", feats.astype(np.float32))   # row i = faces[i]
    for f, l in zip(faces, labels):
        f["cluster"] = int(l)
        del f["feat"]
    (night / "work/faces.json").write_text(json.dumps({"fps": fps, "faces": faces}))
    # contact sheet: up to 10 crops per cluster with 3+ detections, labelled
    cap = cv2.VideoCapture(str(night / "raw/raw.mkv"))
    rows = []
    for c in sorted(set(labels), key=lambda c: -int((labels == c).sum())):
        idx = [j for j in range(len(faces)) if labels[j] == c]
        if len(idx) < 3:
            continue
        crops = []
        for j in [idx[int(q)] for q in np.linspace(0, len(idx) - 1, min(10, len(idx)))]:
            cap.set(cv2.CAP_PROP_POS_MSEC, faces[j]["t"] * 1000)
            ok, fr = cap.read()
            if not ok:
                continue
            x, y, w, h = [int(v) for v in faces[j]["box"]]
            crop = fr[max(y, 0):y + h, max(x, 0):x + w]
            if crop.size:
                crops.append(cv2.resize(crop, (90, 90)))
        crops += [np.zeros((90, 90, 3), np.uint8)] * (10 - len(crops))
        label = np.zeros((90, 160, 3), np.uint8)
        cv2.putText(label, f"#{c}", (5, 40), 0, 1.0, (0, 255, 255), 2)
        cv2.putText(label, f"{len(idx)} det", (5, 75), 0, 0.6, (255, 255, 255), 1)
        rows.append(np.hstack([label] + crops))
    cv2.imwrite(str(night / "work/face_clusters.png"), np.vstack(rows))
    print(f"{len(faces)} detections in {len(cents)} clusters -> work/face_clusters.png")


def boxes_per_frame(faces, clusters, fps, n):
    """Per-frame boxes for the chosen clusters: interpolated between detections, held across gaps up to HOLD."""
    out = [[] for _ in range(n)]
    tracks = {}
    for f in faces:
        if f["cluster"] in clusters:
            tracks.setdefault(f["cluster"], []).append(f)
    for dets in tracks.values():
        dets.sort(key=lambda f: f["t"])
        for a, b in zip(dets, dets[1:] + [None]):
            fa = round(a["t"] * fps)
            fb = round(b["t"] * fps) if b and b["t"] - a["t"] <= HOLD else min(fa + round(HOLD * fps), n - 1)
            for fr in range(max(fa - round(0.3 * fps), 0), min(fb, n - 1) + 1):
                if b and b["t"] - a["t"] <= HOLD and fr >= fa:
                    k = (fr - fa) / max(fb - fa, 1)
                    box = [a["box"][q] + (b["box"][q] - a["box"][q]) * k for q in range(4)]
                else:
                    box = a["box"]
                out[fr].append(box)
    return out


LIKE = 0.30   # a detection this similar to the chosen clusters' centroid is the same person (profiles score lower)


def apply(night: Path, clusters):
    data = json.loads((night / "work/faces.json").read_text())
    # the person is usually split over many clusters (profiles, motion blur, light): besides the chosen clusters,
    # blur every detection whose fingerprint is close to their centroid, so small stray clusters are caught too
    feats = np.load(night / "work/face_feats.npy")
    sel = [i for i, f in enumerate(data["faces"]) if f["cluster"] in clusters]
    cent = feats[sel].mean(0)
    cent /= np.linalg.norm(cent)
    extra = {data["faces"][i]["cluster"] for i in np.where(feats @ cent >= LIKE)[0]}
    clusters = set(clusters)
    hits = [i for i, f in enumerate(data["faces"]) if f["cluster"] in clusters or float(feats[i] @ cent) >= LIKE]
    for i in hits:
        data["faces"][i]["cluster"] = -1   # mark as "blur"
    print(f"blurring {len(hits)} detections ({len(sel)} from the chosen clusters, the rest by likeness; "
          f"{len(extra - clusters)} extra clusters touched)")
    clusters = [-1]
    src = night / "raw/raw_unblurred.mkv"
    raw = night / "raw/raw.mkv"
    if not src.exists():
        raw.replace(src)
    cap = cv2.VideoCapture(str(src))
    fps = data["fps"]
    n = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    W, H = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)), int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    per = boxes_per_frame(data["faces"], set(clusters), fps, n)
    tmp = night / "raw/raw_blur_video.mkv"
    enc = subprocess.Popen(["ffmpeg", "-v", "error", "-y", "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{W}x{H}",
                            "-r", str(fps), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16",
                            "-pix_fmt", "yuv420p", str(tmp)], stdin=subprocess.PIPE)
    blurred = 0
    for i in range(n):
        ok, fr = cap.read()
        if not ok:
            break
        for x, y, w, h in per[i] if i < len(per) else []:
            x0, y0 = int(max(x - w * PAD, 0)), int(max(y - h * PAD, 0))
            x1, y1 = int(min(x + w * (1 + PAD), W)), int(min(y + h * (1 + PAD), H))
            if x1 > x0 and y1 > y0:
                roi = fr[y0:y1, x0:x1]
                # heavy, unrecoverable blur: shrink ~12x, scale back up, then soften the block edges
                small = cv2.resize(roi, (max(1, (x1 - x0) // 12), max(1, (y1 - y0) // 12)), interpolation=cv2.INTER_AREA)
                fr[y0:y1, x0:x1] = cv2.GaussianBlur(cv2.resize(small, (x1 - x0, y1 - y0), interpolation=cv2.INTER_LINEAR),
                                                    (0, 0), 6)
                blurred += 1
        enc.stdin.write(fr.tobytes())
    enc.stdin.close()
    enc.wait()
    # re-attach the original audio untouched
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(tmp), "-i", str(src), "-map", "0:v", "-map", "1:a",
                    "-c", "copy", str(raw)], check=True)
    tmp.unlink()
    print(f"blurred {blurred} face boxes over {n} frames -> {raw.name} (original: {src.name})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["scan", "apply"])
    ap.add_argument("night")
    ap.add_argument("--clusters", default="")
    a = ap.parse_args()
    night = Path(a.night).resolve()
    if a.mode == "scan":
        scan(night)
    else:
        apply(night, [int(c) for c in a.clusters.split(",") if c])


if __name__ == "__main__":
    main()
