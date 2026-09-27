"""Checks for rendered videos (shorts and long-form edits).

Catches the mistakes that otherwise only show up when the user watches the render:
wrong format, missing or clipped audio, black or frozen stretches, dead air, bad
loudness, and (for the Monkey App shorts) stretches where the crop loses every face.
"""
from __future__ import annotations

import sys
from pathlib import Path

import media
from checks import ROOT, check

SHORTS = ["long-form-to-shorts-video-editing/*/output/*.mp4"]
LONG_FORM = ["long-form-video-editing/*/output/*.mp4", "long-form-video-editing/*/out/*.mp4"]
ALL_RENDERS = SHORTS + LONG_FORM
VIDEO_EXTS = {".mp4", ".mov"}

LUFS_RANGE = (-18.0, -10.0)   # YouTube/TikTok/IG normalise around -14; outside this sounds too quiet or crushed
MAX_TRUE_PEAK = -0.5          # dBFS; above this the platform encode is likely to clip
SPIKE_LU = 8.0               # momentary (400ms) loudness this far above integrated = jarring spike
EDGE_GRACE = 1.5              # seconds at the very end where a fade to black/silence is intentional


def _fmt(t: float) -> str:
    return f"{int(t // 60)}:{t % 60:04.1f}"


def being_written(path: Path) -> bool:
    """True while a render is still writing this file (e.g. another session's ffmpeg).

    A half-written MP4 has no moov atom yet, so probing it "fails" even though nothing is wrong;
    it gets checked once the writer finishes.
    """
    try:
        import psutil
    except ImportError:
        psutil = None
    if psutil:
        name = path.name.lower()
        for proc in psutil.process_iter(["name", "cmdline"]):
            try:
                if (proc.info["name"] or "").lower().startswith("ffmpeg") and \
                        any(name in (arg or "").lower() for arg in proc.info["cmdline"] or []):
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    import time
    # no writer process: the file is finished or just flushing. Wait for it to settle, then check it for real
    # (returning True here used to make a freshly written render silently "pass").
    age = time.time() - path.stat().st_mtime
    if age < 20:
        time.sleep(20 - age)
    return False


@check("video-specs", level="full", exts=VIDEO_EXTS, paths=ALL_RENDERS, cache=True)
def video_specs(path: Path) -> list[str]:
    if being_written(path):
        return []  # checked again once the render finishes
    problems = []
    v = media.streams(path, "video")
    a = media.streams(path, "audio")
    if not v:
        return ["no video stream"]
    v = v[0]
    w, h = int(v.get("width", 0)), int(v.get("height", 0))
    is_short = any(Path(path.relative_to(ROOT).as_posix()).match(g) for g in SHORTS)
    if is_short and (w, h) != (1080, 1920):
        problems.append(f"short is {w}x{h}, must be 1080x1920 (9:16)")
    if not is_short and (abs(w / h - 16 / 9) > 0.01 or h < 1080):
        problems.append(f"long-form is {w}x{h}, must be 16:9 at 1080p or higher")
    if v.get("codec_name") not in ("h264", "hevc"):
        problems.append(f"video codec {v.get('codec_name')}, use h264 for platform compatibility")
    if v.get("pix_fmt") not in ("yuv420p", "yuvj420p"):
        problems.append(f"pixel format {v.get('pix_fmt')}, use yuv420p (others fail or look wrong on phones)")
    f = media.fps(v)
    if not 23.9 <= f <= 60.1:
        problems.append(f"frame rate {f:.2f}fps is outside 24-60")
    if not a:
        problems.append("no audio stream")
    else:
        a = a[0]
        if a.get("codec_name") != "aac":
            problems.append(f"audio codec {a.get('codec_name')}, use aac")
        vd, ad = float(v.get("duration", 0) or 0), float(a.get("duration", 0) or 0)
        if vd and ad and abs(vd - ad) > 0.3:
            problems.append(f"audio ({ad:.2f}s) and video ({vd:.2f}s) lengths differ by {abs(vd - ad):.2f}s, "
                            f"check for a silent or frozen tail / sync drift")
        # Declared durations can hide drift: concatenating AAC pieces keeps every piece's encoder
        # priming, so the real sample count grows past the video (monkey_longform_v1 was +4.3s,
        # audio seconds late by the end). Frames x 1024 is the true decoded length.
        nf, sr = int(a.get("nb_frames", 0) or 0), int(a.get("sample_rate", 0) or 0)
        if vd and nf and sr and a.get("codec_name") == "aac":
            real = nf * 1024 / sr
            if abs(real - vd) > 0.5:
                problems.append(f"audio holds {real:.2f}s of samples vs {vd:.2f}s of video ({real - vd:+.2f}s): "
                                f"A/V sync drift, likely AAC pieces concatenated with -c copy (use PCM pieces)")
    d = media.duration(path)
    if is_short and not 5 <= d <= 180:
        problems.append(f"short is {d:.1f}s, must be 5-180s")
    return problems


