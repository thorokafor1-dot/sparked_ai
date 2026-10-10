"""Finds the best short-form moments in a full call transcript with Claude, so segments don't
have to be picked by hand.

Mechanics borrowed from OpenShorts (github.com/mutonby/openshorts, clip_selection.py):
- The transcript is cut into overlapping windows and EVERY window is scored. One call over the
  whole transcript clusters its picks near the start; a positional slice of the answer would too.
- Scores are anchored to a fixed rubric so windows scored in different calls stay comparable,
  then the shortlist is the global top N by score, deduped for overlap, returned in video order.
- Clip edges snap to word boundaries (start ~0.3s before the hook's first word, end ~0.3s after
  the payoff), so nothing starts or ends mid-word.

    python find_moments.py --transcript work/X_transcript.json [--top 6]

run_pipeline.py --auto N calls this and renders the picks directly.
"""
from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path

import anthropic

MODEL = "claude-sonnet-5"
WINDOW_SECS, OVERLAP_SECS, WINDOWS_PER_CALL = 150.0, 30.0, 5
MIN_CLIP, MAX_CLIP = 15.0, 60.0
LEAD, TAIL = 0.3, 0.3

PROMPT = """You pick moments from a Monkey App video-chat recording to become 9:16 Shorts for "Sparked",
an on-camera dating/flirting channel. The host (Thor) chats with women; the brand is cool, smooth,
confident and emotionally intelligent, never cringe or aggressive.

Below are {n} transcript windows (phrases prefixed with absolute start/end seconds). The transcript
has no speaker labels; infer who is talking from context.

For EACH window return its best 1-2 candidate moments (return none only if the window is pure
dead air, setup, or a request to like/subscribe). Each moment:
- is {min_clip:.0f}-{max_clip:.0f} seconds long and STANDS ALONE: a viewer with no context gets it.
- opens on the hook itself (a bold line, a tease, a surprising question, rising tension), not on
  "hi, how are you" small talk. The first 2 seconds must make someone stop scrolling.
- ends right after the payoff (her reaction, the laugh, the comeback, the number/IG, the twist).
- prioritises flirting, banter, chemistry, playful tension. Small talk scores low.

Score each moment 0-100 on this fixed rubric so scores are comparable across calls:
90-100 instantly gripping hook AND a clear, satisfying payoff; would be the channel's best short.
70-89 strong hook or strong payoff, the other is decent.
50-69 watchable flirt beat, but the hook is slow or the payoff is soft.
<50 small talk, needs context, or no payoff.

Return ONLY JSON, no markdown:
{{"moments": [{{"window": <id>, "start": <seconds>, "end": <seconds>, "score": <0-100>,
"hook_line": "<first words spoken in the clip, verbatim from the transcript>",
"why": "<one short sentence: the hook and the payoff>"}}]}}

{windows}"""


def load_env() -> None:
    # same local .env the outlier curation uses (gitignored), CI sets real env vars instead
    env = Path(__file__).resolve().parents[2] / "outlier-tracking" / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            key, sep, value = line.strip().partition("=")
            if sep and not key.startswith("#"):
                os.environ.setdefault(key.strip(), value.strip())


def phrases(words: list[dict], max_gap: float = 0.7) -> list[tuple[float, float, str]]:
    out, cur = [], []
    for w in words:
        if cur and (w["start"] - cur[-1]["end"] > max_gap or len(cur) >= 25):
            out.append((cur[0]["start"], cur[-1]["end"], " ".join(x["text"].strip() for x in cur)))
            cur = []
        cur.append(w)
    if cur:
        out.append((cur[0]["start"], cur[-1]["end"], " ".join(x["text"].strip() for x in cur)))
    return out


def windows(words: list[dict]) -> list[dict]:
    if not words:
        return []
    end, t, out = words[-1]["end"], words[0]["start"], []
    while t < end:
        ws = [w for w in words if t <= w["start"] < t + WINDOW_SECS]
        if ws:
            out.append({"id": len(out), "start": t, "end": min(t + WINDOW_SECS, end),
                        "text": "\n".join(f"[{a:.1f}-{b:.1f}] {s}" for a, b, s in phrases(ws))})
        t += WINDOW_SECS - OVERLAP_SECS
    return out


