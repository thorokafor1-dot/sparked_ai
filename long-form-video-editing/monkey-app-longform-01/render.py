"""Render the Monkey app long-form edit described in edit.json.

Pipeline:
  1. every piece (clip / freeze) is rendered to work/pieces/*.mp4 with the crop,
     her name-badge blur, punch-in zoom and speed baked in (cached by params)
  2. pieces are concatenated into work/base.mp4
  3. SFX bed and ducked music bed are built as separate wavs
  4. final pass: meme/emoji pops, ASS captions + text pops, audio mix -> out/

Usage: python render.py [edit.json] [--preview START END]
"""
import hashlib
import json
import re
import subprocess
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageOps

ROOT = Path(__file__).parent
RAW = "raw/raw.mkv"
WORK = ROOT / "work"
PIECES = WORK / "pieces"
OUT = ROOT / "out"
W, H, FPS, SR = 1920, 1080, 30, 48000

# Monkey web layout inside the 1280x720 browser screen recording
CROP_W, CROP_H, CROP_X, CROP_Y = 1280, 614, 0, 72
BADGE = (0, 0, 330, 80)            # her name/age/location badge, relative to the crop
FG_H = round(W * CROP_H / CROP_W / 2) * 2   # 920
FG_Y = (H - FG_H) // 2

CAP_FONT = "Montserrat Thin Black"
CAP_FONT_2 = "Montserrat Thin ExtraBold"   # fonts/Montserrat-ExtraBold.ttf, calmer weight
PROFANE = re.compile(r"^(fuck\w*|motherfuck\w*|shit\w*|bitch\w*)$", re.I)
MASK = {"FUCK": "F*CK", "SHIT": "SH*T", "BITCH": "B*TCH"}
EMOJI_FILES = {"👀": "1f440", "💀": "1f480", "😏": "1f60f", "🤨": "1f928", "⏭️": "23ed", "😳": "1f633", "⚡": "26a1",
               "📈": "1f4c8", "🔥": "1f525", "😂": "1f602"}


def load_words():
    tp = WORK / "transcript.json"
    out = []
    for seg in (json.load(open(tp, encoding="utf-8")) if tp.exists() else []):
        out += seg["words"]
    return out   # family name inside fonts/Montserrat-Black.ttf


def run(cmd):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        print(r.stderr[-3000:])
        sys.exit(f"ffmpeg failed: {' '.join(cmd[:6])} ...")


# ---------------------------------------------------------------- pieces

ZOOM_VER = 2          # bump when the zoom look changes so zoomed pieces re-render
EASE_FRAMES = 12      # push-in eases over ~0.4s


def frame_chain(zoom, dim=False, ease=False, blurs=()):
    """Shared video chain: crop browser chrome, blur badge, zoom, blurred-bg letterbox."""
    z, cx, cy = zoom or (1.0, 0.5, 0.5)
    bx, by, bw, bh = BADGE
    zw, zh = round(CROP_W / z / 2) * 2, round(CROP_H / z / 2) * 2
    zx = min(max(cx * CROP_W - zw / 2, 0), CROP_W - zw)
    zy = min(max(cy * CROP_H - zh / 2, 0), CROP_H - zh)
    c = (f"crop={CROP_W}:{CROP_H}:{CROP_X}:{CROP_Y},split[a][b];"
         f"[b]crop={bw}:{bh}:{bx}:{by},boxblur=18:4[bb];[a][bb]overlay={bx}:{by},"
         + "".join(f"split[p{i}][q{i}];[q{i}]crop={w}:{h}:{x}:{y},gblur=sigma=14:steps=3[r{i}];[p{i}][r{i}]overlay={x}:{y},"
                   for i, (x, y, w, h) in enumerate(blurs))   # personal info typed in chat (handles, numbers)
         + (f"scale={CROP_W * 2}:{CROP_H * 2}:flags=lanczos,"
            f"zoompan=z='1+({z}-1)*(1-pow(1-min(on/{EASE_FRAMES},1),3))':"
            f"x='max(0,min(iw-iw/zoom,{cx}*iw-iw/zoom/2))':y='max(0,min(ih-ih/zoom,{cy}*ih-ih/zoom/2))':"
            f"d=1:s={W}x{FG_H}:fps={FPS},setsar=1,split[f][g];"
            if ease and zoom else
            f"crop={zw}:{zh}:{zx:.0f}:{zy:.0f},scale={W}:{FG_H}:flags=lanczos,setsar=1,split[f][g];") +
         f"[g]scale=-2:{H},crop={W}:{H},boxblur=40:3,eq=brightness=-0.18[bg];"
         f"[bg][f]overlay=0:{FG_Y}")
    if dim:
        c += ",eq=brightness=-0.25:saturation=0.6"
    return c


