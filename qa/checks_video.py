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
    # Shorts end on a silent endscreen card by design (render_short.ENDSCREEN_MAX_SECS, the YouTube one is 2.4s);
    # a silence that runs to the very end and fits that card isn't dead air. Mid-video silence still fails.
    endscreen_max = 0.0
    if "monkey-app-video-chat" in str(path).replace("\\", "/"):
        sys.path.insert(0, str(MONKEY)) if str(MONKEY) not in sys.path else None
        from render_short import ENDSCREEN_MAX_SECS
        endscreen_max = ENDSCREEN_MAX_SECS + 0.2
    total = media.duration(path)
    for s, e in r["silent"]:
        if total - e < 0.3 and e - s <= endscreen_max:
            continue
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
       paths=["long-form-to-shorts-video-editing/monkey-app-video-chat/output/*.mp4",
              "long-form-to-shorts-video-editing/infield/output/*.mp4"], cache=True)
def short_face_on_screen(path: Path) -> list[str]:
    """The recurring 'no subject in focus' bug: any stretch where the reframed crop shows no face."""
    if being_written(path):
        return []  # checked again once the render finishes
    if str(MONKEY) not in sys.path:
        sys.path.insert(0, str(MONKEY))
    from verify_face_presence import check_face_presence
    from render_short import ENDSCREEN_MAX_SECS
    # 0.25s sampling is enough to catch the 0.5s+ spans we flag, at under half the cost of the default 0.15s
    spans = [s for s in check_face_presence(str(path), sample_interval=0.25) if s["duration"] >= 0.5]
    # The branded endscreen (see render_short.append_endscreen) is a no-face card by design -- only
    # exempt a span that actually reaches the end of the video and fits that window, not a genuine
    # mid-video loss that happens to run long.
    total = media.duration(path)
    spans = [s for s in spans if not (total - s["end"] < 0.3 and s["duration"] <= ENDSCREEN_MAX_SECS + 1.0)]
    # A meme insert may have no human face at all (Tom and Jerry, short_3_v4). Only memes, never the hook
    # seam: that one is real call footage and must keep a face. Older sidecars have no "memes" key.
    import json
    side = path.with_suffix(".render.json")
    memes = json.loads(side.read_text(encoding="utf-8")).get("memes", []) if side.exists() else []
    spans = [s for s in spans if not any(lo - 0.1 <= s["start"] and s["end"] <= hi + 0.1 for lo, hi in memes)]
    return [f"no face on screen {_fmt(s['start'])}-{_fmt(s['end'])} ({s['duration']:.1f}s), "
            f"the crop has lost the subject" for s in spans]


@check("short-jumpy-cuts", level="full", exts=VIDEO_EXTS,
       paths=["long-form-to-shorts-video-editing/monkey-app-video-chat/output/*.mp4",
              "long-form-to-shorts-video-editing/infield/output/*.mp4"], cache=True)
def short_jumpy_cuts(path: Path) -> list[str]:
    """Editing that reads as jumpy: a shot that flashes by (under 0.5s) or a burst of hard cuts in a couple
    of seconds. Unnecessary re-centring cuts inside one person's shot were the cause (fixed by panning)."""
    if being_written(path):
        return []
    if str(MONKEY) not in sys.path:
        sys.path.insert(0, str(MONKEY))
    import json
    from verify_cuts import check_cut_rhythm
    side = path.with_suffix(".render.json")
    spans = json.loads(side.read_text(encoding="utf-8")).get("cutaways", []) if side.exists() else []
    r = check_cut_rhythm(str(path), ignore_spans=spans)
    problems = [f"flash shot {_fmt(a)}-{_fmt(b)} ({b - a:.2f}s), a cut nobody can read as an edit"
                for a, b in r["short_shots"]]
    problems += [f"{n} hard cuts within 2s at {_fmt(a)}, reads as jumpy" for a, _, n in r["bursts"]]
    return problems


