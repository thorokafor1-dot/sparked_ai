"""Build raw/raw.mkv: the kept approach ranges of the night, back to back, on one timeline.

Video is the phone footage (vertical 1080x1920, 30 fps, h264); audio is the synced Wireless GO mic from
work/<clip>_mic.wav (prep_night.py), never the phone audio. The Monkey long-form tools (transcribe, diarize,
words.py, build_edit.py, render.py) then run on raw/raw.mkv unchanged.

raw/segments.json maps every combined-timeline range back to its clip and clip time.
Usage: python build_source.py   (segments are cached; edit SEGMENTS and re-run)
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
sys.path.insert(0, str(ROOT.parent / "infield-nights"))

# (label, clip stem, clip in, clip out, pre_roll): pre_roll = seconds of mic before the clip started,
# shown over the clip's first frame (approach B's opener was said before the phone started recording)
SEGMENTS = [
    ("A", "2026-04-17_205512", 0.0, 550.0, 0),
    ("B", "2026-04-17_210959", 0.0, 356.4, 6.0),
    ("C", "2026-04-17_212239", 85.0, 570.0, 0),
    ("D", "2026-04-17_214012", 160.0, 370.0, 0),
    ("E", "2026-04-17_214012", 665.0, 1050.0, 0),
    ("F", "2026-04-17_214012", 1160.0, 1630.0, 0),
    # F's walk-up and opener sit just before F's range; appended at the end so no existing source time shifts
    ("F0", "2026-04-17_214012", 1130.0, 1162.0, 0),
]
FPS, SR = 30, 48000


def run(cmd):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(r.stderr[-2000:])


def pre_roll_wav(stem, secs, out):
    from prep_night import MicTimeline
    import numpy as np
    sync = {s["clip"]: s for s in json.loads((ROOT / "work" / "sync.json").read_text())}[stem + ".mov"]
    x = MicTimeline(ROOT).slice(sync["mic_start"] - secs, secs, SR)
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1", "-i", "-",
                    "-c:a", "pcm_s24le", str(out)], input=x.astype(np.float32).tobytes(), check=True)


def main():
    seg_dir = ROOT / "work" / "source"
    seg_dir.mkdir(parents=True, exist_ok=True)
    files, table, t = [], [], 0.0
    for label, stem, a, b, pre in SEGMENTS:
        out = seg_dir / f"{label}_{stem}_{a:.0f}_{b:.0f}_{pre:.0f}.mkv"
        n = round((b - a + pre) * FPS)
        if not out.exists():
            mic = ROOT / "work" / f"{stem}_mic.wav"
            ains = ["-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", str(mic)]
            af = "[1:a]"
            if pre:
                pw = seg_dir / f"{label}_pre.wav"
                pre_roll_wav(stem, pre, pw)
                ains = ["-i", str(pw)] + ains
                af = "[1:a][2:a]concat=n=2:v=0:a=1,"
            else:
                af += "anull,"
            vf = (f"[0:v]fps={FPS},scale=1080:1920,setsar=1"
                  + (f",tpad=start_duration={pre}:start_mode=clone" if pre else "") + "[v]")
            tmp = out.with_suffix(".part.mkv")
            run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", f"raw/{stem}.mov", *ains,
                 "-filter_complex", f"{vf};{af}aformat=sample_rates={SR}:channel_layouts=stereo,"
                 f"apad,atrim=end_sample={round(n / FPS * SR)}[a]",
                 "-map", "[v]", "-map", "[a]", "-frames:v", str(n),
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p",
                 "-c:a", "pcm_s16le", str(tmp)])
            tmp.replace(out)
            print("built", out.name, flush=True)
        files.append(out)
        d = n / FPS
        table.append({"label": label, "clip": stem, "start": round(t, 3), "end": round(t + d, 3),
                      "clip_in": a, "pre_roll": pre})
        t += d
    (ROOT / "work" / "source_concat.txt").write_text("".join(f"file '{f.as_posix()}'\n" for f in files))
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", "work/source_concat.txt", "-c", "copy",
         "raw/raw.mkv"])
    run(["ffmpeg", "-v", "error", "-y", "-i", "raw/raw.mkv", "-vn", "-ac", "1", "-ar", "16000", "work/audio16k.wav"])
    (ROOT / "raw" / "segments.json").write_text(json.dumps(table, indent=1))
    for s in table:
        print(f"{s['label']}: {s['start']:7.1f} - {s['end']:7.1f}  ({s['clip']} from {s['clip_in']:.0f}s)")
    print(f"raw/raw.mkv: {t / 60:.1f} min")


if __name__ == "__main__":
    main()
