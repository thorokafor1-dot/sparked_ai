"""Measure the edit style of a YouTube video (an outlier, or one of our own renders).

Usage:
    python measure.py --type explainer <video id or URL> [...]      reference outliers, downloaded then deleted
    python measure.py --type explainer --local ../talking-head-infield/output/x.mp4   our own render

Writes measurements/<type>/<id>.json:
  cuts (scene changes), cuts/min in the hook (0-30s), setup (30-120s) and body, shot-length percentiles,
  words/min and dead-air share (from a whisper transcript), YouTube's most-replayed heatmap with the
  transcript and cut density at its peaks and dips, and a contact sheet (measurements/<type>/<id>.jpg)
  for coding the visual layer (captions, overlays, zooms, b-roll) by eye.
The same function measures our renders, so qa can hold them to the outlier bands.
"""

import argparse
import json
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
SCENE = 0.3  # ffmpeg scene score for a hard cut; slow push-ins and zooms stay under it
JUMP_MIN, JUMP_RATIO = 0.05, 8.0  # a jump cut: a spike this big and this many times the local median
# validated on ten_openers_v13 (62 real cuts): 95% recall, and 0 on a one-shot captioned explainer; the extra hits are title cards fading in/out,
# which are full-frame visual changes too, so read cuts_per_min as visual changes per minute
SECTIONS = [("hook", 0, 30), ("setup", 30, 120), ("body", 120, None)]
DEAD_AIR_GAP = 0.6  # a gap between words this long counts as dead air


def run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def download(vid: str, tmp: Path) -> tuple[Path, dict]:
    url = vid if vid.startswith("http") else f"https://www.youtube.com/watch?v={vid}"
    info = json.loads(run(["yt-dlp", "-J", "--skip-download", url]).stdout)
    r = run(["yt-dlp", "-f", "bv*[height<=480][vcodec^=avc1]+ba/bv*[height<=480][vcodec!^=av01]+ba/b[height<=480]", "--merge-output-format", "mp4",
             "-o", str(tmp / "v.%(ext)s"), url])
    # captions in their own call: a 429 on subtitles aborts a combined download, here it only means whisper
    run(["yt-dlp", "--skip-download", "--write-auto-subs", "--write-subs", "--sub-langs", "en-orig,en",
         "--sub-format", "json3", "--sleep-subtitles", "2", "-o", str(tmp / "v.%(ext)s"), url])
    files = [f for f in tmp.glob("v.*") if f.suffix != ".json3"]
    if not files:
        raise RuntimeError(f"download failed for {vid}: {r.stderr[-500:]}")
    return files[0], info


def duration(path: Path) -> float:
    return float(run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=nw=1:nk=1",
                      str(path)]).stdout)


def frame_scores(path: Path) -> tuple[np.ndarray, np.ndarray]:
    """Per-frame scene-change score (0..1); empty means nothing decoded.

    Scored on a blurred 96px frame so word-by-word captions don't register as cuts (at 320px a one-shot
    captioned explainer read as 7.5 cuts/min), while a jump cut still shifts the whole body.
    """
    out = run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-an", "-vf",
               "scale=96:-2,gblur=sigma=1.5,select='gte(scene,0)',metadata=print:key=lavfi.scene_score:file=-", "-f", "null", "-"]).stdout
    t = [float(x) for x in re.findall(r"pts_time:([\d.]+)", out)]
    v = [float(x) for x in re.findall(r"lavfi.scene_score=([\d.]+)", out)]
    if not v:
        raise RuntimeError(f"no frames decoded from {path.name}")
    return np.array(t[:len(v)]), np.array(v)