CUT_PEAK_DB = -4.0    # cutaway audio peak before the final loudnorm (voice peaks sit around -3)


CUT_LUFS = -27.0      # cutaways loudness-matched to the (leveled) voice; they ranged -7..-34 LUFS raw


def cut_gain(name):
    res = subprocess.run(["ffmpeg", "-i", f"memeclips/{name}.mkv", "-af", "ebur128=peak=true", "-f", "null", "-"],
                         cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    summ = res[res.rfind("Summary:"):]
    i = re.search(r"I:\s+(-?[\d.]+) LUFS", summ)
    pk = re.search(r"Peak:\s+(-?[\d.]+) dBFS", summ)
    if not i or float(i.group(1)) < -60:      # silent clip
        return 0.0
    gain = CUT_LUFS - float(i.group(1))
    if pk:
        gain = min(gain, -6.0 - float(pk.group(1)))   # never let a scream clip past -6 dBFS
    return gain


def cut_mutes(name, start, dur):
    """Bleep swears in a cutaway: word timestamps cached next to the clip."""
    cache = ROOT / "memeclips" / f"{name}.words.json"
    if not cache.exists():
        from faster_whisper import WhisperModel
        model = WhisperModel("small.en", device="cpu", compute_type="int8")
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", f"memeclips/{name}.mkv", "-ac", "1", "-ar", "16000", "work/cut.wav"], cwd=ROOT)
        segs, _ = model.transcribe(str(WORK / "cut.wav"), word_timestamps=True)
        cache.write_text(json.dumps([{"w": w.word, "s": w.start, "e": w.end} for s in segs for w in s.words]), encoding="utf-8")
    words = json.loads(cache.read_text(encoding="utf-8"))
    return [(max(w["s"] - start - 0.03, 0), w["e"] - start + 0.03) for w in words
            if PROFANE.match(re.sub(r"[^\w]", "", w["w"])) and w["e"] > start and w["s"] < start + dur]


def frames_of(seconds):
    return max(1, round(seconds * FPS))


def atempo(speed):
    parts, s = [], speed
    while s > 2.0:
        parts.append("atempo=2.0")
        s /= 2.0
    parts.append(f"atempo={s:.4f}")
    return ",".join(parts)


def render_piece(p):
    key = hashlib.md5(json.dumps({k: p.get(k) for k in ("type", "in", "out", "at", "dur", "zoom", "speed", "mute", "dim", "vol", "mutes", "clip", "start", "blurs")} | ({"lufs": CUT_LUFS} if p["type"] == "cut" else {}) | {"exact": 1}
                                 | ({"zv": ZOOM_VER} if p.get("zoom") and p["type"] == "clip" else {}),
                                 sort_keys=True).encode()).hexdigest()[:12]
    path = PIECES / f"{key}.mkv"   # PCM audio: AAC priming would drift when concatenated
    if path.exists():
        return path
    enc = ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS),
           "-c:a", "pcm_s16le", "-ar", str(SR), "-ac", "2"]
    if p["type"] == "clip":
        sp = p.get("speed", 1.0)
        vf = f"[0:v]{frame_chain(p.get('zoom'), p.get('dim'), ease=True, blurs=p.get('blurs', ()))},setpts=(PTS-STARTPTS)/{sp},fps={FPS}[v]"
        nf = frames_of((p["out"] - p["in"]) / sp)
        dur = nf / FPS          # frame-exact: audio and video end on the same sample, so concat can't drift
        vol = 0 if p.get("mute") else p.get("vol", 1.0)
        bleeps = "".join(f"volume=0:enable='between(t,{a - p['in']:.3f},{b - p['in']:.3f})'," for a, b in p.get("mutes", []))
        af = (f"[0:a]asetpts=PTS-STARTPTS,{bleeps}{atempo(sp) + ',' if sp != 1 else ''}volume={vol},"
              f"apad,atrim=end_sample={round(dur * SR)},afade=t=in:d=0.012,afade=t=out:st={max(dur - 0.015, 0):.3f}:d=0.015[a]")
        cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{p['in']:.3f}", "-to", f"{p['out']:.3f}", "-i", RAW,
               "-filter_complex", vf + ";" + af, "-map", "[v]", "-map", "[a]", "-frames:v", str(nf), *enc, str(path)]
    elif p["type"] == "cut":  # full-screen reaction cutaway with its own audio (Jameer style)
        n = frames_of(p["dur"])
        src = f"memeclips/{p['clip']}.mkv"
        vf = f"[0:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={FPS}[v]"
        ns = round(n / FPS * SR)
        if p["clip"] == "tv_glitch":   # static hiss instead of whatever audio the source glitch carried
            af = f"anoisesrc=color=white:amplitude=0.06:sample_rate={SR},highpass=f=900,aformat=channel_layouts=stereo,atrim=end_sample={ns}[a]"
        else:
            bleeps = "".join(f"volume=0:enable='between(t,{a:.3f},{b:.3f})'," for a, b in cut_mutes(p["clip"], p["start"], p["dur"]))
            af = (f"[0:a]asetpts=PTS-STARTPTS,{bleeps}volume={cut_gain(p['clip']):.2f}dB,apad,atrim=end_sample={ns},"
                  f"afade=t=in:d=0.01,afade=t=out:st={max(n / FPS - 0.03, 0):.3f}:d=0.03[a]")
        cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{p['start']:.3f}", "-i", src,
               "-filter_complex", vf + ";" + af, "-map", "[v]", "-map", "[a]", "-frames:v", str(n), *enc, str(path)]
    else:  # freeze
        n = frames_of(p["dur"])
        vf = (f"[0:v]trim=end_frame=1,loop=loop={n}:size=1:start=0,setpts=N/{FPS}/TB,"
              f"{frame_chain(p.get('zoom'), p.get('dim', False), blurs=p.get('blurs', ()))}[v]")
        cmd = ["ffmpeg", "-v", "error", "-y", "-ss", f"{p['at']:.3f}", "-i", RAW,
               "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=stereo",
               "-filter_complex", vf + f";[1:a]atrim=end_sample={round(n / FPS * SR)}[a]",
               "-map", "[v]", "-map", "[a]", "-frames:v", str(n), *enc, str(path)]
    run(cmd)
    return path


