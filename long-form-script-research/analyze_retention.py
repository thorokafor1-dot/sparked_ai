"""Turns transcripts/*.json into script-structure data for the retention playbook.

Outputs:
  retention_metrics.json  per-video numbers + per-bucket medians (pace, hook length,
                          open-loop / re-hook / pivot / direct-address density, CTA timing)
  skeletons.md            per-video condensed beat sheet: the first line of every
                          minute plus every re-hook / open-loop line, timestamped, so a
                          human (or Claude) can read 40 videos' structure in one sitting

    python long-form-script-research/analyze_retention.py
"""
import glob
import json
import os
import re
import statistics
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))

# Phrase families. Kept as plain regexes so they're easy to extend when the playbook
# work turns up a new device.
DEVICES = {
    "open_loop": r"\b(later (in|on)|by the end|stick around|in a (minute|second|moment)|i'?ll (show|tell|explain) you|we'?ll get (to|there)|more on that|wait (until|till)|you'?ll see (why|what)|coming up)\b",
    "re_hook": r"\b(but here'?s (the|where|what)|but then|that'?s when|and that'?s (not|when)|plot twist|it gets (worse|better|crazier)|what happened next|this is where|little did|turns out|the problem (is|was)|here'?s the thing)\b",
    "stakes": r"\b(if (this|i|we) (fail|lose|don'?t)|only (one|\d+) (chance|shot|minutes?|hours?|days?)|no way|can'?t believe|never (done|seen|been)|first time|last chance|risk|terrified|nervous)\b",
    "direct_address": r"\b(you'?re|you have|you need|you might|you probably|if you'?ve ever|most (guys|men|people)|your)\b",
    "pivot": r"\b(but|so|now|and then|instead)\b",
    "question": r"\?",
    "list_marker": r"\b(number (one|two|three|four|five|\d+)|first(ly)?|second(ly)?|third(ly)?|step (one|two|three|\d+)|tip (number )?\d+|#\d+)\b",
    "cta": r"\b(subscribe|like (this|the) video|comment (below|down)|link (in|below)|description|sponsor|brought to you|patreon|newsletter|my (course|program|coaching))\b",
}
EM_DASH = chr(0x2014)  # house style strips these from generated docs, even inside source titles
REHOOK_LINE = re.compile("|".join(DEVICES[k] for k in ("open_loop", "re_hook", "stakes")), re.I)


def load() -> list[dict]:
    """Skips channels listed under "_excluded" in channels.json (e.g. audience too young)."""
    excluded = set(json.load(open(os.path.join(HERE, "channels.json"), encoding="utf-8")).get("_excluded", {}))
    ts = [json.load(open(p, encoding="utf-8")) for p in sorted(glob.glob(os.path.join(HERE, "transcripts", "*.json")))]
    return [t for t in ts if t["meta"].get("channel") not in excluded]


def bucket(meta: dict) -> str:
    return f"{meta['source']}:{meta['group']}"


def said(segs: list[dict], t0: float, t1: float) -> str:
    return " ".join(s["text"].strip() for s in segs if t0 - 3 <= s["start"] < t1)[:220]


def heat_moments(t: dict, n: int = 3) -> dict:
    """Peaks = most-rewatched moments, dips = most-skipped stretches, each with what was said.
    Ignores the first and last 5% (the hook spike and end-screen fall are always there)."""
    h = t.get("heatmap") or []
    if len(h) < 20:
        return {}
    core = h[5:-5]
    peaks = sorted(core, key=lambda p: -p["value"])
    dips = sorted(core, key=lambda p: p["value"])
    def pick(ps):
        out = []
        for p in ps:
            if all(abs(p["start"] - q["start"]) > 60 for q in out):
                out.append(p)
            if len(out) == n:
                break
        return [{"at": round(p["start"]), "value": p["value"], "said": said(t["segments"], p["start"], p["end"])} for p in out]
    return {"peaks": pick(peaks), "dips": pick(dips)}


