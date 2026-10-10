"""Carry a finished EDL over to a new take of the same script.

Usage:
    python retarget_edl.py --words work/take2_mic_words.json --sync work/take2_main_sync.json \
        --cam input/rerecord/P1040024.MP4 --mic "input/rerecord/10 Conversations Starters Remake.m4a" \
        --angle2 input/rerecord/angle2_iphone.mp4 --angle2-sync work/take2_iphone_sync.json \
        --prefix take2_ --out edl_take2.py

Each talking-head range in the reference EDL (edl.py, take 1) is a script line. Its words are
fuzzy-matched against the new take's mic transcript, in script order, and the best (latest on a tie,
since retakes come after stumbles) span becomes the new range. Clips, cards and labels carry over as-is.
Every range gets its match score and matched text as a comment; low scores are listed at the end
for a manual look. Also writes <prefix>caption_words.json (transcript in main-camera time) for render.py.
"""

import argparse
import difflib
import json
import re
from pathlib import Path

import edl as ref

HERE = Path(__file__).parent
WORK = HERE / "work"
LOW_SCORE = 0.7  # below this the match is worth checking by eye
BACKTRACK = 5.0  # seconds the next line may start before the previous match (overlapping retakes)
GLOBAL_LABELS = {"midroll subscribe"}  # moved out of script order in the reference edit, so searched take-wide


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9']", "", text.lower())


def best_span(ref_toks: list[str], words: list[dict], toks: list[str], t_min: float) -> tuple[float, int, int]:
    n, cands = len(ref_toks), []
    for i in range(len(toks)):
        if words[i]["start"] < t_min:
            continue
        for m in {n, max(1, round(n * 0.8)), round(n * 1.2) + 1}:
            sm = difflib.SequenceMatcher(None, ref_toks, toks[i:i + m], autojunk=False)
            blocks = [b for b in sm.get_matching_blocks() if b.size]
            if blocks:
                cands.append((sm.ratio(), i + blocks[0].b, i + blocks[-1].b + blocks[-1].size - 1))
    if not cands:
        return None
    top = max(c[0] for c in cands)
    return max((c for c in cands if c[0] >= top - 0.02), key=lambda c: c[1])  # ties go to the later take


def kwargs_src(seg: dict) -> str:
    skip = {"src", "start", "end", "exact_start", "exact_end"}
    return "".join(f", {k}={v!r}" for k, v in seg.items() if k not in skip and not (k == "caption" and v is None))


def main() -> None:
    p = argparse.ArgumentParser()
    for a in ("--words", "--sync", "--cam", "--mic", "--out", "--prefix"):
        p.add_argument(a, required=True)
    p.add_argument("--angle2")
    p.add_argument("--angle2-sync")
    p.add_argument("--ref-words", default="work/talking_head_words.json", help="reference take transcript, camera time")
    args = p.parse_args()

    sync = json.loads((HERE / args.sync).read_text())
    to_cam = lambda t: t + sync["offset"] + sync["drift_per_sec"] * t  # noqa: E731  mic -> main camera
    words = [dict(w, start=to_cam(w["start"]), end=to_cam(w["end"])) for w in json.loads((HERE / args.words).read_text())]
    words = [w for w in words if norm(w["text"])]
    (WORK / f"{args.prefix}caption_words.json").write_text(json.dumps(words, indent=1), encoding="utf-8")
    toks = [norm(w["text"]) for w in words]
    ref_words = json.loads((HERE / args.ref_words).read_text())

    lines, low, cursor, subscribe_at = [], [], 0.0, []
    for seg in ref.EDL:
        if seg["src"] == "endscreen":
            lines.append('    {"src": "endscreen"},')
            continue
        if seg["src"] != "th":
            lines.append(f"    clip({seg['src']!r}, {seg['start']}, {seg['end']}{kwargs_src(seg)}),")
            continue
        ref_toks = [norm(w["text"]) for w in ref_words if seg["start"] <= w["start"] < seg["end"]]
        ref_toks = [t for t in ref_toks if t]
        glob = seg.get("label") in GLOBAL_LABELS
        found = best_span(ref_toks, words, toks, 0.0 if glob else cursor - BACKTRACK)
        if found is None or found[0] < LOW_SCORE:  # out of script order (a late retake, a skipped line): look take-wide
            wide = best_span(ref_toks, words, toks, 0.0)
            if found is None or wide[0] > found[0] + 0.1:
                found = wide
                low.append(f"{seg.get('label', '')}: matched out of script order at {words[found[1]]['start']:.1f}s")
        score, a, b = found
        if not glob:
            cursor = words[b]["end"]
        text = " ".join(w["text"] for w in words[a:b + 1])
        flag = "  # CHECK" if score < LOW_SCORE else ""
        if score < LOW_SCORE:
            low.append(f"{seg.get('label', '')} {words[a]['start']:.2f}: {score:.2f} '{' '.join(ref_toks)}' -> '{text}'")
        subscribe_at += [round(w["start"], 2) for w in words[a:b + 1] if norm(w["text"]).startswith("subscrib")]
        print(f"{words[a]['start']:7.1f} {score:.2f} {seg.get('label', ''):8} {text[:70]}")
        lines.append(f"    th({words[a]['start']:.2f}, {words[b]['end']:.2f}{kwargs_src(seg)}),  # {score:.2f} {text[:90]}{flag}")

    angle2 = (f'ANGLE2 = HERE / {args.angle2!r}\nANGLE2_SYNC = HERE / {args.angle2_sync!r}\n'
              if args.angle2 else "ANGLE2, ANGLE2_SYNC = None, None\n")
    src = f'''"""EDL for take {args.prefix.rstrip("_")}, generated by retarget_edl.py from edl.py; hand edits welcome.

Talking-head times are main-camera time ({Path(args.cam).name}); scores are word-match ratios against take 1.
"""

from pathlib import Path

from edl import CLIPS_DIR, QR_PNG, clip, th  # noqa: F401

HERE = Path(__file__).parent
TAKE_PREFIX = {args.prefix!r}
TALKING_HEAD = HERE / {args.cam!r}
MIC = HERE / {args.mic!r}
SYNC = HERE / {args.sync!r}
{angle2}CAPTION_WORDS = HERE / "work" / "{args.prefix}caption_words.json"

SUBSCRIBE_AT = {subscribe_at}

EDL = [
{chr(10).join(lines)}
]
'''
    (HERE / args.out).write_text(src, encoding="utf-8")
    print(f"Wrote {args.out}: {sum(1 for s in ref.EDL if s['src'] == 'th')} talking-head ranges, subscribe at {subscribe_at}")
    for line in low:
        print("LOW MATCH:", line)


if __name__ == "__main__":
    main()