def expand(edit):
    """Split clips with 'zooms' into sub-pieces and compute output timing for every piece."""
    pieces = []
    for p in edit["pieces"]:
        if p["type"] == "clip" and p.get("zooms"):
            cuts = sorted({p["in"], p["out"], *[t for z in p["zooms"] for t in z[:2] if p["in"] < t < p["out"]]})
            for a, b in zip(cuts, cuts[1:]):
                zm = next((z[2:] for z in p["zooms"] if z[0] <= a and b <= z[1]), None)
                pieces.append({**p, "in": a, "out": b, "zoom": zm, "zooms": None,
                               "fx": [f for f in p.get("fx", []) if a <= f["at"] < b or (f["at"] == p["out"] and b == p["out"])],
                               "hl": p.get("hl", []), "_parent": id(p)})
        else:
            pieces.append(p)
    t = 0.0
    for p in pieces:
        p["_t0"] = t
        p["_dur"] = frames_of((p["out"] - p["in"]) / p.get("speed", 1.0) if p["type"] == "clip" else p["dur"]) / FPS
        t += p["_dur"]
    return pieces, t


def out_time(p, at):
    """Map a source timestamp (clips) or relative offset (freeze) to output time."""
    if p["type"] == "clip":
        return p["_t0"] + (at - p["in"]) / p.get("speed", 1.0)
    return p["_t0"] + at


# ---------------------------------------------------------------- captions + text pops (ASS)

def ass_time(t):
    t = max(t, 0)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


ASS_HEAD = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{CAP_FONT_2},66,&H00FFFFFF,&H00FFFFFF,&H00141414,&H80000000,0,0,0,0,100,100,1,0,1,4,2,2,60,60,140,1
Style: Pop,{CAP_FONT_2},84,&H00FFFFFF,&H00FFFFFF,&H00141414,&H80000000,0,0,0,0,100,100,4,0,1,3,3,5,60,60,60,1
Style: Banner,{CAP_FONT_2},50,&H00FFFFFF,&H00FFFFFF,&H00000000,&HA0000000,0,0,0,0,100,100,8,0,3,16,0,8,60,60,70,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

HL = r"{\c&H0051C4F5&}"                        # active word: soft gold, no size bump (smooth, not bouncy)
KEY = ""                                       # keyword colouring retired (mature look)


def clean(w):
    return re.sub(r"[^\w'?!$%]", "", w).upper()