def analyze(t: dict) -> dict:
    segs = t["segments"]
    end = max(segs[-1]["start"], 1.0)
    text = " ".join(s["text"] for s in segs)
    words = len(text.split())
    minutes = end / 60
    per_min = lambda pat: round(len(re.findall(pat, text, re.I)) / minutes, 2)
    cta_times = [round(s["start"]) for s in segs if re.search(DEVICES["cta"], s["text"], re.I)]
    rehook_times = [s["start"] for s in segs if REHOOK_LINE.search(s["text"])]
    gaps = [b - a for a, b in zip(rehook_times, rehook_times[1:])]
    # pace by fifths: does delivery speed up or slow down across the video?
    fifths = []
    for i in range(5):
        lo, hi = end * i / 5, end * (i + 1) / 5
        w = sum(len(s["text"].split()) for s in segs if lo <= s["start"] < hi)
        fifths.append(round(w / max((hi - lo) / 60, 0.01)))
    return {
        **{k: t["meta"].get(k) for k in ("vid", "title", "channel", "views", "group", "source", "videoUrl")},
        "bucket": bucket(t["meta"]),
        "minutes": round(minutes, 1),
        "wpm": round(words / minutes),
        "wpm_by_fifth": fifths,
        "first_30s_words": sum(len(s["text"].split()) for s in segs if s["start"] < 30),
        **{f"{k}_per_min": per_min(v) for k, v in DEVICES.items() if k != "cta"},
        "median_secs_between_rehooks": round(statistics.median(gaps)) if gaps else None,
        "first_cta_sec": cta_times[0] if cta_times else None,
        "cta_count": len(cta_times),
        "has_heatmap": bool(t.get("heatmap")),
        **heat_moments(t),
    }