@check("endscreen-card-blocky", level="fast", exts={".png"},
       paths=["long-form-to-shorts-video-editing/monkey-app-video-chat/assets/endscreen_card.png"])
def endscreen_card_blocky(path: Path) -> list[str]:
    """The user could "literally see the pixels" in the shorts endscreen: the card was a frame lifted from a
    compressed screen recording, so its 8x8 codec blocks were baked in. Blocky images have noticeably
    stronger gradients on the 8px grid than between it (that frame: 1.17x; the rebuilt card: 0.98x)."""
    import cv2
    import numpy as np
    g = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    if g is None:
        return []
    g = g.astype(np.float32)
    worst = 0.0
    for d in (np.abs(np.diff(g, axis=1)).mean(axis=0), np.abs(np.diff(g, axis=0)).mean(axis=1)):
        on_grid = (np.arange(len(d)) % 8) == 7
        worst = max(worst, float(d[on_grid].mean() / max(d[~on_grid].mean(), 1e-6)))
    return [] if worst < 1.06 else [f"8x8 compression blocks visible ({worst:.2f}x edge energy on the block grid); "
                                    f"rebuild it with make_endscreen_card.py from clean sources"]


@check("short-bitrate", level="full", exts=VIDEO_EXTS,
       paths=["long-form-to-shorts-video-editing/monkey-app-video-chat/output/*.mp4",
              "long-form-to-shorts-video-editing/infield/output/*.mp4"])
def short_bitrate(path: Path) -> list[str]:
    """The user saw v69 as pixelated: two stacked veryfast/crf20 encodes left a 1080x1920 short at ~3.7 Mbps.
    One crf17/slow encode lands ~6 Mbps on the same footage, so anything under 5 Mbps means the encode
    settings regressed (or a second re-encode crept back in)."""
    if being_written(path):
        return []
    import subprocess
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "format=bit_rate",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout.strip()
    try:
        mbps = int(out) / 1e6
    except ValueError:
        return []
    return [] if mbps >= 5.0 else [f"bitrate {mbps:.1f} Mbps is under 5 Mbps, the short will look pixelated "
                                   f"(check VIDEO_ENC in render_short.py and that nothing re-encodes after it)"]


@check("short-lone-frame", level="full", exts=VIDEO_EXTS,
       paths=["long-form-to-shorts-video-editing/monkey-app-video-chat/output/*.mp4",
              "long-form-to-shorts-video-editing/infield/output/*.mp4"], cache=True)
def short_lone_frame(path: Path) -> list[str]:
    """"One frame where the cut wasn't adjusted yet" (the user's own words, three confirmed instances in
    one session: a stale crop over already-changed content, a blank frame, a sliver of source UI chrome).
    All three shared one shape in the rendered output: two large frame-to-frame jumps back to back, where
    a real cut only ever makes one. Skips anything inside a known cutaway/meme span, where a clip's own
    fast motion (someone clapping) produces the same two-large-jumps shape without being this bug."""
    if being_written(path):
        return []
    if str(MONKEY) not in sys.path:
        sys.path.insert(0, str(MONKEY))
    import json
    from verify_lone_frames import find_lone_frames
    side = path.with_suffix(".render.json")
    ignore = json.loads(side.read_text(encoding="utf-8")).get("cutaways", []) if side.exists() else []
    found = [
        (t, a, b) for t, a, b in find_lone_frames(str(path), handheld="/infield/" in path.as_posix())
        # interior only: a correctly placed span edge makes ONE jump, so a lone frame at the edge itself is
        # a boundary landed a frame off (v67 0:08: one zoomed meme frame after the letterboxed meme ended).
        # The old +-0.2s pad exempted exactly those.
        if not any(lo + 0.05 <= t <= hi - 0.05 for lo, hi in ignore)
    ]
    return [f"lone off frame at {_fmt(t)} (jump in {a}, out {b}), likely one frame of mismatched content "
            f"at a cut" for t, a, b in found]


