"""Build raw/raw.mkv: the kept ranges of the 2026-04-23 campus clip, back to back, on one timeline.

Video is the phone clip (vertical 1080x1920, 30 fps, h264). Audio per segment is either the client's voice memo
("memo": raw/mic/elmwood_pl.m4a, lossless, he wears it, so it hears his sets and the coaching clearly) or the phone's
own audio ("phone": only where the memo doesn't hear the conversation, e.g. Thor's Regina set, when the client was
out of earshot). There is no Wireless GO recording of this session.

raw/segments.json maps every combined-timeline range back to the clip time and audio source.
Usage: python build_source.py   (segments are cached; edit SEGMENTS and re-run)
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
CLIP = "raw/2026-04-23_192431.mov"
MEMO = "raw/mic/elmwood_pl.m4a"
MEMO_OFFSET = 24.865   # memo time = clip time + MEMO_OFFSET (cross-correlated: 7 ms drift over 35 min)

# (label, clip in, clip out, audio "memo" | "phone")
# One clip, so the source keeps the clip's own timeline (source time = clip time): the memo everywhere except Thor's
# Regina set, which only the phone heard (the client was out of earshot).
SEGMENTS = [
    ("memo1", 0.0, 1655.0, "memo"),
    ("regina", 1655.0, 1775.0, "phone"),
    ("memo2", 1775.0, 2109.2, "memo"),
]
FPS, SR = 30, 48000


def run(cmd):
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode:
        sys.exit(r.stderr[-2000:])


def main():
    seg_dir = ROOT / "work" / "source"
    seg_dir.mkdir(parents=True, exist_ok=True)
    files, table, t = [], [], 0.0
    for label, a, b, audio in SEGMENTS:
        out = seg_dir / f"{label}_{a:.0f}_{b:.0f}_{audio}.mkv"
        n = round((b - a) * FPS)
        if not out.exists():
            if audio == "memo":
                ains = ["-ss", f"{a + MEMO_OFFSET:.3f}", "-t", f"{b - a:.3f}", "-i", MEMO]
                amap = "[1:a]"
            else:
                ains, amap = [], "[0:a]"
            tmp = out.with_suffix(".part.mkv")
            run(["ffmpeg", "-v", "error", "-y", "-ss", f"{a:.3f}", "-to", f"{b:.3f}", "-i", CLIP, *ains,
                 "-filter_complex", f"[0:v]fps={FPS},scale=1080:1920,setsar=1[v];"
                 f"{amap}aformat=sample_rates={SR}:channel_layouts=stereo,apad,atrim=end_sample={round(n / FPS * SR)}[a]",
                 "-map", "[v]", "-map", "[a]", "-frames:v", str(n),
                 "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-pix_fmt", "yuv420p",
                 "-c:a", "pcm_s16le", str(tmp)])
            tmp.replace(out)
            print("built", out.name, flush=True)
        files.append(out)
        d = n / FPS
        table.append({"label": label, "start": round(t, 3), "end": round(t + d, 3), "clip_in": a, "audio": audio})
        t += d
    (ROOT / "work" / "source_concat.txt").write_text("".join(f"file '{f.as_posix()}'\n" for f in files))
    run(["ffmpeg", "-v", "error", "-y", "-f", "concat", "-safe", "0", "-i", "work/source_concat.txt", "-c", "copy",
         "raw/raw.mkv"])
    run(["ffmpeg", "-v", "error", "-y", "-i", "raw/raw.mkv", "-vn", "-ac", "1", "-ar", "16000", "work/audio16k.wav"])
    (ROOT / "raw" / "segments.json").write_text(json.dumps(table, indent=1))
    for s in table:
        print(f"{s['label']}: {s['start']:7.1f} - {s['end']:7.1f}  (clip {s['clip_in']:.0f}s, {s['audio']} audio)")
    print(f"raw/raw.mkv: {t / 60:.1f} min")


if __name__ == "__main__":
    main()
