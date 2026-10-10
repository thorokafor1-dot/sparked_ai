"""Demand / curiosity check for one video idea, the three-signal test used for the
e-date title lists (video-ideas/monkey-app-video-chat/next_recordings_titles.md).

  1. PROOF   a comparable video already beat its own channel's median (x) or scored as an
             outlier. Sources: outlier-tracking/*/data.json and the inspiration-channel
             pull (thumbnail-creation/work/channel_refs/<set>/index.tsv).
  2. SEARCH  what people type: YouTube autocomplete for each seed phrase (US). Shows that
             the curiosity exists, not how big it is.
  3. GAP     how many of the inspiration channels' titles already cover it. Low supply plus
             real demand is the opening.

Usage:
    python demand_check.py --match "bingo" --seeds "flirting bingo" "monkey app bingo"
    python demand_check.py --match "attractive|beard" --seeds "what women find attractive" "women rate beards"
--match is a regex run over existing titles; --seeds are phrases for autocomplete.
"""
import argparse
import csv
import json
import re
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTLIERS = ["niche-long-form", "general-long-form", "niche-short-form", "general-short-form"]
REFS = ROOT / "thumbnail-creation" / "work" / "channel_refs"


def autocomplete(q):
    u = "https://suggestqueries.google.com/complete/search?client=firefox&ds=yt&hl=en&gl=us&q=" + urllib.parse.quote(q)
    try:
        return json.loads(urllib.request.urlopen(u, timeout=10).read().decode("utf-8", "replace"))[1]
    except Exception as e:  # network hiccup: report, don't crash the check
        return [f"(autocomplete failed: {e})"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--match", required=True, help="regex over existing titles")
    ap.add_argument("--seeds", nargs="*", default=[], help="phrases for YouTube autocomplete")
    ap.add_argument("--set", default="videochat", help="inspiration set pulled by pull_channel_thumbs.py --set")
    a = ap.parse_args()
    INSPO = REFS / a.set / "index.tsv"
    pat = re.compile(a.match, re.I)

    print("== 1. PROOF (comparable videos that already won)")
    proof = []
    for folder in OUTLIERS:
        f = ROOT / "outlier-tracking" / folder / "data.json"
        if f.exists():
            for r in json.loads(f.read_text(encoding="utf-8")):
                if pat.search(r.get("title", "")):
                    proof.append((r.get("score") or 0, f"score {r.get('score') or 0:.0f}", r.get("views"), r["channel"].strip(), r["title"], folder))
    inspo = list(csv.reader(INSPO.open(encoding="utf-8"), delimiter="\t"))[1:] if INSPO.exists() else []
    for r in inspo:
        if pat.search(r[7]):
            proof.append((float(r[5]) * 10, f"{r[5]}x median", r[4], r[0], r[7], "inspiration"))
    for _, s, v, ch, t, src in sorted(proof, key=lambda p: -p[0])[:12]:
        print(f"  {s:>12}  {int(v or 0):>10,}  {ch} | {t[:80]}  [{src}]")
    if not proof:
        print("  none found: no proven model yet (treat as experimental)")

    print("\n== 2. SEARCH (what people type, YouTube autocomplete, US)")
    for s in a.seeds:
        print(f"  {s!r}: " + " | ".join(autocomplete(s)[:8]))

    print("\n== 3. GAP (supply among inspiration channels)")
    hits = [r for r in inspo if pat.search(r[7])]
    print(f"  {len(hits)} of {len(inspo)} inspiration titles match" + (": " + "; ".join(f"{h[0]} {h[5]}x" for h in hits[:6]) if hits else ""))

    strong = any(p[0] >= 20 for p in proof)
    print("\n== VERDICT")
    print("  proof: " + ("STRONG (a model beat its channel by 2x+ or scored 20+)" if strong else "weak or none"))
    print("  gap:   " + ("OPEN (few or no competitors)" if len(hits) <= 2 else "CROWDED, so a twist is needed"))


if __name__ == "__main__":
    main()
