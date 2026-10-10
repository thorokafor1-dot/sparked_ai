"""Cut the talking head, splice infield clips between lines, render the long-form video.

Usage:
    python render.py --out output/ten_openers_v1.mp4
    python render.py --edl edl_take2 --out output/ten_openers_take2_v1.mp4

The edit lives in an EDL module (edl.py for take 1, edl_take2.py etc.), which also names its take's
camera, mic, sync file and optional second angle, so a new take is a new EDL module, not a code change. Talking-head ranges get their internal
pauses (>= MIN_GAP) jump-cut out automatically; infield clips play as-is with
their real audio. Every segment is normalized to 1080p30 / 48k stereo so the
final concat is a straight stream copy, then the whole thing gets one loudnorm pass.
"""

import argparse
import importlib
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

import sync_mic

from brand_graphics import SUB_BELL_AT, SUB_CLICK_AT, SUB_SECS
from edl import CLIPS_DIR, EDL, MIC, SUBSCRIBE_AT, TALKING_HEAD  # defaults; --edl swaps them via load_take()

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "tools"))
from denoise import denoised_wav  # noqa: E402  DeepFilterNet street-noise removal for the infield clips

HERE = Path(__file__).parent
WORK = HERE / "work"
SEG_DIR = WORK / "segments"
TXT_DIR = WORK / "txt"
CLEAN_AUDIO: dict[Path, Path] = {}  # infield clip -> its denoised wav (filled in main unless --no-denoise)
BRAND = WORK / "brand"  # Sparked graphics from brand_graphics.py
CAPTION_FONT = "work/fonts/grotesk_600.ttf"  # Space Grotesk, the landing page body font

SHADOW = "shadowcolor=black@0.65:shadowx=0:shadowy=4"
CARD_FADE = 0.3
AUDIO_DIR = HERE / "input" / "audio"  # from the channel's licensed library (monkey-app-longform-01, mixkit)
MUSIC = AUDIO_DIR / "rnb.mp3"  # R&B dating-feel bed for the outro
WHOOSH = AUDIO_DIR / "whoosh_1491.mp3"  # "cinematic whoosh fast transition"
DING = AUDIO_DIR / "ding_217.mp3"  # "attention bell ding"
MUSIC_BED, MUSIC_SWELL = 0.14, 0.55  # under the spoken close / on the endscreen
BODY_TRACKS = [AUDIO_DIR / "babe.mp3", AUDIO_DIR / "sensual.mp3"]  # smooth R&B beds for the two halves of the body (user: "background music to add to the vibe")
BODY_BED, BODY_DUCK = 0.10, 0.025  # under his voice / under infield clips, whose own audio must stay clean
WHOOSH_VOL = 0.35
ENDSCREEN_SECS = 7.0  # YouTube end-screen elements need >= 5s; longer just bleeds retention
GRADE = "eq=contrast=1.06:saturation=1.1:gamma=0.98"
PUSH_BASE = (1.0, 1.12)  # consecutive main-camera pieces ALWAYS alternate wide/tight, so a cut reads as a camera change
PUSH_AMOUNT = 0.018  # ...with a gentle ease-in; bigger pushes read as 'pans then resets' at the next cut (user, #6/#3)
VOICE_CHAIN = "highpass=f=80,acompressor=threshold=-20dB:ratio=3:attack=5:release=100:makeup=2"
PEAK_TAMER = "acompressor=threshold=-12dB:ratio=4:attack=3:release=150"  # post-gain, shouts only

MIN_GAP = 0.55  # pauses at least this long inside a talking-head range get cut
EDGE_GAP = 0.12  # shortest breath between phrases that a range edge may snap to
PAD = 0.12  # breathing room kept after speech stops at a jump cut
PRE_ROLL = 0.18  # kept before speech starts, so the first consonant never gets clipped
SNAP = 0.45  # how far a range start may move back to reach the pause before the speech
END_REACH = 1.2  # how far a range end may move forward to reach the pause after the sentence
VOICE_DB = -44.0  # anything this loud is voice, whatever its texture (inhales peak around -48)
QUIET_VOICE_DB = -58.0  # quieter than this is never counted as voice
VOICED_ZCR = 0.12  # tonal voice sits under this zero-crossing rate; breath hiss sits around 0.2+
ATTACK = 0.06  # kept before the voice onset so consonants keep their attack
REUSE = False  # --reuse-segments: keep already-rendered pieces (iterate on the final mix without re-encoding)
CUT_WARNINGS: list[str] = []  # edges that couldn't land in a pause; printed after the render
CARD_PUSH = 0.05  # cards slowly push in 5% over their hold, so they never read as a frozen frame
CARD_SECS = 3.0  # still card held 3.0s (2.7s fully up): readable, and under the 3s frozen-picture gate
TARGET_LUFS = -16.0  # per-source static gain target before the final loudnorm

# take config, overridden by load_take() from the chosen EDL module
SYNC = WORK / "mic_sync.json"  # main camera <-> mic
ANGLE2, ANGLE2_SYNC = None, None  # optional second camera (and its own camera <-> mic sync)
TAKE_PREFIX = ""  # keeps each take's silence caches apart
SILENCE_DB = -60  # take 1's mic app noise-gates to digital silence; an ungated mic needs this above its noise floor
# iPhone 3/4 angle: crop in on him (1.33x keeps a 1080p source sharp), then match the Lumix per colour channel.
# The gain/offset is mean+contrast matching measured on 7 synced moments; the earlier hand grade (warm tint,
# gamma down) left it brighter and flatter than the main angle, which read as a flashback (user, 2026-10-01).
SIDE_VF = ["crop=1440:810:430:110", "scale=1920:1080", "format=rgb24",
           "lutrgb=r='clip(1.232*val-63.5,0,255)':g='clip(1.144*val-57.3,0,255)':b='clip(1.124*val-59.7,0,255)'",
           "unsharp=5:5:0.6"]
SIDE_SHARE = 0.33  # target share of talking-head time on the side angle (explanations only; "every 4th piece" gave 14%)
CLOSE_BASE = 1.3  # "close-up" angle: a tighter framing of the main camera, every 3rd main explanation piece
SIDE_MIN_SECS = 1.5  # shorter pieces stay on the main angle; a flash of a second camera reads as a glitch

