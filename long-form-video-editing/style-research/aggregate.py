"""Turn one type's outlier measurements into the numeric bands of its style profile.

Usage:
    python aggregate.py explainer          -> styles/explainer.bands.json

Bands are the 25th-75th percentile across the reference outliers (our own renders, "local", are
excluded). styles/<type>.md is the readable guide written from these numbers plus the contact sheets
and heatmap moments; qa/checks_edit_style.py holds our renders to the bands.
"""

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
METRICS = {
    "cuts_per_min": lambda m: m["cuts_per_min"],
    "hook_cuts_per_min": lambda m: m["sections"].get("hook", {}).get("cuts_per_min"),
    "setup_cuts_per_min": lambda m: m["sections"].get("setup", {}).get("cuts_per_min"),
    "body_cuts_per_min": lambda m: m["sections"].get("body", {}).get("cuts_per_min"),
    "shot_median_secs": lambda m: m["shot_secs"]["median"],
    "shot_p90_secs": lambda m: m["shot_secs"]["p90"],
    "longest_shot_secs": lambda m: m["longest_shot"],
    "words_per_min": lambda m: m["words_per_min"],
    "dead_air_share": lambda m: m["dead_air_share"],
    "duration_min": lambda m: m["duration"] / 60,
}


def bands(type_: str) -> dict:
    ms = [json.loads(p.read_text(encoding="utf-8")) for p in sorted((HERE / "measurements" / type_).glob("*.json"))]
    ms = [m for m in ms if not m.get("local")]
    out = {"type": type_, "n": len(ms), "sources": [f"{m['id']} {m['channel']} ({m['views']:,} views)" for m in ms],
           "bands": {}}
    for name, f in METRICS.items():
        vals = [v for v in (f(m) for m in ms) if v is not None]
        if vals:
            out["bands"][name] = {"p25": round(float(np.percentile(vals, 25)), 2), "median": round(float(np.median(vals)), 2),
                                  "p75": round(float(np.percentile(vals, 75)), 2), "min": round(min(vals), 2),
                                  "max": round(max(vals), 2)}
    return out


if __name__ == "__main__":
    t = sys.argv[1]
    b = bands(t)
    (HERE / "styles").mkdir(exist_ok=True)
    (HERE / "styles" / f"{t}.bands.json").write_text(json.dumps(b, indent=1), encoding="utf-8")
    print(f"{t}: n={b['n']}")
    for k, v in b["bands"].items():
        print(f"  {k:20} p25 {v['p25']:>7} median {v['median']:>7} p75 {v['p75']:>7}")
