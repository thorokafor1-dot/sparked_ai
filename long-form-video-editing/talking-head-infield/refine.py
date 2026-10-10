"""Whole-video cut planning for the talking head, run before anything renders.

Each rule is a user correction on take 2:
- never cut a sentence short: a piece may not end inside a word or while the voice is still going
- script-reading glances: after a finished sentence he looks off at his script; those silent stretches go
  (looking away MID-sentence while thinking stays, that's his natural style)
- unintentional repeats: a false start then a restart ("alright number, alright number one") keeps only
  the clean attempt
Every change is reported so it can be checked.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

END_PUNCT = ".?!"
GLANCE_MIN_GAP = 0.3  # silent stretch worth checking for a script glance
GLANCE_AWAY = 0.4  # fraction of that stretch spent looking off-camera that marks it as a script glance
WORD_TAIL = 0.12  # kept after the last word of a piece
WORD_LEAD = 0.08  # kept before the first word after a cut
MAX_EXTEND = 0.8  # how far a piece end may grow to let a still-sounding word finish
MAX_PAUSE = 0.5  # pauses longer than this get tightened...
TIGHT_PAUSE = 0.3  # ...down to about this
DRAMATIC_PAUSE = 0.8  # one pause per DRAMATIC_EVERY seconds may stay this long, for effect
DRAMATIC_EVERY = 60.0
RESTART_SPAN = 10  # longest aborted attempt (words) treated as a false start
# 2-word repeats count only as an immediate restart ('alright number, alright number one'); 'we're not gonna be
# alone, they're gonna be in a group' is normal speech and v12's looser rule mangled it
RESTART_WINDOW = 6.0  # a real false start and its restart sit within seconds of each other in the recording;
# a phrase repeated across an editorial join (e.g. "not knowing what to say. Here's exactly what to say") is intentional


def load_words(path: Path) -> list[dict]:
    words = []
    for w in json.loads(path.read_text()):
        if words and w["text"].startswith("-"):  # whisper splits hyphenated words ("go" "-tos")
            words[-1] = dict(words[-1], text=words[-1]["text"] + w["text"], end=w["end"])
        else:
            words.append(dict(w))
    for i, w in enumerate(words):
        w["id"] = i  # identity: whisper can give two words the same start time ('Number' and 'seven')
    return words


def norm(text: str) -> str:
    return re.sub(r"[^a-z0-9']", "", text.lower())


def sentence_end(w: dict) -> bool:
    return w["text"].rstrip()[-1:] in END_PUNCT


MAX_WORD = 0.8  # longer "words" are whisper stretching a word across a pause; only the first part is speech


def wend(w):
    return min(w["end"], w["start"] + MAX_WORD)


def frange(a, b, step=0.05):
    n = max(int((b - a) / step), 1)
    return [a + i * step for i in range(n)]


def words_in(words, s, e):
    return [w for w in words if s - 0.02 <= w["start"] < e]


def guard_end(piece, words, voiced, exact_end, log):
    """Extend a piece end so the last word (and any voice still sounding) finishes."""
    s, e = piece
    # a piece must not START inside a word either (first syllable clipped)
    straddle = [w for w in words if w["start"] < s - 0.02 and wend(w) > s + 0.05]
    if straddle:
        new = straddle[0]["start"] - WORD_LEAD
        log.append(f"  start {s:.2f} -> {new:.2f}: '{straddle[0]['text']}' would start mid-word")
        s = new
    inside = words_in(words, s, e)
    if inside and wend(inside[-1]) + WORD_TAIL > e:
        new = min(wend(inside[-1]) + WORD_TAIL, e + MAX_EXTEND)
        if new > e + 0.03:
            log.append(f"  end {e:.2f} -> {new:.2f}: '{inside[-1]['text']}' was cut short")
        e = max(e, new)
    if not exact_end:  # exact ends are hand-picked word boundaries on run-ons; the next word must not leak in
        # finish the sound of the current word, but never run into the NEXT word (v10 left a stray "and" at 0:21)
        nxt = [w["start"] for w in words if w["start"] >= e - 0.02]
        cap = min(e + MAX_EXTEND, (nxt[0] - 0.05) if nxt else e + MAX_EXTEND)
        grown = 0.0
        while voiced(e) and e + 0.02 <= cap:
            e += 0.02
            grown += 0.02
        if grown > 0.05:
            log.append(f"  end -> {e:.2f}: voice still sounding, extended {grown:.2f}s")
    return s, e


def cut_glances(piece, words, gaze, voiced, log):
    """Cut silent stretches where he's looking off-camera: that's him reading the script between lines.

    Scans the picture directly (0.1s steps) instead of trusting word timings or punctuation, which this
    transcript barely has. Looking away while still talking is thinking, his natural style, and stays.
    """
    s, e = piece
    ts = frange(s, e, 0.1)
    away = [gaze.away(t) and sum(voiced(t + d) for d in (0.0, 0.03, 0.06)) == 0 for t in ts]
    cuts, i = [], 0
    while i < len(ts):
        if away[i]:
            j = i
            while j < len(ts) and away[j]:
                j += 1
            c0g, c1g = ts[i], ts[j - 1] + 0.1
            if (j - i) * 0.1 >= GLANCE_MIN_GAP and not any(c0g + 0.03 < w["start"] < c1g - 0.03 for w in words_in(words, c0g - 0.5, c1g + 0.5)):
                cuts.append((c0g, c1g))
            i = j
        else:
            i += 1
    out, cur = [], s
    for c0, c1 in cuts:
        log.append(f"  {c0:.2f}-{c1:.2f}: silent look-away (script glance), cut")
        out.append((cur, c0))
        cur = c1
    out.append((cur, e))
    return [(a, b) for a, b in out if b - a > 0.2]


def find_restarts(seq):
    """seq: list of words in output order. Returns (i, j) index pairs: words i..j-1 are an aborted attempt."""
    toks = [norm(w["text"]) for w in seq]
    for j in range(len(seq)):
        for k in (4, 3, 2):
            if j + k > len(seq):
                continue
            for i in range(max(0, j - RESTART_SPAN), j - k + 1):
                if toks[i:i + k] == toks[j:j + k] and all(toks[i:i + k]) and seq[i]["start"] < seq[j]["start"] - 0.1 and \
                        j - i <= k + 3 and (k >= 3 or j - i <= 3) and \
                        seq[j]["start"] - seq[i]["start"] < RESTART_WINDOW and \
                        not any(sentence_end(w) for w in seq[i:j - 1]):
                    return i, j
    return None


def remove_span(plan, t0, t1):
    """Remove source time [t0, t1) from every piece in the plan."""
    for key, pieces in plan.items():
        new = []
        for s, e in pieces:
            if e <= t0 or s >= t1:
                new.append((s, e))
                continue
            if t0 - s > 0.08:
                new.append((s, t0))
            if e - t1 > 0.08:
                new.append((t1, e))
        plan[key] = new


def tighten_pauses(plan, words, voiced, log):
    """Silences inside a piece read as dead air when they pile up (user: 'too much silent moments in a row').
    Found from the mic (whisper stretches words across pauses and hides them). Every silence over MAX_PAUSE is
    tightened to ~TIGHT_PAUSE, except one dramatic pause per DRAMATIC_EVERY seconds of output, kept up to
    DRAMATIC_PAUSE."""
    gaps, out_t = [], 0.0
    for k in plan:
        for s, e in plan[k]:
            ts = frange(s, e, 0.02)
            i = 0
            while i < len(ts):
                if not voiced(ts[i]):
                    j = i
                    while j < len(ts) and not voiced(ts[j]):
                        j += 1
                    a, b = ts[i], ts[j - 1] + 0.02
                    # a soft word can sit under the voicing threshold: never treat a stretch holding a word start as a pause
                    soft_word = any(a + 0.03 < w["start"] < b - 0.03 for w in words_in(words, a - 0.5, b + 0.5))
                    if b - a > MAX_PAUSE and a > s + 0.05 and b < e - 0.05 and not soft_word:
                        gaps.append((out_t + a - s, a, b))
                    i = j
                else:
                    i += 1
            out_t += e - s
    keep_long = set()
    for bucket in {int(t // DRAMATIC_EVERY) for t, *_ in gaps}:
        keep_long.add(max((g for g in gaps if int(g[0] // DRAMATIC_EVERY) == bucket), key=lambda g: g[2] - g[1]))
    for g in gaps:
        _, a, b = g
        target = DRAMATIC_PAUSE if g in keep_long else TIGHT_PAUSE
        if b - a <= target + 0.05:
            continue
        log.append(f"  pause {a:.2f}-{b:.2f} ({b - a:.2f}s) -> ~{target:.1f}s" + (" (kept dramatic)" if g in keep_long else ""))
        remove_span(plan, a + target / 2, b - target / 2)


DANGLING = {"and", "so", "but", "or", "because", "the", "a", "an", "to", "of", "for", "with", "that", "i", "i'm",
            "you", "your", "if", "like", "when", "then", "um", "uh", "gonna", "just", "is", "are", "in", "on", "at",
            "my", "it's", "they", "she", "he", "we", "this"}


def fix_dangling(edl, plan, words, log):
    """A piece that ends on a word that can't end a sentence ('and', 'so', 'the'...) and then jumps elsewhere
    sounds cut off (user heard 'and...' then a cut). Trim that word, or drop the piece if that's all it holds."""
    order = []
    for k in sorted(plan):
        for p in plan[k]:
            order.append((k, p))
    for idx, (k, (s, e)) in enumerate(order):
        nxt = order[idx + 1] if idx + 1 < len(order) else None
        # the next piece continues the sentence if only silence was removed in between (pause tightening)
        contiguous = nxt is not None and nxt[0] in (k, k + 1) and 0 <= nxt[1][0] - e < 3.0 and \
            not words_in(words, e, nxt[1][0])
        if contiguous:
            continue
        ws = words_in(words, s, e)
        while ws and norm(ws[-1]["text"]) in DANGLING:
            ws = ws[:-1]
        full = words_in(words, s, e)
        if len(ws) == len(full):
            continue
        cut = full[len(ws):]
        new = (s, min(ws[-1]["end"] + WORD_TAIL, cut[0]["start"] - 0.03)) if ws else None
        log.append(f"  dangling end '{' '.join(w['text'] for w in cut)}' at {e:.2f}: "
                   + ("trimmed" if new else "piece dropped"))
        plan[k] = [q for q in plan[k] if q != (s, e)] + ([new] if new else [])
        plan[k].sort()