def captions(pieces, edit):
    words = load_words()
    small_p = WORK / "transcript_small.json"
    small = [w for sg in json.load(open(small_p, encoding="utf-8")) for w in sg["words"]] if small_p.exists() else words
    fixes = {k.upper(): v.upper() for k, v in edit.get("caption_fixes", {}).items()}
    keys = {k.upper() for k in edit.get("key_words", [])}
    lines = []
    for p in pieces:
        if p["type"] != "clip" or p.get("speed", 1.0) != 1.0 or p.get("mute") or p.get("nocap"):
            continue
        src = small if p.get("cap_src") == "small" else words
        ws = [w for w in src if p["in"] - 0.06 <= w["s"] < p["out"] - 0.05]
        ws = [{"t": clean(w["w"]), "s": out_time(p, max(w["s"], p["in"])), "e": out_time(p, min(w["e"], p["out"]))}
              for w in ws if clean(w["w"])]
        for w in ws:
            w["t"] = fixes.get(w["t"], w["t"])
            for k, v in MASK.items():
                w["t"] = w["t"].replace(k, v)
        # chunk into 1-3 word groups
        chunks, cur = [], []
        for i, w in enumerate(ws):
            if cur and (len(cur) == 3 or w["s"] - cur[-1]["e"] > 0.35 or sum(len(x["t"]) for x in cur) + len(w["t"]) > 16
                        or cur[-1]["t"][-1:] in "?!"):
                chunks.append(cur)
                cur = []
            cur.append(w)
        if cur:
            chunks.append(cur)
        end_lim = p["_t0"] + p["_dur"]
        for ci, ch in enumerate(chunks):
            nxt = chunks[ci + 1][0]["s"] if ci + 1 < len(chunks) else end_lim
            for wi, w in enumerate(ch):
                s = w["s"] if wi else ch[0]["s"]
                e = ch[wi + 1]["s"] if wi + 1 < len(ch) else min(nxt, w["e"] + 0.35, end_lim)
                if e - s < 0.04:
                    continue
                txt = " ".join((HL if j == wi else (KEY if x["t"].strip("?!") in keys else "")) + x["t"] + r"{\r}"
                               for j, x in enumerate(ch))
                pop = r"{\fad(90,0)}" if wi == 0 else ""
                lines.append(f"Dialogue: 0,{ass_time(s)},{ass_time(e)},Cap,,0,0,0,,{pop}{txt}")
    return lines


def text_pop(t, f):
    d = f.get("dur", 1.4)
    txt = f["text"].replace("\n", r"\N")
    if f.get("style") == "banner":
        return f"Dialogue: 2,{ass_time(t)},{ass_time(t + d)},Banner,,0,0,0,,{{\\fad(220,260)}}{txt}"
    col = "&H0051C4F5&" if f.get("color") in ("yellow", "gold") else "&H00FFFFFF&"   # brand: white or soft gold
    x, y = f.get("pos", (W // 2, 230))
    return (f"Dialogue: 2,{ass_time(t)},{ass_time(t + d)},Pop,,0,0,0,,"
            f"{{\\pos({x},{y})\\c{col}\\fscx96\\fscy96\\t(0,260,\\fscx100\\fscy100)\\fad(220,280)}}{txt}")


# ---------------------------------------------------------------- audio beds

SFX_PEAK_DB = -24.0   # every SFX normalised to this peak before its cue volume (voice peaks sit around -3)


def norm_sfx(name):
    out = WORK / "sfx_norm" / f"{name}.wav"
    if out.exists():
        return out
    out.parent.mkdir(exist_ok=True)
    res = subprocess.run(["ffmpeg", "-i", f"sfx/{name}.mp3", "-af", "volumedetect", "-f", "null", "-"],
                         cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    peak = float(re.search(r"max_volume: (-?[\d.]+) dB", res.stderr).group(1))
    run(["ffmpeg", "-v", "error", "-y", "-i", f"sfx/{name}.mp3", "-af", f"volume={SFX_PEAK_DB - peak:.2f}dB",
         "-ar", str(SR), "-ac", "2", str(out.relative_to(ROOT))])
    return out


def build_sfx_bed(events, total):
    path = WORK / "sfx_bed.wav"
    if not events:
        run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"anullsrc=r={SR}:cl=stereo", "-t", f"{total:.3f}", str(path)])
        return path
    ins, fl = [], []
    for i, (t, name, vol, maxd) in enumerate(events):
        ins += ["-i", str(norm_sfx(name).relative_to(ROOT))]
        ms = int(t * 1000)
        fl.append(f"[{i}:a]aresample={SR},aformat=channel_layouts=stereo,atrim=0:{maxd},"
                  f"afade=t=out:st={max(maxd - min(0.25, maxd / 4), 0):.3f}:d={min(0.25, maxd / 4):.3f},volume={vol},adelay={ms}|{ms}[s{i}]")
    fl.append("".join(f"[s{i}]" for i in range(len(events))) +
              f"amix=inputs={len(events)}:normalize=0:dropout_transition=0,apad,atrim=0:{total:.3f}[out]")
    script = WORK / "sfx_filter.txt"
    script.write_text(";\n".join(fl), encoding="utf-8")
    run(["ffmpeg", "-v", "error", "-y", *ins, "-/filter_complex", str(script.relative_to(ROOT)),
         "-map", "[out]", str(path)])
    return path


MUSIC_UNDER_VOICE_DB = 22.0   # music sits this far under the creator's speech (before ducking) so words stay clear


def _rms_frames(path, hop=1600):
    import numpy as np
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-vn", "-ac", "1", "-ar", "16000", "-f", "s16le", "-"],
                         capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).astype(float) / 32768
    n = len(x) // hop
    return 20 * np.log10(np.sqrt((x[:n * hop].reshape(n, hop) ** 2).mean(1)) + 1e-9)


