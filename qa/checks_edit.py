"""Checks for long-form edit decision lists (long-form-video-editing/*/edl.py) and their renderers.

Each rule here is a correction the user had to make by watching a render:
- infield uploads already carry burned-in word captions, so our own captions on clips doubled the text
- clips ran past her first response into brush-offs and small talk (the video is about openers)
- the hook ran long / wasn't an actual opener moment
- the endscreen held for 15s and bled retention
- the talking head's camera audio slipped in instead of the synced external mic
"""
from __future__ import annotations

import json
import re
import runpy
import sys
from pathlib import Path

from checks import check, read_text

EDL_GLOB = ["long-form-video-editing/*/edl.py"]
RENDER_GLOB = ["long-form-video-editing/*/render.py"]

MAX_CLIP_SECS = 9.0  # opener line + her first response; anything longer is conversation, not the opener
MAX_HOOK_SECS = 6.0  # cold open: the opener and her reaction, then straight into the video
MAX_TAIL_SECS = 1.2  # a clip may hold on her reaction this long after the last word, no longer
ENDSCREEN_RANGE = (5.0, 10.0)  # YouTube end-screen elements need >= 5s; past ~10s viewers just leave


@check("edl-openers", level="fast", exts={".py"}, paths=EDL_GLOB)
def edl_openers(path: Path) -> list[str]:
    sys.path.insert(0, str(path.parent))
    try:
        ns = runpy.run_path(str(path))
    except Exception as exc:  # a broken EDL is itself the problem
        return [f"edl.py failed to load: {exc}"]
    finally:
        sys.path.remove(str(path.parent))
    problems = []
    for i, seg in enumerate(ns.get("EDL", [])):
        src = seg.get("src")
        if src in ("th", "endscreen", "sting"):
            continue
        label = seg.get("label") or f"#{seg.get('num', '?')} clip ({src})"
        if seg.get("caption"):
            problems.append(f"{label}: caption set on an infield clip; the uploads already have burned-in "
                            f"captions, so this doubles the text (use top_label if a label is really needed)")
        start, end = seg.get("start"), seg.get("end")
        if start is None or end is None:
            problems.append(f"{label}: missing start/end")
            continue
        dur = end - start
        limit = MAX_HOOK_SECS if seg.get("label") == "hook" else MAX_CLIP_SECS
        if dur > limit:
            problems.append(f"{label}: {dur:.1f}s is longer than {limit:.0f}s; end the clip right after her first "
                            f"response (no brush-offs, no follow-up conversation)")
    # the same footage shown twice reads as filler; allowed only when marked with repeats="<which item>"
    clips = [s for s in ns.get("EDL", []) if s.get("src") not in ("th", "endscreen", "sting") and s.get("start") is not None]
    for i, a in enumerate(clips):
        for b in clips[i + 1:]:
            if a["src"] == b["src"] and a["start"] < b["end"] and b["start"] < a["end"] \
                    and not (a.get("repeats") or b.get("repeats")):
                problems.append(f"{a['src']} {a['start']}-{a['end']} and {b['start']}-{b['end']} overlap: the same "
                                f"footage plays twice; pick different moments or mark the repeat with repeats=")
    # a clip should end on a word (her response), not trail into dead air or a camera pan
    for seg in clips:
        words_path = path.parent / "work" / f"infield_{seg['src']}_words.json"
        if not words_path.exists():
            continue
        words = json.loads(words_path.read_text(encoding="utf-8"))
        spoken = [w for w in words if seg["start"] <= w["start"] < seg["end"]]
        if spoken and seg["end"] - spoken[-1]["end"] > MAX_TAIL_SECS:
            problems.append(f"{seg['src']} clip {seg['start']}-{seg['end']} ends {seg['end'] - spoken[-1]['end']:.1f}s "
                            f"after the last word; end it on her response, not on silence")
    if ns.get("EDL") and ns["EDL"][0].get("label") != "hook":
        problems.append("first EDL entry should be the hook clip (an actual opener + her reaction), labeled 'hook'")
    return problems


MAX_LEAD_IN_SECS = 0.1  # a talking-head piece may open this long before the voice, no more (else: audible inhale)


