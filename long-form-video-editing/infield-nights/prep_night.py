"""Prep one infield night: line every phone clip up with the all-night mic, cut a
matching mic track per clip, transcribe it, and write a triage list.

Usage:
    python prep_night.py ../infield-night-2026-04-17 [--no-transcribe] [--model-size small]
    python prep_night.py ../infield-mall --phone-audio   (no Wireless GO: use each clip's own audio)

Night folder layout:
    raw/*.mov              phone clips, named YYYY-MM-DD_HHMMSS (tools/gphotos_fetch.py does this)
    raw/mic/*.wav          Wireless GO chunks (it splits a long recording into 1 h files)
    mic_chunks.json        {"<chunk>.wav": "<local end time ISO>"} from Drive modifiedTime

Writes to <night>/work/:
    <clip>_mic.wav         mic audio cut to the clip's exact length (48 kHz mono)
    <clip>_words.json/.txt mic transcript (word timestamps)
    sync.json              per clip: mic offset, drift, correlation strength
    triage.md              per clip: length, speech share, transcript, for keep/cut calls
"""

import argparse
import datetime as dt
import json
import subprocess
from pathlib import Path

import numpy as np
from scipy.signal import fftconvolve

SR = 4000          # sync analysis rate
SEARCH = 90        # pass-1 seconds either side of the timestamp guess
OUT_SR = 48000


def probe_dur(p: Path) -> float:
    return float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                 "-of", "csv=p=0", str(p)], capture_output=True, text=True).stdout)


def decode(p: Path, sr: int, ss: float = 0.0, t: float | None = None) -> np.ndarray:
    cmd = ["ffmpeg", "-v", "error", "-ss", f"{max(ss, 0):.3f}", "-i", str(p)]
    if t is not None:
        cmd += ["-t", f"{t:.3f}"]
    cmd += ["-ac", "1", "-ar", str(sr), "-f", "f32le", "-"]
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, dtype=np.float32)


class MicTimeline:
    """The mic chunks laid out on wall-clock time (seconds since the first chunk start)."""

    def __init__(self, night: Path):
        ends = json.loads((night / "mic_chunks.json").read_text())
        chunks = []
        for name, end in ends.items():
            if name.startswith("_"):
                continue
            p = night / "raw" / "mic" / name
            d = probe_dur(p)
            chunks.append((dt.datetime.fromisoformat(end) - dt.timedelta(seconds=d), d, p))
        chunks.sort(key=lambda c: c[0])
        self.t0 = chunks[0][0]
        self.chunks = [((s - self.t0).total_seconds(), d, p) for s, d, p in chunks]

    def at(self, when: dt.datetime) -> float:
        return (when - self.t0).total_seconds()

    def slice(self, start: float, dur: float, sr: int) -> np.ndarray:
        """Mic audio for [start, start+dur) on the timeline; gaps are silence."""
        out = np.zeros(int(round(dur * sr)), dtype=np.float32)
        for cs, cd, p in self.chunks:
            a, b = max(start, cs), min(start + dur, cs + cd)
            if b <= a:
                continue
            x = decode(p, sr, a - cs, b - a)
            i = int(round((a - start) * sr))
            n = min(len(x), len(out) - i)
            out[i:i + n] = x[:n]
        return out


