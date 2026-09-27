"""Find Monkey chat bubbles (typed Instagram handles, numbers) so render.py can blur them.

Scans raw/raw.mkv at 4 fps for near-white bubbles in the chat zone (left edge of the creator's pane,
above "Send Message"), then measures each stretch's bounding box. Writes work/chat_blur.json:
[{"span": [start, end], "box": [x, y, w, h]}] in crop coordinates; render.py blurs every piece that
overlaps a span. Run once per new recording, before render.py.
"""
import json
import subprocess

import numpy as np

X, Y, WD, HT = 650, 372, 400, 194     # chat zone in raw 1280x720 coords (HT even: yuv420 crops round down)
CROP_Y = 72                           # render.py crops the browser chrome at y=72


def bubble_mask(z):
    m = z.min(axis=2)
    return (m > 210) & ((z.max(axis=2) - m) < 14)   # light, colourless = chat bubble, not wall or skin


def frames(vf, *pre):
    p = subprocess.Popen(["ffmpeg", "-v", "error", *pre, "-i", "raw/raw.mkv", "-vf", vf, "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], stdout=subprocess.PIPE)
    size = WD * HT * 3
    while True:
        b = p.stdout.read(size)
        if len(b) < size:
            return
        yield np.frombuffer(b, np.uint8).reshape(HT, WD, 3).astype(np.int16)


def main():
    hits = [n / 4 for n, z in enumerate(frames(f"fps=4,crop={WD}:{HT}:{X}:{Y}"))
            if bubble_mask(z).sum(axis=1).max() >= 40]
    spans = []
    for t in hits:
        if spans and t - spans[-1][1] <= 1.0:
            spans[-1][1] = t
        else:
            spans.append([t, t])
    out = []
    for a, b in spans:
        if b - a < 1.5:
            continue
        x0 = y0 = 10 ** 9
        x1 = y1 = -1
        for t in np.linspace(a, b, 8):
            z = next(frames(f"crop={WD}:{HT}:{X}:{Y}", "-ss", f"{t:.2f}"), None)
            if z is None:
                continue
            w = bubble_mask(z)
            rows = np.where(w.sum(axis=1) >= 40)[0]
            if len(rows):
                cols = np.where(w[rows].any(axis=0))[0]
                y0, y1, x0, x1 = min(y0, rows.min()), max(y1, rows.max()), min(x0, cols.min()), max(x1, cols.max())
        if x1 >= 0:   # pad, and reach left to cover the sender's avatar circle
            out.append({"span": [round(a - 0.5, 2), round(b + 0.5, 2)],
                        "box": [int(X + x0 - 45), int(Y - CROP_Y + y0 - 18), int(x1 - x0 + 65), int(y1 - y0 + 64)]})
            # bottom padding: text rows inside the bubble are not solid white, so the detector undershoots
    json.dump(out, open("work/chat_blur.json", "w"), indent=1)
    print(f"{len(out)} chat stretches to blur:", [c["span"] for c in out])


if __name__ == "__main__":
    main()
