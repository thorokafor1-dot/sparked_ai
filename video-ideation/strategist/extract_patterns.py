"""Mechanical half of the video-idea strategist pipeline: pulls outlier-tracking
data.json files, buckets entries into this channel's content categories (mirrors
video-ideation/video-ideas/'s folder split), and tags recurring title *structures*
(TIER LIST, "I Tested X", "Her Reaction", POV:, numbered list, etc.) so the pattern
work done by hand across this session's research threads (Coach Knox tier-list
study, bar line-testing titles, bar cold-approach titles) doesn't get re-derived
from scratch every time.

This script does NOT invent video ideas, it only surfaces what's actually in the
data: which categories have real volume, which title structures repeat across
multiple outliers, and the view/score numbers behind each. Turning a pattern into
a concrete new title is a judgment call for Claude to make each run (see
.claude/skills/video-idea-dashboard/SKILL.md), not something to hardcode here.

Usage:
    python extract_patterns.py [--min-score 0] [--top-n 8]
    python extract_patterns.py --json  # machine-readable, for the dashboard step
"""
import argparse
import json
import os
import re
import sys

# Windows' default console encoding (cp1252) can't represent characters that show
# up in real video titles (emoji, curly quotes), same fix as outlier-tracking/common.py.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_THIS_DIR))

# Maps this channel's video-ideas/ category folders to the niche-long-form keyword
# buckets that belong in each (see outlier-tracking/common.py's KEYWORDS list).
# A keyword not listed here falls into "uncategorized" rather than being guessed at.
CATEGORY_KEYWORDS = {
    # "party" has no dedicated video-ideas/ folder, folded into bar/nightlife since
    # the social dynamics (alcohol, music, mingling) are closer to bar than daytime
    # street approach.
    "bar": [
        "club approach women", "bar approach women", "bar game infield",
        "nightclub approach", "night game infield", "bar pickup",
        "approaching women at bars", "approaching women at the club", "bar flirting",
        "how to approach a girl at a bar", "how to talk to a girl at a bar",
        "club seduction", "club infield", "nightgame infield", "flirting at the club",
        "approaching a girl at a party", "flirting at a party",
    ],
    "monkey-app-video-chat": [
        "flirting on video chat", "getting numbers on video chat", "video call with strangers",
        "monkey app flirting", "monkey app girls", "monkey app baddies",
        "monkey app best moments", "omegle flirting", "random video chat girls",
        "azar app flirting", "rizzing up baddies monkey app", "making girls fold monkey app",
        "video chat rizz", "omegle rizz", "stranger video chat girls",
        "chatroulette flirting", "video chat pickup",
    ],
    "street-daytime-pov": [
        "street game infield", "daygame infield", "cold approach infield",
        "approaching random girls", "street flirting", "cold approach",
        "picking up girls", "picking up girls in public", "daygame",
        "approaching women at college", "approaching women at the gym",
        "flirting with strangers", "seduction infield",
        "talking to girls in public", "flirting experiment public",
        "social experiment flirting", "rizz in public", "overcoming approach anxiety",
        "approach women",
    ],
    "explainer": [
        "attraction psychology", "attraction triggers in women explained",
        "body language attraction signs", "female attraction triggers",
        "female body language flirting", "female body language signs",
        "female dating psychology explained", "female psychology dating advice",
        "female psychology explained", "hidden attraction signals women",
        "how to know if she likes you", "how women test men",
        "psychology of attraction women", "reading body language women",
        "signs a girl is interested", "signs of attraction",
        "signs of female interest", "signs she likes you",
        "signs she wants you to approach", "understanding women attraction",
        "what women want explained",
    ],
}

# Structural title patterns worth tracking, each is (label, compiled regex).
# Ordered roughly by how often they've shown up as winners in this session's
# manual research, not alphabetically.
TITLE_PATTERNS = [
    ("TIER LIST", re.compile(r"\btier\s*list\b", re.I)),
    ("I Tested / I Tried", re.compile(r"\bi\s+(tested|tried)\b", re.I)),
    ("Her Reaction", re.compile(r"\bher\s+reaction\b", re.I)),
    ("POV framing", re.compile(r"\bpov\s*:", re.I)),
    ("Ranked / Ranking", re.compile(r"\brank(ed|ing)?\b", re.I)),
    ("Numbered list (N Things/Ways/Signs)", re.compile(r"^\s*\d+\s+\w", re.I)),
    ("Question title", re.compile(r"\?\s*$")),
    ("Parenthetical reaction tag", re.compile(r"\((wholesome|real|honest|uncut)[^)]*\)", re.I)),
    ("Superlative claim (Best/Worst/Every)", re.compile(r"\b(best|worst|every)\b", re.I)),
]


