"""ffprobe/ffmpeg helpers shared by the media checks."""
from __future__ import annotations

import json
import re
import subprocess
from functools import lru_cache
from pathlib import Path


@lru_cache(maxsize=64)
def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    if out.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {out.stderr.strip()[:200]}")
    return json.loads(out.stdout)


def streams(path: Path, kind: str) -> list[dict]:
    return [s for s in probe(path)["streams"] if s.get("codec_type") == kind]


def duration(path: Path) -> float:
    return float(probe(path)["format"].get("duration", 0))


def fps(stream: dict) -> float:
    num, _, den = stream.get("avg_frame_rate", "0/1").partition("/")
    return float(num) / float(den or 1) if float(den or 1) else 0.0


@lru_cache(maxsize=16)
def analyze(path: Path) -> dict:
    """One decode pass: black spans, frozen spans, silent spans, loudness.

    Video is scaled to 320px wide first so the filters are cheap; decode is the main cost
    (~10-20x realtime for 1080p H.264).
    """
    has_audio = bool(streams(path, "audio"))
    vf = "[0:v]scale=320:-2,blackdetect=d=0.5:pix_th=0.10,freezedetect=n=0.003:d=3[v]"
    af = ";[0:a]silencedetect=n=-50dB:d=2,ebur128=peak=true:framelog=verbose[a]" if has_audio else ""
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-filter_complex", vf + af,
           "-map", "[v]"] + (["-map", "[a]"] if has_audio else []) + ["-f", "null", "-"]
    err = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace").stderr

    def spans(start_rx: str, end_rx: str) -> list[tuple[float, float]]:
        starts = [float(x) for x in re.findall(start_rx, err)]
        ends = [float(x) for x in re.findall(end_rx, err)]
        total = duration(path)
        return [(s, ends[i] if i < len(ends) else total) for i, s in enumerate(starts)]

    black = [(float(a), float(b)) for a, b in re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", err)]
    frozen = spans(r"freeze_start: ([\d.]+)", r"freeze_end: ([\d.]+)")
    silent = spans(r"silence_start: (-?[\d.]+)", r"silence_end: ([\d.]+)")
    summary = err[err.rfind("Summary:"):] if "Summary:" in err else ""
    lufs = re.search(r"I:\s+(-?[\d.]+) LUFS", summary)
    peak = re.search(r"Peak:\s+(-?[\d.]+|-inf) dBFS", summary)
    return {
        "black": black,
        "frozen": frozen,
        "silent": silent,
        "lufs": float(lufs.group(1)) if lufs else None,
        "true_peak": float(peak.group(1)) if peak and peak.group(1) != "-inf" else None,
    }
