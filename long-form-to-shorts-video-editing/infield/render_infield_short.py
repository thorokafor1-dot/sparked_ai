"""Render one 9:16 short from raw vertical infield footage (phone POV, already 1080x1920 once rotated).

Spec (specs/<name>.json):
    {"source": "<night folder relative to repo>/raw/<clip>.mov",
     "words":  "<night>/work/<clip>_words.json",          # prep_night.py transcript (source seconds)
     "keep":   [[a, b], ...],                              # source ranges, in order; opener first
     "her":    [[a, b], ...],                              # source ranges where SHE is talking (caption colour)
     "sfx":    [[t, "sparkle" | "rizz_869", seg?, vol?]],  # just after a flirty line; name a file for the key twist
     "fixes":  {"WRONG": "RIGHT"},                         # caption word fixes (verified by ear)
     "drop":   [[a, b], ...],                              # source ranges never captioned (unverifiable words)
     "patch":  [[a, b, "VERIFIED WORDS"], ...],            # replace the transcript inside a span (heard by ear)
     "hold":   [[a, b, f], ...],                           # show a still of source frame f over a..b (swing, arm in lens)
     "push":   {"from": 1.5, "secs": 2.0, "fx": 1.0},      # opening punch-in on her, eases out (fx 1 = right edge)
     "later":  [i, ...],                                   # segment i follows a real time jump: dip + "LATER" tag
     "jcut":   {"video_from": t, "live": s, "still": f},   # opener audio over her turning to camera, then a held push
     "vsub":   {"i": [[a, b], ...]},                       # segment i's picture from other live footage (no freezes)
     "dip":    [i, ...],
     "notch":  [hz, ...],                                  # notch out background beeps/tones (measure the peak)
     "slowmo": {"i": {"song": "song_x", "from": 0.0, "speed": 0.5, "slowed": 0.9, "vol": 0.9}}}
                                                           # segment i = her reaction in slow-mo + slowed/reverbed song                                   # soft dip through black into segment i (after a cold-open hook)

One encode for everything (cuts, captions, SFX, loudness, endscreen), so nothing is re-compressed.
Writes output/<name>_vN.mp4, its .render.json sidecar, and work/<name>_vN.ass.

Usage: python render_infield_short.py specs/amanda.json [--version 1]
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
MONKEY = REPO / "long-form-to-shorts-video-editing" / "monkey-app-video-chat"
NIGHT_REF = REPO / "long-form-video-editing" / "infield-night-2026-04-17"   # shared fonts + SFX library
sys.path.insert(0, str(MONKEY))
from render_short import VIDEO_ENC, ENDSCREEN_SECS, ENDSCREEN_FADE, ENDSCREEN_PNG  # noqa: E402

W, H, FPS = 1080, 1920, 30
ME_Y, HER_Y = 1500, 1330          # caption bottom edges (safe zone ends at 1536)
# real flirting "drive it home" stings (user, 2026-10-08: TikTok-style rizz sounds after a flirty line; magic
# sparkles, harp and chimes all "missed the mark"). Generated with ElevenLabs sound effects (Starter plan = commercial
# licence) into long-form-video-editing/infield-night-2026-04-17/sfx/flirt_*.mp3. Best first.
# 2026-10-08 (user: "use the types of sound effects Jameer would actually use and rizz youtubers and tiktokers use"):
# the real meme rizz sounds come first (voicy.network, see sfx/catalog.txt). They come from meme/music audio, so a
# YouTube Content ID claim is possible; the ElevenLabs flirt_* stings are the royalty-free fallback.
SPARKLES = ["meme_rizz_bright", "meme_rizz", "meme_owen_wow", "meme_mmm_hmm", "meme_oh_la_la", "meme_whitetee", "meme_wowowow", "flirt_sax1", "flirt_wah", "flirt_sax2", "flirt_whistle", "flirt_mmm"]
BANNED_SFX = {"heart_2779", "heart_496", "rizz_2586"}
# each sound plays at most once per short (user, 2026-10-08: "do not repeat the same flirty sound effect too much")
HEART = "heart_2779"
SFX_PEAK_DB = -14.0               # stings must clearly land over the voice ("I still don't hear flirty sound effects")
SFX_VOL = {"sparkle": 0.7}
SFX_MAX = 2.4          # the whole sting
MASK = {"FUCK": "F*CK", "SHIT": "SH*T", "BITCH": "B*TCH", "NIGGAS": ""}
FONT = "Montserrat Thin ExtraBold"

ASS_HEAD = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {W}
PlayResY: {H}
WrapStyle: 2
ScaledBorderAndShadow: yes

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Cap,{FONT},74,&H00FFFFFF,&H00FFFFFF,&H00141414,&H80000000,0,0,0,0,100,100,1,0,1,5,2,2,60,60,0,1
Style: Tag,{FONT},56,&H00FFFFFF,&H00FFFFFF,&H00141414,&H80000000,0,0,0,0,100,100,6,0,1,4,2,8,60,60,0,1
Style: CapHer,{FONT},70,&H00C4A1F7,&H00C4A1F7,&H00141414,&H80000000,0,0,0,0,100,100,1,0,1,5,2,2,60,60,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
RNN = (HERE / "models" / "cb.rnnn").relative_to(REPO).as_posix()   # RNNoise speech model (GregorR/rnnoise-models)
HL, HL_HER = r"{\c&H0051C4F5&}", r"{\c&H00FFFFFF&}"   # active word: gold for him, white for her


def ass_time(t):
    t = max(t, 0)
    return f"{int(t // 3600)}:{int(t % 3600 // 60):02d}:{t % 60:05.2f}"


def clean(w):
    return re.sub(r"[^\w'?!$%]", "", w).upper()


CAP_SPANS = []   # output (start, end) of every captioned word, filled by captions(); voice memes must not overlap
SPEED = {}   # segment index -> playback speed (slow-mo rizz moments), filled from the spec in main()


def out_time(keep, t, seg=None):
    """Source time -> output time, or None when t falls in a cut. seg pins the segment index: a cold-open hook
    replays footage that appears again later, so a source time can map to two output times."""
    acc = 0.0
    for i, (a, b) in enumerate(keep):
        sp = SPEED.get(i, 1.0)
        if (seg is None or seg == i) and a <= t <= b:
            return acc + (t - a) / sp
        acc += (b - a) / sp
    return None


def in_any(spans, t):
    return any(a <= t < b for a, b in spans)


def captions(spec, keep):
    segs = json.loads((REPO / spec["words"]).read_text(encoding="utf-8"))
    fixes = {k.upper(): v.upper() for k, v in spec.get("fixes", {}).items()}
    patches = spec.get("patch", [])
    # any overlap drops the original word: a mid-point test leaked a long-smeared "AMANDA?" into amanda_v3
    src = [w for g in segs for w in g.get("words", [])
           if not any(w["s"] < pb and w["e"] > pa for pa, pb, _ in patches)]
    for pa, pb, text in patches:   # verified words; "WORD@812.4" pins a start time, the rest spread evenly
        toks = [(t.split("@")[0], float(t.split("@")[1]) if "@" in t else None) for t in text.split()]
        step = (pb - pa) / len(toks)
        starts = [s if s is not None else pa + i * step for i, (_, s) in enumerate(toks)]
        for i, (t, _) in enumerate(toks):
            end = min(starts[i + 1] - 0.02 if i + 1 < len(toks) else pb, starts[i] + 0.8)
            src.append({"w": t, "s": starts[i], "e": max(end, starts[i] + 0.05)})
    src.sort(key=lambda w: w["s"])
    lines = []
    for si, (a, b) in enumerate(keep):
        if si in SPEED:   # slow-mo rizz moment: the song plays, nobody is talking
            continue
        ws = []
        for g in [{"words": src}]:
            for w in g.get("words", []):
                mid = (w["s"] + w["e"]) / 2
                if not (a - 0.06 <= w["s"] < b - 0.05) or in_any(spec.get("drop", []), mid):
                    continue
                t = fixes.get(clean(w["w"]), clean(w["w"]))
                t = MASK.get(t.strip("?!"), t)
                if t:
                    ws.append({"t": t, "s": out_time(keep, max(w["s"], a), si), "e": out_time(keep, min(w["e"], b), si),
                               # speaker from the word's onset: a last patched word used to run to the span end,
                               # so its mid-point fell outside her range ("REALLY?" in his colour, amanda_v4)
                               "her": in_any(spec.get("her", []), w["s"] + 0.03)})
        chunks, cur = [], []
        for w in ws:   # 1-3 word groups, never across a speaker change, a pause or a question/exclamation
            if cur and (len(cur) == 3 or w["her"] != cur[-1]["her"] or w["s"] - cur[-1]["e"] > 0.35
                        or sum(len(x["t"]) for x in cur) + len(w["t"]) > 14 or cur[-1]["t"][-1:] in "?!"):
                chunks.append(cur)
                cur = []
            cur.append(w)
        if cur:
            chunks.append(cur)
        CAP_SPANS.extend((w["s"], w["e"]) for w in ws)
        end_lim = out_time(keep, b, si)
        for ci, ch in enumerate(chunks):
            nxt = chunks[ci + 1][0]["s"] if ci + 1 < len(chunks) else end_lim
            her = ch[0]["her"]
            for wi, w in enumerate(ch):
                s = w["s"]
                e = ch[wi + 1]["s"] if wi + 1 < len(ch) else min(nxt, w["e"] + 0.35, end_lim)
                if e - s < 0.04:
                    continue
                txt = " ".join(((HL_HER if her else HL) if j == wi else "") + x["t"] + r"{\r}" for j, x in enumerate(ch))
                pos = rf"{{\pos({W // 2},{HER_Y if her else ME_Y})}}" + (r"{\fad(90,0)}" if wi == 0 else "")
                lines.append(f"Dialogue: 0,{ass_time(s)},{ass_time(e)},{'CapHer' if her else 'Cap'},,0,0,0,,{pos}{txt}")
    return lines


_ASR = None


def sfx_has_vocals(path):
    """True when the clip has sung/spoken words (white-tee's lyrics played over dialogue at sammy_v14 0:20, user:
    "a distracting voice"). Vocal clips are only allowed in slow-mo moments, where nobody is talking."""
    global _ASR
    if _ASR is None:
        from faster_whisper import WhisperModel
        _ASR = WhisperModel("small", device="cpu", compute_type="int8")
    segs, _ = _ASR.transcribe(str(path), vad_filter=False, condition_on_previous_text=False)
    return any(len(g.text.split()) >= 1 and g.no_speech_prob < 0.5 for g in segs)


def norm_sfx(name, work):
    out = work / "sfx_norm" / f"{name}.wav"
    src = NIGHT_REF / "sfx" / f"{name}.mp3"
    assert name not in BANNED_SFX, f"SFX {name} is banned (user, 2026-10-08)"
    if out.exists():
        return out
    out.parent.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["ffmpeg", "-i", str(src), "-af", "volumedetect", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    peak = float(re.search(r"max_volume: (-?[\d.]+) dB", r.stderr).group(1))
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(src), "-af", f"volume={SFX_PEAK_DB - peak:.2f}dB",
                    "-ar", "48000", "-ac", "2", str(out)], check=True)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("spec")
    ap.add_argument("--version", type=int, default=1)
    a = ap.parse_args()
    spec_p = Path(a.spec).resolve()
    spec = json.loads(spec_p.read_text(encoding="utf-8"))
    name = spec_p.stem
    work, outd = HERE / "work", HERE / "output"
    work.mkdir(exist_ok=True)
    outd.mkdir(exist_ok=True)
    keep = spec["keep"]
    assert all(b > a for a, b in keep), "every keep range needs end > start"
    slow = {int(k): v for k, v in spec.get("slowmo", {}).items()}
    SPEED.clear()
    SPEED.update({i: v.get("speed", 0.5) for i, v in slow.items()})
    body = sum((b - a) / SPEED.get(i, 1.0) for i, (a, b) in enumerate(keep))

    later = set(spec.get("later", []))   # segment indices that start after a real time jump
    tags = [f"Dialogue: 1,{ass_time(out_time(keep, keep[i][0], i) + 0.1)},{ass_time(out_time(keep, keep[i][0], i) + 1.4)},"
            rf"Tag,,0,0,0,,{{\pos({W // 2},300)}}{{\fad(150,200)}}LATER" for i in sorted(later)]
    ass = work / f"{name}_v{a.version}.ass"   # per version: the sidecar of an older render must keep its own captions
    ass.write_text(ASS_HEAD + "\n".join(captions(spec, keep) + tags) + "\n", encoding="utf-8")

    src = str(REPO / spec["source"])
    ins, fl = [], []
    holds = [list(h) for h in spec.get("hold", [])]
    extras = []                                  # (start, dur) of extra video inputs, appended after the segments
    for i, (s, e) in enumerate(keep):
        ins += ["-ss", f"{s:.3f}", "-t", f"{e - s:.3f}", "-i", src]
    jcut = spec.get("jcut")
    if jcut:   # opener said while the camera is still off her: his audio runs from keep[0][0], the picture
        # starts where she turns to camera (video_from) for `live` seconds, then holds `still` with a slow push
        s0, e0 = keep[0]
        holds.append([s0 + jcut["live"], e0, jcut["still"]])
    # pure background tones (store scanner beep at 1523 Hz + harmonic under sammy's opener; find it as the bin that
    # stays loud across STFT frames, not the loudest FFT peak, which is a voice harmonic, user: "a weird sound effect
    # after we're looking for"): narrow notches leave the voice alone
    notch = "".join(f"bandreject=f={f}:width_type=h:w=60,bandreject=f={f}:width_type=h:w=60," for f in spec.get("notch", []))
    # phone mic in a mall: RNNoise speech denoise at full strength (80% let the hiss back, sammy_v21) + light FFT
    # cleanup + de-click + de-ess, run ONCE over the whole span the short uses (no cold restarts = no dropouts)
    clean_t0 = max(0.0, min(a for a, _ in keep) - 2.0)
    clean_t1 = max(b for _, b in keep) + 2.0
    chain = (f"highpass=f=90,adeclick,arnndn=m={RNN},afftdn=nf=-40:nr=12,{notch}"
             f"deesser=i=1:m=0.5:f=0.5:s=o,highshelf=f=5000:g=-4")
    import hashlib
    tag = hashlib.md5(f"{spec['source']}|{clean_t0}|{clean_t1}|{chain}".encode()).hexdigest()[:10]
    clean_wav = work / f"clean_{tag}.wav"
    if not clean_wav.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-ss", f"{clean_t0:.3f}", "-t", f"{clean_t1 - clean_t0:.3f}",
                        "-i", src, "-vn", "-af", chain, "-ar", "48000", "-ac", "2", str(clean_wav)], cwd=REPO, check=True)
    for i, (s, e) in enumerate(keep):
        d = e - s
        base = f"fps={FPS},scale={W}:{H}:flags=lanczos,setsar=1"
        vin = i
        if jcut and i == 0:
            vin = len(keep) + len(extras)
            extras.append((jcut["video_from"], d))
        seg_holds = sorted(h for h in holds if s <= h[0] < h[1] <= e + 0.01)
        vparts = spec.get("vsub", {}).get(str(i))
        if vparts:   # picture from other LIVE footage of her (his line said while the camera was off her), no freeze
            labels = ""
            for q, (va, vb) in enumerate(vparts):
                j = len(keep) + len(extras)
                extras.append((va, vb - va))
                fl.append(f"[{j}:v]{base},setpts=PTS-STARTPTS[x{i}_{q}]")
                labels += f"[x{i}_{q}]"
            got = sum(vb - va for va, vb in vparts)
            assert abs(got - d) < 0.15, f"vsub for segment {i} covers {got:.2f}s, audio is {d:.2f}s"
            fl.append(f"{labels}concat=n={len(vparts)}:v=1:a=0,tpad=stop_mode=clone:stop_duration=0.2,"
                      f"trim=duration={d:.3f}[r{i}]")
            src_lbl, vf = f"[r{i}]", "null"
        elif seg_holds:   # camera off her (swing, arm in lens): show a still of her frame while the audio keeps playing
            fl.append(f"[{vin}:v]{base},split={len(seg_holds) + 1}" + "".join(f"[p{i}_{q}]" for q in range(len(seg_holds) + 1)))
            parts, cur = "", s
            for q, (ha, hb, hf) in enumerate(seg_holds):
                if ha - cur > 0.02:
                    fl.append(f"[p{i}_{q}]trim={cur - s:.3f}:{ha - s:.3f},setpts=PTS-STARTPTS[l{i}_{q}]")
                    parts += f"[l{i}_{q}]"
                else:
                    fl.append(f"[p{i}_{q}]nullsink")
                j = len(keep) + len(extras)
                extras.append((hf, 0.2))
                fl.append(f"[{j}:v]{base},trim=end_frame=1,setpts=PTS-STARTPTS,"
                          f"tpad=stop_mode=clone:stop_duration={hb - ha:.3f},trim=duration={hb - ha:.3f}[f{i}_{q}]")
                parts += f"[f{i}_{q}]"
                cur = hb
            last = len(seg_holds)
            if e - cur > 0.02:
                fl.append(f"[p{i}_{last}]trim={cur - s:.3f}:{d:.3f},setpts=PTS-STARTPTS[l{i}_{last}]")
                parts += f"[l{i}_{last}]"
            else:
                fl.append(f"[p{i}_{last}]nullsink")
            fl.append(f"{parts}concat=n={parts.count('[')}:v=1:a=0[r{i}]")
            src_lbl, vf = f"[r{i}]", "null"
        else:
            src_lbl, vf = f"[{vin}:v]", base
        if jcut and i == 0:   # slow 1.0 -> 1.08 push on the held frame so it reads as a deliberate beat
            live, rest = jcut["live"], d - jcut["live"]
            vf += (f",scale={W * 2}:{H * 2}:flags=lanczos,zoompan=z='1+0.08*max(0,it-{live})/{rest:.3f}':"
                   f"x='(iw-iw/zoom)/2':y='(ih-ih/zoom)/2':d=1:s={W}x{H}:fps={FPS}")
        push = spec.get("push")
        if push and i == 0:   # opening punch-in on her that eases out to the full frame (smoothstep)
            z0, secs, fx = push["from"], push["secs"], push.get("fx", 0.5)
            p = f"min(1,it/{secs})"
            ease = f"({p})*({p})*(3-2*({p}))"
            vf += (f",scale={W * 2}:{H * 2}:flags=lanczos,zoompan=z='{z0}-({z0 - 1})*{ease}':"
                   f"x='(iw-iw/zoom)*({fx}+(0.5-{fx})*{ease})':y='(ih-ih/zoom)/2':d=1:s={W}x{H}:fps={FPS}")
        dips = later | set(spec.get("dip", []))   # dip: same soft dip through black, no "LATER" tag
        if i in dips:
            vf += ",fade=t=in:d=0.25"
        if i + 1 in dips:
            vf += f",fade=t=out:st={d - 0.25:.3f}:d=0.25"
        if i in slow:   # rizz moment: her reaction in smooth slow-mo, a slowed + reverbed song over it
            cfg, sp = slow[i], SPEED[i]
            od = d / sp
            vf += (f",setpts=PTS/{sp},minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:vsbmc=1,"
                   f"trim=duration={od:.3f},setpts=PTS-STARTPTS")
            fl.append(f"{src_lbl}{vf},format=yuv420p[v{i}]")
            j = len(keep) + len(extras)
            extras.append(("song", cfg))
            rate = cfg.get("slowed", 0.9)
            fl.append(f"[{j}:a]aresample=48000,aformat=channel_layouts=stereo,asetrate={round(48000 * rate)},"
                      f"aresample=48000,aecho=0.8:0.75:70|140|210:0.35|0.25|0.15,atrim=0:{od:.3f},"
                      f"apad=whole_dur={od:.3f},afade=t=in:d=0.12,afade=t=out:st={od - 0.7:.3f}:d=0.7,"
                      f"volume={cfg.get('vol', 0.9)}[a{i}]")
            continue
        # video and audio of every segment must be EXACTLY d long: a frame of rounding on the video side made concat
        # pad the audio with 40-90 ms of dead silence at every cut (sammy_v19-v21, gate infield-audio-dropouts)
        fl.append(f"{src_lbl}{vf},tpad=stop_mode=clone:stop_duration=0.2,trim=duration={d:.4f},setpts=PTS-STARTPTS,"
                  f"format=yuv420p[v{i}]")
        # voice comes from the pre-cleaned continuous track (clean_voice): denoising each segment separately made
        # RNNoise restart cold at every cut and drop to dead silence for 50-90 ms (user, sammy_v19: "a weird sound
        # after did I catch your name")
        j = len(keep) + len(extras)
        extras.append(("clean", (s - clean_t0, d)))
        fl.append(f"[{j}:a]aresample=48000,aformat=channel_layouts=stereo,apad,atrim=0:{d:.4f},asetpts=PTS-STARTPTS,"
                  f"afade=t=in:d=0.01,afade=t=out:st={d - 0.015:.3f}:d=0.015[a{i}]")
    for t0, dur in extras:
        if t0 == "clean":
            ins += ["-ss", f"{dur[0]:.3f}", "-t", f"{dur[1]:.3f}", "-i", str(clean_wav)]
        elif t0 == "song":
            song = NIGHT_REF / "sfx" / f"{dur['song']}.mp3"
            ins += ["-ss", f"{dur.get('from', 0):.3f}", "-t", "12", "-i", str(song)]
        else:
            ins += ["-ss", f"{t0:.3f}", "-t", f"{dur:.3f}", "-i", src]
    n = len(keep)
    fl.append("".join(f"[v{i}][a{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=1[vc][ac]")
    # phone mic in a mall: cut rumble, light broadband denoise, then the mix is levelled to -14 LUFS below
    # room tone: full-strength RNNoise leaves the pauses dead silent (sammy_v22: 250 ms at 0:13.2, a glitchy cut-out),
    # weaker settings bring the hiss back (v21). A faint smooth brown-noise bed (~-55 dBFS rms; -70 got zeroed by the AAC encoder; all rumble, no hiss) keeps
    # pauses sounding like a room. Gates: infield-audio-dropouts + infield-hiss.
    fl.append("anoisesrc=color=brown:amplitude=0.01:r=48000,aformat=channel_layouts=stereo,lowpass=f=900[rt]")
    fl.append("[ac][rt]amix=inputs=2:duration=first:normalize=0[voice]")

    k = n + len(extras)
    assert len(spec.get("sfx", [])) <= len(SPARKLES), (
        f"{len(spec['sfx'])} SFX but only {len(SPARKLES)} distinct smooth sounds; each may play once per short")
    named = {k for _, k, *_ in spec.get("sfx", []) if k in SPARKLES}
    sparkles = iter([n for n in SPARKLES if n not in named])   # auto picks skip sounds the spec names itself
    sfx_lbls, sfx_marks = [], []
    for t, kind, *rest in spec.get("sfx", []):   # optional 3rd field: segment index (for replayed footage)
        at = out_time(keep, t, rest[0] if rest else None)
        assert at is not None, f"SFX at {t} is outside the kept footage"
        assert kind != "heart", "the heartbeat SFX is banned (user, 2026-10-08); use a sparkle"
        sfx_name = kind if kind in SPARKLES else next(sparkles)   # naming a file ("flirt_sax1") pins it (the key twist)
        f = norm_sfx(sfx_name, work)
        if sfx_has_vocals(NIGHT_REF / "sfx" / f"{sfx_name}.mp3"):   # voice meme: only into a gap nobody talks in
            clip_len = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of",
                                             "csv=p=0", str(f)], capture_output=True, text=True).stdout)
            # a word STARTING inside the clip is a clash (padded word ends of the line it follows are not)
            clash = [(a0, b0) for a0, b0 in CAP_SPANS if at + 0.05 < a0 < at + min(clip_len, SFX_MAX) - 0.05]
            assert not clash, (f"voice meme {sfx_name} at {at:.2f}s talks over dialogue at {clash[0][0]:.2f}s "
                               f"(user: no voices over the conversation); move it into a pause")
        ins += ["-i", str(f)]
        ms = int(at * 1000)
        # never let a sound spill across a cut onto an unrelated line (user, 2026-10-08: the hook sparkle swelled
        # over the opener's "Excuse me" "like something is revealed"): fade it out by the end of its own segment
        si = rest[0] if rest and rest[0] is not None else next(i for i, (a0, b0) in enumerate(keep) if a0 <= t <= b0)
        seg_end = out_time(keep, keep[si][1], si)
        dur = SFX_MAX if si == len(keep) - 1 else min(SFX_MAX, seg_end - at + 0.1)
        assert dur >= 0.6, (f"SFX at {t} sits {seg_end - at:.2f}s before a cut; it would bleed into the next "
                            f"segment (move it or drop it)")
        fl.append(f"[{k}:a]atrim=0:{dur:.3f},afade=t=out:st={dur - 0.25:.3f}:d=0.25,volume={rest[1] if len(rest) > 1 else SFX_VOL["sparkle"]},"
                  f"adelay={ms}|{ms}[s{k}]")
        sfx_lbls.append(f"[s{k}]")
        sfx_marks.append(round(at, 2))
        k += 1
    if sfx_lbls:
        fl.append("[voice]" + "".join(sfx_lbls) + f"amix=inputs={1 + len(sfx_lbls)}:normalize=0:duration=first[mix]")
    else:
        fl.append("[voice]anull[mix]")
    fl.append("[mix]loudnorm=I=-14:TP=-1.5:LRA=11,aresample=48000[am]")

    # endscreen: the channel's brand card, slow push-in and fade (same as the video-chat shorts)
    frames = round(ENDSCREEN_SECS * FPS)
    ins += ["-loop", "1", "-framerate", str(FPS), "-t", f"{ENDSCREEN_SECS}", "-i", str(ENDSCREEN_PNG),
            "-f", "lavfi", "-t", f"{ENDSCREEN_SECS}", "-i", "anullsrc=r=48000:cl=stereo"]
    fl.append(f"[{k}:v]scale={W * 4}:{H * 4},zoompan=z='1+0.12*on/{frames}':x='iw/2-(iw/zoom/2)':"
              f"y='ih/2-(ih/zoom/2)':d={frames}:s={W}x{H}:fps={FPS},trim=duration={ENDSCREEN_SECS},"
              f"fade=t=out:st={ENDSCREEN_SECS - ENDSCREEN_FADE:.2f}:d={ENDSCREEN_FADE},format=yuv420p,setsar=1[ve]")
    fl.append(f"[{k + 1}:a]aformat=channel_layouts=stereo[ae]")
    fonts = (NIGHT_REF / "fonts").relative_to(REPO).as_posix()
    fl.append(f"[vc]subtitles={ass.relative_to(REPO).as_posix()}:fontsdir={fonts}[vs]")
    fl.append("[vs][am][ve][ae]concat=n=2:v=1:a=1[vout][aout]")

    script = work / f"{name}_filter.txt"
    script.write_text(";\n".join(fl), encoding="utf-8")
    out = outd / f"{name}_v{a.version}.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", *ins, "-/filter_complex", str(script.relative_to(REPO)),
                    "-map", "[vout]", "-map", "[aout]", *VIDEO_ENC, "-c:a", "aac", "-b:a", "192k",
                    "-movflags", "+faststart", str(out.relative_to(REPO))], cwd=REPO, check=True)

    # sidecar for the shorts gates (duration plan, no memes/cutaways/splits in raw infield)
    out.with_suffix(".render.json").write_text(json.dumps({
        "video": spec["source"], "keep": keep, "duration": round(body, 3),
        "sfx_at": sfx_marks, "memes": [], "cutaways": [], "splits": [], "captions": ass.relative_to(REPO).as_posix(),
        "slowmo_out": [[round(out_time(keep, keep[i][0], i), 2), round(out_time(keep, keep[i][1], i), 2)] for i in slow],
        # her speaking spans in output time, for the infield-caption-speaker gate
        "her_out": [[round(out_time(keep, max(ha, ka), si), 2), round(out_time(keep, min(hb, kb), si), 2)]
                    for ha, hb in spec.get("her", []) for si, (ka, kb) in enumerate(keep) if ha < kb and hb > ka]},
        indent=1), encoding="utf-8")
    print(f"wrote {out.relative_to(REPO)}  ({body:.1f}s + endscreen, {n} cuts, {len(sfx_marks)} SFX)")


if __name__ == "__main__":
    main()
