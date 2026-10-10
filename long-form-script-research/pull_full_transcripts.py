"""Pulls FULL timestamped transcripts (not just the hook window) for script-structure
research. Two sources:
  niche   - top niche long-form outliers per format from outlier-tracking/niche-long-form
  general - general_candidates.json from find_general_outliers.py

Each video is saved once as transcripts/<vid>.json ({meta, segments:[{start, text}]}),
so reruns skip what's already pulled. Fetch order: YouTube caption API, then yt-dlp
auto-subs (different endpoint, survives caption-API rate limits), then faster-whisper
only with --whisper (slow on CPU for 20+ minute videos).

    python long-form-script-research/pull_full_transcripts.py --source all [--per-format 8] [--whisper]
"""
import argparse
import json
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(ROOT, "long-form-hook-research"))
from _common import looks_english  # noqa: E402

_whisper = {}

OUT_DIR = os.path.join(HERE, "transcripts")
NICHE_FORMATS = ("In-Person", "Video Chat", "Explainer Video")
# The user's reference creators (memory: project_niche_channels_cold_approach). Their best
# niche-data row is always studied, whatever its outlier score.
PREFERRED = ("coach kyle", "todd v", "diego day", "social stoic", "ian's room", "alex le", "trey star",
             "coach knox", "jameer", "lil praisey", "jay throck", "ugly tv")
MIN_SECONDS = 6 * 60
WHISPER_MODEL = "base.en"  # structure research, not captions: speed beats accuracy


def _secs(d) -> int:
    if isinstance(d, (int, float)):
        return int(d)
    parts = [int(p) for p in str(d or "0").split(":")]
    total = 0
    for p in parts:
        total = total * 60 + p
    return total


def via_captions(vid: str) -> list[dict]:
    from youtube_transcript_api import YouTubeTranscriptApi
    return [{"start": round(s.start, 1), "text": s.text} for s in YouTubeTranscriptApi().fetch(vid)]


def via_ytdlp_subs(vid: str) -> list[dict]:
    import yt_dlp
    with tempfile.TemporaryDirectory() as tmp:
        opts = {"skip_download": True, "writeautomaticsub": True, "writesubtitles": True,
                "subtitleslangs": ["en", "en-orig", "en-US"], "subtitlesformat": "json3",
                "outtmpl": os.path.join(tmp, "%(id)s"), "quiet": True, "no_warnings": True}
        with yt_dlp.YoutubeDL(opts) as y:
            y.download([f"https://www.youtube.com/watch?v={vid}"])
        files = [f for f in os.listdir(tmp) if f.endswith(".json3")]
        if not files:
            raise RuntimeError("no subtitles")
        data = json.load(open(os.path.join(tmp, files[0]), encoding="utf-8"))
    segs = []
    for ev in data.get("events", []):
        text = "".join(s.get("utf8", "") for s in ev.get("segs") or []).strip()
        if text:
            segs.append({"start": round(ev.get("tStartMs", 0) / 1000, 1), "text": text})
    return segs


