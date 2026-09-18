"""Downloads the long-form source video from a Google Drive link into input/,
same resolve-and-download pattern as ig-posting-automation/upload_short.py.

Usage:
    python download_source.py --drive-link "https://drive.google.com/file/d/XXXX/view"
"""
import argparse
import re
from pathlib import Path

INPUT_DIR = Path(__file__).parent / "input"


def resolve_drive_file_id(url_or_id: str) -> str:
    for pattern in (r"/d/([a-zA-Z0-9_-]+)", r"[?&]id=([a-zA-Z0-9_-]+)"):
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    return url_or_id


def download_from_drive(drive_link: str, dest_dir: Path = INPUT_DIR) -> Path:
    import gdown

    dest_dir.mkdir(parents=True, exist_ok=True)
    file_id = resolve_drive_file_id(drive_link)
    dest_path = dest_dir / f"{file_id}.mp4"
    if dest_path.exists():
        print(f"Already downloaded: {dest_path}")
        return dest_path
    gdown.download(id=file_id, output=str(dest_path), quiet=False)
    if not dest_path.exists():
        raise RuntimeError(
            f"Download failed for Drive file {file_id}. Confirm sharing is set to "
            "'Anyone with the link' and the link points to a single video file."
        )
    return dest_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Download the long-form source video from Drive.")
    parser.add_argument("--drive-link", required=True, help="Google Drive share link (or file ID)")
    args = parser.parse_args()
    path = download_from_drive(args.drive_link)
    print(f"Saved to: {path}")


if __name__ == "__main__":
    main()