@check("video-content", level="full", exts=VIDEO_EXTS, paths=ALL_RENDERS, cache=True)
def video_content(path: Path) -> list[str]:
    """Black frames, frozen picture, dead air, and loudness, from one decode pass."""
    if being_written(path):
        return []  # checked again once the render finishes
    r = media.analyze(path)
    end = media.duration(path) - EDGE_GRACE
    problems = []
    for s, e in r["black"]:
        if s < end:
            problems.append(f"black screen {_fmt(s)}-{_fmt(e)} ({e - s:.1f}s)")
    for s, e in r["frozen"]:
        if s < end:
            problems.append(f"frozen picture {_fmt(s)}-{_fmt(e)} ({e - s:.1f}s), a stalled cut or a missing clip")
    for s, e in r["silent"]:
        if s < end:
            problems.append(f"dead air (below -50dB) {_fmt(max(s, 0))}-{_fmt(e)} ({e - max(s, 0):.1f}s)")
    if r["lufs"] is not None and not LUFS_RANGE[0] <= r["lufs"] <= LUFS_RANGE[1]:
        problems.append(f"integrated loudness {r['lufs']:.1f} LUFS, target about -14 "
                        f"(allowed {LUFS_RANGE[0]:.0f} to {LUFS_RANGE[1]:.0f}); add loudnorm=I=-14:TP=-1")
    # Sudden spikes read as "ear rape" even when the average is fine (user feedback on monkey_longform_v2:
    # SFX far louder than the voice). Flag momentary loudness well above the integrated level.
    if r["lufs"] is not None:
        hot = [t for t, m in r.get("momentary", []) if m > r["lufs"] + SPIKE_LU]
        spans, cur = [], None
        for t in hot:
            if cur and t - cur[1] <= 0.5:
                cur[1] = t
            else:
                cur = [t, t]
                spans.append(cur)
        for s, e in spans[:8]:
            problems.append(f"loudness spike {_fmt(max(s - 0.4, 0))}-{_fmt(e)}: momentary loudness over "
                            f"{SPIKE_LU:.0f} LU above the average, an SFX or music hit is too loud for the voice")
    if r["true_peak"] is not None and r["true_peak"] > MAX_TRUE_PEAK:
        problems.append(f"true peak {r['true_peak']:.1f} dBFS, will clip after platform re-encode; "
                        f"limit to -1 dBTP")
    return problems


MONKEY = ROOT / "long-form-to-shorts-video-editing" / "monkey-app-video-chat"


@check("short-face-on-screen", level="full", exts=VIDEO_EXTS,
       paths=["long-form-to-shorts-video-editing/monkey-app-video-chat/output/*.mp4"], cache=True)
def short_face_on_screen(path: Path) -> list[str]:
    """The recurring 'no subject in focus' bug: any stretch where the reframed crop shows no face."""
    if being_written(path):
        return []  # checked again once the render finishes
    if str(MONKEY) not in sys.path:
        sys.path.insert(0, str(MONKEY))
    from verify_face_presence import check_face_presence
    # 0.25s sampling is enough to catch the 0.5s+ spans we flag, at under half the cost of the default 0.15s
    spans = [s for s in check_face_presence(str(path), sample_interval=0.25) if s["duration"] >= 0.5]
    return [f"no face on screen {_fmt(s['start'])}-{_fmt(s['end'])} ({s['duration']:.1f}s), "
            f"the crop has lost the subject" for s in spans]