EDGE_TAIL = 0.18  # kept after the voice actually trails off (natural decay)
EDGE_LEAD = 0.07  # kept before the voice comes in


def tighten_edges(plan, words, audible, log):
    """Dead air piled up at the cuts (a piece's silent tail + the next piece's silent head reached 0.7-1.4s on
    v10). Trim every edge to where the voice really stops/starts on the mic. Exact hand-picked edges included,
    since only silence is removed; a transcript word is never cut into."""
    trimmed = 0.0
    for k in plan:
        new = []
        for s, e in plan[k]:
            ws = words_in(words, s, e)
            t = e
            while t > s + 0.2 and not audible(t - 0.02):
                t -= 0.02
            ne = max(t + EDGE_TAIL, (ws[-1]["start"] + 0.08) if ws else s)
            t = s
            while t < ne - 0.2 and not audible(t):
                t += 0.02
            ns = min(t - EDGE_LEAD, (ws[0]["start"] + 0.45) if ws else ne)  # whisper starts often run early
            ns, ne = max(ns, s), min(ne, e)
            trimmed += (ns - s) + (e - ne)
            new.append((ns, ne))
        plan[k] = new
    log.append(f"  edges tightened: {trimmed:.1f}s of dead air removed at cuts")


def dedupe(plan, words, log):
    """Every recorded word plays at most once. Overlapping or reordered EDL ranges played words twice
    ("alright number, alright number one"); the later piece loses the repeated words wherever they sit."""
    used = set()
    for k in plan:
        fixed = []
        for s, e in plan[k]:
            inside = words_in(words, s, e)
            dup = [w for w in inside if w["id"] in used]
            if dup:
                log.append(f"  piece {s:.2f}-{e:.2f}: '{' '.join(w['text'] for w in dup)}' already played, removed")
                runs, cur = [], s
                for w in inside:  # keep the stretches between repeated words
                    if w["id"] in used:
                        if w["start"] - 0.03 - cur > 0.15:
                            runs.append((cur, w["start"] - 0.03))
                        cur = max(cur, w["end"] + 0.02)
                if e - cur > 0.15:
                    runs.append((cur, e))
                pieces = [r for r in runs if words_in(words, *r)]
            else:
                pieces = [(s, e)]
            for r in pieces:
                used.update(w["id"] for w in words_in(words, *r))
            fixed += pieces
        plan[k] = fixed


