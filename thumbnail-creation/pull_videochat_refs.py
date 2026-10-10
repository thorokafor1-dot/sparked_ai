"""Pull the flirting-relevant Video Chat outlier thumbnails and build a numbered
contact sheet, the reference board for videochat_thumbnail_strategy.md.

Reads outlier-tracking/niche-long-form/data.json (format "Video Chat"), keeps rows
whose title is about flirting, pulling or dating shows (drops celebrity cameos, trolling),
downloads each hqdefault thumbnail and tiles them 3x4 per sheet.

Usage:
    python pull_videochat_refs.py            # -> work/videochat_refs/sheet_*.jpg + index.txt
    python pull_videochat_refs.py --min-score 30
"""
import argparse
import json
import re
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "outlier-tracking" / "niche-long-form" / "data.json"
OUT = ROOT / "work" / "videochat_refs"
FLIRT = re.compile(r"rizz|baddie|girls|flirt|goddess|fold|mogg|view|flex|aesthetic|spider-?man|pull"
                   r"|\bdat(e|ing)\b|boyfriend|girlfriend|\bfind(ing)?\b.*\ba (man|girl)\b", re.I)
# channels that match the keywords but aren't the format (exposé, non-English, raunch).
# Celebrity/streamer cameos (IShowSpeed, Clavicular, Marlon) fall out on keywords alone.
DENY = {"Turkey Tom", "Hisanlo", "Life of Yama", "ʚїɞ", "YK DJay",
        "Kalogeras Sisters", "Family Friendly"}  # female hosts / mega-influencers: not models for a male creator (user, 2026-10-09)
# established flirting-format channels, kept even when the title has no keyword
ALLOW = {"MarcusT", "Jameer", "Jay Throck", "France Fit", "Teige", "Fabss", "Ejay"}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--min-score", type=float, default=10)
    a = ap.parse_args()

    rows = [r for r in json.loads(DATA.read_text(encoding="utf-8"))
            if str(r.get("format", "")).startswith("Video") and (r.get("score") or 0) >= a.min_score
            and (FLIRT.search(r["title"]) or r["channel"].strip() in ALLOW) and r["channel"].strip() not in DENY]
    rows.sort(key=lambda r: -r["score"])
    OUT.mkdir(parents=True, exist_ok=True)
    for old in OUT.glob("sheet_*.jpg"):
        old.unlink()

    kept, lines = [], []
    for r in rows:
        f = OUT / f"{r['vid']}.jpg"
        if not f.exists():
            try:
                urllib.request.urlretrieve(f"https://i.ytimg.com/vi/{r['vid']}/hqdefault.jpg", f)
            except OSError:
                continue
        kept.append(f)
        lines.append(f"{len(kept):>2}  {r['score']:>6.1f}  {r['views']:>9}  {r['channel'].strip()} | {r['title']}")

    w, h = 480, 270
    for p in range(0, len(kept), 12):
        sheet = Image.new("RGB", (w * 3, h * 4), "black")
        d = ImageDraw.Draw(sheet)
        for i, f in enumerate(kept[p:p + 12]):
            x, y = (i % 3) * w, (i // 3) * h
            sheet.paste(Image.open(f).convert("RGB").crop((0, 45, 480, 315)).resize((w, h)), (x, y))
            d.rectangle((x, y, x + 40, y + 20), fill="black")
            d.text((x + 4, y + 4), str(p + i + 1), fill="yellow")
        sheet.save(OUT / f"sheet_{p // 12 + 1}.jpg", quality=88)
    (OUT / "index.txt").write_text("\n".join(lines), encoding="utf-8")
    print(f"{len(kept)} refs -> {OUT}")


if __name__ == "__main__":
    main()
