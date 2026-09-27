"""Shared transcript-fetching helper for infield/, video-chat/, and explainer/'s
pull_hook_transcripts.py scripts. YouTube's transcript API gets IP-rate-limited after
a burst of requests (hit twice in one research session), so this tries the fast path
first and falls back to a local download + transcribe rather than giving up on the
whole batch.
"""
import os
import re
import tempfile

from youtube_transcript_api import YouTubeTranscriptApi

_whisper_model = None

# Deliberately a separate heuristic from qa/checks_data.py's hook-transcripts check
# (different word list, different ratios), so the puller's live filtering and the
# QA gate that verifies its output don't share a bug. Kept simple on purpose, this
# only needs to catch "wrong language entirely", not borderline cases.
_COMMON_EN_WORDS = {
    "the", "you", "and", "to", "a", "i", "it", "is", "that", "of", "in", "what", "my", "so", "like",
    "me", "your", "we", "this", "just", "do", "are", "was", "no", "be", "for", "on", "have", "with",
    "not", "she", "he", "her", "his", "if", "but", "can", "how", "up", "out", "about", "know",
}


def looks_english(text: str) -> bool:
    """Cheap language gate: a dubbed/foreign-audio video under an English title should
    not poison the pattern research. Same signal as the QA check (non-Latin/accented
    character density, common-English-word ratio), reimplemented independently."""
    text = (text or "").strip()
    if not text:
        return False
    non_ascii = sum(1 for ch in text if ord(ch) > 127 and ch.isalpha()) / max(len(text), 1)
    if non_ascii > 0.2:
        return False
    words = re.findall(r"[A-Za-z']+", text.lower())
    if len(words) < 20:
        return True  # too short to judge reliably, don't reject on word ratio alone
    english_ratio = sum(1 for w in words if w in _COMMON_EN_WORDS) / len(words)
    return english_ratio >= 0.08


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        _whisper_model = WhisperModel("small", device="cpu", compute_type="int8")
    return _whisper_model


def _fetch_via_captions(vid: str, window_seconds: int) -> str:
    snippets = YouTubeTranscriptApi().fetch(vid)
    lines = [s.text for s in snippets if s.start < window_seconds]
    return " ".join(lines).strip()


def _fetch_via_local_transcription(vid: str, window_seconds: int) -> str:
    import yt_dlp

    with tempfile.TemporaryDirectory() as tmpdir:
        out_path = os.path.join(tmpdir, f"{vid}.%(ext)s")
        ydl_opts = {
            "format": "bestaudio",
            "outtmpl": out_path,
            "postprocessors": [{"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": "5"}],
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([f"https://www.youtube.com/watch?v={vid}"])

        mp3_path = os.path.join(tmpdir, f"{vid}.mp3")
        model = _get_whisper_model()
        segments, _info = model.transcribe(mp3_path, word_timestamps=False, clip_timestamps=[0, window_seconds])
        return " ".join(s.text.strip() for s in segments)


def fetch_hook_transcript(vid: str, window_seconds: int = 90) -> str:
    """Returns the opening `window_seconds` of a video's transcript. Tries YouTube's
    caption API first (fast, no download); on ANY failure, no captions available,
    IP-block/rate-limit, whatever, falls back to a local yt-dlp download +
    faster-whisper transcription instead of skipping the video outright. Only raises
    if the local fallback itself fails (e.g. the video is private/deleted)."""
    try:
        return _fetch_via_captions(vid, window_seconds)
    except Exception:
        return _fetch_via_local_transcription(vid, window_seconds)


def _data_path() -> str:
    """The niche-long-form outlier data to pull candidates from. Override with the
    HOOK_RESEARCH_DATA_PATH env var to point at a snapshot (e.g. a fresher copy read
    from origin/main) without touching the tracked working-tree file."""
    override = os.getenv("HOOK_RESEARCH_DATA_PATH")
    if override:
        return override
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "..", "outlier-tracking", "niche-long-form", "data.json")


def pull_hook_transcripts(format_label: str, out_path: str, window_seconds: int = 90,
                           target: int = 12, max_candidates: int = 60) -> None:
    """Shared driver for the 3 subfolders' pull_hook_transcripts.py: load candidates
    for one Format value, sorted by score, walk the FULL ranked list (not a fixed
    top-N slice) fetching transcripts and skipping empty/non-English ones on the fly,
    until `target` good transcripts are collected or `max_candidates` have been tried.
    Walking the full list instead of a fixed slice means a format with a high
    non-English/empty rate (explainer, video-chat) still ends up with a full, usable
    sample instead of silently returning mostly-unusable rows."""
    import json

    with open(_data_path(), encoding="utf-8") as f:
        rows = json.load(f)
    candidates = sorted((r for r in rows if r.get("format") == format_label),
                        key=lambda r: r.get("score", 0), reverse=True)

    results = []
    tried = 0
    for row in candidates:
        if len(results) >= target or tried >= max_candidates:
            break
        tried += 1
        vid = row["vid"]
        try:
            text = fetch_hook_transcript(vid, window_seconds)
        except Exception as e:
            print(f"SKIP {vid} ({row['title'][:60]}): fetch failed: {e}")
            continue
        if not looks_english(text):
            print(f"SKIP {vid} ({row['title'][:60]}): not English (or empty)")
            continue

        results.append({
            "title": row["title"],
            "channel": row["channel"],
            "views": row["views"],
            "subscribers": row["subscribers"],
            "score": row.get("score"),
            "reason": row.get("reason"),
            "duration": row.get("duration"),
            "videoUrl": row["videoUrl"],
            "vid": vid,
            "hookTranscript": text,
        })
        print(f"OK   {vid} ({row['title'][:60]})")

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nWrote {len(results)} usable hook transcripts to {out_path} "
          f"(tried {tried}/{len(candidates)} '{format_label}' candidates)")