MIN_PIECE = 0.6  # shorter talking-head pieces flash on screen and read as a glitch (v12: a 0.18s sliver before a side-angle cut)


def merge_slivers(plan, words, log):
    """Join a too-short piece to its neighbour when only silence sits between them; drop it if it can't join
    and holds no complete word worth keeping."""
    for k in plan:
        ps = sorted(plan[k])
        out = []
        for s, e in ps:
            if out and (e - s < MIN_PIECE or out[-1][1] - out[-1][0] < MIN_PIECE) and \
                    0 <= s - out[-1][1] < 1.2 and not words_in(words, out[-1][1], s):
                log.append(f"  sliver merged: {out[-1][0]:.2f}-{out[-1][1]:.2f} + {s:.2f}-{e:.2f}")
                out[-1] = (out[-1][0], e)
            else:
                out.append((s, e))
        plan[k] = out


def resolve_overlaps(plan, log):
    """Where a later piece re-covers the tail of an earlier one (overlapping EDL ranges), trim the EARLIER
    piece's tail so the later piece carries the sentence whole. Trimming the later piece's head instead (and
    then a dangling-word trim on the earlier one) lost "It's" from both on take 2."""
    order = [(k, i) for k in sorted(plan) for i in range(len(plan[k]))]
    for x, (ka, ia) in enumerate(order):
        a0, a1 = plan[ka][ia]
        for kb, ib in order[x + 1:x + 6]:
            b0, b1 = plan[kb][ib]
            if a0 < b0 < a1 and b1 > a1:
                log.append(f"  overlap: {a0:.2f}-{a1:.2f} trimmed to end at {b0:.2f} (next piece continues from there)")
                a1 = b0 - 0.02
                plan[ka][ia] = (a0, a1)