def score_windows(client: anthropic.Anthropic, batch: list[dict]) -> list[dict]:
    body = "\n\n".join(f"=== WINDOW {w['id']} ({w['start']:.0f}s-{w['end']:.0f}s) ===\n{w['text']}" for w in batch)
    # 4000 tokens cut the first batch's JSON off mid-moment, so every --auto run silently lost the
    # first ~5 minutes of the call (found 2026-10-04). Room to spare now, plus one retry on bad JSON.
    for attempt in range(2):
        msg = client.messages.create(model=MODEL, max_tokens=16000, messages=[{"role": "user", "content": PROMPT.format(
            n=len(batch), min_clip=MIN_CLIP, max_clip=MAX_CLIP, windows=body)}])
        text = "".join(b.text for b in msg.content if b.type == "text").strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
        try:
            return json.loads(text)["moments"]
        except (json.JSONDecodeError, KeyError):
            print(f"could not parse moments for windows {[w['id'] for w in batch]} "
                  f"(attempt {attempt + 1}, stop_reason={msg.stop_reason}):\n{text[-300:]}")
    return []


def snap(m: dict, words: list[dict]) -> dict | None:
    """Word-boundary edges inside the clip-length band, or None if the moment can't fit it."""
    inside = [w for w in words if w["start"] >= m["start"] - 0.5 and w["end"] <= m["end"] + 0.5]
    if not inside:
        return None
    first = inside[0]
    prev_end = max((w["end"] for w in words if w["end"] <= first["start"]), default=0.0)
    start = max(first["start"] - LEAD, prev_end)  # lead-in, but never into the previous word
    last = inside[-1]
    for w in inside:  # longest word-aligned end within the max length
        if w["end"] + TAIL - start <= MAX_CLIP:
            last = w
    end = last["end"] + TAIL
    if end - start < MIN_CLIP:
        return None
    return {**m, "start": round(start, 2), "end": round(end, 2)}


def dedupe(moments: list[dict], ratio: float = 0.4) -> list[dict]:
    kept = []
    for m in sorted(moments, key=lambda m: -m["score"]):
        if all(min(m["end"], k["end"]) - max(m["start"], k["start"]) < ratio * (m["end"] - m["start"]) for k in kept):
            kept.append(m)
    return kept


def find_moments(words: list[dict], top: int = 6) -> list[dict]:
    load_env()
    client = anthropic.Anthropic()
    wins = windows(words)
    raw = []
    for i in range(0, len(wins), WINDOWS_PER_CALL):
        batch = wins[i:i + WINDOWS_PER_CALL]
        print(f"scoring windows {batch[0]['id']}-{batch[-1]['id']} of {len(wins)}", flush=True)
        raw += score_windows(client, batch)
    snapped = [s for m in raw if isinstance(m.get("start"), (int, float)) and (s := snap(m, words))]
    best = dedupe(snapped)[:top]
    return sorted(best, key=lambda m: m["start"])  # global top by score, handed back in video order


def main() -> None:
    parser = argparse.ArgumentParser(description="Rank the best Shorts moments in a word-level transcript.")
    parser.add_argument("--transcript", required=True)
    parser.add_argument("--top", type=int, default=6)
    args = parser.parse_args()
    words = json.loads(Path(args.transcript).read_text(encoding="utf-8"))
    moments = find_moments(words, args.top)
    out = Path(args.transcript).with_name(Path(args.transcript).stem.replace("_transcript", "") + "_moments.json")
    out.write_text(json.dumps(moments, indent=1), encoding="utf-8")
    for m in moments:
        print(f"{m['score']:3d}  {m['start']:7.1f}-{m['end']:7.1f}  {m['hook_line'][:50]!r}  {m['why']}")
    print(out)


if __name__ == "__main__":
    main()