@check("short-opens-on-her", level="full", exts=VIDEO_EXTS,
       paths=["long-form-to-shorts-video-editing/monkey-app-video-chat/output/*.mp4",
              "long-form-to-shorts-video-editing/infield/output/*.mp4"], cache=True)
def short_opens_on_her(path: Path) -> list[str]:
    """User, 2026-10-06: the first 2 seconds decide the swipe, so the woman must be on screen first (not
    him, not a meme, not her empty wall). See verify_opening.py for the identity calibration."""
    if being_written(path):
        return []
    import json
    if str(MONKEY) not in sys.path:
        sys.path.insert(0, str(MONKEY))
    from verify_opening import INFIELD_MIN_FACE, opening_problems
    side = path.with_suffix(".render.json")
    memes = json.loads(side.read_text(encoding="utf-8")).get("memes", []) if side.exists() else []
    found = opening_problems(str(path), memes,
                              min_face=INFIELD_MIN_FACE if "/infield/" in path.as_posix() else None)
    return found[:3] + ([f"...and {len(found) - 3} more opening samples"] if len(found) > 3 else [])


@check("short-split-both-faces", level="full", exts=VIDEO_EXTS,
       paths=["long-form-to-shorts-video-editing/monkey-app-video-chat/output/*.mp4"], cache=True)
def short_split_both_faces(path: Path) -> list[str]:
    """Each half of a stacked two-person shot must show a face. short_5_v2 0:07 (user screenshot,
    2026-10-06): the top half pointed at an empty pane sliver while her eye filled the bottom half, and
    short-face-on-screen passed because it only asks for a face anywhere in the frame."""
    if being_written(path):
        return []
    import json
    import cv2
    side = path.with_suffix(".render.json")
    if not side.exists():
        return []
    splits = json.loads(side.read_text(encoding="utf-8")).get("splits", [])
    if not splits:
        return []
    if str(MONKEY) not in sys.path:
        sys.path.insert(0, str(MONKEY))
    from reframe import _best_face, _get_detector
    det = _get_detector()
    cap = cv2.VideoCapture(str(path))
    problems = []
    for lo, hi in splits:
        miss = {"top": [], "bottom": []}
        t = lo + 0.15
        while t < hi - 0.15:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = cap.read()
            if ok:
                h = frame.shape[0] // 2
                for name, half in (("top", frame[:h]), ("bottom", frame[h:])):
                    det.setScoreThreshold(0.4)
                    found = _best_face(det, half) is not None
                    det.setScoreThreshold(0.6)
                    miss[name].append(t if not found else None)
            t += 0.25
        for name, seq in miss.items():
            run = []
            for v in seq + [None]:
                if v is not None:
                    run.append(v)
                    continue
                if len(run) >= 2:  # 2 samples at 0.25s = a 0.5s+ hole
                    problems.append(f"stacked shot {_fmt(lo)}-{_fmt(hi)}: {name} half has no face "
                                    f"{_fmt(run[0])}-{_fmt(run[-1] + 0.25)}; that person is out of their pane, "
                                    f"render it solo (render_short._demote_hollow_splits)")
                run = []
    return problems


@check("short-duration-matches-plan", level="full", exts=VIDEO_EXTS,
       paths=["long-form-to-shorts-video-editing/monkey-app-video-chat/output/*.mp4",
              "long-form-to-shorts-video-editing/infield/output/*.mp4"])
def short_duration_matches_plan(path: Path) -> list[str]:
    """short_5_v1 (2026-10-04) rendered 88s from a 59.9s clip: overlapping plan chunks replayed ~27s of
    footage and every other gate passed. Rendered length must be the sidecar's clip length plus the
    endscreen (1.25s brand card, 2.4s YouTube card), nothing more."""
    if being_written(path):
        return []
    import json
    side = path.with_suffix(".render.json")
    if not side.exists():
        return []
    want = json.loads(side.read_text(encoding="utf-8"))["duration"]
    got = media.duration(path)
    extra = got - want
    if not -0.3 <= extra <= 3.0:
        return [f"rendered {got:.1f}s from a {want:.1f}s clip ({extra:+.1f}s); the crop plan likely repeats or drops "
                f"footage (overlapping chunks in the 'Reframe plan' log line)"]
    return []