def refine(edl, plan, words, gaze, voiced, cut_out=(), audible=None):
    """plan: {edl index: [(start, end), ...]} for talking-head segments, in EDL order. Returns the new plan + log."""
    log = []
    for k in plan:
        seg = edl[k]
        out = []
        for p in plan[k]:
            p = guard_end(p, words, voiced, seg.get("exact_end", False), log)
            out += cut_glances(p, words, gaze, voiced, log)
        plan[k] = out
    for t0, t1 in cut_out:
        log.append(f"  misspeak cut {t0:.2f}-{t1:.2f}")
        remove_span(plan, t0, t1)
    resolve_overlaps(plan, log)
    dedupe(plan, words, log)
    tighten_pauses(plan, words, voiced, log)
    # unintentional repeats, across piece and segment boundaries, in output order
    for _ in range(50):
        seq = [w for k in plan for s, e in plan[k] for w in words_in(words, s, e)]
        hit = find_restarts(seq)
        if not hit:
            break
        i, j = hit
        a, b = seq[i], seq[j]
        log.append(f"  repeat: '{' '.join(w['text'] for w in seq[i:j])}' then restart '{b['text']}...' -> "
                   f"cut {a['start']:.2f}-{b['start']:.2f}")
        remove_span(plan, a["start"] - 0.03, b["start"] - WORD_LEAD)
    fix_dangling(edl, plan, words, log)
    tighten_edges(plan, words, audible or voiced, log)
    fix_dangling(edl, plan, words, log)  # edges can expose a dangling word
    dedupe(plan, words, log)
    merge_slivers(plan, words, log)
    # leftover slivers with no words in them are just scraps of breath or room tone
    for k in plan:
        plan[k] = [(s, e) for s, e in plan[k] if words_in(words, s, e) or e - s > 0.6]
    return plan, log