@check("talking-head-no-breath-starts", level="full", exts={".py"}, paths=EDL_GLOB)
def talking_head_no_breath_starts(path: Path) -> list[str]:
    """Every talking-head cut must open on the voice, not on the inhale before it (user heard breaths)."""
    render_py = path.parent / "render.py"
    text = read_text(render_py) or ""
    if "def voice_onset" not in text or "def split_on_pauses" not in text:
        return []  # not a mic-synced talking-head project
    sys.path.insert(0, str(path.parent))
    try:
        import importlib
        for mod in ("edl", "render"):
            sys.modules.pop(mod, None)
        edl, render = importlib.import_module("edl"), importlib.import_module("render")
        sil = render.talking_head_silences()
        problems = []
        for seg in edl.EDL:
            if seg.get("src") != "th":
                continue
            pieces = render.split_on_pauses(seg["start"], seg["end"], sil,
                                             seg.get("exact_start", False), seg.get("exact_end", False))
            for s, e in pieces:
                i = int(render.cam_to_mic(s) / 0.02)
                on = render.voice_onset(i, i + 75)
                lead = None if on is None else (on - i) * 0.02
                if lead is None or lead > MAX_LEAD_IN_SECS:
                    problems.append(f"talking-head piece at {s:.2f}s opens "
                                    f"{'with no voice' if lead is None else f'{lead:.2f}s before the voice'} "
                                    f"(audible inhale/dead air); trim to the voice onset")
        problems += [f"cut warning: {w}" for w in render.CUT_WARNINGS]
        return problems
    finally:
        sys.path.remove(str(path.parent))
        for mod in ("edl", "render", "brand_graphics"):
            sys.modules.pop(mod, None)


MAX_EDGE_SILENCE = 0.35  # dead air allowed at the head or tail of a talking-head piece


@check("talking-head-cut-quality", level="full", exts={".py"}, paths=["long-form-video-editing/*/edl*.py"])
def talking_head_cut_quality(path: Path) -> list[str]:
    """Runs the real cut planner and checks what the user kept catching by ear: cuts that end on 'and...',
    words played twice, and dead air piled up at cuts."""
    folder = path.parent
    if not (folder / "refine.py").exists():
        return []
    sys.path.insert(0, str(folder))
    try:
        import importlib
        for mod in ("render", "refine", "gaze", "sync_mic", path.stem):
            sys.modules.pop(mod, None)
        render = importlib.import_module("render")
        refine = importlib.import_module("refine")
        gaze = importlib.import_module("gaze")
        render.load_take(path.stem)
        sil = render.talking_head_silences()
        plan = {k: render.split_on_pauses(s["start"], s["end"], sil, s.get("exact_start", False), s.get("exact_end", False))
                for k, s in enumerate(render.EDL) if s["src"] == "th"}
        words = refine.load_words(render.CAPTION_WORDS)
        db, _ = render.mic_levels()
        level = lambda t: db[min(int(render.cam_to_mic(t) / 0.02), len(db) - 1)]
        voiced = lambda t: level(t) > render.SILENCE_DB + 6
        audible = lambda t: level(t) > render.SILENCE_DB + 3
        plan, _ = refine.refine(render.EDL, plan, words, gaze.Gaze(render.TALKING_HEAD), voiced,
                                getattr(render.TAKE, "CUT_OUT", ()), audible)
        problems, seen = [], set()
        order = [(k, p) for k in sorted(plan) for p in plan[k]]
        for idx, (k, (s, e)) in enumerate(order):
            ws = refine.words_in(words, s, e)
            for w in ws:
                key = w.get("id", round(w["start"], 2))
                if key in seen:
                    problems.append(f"word '{w['text']}' at {w['start']:.2f}s plays twice")
                seen.add(key)
            nxt = order[idx + 1] if idx + 1 < len(order) else None
            jumps = nxt is None or not (nxt[0] in (k, k + 1) and 0 <= nxt[1][0] - e < 3.0
                                         and not refine.words_in(words, e, nxt[1][0]))
            if ws and jumps and refine.norm(ws[-1]["text"]) in refine.DANGLING:
                problems.append(f"cut at {e:.2f}s ends on '{ws[-1]['text']}' and jumps away (sounds cut off)")
            if e - s < 0.4:
                problems.append(f"piece {s:.2f}-{e:.2f}s is only {e - s:.2f}s: a flash that reads as a glitch")
            # soft words can sit under the audibility threshold; dead air is measured only up to the nearest word
            head = min(next((t for t in refine.frange(s, e, 0.02) if audible(t)), e), ws[0]["start"] if ws else e) - s
            tail = e - max(next((t for t in reversed(refine.frange(s, e, 0.02)) if audible(t)), s),
                           (ws[-1]["start"] + 0.08) if ws else s)
            if head > MAX_EDGE_SILENCE or tail > MAX_EDGE_SILENCE + 0.05:
                problems.append(f"piece {s:.2f}-{e:.2f}s carries {head:.2f}s/{tail:.2f}s of dead air at its edges")
        return problems[:15]
    finally:
        sys.path.remove(str(folder))
        for mod in ("render", "refine", "gaze", "sync_mic", "brand_graphics", path.stem):
            sys.modules.pop(mod, None)