@check("short-call-as-cutaway", level="full", exts=VIDEO_EXTS,
       paths=["long-form-to-shorts-video-editing/monkey-app-video-chat/output/*.mp4"], cache=True)
def short_call_as_cutaway(path: Path) -> list[str]:
    """Real call footage misread as a meme insert renders as the whole landscape call letterboxed (both
    panes side by side) instead of the stacked/solo crop. Seen 2026-10-02 (short_3_v3): her warm-lit room
    tripped the old saturation test. Independent of reframe.py's own detector: the Monkey App's yellow
    "Friend" pill only ever appears on call frames, so finding it in the source inside a cutaway span means
    the span is wrong. The pill isn't on screen in every layout, so this catches most misreads, not all."""
    if being_written(path):
        return []
    import json
    import cv2
    side = path.with_suffix(".render.json")
    if not side.exists():
        return []
    meta = json.loads(side.read_text(encoding="utf-8"))
    src = MONKEY / meta["video"]
    if not src.exists():
        return []
    cap = cv2.VideoCapture(str(src))
    bad = []
    for lo, hi in meta.get("memes", meta.get("cutaways", [])):
        t = lo
        while t < hi:
            cap.set(cv2.CAP_PROP_POS_MSEC, (meta["start"] + t) * 1000)
            ok, frame = cap.read()
            if ok:
                mask = cv2.inRange(cv2.cvtColor(frame, cv2.COLOR_BGR2HSV), (22, 150, 180), (34, 255, 255))
                _, _, stats, _ = cv2.connectedComponentsWithStats(mask)
                # the pill sits on the bottom edge of a pane (y ~1014 of 1080); a meme's yellow prop elsewhere
                # (short_5: a chair behind someone's head) is not it
                fh = frame.shape[0]
                if any(120 < w < 600 and 20 < h < 90 and w > 3 * h and y > 0.85 * fh for _, y, w, h, _ in stats[1:]):
                    bad.append((lo, hi))
                    break
            t += 0.25
    return [f"cutaway {_fmt(lo)}-{_fmt(hi)} is real call footage (Monkey 'Friend' button visible), rendered "
            f"letterboxed side by side instead of cropped; check reframe._looks_like_cutaway" for lo, hi in bad]


@check("short-frozen-half", level="full", exts=VIDEO_EXTS,
       paths=["long-form-to-shorts-video-editing/monkey-app-video-chat/output/*.mp4"], cache=True)
def short_frozen_half(path: Path) -> list[str]:
    """A stacked (split) half that barely moves for a while reads as a stuck frame, not a held shot. Only
    flags an ASYMMETRIC freeze (one half static while the other keeps moving) -- both halves pausing
    together is just a calm moment in a solo shot, not this bug."""
    if being_written(path):
        return []
    if str(MONKEY) not in sys.path:
        sys.path.insert(0, str(MONKEY))
    from verify_freeze import check_freeze_spans
    spans = check_freeze_spans(str(path))

    def not_covered_by(span, other_spans):
        a, b = span
        return not any(oa <= a and b <= ob for oa, ob in other_spans)

    problems = [f"top half frozen {_fmt(a)}-{_fmt(b)} ({b - a:.1f}s) while the bottom kept moving"
                for a, b in spans["top"] if not_covered_by((a, b), spans["bottom"])]
    problems += [f"bottom half frozen {_fmt(a)}-{_fmt(b)} ({b - a:.1f}s) while the top kept moving"
                 for a, b in spans["bottom"] if not_covered_by((a, b), spans["top"])]
    return problems


