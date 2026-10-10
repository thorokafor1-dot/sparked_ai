"""Pull recent long-form thumbnails from named inspiration channels, score each video
against its own channel's median views, and tile numbered contact sheets for a
thumbnail-text / style review (videochat_thumbnail_strategy.md, "Text trends").

Usage:
    python pull_channel_thumbs.py --channels v:UUlHWMDoSsk v:imny7n9lcME v:1tVFTg0up1w v:PKzB1_QB4s8 "Lil Praisey"
    (v:<videoId> pins the exact channel; a plain name search hit "Jameer Live" not Jameer)
    -> work/channel_refs/<set>/<channel>/sheet_*.jpg + work/channel_refs/<set>/index.tsv

--per-channel N recent long-forms each (default 24). Uses YOUTUBE_API_KEY from
outlier-tracking/.env (about 100 quota units per channel for the name lookup).
"""
import argparse
import os
import re
import statistics
import sys
import urllib.request
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "work" / "channel_refs"
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "outlier-tracking"))
try:
    from dotenv import load_dotenv
    load_dotenv(ROOT.parent / "outlier-tracking" / ".env")
except ImportError:
    pass
import common  # noqa: E402

common.API_KEY = os.getenv("YOUTUBE_API_KEY", common.API_KEY)


def resolve(yt, name):
    """'v:<videoId>' = that video's channel (exact), '@handle' = handle, else name search (can mis-hit)."""
    if name.startswith("v:"):
        r = common.execute_request(yt.videos().list(part="snippet", id=name[2:]))
        return r["items"][0]["snippet"]["channelId"] if r and r.get("items") else None
    if name.startswith("@"):
        r = common.execute_request(yt.channels().list(part="id", forHandle=name))
        return r["items"][0]["id"] if r and r.get("items") else None
    r = common.execute_request(yt.search().list(part="snippet", q=name, type="channel", maxResults=1))
    return r["items"][0]["snippet"]["channelId"] if r and r.get("items") else None


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--channels", nargs="+", required=True)
    ap.add_argument("--per-channel", type=int, default=24)
    ap.add_argument("--set", default="videochat", help="format set, e.g. videochat / explainer / infield (own folder + index)")
    a = ap.parse_args()
    out_root = OUT / a.set
    yt = common.build_youtube_client()
    if not yt:
        sys.exit("YOUTUBE_API_KEY missing")

    rows = []
    for name in a.channels:
        cid = resolve(yt, name)
        ch = common.execute_request(yt.channels().list(part="snippet,statistics,contentDetails", id=cid)) if cid else None
        if not ch or not ch.get("items"):
            print(f"!! could not resolve {name}")
            continue
        ch = ch["items"][0]
        title, subs = ch["snippet"]["title"], int(ch["statistics"].get("subscriberCount", 0))
        uploads = ch["contentDetails"]["relatedPlaylists"]["uploads"]
        vids, token = [], None
        while len(vids) < a.per_channel * 3:
            pl = common.execute_request(yt.playlistItems().list(part="contentDetails", playlistId=uploads,
                                                               maxResults=50, pageToken=token))
            if not pl:
                break
            ids = [i["contentDetails"]["videoId"] for i in pl["items"]]
            vs = common.execute_request(yt.videos().list(part="snippet,statistics,contentDetails", id=",".join(ids)))
            for v in (vs or {}).get("items", []):
                if common.parse_duration_seconds(v["contentDetails"]["duration"]) > 180:
                    vids.append(v)
            token = pl.get("nextPageToken")
            if not token:
                break
        vids = vids[:a.per_channel]
        if not vids:
            continue
        med = statistics.median(int(v["statistics"].get("viewCount", 0)) for v in vids) or 1
        slug = re.sub(r"\W+", "_", title).strip("_").lower()
        d = out_root / slug
        d.mkdir(parents=True, exist_ok=True)
        files = []
        for i, v in enumerate(vids, 1):
            f = d / f"{v['id']}.jpg"
            if not f.exists():
                try:
                    urllib.request.urlretrieve(f"https://i.ytimg.com/vi/{v['id']}/hqdefault.jpg", f)
                except OSError:
                    continue
            views = int(v["statistics"].get("viewCount", 0))
            files.append((i, f))
            rows.append([title, subs, i, v["id"], views, round(views / med, 2),
                         v["snippet"]["publishedAt"][:10], v["snippet"]["title"]])
        w, h = 480, 270
        for p in range(0, len(files), 12):
            sheet = Image.new("RGB", (w * 3, h * 4), "black")
            dr = ImageDraw.Draw(sheet)
            for k, (i, f) in enumerate(files[p:p + 12]):
                x, y = (k % 3) * w, (k // 3) * h
                sheet.paste(Image.open(f).convert("RGB").crop((0, 45, 480, 315)).resize((w, h)), (x, y))
                dr.rectangle((x, y, x + 34, y + 18), fill="black")
                dr.text((x + 4, y + 3), str(i), fill="yellow")
            sheet.save(d / f"sheet_{p // 12 + 1}.jpg", quality=88)
        print(f"{title}: {subs} subs, {len(files)} long-forms, median {int(med)} views -> {d}")

    out_root.mkdir(parents=True, exist_ok=True)
    with open(out_root / "index.tsv", "w", encoding="utf-8") as fh:
        fh.write("channel\tsubs\tn\tvid\tviews\tx_median\tdate\ttitle\n")
        fh.writelines("\t".join(map(str, r)) + "\n" for r in rows)


if __name__ == "__main__":
    main()