def scene_cuts(path: Path) -> list[float]:
    """Hard cuts plus same-framing jump cuts.

    A jump cut in a talking head keeps the background, so its scene score is small (~0.03-0.15),
    but it is a sharp one-frame spike over the near-zero frames around it; a push-in or gesture is not.
    """
    t, v = frame_scores(path)
    cuts, last = [], -1.0
    for i in range(len(v)):
        local = np.median(v[max(0, i - 15):i + 16])
        if v[i] >= SCENE or (v[i] >= JUMP_MIN and v[i] > JUMP_RATIO * max(local, 0.002)):
            if t[i] - last >= 0.25:  # one cut, not its neighbouring frames
                cuts.append(round(float(t[i]), 2))
                last = t[i]
    return cuts


def caption_words(path: Path) -> list[dict] | None:
    """Word timings from YouTube's own captions (json3, fetched with the video): seconds, not whisper's minutes."""
    subs = sorted(path.parent.glob("v*.json3"), key=lambda f: ("orig" not in f.name, f.name))
    if not subs:
        return None
    words = []
    for ev in json.loads(subs[0].read_text(encoding="utf-8")).get("events", []):
        t0 = ev.get("tStartMs", 0)
        segs = [sg for sg in ev.get("segs") or [] if sg.get("utf8", "").strip()]
        for k, sg in enumerate(segs):
            s = (t0 + sg.get("tOffsetMs", 0)) / 1000
            nxt = (t0 + segs[k + 1].get("tOffsetMs", 0)) / 1000 if k + 1 < len(segs) else s + 0.4
            for tok in sg["utf8"].split():
                words.append({"t": tok, "s": round(s, 2), "e": round(min(nxt, s + 0.6), 2)})
    return words or None


def transcribe(path: Path) -> list[dict]:
    from faster_whisper import WhisperModel

    model = WhisperModel("base", device="cpu", compute_type="int8")  # pace metrics only need word timing, not accuracy
    segs, _ = model.transcribe(str(path), word_timestamps=True, vad_filter=True)
    return [{"t": w.word.strip(), "s": round(w.start, 2), "e": round(w.end, 2)} for s in segs for w in s.words]


def contact_sheet(path: Path, dur: float, out: Path) -> None:  # noqa: D103
    # 24 evenly spaced frames, timestamp burned in, 6x4 grid
    n = 24
    fps = n / dur
    run(["ffmpeg", "-y", "-v", "error", "-i", str(path), "-vf",
         f"fps={fps:.6f},scale=320:-2,drawtext=fontfile='C\\:/Windows/Fonts/arial.ttf':text='%{{pts\\:hms}}':x=6:y=6:fontsize=18:fontcolor=white:box=1:boxcolor=black@0.6,"
         "tile=6x4", "-frames:v", "1", str(out)])
    if not out.exists():
        raise RuntimeError(f"contact sheet failed for {path.name}")


def section_stats(cuts: list[float], words: list[dict], dur: float) -> dict:
    out = {}
    for name, a, b in SECTIONS:
        b = dur if b is None else min(b, dur)
        if b <= a:
            continue
        mins = (b - a) / 60
        ws = [w for w in words if a <= w["s"] < b]
        out[name] = {"cuts_per_min": round(sum(a <= c < b for c in cuts) / mins, 1),
                     "words_per_min": round(len(ws) / mins, 1)}
    return out


def dead_air(words: list[dict], dur: float) -> float:
    gaps = [b["s"] - a["e"] for a, b in zip(words, words[1:]) if b["s"] - a["e"] >= DEAD_AIR_GAP]
    lead = words[0]["s"] if words else dur
    return round((sum(gaps) + (lead if lead >= DEAD_AIR_GAP else 0)) / dur, 3)