@check("longform-endscreen-shake", level="full", exts=VIDEO_EXTS, paths=["long-form-video-editing/*/output/*.mp4"], cache=True)
def longform_endscreen_shake(path: Path) -> list[str]:
    """The endscreen's slow push-in must glide, not jitter. ffmpeg zoompan snaps its crop to whole pixels
    each frame, which the user saw as the endscreen "shaking like an earthquake" (2026-10-01).
    Measured on the last 6s: frame-to-frame motion of the top-left quadrant (phase correlation); a smooth
    zoom drifts steadily (jerk ~0.004 px), zoompan jittered at ~0.14 px with ~100 direction flips."""
    if being_written(path):
        return []
    import subprocess

    import cv2
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-sseof", "-6", "-i", str(path), "-vf", "scale=960:540,format=gray",
                          "-f", "rawvideo", "-"], capture_output=True).stdout
    fr = np.frombuffer(raw, np.uint8)
    if fr.size < 960 * 540 * 30:
        return []
    fr = fr[:fr.size // (960 * 540) * 960 * 540].reshape(-1, 540, 960).astype(np.float32)
    q = [f[20:250, 20:450] for f in fr]
    d = np.array([cv2.phaseCorrelate(a, b)[0] for a, b in zip(q, q[1:])])
    jerk = float(np.abs(np.diff(d, axis=0)).mean())
    if jerk > 0.05:
        return [f"endscreen push-in jitters (jerk {jerk:.3f} px/frame, smooth is < 0.05): draw the zoom with "
                f"sub-pixel crops (render.py render_endscreen uses PIL resize with a float box), not ffmpeg zoompan"]
    return []


@check("infield-caption-speaker", level="full", exts=VIDEO_EXTS,
       paths=["long-form-to-shorts-video-editing/infield/output/*.mp4"])
def infield_caption_speaker(path: Path) -> list[str]:
    """Her lines must be in her caption style and his in his (critic, amanda_v4: her "REALLY?" rendered in his
    white/gold because a patched word's end ran to its span end and its mid-point missed her range).
    Compares every caption event's style with the sidecar's her_out spans (output seconds)."""
    import json
    import re
    side = path.with_suffix(".render.json")
    if not side.exists():
        return []
    meta = json.loads(side.read_text(encoding="utf-8"))
    ass = ROOT / meta.get("captions", "")
    if "her_out" not in meta or not ass.is_file():
        return []
    her = meta["her_out"]
    problems = []
    for m in re.finditer(r"^Dialogue: \d+,(\d+):(\d+):([\d.]+),[^,]*,(Cap|CapHer),.*?\}([^{]*)\{", ass.read_text(encoding="utf-8"), re.M):
        t = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
        is_her = any(a <= t + 0.03 < b for a, b in her)   # same onset rule as the renderer
        if is_her != (m[4] == "CapHer"):
            problems.append(f"caption at {_fmt(t)} is styled {m[4]} but the spec says "
                            f"{'she' if is_her else 'he'} is speaking")
    return problems[:5]


@check("infield-her-visible-when-speaking", level="full", exts=VIDEO_EXTS,
       paths=["long-form-to-shorts-video-editing/infield/output/*.mp4"], cache=True)
def infield_her_visible_when_speaking(path: Path) -> list[str]:
    """User rule (2026-10-07): only use footage where you can truly see the woman. Critic, sammy_v3 23.7s: his hand
    blurred across the lens during her "Oh, thank you" while short-face-on-screen passed on the half second either
    side. While she is speaking (sidecar her_out), a readable face must be on screen; a gap over 0.3s fails
    (fix it with a `hold` in the spec)."""
    if being_written(path):
        return []
    import json
    import cv2
    side = path.with_suffix(".render.json")
    if not side.exists():
        return []
    her = json.loads(side.read_text(encoding="utf-8")).get("her_out", [])
    if not her:
        return []
    if str(MONKEY) not in sys.path:
        sys.path.insert(0, str(MONKEY))
    from verify_opening import INFIELD_MIN_FACE
    det = cv2.FaceDetectorYN_create(str(MONKEY / "models" / "face_detection_yunet.onnx"), "", (540, 960), 0.6)
    cap = cv2.VideoCapture(str(path))
    problems = []
    for a, b in her:
        t, gap_start = a, None
        while t <= b:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = cap.read()
            if not ok:
                break
            _, faces = det.detect(cv2.resize(frame, (540, 960)))
            seen = faces is not None and max(f[2] for f in faces) * 2 >= INFIELD_MIN_FACE
            if not seen and gap_start is None:
                gap_start = t
            if (seen or t + 0.1 > b) and gap_start is not None:
                if t - gap_start > 0.3:
                    problems.append(f"her face not visible {_fmt(gap_start)}-{_fmt(t)} while she speaks; "
                                    f"add a hold of a clean frame or cut the line")
                gap_start = None
            t += 0.1
    cap.release()
    return problems[:5]


@check("infield-no-extra-voices", level="full", exts=VIDEO_EXTS,
       paths=["long-form-to-shorts-video-editing/infield/output/*.mp4"], cache=True)
def infield_no_extra_voices(path: Path) -> list[str]:
    """User, sammy_v14: "a distracting voice being played at 0:20... I shouldn't have to point these things out"
    (a sound effect with sung lyrics over the dialogue). Transcribe the finished mix and flag 3+ heard words in a
    row that the captions don't account for (a vocal SFX, song lyrics, a loud bystander). Slow-mo song moments
    are exempt (sidecar "slowmo_out")."""
    if being_written(path):
        return []
    import json
    import re
    side = path.with_suffix(".render.json")
    if not side.exists():
        return []
    meta = json.loads(side.read_text(encoding="utf-8"))
    ass = ROOT / meta.get("captions", "")
    if not ass.is_file():
        return []
    cap = []
    for m in re.finditer(r"^Dialogue: \d+,(\d+):(\d+):([\d.]+),(\d+):(\d+):([\d.]+),(Cap|CapHer),[^\n]*?,,(.*)$",
                         ass.read_text(encoding="utf-8"), re.M):
        t0 = int(m[1]) * 3600 + int(m[2]) * 60 + float(m[3])
        t1 = int(m[4]) * 3600 + int(m[5]) * 60 + float(m[6])
        for w in re.sub(r"\{[^}]*\}", "", m[8]).split():
            cap.append((t0, t1, re.sub(r"[^a-z0-9']", "", w.lower())))
    slow = meta.get("slowmo_out", [])
    from faster_whisper import WhisperModel
    asr = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _ = asr.transcribe(str(path), language="en", word_timestamps=True, vad_filter=True)
    heard = [(w.start, re.sub(r"[^a-z0-9']", "", w.word.lower())) for g in segs for w in (g.words or [])]
    run, problems = [], []
    for t, w in heard + [(1e9, "")]:
        ok = (not w or any(a <= t < b for a, b in slow)
              or any(t0 - 1.0 <= t <= t1 + 1.0 and (w == cw or w[:4] == cw[:4]) for t0, t1, cw in cap))
        if not ok:
            run.append((t, w))
            continue
        if len(run) >= 3:
            # the transcriber re-splits words it mishears ("everybody" -> "be here buddy", sammy_v18): accept the
            # run when its letters largely appear in the captions shown around it
            import difflib
            heard_s = "".join(x for _, x in run)
            shown = "".join(cw for t0, t1, cw in cap if t0 - 1.5 <= run[-1][0] and t1 + 1.5 >= run[0][0])
            sm = difflib.SequenceMatcher(None, heard_s, shown)
            if sum(b.size for b in sm.get_matching_blocks()) >= 0.7 * len(heard_s):
                run = []
                continue
            problems.append(f"voice not in the captions {_fmt(run[0][0])}-{_fmt(run[-1][0])}: "
                            f"\"{' '.join(x for _, x in run)}\" (vocal SFX / song lyrics / bystander over the dialogue?)")
        run = []
    return problems[:5]


@check("infield-audio-dropouts", level="full", exts=VIDEO_EXTS,
       paths=["long-form-to-shorts-video-editing/infield/output/*.mp4"], cache=True)
def infield_audio_dropouts(path: Path) -> list[str]:
    """User, sammy_v19: "a weird sound after did I catch your name". RNNoise restarted at every cut and gated the
    room tone to dead silence for 50-90 ms (11 dropouts in one short), which reads as the sound chopping in and out.
    Flag any stretch of 30 ms+ below -70 dBFS before the endscreen (a real phone recording never goes that quiet)."""
    if being_written(path):
        return []
    import json
    import subprocess
    import numpy as np
    side = path.with_suffix(".render.json")
    end = json.loads(side.read_text(encoding="utf-8")).get("duration") if side.exists() else None
    x = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "48000", "-f",
                                      "f32le", "-"], capture_output=True).stdout, np.float32)
    hop = 480
    r = 20 * np.log10(np.array([np.sqrt(np.mean(x[i:i + hop] ** 2)) for i in range(0, len(x) - hop, hop)]) + 1e-9)
    stop = int((end - 0.1) * 100) if end else len(r)
    bad, i = [], 0
    while i < stop:
        if r[i] < -70:
            j = i
            while j < stop and r[j] < -70:
                j += 1
            if j - i >= 3 and i > 3:
                bad.append(f"audio drops to dead silence at {_fmt(i / 100)} for {(j - i) * 10} ms "
                           f"(denoise gating / cut fade), it sounds like a glitch")
            i = j
        i += 1
    return bad[:5]


