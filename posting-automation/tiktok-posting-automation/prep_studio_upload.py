"""One-command prep for a manual TikTok Studio upload (the API can't post publicly yet, see claude.md).

Copies the caption to the clipboard, puts the cover PNG next to the video, opens Explorer with the video
selected and opens TikTok Studio's upload page in the user's normal Chrome, then prints the caption so it
can be shown in chat as a copy-paste block (user, 2026-10-04: always show it, never make them ask).
Posting stays the user's click.

  python prep_studio_upload.py --video <short.mp4> [--cover <cover.png>] [--caption-file caption.txt]
"""
import argparse
import shutil
import subprocess
import tempfile
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
UPLOAD_URL = "https://www.tiktok.com/tiktokstudio/upload"


def copy_to_clipboard(text: str) -> None:
    """clip.exe and piping into PowerShell both mangle emoji (tested 2026-10-04: the 👇 was lost);
    reading a UTF-8 file inside PowerShell keeps it intact."""
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", suffix=".txt", delete=False) as f:
        f.write(text)
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             f"Get-Content -LiteralPath '{f.name}' -Raw -Encoding UTF8 | Set-Clipboard"],
            check=True,
        )
    finally:
        Path(f.name).unlink(missing_ok=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--video", required=True)
    ap.add_argument("--cover", default=None, help="cover PNG; copied next to the video for one-folder picking")
    ap.add_argument("--caption-file", default=str(HERE / "caption.txt"))
    ap.add_argument("--dry-run", action="store_true", help="pre-flight and print the caption, open nothing")
    a = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    video = Path(a.video).resolve()
    caption = Path(a.caption_file).read_text(encoding="utf-8").strip()
    sys.path.insert(0, str(HERE.parents[1] / "qa"))
    from preflight_post import caption_problems, enforce, vertical_video_problems
    enforce(caption_problems("tiktok", caption), "caption")
    enforce(vertical_video_problems("tiktok", video), "video file")

    if a.dry_run:
        print(caption)
        return
    if a.cover:
        cover = Path(a.cover).resolve()
        if cover.parent != video.parent:
            shutil.copy2(cover, video.parent / cover.name)
    copy_to_clipboard(caption)
    subprocess.Popen(["explorer.exe", f"/select,{video}"])
    subprocess.Popen(["cmd", "/c", "start", "", "chrome.exe", UPLOAD_URL])
    print("Caption copied to clipboard. TikTok Studio and the video folder are open.\n")
    print("CAPTION (show this in chat as a copy-paste block):")
    print(caption)


if __name__ == "__main__":
    main()
