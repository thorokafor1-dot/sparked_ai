"""Checks for data files: outlier-tracking dashboards and hook-research transcripts."""
from __future__ import annotations

import json
import re
from datetime import date, datetime
from pathlib import Path

from checks import check

VID_RX = re.compile(r"^[A-Za-z0-9_-]{11}$")
GENERAL_MIN_VIEWS = 500_000
GENERAL_MAX_AGE_DAYS = 90


def _date(s: str) -> date | None:
    for fmt in ("%Y-%m-%d", "%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except ValueError:
            continue
    try:
        return date.fromisoformat(s[:10])  # tolerate full ISO timestamps
    except ValueError:
        return None


def _num(v) -> float | None:
    try:
        return float(str(v).replace(",", ""))
    except ValueError:
        return None


@check("outlier-data", paths=["outlier-tracking/*/data.json"], exts={".json"})
def outlier_data(path: Path) -> list[str]:
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []  # valid-json reports it
    if not isinstance(rows, list) or not rows:
        return ["must be a non-empty JSON list of entries (the dashboard reads it as an array)"]
    problems = []
    keys = set(rows[0])
    general = "general-" in path.parent.name
    seen, today = set(), date.today()
    stale, low = [], []
    for i, r in enumerate(rows):
        vid = r.get("vid", "")
        if set(r) != keys:
            problems.append(f"entry {i} ({vid}) has different fields: missing {sorted(keys - set(r))}, "
                            f"extra {sorted(set(r) - keys)}")
        if not VID_RX.match(vid or ""):
            problems.append(f"entry {i} has invalid vid '{vid}'")
        elif vid in seen:
            problems.append(f"duplicate video {vid}")
        seen.add(vid)
        if vid and vid not in (r.get("videoUrl") or ""):
            problems.append(f"entry {i}: videoUrl doesn't match vid {vid}")
        if _num(r.get("views")) is None:
            problems.append(f"entry {i} ({vid}): views '{r.get('views')}' is not a number")
        d = _date(str(r.get("publishedAt") or ""))
        if d is None:
            problems.append(f"entry {i} ({vid}): unparseable publishedAt '{r.get('publishedAt')}'")
        elif general and (today - d).days > GENERAL_MAX_AGE_DAYS:
            stale.append(vid)
        if general and (_num(r.get("views")) or 0) < GENERAL_MIN_VIEWS:
            low.append(vid)
    if stale:
        problems.append(f"{len(stale)} entries older than {GENERAL_MAX_AGE_DAYS} days (general tabs must prune "
                        f"these every run): {', '.join(stale[:6])}{' ...' if len(stale) > 6 else ''}")
    if low:
        problems.append(f"{len(low)} entries under {GENERAL_MIN_VIEWS:,} views (below the general bar): "
                        f"{', '.join(low[:6])}{' ...' if len(low) > 6 else ''}")
    return problems[:12]


COMMON_EN = {"the", "you", "and", "to", "a", "i", "it", "is", "that", "of", "in", "what", "my", "so", "like",
             "me", "your", "we", "this", "just", "yeah", "do", "are", "was", "no", "oh", "be", "for", "on"}


@check("hook-transcripts", paths=["long-form-hook-research/*/hook_transcripts.json", "shorts-hook-research/*.json"],
       exts={".json"})
def hook_transcripts(path: Path) -> list[str]:
    """A dubbed/non-English video under an English title poisons the pattern research."""
    try:
        rows = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return []
    if not isinstance(rows, list):
        return ["must be a JSON list of entries"]
    problems = []
    for r in rows:
        t = (r.get("hookTranscript") or "").strip()
        vid = r.get("vid", "?")
        if not t:
            problems.append(f"{vid}: empty hookTranscript (no captions); drop it or transcribe the audio")
            continue
        words = re.findall(r"[A-Za-z']+", t.lower())
        non_ascii = sum(1 for ch in t if ord(ch) > 127 and ch.isalpha()) / max(len(t), 1)
        english = sum(w in COMMON_EN for w in words) / max(len(words), 1)
        if non_ascii > 0.2 or (len(words) >= 20 and english < 0.08):
            problems.append(f"{vid}: transcript doesn't look English (dubbed/foreign audio under an English "
                            f"title?); exclude it from pattern research")
    return problems
