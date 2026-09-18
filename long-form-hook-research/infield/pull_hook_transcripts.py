"""Pulls opening-~90-second transcripts for the strongest In-Person niche long-form outliers,
as raw material for hook_patterns.md. Reads candidates from
outlier-tracking/niche-long-form/data.json (source of truth for outlier scoring lives there,
not here) and writes long-form-hook-research/hook_transcripts.json.
"""
import json
import os
import sys

# Windows console defaults to cp1252, which can't print the emoji that shows up
# in a lot of these titles, so widen stdout to tolerate it instead of crashing.
sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _common import fetch_hook_transcript

HOOK_WINDOW_SECONDS = 90
TOP_N = 15

HERE = os.path.dirname(__file__)
DATA_PATH = os.path.join(HERE, "..", "..", "outlier-tracking", "niche-long-form", "data.json")
OUT_PATH = os.path.join(HERE, "hook_transcripts.json")


def load_candidates():
    with open(DATA_PATH, encoding="utf-8") as f:
        rows = json.load(f)
    # Video Chat/Omegle outliers are a different production style than this channel's
    # in-person cold approach, so they're not useful hook references here.
    in_person = [r for r in rows if r.get("format") == "In-Person"]
    in_person.sort(key=lambda r: r.get("score", 0), reverse=True)
    return in_person[:TOP_N]


def main():
    candidates = load_candidates()
    results = []
    for row in candidates:
        vid = row["vid"]
        try:
            text = fetch_hook_transcript(vid, HOOK_WINDOW_SECONDS)
        except Exception as e:
            print(f"SKIP {vid} ({row['title'][:60]}): {e}", file=sys.stderr)
            continue

        results.append({
            "title": row["title"],
            "channel": row["channel"],
            "views": row["views"],
            "subscribers": row["subscribers"],
            "score": row.get("score"),
            "reason": row.get("reason"),
            "duration": row.get("duration"),
            "videoUrl": row["videoUrl"],
            "vid": vid,
            "hookTranscript": text,
        })
        print(f"OK   {vid} ({row['title'][:60]})")

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {len(results)}/{len(candidates)} hook transcripts to {OUT_PATH}")


if __name__ == "__main__":
    main()
