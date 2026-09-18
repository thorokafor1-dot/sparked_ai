"""Shared transcript-fetching helper for infield/, video-chat/, and explainer/'s
pull_hook_transcripts.py scripts. YouTube's transcript API gets IP-rate-limited after
a burst of requests (hit twice in one research session), so this tries the fast path
first and falls back to a local download + transcribe rather than giving up on the
whole batch.
"""
import os
import tempfile

from youtube_transcript_api import YouTubeTranscriptApi

_whisper_model = None


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
