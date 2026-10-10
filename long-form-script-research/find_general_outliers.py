"""Finds recent long-form outliers on the big men-audience channels in channels.json,
using yt-dlp (no YouTube API quota). An outlier is a video that beat its own channel's
recent median by OUTLIER_RATIO and cleared MIN_VIEWS, published inside LOOKBACK_DAYS.

Writes general_candidates.json, which pull_full_transcripts.py --source general reads.

    python long-form-script-research/find_general_outliers.py [--per-channel 2]
"""
import argparse
import datetime as dt
import json
import os
import statistics
import sys

import yt_dlp

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
SCAN_DEPTH = 40            # most recent uploads per channel to compute the median from
MIN_SECONDS = 8 * 60       # long-form only
MAX_SECONDS = 60 * 60      # podcasts/streams are unscripted, useless for script craft
MIN_VIEWS = 1_000_000
OUTLIER_RATIO = 1.8
LOOKBACK_DAYS = 365
SKIP_WORDS = ("podcast", "livestream", "live stream", "full episode", "#shorts", "q&a")


def list_channel(handle: str) -> tuple[list[dict], int | None]:
    opts = {"extract_flat": True, "quiet": True, "no_warnings": True, "playlistend": SCAN_DEPTH}
    with yt_dlp.YoutubeDL(opts) as y:
        info = y.extract_info(f"https://www.youtube.com/{handle}/videos", download=False)
    return info.get("entries") or [], info.get("channel_follower_count")


def upload_date(vid: str) -> dt.date | None:
    opts = {"quiet": True, "no_warnings": True, "skip_download": True}
    with yt_dlp.YoutubeDL(opts) as y:
        d = y.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False).get("upload_date")
    return dt.datetime.strptime(d, "%Y%m%d").date() if d else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-channel", type=int, default=2)
    ap.add_argument("--group", help="scan only this channels.json group (results merge into the file)")
    args = ap.parse_args()

    groups = json.load(open(os.path.join(HERE, "channels.json"), encoding="utf-8"))
    today = dt.date.today()
    out = []
    for group, spec in groups.items():
        if group.startswith("_") or (args.group and group != args.group):
            continue
        for handle in spec["handles"]:
            try:
                entries, subs = list_channel(handle)
            except Exception as e:
                print(f"SKIP {handle}: {str(e)[:80]}")
                continue
            longs = [e for e in entries if e.get("view_count") and e.get("duration")
                     and MIN_SECONDS <= e["duration"] <= MAX_SECONDS
                     and not any(w in (e.get("title") or "").lower() for w in SKIP_WORDS)]
            if len(longs) < 4:
                print(f"SKIP {handle}: only {len(longs)} long-form uploads")
                continue
            median = statistics.median(e["view_count"] for e in longs)
            ranked = sorted(longs, key=lambda e: e["view_count"] / median, reverse=True)
            kept = 0
            for e in ranked:
                ratio = e["view_count"] / median
                if kept >= args.per_channel or ratio < OUTLIER_RATIO:
                    break
                if e["view_count"] < spec.get("min_views", MIN_VIEWS):
                    continue
                try:
                    published = upload_date(e["id"])
                except Exception:
                    continue
                if not published or published < today - dt.timedelta(days=spec.get("lookback_days", LOOKBACK_DAYS)):
                    continue
                kept += 1
                out.append({
                    "vid": e["id"], "title": e["title"], "channel": handle, "group": group,
                    "views": e["view_count"], "channelMedian": int(median), "ratio": round(ratio, 2),
                    "subscribers": subs, "duration": e["duration"], "publishedAt": published.isoformat(),
                    "videoUrl": f"https://www.youtube.com/watch?v={e['id']}",
                })
            if kept == 0:  # consistent mega-channels never clear the ratio; study their best recent video anyway
                for e in sorted(longs, key=lambda e: e["view_count"], reverse=True)[:3]:
                    if e["view_count"] < spec.get("min_views", MIN_VIEWS):
                        break
                    try:
                        published = upload_date(e["id"])
                    except Exception:
                        continue
                    if published and published >= today - dt.timedelta(days=spec.get("lookback_days", LOOKBACK_DAYS)):
                        kept = 1
                        out.append({
                            "vid": e["id"], "title": e["title"], "channel": handle, "group": group,
                            "views": e["view_count"], "channelMedian": int(median),
                            "ratio": round(e["view_count"] / median, 2), "channelBest": True,
                            "subscribers": subs, "duration": e["duration"], "publishedAt": published.isoformat(),
                            "videoUrl": f"https://www.youtube.com/watch?v={e['id']}",
                        })
                        break
            print(f"{handle}: median {int(median):,}, kept {kept}")

    path = os.path.join(HERE, "general_candidates.json")
    if args.group and os.path.exists(path):
        out += [r for r in json.load(open(path, encoding="utf-8")) if r["group"] != args.group]
    out.sort(key=lambda r: r["ratio"], reverse=True)
    json.dump(out, open(path, "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    print(f"\nWrote {len(out)} candidates to {path}")


if __name__ == "__main__":
    main()