MAX_SYNC_MS = 45  # audio more than this off the lips is visible


@check("talking-head-lip-sync", level="full", exts={".py"}, paths=["long-form-video-editing/*/edl*.py"])
def talking_head_lip_sync(path: Path) -> list[str]:
    """Mic audio placed by the renderer must line up with the camera's own audio (user: 'lip syncing is off')."""
    folder = path.parent
    if not (folder / "render.py").exists() or "def cam_to_mic" not in (read_text(folder / "render.py") or ""):
        return []
    sys.path.insert(0, str(folder))
    try:
        import importlib
        import subprocess
        import numpy as np
        from scipy.signal import fftconvolve
        for mod in ("render", "sync_mic", path.stem):
            sys.modules.pop(mod, None)
        render, sync_mic = importlib.import_module("render"), importlib.import_module("sync_mic")
        render.load_take(path.stem)
        sr = sync_mic.SR

        def env(p, ss, dur):
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{ss:.3f}", "-t", str(dur), "-i", str(p), "-ac", "1",
                                  "-ar", str(sr), "-f", "f32le", "-"], capture_output=True).stdout
            return sync_mic.envelope(np.frombuffer(raw, np.float32))

        res = []
        ths = [s for s in render.EDL if s.get("src") == "th"]
        for seg in ths[:: max(1, len(ths) // 8)]:
            t = (seg["start"] + seg["end"]) / 2 - 6
            cam, mic = env(render.TALKING_HEAD, t - 1, 14), env(render.MIC, render.cam_to_mic(t), 12)
            if len(cam) <= len(mic) or len(mic) < sr:
                continue
            corr = fftconvolve(cam, mic[::-1], mode="valid")
            i = int(np.argmax(corr))
            score = corr[i] / (np.linalg.norm(mic) * np.linalg.norm(cam[i:i + len(mic)]) + 1e-9)
            if score > 0.25:
                res.append((i / sr - 1) * 1000)
        if len(res) >= 3 and abs(float(np.median(res))) > MAX_SYNC_MS:
            return [f"{path.name}: mic audio sits {np.median(res):+.0f} ms off the picture (median of {len(res)} "
                    f"checks); re-run sync_mic.py and make sure the mic is read from WAV"]
        return []
    finally:
        sys.path.remove(str(folder))
        for mod in ("render", "sync_mic", "brand_graphics", path.stem):
            sys.modules.pop(mod, None)


@check("render-mic-and-outro", level="fast", exts={".py"}, paths=RENDER_GLOB)
def render_mic_and_outro(path: Path) -> list[str]:
    text = read_text(path) or ""
    problems = []
    m = re.search(r"^ENDSCREEN_SECS\s*=\s*([\d.]+)", text, re.M)
    if m and not ENDSCREEN_RANGE[0] <= float(m.group(1)) <= ENDSCREEN_RANGE[1]:
        problems.append(f"ENDSCREEN_SECS = {m.group(1)}; keep it {ENDSCREEN_RANGE[0]:.0f}-{ENDSCREEN_RANGE[1]:.0f}s for retention")
    if "TALKING_HEAD" in text and "MIC" in text and not re.search(r'"-i",\s*str\(MIC\)', text):
        problems.append("talking-head audio must come from the synced external mic (MIC input), never the camera track")
    if "TALKING_HEAD" in text and "MIC" in text and not re.search(r"MIC = ensure_wav\(MIC\)", text):
        problems.append("the mic must be converted to WAV before seeking (ensure_wav): -ss into Sound Recorder .m4a "
                        "lands 0.26-0.8s early and broke lip sync on take 2")
    if "eval=frame" in text and re.search(r"crop=1920:1080:\(iw-1920\)", text):
        problems.append("an eval=frame zoom is cropped with (iw-1920)/2, which only sees the first frame's width: "
                        "the zoom drifts and jumps at the next cut (user: 'it pans then resets'); use zoom_vf()")
    if re.search(r"zoom_vf\([^\n]*CARD", text) or re.search(r"CARD_PUSH\s*\*", text):
        problems.append("title cards must stay still: zooming sharp card text shimmers (user: 'shaking like an "
                        "earthquake'); keep CARD_SECS under the 3s frozen-picture gate instead")
    if "TALKING_HEAD" in text and "refine(" not in text:
        problems.append("talking-head renders must run the refine.py cut planner (no cut-short words, no repeats, "
                        "no silent script glances)")
    if "TALKING_HEAD" in text and "subtitles=" not in text:
        problems.append("talking-head long-form must burn in captions for the talking-head parts (user: 'it's missing captions')")
    if re.search(r"crop=iw/\{?PUNCH", text):
        problems.append("hard punch-in zooms on jump cuts; Sparked brand uses smooth eased push-ins")
    return problems


MONKEY_EDIT_GLOB = ["long-form-video-editing/*/edit.json"]
CUT_SPEECH_DB = -44.0   # near side of the cut louder than this = not silence (room floor ~-54)
CUT_LOUD_DB = -20.0     # loud speech within 75 ms past the cut = the line carries on ("Filipi-"); quiet tails are handled by build snap()


@check("edit-no-cut-mid-speech", level="full", exts={".json"}, paths=MONKEY_EDIT_GLOB)
def edit_no_cut_mid_speech(path: Path) -> list[str]:
    """Monkey long-form cut lists: no clip may start or end while someone is mid-word.

    The user heard "I'm Filipi-" and "twenty-tw-" cut off (first_video v4): word timings end early, so the
    cut points are checked against the actual audio (work/audio16k.wav) instead.
    """
    import wave
    import numpy as np
    wav = path.parent / "work" / "audio16k.wav"
    if not wav.exists():
        return []
    edit = json.loads(read_text(path) or "{}")
    words = []
    for name in ("transcript.json", "transcript_small.json"):
        f = path.parent / "work" / name
        if f.exists():
            words += [x for sg in json.loads(f.read_text(encoding="utf-8")) for x in sg["words"]]
    problems = []
    with wave.open(str(wav)) as w:
        sr = w.getframerate()

        def db(t):
            if int(t * sr) >= w.getnframes():   # past the end of the source
                return -120.0
            w.setpos(max(int(t * sr), 0))
            x = np.frombuffer(w.readframes(int(0.025 * sr)), dtype=np.int16).astype(float) / 32768
            return 20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-9) if len(x) else -120.0

        def floor(t, span=8.0):
            """20th percentile of 25 ms RMS within +-span s: the room/bar noise level around the cut."""
            a = min(max(int((t - span) * sr), 0), max(w.getnframes() - 1, 0))
            w.setpos(a)
            x = np.frombuffer(w.readframes(int(2 * span * sr)), dtype=np.int16).astype(float) / 32768
            hop = int(0.025 * sr)
            fr = x[:len(x) // hop * hop].reshape(-1, hop)
            return float(np.percentile(20 * np.log10(np.sqrt((fr ** 2).mean(1)) + 1e-9), 20)) if len(fr) else -120.0

        clips = [q for q in edit.get("pieces", []) if q.get("type") == "clip"]
        for i, p in enumerate(clips):
            # Chopped = the utterance carries on through the cut: loud speech right on the far side of the cut
            # while the near side isn't silent. ("Fili|pino" has a syllable dip at the cut, so "quiet at the cut"
            # alone can't tell; what follows the cut can.)
            if p.get("cut_ok"):   # boundary checked by hand (e.g. a start in a short gap after someone else's word)
                continue
            for side, t in (("ends", p["out"]), ("starts", p["in"])):
                # a cut straight into the next bit of the same source is seamless (consecutive clips of one take)
                nb = clips[i + 1] if side == "ends" and i + 1 < len(clips) else clips[i - 1] if side == "starts" and i else None
                if nb and abs((nb["in"] if side == "ends" else nb["out"]) - t) < 0.05:
                    continue
                # a transcript word running through the cut is a chop whatever the room noise (bar audio hides it
                # from the level test: "Hold o|n" at 607.67, infield v4)
                cut_word = next((x for x in words if x["s"] < t - 0.06 and x["e"] > t + 0.06 and x["e"] - x["s"] < 1.2), None)
                if cut_word:
                    problems.append(f"clip {p['in']:.2f}-{p['out']:.2f} {side} inside the word \"{cut_word['w'].strip()}\" "
                                    f"({cut_word['s']:.2f}-{cut_word['e']:.2f}): move the cut to a gap between words")
                    continue
                if side == "ends":
                    far = max(db(t + k * 0.025) for k in range(3))          # 75 ms right after the end
                    near = max(db(t - (k + 1) * 0.025) for k in range(2))   # last 50 ms of the clip
                else:
                    far = max(db(t - (k + 1) * 0.025) for k in range(3))    # 75 ms right before the start
                    near = max(db(t + k * 0.025) for k in range(2))         # first 50 ms of the clip
                # "not silence" is judged against the local noise floor: in a loud bar (infield, floor up to -26 dB)
                # the fixed room threshold (-44) counted crowd and music as speech on every cut
                near_db = max(CUT_SPEECH_DB, floor(t) + 10)
                if far > max(CUT_LOUD_DB, floor(t) + 14) and near > near_db:
                    problems.append(f"clip {p['in']:.2f}-{p['out']:.2f} {side} mid-utterance (speech continues at "
                                    f"{far:.0f} dB right past the cut): a word or sentence gets chopped; "
                                    f"move the cut to where the line finishes (build_edit.py snap())")
    return problems[:12]


INFIELD_EDIT_GLOB = ["long-form-video-editing/infield-night-*/edit.json"]


@check("raw-infield-format", level="fast", exts={".json"}, paths=INFIELD_EDIT_GLOB)
def raw_infield_no_teaser(path: Path) -> list[str]:
    """Raw infield long-forms open straight on the first opener: no highlight teaser, no brand sting, no teaser
    bars (user, 2026-10-05: "I don't want any intro teaser for raw infield footage type of videos")."""
    import json
    edit = json.loads(path.read_text(encoding="utf-8"))
    problems = []
    pieces = edit.get("pieces", [])
    n = sum(1 for p in pieces if p.get("teaser"))
    if n:
        problems.append(f"{n} teaser clip(s): raw infield videos have no intro teaser (set TEASER = False)")
    if any(p.get("type") == "cut" and p.get("clip") == "brand_sting" for p in pieces):
        problems.append("brand_sting piece: only used to bridge a teaser, raw infield opens on the first opener")
    if edit.get("teaser_bars"):
        problems.append("teaser_bars set: raw infield has no cold open to mark")
    # no meme reaction cutaways in raw infield (user, 2026-10-05); flirty SFX carry the reactions instead
    memes = sorted({p["clip"] for p in pieces if p.get("type") == "cut"
                    and p.get("clip") not in ("tv_glitch", "brand_outro_end", "brand_outro")})
    if memes:
        problems.append(f"meme cutaways {memes}: raw infield uses flirty SFX, not memeclips (USE_CUTAWAYS = False)")
    # no TV glitch between approaches (user, 2026-10-05: "this is not monkey app"): a dip through black instead
    if any(p.get("type") == "cut" and p.get("clip") == "tv_glitch" for p in pieces):
        problems.append("tv_glitch transition: Monkey App only; raw infield joins approaches with a dip to black (DIP)")
    return problems
