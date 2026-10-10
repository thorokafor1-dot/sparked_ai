"""Download every video (and photo) from public Google Photos share links.

Usage:
    python tools/gphotos_fetch.py --out <folder> <link> [<link> ...]

Each link may be a photos.app.goo.gl short link or a photos.google.com/share
album URL. Files are named by capture time (YYYY-MM-DD_HHMMSS.<ext>) so takes
from several albums sort into shooting order. Already-downloaded files with the
right size are skipped, so re-running with more links is cheap.
"""
import argparse
import datetime as dt
import os
import re
import sys
import urllib.request

UA = {"User-Agent": "Mozilla/5.0"}
# ["<mediaKey>",["<baseUrl>",w,h,...]],<captureMs>,"<dedup>",<tzOffsetMs>
ITEM_RE = re.compile(
    r'\["(AF1Qip[\w-]+)",\["(https://lh3\.googleusercontent\.com/pw/[\w-]+)",'
    r'(\d+),(\d+)[^\]]*?(?:\][^\]]*?)*?\]\],(\d{13}),"[^"]*",(-?\d+)'
)
EXT = {"video/quicktime": ".mov", "video/mp4": ".mp4", "image/jpeg": ".jpg",
       "image/heif": ".heic", "image/png": ".png"}


def get(url, timeout=120):
    return urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout)


def album_items(link):
    html = get(link).read().decode("utf-8", "replace")
    seen = {}
    for m in ITEM_RE.finditer(html):
        key, base, w, h, ms, tz = m.groups()
        # video items carry a "76647426":[<durationMs>,...] block right after the entry
        is_video = '"76647426":[' in html[m.start():m.start() + 3000]
        seen.setdefault(key, (base, int(w), int(h), int(ms), int(tz), is_video))
    return list(seen.values())


def download(base, ms, tz, out_dir, is_video):
    # =dv returns the original video (long ones can take minutes before the first
    # byte, so no short timeout); =d is the photo. Never save a video's still frame.
    for suffix in (("=dv",) if is_video else ("=d",)):
        try:
            resp = get(base + suffix, timeout=1800 if is_video else 120)
        except Exception as e:
            print(f"error  {suffix}: {e}", file=sys.stderr)
            continue
        ctype = resp.headers.get("Content-Type", "").split(";")[0]
        if is_video and not ctype.startswith("video/"):
            print(f"error  video item returned {ctype}", file=sys.stderr)
            continue
        size = int(resp.headers.get("Content-Length", 0))
        stamp = dt.datetime.fromtimestamp((ms + tz) / 1000, dt.timezone.utc)
        path = os.path.join(out_dir, stamp.strftime("%Y-%m-%d_%H%M%S") + EXT.get(ctype, ".bin"))
        if os.path.exists(path) and os.path.getsize(path) == size:
            print(f"skip   {path}")
            return path
        with open(path + ".part", "wb") as f:
            while chunk := resp.read(1 << 20):
                f.write(chunk)
        os.replace(path + ".part", path)
        print(f"saved  {path}  ({size / 1e6:.0f} MB, {ctype})")
        return path
    print(f"FAILED {base}", file=sys.stderr)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("links", nargs="+")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)
    failed = 0
    for link in a.links:
        items = album_items(link)
        print(f"{link}: {len(items)} item(s)")
        if not items:
            failed += 1
        for base, _w, _h, ms, tz, is_video in items:
            failed += download(base, ms, tz, a.out, is_video) is None
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