VIDEO_ARGS = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", "30"]
AUDIO_ARGS = ["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
SEG_AUDIO_ARGS = ["-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2"]  # intermediates: AAC only once, at the end


def run(cmd: list[str]) -> str:
    result = subprocess.run(cmd, cwd=HERE, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"ffmpeg failed:\n{' '.join(cmd)}\n{result.stderr[-2000:]}")
    return result.stderr


def source_gain(path: Path, cache: dict) -> float:
    key = str(path)
    if key not in cache:
        err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vn", "-af", "loudnorm=print_format=json", "-f", "null", "-"])
        measured = json.loads(err[err.rindex("{"):err.rindex("}") + 1])
        cache[key] = round(TARGET_LUFS - float(measured["input_i"]), 2)
    return cache[key]


def talking_head_silences(min_gap: float = None) -> list[tuple[float, float]]:
    """Pauses in the talking head, in camera time.

    Detected on the external mic, not the camera: the mic app noise-gates to true
    digital silence between words, so -60dB finds real pauses without mistaking a
    soft first syllable for silence (the camera track at -35dB clipped sentence starts).
    min_gap=MIN_GAP gives the pauses worth jump-cutting; EDGE_GAP gives every breath
    between phrases, which is what range edges snap to.
    """
    min_gap = MIN_GAP if min_gap is None else min_gap
    cache = WORK / f"{TAKE_PREFIX}th_silences_mic_{min_gap:.2f}.json"
    if cache.exists():
        return [tuple(x) for x in json.loads(cache.read_text())]
    err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(MIC), "-vn",
               "-af", f"silencedetect=noise={SILENCE_DB}dB:d={min_gap}", "-f", "null", "-"])
    starts = [mic_to_cam(float(x)) for x in re.findall(r"silence_start: ([\d.]+)", err)]
    ends = [mic_to_cam(float(x)) for x in re.findall(r"silence_end: ([\d.]+)", err)]
    silences = list(zip(starts, ends))
    cache.write_text(json.dumps(silences))
    return silences


def snap_to_speech(start: float, end: float, silences, exact_start=False, exact_end=False) -> tuple[float, float]:
    """Every cut must land in a real pause, never mid-word.

    Whisper word times run a few hundred ms off (e.g. "Number eight." ended early and the cut
    chopped the word), so range edges move to the pause the speech actually starts after / stops at.
    Edges that can't reach a pause are reported, not silently cut.
    """
    # exact edges were hand-picked at a word boundary where the speaker runs on without a pause
    containing = [e for s, e in silences if s <= start < e]
    before = [] if exact_start else [e for s, e in silences if e <= start + 0.1]
    if exact_start:
        pass
    elif containing:  # start sits inside a pause: go forward to where that pause ends, never back
        start = containing[0] - PRE_ROLL
    elif before and start - before[-1] <= SNAP:
        start = before[-1] - PRE_ROLL
    elif not any(s <= start <= e for s, e in silences):
        CUT_WARNINGS.append(f"start {start:.2f}s is mid-speech (no pause within {SNAP}s before it)")
    if exact_end:
        return start, end
    inside = [s for s, e in silences if s <= end <= e]
    after = [s for s, e in silences if s >= end - 0.1]
    if inside:
        end = inside[0] + PAD
    elif after and after[0] - end <= END_REACH:
        end = after[0] + PAD
    else:
        CUT_WARNINGS.append(f"end {end:.2f}s is mid-speech (no pause within {END_REACH}s after it)")
    return start, end


_MIC = None  # (20ms RMS dB, 20ms zero-crossing rate) of the whole mic track, loaded once


