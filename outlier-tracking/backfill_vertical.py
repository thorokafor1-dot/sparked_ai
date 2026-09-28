"""Re-check every existing entry in the long-form data files and set its "vertical"
flag from the video's real aspect ratio (player embed size). One videos.list call per
50 videos, so the whole tracker costs a handful of quota units. Run it after changing
the vertical detector, or to refresh flags on rows that predate the field.

    python outlier-tracking/backfill_vertical.py
"""
import importlib.util
import json
import os
import re
import subprocess
import sys

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _THIS_DIR)
from curate_general_with_claude import _load_local_env, rewrite_swipe_file  # noqa: E402

_load_local_env()
import common  # noqa: E402


def vertical_flags(youtube, video_ids):
    flags = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        resp = youtube.videos().list(
            part="contentDetails,player", id=",".join(batch), maxHeight=720, maxWidth=720,
            fields="items(id,contentDetails/duration,player/embedWidth,player/embedHeight)",
        ).execute()
        for it in resp.get("items", []):
            p = it.get("player", {})
            flags[it["id"]] = common.is_vertical_format(
                it.get("contentDetails", {}).get("duration", ""), p.get("embedWidth"), p.get("embedHeight"))
    return flags


def main():
    youtube = common.build_youtube_client()
    if not youtube:
        raise SystemExit("No YOUTUBE_API_KEY.")

    niche_path = os.path.join(_THIS_DIR, "niche-long-form", "data.json")
    rows = json.load(open(niche_path, encoding="utf-8"))
    flags = vertical_flags(youtube, [r["vid"] for r in rows])
    for r in rows:
        r["vertical"] = bool(flags.get(r["vid"], False))
    json.dump(rows, open(niche_path, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"niche-long-form: {sum(r['vertical'] for r in rows)} vertical of {len(rows)}")

    module_path = os.path.join(_THIS_DIR, "general-long-form", "general_outlier_swipe_file.py")
    spec = importlib.util.spec_from_file_location("gl", module_path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    entries = mod.SWIPE_FILE
    vid_of = lambda e: re.search(r"[?&]v=([\w-]{6,})", e["url"]).group(1)
    gflags = vertical_flags(youtube, [vid_of(e) for e in entries])
    for e in entries:
        e["vertical"] = bool(gflags.get(vid_of(e), False))
    rewrite_swipe_file(module_path, entries)
    subprocess.run([sys.executable, module_path], check=True)
    print(f"general-long-form: {sum(e['vertical'] for e in entries)} vertical of {len(entries)}")


if __name__ == "__main__":
    main()