def via_whisper(vid: str) -> list[dict]:
    import yt_dlp
    with tempfile.TemporaryDirectory() as tmp:
        opts = {"format": "bestaudio", "outtmpl": os.path.join(tmp, f"{vid}.%(ext)s"), "quiet": True,
                "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "5"}]}
        with yt_dlp.YoutubeDL(opts) as y:
            y.download([f"https://www.youtube.com/watch?v={vid}"])
        if "m" not in _whisper:
            from faster_whisper import WhisperModel
            _whisper["m"] = WhisperModel(WHISPER_MODEL, device="cpu", compute_type="int8", cpu_threads=os.cpu_count() or 4)
        segments, _ = _whisper["m"].transcribe(os.path.join(tmp, f"{vid}.mp3"), vad_filter=True, beam_size=1)
        return [{"start": round(s.start, 1), "text": s.text.strip()} for s in segments]


def heatmap(vid: str) -> list[dict]:
    """YouTube's public "Most replayed" curve: 100 points of relative replay intensity (0-1).
    The only retention-like signal available for other creators' videos. Small videos have none."""
    import yt_dlp
    with yt_dlp.YoutubeDL({"quiet": True, "no_warnings": True, "skip_download": True}) as y:
        h = y.extract_info(f"https://www.youtube.com/watch?v={vid}", download=False).get("heatmap") or []
    return [{"start": round(p["start_time"], 1), "end": round(p["end_time"], 1), "value": round(p["value"], 3)} for p in h]


def fetch(vid: str, whisper: bool, whisper_only: bool = False) -> tuple[list[dict], str]:
    methods = [] if whisper_only else [("captions", via_captions), ("ytdlp-subs", via_ytdlp_subs)]
    if whisper or whisper_only:
        methods.append(("whisper", via_whisper))
    last = None
    for name, fn in methods:
        try:
            segs = fn(vid)
            if segs:
                return segs, name
        except Exception as e:
            last = e
    raise RuntimeError(f"all methods failed: {str(last)[:80]}")


def niche_candidates(per_format: int) -> list[dict]:
    rows = json.load(open(os.path.join(ROOT, "outlier-tracking", "niche-long-form", "data.json"), encoding="utf-8"))
    out = []
    for fmt in NICHE_FORMATS:
        ranked = sorted((r for r in rows if r.get("format") == fmt and _secs(r.get("duration")) >= MIN_SECONDS),
                        key=lambda r: float(r.get("score") or 0), reverse=True)
        out += [{**r, "source": "niche", "group": fmt, "_quota": per_format} for r in ranked[:per_format * 4]]
    for name in PREFERRED:
        mine = [r for r in rows if name in r["channel"].lower() and _secs(r.get("duration")) >= MIN_SECONDS]
        out += [{**r, "source": "niche", "group": f"Preferred:{name}", "_quota": 1}
                for r in sorted(mine, key=lambda r: -int(str(r.get("views") or 0).replace(",", "")))[:3]]
    return out


def general_candidates() -> list[dict]:
    path = os.path.join(HERE, "general_candidates.json")
    if not os.path.exists(path):
        print("No general_candidates.json, run find_general_outliers.py first")
        return []
    return [{**r, "source": "general", "_quota": 10**6} for r in json.load(open(path, encoding="utf-8"))]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", choices=["niche", "general", "all"], default="all")
    ap.add_argument("--per-format", type=int, default=8, help="niche videos kept per format")
    ap.add_argument("--whisper", action="store_true", help="allow slow local transcription fallback")
    ap.add_argument("--whisper-only", action="store_true", help="skip caption endpoints (use while YouTube 429s them)")
    args = ap.parse_args()

    os.makedirs(OUT_DIR, exist_ok=True)
    cands = []
    if args.source in ("niche", "all"):
        cands += niche_candidates(args.per_format)
    if args.source in ("general", "all"):
        cands += general_candidates()

    kept: dict[str, int] = {}
    for c in cands:
        key = f"{c['source']}:{c['group']}"
        if kept.get(key, 0) >= c["_quota"]:
            continue
        path = os.path.join(OUT_DIR, f"{c['vid']}.json")
        if os.path.exists(path):
            kept[key] = kept.get(key, 0) + 1
            d = json.load(open(path, encoding="utf-8"))
            if "heatmap" not in d:  # backfill transcripts pulled before heatmaps were captured
                try:
                    d["heatmap"] = heatmap(c["vid"])
                    json.dump(d, open(path, "w", encoding="utf-8"), ensure_ascii=False)
                except Exception as e:
                    print(f"WARN {c['vid']} heatmap: {str(e)[:60]}")
            continue
        try:
            segs, method = fetch(c["vid"], args.whisper, args.whisper_only)
        except Exception as e:
            print(f"SKIP {c['vid']} {c['title'][:50]}: {e}")
            continue
        if not looks_english(" ".join(s["text"] for s in segs[:200])):
            print(f"SKIP {c['vid']} {c['title'][:50]}: not English")
            continue
        meta = {k: c.get(k) for k in ("vid", "title", "channel", "views", "subscribers", "duration",
                                       "publishedAt", "videoUrl", "source", "group", "score", "ratio")}
        meta["method"] = method
        try:
            hm = heatmap(c["vid"])
        except Exception:
            hm = []
        json.dump({"meta": meta, "segments": segs, "heatmap": hm}, open(path, "w", encoding="utf-8"), ensure_ascii=False)
        kept[key] = kept.get(key, 0) + 1
        print(f"OK   {c['vid']} [{key}] via {method}: {c['title'][:55]}")

    print("\nKept per bucket:", json.dumps(kept, indent=1))


if __name__ == "__main__":
    main()
