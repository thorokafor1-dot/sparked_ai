"""Score each candidate approach for "can you truly see her" (user, 2026-10-07: only use clips where you can
truly see the woman). YuNet every 0.5 s on the upright phone frame; every face that SFace says is NOT him
(cosine to the host ref < 0.363) and is at least MIN_W of frame width counts as her.

Usage: python scan_visibility.py            writes work/visibility.json and prints a table
"""
import json
import sys
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent
MONKEY = ROOT.parents[1] / "long-form-to-shorts-video-editing" / "monkey-app-video-chat"
DET = cv2.FaceDetectorYN_create(str(MONKEY / "models" / "face_detection_yunet.onnx"), "", (320, 320), 0.6)
REC = cv2.FaceRecognizerSF_create(str(MONKEY / "models" / "face_recognition_sface.onnx"), "")
STEP = 0.5
MIN_W = 0.06          # of frame width: a face a viewer can actually read on a phone
DETECT_W = 540

# (id, clip, start s, end s, note) -- approach ranges from work/triage.md, opener to her last line
APPROACHES = [
    ("A1", "2026-03-22_152401", 552, 682, "Diana/Elena style opener"),
    ("A2", "2026-03-22_152401", 960, 995, "birthday-party group"),
    ("A3", "2026-03-22_152401", 1505, 1530, "store worker"),
    ("A4", "2026-03-22_152401", 1767, 1836, "Yanet, rare name"),
    ("A5", "2026-03-22_152401", 2560, 2878, "Renae twins, directions to your heart"),
    ("A6", "2026-03-22_152401", 2962, 3030, "Cubans with sunglasses"),
    ("B1", "2026-03-22_161732", 5, 30, "dress, calm vibe"),
    ("B2", "2026-03-22_161732", 283, 300, "bike outfit, I'm pregnant"),
    ("B3", "2026-03-22_161732", 404, 430, "white pants"),
    ("B4", "2026-03-22_161732", 693, 785, "Grace, I'd hire you"),
    ("B5", "2026-03-22_161732", 882, 935, "corporate pants"),
    ("C1", "2026-03-22_165208", 795, 997, "Amanda, all the Amandas are trouble"),
    ("C2", "2026-03-22_165208", 1125, 1160, "shirt for sister"),
    ("C3", "2026-03-22_165208", 1298, 1440, "Lina, sparkling, matcha"),
    ("C4", "2026-03-22_165208", 1486, 1550, "Cindy, Thor like the god"),
    ("C5", "2026-03-22_165208", 2040, 2230, "Sammy boots, fun size"),
]


def host_feature():
    ref = cv2.imread(str(MONKEY / "assets" / "host_face_ref.png"))
    DET.setInputSize((ref.shape[1], ref.shape[0]))
    _, f = DET.detect(ref)
    best = max(f, key=lambda r: r[2] * r[3])
    return REC.feature(REC.alignCrop(ref, best))


def scan(clip, a, b, host):
    cap = cv2.VideoCapture(str(ROOT / "raw" / f"{clip}.mov"))   # OpenCV applies the -90 display rotation
    cap.set(cv2.CAP_PROP_POS_MSEC, a * 1000)
    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    every = max(1, round(fps * STEP))
    hits, n, i = [], 0, 0
    while True:
        ok = cap.grab()
        if not ok:
            break
        t = a + i / fps
        if t > b:
            break
        if i % every == 0:
            _, frame = cap.retrieve()
            k = DETECT_W / frame.shape[1]
            small = cv2.resize(frame, None, fx=k, fy=k, interpolation=cv2.INTER_AREA)
            DET.setInputSize((small.shape[1], small.shape[0]))
            _, faces = DET.detect(small)
            her = 0.0
            for f in (faces if faces is not None else []):
                w = f[2] / small.shape[1]
                if w < MIN_W:
                    continue
                feat = REC.feature(REC.alignCrop(small, f))
                if REC.match(host, feat, cv2.FaceRecognizerSF_FR_COSINE) < 0.363:
                    her = max(her, w)
            hits.append(round(t, 1) if her else None)
            n += 1
        i += 1
    cap.release()
    seen = [h for h in hits if h is not None]
    first = seen[0] - a if seen else None
    return {"samples": n, "her_pct": round(100 * len(seen) / max(n, 1)), "first_seen_s": first,
            "seen_at": seen}


def main():
    host = host_feature()
    only = set(sys.argv[1:])
    out = ROOT / "work" / "visibility.json"
    res = json.loads(out.read_text()) if out.exists() else {}
    for aid, clip, a, b, note in APPROACHES:
        if only and aid not in only:
            continue
        r = scan(clip, a, b, host)
        res[aid] = {"clip": clip, "start": a, "end": b, "note": note, **r}
        print(f"{aid}  {note:40s} her visible {r['her_pct']:3d}%  first at +{r['first_seen_s']}s", flush=True)
        out.write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    main()