def heatmap_moments(heat: list[dict], words: list[dict], cuts: list[float]) -> dict:
    """Peaks and dips of the most-replayed curve (skipping the first 5%, which always peaks), with what was said."""
    if not heat:
        return {}
    vals = np.array([h["value"] for h in heat])
    skip = max(1, len(heat) // 20)

    def describe(i: int) -> dict:
        h = heat[i]
        said = " ".join(w["t"] for w in words if h["start_time"] <= w["s"] < h["end_time"])
        n_cuts = sum(h["start_time"] <= c < h["end_time"] for c in cuts)
        span = h["end_time"] - h["start_time"]
        return {"start": round(h["start_time"], 1), "end": round(h["end_time"], 1), "value": round(h["value"], 3),
                "cuts_per_min": round(n_cuts / span * 60, 1), "said": said[:300]}

    order = np.argsort(vals[skip:]) + skip
    return {"curve": [round(v, 3) for v in vals.tolist()],
            "first_minute_mean": round(float(vals[:max(1, int(len(vals) * 60 / heat[-1]['end_time']))].mean()), 3),
            "peaks": [describe(int(i)) for i in order[::-1][:4]],
            "dips": [describe(int(i)) for i in order[:3]]}


def measure(path: Path, info: dict, out_dir: Path, vid: str) -> dict:
    dur = duration(path)
    cuts = scene_cuts(path)
    words = caption_words(path)
    words_source = "youtube-captions" if words else "whisper-base"
    words = words or transcribe(path)
    shots = np.diff([0.0] + cuts + [dur])
    contact_sheet(path, dur, out_dir / f"{vid}.jpg")
    return {
        "id": vid, "local": "view_count" not in info, "title": info.get("title"), "channel": info.get("channel"), "views": info.get("view_count"),
        "upload_date": info.get("upload_date"), "duration": round(dur, 1),
        "cuts_total": len(cuts), "cuts_per_min": round(len(cuts) / dur * 60, 1),
        "sections": section_stats(cuts, words, dur),
        "shot_secs": {p: round(float(np.percentile(shots, q)), 2) for p, q in (("p10", 10), ("median", 50), ("p90", 90))},
        "longest_shot": round(float(shots.max()), 1),
        "words_per_min": round(len(words) / dur * 60, 1), "dead_air_share": dead_air(words, dur), "words_source": words_source,
        "chapters": [c.get("title") for c in info.get("chapters") or []],
        "heatmap": heatmap_moments(info.get("heatmap") or [], words, cuts),
        "cuts": cuts, "transcript_head": " ".join(w["t"] for w in words if w["s"] < 60),
    }


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--type", required=True, choices=["explainer", "infield", "video-chat"])
    p.add_argument("--local", action="store_true", help="arguments are local files (our renders), not YouTube ids")
    p.add_argument("--force", action="store_true", help="re-measure even if a measurement exists")
    p.add_argument("videos", nargs="+")
    args = p.parse_args()
    out_dir = HERE / "measurements" / args.type
    out_dir.mkdir(parents=True, exist_ok=True)
    for v in args.videos:
        vid = Path(v).stem if args.local else re.sub(r".*(?:v=|youtu\.be/)", "", v)[:11]
        out = out_dir / f"{vid}.json"
        if out.exists() and not args.force:
            print(f"skip {vid} (measured)")
            continue
        tmp = Path(tempfile.mkdtemp())
        try:
            path, info = (Path(v), {"title": Path(v).name}) if args.local else download(vid, tmp)
            m = measure(path, info, out_dir, vid)
        except Exception as e:  # one bad video shouldn't stop the batch
            print(f"FAIL {vid}: {e}")
            continue
        finally:
            shutil.rmtree(tmp, ignore_errors=True)
        out.write_text(json.dumps(m, indent=1, ensure_ascii=False), encoding="utf-8")
        h = m["heatmap"]
        print(f"{vid} {m['duration'] / 60:.1f}min cuts/min {m['cuts_per_min']} (hook {m['sections'].get('hook', {}).get('cuts_per_min')}) "
              f"shot median {m['shot_secs']['median']}s wpm {m['words_per_min']} dead air {m['dead_air_share']:.0%} "
              f"heatmap {'yes' if h else 'no'}")


if __name__ == "__main__":
    main()
