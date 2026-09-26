"""Checks for finished thumbnails in thumbnail-creation/output/.

Thresholds were calibrated on this folder's own history: the thumbnails the user picked
as final (meet9_FINAL*) score 350-580 on main-face sharpness, while rejected soft drafts
mostly score under 70.
"""
from __future__ import annotations

from pathlib import Path

from checks import ROOT, check

THUMBS = ["thumbnail-creation/output/*"]
# Comparison sheets / option grids live in output/ too but aren't thumbnails.
NOT_THUMBS = ["thumbnail-creation/output/*options*", "thumbnail-creation/output/*comparison*",
              "thumbnail-creation/output/*sheet*", "thumbnail-creation/output/*grid*"]
YUNET = ROOT / "long-form-to-shorts-video-editing" / "monkey-app-video-chat" / "models" / "face_detection_yunet.onnx"

MAX_BYTES = 2 * 1024 * 1024   # YouTube rejects custom thumbnails over 2MB
MIN_FACE_SHARPNESS = 100      # Laplacian variance of the main face resized to 256x256
MIN_FACE_HEIGHT = 0.12        # main face must be at least 12% of image height to read on mobile
MIN_MEAN_LUMA = 30            # darker than this turns to mud at feed size


def main_face(img):
    """(x, y, w, h) of the largest face YuNet finds, or None."""
    import cv2
    h, w = img.shape[:2]
    det = cv2.FaceDetectorYN_create(str(YUNET), "", (w, h), score_threshold=0.7)
    _, faces = det.detect(img)
    if faces is None or not len(faces):
        return None
    x, y, fw, fh = max(faces, key=lambda f: f[3])[:4]
    return max(0, int(x)), max(0, int(y)), int(fw), int(fh)


def face_sharpness(gray, box) -> float:
    import cv2
    x, y, w, h = box
    crop = cv2.resize(gray[y:y + h, x:x + w], (256, 256))
    return float(cv2.Laplacian(crop, cv2.CV_64F).var())


@check("thumbnail-specs", level="full", exts={".png", ".jpg", ".jpeg", ".webp"}, paths=THUMBS,
       exclude=NOT_THUMBS, cache=True)
def thumbnail_specs(path: Path) -> list[str]:
    import cv2
    problems = []
    size = path.stat().st_size
    if size > MAX_BYTES:
        problems.append(f"{size / 1048576:.1f}MB, YouTube rejects thumbnails over 2MB; "
                        f"export a JPG at quality ~90 (1920x1080 lands around 400-500KB)")
    img = cv2.imread(str(path))
    if img is None:
        return problems + ["image could not be read"]
    h, w = img.shape[:2]
    if abs(w / h - 16 / 9) > 0.01 or w < 1280:
        problems.append(f"{w}x{h}, must be 16:9 and at least 1280x720")
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    if gray.mean() < MIN_MEAN_LUMA:
        problems.append(f"very dark overall (mean brightness {gray.mean():.0f}/255), lift exposure so it reads in the feed")
    if not YUNET.exists():
        return problems
    face = main_face(img)
    if face is None or face[3] < h * MIN_FACE_HEIGHT:
        problems.append("no clear face (none at least 12% of the frame height); this niche's winning "
                        "thumbnails all show a readable face/reaction")
        return problems
    sharp = face_sharpness(gray, face)
    if sharp < MIN_FACE_SHARPNESS:
        problems.append(f"main face is soft (sharpness {sharp:.0f}, need {MIN_FACE_SHARPNESS}+; finals scored 350+). "
                        f"Pick a sharper frame or run restore_faces.py on it")
    return problems