def _load(path: str) -> list:
    full = os.path.join(_ROOT, path)
    if not os.path.exists(full):
        return []
    with open(full, encoding="utf-8") as f:
        return json.load(f)


def _score_of(entry: dict) -> float:
    for key in ("score", "scoreNum"):
        v = entry.get(key)
        if isinstance(v, (int, float)):
            return float(v)
    return 0.0


def _title_of(entry: dict) -> str:
    return entry.get("coldTitle") or entry.get("title") or ""


def categorize(entry: dict, source: str) -> str:
    if source == "general":
        return "general"
    kw = (entry.get("keyword") or "").strip().lower()
    for cat, kws in CATEGORY_KEYWORDS.items():
        if kw in kws:
            return cat
    return "uncategorized"


def detect_patterns(title: str) -> list:
    return [label for label, rx in TITLE_PATTERNS if rx.search(title)]


def build_report(min_score: float, top_n: int) -> dict:
    niche = [(_load("outlier-tracking/niche-long-form/data.json"), "niche")]
    general = [(_load("outlier-tracking/general-long-form/data.json"), "general")]

    entries = []
    for rows, source in niche + general:
        for e in rows:
            score = _score_of(e)
            if score < min_score:
                continue
            title = _title_of(e)
            if not title:
                continue
            entries.append({
                "title": title,
                "channel": e.get("channel", ""),
                "score": score,
                "views": e.get("views") or e.get("viewsRaw"),
                "category": categorize(e, source),
                "source": source,
                "url": e.get("videoUrl", ""),
                "patterns": detect_patterns(title),
            })

    by_category: dict = {}
    for e in entries:
        by_category.setdefault(e["category"], []).append(e)

    category_report = {}
    for cat, rows in by_category.items():
        rows_sorted = sorted(rows, key=lambda r: -r["score"])
        category_report[cat] = {
            "count": len(rows),
            "top_score": rows_sorted[0]["score"] if rows_sorted else 0,
            "top_titles": rows_sorted[:top_n],
        }

    pattern_totals: dict = {}
    for e in entries:
        for p in e["patterns"]:
            bucket = pattern_totals.setdefault(p, {"count": 0, "max_score": 0.0, "examples": []})
            bucket["count"] += 1
            bucket["max_score"] = max(bucket["max_score"], e["score"])
            if len(bucket["examples"]) < 3:
                bucket["examples"].append(f'{e["title"]} ({e["channel"]}, score {e["score"]:.1f})')

    pattern_ranked = sorted(pattern_totals.items(), key=lambda kv: -kv[1]["max_score"])

    return {
        "categories": category_report,
        "patterns_ranked": [{"pattern": p, **stats} for p, stats in pattern_ranked],
        "category_coverage_note": (
            "Categories with low/zero count here have thin real data in "
            "outlier-tracking, per feedback_wider_lookback_for_thin_niches -- "
            "treat their ideas as adjacent-adapted, not outlier-proven, same "
            "caveat already applied by hand to the bar/nightgame research."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-score", type=float, default=0.0)
    parser.add_argument("--top-n", type=int, default=8)
    parser.add_argument("--json", action="store_true", help="print machine-readable JSON only")
    args = parser.parse_args()

    report = build_report(args.min_score, args.top_n)

    if args.json:
        print(json.dumps(report, indent=2))
        return

    print(f"=== Category coverage ===")
    for cat, data in sorted(report["categories"].items(), key=lambda kv: -kv[1]["count"]):
        print(f"{cat}: {data['count']} entries, top score {data['top_score']:.1f}")
        for t in data["top_titles"][:3]:
            print(f"    {t['score']:.1f} | {t['channel']} | {t['title']}")

    print(f"\n=== Title patterns ranked by strongest single outlier ===")
    for p in report["patterns_ranked"]:
        print(f"{p['pattern']}: seen {p['count']}x, strongest score {p['max_score']:.1f}")
        for ex in p["examples"]:
            print(f"    {ex}")

    print(f"\nNote: {report['category_coverage_note']}")


if __name__ == "__main__":
    sys.exit(main() or 0)