def skeleton(t: dict) -> str:
    m = t["meta"]
    lines = [f"### {m['title']}", f"{m['channel']} | {m.get('views'):,} views | {m['group']} | {m['videoUrl']}", ""]
    seen_min = set()
    for s in t["segments"]:
        mm = int(s["start"] // 60)
        tag = None
        if mm not in seen_min:
            seen_min.add(mm)
            tag = "MIN"
        if REHOOK_LINE.search(s["text"]):
            tag = "HOOK" if tag is None else "MIN+HOOK"
        if s["start"] < 45:
            tag = tag or "OPEN"
        if tag:
            ts = f"{mm}:{int(s['start'] % 60):02d}"
            lines.append(f"- `{ts}` {tag}: {s['text'].strip()[:160]}")
    hm = heat_moments(t)
    for kind in ("peaks", "dips"):
        for p in hm.get(kind, []):
            lines.append(f"- REPLAY {kind[:-1].upper()} `{p['at'] // 60}:{p['at'] % 60:02d}` ({p['value']}): {p['said']}")
    return "\n".join(lines) + "\n"


# Which of the channel's 3 content categories each sample group informs. General groups map to
# the category whose structure they share (social experiments are real-people footage like infield).
CATEGORY = {
    "In-Person": "infield", "social_experiment": "infield", "craft_only": "infield",
    "Preferred:coach kyle": "infield", "Preferred:todd v": "infield", "Preferred:social stoic": "infield",
    "Preferred:trey star": "infield", "Preferred:alex le": "infield", "Preferred:diego day": "infield",
    "Preferred:ian's room": "infield", "@ToddVDating": "infield",
    "Video Chat": "video-chat", "Preferred:jameer": "video-chat", "Preferred:jay throck": "video-chat",
    "Preferred:lil praisey": "video-chat", "Preferred:ugly tv": "video-chat", "@JayThrock": "video-chat",
    "Explainer Video": "explainer", "mens_self_improvement": "explainer", "story_explainer": "explainer",
    "Preferred:coach knox": "explainer",
}


def category(meta: dict) -> str | None:
    return CATEGORY.get(meta.get("group")) or CATEGORY.get(meta.get("channel"))


def attention_curve(ts: list[dict], bins: int = 10) -> list[float]:
    """Average "Most replayed" intensity per 10% of runtime, each video normalised to its own
    peak so a 30M-view video doesn't drown out a 100K one. Skips the hook spike's distortion
    by reporting it, not hiding it: bin 0 is always high."""
    acc = [[] for _ in range(bins)]
    for t in ts:
        h = t.get("heatmap") or []
        if len(h) < 20:
            continue
        top = max(p["value"] for p in h) or 1
        for i, p in enumerate(h):
            acc[min(i * bins // len(h), bins - 1)].append(p["value"] / top)
    return [round(statistics.mean(a), 2) if a else None for a in acc]


def beat_map(cat: str, ts: list[dict], rows: dict) -> str:
    curve = attention_curve(ts)
    n_hm = sum(1 for t in ts if len(t.get("heatmap") or []) >= 20)
    out = [f"# Beat map: {cat}", "",
           f"Generated by analyze_retention.py from {len(ts)} outlier transcripts ({n_hm} with \"Most replayed\" data). "
           "Outliers only, never our own channel. Rules for using this live in `retention_playbook.md` and the script-writer agent.", "",
           "## Replay curve (average \"Most replayed\" intensity per 10% of runtime, 1.0 = each video's own peak)", "",
           "| Runtime | " + " | ".join(f"{i*10}-{i*10+10}%" for i in range(10)) + " |",
           "|---" * 11 + "|",
           "| Replay | " + " | ".join("n/a" if v is None else f"{v:.2f}" for v in curve) + " |", ""]
    valid = [(i, v) for i, v in enumerate(curve) if v is not None and i > 0]
    if valid:
        lo = min(valid, key=lambda x: x[1]); hi = max(valid, key=lambda x: x[1])
        out += [f"After the hook, replay intensity is lowest at {lo[0]*10}-{lo[0]*10+10}% and highest at {hi[0]*10}-{hi[0]*10+10}%. "
                "Put a re-hook or strong friction just before the low zone, and the promised climax in the high zone. "
                "Note: this measures what viewers rewatch, not where they leave; a low zone is where nothing is worth rewatching.", ""]
    out += ["## Reference videos (pick the 2 closest to the concept, mirror their beat proportions)", ""]
    ranked = sorted(ts, key=lambda t: (len(t.get("heatmap") or []) >= 20, t["meta"]["source"] == "niche",
                                       t["meta"].get("views") or 0), reverse=True)
    for t in ranked:
        m, r = t["meta"], rows[t["meta"]["vid"]]
        dur = r["minutes"] * 60 or 1
        label = " (CRAFT-ONLY: borrow structure, never tone or topics)" if m.get("group") == "craft_only" else ""
        label = label or (" (big-channel, adjacent)" if m["source"] == "general" else " (niche)")
        out.append(f"### {m['title']}{label}")
        out.append(f"{m['channel']} | {(m.get('views') or 0):,} views | {r['minutes']} min | {r['wpm']} wpm | `{m['vid']}` | {m['videoUrl']}")
        for kind in ("peaks", "dips"):
            for p in r.get(kind, []):
                out.append(f"- {kind[:-1].upper()} at {round(100 * p['at'] / dur)}% ({p['at'] // 60}:{p['at'] % 60:02d}): {p['said'][:150]}")
        if not r.get("peaks"):
            out.append("- no \"Most replayed\" data; structure only, see skeletons.md")
        out.append("")
    return "\n".join(out)


def main() -> None:
    ts = load()
    rows = [analyze(t) for t in ts]
    numeric = [k for k in rows[0] if isinstance(rows[0][k], (int, float)) and not isinstance(rows[0][k], bool)
               and k != "views"] if rows else []
    buckets = {}
    for b in sorted({r["bucket"] for r in rows}):
        rs = [r for r in rows if r["bucket"] == b]
        buckets[b] = {"n": len(rs), **{k: round(statistics.median(r[k] for r in rs if r[k] is not None), 2)
                                        for k in numeric if any(r[k] is not None for r in rs)}}
    json.dump({"buckets": buckets, "videos": rows}, open(os.path.join(HERE, "retention_metrics.json"), "w",
              encoding="utf-8"), indent=1, ensure_ascii=False)
    with open(os.path.join(HERE, "skeletons.md"), "w", encoding="utf-8") as f:
        f.write("# Script skeletons\n\nGenerated by analyze_retention.py. MIN = first line of each minute, "
                "HOOK = open-loop / re-hook / stakes line, OPEN = first 45s.\n\n")
        for b in sorted({bucket(t["meta"]) for t in ts}):
            f.write(f"## {b}\n\n")
            for t in ts:
                if bucket(t["meta"]) == b:
                    f.write(skeleton(t).replace(EM_DASH, ",") + "\n")
    os.makedirs(os.path.join(HERE, "beat_maps"), exist_ok=True)
    by_vid = {r["vid"]: r for r in rows}
    for cat in ("infield", "video-chat", "explainer"):
        cts = [t for t in ts if category(t["meta"]) == cat]
        with open(os.path.join(HERE, "beat_maps", f"{cat}.md"), "w", encoding="utf-8") as f:
            f.write(beat_map(cat, cts, by_vid).replace(EM_DASH, ","))  # house style: no em dashes, even in source titles
        print(f"beat_maps/{cat}.md: {len(cts)} references, curve {attention_curve(cts)}")
    unmapped = sorted({t["meta"]["group"] for t in ts if not category(t["meta"])})
    if unmapped:
        print("UNMAPPED groups (add to CATEGORY):", unmapped)


if __name__ == "__main__":
    main()
