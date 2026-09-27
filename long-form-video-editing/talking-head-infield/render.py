"""Cut the talking head, splice infield clips between lines, render the long-form video.

Usage:
    python render.py --out output/ten_openers_v1.mp4

The edit lives in edl.py (EDL list). Talking-head ranges get their internal
pauses (>= MIN_GAP) jump-cut out automatically; infield clips play as-is with
their real audio. Every segment is normalized to 1080p30 / 48k stereo so the
final concat is a straight stream copy, then the whole thing gets one loudnorm pass.
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

from brand_graphics import SUB_BELL_AT, SUB_CLICK_AT, SUB_SECS
from edl import CLIPS_DIR, EDL, MIC, SUBSCRIBE_AT, TALKING_HEAD

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
WHOOSH_VOL = 0.35
ENDSCREEN_SECS = 7.0  # YouTube end-screen elements need >= 5s; longer just bleeds retention
GRADE = "eq=contrast=1.06:saturation=1.1:gamma=0.98"
PUSH_BASE = (1.0, 1.07)  # talking-head pieces alternate wide/tighter framing to hide jump cuts
PUSH_AMOUNT = 0.035  # ...and each one eases in slowly (brand: smooth push-ins, never hard punch-ins)
VOICE_CHAIN = "highpass=f=80,acompressor=threshold=-20dB:ratio=3:attack=5:release=100:makeup=2"

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
CUT_WARNINGS: list[str] = []  # edges that couldn't land in a pause; printed after the render
CARD_PUSH = 0.05  # cards slowly push in 5% over their hold, so they never read as a frozen frame
CARD_SECS = 3.5  # how long each number's title card holds before the talking head returns
TARGET_LUFS = -16.0  # per-source static gain target before the final loudnorm

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
    cache = WORK / f"th_silences_mic_{min_gap:.2f}.json"
    if cache.exists():
        return [tuple(x) for x in json.loads(cache.read_text())]
    err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(MIC), "-vn",
               "-af", f"silencedetect=noise=-60dB:d={min_gap}", "-f", "null", "-"])
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


def cam_to_mic(t: float) -> float:
    # sync_mic.py measures offset = cam - mic, drifting slightly over the take
    sync = json.loads((WORK / "mic_sync.json").read_text())
    return t - sync["offset"] - sync["drift_per_sec"] * t


def mic_to_cam(t: float) -> float:
    sync = json.loads((WORK / "mic_sync.json").read_text())
    return t + sync["offset"] + sync["drift_per_sec"] * t


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
        if seg.get("card_in"):
            fades.append(f"fade=t=in:st=0:d={CARD_FADE}:alpha=1")
        if seg.get("card_out"):
            fades.append(f"fade=t=out:st={max(card_secs - CARD_FADE, 0):.3f}:d={CARD_FADE}:alpha=1")
        push = (f"scale=w='trunc(1920*(1+{CARD_PUSH}*(t+{seg.get('card_offset', 0):.3f})/{CARD_SECS})/2)*2':h=-2:eval=frame,"
                "crop=1920:1080:(iw-1920)/2:(ih-1080)/2")
        images.append({"png": BRAND / f"card_{num}.png", "x": 0, "y": 0, "fades": [push] + fades,
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


def ass_time(t: float) -> str:
    t = max(t, 0)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def build_captions(th_spans, starts, sub_times) -> Path:
    """Word-by-word captions for the talking head only (clips carry burned-in captions, cards cover the frame).

    Sparked style: natural case, 2-4 words at a time, active word in brand gold, soft fade, no bounce.
    Lifted above the subscribe pop-up while it's on screen.
    """
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


def render_endscreen(idx: int) -> Path:
    """Sparked endscreen with a slow push-in, fading up from black, silent bed."""
    out = SEG_DIR / f"seg_{idx:03d}.mkv"
    frames = int(ENDSCREEN_SECS * 30)
    vf = (f"scale=3840:2160,zoompan=z='1+0.06*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
          f":d=1:s=1920x1080:fps=30,fade=t=in:st=0:d=0.4,format=yuv420p")
    run(["ffmpeg", "-y", "-hide_banner", "-loop", "1", "-framerate", "30", "-t", f"{ENDSCREEN_SECS}",
         "-i", str(BRAND / "endscreen.png"), "-f", "lavfi", "-t", f"{ENDSCREEN_SECS}", "-i", "anullsrc=r=48000:cl=stereo",
         "-vf", vf, "-map", "0:v", "-map", "1:a"] + VIDEO_ARGS + SEG_AUDIO_ARGS + ["-shortest", str(out)])
    return out


def render_segment(seg: dict, idx: int, start: float, end: float, src: Path, gain: float, punch_in: bool) -> Path:
    out = SEG_DIR / f"seg_{idx:03d}.mkv"
    dur = end - start
    vf = ["scale=1920:1080:force_original_aspect_ratio=decrease", "pad=1920:1080:(ow-iw)/2:(oh-ih)/2", "fps=30"]
    if src == TALKING_HEAD:
        # slow eased push-in (smoothstep), alternating base framing so jump cuts read as camera moves
        base = PUSH_BASE[1] if punch_in else PUSH_BASE[0]
        z = f"({base}+{PUSH_AMOUNT}*(min(t/{dur:.3f},1)*min(t/{dur:.3f},1)*(3-2*min(t/{dur:.3f},1))))"
        vf += [f"scale=w='trunc(1920*{z}/2)*2':h=-2:eval=frame", "crop=1920:1080:(iw-1920)/2:(ih-1080)*0.4"]
    vf.append(GRADE)
    if src == TALKING_HEAD:
        vf.append("vignette=PI/5")
    extra_vf, images = overlays(seg, idx, dur)
    vf += extra_vf
    af = f"volume={gain}dB,afade=t=in:d=0.02,afade=t=out:st={max(dur - 0.04, 0):.3f}:d=0.04"
    if src == TALKING_HEAD:
        af = VOICE_CHAIN + "," + af
    cmd = ["ffmpeg", "-y", "-hide_banner", "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(src)]
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
    parser.add_argument("--no-denoise", action="store_true", help="Use the infield clips' raw street audio")
    parser.add_argument("--denoise-atten", type=float, default=18.0, help="Max street-noise reduction in dB")
    args = parser.parse_args()
    if not args.no_denoise:
        for clip in sorted({CLIPS_DIR / f"{seg['src']}.mp4" for seg in EDL if seg["src"] not in ("th", "endscreen")}):
            print(f"denoise {clip.name}", flush=True)
            CLEAN_AUDIO[clip] = denoised_wav(clip, WORK / "denoised", args.denoise_atten)

    shutil.rmtree(SEG_DIR, ignore_errors=True)
    SEG_DIR.mkdir(parents=True)
    TXT_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.run([sys.executable, "brand_graphics.py"], cwd=HERE, check=True)

    silences = talking_head_silences()
    gains: dict = {}
    segments, idx, th_pieces = [], 0, 0
    card_starts, close_seg, end_seg = [], None, None
    card_left, card, shown_before = 0.0, None, 0.0
    th_spans = []  # (segment index, cam start, cam end) for mapping spoken words onto the output timeline
    for seg in EDL:
        if seg["src"] == "endscreen":
            end_seg = len(segments)
            segments.append(render_endscreen(idx))
            idx += 1
            print("endscreen", flush=True)
            continue
        if seg["src"] == "th":
            src, ranges = TALKING_HEAD, split_on_pauses(seg["start"], seg["end"], silences,
                                                       seg.get("exact_start", False), seg.get("exact_end", False))
        else:
            src, ranges = CLIPS_DIR / f"{seg['src']}.mp4", [(seg["start"], seg["end"])]
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
            if card_left > 0:
                # a title card can span jump cuts; it only fades in on the first piece and out on the last
                shown = min(card_left, e - s)
                card_left -= shown
                piece = {**piece, "card": card, "card_secs": shown, "card_in": shown_before == 0, "card_out": card_left <= 0,
                         "card_offset": shown_before}
                shown_before += shown
            is_th = src == TALKING_HEAD
            segments.append(render_segment(piece, idx, s, e, src, gain, punch_in=is_th and th_pieces % 2 == 1))
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
    sub_times = [starts[i] + (t - s) for t in SUBSCRIBE_AT for i, s, e, _ in th_spans if s <= t < e]
    captions = build_captions(th_spans, starts, sub_times)
    sfx = subscribe_sfx()
    cmd = ["ffmpeg", "-y", "-hide_banner", "-i", str(joined)]
    fc, v, mix, n = [], "0:v", ["[0:a]"], 1
    for k, t in enumerate(sub_times):
        cmd += ["-framerate", "30", "-i", str(BRAND / "subscribe" / "f_%03d.png"), "-i", str(sfx)]
        fc.append(f"[{n}:v]format=rgba,setpts=PTS+{t:.3f}/TB[s{k}]")
        fc.append(f"[{v}][s{k}]overlay=(W-w)/2:H-h-40:eof_action=pass[v{k}]")
        fc.append(f"[{n + 1}:a]adelay={int(t * 1000)}:all=1[x{k}]")
        v, n = f"v{k}", n + 2
        mix.append(f"[x{k}]")
    for k, i in enumerate(card_starts):
        cmd += ["-i", str(WHOOSH)]
        fc.append(f"[{n}:a]volume={WHOOSH_VOL},adelay={int(max(starts[i] - 0.15, 0) * 1000)}:all=1[w{k}]")
        mix.append(f"[w{k}]")
        n += 1
    if close_seg is not None and end_seg is not None:
        m0, m_end = starts[close_seg], starts[end_seg]
        dur = total - m0
        cmd += ["-i", str(MUSIC)]
        # low bed under the spoken close, swells on the endscreen, fades out with the picture
        fc.append(f"[{n}:a]atrim=0:{dur:.3f},asetpts=PTS-STARTPTS,"
                  f"volume='if(lt(t,{m_end - m0:.3f}),{MUSIC_BED},{MUSIC_SWELL})':eval=frame,"
                  f"afade=t=in:d=1.5,afade=t=out:st={dur - 1.5:.3f}:d=1.5,adelay={int(m0 * 1000)}:all=1[music]")
        mix.append("[music]")
    fc.append(f"[{v}]subtitles={captions.relative_to(HERE).as_posix()}:fontsdir={CAP_FONT_DIR.relative_to(HERE).as_posix()},format=yuv420p[vout]")
    fc.append(f"{''.join(mix)}amix=inputs={len(mix)}:normalize=0:duration=first,loudnorm=I=-14:TP=-1.5:LRA=11[aout]")
    out = HERE / args.out
    out.parent.mkdir(parents=True, exist_ok=True)
    run(cmd + ["-filter_complex", ";".join(fc), "-map", "[vout]", "-map", "[aout]"]
        + VIDEO_ARGS + AUDIO_ARGS + ["-movflags", "+faststart", str(out)])
    print(f"subscribe animations at {', '.join(f'{t:.1f}s' for t in sub_times)}; "
          f"{len(card_starts)} card whooshes; music from {starts[close_seg]:.1f}s")
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1", str(out)],
                           capture_output=True, text=True).stdout.strip()
    print(f"Wrote {out} ({float(probe) / 60:.2f} min, {len(segments)} segments)")
    for w in CUT_WARNINGS:
        print(f"CUT WARNING: {w}")


if __name__ == "__main__":
    main()
