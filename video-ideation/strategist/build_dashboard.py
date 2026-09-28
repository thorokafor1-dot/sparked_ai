"""Builds the Idea Desk dashboard page from ideas.json (run: python build_dashboard.py).
Output goes to strategist/dashboard/ (gitignored): idea_desk.html plus thumbs/. Publish it as a
Claude Artifact with the thumbs as supporting files, see the video-idea-dashboard skill."""
import json
import shutil
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = HERE / "dashboard"
sys.path.insert(0, str(HERE))
import extract_patterns as ep  # noqa: E402

ideas = json.load(open(ROOT / "video-ideation/strategist/ideas.json", encoding="utf-8"))
niche = json.load(open(ROOT / "outlier-tracking/niche-long-form/data.json", encoding="utf-8"))
overall_median = statistics.median(r["score"] for r in niche)

import formats as F  # noqa: E402

CAT_LABEL = {c: d["label"] for c, d in ideas["categories"].items()}
by_cat = {}
for r in niche:
    by_cat.setdefault(ep.categorize(r, "niche"), []).append(r)

# Per category: only the formats that make sense for it (formats.RELEVANT), with that category's own numbers.
formats_by_cat = {}
for cat, allowed in F.RELEVANT.items():
    rows = by_cat.get(cat, [])
    cat_median = round(statistics.median(r["score"] for r in rows), 1) if rows else 0
    used = {}
    for i in ideas["categories"][cat]["ideas"]:
        for f in i.get("formats", []):
            used.setdefault(f, []).append({"id": i["id"], "title": i["title"], "rank": i["rank"]})
    entries = []
    for fid in allowed:
        hits = [r for r in rows if fid in F.detect(r["title"])]
        if not hits:
            continue
        best = max(hits, key=lambda r: r["score"])
        entries.append({
            "id": fid, "label": F.FORMATS[fid][0], "n": len(hits),
            "median": round(statistics.median(r["score"] for r in hits), 1),
            "best_title": best["title"].strip().replace(" " + chr(0x2014) + " ", ", ")[:90], "best_score": round(best["score"]),
            "best_url": best["videoUrl"], "best_vid": best["vid"], "best_thumb": best["thumbnailUrl"],
            "thumb_note": F.THUMB_NOTES.get(fid, ""),
            "thin": len(hits) < 3, "ideas": sorted(used.get(fid, []), key=lambda x: x["rank"]),
        })
    entries.sort(key=lambda x: (x["thin"], -x["median"]))
    formats_by_cat[cat] = {"label": CAT_LABEL[cat], "videos": len(rows), "median": cat_median, "formats": entries}
for cat, block in formats_by_cat.items():
    for entry in block["formats"]:
        entry["also"] = [CAT_LABEL[c] for c, b in formats_by_cat.items() if c != cat and any(x["id"] == entry["id"] for x in b["formats"] if not x["thin"])]
(HERE / "formats.json").write_text(json.dumps(formats_by_cat, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

data = {
    "generated": ideas["generated"],
    "tracked": len(niche),
    "headline": (
        "Explainer titles hold the strongest outliers in your tracker (top score 594x channel average), and video chat e-dates have "
        "by far the most data (174 videos). Bar-specific data is thin (11 videos), so the bar ideas lean on reaction and ranking "
        "formats proven in other niches. Most explainer winners are faceless voiceover from small channels, so real footage from you "
        "is the difference."
    ),
    "footnote": (
        "Scores are multiples of each channel's average views from the outlier tracker. Cross-niche evidence shows 90-day views. "
        "Refresh with the video-idea-dashboard skill after each outlier refresh. Typical niche video scores " + f"{overall_median:.0f}."
    ),
    "formats": formats_by_cat,
    "categories": ideas["categories"],
    "parked": ideas["parked"],
}

for _c in ideas["categories"].values():
    for _i in _c["ideas"]:
        for _e in _i["evidence"]:
            _e["title"] = _e["title"].replace(" " + chr(0x2014) + " ", ", ").replace(chr(0x2014), ",")

html = (HERE / "dashboard_template.html").read_text(encoding="utf-8").replace("__DATA__", json.dumps(data, ensure_ascii=False))
OUT.mkdir(exist_ok=True)
(OUT / "thumbs").mkdir(exist_ok=True)
import requests  # noqa: E402

_needed = [(_e["vid"], _e["thumbnail"]) for _c in ideas["categories"].values() for _i in _c["ideas"] for _e in _i["evidence"]]
_needed += [(_f["best_vid"], _f["best_thumb"]) for _b in formats_by_cat.values() for _f in _b["formats"]]
for _vid, _thumb in _needed:
    _p = OUT / "thumbs" / f"{_vid}.jpg"
    if not _p.exists():
        _r = requests.get(_thumb, timeout=20)
        if _r.ok:
            _p.write_bytes(_r.content)
out = OUT / "idea_desk.html"
out.write_text(html, encoding="utf-8")
print("html bytes", len(html), {c: len(b["formats"]) for c, b in formats_by_cat.items()})