def mic_levels() -> tuple[np.ndarray, np.ndarray]:
    global _MIC
    if _MIC is None:
        raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(MIC), "-ac", "1", "-ar", "16000", "-f", "f32le", "-"],
                             capture_output=True, check=True).stdout
        x = np.frombuffer(raw, np.float32)
        x = x[:len(x) // 320 * 320].reshape(-1, 320)
        db = 20 * np.log10(np.sqrt((x ** 2).mean(1)) + 1e-9)
        zcr = (np.abs(np.diff(np.sign(x), axis=1)) > 0).mean(1)
        _MIC = (db, zcr)
    return _MIC


def voice_onset(i0: int, i1: int) -> int | None:
    """First 20ms frame of actual voice: loud, or quieter but tonal (low zero-crossing rate).

    Inhales on this mic sit around -75..-48dB but are hissy (ZCR ~0.2+), voice is tonal (ZCR < 0.12),
    so texture, not loudness, is what separates a breath from a soft first syllable.
    """
    db, zcr = mic_levels()
    for i in range(i0, min(i1, len(db) - 1)):
        voiced = db[i] > VOICE_DB or (db[i] > QUIET_VOICE_DB and zcr[i] < VOICED_ZCR)
        if voiced and (db[i + 1] > QUIET_VOICE_DB):  # sustained, not a lone click
            return i
    return None


def skip_inhale(start: float, end: float) -> float:
    """Move a piece start past the audible inhale before the first word (the mic gate opens on the breath)."""
    i0 = int(cam_to_mic(start) / 0.02)
    i = voice_onset(i0, int(cam_to_mic(min(end, start + 1.5)) / 0.02))
    if i is None or i == i0:
        return start
    return max(start, mic_to_cam(i * 0.02) - ATTACK)


def split_on_pauses(start: float, end: float, silences, exact_start=False, exact_end=False) -> list[tuple[float, float]]:
    start, end = snap_to_speech(start, end, talking_head_silences(EDGE_GAP), exact_start, exact_end)
    pieces, cursor = [], start
    for s, e in silences:
        if s + PAD > cursor + 0.2 and e - PRE_ROLL < end - 0.2 and s > cursor:
            pieces.append((cursor, s + PAD))
            cursor = e - PRE_ROLL
    pieces.append((cursor, end))
    pieces = [(skip_inhale(s, e), e) for s, e in pieces]
    # a sliver with no voice in it is just breath or a tail from the take before; drop it
    return [(s, e) for s, e in pieces if voice_onset(int(cam_to_mic(s) / 0.02), int(cam_to_mic(e) / 0.02)) is not None]


_SYNC_CACHE: dict = {}


def _sync(sync_file: Path = None) -> dict:
    f = sync_file or SYNC
    if f not in _SYNC_CACHE:
        _SYNC_CACHE[f] = json.loads(f.read_text())
    return _SYNC_CACHE[f]


def cam_to_mic(t: float, sync_file: Path = None) -> float:
    # sync_mic.py's measured map (dense points when present, else offset + drift line)
    return sync_mic.cam_to_mic(t, _sync(sync_file))


def mic_to_cam(t: float, sync_file: Path = None) -> float:
    return sync_mic.mic_to_cam(t, _sync(sync_file))


def main_to_side(t: float) -> float:
    """Main-camera time -> the same moment on the second angle, via the mic clock both are synced to."""
    return mic_to_cam(cam_to_mic(t), ANGLE2_SYNC)


def ensure_wav(path: Path) -> Path:
    """Lossless WAV copy of a compressed mic recording, made once.

    Seeking (-ss) into Windows Sound Recorder .m4a files lands 0.26-0.8s early (bad seek index), which
    put every talking-head piece out of lip sync on take 2. Seeking in PCM WAV is sample-exact, and the
    sync offsets (measured on a full decode) stay valid because a full decode and the WAV are identical.
    """
    if path.suffix.lower() == ".wav":
        return path
    out = WORK / f"{path.stem}.wav"
    if not out.exists() or out.stat().st_mtime < path.stat().st_mtime:
        run(["ffmpeg", "-y", "-hide_banner", "-i", str(path), "-c:a", "pcm_s16le", "-ar", "48000", str(out)])
    return out


def load_take(name: str) -> None:
    """Point the renderer at one take's EDL module and its sources."""
    global EDL, MIC, SUBSCRIBE_AT, TALKING_HEAD, CLIPS_DIR, SYNC, ANGLE2, ANGLE2_SYNC, TAKE_PREFIX, CAPTION_WORDS
    global SILENCE_DB, QUIET_VOICE_DB
    global TAKE
    mod = importlib.import_module(name)
    TAKE = mod
    EDL, MIC, SUBSCRIBE_AT, TALKING_HEAD, CLIPS_DIR = mod.EDL, mod.MIC, mod.SUBSCRIBE_AT, mod.TALKING_HEAD, mod.CLIPS_DIR
    MIC = ensure_wav(MIC)
    SYNC = getattr(mod, "SYNC", SYNC)
    ANGLE2, ANGLE2_SYNC = getattr(mod, "ANGLE2", None), getattr(mod, "ANGLE2_SYNC", None)
    TAKE_PREFIX = getattr(mod, "TAKE_PREFIX", "")
    CAPTION_WORDS = getattr(mod, "CAPTION_WORDS", CAPTION_WORDS)
    SILENCE_DB = getattr(mod, "SILENCE_DB", SILENCE_DB)
    QUIET_VOICE_DB = getattr(mod, "QUIET_VOICE_DB", QUIET_VOICE_DB)  # must sit above the mic's noise floor too


def text_file(name: str, text: str) -> str:
    path = TXT_DIR / f"{name}.txt"
    path.write_text(text, encoding="utf-8")
    return path.relative_to(HERE).as_posix()


def overlays(seg: dict, idx: int, dur: float) -> tuple[list[str], list[dict]]:
    """Returns (filters on the base picture, branded PNG overlays to composite on top)."""
    filters, images = [], []
    card_secs = seg.get("card_secs", 0)
    if card_secs:
        # opaque card over the talking head; his voice keeps running underneath
        num = seg["card"][0]
        fades = []
        # no fade-in: the card cuts in instantly so he's never seen talking before it (user)
        if seg.get("card_out"):
            fades.append(f"fade=t=out:st={max(card_secs - CARD_FADE, 0):.3f}:d={CARD_FADE}:alpha=1")
        push = None  # cards stay perfectly still: any zoom on sharp text shimmered (user: "shaking like an earthquake")
        images.append({"png": BRAND / f"card_{num}.png", "x": 0, "y": 0, "fades": fades,
                       "enable": f"lt(t,{card_secs:.3f})"})
    if seg.get("num"):
        # corner badge takes over once the title card is gone
        # after the card, the opener line stays up in the corner for the rest of the item
        images.append({"png": BRAND / f"corner_{seg['num']}.png", "x": 36, "y": 30, "fades": [],
                       "enable": f"gte(t,{card_secs:.3f})" if card_secs else None})
    if seg.get("caption"):
        tf = text_file(f"cap_{idx}", seg["caption"])
        show = min(dur, seg.get("caption_secs", 4.5))
        filters.append(f"drawtext=fontfile={CAPTION_FONT}:textfile={tf}:fontsize=58:fontcolor=white:text_align=C"
                       f":line_spacing=12:{SHADOW}:borderw=2:bordercolor=black@0.55"
                       f":x=(w-text_w)/2:y=h-text_h-120:enable='lt(t,{show})'")
    if seg.get("top_label"):
        # clips carry their own burned-in captions at the bottom, so labels go up top
        tf = text_file(f"top_{idx}", seg["top_label"])
        filters.append(f"drawtext=fontfile={CAPTION_FONT}:textfile={tf}:fontsize=54:fontcolor=white"
                       f":{SHADOW}:borderw=2:bordercolor=black@0.55:x=(w-text_w)/2:y=70:enable='lt(t,2.5)'")
    if seg.get("cta"):
        images.append({"png": BRAND / "cta.png", "x": 1920 - 470 - 60, "y": (1080 - 640) // 2, "fades": [], "enable": None})
    return filters, images


def subscribe_sfx() -> Path:
    """Soft pop as the pill appears, a mouse click, then a bell ding, timed to the animation frames."""
    out = WORK / "subscribe_sfx.wav"
    pop = "0.5*sin(2*PI*(700*t-2200*t*t))*exp(-30*t)"
    click = "(0.7*(random(0)*2-1)*exp(-400*t)+0.5*sin(2*PI*180*t)*exp(-70*t))"
    click_ms, bell_ms = int(SUB_CLICK_AT * 1000), int(SUB_BELL_AT * 1000)
    run(["ffmpeg", "-y", "-hide_banner",
         "-f", "lavfi", "-i", f"aevalsrc='{pop}':s=48000:d=0.25",
         "-f", "lavfi", "-i", f"aevalsrc='{click}':s=48000:d=0.12",
         "-i", str(DING),  # real "attention bell ding" (mixkit 217) instead of a synth tone
         "-filter_complex", f"[1]adelay={click_ms}[c];[2]aresample=48000,atrim=0:1.2,volume=0.6,adelay={bell_ms}:all=1[b];"
                            f"[0][c][b]amix=inputs=3:normalize=0,apad=whole_dur={SUB_SECS},volume=-6dB",
         "-ac", "2", str(out)])
    return out


CAPTION_WORDS = WORK / "caption_words.json"  # medium-model transcript of the kept mic ranges, camera time
CAP_FONT_DIR = WORK / "capfonts"
CAP_GOLD = "&H0073D8FF&"  # brand gold #FFD873 in ASS BGR
CAP_FIXES = {"with one": "with women", "go tools": "go-tos"}  # whisper slips on this channel's words
CAPTION_STYLE = "hormozi"  # "hormozi" (user's pick, 2026-10-01) or "sparked" (the earlier soft karaoke style)


def ass_time(t: float) -> str:
    t = max(t, 0)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def build_captions_hormozi(th_spans, starts, sub_times) -> Path:
    """Alex Hormozi-style captions: ALL CAPS Montserrat Black, 1-3 words at a time, lower-centre,
    white with a heavy black outline, each word turning brand gold as it's spoken, quick pop-in on each chunk.
    Talking head only (clips carry burned-in captions, cards cover the frame); lifted above the subscribe pop-up.
    """
    from fontTools.ttLib import TTFont

    CAP_FONT_DIR.mkdir(parents=True, exist_ok=True)
    src_font = WORK / "fonts" / "montserrat_900.ttf"
    shutil.copy(src_font, CAP_FONT_DIR / src_font.name)
    family = TTFont(src_font)["name"].getDebugName(1)
    words = []
    for w in json.loads(CAPTION_WORDS.read_text()):
        if words and w["text"].startswith("-"):  # whisper splits hyphenated words ("go" "-tos")
            words[-1] = dict(words[-1], text=words[-1]["text"] + w["text"], end=w["end"])
        else:
            words.append(w)
    style = "{name},{family},92,&H00FFFFFF,&H00FFFFFF,&H00000000,&HA0000000,-1,0,0,0,100,100,1,0,1,7,4,2,120,120,{mv},1"
    head = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
            f"[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
            f"Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
            f"MarginR, MarginV, Encoding\n"
            f"Style: {style.format(name='Cap', family=family, mv=230)}\n"
            f"Style: {style.format(name='CapHigh', family=family, mv=400)}\n\n"
            f"[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    events = []
    for seg_i, s, e, card_secs in th_spans:
        t0 = starts[seg_i]
        ws = [dict(w, o_s=t0 + max(w["start"], s) - s, o_e=t0 + min(w["end"], e) - s)
              for w in words if s - 0.05 <= w["start"] < e - 0.05 and w["start"] - s >= card_secs - 0.05]
        chunks, cur = [], []
        for w in ws:
            chars = sum(len(x["text"]) for x in cur) + len(w["text"])
            # whisper capitalises sentence starts, so a capital (other than I/I'm/I'll/I've) also ends the chunk
            new_sentence = w["text"][:1].isupper() and w["text"].rstrip(".,!?") not in ("I", "I'm", "I'll", "I've", "I'd")
            if cur and (len(cur) == 3 or chars > 16 or w["o_s"] - cur[-1]["o_e"] > 0.3 or cur[-1]["text"][-1:] in ".?!,"
                        or new_sentence):
                chunks.append(cur)
                cur = []
            cur.append(w)
        if cur:
            chunks.append(cur)
        piece_end = t0 + (e - s)
        for ci, ch in enumerate(chunks):
            line = " ".join(x["text"] for x in ch)
            for bad, good in CAP_FIXES.items():
                line = line.replace(bad, good)
            toks = [t.strip(".,!?\"").upper() for t in line.split()]
            # the word being spoken turns gold (user, 2026-10-01: "each word highlighted as I talk");
            # if a fix changed the word count the timings no longer line up, so show the chunk plain
            per_word = len(toks) == len(ch)
            st0 = ch[0]["o_s"]
            nxt = chunks[ci + 1][0]["o_s"] if ci + 1 < len(chunks) else piece_end
            chunk_end = min(nxt, ch[-1]["o_e"] + 0.3, piece_end)
            style_name = "CapHigh" if any(t - 0.2 <= st0 <= t + SUB_SECS for t in sub_times) else "Cap"
            for wi in range(len(ch)) if per_word else [None]:
                st = st0 if not wi else ch[wi]["o_s"]
                en = ch[wi + 1]["o_s"] if per_word and wi + 1 < len(ch) else chunk_end
                if en - st < 0.04:
                    continue
                shown = " ".join(f"{{\\c{CAP_GOLD}}}{t}{{\\c&H00FFFFFF&}}" if j == wi else t for j, t in enumerate(toks) if t)
                pop = r"{\fscx85\fscy85\t(0,90,\fscx100\fscy100)}" if not wi else ""  # the chunk pops in once
                events.append(f"Dialogue: 0,{ass_time(st)},{ass_time(en)},{style_name},,0,0,0,,{pop}{shown}")
    out = WORK / "captions.ass"
    out.write_text(head + "\n".join(events) + "\n", encoding="utf-8-sig")
    return out


def build_captions(th_spans, starts, sub_times) -> Path:
    """Word-by-word captions for the talking head only (clips carry burned-in captions, cards cover the frame).

    Sparked style: natural case, 2-4 words at a time, active word in brand gold, soft fade, no bounce.
    Lifted above the subscribe pop-up while it's on screen.
    """
    if CAPTION_STYLE == "hormozi":
        return build_captions_hormozi(th_spans, starts, sub_times)
    from fontTools.ttLib import TTFont

    CAP_FONT_DIR.mkdir(parents=True, exist_ok=True)
    src_font = WORK / "fonts" / "grotesk_600.ttf"
    shutil.copy(src_font, CAP_FONT_DIR / src_font.name)
    family = TTFont(src_font)["name"].getDebugName(1)
    words = []
    for w in json.loads(CAPTION_WORDS.read_text()):
        if words and w["text"].startswith("-"):  # whisper splits hyphenated words ("go" "-tos")
            words[-1] = dict(words[-1], text=words[-1]["text"] + w["text"], end=w["end"])
        else:
            words.append(w)
    head = (f"[Script Info]\nScriptType: v4.00+\nPlayResX: 1920\nPlayResY: 1080\nWrapStyle: 2\nScaledBorderAndShadow: yes\n\n"
            f"[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, "
            f"Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
            f"MarginR, MarginV, Encoding\n"
            f"Style: Cap,{family},66,&H00F6ECE3,&H00FFFFFF,&H00100705,&H99000000,0,0,0,0,100,100,0.5,0,1,3,2,2,120,120,110,1\n"
            f"Style: CapHigh,{family},66,&H00F6ECE3,&H00FFFFFF,&H00100705,&H99000000,0,0,0,0,100,100,0.5,0,1,3,2,2,120,120,330,1\n\n"
            f"[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n")
    events = []
    for seg_i, s, e, card_secs in th_spans:
        t0 = starts[seg_i]
        ws = [dict(w, o_s=t0 + max(w["start"], s) - s, o_e=t0 + min(w["end"], e) - s)
              for w in words if s - 0.05 <= w["start"] < e - 0.05 and w["start"] - s >= card_secs - 0.05]
        chunks, cur = [], []
        for w in ws:
            text_so_far = " ".join(x["text"] for x in cur)
            if cur and (len(cur) == 4 or w["o_s"] - cur[-1]["o_e"] > 0.35 or len(text_so_far) + len(w["text"]) > 26
                        or cur[-1]["text"][-1:] in ".?!,"):
                chunks.append(cur)
                cur = []
            cur.append(w)
        if cur:
            chunks.append(cur)
        piece_end = t0 + (e - s)
        for ci, ch in enumerate(chunks):
            line = " ".join(x["text"] for x in ch)
            for bad, good in CAP_FIXES.items():
                line = line.replace(bad, good)
            toks = line.split()
            if len(toks) != len(ch):  # a fix changed the word count; show the chunk without per-word highlight
                toks, per_word = [line], False
            else:
                per_word = True
            nxt = chunks[ci + 1][0]["o_s"] if ci + 1 < len(chunks) else piece_end
            style = "CapHigh" if any(st - 0.2 <= ch[0]["o_s"] <= st + SUB_SECS for st in sub_times) else "Cap"
            steps = range(len(ch)) if per_word else [0]
            for wi in steps:
                st = ch[wi]["o_s"] if wi else ch[0]["o_s"]
                en = ch[wi + 1]["o_s"] if per_word and wi + 1 < len(ch) else min(nxt, ch[-1]["o_e"] + 0.3, piece_end)
                if en - st < 0.04:
                    continue
                shown = " ".join((f"{{\\c{CAP_GOLD}}}{tok.rstrip(',.')}{{\\r}}" if per_word and j == wi else tok.rstrip(",."))
                                 for j, tok in enumerate(toks))
                fade = r"{\fad(90,0)}" if wi == 0 else ""
                events.append(f"Dialogue: 0,{ass_time(st)},{ass_time(en)},{style},,0,0,0,,{fade}{shown}")
    out = WORK / "captions.ass"
    out.write_text(head + "\n".join(events) + "\n", encoding="utf-8-sig")
    return out


def segment_starts(segments: list[Path]) -> list[float]:
    """Actual start time of each segment in the joined file (frame rounding adds up over 70 cuts)."""
    starts, t = [], 0.0
    for p in segments:
        starts.append(t)
        t += float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                                   "-of", "default=nw=1:nk=1", str(p)], capture_output=True, text=True).stdout)
    return starts


