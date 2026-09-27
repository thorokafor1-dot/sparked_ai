"""Street-noise removal for infield audio with DeepFilterNet (github.com/Rikorose/DeepFilterNet).

Uses the standalone deep-filter binary (CPU, no torch needed). It lives in tools/bin/ (gitignored);
if it's missing, it's downloaded on first use.

    python tools/denoise.py clip.mp4                 # writes clip_denoised.mp4 (video stream copied)
    python tools/denoise.py clip.mp4 --atten 24      # stronger cleanup
    python tools/denoise.py voice.m4a --out clean.wav

From code:
    from denoise import denoised_wav
    wav = denoised_wav(src, cache_dir)  # 48 kHz wav, cached by source path/size/mtime + settings

The attenuation limit is the key setting. Full suppression (100 dB) makes street audio sound
underwater and kills the sense of place, which clashes with the smooth, natural brand feel.
18 dB takes traffic and wind down to a bed under the voices without artefacts on her quieter lines.
"""
from __future__ import annotations

import argparse
import hashlib
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

VERSION = "0.5.6"
BIN = Path(__file__).parent / "bin" / "deep-filter.exe"
URL = (f"https://github.com/Rikorose/DeepFilterNet/releases/download/v{VERSION}/"
       f"deep-filter-{VERSION}-x86_64-pc-windows-msvc.exe")
DEFAULT_ATTEN_DB = 18.0


def ensure_binary() -> Path:
    if not BIN.exists():
        BIN.parent.mkdir(parents=True, exist_ok=True)
        print(f"downloading deep-filter {VERSION}...", flush=True)
        urllib.request.urlretrieve(URL, BIN)
    return BIN


def denoised_wav(src: Path, cache_dir: Path, atten_db: float = DEFAULT_ATTEN_DB) -> Path:
    """Denoise src's audio track to a 48 kHz stereo wav, same duration and timing as the source."""
    src = Path(src)
    st = src.stat()
    key = hashlib.sha1(f"{src.resolve()}|{st.st_size}|{st.st_mtime_ns}|{atten_db}|{VERSION}".encode()).hexdigest()[:12]
    cache_dir.mkdir(parents=True, exist_ok=True)
    out = cache_dir / f"{src.stem}_dfn_{key}.wav"
    if out.exists():
        return out
    with tempfile.TemporaryDirectory() as tmp:
        raw = Path(tmp) / f"{src.stem}.wav"
        # DeepFilterNet only runs at 48 kHz
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vn", "-ac", "2", "-ar", "48000",
                        "-c:a", "pcm_s16le", str(raw)], check=True)
        # -D compensates the STFT/lookahead delay so the audio stays in sync with the picture
        subprocess.run([str(ensure_binary()), "-D", "-a", str(atten_db), "-o", str(Path(tmp) / "out"), str(raw)],
                       check=True, capture_output=True)
        shutil.move(str(Path(tmp) / "out" / raw.name), out)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("src", type=Path)
    parser.add_argument("--out", type=Path, help="Default: <src>_denoised<ext> next to the source")
    parser.add_argument("--atten", type=float, default=DEFAULT_ATTEN_DB, help="Max noise reduction in dB (default 18)")
    args = parser.parse_args()

    out = args.out or args.src.with_name(f"{args.src.stem}_denoised{args.src.suffix}")
    wav = denoised_wav(args.src, Path(tempfile.gettempdir()) / "sparked_denoise", args.atten)
    if out.suffix.lower() == ".wav":
        shutil.copy(wav, out)
    else:
        has_video = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries", "stream=index",
                                    "-of", "csv=p=0", str(args.src)], capture_output=True, text=True).stdout.strip()
        cmd = ["ffmpeg", "-y", "-v", "error", "-i", str(args.src), "-i", str(wav)]
        cmd += (["-map", "0:v", "-map", "1:a", "-c:v", "copy"] if has_video else ["-map", "1:a"])
        subprocess.run(cmd + ["-c:a", "aac", "-b:a", "192k", "-shortest", str(out)], check=True)
    print(out)


if __name__ == "__main__":
    sys.exit(main())