def envelope(x: np.ndarray) -> np.ndarray:
    # voice band only (street rumble and hiss differ a lot between phone and lav), 20 ms smoothing
    from scipy.signal import butter, sosfilt
    x = sosfilt(butter(4, [300, 1800], btype="band", fs=SR, output="sos"), x)
    e = np.log1p(50 * np.convolve(np.abs(x), np.ones(SR // 50) / (SR // 50), mode="same"))
    return (e - e.mean()) / (e.std() + 1e-9)


def best_lag(cam: np.ndarray, mic: np.ndarray) -> tuple[float, float]:
    """Lag (s) of cam inside mic, and peak strength vs the correlation's spread."""
    if np.abs(mic).max() < 1e-6:
        return 0.0, 0.0
    c = fftconvolve(envelope(mic), envelope(cam)[::-1], mode="valid")
    i = int(np.argmax(c))
    return i / SR, float((c[i] - np.median(c)) / (c.std() + 1e-9))


def sync_clip(clip: Path, mic: MicTimeline, center: float, search: float) -> dict:
    """center: expected clock error (s) between phone timestamp and mic timeline."""
    when = dt.datetime.strptime(clip.stem, "%Y-%m-%d_%H%M%S")
    dur = probe_dur(clip)
    guess = mic.at(when) + center
    win = min(30.0, dur)
    n = max(1, min(12, int(dur // 60)))
    anchors = np.linspace(0, dur - win, n) if n > 1 else [0.0]
    found = []  # (anchor, mic time of clip start, strength)
    for a in anchors:
        lo = guess + a - search
        lag, strength = best_lag(decode(clip, SR, a, win), mic.slice(lo, win + 2 * search, SR))
        if strength > 0:
            found.append((float(a), lo + lag - a, strength))
    # keep anchors that agree with the strongest one (within 0.3 s plus drift room)
    best = max(found, key=lambda f: f[2]) if found else (0.0, guess, 0.0)
    ok = [f for f in found if abs(f[1] - best[1]) < 0.3 + 0.0005 * abs(f[0] - best[0])]
    if len(ok) >= 2:
        slope, icpt = np.polyfit([f[0] for f in ok], [f[1] for f in ok], 1)
        start, drift = float(icpt), float(slope * dur)
    else:
        start, drift = best[1], 0.0
    agree = len(ok) / max(1, len(found))
    return {"clip": clip.name, "duration": round(dur, 3), "mic_start": round(start, 3),
            "timestamp_error": round(start - mic.at(when), 2), "drift": round(drift, 3),
            "peak": round(best[2], 1), "anchors_agree": f"{len(ok)}/{len(found)}",
            "weak": bool(best[2] < 8 or (len(found) > 2 and agree < 0.5))}


def fmt(t: float) -> str:
    return f"{int(t // 60):02d}:{t % 60:04.1f}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("night")
    ap.add_argument("--no-transcribe", action="store_true")
    ap.add_argument("--model-size", default="small")
    ap.add_argument("--phone-audio", action="store_true",
                    help="no mic was worn: <clip>_mic.wav is the phone's own audio, no sync")
    a = ap.parse_args()
    night = Path(a.night).resolve()
    work = night / "work"
    work.mkdir(exist_ok=True)
    clips = sorted(p for p in (night / "raw").glob("*") if p.suffix.lower() in (".mov", ".mp4"))
    if a.phone_audio:
        syncs = phone_audio(clips, work)
    else:
        syncs = mic_sync(night, clips, work)
    transcribe(night, work, syncs, a)


def phone_audio(clips: list[Path], work: Path) -> list[dict]:
    syncs = []
    for clip in clips:
        out = work / f"{clip.stem}_mic.wav"
        if not out.exists():
            subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(clip), "-vn", "-ac", "1", "-ar", str(OUT_SR),
                            "-c:a", "pcm_s24le", str(out)], check=True)
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0",
                                    str(clip)], capture_output=True, text=True, check=True).stdout)
        syncs.append({"clip": clip.name, "mic_start": 0.0, "duration": dur, "drift": 0.0, "weak": False,
                      "mic_missing_s": 0.0, "source": "phone"})
    (work / "sync.json").write_text(json.dumps(syncs, indent=2))
    return syncs


def mic_sync(night: Path, clips: list[Path], work: Path) -> list[dict]:
    mic = MicTimeline(night)
    # pass 1: wide search to learn the phone-vs-mic clock error from clips that lock in strongly
    first = [sync_clip(c, mic, 0.0, SEARCH) for c in clips]
    strong = [s["timestamp_error"] for s in first if not s["weak"]]
    center = float(np.median(strong)) if strong else 0.0
    print(f"clock error from {len(strong)} strong clip(s): {center:+.1f}s")
    # pass 2: tight search around that clock error
    sync_p = work / "sync.json"
    prev = {p["clip"]: p for p in json.loads(sync_p.read_text())} if sync_p.exists() else {}
    syncs = []
    for clip in clips:
        s = sync_clip(clip, mic, center, 15.0)
        # a soft peak is still trustworthy when it lands on the night's clock error
        s["weak"] = bool(s["weak"] and abs(s["timestamp_error"] - center) > 1.5)
        s["mic_missing_s"] = round(max(0.0, -s["mic_start"]), 1)
        print(f"{clip.name}: mic@{s['mic_start']:.2f}s (timestamp off {s['timestamp_error']:+.1f}s, "
              f"drift {s['drift'] * 1000:+.0f} ms, peak {s['peak']}, anchors {s['anchors_agree']})"
              f"{'  WEAK SYNC' if s['weak'] else ''}")
        syncs.append(s)
        # always recut (cheap) so a changed sync never leaves a stale track behind;
        # a transcript is only reused while the sync it was made from is unchanged
        out = work / f"{clip.stem}_mic.wav"
        old = prev.get(clip.name)
        if old and abs(old["mic_start"] - s["mic_start"]) > 0.05:
            for f in (work / f"{clip.stem}_words.json", work / f"{clip.stem}.txt"):
                f.unlink(missing_ok=True)
        # cut at 48k with any drift spread evenly via resampling
        x = mic.slice(s["mic_start"], s["duration"] + s["drift"], OUT_SR)
        if abs(s["drift"]) > 0.02:
            idx = np.linspace(0, len(x) - 1, int(round(s["duration"] * OUT_SR)))
            x = np.interp(idx, np.arange(len(x)), x).astype(np.float32)
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(OUT_SR), "-ac", "1",
                        "-i", "-", "-c:a", "pcm_s24le", str(out)], input=x.tobytes(), check=True)
    sync_p.write_text(json.dumps(syncs, indent=2))
    return syncs


def transcribe(night: Path, work: Path, syncs: list[dict], a) -> None:
    if a.no_transcribe:
        return
    from faster_whisper import WhisperModel
    model = WhisperModel(a.model_size, device="cpu", compute_type="int8")
    report = [f"# Triage: {night.name}\n"]
    for s in syncs:
        stem = Path(s["clip"]).stem
        words_p = work / f"{stem}_words.json"
        if words_p.exists():
            segs = json.loads(words_p.read_text())
        else:
            res, _ = model.transcribe(str(work / f"{stem}_mic.wav"), word_timestamps=True, language="en",
                                      vad_filter=True)
            segs = [{"start": g.start, "end": g.end, "text": g.text.strip(),
                     "words": [{"w": w.word, "s": w.start, "e": w.end} for w in (g.words or [])]} for g in res]
            words_p.write_text(json.dumps(segs, indent=1))
            (work / f"{stem}.txt").write_text("\n".join(f"[{fmt(g['start'])}] {g['text']}" for g in segs),
                                              encoding="utf-8")
        speech = sum(g["end"] - g["start"] for g in segs)
        report.append(f"## {s['clip']}  ({fmt(s['duration'])}, speech {100 * speech / s['duration']:.0f}%"
                      f"{', WEAK SYNC' if s['weak'] else ''})\n")
        report += [f"- [{fmt(g['start'])}] {g['text']}" for g in segs] or ["- (no speech on mic)"]
        report.append("")
        print(f"transcribed {s['clip']}: {len(segs)} segments")
    (work / "triage.md").write_text("\n".join(report), encoding="utf-8")


if __name__ == "__main__":
    main()
