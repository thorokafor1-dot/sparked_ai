"""On-demand export: pulls the top N outliers from one dashboard tab and packages them
into a small "swipe pack" (JSON + CSV + saved thumbnails) sized for handing to an
external tool like Grok, per Grok's own requested format (YouTube URL, outlier score,
title, niche/topic, thumbnail image URL or saved .jpg, 1-line "why it won" note).

This script only automates the mechanical half: selecting the top-scoring rows,
downloading their thumbnails, and writing JSON/CSV. It deliberately leaves each row's
"note" field null — writing a real "why it won" note (face size, expression, colors,
cleavage/neckline, text) requires actually looking at the thumbnail, which needs a
vision-capable model in the loop. Ask Claude to fill in the notes after running this;
there's no xAI API key on this account to automate that step too, and grok.com's
consumer chat has no upload API to automate the handoff either — that stays a manual
drag-and-drop of the output folder's contents into the chat.

Usage:
    python grok_swipe_pack.py [--tab outliers] [--count 8] [--out grok-swipe-pack]

--tab is one of: outliers (niche long-form), shorts (niche short-form),
generalOutliers, generalShorts — matching the dashboard's four tabs.
"""
import argparse
import csv
import json
import os
import urllib.request

TAB_TO_PATH = {
    "outliers": "niche-long-form/data.json",
    "shorts": "niche-short-form/data.json",
    "generalOutliers": "general-long-form/data.json",
    "generalShorts": "general-short-form/data.json",
}


def load_rows(tab: str) -> list:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), TAB_TO_PATH[tab])
    with open(path, encoding="utf-8") as f:
        rows = json.load(f)
    score_key = "score" if "score" in rows[0] else "scoreNum"
    rows.sort(key=lambda r: r[score_key], reverse=True)
    return rows, score_key


def download_thumbnail(vid: str, dest_dir: str) -> str:
    dest = os.path.join(dest_dir, f"{vid}.jpg")
    if os.path.exists(dest):
        return dest
    url = f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = resp.read()
    with open(dest, "wb") as f:
        f.write(data)
    return dest


def main() -> None:
    parser = argparse.ArgumentParser(description="Export a small swipe pack for sharing with an external tool.")
    parser.add_argument("--tab", default="outliers", choices=list(TAB_TO_PATH.keys()))
    parser.add_argument("--count", type=int, default=8, help="How many rows to include (Grok's own spec asks for 3-8).")
    parser.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "grok-swipe-pack"))
    args = parser.parse_args()

    if args.count < 1 or args.count > 8:
        print("Warning: Grok's requested format is 3-8 videos; proceeding anyway.")

    rows, score_key = load_rows(args.tab)
    top = rows[: args.count]

    thumbs_dir = os.path.join(args.out, "thumbs")
    os.makedirs(thumbs_dir, exist_ok=True)

    pack = []
    for r in top:
        vid = r["vid"]
        try:
            download_thumbnail(vid, thumbs_dir)
            saved_thumb = f"thumbs/{vid}.jpg"
        except Exception as e:
            print(f"  → Could not download thumbnail for {vid}: {e}")
            saved_thumb = ""

        pack.append({
            "youtubeUrl": r["videoUrl"],
            "outlierScore": f"{r[score_key]}x",
            "title": r["title"],
            "niche": r.get("keyword") or r.get("niche", ""),
            "thumbnailUrl": r["thumbnailUrl"],
            "savedThumbnail": saved_thumb,
            "note": None,  # fill in after actually looking at the thumbnail
        })

    os.makedirs(args.out, exist_ok=True)
    json_path = os.path.join(args.out, "swipe_pack.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(pack, f, indent=2, ensure_ascii=False)

    csv_path = os.path.join(args.out, "swipe_pack.csv")
    with open(csv_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=list(pack[0].keys()))
        writer.writeheader()
        writer.writerows(pack)

    print(f"Wrote {len(pack)} rows to {json_path} and {csv_path}")
    print(f"Thumbnails saved to {thumbs_dir}")
    print("Note fields are blank — ask Claude to fill in the \"why it won\" notes, "
          "then drag the folder's contents into grok.com yourself (no upload API exists to automate that step).")


if __name__ == "__main__":
    main()