def music_gain_db(music_bed):
    """Calibrate the music to the actual voice level (user: 'make sure the music isn't too loud')."""
    import numpy as np
    v, m = _rms_frames(WORK / "base.mkv"), _rms_frames(music_bed)
    n = min(len(v), len(m))
    speech = v[:n] > -35
    gap = float(np.median(v[:n][speech] - m[:n][speech])) if speech.any() else MUSIC_UNDER_VOICE_DB
    gain = min(0.0, gap - MUSIC_UNDER_VOICE_DB)
    print(f"music: {gap:.1f} dB under the voice before calibration, applying {gain:+.1f} dB")
    return gain


def creator_boost(pieces, pad=0.06):
    """Match the creator's (quieter) mic to the women's level: measured gain, applied on his speech spans.

    Speaker tags come from diarize.py (pitch) in work/transcript_small.json. Returns (gain_db, output spans).
    """
    import numpy as np
    src = WORK / "transcript_small.json"
    if not src.exists():
        return 0.0, []
    segs = [s for s in json.load(open(src, encoding="utf-8")) if s.get("spk") in ("ME", "HER")]
    x = _raw_audio16()
    clips = [p for p in pieces if p["type"] == "clip" and p.get("speed", 1.0) == 1.0 and not p.get("mute")]
    lv = {"ME": [], "HER": []}
    spans = []
    for p in clips:
        for s in segs:
            a, b = max(s["start"], p["in"]), min(s["end"], p["out"])
            if b - a <= 0.05:
                continue
            seg = x[int(a * 16000):int(b * 16000)]
            if len(seg) >= 1600:
                fr = seg[:len(seg) // 1600 * 1600].reshape(-1, 1600)
                db = 20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9)
                lv[s["spk"]] += list(db[db > -45])
            if s["spk"] == "ME":
                spans.append([out_time(p, a) - pad, out_time(p, b) + pad])
    if not lv["ME"] or not lv["HER"]:
        return 0.0, []
    gain = float(np.clip(np.median(lv["HER"]) - np.median(lv["ME"]), 0, 12))
    spans.sort()
    merged = []
    for a, b in spans:
        if merged and a - merged[-1][1] < 0.15:
            merged[-1][1] = max(merged[-1][1], b)
        else:
            merged.append([max(a, 0), b])
    print(f"creator voice: {gain:+.1f} dB on {len(merged)} speaking stretches (to match her level)")
    return gain, merged


def level_voice(pieces, ramp=0.02):
    """work/voice_leveled.wav: base audio with creator_boost's gain on his speaking spans (20ms ramps)."""
    import numpy as np
    out = WORK / "voice_leveled.wav"
    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(WORK / "base.mkv"), "-vn", "-ac", "2", "-ar", str(SR),
                          "-f", "s16le", "-"], capture_output=True).stdout
    x = np.frombuffer(raw, dtype=np.int16).reshape(-1, 2).astype(np.float32)
    gain_db, spans = creator_boost(pieces)
    env = np.ones(len(x), dtype=np.float32)
    g, rn = 10 ** (gain_db / 20), int(ramp * SR)
    for a, b in spans:
        i, j = int(a * SR), min(int(b * SR), len(x))
        if j - i <= 2 * rn:
            continue
        env[i:j] = g
        env[i:i + rn] = np.linspace(1, g, rn)
        env[j - rn:j] = np.linspace(g, 1, rn)
    y = np.clip(x * env[:, None], -32768, 32767).astype(np.int16)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "s16le", "-ar", str(SR), "-ac", "2", "-i", "-", str(out)],
                   input=y.tobytes(), check=True)
    return out