STING = HERE / "input" / "brand_sting.mkv"  # 'Sparked Thor' sting, same as the video-chat long-forms (make_brand_sting.py)


def render_sting(idx: int) -> Path:
    """The channel's branded intro sting between the hook and the video (fades up from / down to black)."""
    out = SEG_DIR / f"seg_{idx:03d}.mkv"
    run(["ffmpeg", "-y", "-hide_banner", "-i", str(STING), "-vf",
         "scale=1920:1080:force_original_aspect_ratio=decrease,pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p"]
        + VIDEO_ARGS + SEG_AUDIO_ARGS + [str(out)])
    return out


def render_endscreen(idx: int) -> Path:
    """Sparked endscreen with a slow push-in, fading up from black, silent bed."""
    out = SEG_DIR / f"seg_{idx:03d}.mkv"
    if REUSE and out.exists():
        return out
    from PIL import Image

    # the push-in is drawn here with sub-pixel crop boxes: ffmpeg's zoompan snaps its crop to whole pixels
    # each frame, which made the endscreen visibly shake (user, 2026-10-01: "like an earthquake")
    frames = int(ENDSCREEN_SECS * 30)
    src = Image.open(BRAND / "endscreen.png").convert("RGB")
    w, h = src.size
    proc = subprocess.Popen(["ffmpeg", "-y", "-hide_banner", "-v", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
                             "-s", f"{w}x{h}", "-framerate", "30", "-i", "-",
                             "-f", "lavfi", "-t", f"{ENDSCREEN_SECS}", "-i", "anullsrc=r=48000:cl=stereo",
                             "-vf", "fade=t=in:st=0:d=0.4,format=yuv420p", "-map", "0:v", "-map", "1:a"]
                            + VIDEO_ARGS + SEG_AUDIO_ARGS + ["-shortest", str(out)], stdin=subprocess.PIPE, cwd=HERE)
    for i in range(frames):
        p = i / max(frames - 1, 1)
        z = 1 + 0.06 * p * p * (3 - 2 * p)  # eased, like the talking-head push-ins
        cw, ch = w / z, h / z
        box = ((w - cw) / 2, (h - ch) / 2, (w + cw) / 2, (h + ch) / 2)
        proc.stdin.write(src.resize((w, h), Image.LANCZOS, box=box).tobytes())
    proc.stdin.close()
    if proc.wait() != 0:
        raise RuntimeError("endscreen render failed")
    return out


