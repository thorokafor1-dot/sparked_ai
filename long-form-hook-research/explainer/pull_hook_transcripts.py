"""Pulls opening-~90-second transcripts for the strongest Explainer Video niche
long-form outliers (talking-head/analysis, no infield footage), as raw material for
hook_patterns.md. Walks the full ranked candidate list (not a fixed slice) and skips
empty/non-English transcripts on the fly, see ../_common.py's pull_hook_transcripts()
for the shared driver all 3 content-type subfolders use, and its own hook_patterns.md
for why this format needs a larger max_candidates (high non-English/templated-script
rate found in this bucket). Reads outlier-tracking/niche-long-form/data.json (or
HOOK_RESEARCH_DATA_PATH if set) and writes explainer/hook_transcripts.json.
"""
import os
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.stderr.reconfigure(encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from _common import pull_hook_transcripts

OUT_PATH = os.path.join(os.path.dirname(__file__), "hook_transcripts.json")

if __name__ == "__main__":
    pull_hook_transcripts(format_label="Explainer Video", out_path=OUT_PATH, target=15, max_candidates=90)
