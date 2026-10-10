"""Ingest saved Pinterest (or any web) photos into the women pool as MOCK-ONLY.

Drop images into reference/women_pool/pins_inbox/ (any names, jpg/png/webp), then run:
    python ingest_pins.py                 # crop around the face, file under pins/, index as mock_only
    python ingest_pins.py --look latina   # tag this batch with an archetype (else "unsorted")

Pinned women are real strangers: usable for private concept mocks only, never in a published
thumbnail (likeness / copyright / misleading). mock_videochat_thumbs.py refuses mock_only
images when building finals into output/ (see --final there).
"""
import argparse
import hashlib
import json
import re
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).resolve().parent
POOL = ROOT / "reference" / "women_pool"
INBOX, PINS = POOL / "pins_inbox", POOL / "pins"


def face_box(img):
    import cv2
    import numpy as np
    g = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2GRAY)
    det = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    faces = det.detectMultiScale(g, 1.1, 5, minSize=(img.width // 10, img.width // 10))
    return max(faces, key=lambda f: f[2] * f[3]) if len(faces) else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--look", default="unsorted")
    ap.add_argument("--from", dest="src", default=None,
                    help="read from this folder instead of the inbox and leave its files untouched, e.g. "
                         "the user's master folder: OneDrive/Pictures/Baddies forThumbnails (monkey video chat)")
    a = ap.parse_args()
    src = Path(a.src) if a.src else INBOX
    keep = a.src is not None
    INBOX.mkdir(parents=True, exist_ok=True)
    PINS.mkdir(parents=True, exist_ok=True)
    idx_path = POOL / "index.json"
    index = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else []
    seen = {e.get("sha") for e in index}
    seen_pins = {e.get("pin_id") for e in index if e.get("pin_id")}  # files named pin_<id> dedupe by Pinterest id
    added = skipped = 0
    for f in sorted(p for p in src.iterdir() if p.is_file()):
        if f.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        sha = hashlib.sha1(f.read_bytes()).hexdigest()[:12]
        m = re.match(r"pin_(\d{6,})$", f.stem)
        pin_id = m.group(1) if m else None
        if sha in seen or (pin_id and pin_id in seen_pins):
            if not keep:
                f.unlink()
            continue
        img = ImageOps.exif_transpose(Image.open(f)).convert("RGB")
        if min(img.size) < 400:
            print(f"skip {f.name}: too small")
            skipped += 1
            continue
        box = face_box(img)
        if box is None:  # haar misses tilted / partly covered faces: keep the frame, crop 2:3 from the top
            cw, ch = min(img.width, int(img.height / 1.5)), min(img.height, int(img.width * 1.5))
            left, top = (img.width - cw) // 2, 0
        else:
            x, y, w, h = box
            cw = min(img.width, int(w * 4.2))  # head-and-shoulders portrait crop, 2:3, face in upper third
            ch = min(img.height, int(cw * 1.5))
            cx, top = x + w / 2, y - h * 1.1
            left = int(min(max(cx - cw / 2, 0), img.width - cw))
            top = int(min(max(top, 0), img.height - ch))
        out = PINS / f"pin_{sha}.jpg"
        img.crop((left, top, left + cw, top + ch)).save(out, quality=92)
        index.append({"file": str(out.relative_to(ROOT)).replace("\\", "/"), "source": "pinterest", "sha": sha,
                      "mock_only": True, "look": a.look, "used_in": [], **({"pin_id": pin_id} if pin_id else {})})
        if pin_id:
            seen_pins.add(pin_id)
        seen.add(sha)
        if not keep:
            f.unlink()
        added += 1
    idx_path.write_text(json.dumps(index, indent=1), encoding="utf-8")
    print(f"added {added}, skipped {skipped} (left in {src}), pool size {len(index)}")


if __name__ == "__main__":
    main()