def zoom_vf(z: str, y_anchor: float = 0.5) -> str:
    """Smooth eased zoom with SUB-PIXEL accuracy. `z` is an expression in T (seconds into the piece).

    The perspective filter samples the input at fractional coordinates every frame, so the zoom glides.
    Integer scale+crop stepped 1-2px per frame and made title cards shake ("like an earthquake"), and cropping
    with (iw-1920)/2 used the first frame's width only, so zooms drifted and jumped at cuts ("pans then resets")."""
    zz = z.replace("T", "(on/30)")
    x0 = f"(W-W/{zz})*0.5"
    y0 = f"(H-H/{zz})*{y_anchor}"
    x1 = f"{x0}+W/{zz}"
    y2 = f"{y0}+H/{zz}"
    return (f"perspective=x0='{x0}':y0='{y0}':x1='{x1}':y1='{y0}':x2='{x0}':y2='{y2}':x3='{x1}':y3='{y2}'"
            f":interpolation=cubic:eval=frame")


def render_segment(seg: dict, idx: int, start: float, end: float, src: Path, gain: float, punch_in: bool) -> Path:
    out = SEG_DIR / f"seg_{idx:03d}.mkv"
    if REUSE and out.exists():
        return out
    dur = end - start
    side = src == TALKING_HEAD and seg.get("angle") == "side"
    vf = ["scale=1920:1080:force_original_aspect_ratio=decrease", "pad=1920:1080:(ow-iw)/2:(oh-ih)/2", "fps=30"]
    if seg.get("delogo"):
        # paint out a burned-in overlay from the source upload (e.g. an "8/10" rating badge), source pixel coords
        x, y, w, h = seg["delogo"]
        vf.insert(0, f"delogo=x={x}:y={y}:w={w}:h={h}")
    if side:
        vf = SIDE_VF + vf
    if src == TALKING_HEAD:
        # slow eased push-in (smoothstep), alternating base framing so jump cuts read as camera moves
        base = seg.get("base", PUSH_BASE[0])
        z = f"({base}+{PUSH_AMOUNT}*(min(T/{dur:.3f},1)*min(T/{dur:.3f},1)*(3-2*min(T/{dur:.3f},1))))"
        vf += [zoom_vf(z, 0.4)]  # anchored a little above centre: his face
    vf.append(GRADE)
    if src == TALKING_HEAD:
        vf.append("vignette=PI/5")
    extra_vf, images = overlays(seg, idx, dur)
    vf += extra_vf
    # PEAK_TAMER runs after the gain on every source: taming only the talking head lowered the
    # average and pushed a loud infield laugh over the 8 LU spike gate instead
    af = f"volume={gain}dB,{PEAK_TAMER},afade=t=in:d=0.02,afade=t=out:st={max(dur - 0.04, 0):.3f}:d=0.04"
    if src == TALKING_HEAD:
        # VOICE_CHAIN runs on the raw (quiet) mic, so it barely touches emphasised words ("Number two!"
        # spiked 8 LU over the average); PEAK_TAMER after the gain catches those
        af = VOICE_CHAIN + "," + af
    # start/end stay in main-camera time everywhere (captions, silences); only the side picture seeks elsewhere
    v_src, v_start = (ANGLE2, main_to_side(start)) if side else (src, start)
    cmd = ["ffmpeg", "-y", "-hide_banner", "-ss", f"{v_start:.3f}", "-t", f"{dur:.3f}", "-i", str(v_src)]
    audio_in = 0
    if src == TALKING_HEAD:
        # picture from the camera, sound from the synced external mic
        mic_start = cam_to_mic(start)
        cmd += ["-ss", f"{mic_start:.3f}", "-t", f"{dur:.3f}", "-i", str(MIC)]
        audio_in = 1
    elif src in CLEAN_AUDIO:
        # denoised wav is sample-aligned with the clip (deep-filter -D), so the same seek applies
        cmd += ["-ss", f"{start:.3f}", "-t", f"{dur:.3f}", "-i", str(CLEAN_AUDIO[src])]
        audio_in = 1
    fc = [f"[0:v]{','.join(vf)}[b0]"]
    for k, img in enumerate(images):
        n = audio_in + 1 + k
        cmd += ["-loop", "1", "-framerate", "30", "-t", f"{dur:.3f}", "-i", str(img["png"])]
        fc.append(f"[{n}:v]{','.join(['format=rgba'] + img['fades'])}[i{k}]")
        enable = f":enable='{img['enable']}'" if img["enable"] else ""
        fc.append(f"[b{k}][i{k}]overlay={img['x']}:{img['y']}:shortest=1{enable}[b{k + 1}]")
    fc.append(f"[b{len(images)}]format=yuv420p[v];[{audio_in}:a]{af}[a]")
    cmd += ["-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[a]"]
    run(cmd + VIDEO_ARGS + SEG_AUDIO_ARGS + [str(out)])
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="output/ten_openers_v1.mp4")
    parser.add_argument("--edl", default="edl", help="EDL module for the take, e.g. edl_take2")
    parser.add_argument("--reuse-segments", action="store_true", help="only redo the final mix (same EDL as last run)")
    parser.add_argument("--no-denoise", action="store_true", help="Use the infield clips' raw street audio")
    parser.add_argument("--denoise-atten", type=float, default=18.0, help="Max street-noise reduction in dB")
    args = parser.parse_args()
    load_take(args.edl)
    global REUSE
    REUSE = args.reuse_segments
    if not args.no_denoise:
        for clip in sorted({CLIPS_DIR / f"{seg['src']}.mp4" for seg in EDL if seg["src"] not in ("th", "endscreen", "sting")}):
            print(f"denoise {clip.name}", flush=True)
            CLEAN_AUDIO[clip] = denoised_wav(clip, WORK / "denoised", args.denoise_atten)

    if not REUSE:
        shutil.rmtree(SEG_DIR, ignore_errors=True)
    SEG_DIR.mkdir(parents=True, exist_ok=True)
    TXT_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "brand_graphics.py"], cwd=HERE, check=True)

    silences = talking_head_silences()
    gains: dict = {}
    segments, idx, th_pieces, last_side = [], 0, 0, False
    last_main_base = None
    angle_secs = {"main": 0.0, "side": 0.0, "close": 0.0}
    main_auto = 0
    card_starts, close_seg, end_seg = [], None, None
    clip_segs, body_seg = [], None  # output segment indices of infield clips / first body segment
    card_left, card, shown_before = 0.0, None, 0.0
    th_spans = []  # (segment index, cam start, cam end) for mapping spoken words onto the output timeline
    # plan every talking-head cut for the whole video first, so repeats/glances across cut boundaries are caught
    plan = {k: split_on_pauses(seg["start"], seg["end"], silences, seg.get("exact_start", False), seg.get("exact_end", False))
            for k, seg in enumerate(EDL) if seg["src"] == "th"}
    from gaze import Gaze
    from refine import load_words, refine
    db, _ = mic_levels()
    voiced = lambda t: db[min(int(cam_to_mic(t) / 0.02), len(db) - 1)] > SILENCE_DB + 6
    audible = lambda t: db[min(int(cam_to_mic(t) / 0.02), len(db) - 1)] > SILENCE_DB + 3  # softer than voiced: keeps word tails
    plan, log = refine(EDL, plan, load_words(CAPTION_WORDS), Gaze(TALKING_HEAD), voiced, getattr(TAKE, "CUT_OUT", ()), audible)
    print("cut planner:\n" + "\n".join(log), flush=True)
    for k, seg in enumerate(EDL):
        if seg["src"] == "sting":
            segments.append(render_sting(idx))
            body_seg = len(segments) + 1  # the body (and its music bed) starts right after the sting
            idx += 1
            print("brand sting", flush=True)
            continue
        if seg["src"] == "endscreen":
            end_seg = len(segments)
            segments.append(render_endscreen(idx))
            idx += 1
            print("endscreen", flush=True)
            continue
        if seg["src"] == "th":
            src, ranges = TALKING_HEAD, plan[k]
        else:
            src, ranges = CLIPS_DIR / f"{seg['src']}.mp4", [(seg["start"], seg["end"])]
            clip_segs.append(len(segments))
        gain = source_gain(MIC if src == TALKING_HEAD else CLEAN_AUDIO.get(src, src), gains)
        # a card starts on the item's first line and carries across short talking-head segments
        # ("Number nine." is under a second); an infield clip always ends it
        if seg.get("card"):
            card_left, card, shown_before = CARD_SECS, seg["card"], 0.0
        elif src != TALKING_HEAD:
            card_left = 0.0
        for i, (s, e) in enumerate(ranges):
            # captions/CTA only on the first piece of a jump-cut range, numbers on all
            piece = seg if i == 0 else {k: v for k, v in seg.items() if k not in ("caption",)}
            if src == TALKING_HEAD and ANGLE2:
                # delivery (openers, intro, close, CTA) stays on the main angle; explanations cut to the side
                # angle now and then, never twice in a row and never on a flash-length piece
                mode = seg.get("angle") or ("main" if seg.get("card") or seg.get("cta") or seg.get("label") else "auto")
                if mode == "auto":
                    total = sum(angle_secs.values()) + (e - s)
                    behind = (angle_secs["side"] + (e - s)) / total <= SIDE_SHARE + 0.03
                    mode = "side" if behind and e - s >= SIDE_MIN_SECS and not last_side else "main"
                    if mode == "main":
                        main_auto += 1
                        if main_auto % 3 == 0 and e - s >= 2.0:
                            mode = "close"  # third angle: a tight close-up of the main camera for variety
                piece = {**piece, "angle": mode}
                last_side = mode == "side"
                angle_secs[mode] += e - s
            if card_left > 0:
                # a title card can span jump cuts; it only fades in on the first piece and out on the last
                shown = min(card_left, e - s)
                card_left -= shown
                piece = {**piece, "card": card, "card_secs": shown, "card_in": shown_before == 0, "card_out": card_left <= 0,
                         "card_offset": shown_before}
                shown_before += shown
            is_th = src == TALKING_HEAD
            if is_th:
                # framing alternates on what's actually visible on the main camera: two same-framed main pieces in a
                # row made the push-in visibly snap back at the cut (user: 'it pans then resets' at #6 and #3)
                if piece.get("angle") == "close":
                    base = CLOSE_BASE
                elif piece.get("angle") == "side":
                    base = PUSH_BASE[0]
                else:
                    base = PUSH_BASE[1] if last_main_base == PUSH_BASE[0] else PUSH_BASE[0]
                if piece.get("angle") != "side":
                    assert base != last_main_base or piece.get("card_secs", 0) >= e - s - 0.05, \
                        f"two same-framed main pieces in a row at {s:.2f}s"
                    last_main_base = base if not piece.get("card_secs", 0) >= e - s - 0.05 else last_main_base
                piece = {**piece, "base": base}
            segments.append(render_segment(piece, idx, s, e, src, gain, punch_in=False))
            if piece.get("card_in"):
                card_starts.append(len(segments) - 1)
            if seg.get("label") == "close" and i == 0:
                close_seg = len(segments) - 1
            if is_th:
                th_spans.append((len(segments) - 1, s, e, piece.get("card_secs", 0)))
            th_pieces += is_th
            idx += 1
        print(f"{seg.get('label', seg['src'])}: {len(ranges)} piece(s)", flush=True)

    concat_list = WORK / "concat.txt"
    concat_list.write_text("".join(f"file '{p.resolve().as_posix()}'\n" for p in segments))
    joined = WORK / "joined.mkv"
    run(["ffmpeg", "-y", "-hide_banner", "-f", "concat", "-safe", "0", "-i", str(concat_list), "-c", "copy", str(joined)])

    # everything timed to the finished timeline goes on in one pass, so jump cuts can't chop it:
    # subscribe pop-ups + SFX, a whoosh as each title card lands, and the R&B bed under the outro
    starts = segment_starts(segments)
    total = starts[-1] + ENDSCREEN_SECS
    sub_times = []
    for t in SUBSCRIBE_AT:
        # snap to the kept piece containing the moment, or the next one within 2s (cut trimming can move a
        # piece start past the marker; on take 2 v10 that silently dropped the mid-roll animation)
        hit = next(((i, s) for i, s, e, _ in th_spans if s <= t < e), None) or \
            next(((i, s) for i, s, e, _ in sorted(th_spans, key=lambda x: x[1]) if 0 <= s - t < 2.0), None)
        if hit is None:
            CUT_WARNINGS.append(f"subscribe moment at {t:.2f}s is not in the edit; animation NOT placed")
            continue
        i, s = hit
        sub_times.append(starts[i] + max(t - s, 0.0))
    captions = build_captions(th_spans, starts, sub_times)
    sfx = subscribe_sfx()
    cmd = ["ffmpeg", "-y", "-hide_banner", "-i", str(joined)]
    fc, afc, v, mix, n = [], [], "0:v", ["[0:a]"], 1  # fc: picture graph, afc: sound graph
    for k, t in enumerate(sub_times):
        cmd += ["-framerate", "30", "-i", str(BRAND / "subscribe" / "f_%03d.png"), "-i", str(sfx)]
        fc.append(f"[{n}:v]format=rgba,setpts=PTS+{t:.3f}/TB[s{k}]")
        fc.append(f"[{v}][s{k}]overlay=(W-w)/2:H-h-40:eof_action=pass[v{k}]")
        afc.append(f"[{n + 1}:a]adelay={int(t * 1000)}:all=1[x{k}]")
        v, n = f"v{k}", n + 2
        mix.append(f"[x{k}]")
    for k, i in enumerate(card_starts):
        cmd += ["-i", str(WHOOSH)]
        afc.append(f"[{n}:a]volume={WHOOSH_VOL},adelay={int(max(starts[i] - 0.15, 0) * 1000)}:all=1[w{k}]")
        mix.append(f"[w{k}]")
        n += 1
    if body_seg is not None and close_seg is not None and body_seg < close_seg:
        # music bed under the body: two smooth R&B tracks split at the midpoint, crossfading, looped if short,
        # dipped almost silent under every infield clip, handing over to the outro track at the close
        b0, b1 = starts[body_seg], starts[close_seg]
        clips = [(starts[i], starts[i + 1] if i + 1 < len(starts) else total) for i in clip_segs]
        mid = (b0 + b1) / 2
        for ti, (t0, t1) in enumerate(((b0, mid + 1.0), (mid - 1.0, b1 + 1.0))):
            dur = t1 - t0
            duck = "+".join(f"between(t,{a - t0 - 0.15:.2f},{z - t0 + 0.15:.2f})" for a, z in clips if z > t0 and a < t1) or "0"
            # loop into a WAV first: -stream_loop on an MP3 inside the mix left timestamp holes (0.56s of
            # missing samples on take 2 v11)
            bed_wav = WORK / f"bed_{ti}.wav"
            run(["ffmpeg", "-y", "-hide_banner", "-stream_loop", "-1", "-i", str(BODY_TRACKS[ti % len(BODY_TRACKS)]),
                 "-t", f"{dur + 0.5:.3f}", "-ar", "48000", "-ac", "2", "-c:a", "pcm_s16le", str(bed_wav)])
            cmd += ["-i", str(bed_wav)]
            afc.append(f"[{n}:a]atrim=0:{dur:.3f},asetpts=PTS-STARTPTS,"
                       f"volume='if({duck},{BODY_DUCK},{BODY_BED})':eval=frame,"
                       f"afade=t=in:d=2,afade=t=out:st={dur - 2:.3f}:d=2,adelay={int(t0 * 1000)}:all=1[bed{ti}]")
            mix.append(f"[bed{ti}]")
            n += 1
    if close_seg is not None and end_seg is not None:
        m0, m_end = starts[close_seg], starts[end_seg]
        dur = total - m0
        cmd += ["-i", str(MUSIC)]
        # low bed under the spoken close, swells on the endscreen, fades out with the picture
        afc.append(f"[{n}:a]atrim=0:{dur:.3f},asetpts=PTS-STARTPTS,"
                  f"volume='if(lt(t,{m_end - m0:.3f}),{MUSIC_BED},{MUSIC_SWELL})':eval=frame,"
                  f"afade=t=in:d=1.5,afade=t=out:st={dur - 1.5:.3f}:d=1.5,adelay={int(m0 * 1000)}:all=1[music]")
        mix.append("[music]")
    fc.append(f"[{v}]subtitles={captions.relative_to(HERE).as_posix()}:fontsdir={CAP_FONT_DIR.relative_to(HERE).as_posix()},format=yuv420p[vout]")
    afc.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first,aresample=48000:async=1:first_pts=0,loudnorm=I=-14:TP=-1.5:LRA=11,aresample=192000,alimiter=limit=0.75:level=disabled,aresample=48000[aout]")
    out = HERE / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    # picture and sound are encoded in separate passes, then stream-copied together: in one graph, take 2
    # (two subscribe pop-ups over a slow overlay+subtitles chain) lost 33s of audio samples while each
    # half on its own was complete
    v_tmp, a_tmp = WORK / "final_video.mkv", WORK / "final_audio.m4a"
    run(cmd + ["-filter_complex", ";".join(fc), "-map", "[vout]", "-an"] + VIDEO_ARGS + [str(v_tmp)])
    run(cmd + ["-filter_complex", ";".join(afc), "-map", "[aout]", "-vn"] + AUDIO_ARGS + [str(a_tmp)])
    run(["ffmpeg", "-y", "-hide_banner", "-i", str(v_tmp), "-i", str(a_tmp), "-map", "0:v", "-map", "1:a",
         "-c", "copy", "-movflags", "+faststart", str(out)])
    print(f"subscribe animations at {', '.join(f'{t:.1f}s' for t in sub_times)}; "
          f"{len(card_starts)} card whooshes; music from {starts[close_seg]:.1f}s")
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(out)],
                           capture_output=True, text=True).stdout.strip()
    print(f"Wrote {out} ({float(probe) / 60:.2f} min, {len(segments)} segments)")
    if ANGLE2:
        total_th = sum(angle_secs.values()) or 1
        print(f"angles: side {angle_secs['side']:.0f}s, close-up {angle_secs['close']:.0f}s of {total_th:.0f}s talking head "
          f"({angle_secs['side'] / total_th:.0%} side, {angle_secs['close'] / total_th:.0%} close)")
    for w in CUT_WARNINGS:
        print(f"CUT WARNING: {w}")


if __name__ == "__main__":
    main()