@check("infield-hiss", level="full", exts=VIDEO_EXTS,
       paths=["long-form-to-shorts-video-editing/infield/output/*.mp4"], cache=True)
def infield_hiss(path: Path) -> list[str]:
    """User, twice ("hiss in the audio, static noise", then "the static noise is back" on sammy_v21): the phone-mic
    hiss must stay cleaned. Calibrated on sammy: clean v15/v18 = floor -37/-36 dB, quiet-frame >4 kHz -24.4/-23.9;
    hissy v14/v21 = -26.8/-34.4, -19.6/-22.2."""
    if being_written(path):
        return []
    import json
    import subprocess
    import numpy as np
    side = path.with_suffix(".render.json")
    dur = json.loads(side.read_text(encoding="utf-8")).get("duration") if side.exists() else None
    x = np.frombuffer(subprocess.run(["ffmpeg", "-v", "error", *(["-t", str(dur)] if dur else []), "-i", str(path),
                                      "-ac", "1", "-ar", "48000", "-f", "f32le", "-"], capture_output=True).stdout,
                      np.float32)
    r = 20 * np.log10(np.array([np.sqrt(np.mean(x[i:i + 960] ** 2)) for i in range(0, len(x) - 960, 960)]) + 1e-9)
    r = r[r > -90]
    if not len(r):
        return []
    q = np.percentile(r, 25)
    fr = np.fft.rfftfreq(2048, 1 / 48000)
    hb = []
    for i in range(0, len(x) - 2048, 2048):
        s = x[i:i + 2048]
        if 20 * np.log10(np.sqrt(np.mean(s ** 2)) + 1e-9) < q:
            sp = np.abs(np.fft.rfft(s))
            hb.append(20 * np.log10(np.sqrt(np.mean(sp[fr > 4000] ** 2)) + 1e-9))
    floor, hiss = float(np.percentile(r, 15)), float(np.median(hb)) if hb else -99.0
    if floor > -35.5 or hiss > -23.0:
        return [f"background hiss is back: noise floor {floor:.1f} dB (max -35.5), quiet-frame hiss {hiss:.1f} dB "
                f"(max -23.0); keep RNNoise at full strength on the continuous clean track"]
    return []