def _raw_audio16():
    import numpy as np
    import wave
    with wave.open(str(WORK / "audio16k.wav")) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(float) / 32768


def build_music_bed(music, total):
    """music: list of {file, start, end, vol, [drops: [[a,b],...]]} on the output timeline."""
    path = WORK / "music_bed.wav"
    ins, fl = [], []
    for i, m in enumerate(music):
        ins += ["-stream_loop", "-1", "-i", m["file"]]
        d = m["end"] - m["start"]
        ms = int(m["start"] * 1000)
        mute = "".join(f",volume=enable='between(t,{a - m['start']:.2f},{b - m['start']:.2f})':volume=0"
                       for a, b in m.get("drops", []))
        fl.append(f"[{i}:a]aresample={SR},aformat=channel_layouts=stereo,atrim=0:{d:.3f},volume={m.get('vol', 0.12)}{mute},"
                  f"afade=t=in:d=0.8,afade=t=out:st={max(d - 1.2, 0):.3f}:d=1.2,adelay={ms}|{ms}[m{i}]")
    fl.append("".join(f"[m{i}]" for i in range(len(music))) +
              f"amix=inputs={len(music)}:normalize=0,apad,atrim=0:{total:.3f}[out]")
    script = WORK / "music_filter.txt"
    script.write_text(";\n".join(fl), encoding="utf-8")
    run(["ffmpeg", "-v", "error", "-y", *ins, "-/filter_complex", str(script.relative_to(ROOT)),
         "-map", "[out]", str(path)])
    return path


POP = [0.5, 0.78, 1.06, 1.1, 1.04, 1.0]   # per-frame scale for the pop-in


def overlay_seq(k, img_path, w, rot, d, border):
    """Pre-render a pop-in / fade-out overlay as a fixed-size PNG sequence (ffmpeg can't resize mid-stream)."""
    folder = WORK / "ov" / str(k)
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    im = Image.open(img_path).convert("RGBA")
    im = im.resize((w, round(im.height * w / im.width)), Image.LANCZOS)
    if border:
        im = ImageOps.expand(im, border=8, fill=(255, 255, 255, 255))
    big = im.resize((round(im.width * 1.1), round(im.height * 1.1)), Image.LANCZOS).rotate(rot, expand=True)
    cw, ch = big.width + 4, big.height + 4
    n = max(round(d * FPS), len(POP) + 1)
    for i in range(n):
        sc = POP[i] if i < len(POP) else 1.0
        fr = im.resize((max(1, round(im.width * sc)), max(1, round(im.height * sc))), Image.LANCZOS).rotate(rot, expand=True, resample=Image.BICUBIC)
        a = min(1.0, (n - i) / 5)
        if a < 1:
            fr.putalpha(fr.getchannel("A").point(lambda v: int(v * a)))
        canvas = Image.new("RGBA", (cw, ch))
        canvas.paste(fr, ((cw - fr.width) // 2, (ch - fr.height) // 2), fr)
        canvas.save(folder / f"{i:04d}.png")
    return folder



def clip_seq(k, name, w, d, radius=26, fade=7):
    """A muted gif-like reaction clip as a rounded, shadowed PNG sequence that fades in and out."""
    from PIL import ImageDraw, ImageFilter
    folder = WORK / "ov" / f"c{k}"
    shutil.rmtree(folder, ignore_errors=True)
    folder.mkdir(parents=True)
    src = ROOT / "clips" / f"{name}.mp4"
    total = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(src)],
                                 capture_output=True, text=True).stdout)
    start = max(total / 2 - d / 2, 0)
    run(["ffmpeg", "-v", "error", "-y", "-ss", f"{start:.2f}", "-t", f"{d:.2f}", "-i", str(src.relative_to(ROOT)),
         "-vf", f"fps={FPS},scale={w}:-2:flags=lanczos", str((folder / "raw_%04d.png").relative_to(ROOT))])
    frames = sorted(folder.glob("raw_*.png"))
    fw, fh = Image.open(frames[0]).size
    mask = Image.new("L", (fw, fh), 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, fw - 1, fh - 1], radius, fill=255)
    pad = 24
    shadow = Image.new("L", (fw + 2 * pad, fh + 2 * pad), 0)
    ImageDraw.Draw(shadow).rounded_rectangle([pad, pad + 6, pad + fw, pad + fh + 6], radius, fill=150)
    shadow = shadow.filter(ImageFilter.GaussianBlur(12))
    n = len(frames)
    for i, fp in enumerate(frames):
        a = min(1.0, (i + 1) / fade, (n - i) / fade)
        canvas = Image.new("RGBA", shadow.size, (0, 0, 0, 0))
        canvas.putalpha(shadow.point(lambda v: int(v * a)))
        fr = Image.open(fp).convert("RGBA")
        fr.putalpha(mask.point(lambda v: int(v * a)))
        canvas.alpha_composite(fr, (pad, pad))
        canvas.save(folder / f"{i:04d}.png")
        fp.unlink()
    return folder


