"""Checks for long-form edit decision lists (long-form-video-editing/*/edl.py) and their renderers.

Each rule here is a correction the user had to make by watching a render:
- infield uploads already carry burned-in word captions, so our own captions on clips doubled the text
- clips ran past her first response into brush-offs and small talk (the video is about openers)
- the hook ran long / wasn't an actual opener moment
- the endscreen held for 15s and bled retention
- the talking head's camera audio slipped in instead of the synced external mic
"""
from __future__ import annotations

import json
import re
import runpy
import sys
from pathlib import Path

from checks import check, read_text

EDL_GLOB = ["long-form-video-editing/*/edl.py"]
RENDER_GLOB = ["long-form-video-editing/*/render.py"]

MAX_CLIP_SECS = 9.0  # opener line + her first response; anything longer is conversation, not the opener
MAX_HOOK_SECS = 6.0  # cold open: the opener and her reaction, then straight into the video
MAX_TAIL_SECS = 1.2  # a clip may hold on her reaction this long after the last word, no longer
ENDSCREEN_RANGE = (5.0, 10.0)  # YouTube end-screen elements need >= 5s; past ~10s viewers just leave


@check("edl-openers", level="fast", exts={".py"}, paths=EDL_GLOB)
def edl_openers(path: Path) -> list[str]:
    sys.path.insert(0, str(path.parent))
    try:
        ns = runpy.run_path(str(path))
    except Exception as exc:  # a broken EDL is itself the problem
        return [f"edl.py failed to load: {exc}"]
    finally:
        sys.path.remove(str(path.parent))
    problems = []
    for i, seg in enumerate(ns.get("EDL", [])):
        src = seg.get("src")
        if src in ("th", "endscreen"):
            continue
        label = seg.get("label") or f"#{seg.get('num', '?')} clip ({src})"
        if seg.get("caption"):
            problems.append(f"{label}: caption set on an infield clip; the uploads already have burned-in "
                            f"captions, so this doubles the text (use top_label if a label is really needed)")
        start, end = seg.get("start"), seg.get("end")
        if start is None or end is None:
            problems.append(f"{label}: missing start/end")
            continue
        dur = end - start
        limit = MAX_HOOK_SECS if seg.get("label") == "hook" else MAX_CLIP_SECS
        if dur > limit:
            problems.append(f"{label}: {dur:.1f}s is longer than {limit:.0f}s; end the clip right after her first "
                            f"response (no brush-offs, no follow-up conversation)")
    # the same footage shown twice reads as filler; allowed only when marked with repeats="<which item>"
    clips = [s for s in ns.get("EDL", []) if s.get("src") not in ("th", "endscreen") and s.get("start") is not None]
    for i, a in enumerate(clips):
        for b in clips[i + 1:]:
            if a["src"] == b["src"] and a["start"] < b["end"] and b["start"] < a["end"] \
                    and not (a.get("repeats") or b.get("repeats")):
                problems.append(f"{a['src']} {a['start']}-{a['end']} and {b['start']}-{b['end']} overlap: the same "
                                f"footage plays twice; pick different moments or mark the repeat with repeats=")
    # a clip should end on a word (her response), not trail into dead air or a camera pan
    for seg in clips:
        words_path = path.parent / "work" / f"infield_{seg['src']}_words.json"
        if not words_path.exists():
            continue
        words = json.loads(words_path.read_text(encoding="utf-8"))
        spoken = [w for w in words if seg["start"] <= w["start"] < seg["end"]]
        if spoken and seg["end"] - spoken[-1]["end"] > MAX_TAIL_SECS:
            problems.append(f"{seg['src']} clip {seg['start']}-{seg['end']} ends {seg['end'] - spoken[-1]['end']:.1f}s "
                            f"after the last word; end it on her response, not on silence")
    if ns.get("EDL") and ns["EDL"][0].get("label") != "hook":
        problems.append("first EDL entry should be the hook clip (an actual opener + her reaction), labeled 'hook'")
    return problems


MAX_LEAD_IN_SECS = 0.1  # a talking-head piece may open this long before the voice, no more (else: audible inhale)


@check("talking-head-no-breath-starts", level="full", exts={".py"}, paths=EDL_GLOB)
def talking_head_no_breath_starts(path: Path) -> list[str]:
    """Every talking-head cut must open on the voice, not on the inhale before it (user heard breaths)."""
    render_py = path.parent / "render.py"
    text = read_text(render_py) or ""
    if "def voice_onset" not in text or "def split_on_pauses" not in text:
        return []  # not a mic-synced talking-head project
    sys.path.insert(0, str(path.parent))
    try:
        import importlib
        for mod in ("edl", "render"):
            sys.modules.pop(mod, None)
        edl, render = importlib.import_module("edl"), importlib.import_module("render")
        sil = render.talking_head_silences()
        problems = []
        for seg in edl.EDL:
            if seg.get("src") != "th":
                continue
            pieces = render.split_on_pauses(seg["start"], seg["end"], sil,
                                             seg.get("exact_start", False), seg.get("exact_end", False))
            for s, e in pieces:
                i = int(render.cam_to_mic(s) / 0.02)
                on = render.voice_onset(i, i + 75)
                lead = None if on is None else (on - i) * 0.02
                if lead is None or lead > MAX_LEAD_IN_SECS:
                    problems.append(f"talking-head piece at {s:.2f}s opens "
                                    f"{'with no voice' if lead is None else f'{lead:.2f}s before the voice'} "
                                    f"(audible inhale/dead air); trim to the voice onset")
        problems += [f"cut warning: {w}" for w in render.CUT_WARNINGS]
        return problems
    finally:
        sys.path.remove(str(path.parent))
        for mod in ("edl", "render", "brand_graphics"):
            sys.modules.pop(mod, None)


@check("render-mic-and-outro", level="fast", exts={".py"}, paths=RENDER_GLOB)
def render_mic_and_outro(path: Path) -> list[str]:
    text = read_text(path) or ""
    problems = []
    m = re.search(r"^ENDSCREEN_SECS\s*=\s*([\d.]+)", text, re.M)
    if m and not ENDSCREEN_RANGE[0] <= float(m.group(1)) <= ENDSCREEN_RANGE[1]:
        problems.append(f"ENDSCREEN_SECS = {m.group(1)}; keep it {ENDSCREEN_RANGE[0]:.0f}-{ENDSCREEN_RANGE[1]:.0f}s for retention")
    if "TALKING_HEAD" in text and "MIC" in text and not re.search(r'"-i",\s*str\(MIC\)', text):
        problems.append("talking-head audio must come from the synced external mic (MIC input), never the camera track")
    if "TALKING_HEAD" in text and "subtitles=" not in text:
        problems.append("talking-head long-form must burn in captions for the talking-head parts (user: 'it's missing captions')")
    if re.search(r"crop=iw/\{?PUNCH", text):
        problems.append("hard punch-in zooms on jump cuts; Sparked brand uses smooth eased push-ins")
    return problems
