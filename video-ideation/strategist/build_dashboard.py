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

LABELS = {
    "Numbered list (N Things/Ways/Signs)": "Numbered list (N signs, ways, things)",
    "I Tested / I Tried": "I tested / I tried",
    "Superlative claim (Best/Worst/Every)": "Best, worst or every",
    "Parenthetical reaction tag": "Trust tag in brackets (Uncut, Real)",
    "POV framing": "POV: framing",
    "TIER LIST": "(TIER LIST) title",
}
buckets = {}
for r in niche:
    for p in ep.detect_patterns(r["title"]):
        if p in LABELS:
            buckets.setdefault(p, []).append(r)
formats = []
for p, rows in buckets.items():
    best = max(rows, key=lambda r: r["score"])
    med = round(statistics.median(r["score"] for r in rows), 1)
    note = f'Best: "{best["title"].strip()[:90]}" ({round(best["score"])}x)'
    if len(rows) < 3:
        note += ". Only " + str(len(rows)) + " tracked, so not proven."
    formats.append({"name": LABELS[p], "median": med, "n": len(rows), "note": note})
formats.sort(key=lambda f: (f["n"] < 3, -f["median"]))

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
    "formats": formats,
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

for _c in ideas["categories"].values():
    for _i in _c["ideas"]:
        for _e in _i["evidence"]:
            _p = OUT / "thumbs" / f"{_e['vid']}.jpg"
            if not _p.exists():
                _r = requests.get(_e["thumbnail"], timeout=20)
                if _r.ok:
                    _p.write_bytes(_r.content)
out = OUT / "idea_desk.html"
out.write_text(html, encoding="utf-8")
print("html bytes", len(html), "formats", [(f["name"], f["median"], f["n"]) for f in formats])