# ---------------------------------------------------------------- main

SFX_MAX = {"crowd": 2.6, "impact": 1.6, "glitch": 0.9, "tension": 2.5, "whoosh": 1.0, "heart": 2.2,
           "joke": 1.6, "rizz": 1.8, "ding": 1.2}


def main():
    args = sys.argv[1:]
    edit_path = args[0] if args and not args[0].startswith("--") else "edit.json"
    edit = json.load(open(ROOT / edit_path, encoding="utf-8"))
    PIECES.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(exist_ok=True)

    pieces, total = expand(edit)
    chat = json.load(open(WORK / "chat_blur.json")) if (WORK / "chat_blur.json").exists() else []
    for p in pieces:
        a, b = (p["in"], p["out"]) if p["type"] == "clip" else (p.get("at", -1), p.get("at", -1) + 0.01)
        p["blurs"] = [c["box"] for c in chat if c["span"][0] < b and a < c["span"][1]]
    words = load_words()
    for p in pieces:
        if p["type"] != "clip":
            continue
        bad = [w for w in words if p["in"] <= (w["s"] + w["e"]) / 2 < p["out"] and PROFANE.match(re.sub(r"[^\w]", "", w["w"]))]
        p["mutes"] = [[max(w["s"] - 0.02, p["in"]), min(w["e"] + 0.02, p["out"])] for w in bad]
        p["fx"] = p.get("fx", []) + [{"at": a, "sfx": "beep_1000", "vol": 0.3, "max": round(b - a, 3), "_auto": 1} for a, b in p["mutes"]]
    print(f"{len(pieces)} pieces, runtime {total / 60:.1f} min")

    for i, p in enumerate(pieces):
        p["_file"] = render_piece(p)
        print(f"\r  piece {i + 1}/{len(pieces)}", end="", flush=True)
    print()
    (WORK / "concat.txt").write_text("".join(f"file 'pieces/{p['_file'].name}'\n" for p in pieces))
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", "work/concat.txt", "-c", "copy", "work/base.mkv"])

    # gather fx on the output timeline
    ass, sfx, overlays = [], [], []
    seen_fx = set()
    for p in pieces:
        for f in p.get("fx", []):
            fid = (id(f))
            if fid in seen_fx:
                continue
            seen_fx.add(fid)
            t = out_time(p, f["at"] if "at" in f else f["t"])
            if f.get("sfx"):
                for name in ([f["sfx"]] if isinstance(f["sfx"], str) else f["sfx"]):
                    maxd = f.get("max", SFX_MAX.get(name.split("_")[0], 1.5))
                    sfx.append((t + f.get("sfx_off", 0), name, f.get("vol", 0.8), maxd))
            if f.get("text"):
                txt = f["text"]
                emo = [e for e in EMOJI_FILES if e in txt]
                for e in emo:
                    txt = txt.replace(e, "")
                g = {**f, "text": txt.strip()}
                ass.append(text_pop(t, g))
                if emo:
                    banner = f.get("style") == "banner"
                    size = 82 if banner else 150
                    half = len(g["text"]) * size * 0.36 + (60 if banner else 40)
                    cx, cy = f.get("pos", (W // 2, 105 if banner else 330))
                    overlays.append((t, {"emoji": EMOJI_FILES[emo[0]], "dur": f.get("dur", 1.4),
                                         "w": 100 if banner else 150, "pos": (min(int(cx + half), W - 90), cy)}))
            if f.get("meme") or f.get("emoji") or f.get("clip"):
                overlays.append((t, f))
    for c in edit.get("text_cards", []):
        ass.append(text_pop(c["t"], c))

    ass_lines = captions(pieces, edit)
    (WORK / "captions.ass").write_text(ASS_HEAD + "\n".join(ass_lines + ass) + "\n", encoding="utf-8-sig")

    sfx_bed = build_sfx_bed(sfx, total)
    music_bed = build_music_bed(edit.get("music", []), total)
    music_db = music_gain_db(music_bed)

    # final pass
    ins = ["-i", "work/base.mkv", "-i", str(sfx_bed.relative_to(ROOT)), "-i", str(music_bed.relative_to(ROOT))]
    fl, last = [], "[0:v]"
    for k, (t, f) in enumerate(overlays):
        idx = 3 + k
        d = f.get("dur", 1.5)
        if f.get("clip"):
            w = f.get("w", 540)
            x, y = f.get("pos", (1560, 300))
            seq = clip_seq(k, f["clip"], w, d)
            ins += ["-framerate", str(FPS), "-i", str(seq.relative_to(ROOT) / "%04d.png")]
            fl.append(f"[{idx}:v]format=rgba,setpts=PTS-STARTPTS+{t:.3f}/TB[o{k}]")
            nxt = f"[v{k}]"
            # glides up 24px while fading in
            fl.append(f"{last}[o{k}]overlay=x={x}-w/2:y='{y}-h/2+24*max(0,1-(t-{t:.3f})/0.3)':eval=frame:"
                      f"eof_action=pass:enable='between(t,{t:.3f},{t + d:.3f})'{nxt}")
            last = nxt
            continue
        if f.get("meme"):
            img = next((ROOT / "memes").glob(f["meme"] + ".*"))
            w, border = f.get("w", 820), True
            x, y = f.get("pos", (W // 2, H // 2 - 40))
        else:
            img = ROOT / "emoji" / f"{f['emoji']}.png"
            w, border = f.get("w", 190), False
            x, y = f.get("pos", (1700, 300))
        seq = overlay_seq(k, img, w, f.get("rot", 0), d, border)
        ins += ["-framerate", str(FPS), "-i", str(seq.relative_to(ROOT) / "%04d.png")]
        fl.append(f"[{idx}:v]format=rgba,setpts=PTS-STARTPTS+{t:.3f}/TB[o{k}]")
        nxt = f"[v{k}]"
        fl.append(f"{last}[o{k}]overlay=x={x}-w/2:y={y}-h/2:eof_action=pass:"
                  f"enable='between(t,{t:.3f},{t + d:.3f})'{nxt}")
        last = nxt
    fl.append(f"{last}subtitles=work/captions.ass:fontsdir=fonts[vout]")
    # Audio is mixed in its own pass. Mixing it in the same run as the heavy video graph made ffmpeg drop
    # ~18s of audio (v7/v8 went out of sync in places); a finished PCM track can't be starved that way.
    voice = level_voice(pieces)   # creator's quieter mic lifted to her level
    audio_fl = [
        # gentle dialogue compression: tames loud laughs/shouts in the calls (a spike at 0:28 in v9)
        "[2:a]acompressor=threshold=-20dB:ratio=3:attack=5:release=200:makeup=1,asplit[voice][key]",
        f"[1:a]volume={music_db:.1f}dB[mus]",
        "[mus][key]sidechaincompress=threshold=0.02:ratio=10:attack=15:release=450[duck]",
        "[voice][0:a][duck]amix=inputs=3:normalize=0,apad=pad_dur=4,"
        f"loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000,atrim=0:{total:.3f}[aout]",
    ]
    (WORK / "audio_filter.txt").write_text(";\n".join(audio_fl), encoding="utf-8")
    final_audio = WORK / "final_audio.wav"
    run(["ffmpeg", "-v", "error", "-y", "-i", str(sfx_bed.relative_to(ROOT)), "-i", str(music_bed.relative_to(ROOT)),
         "-i", str(voice.relative_to(ROOT)), "-/filter_complex", "work/audio_filter.txt", "-map", "[aout]",
         "-c:a", "pcm_s16le", str(final_audio.relative_to(ROOT))])
    aidx = ins.count("-i")
    ins += ["-i", str(final_audio.relative_to(ROOT))]
    script = WORK / "final_filter.txt"
    script.write_text(";\n".join(fl), encoding="utf-8")

    name = edit.get("name", "monkey_longform")
    rng = []
    if "--preview" in args:
        i = args.index("--preview")
        a, b = float(args[i + 1]), float(args[i + 2])
        rng = ["-ss", str(a), "-to", str(b)]
        name += f"_preview_{int(a)}"
    out = OUT / f"{name}.mp4"
    run(["ffmpeg", "-v", "error", "-y", *ins, "-/filter_complex", str(script.relative_to(ROOT)),
         "-map", "[vout]", "-map", f"{aidx}:a", *rng, "-c:v", "libx264", "-preset", "medium", "-crf", "19",
         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart", str(out)])
    print("wrote", out)


if __name__ == "__main__":
    main()
