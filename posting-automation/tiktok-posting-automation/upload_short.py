"""Publishes a short video to TikTok via the official Content Posting API
(Direct Post) -- no browser automation, unlike the Facebook/Instagram
automations in this repo. Downloads the video from a Google Drive link, then
runs TikTok's documented three-step flow: query creator info, init the
publish (chunked FILE_UPLOAD), upload the video bytes, poll publish status.

Requires a one-time login via oauth_setup.py first (see that file), which
saves an access/refresh token pair to tokens.json next to this script. This
script always refreshes the access token before use, since TikTok's access
tokens are short-lived.

Until the TikTok app has passed audit for the `video.publish` scope, the API
only accepts privacy_level=SELF_ONLY (post is visible only to your own
account) -- this is TikTok's restriction, not something this script can work
around. Pass --privacy-level PUBLIC_TO_EVERYONE once the app is audited and
the account's creator_info confirms that option is available.

Nothing publishes without an explicit confirmation step: by default the
script prints the final caption and chosen cover frame, then requires typing
"y" before calling the publish API (running non-interactively with no stdin
counts as "not confirmed", same reasoning as the Facebook/Instagram browser
automations' final manual Publish click). Pass --yes to skip the prompt once
you've already reviewed everything.

Cover frame selection is a two-step flow, same shape as the Facebook
automation's frame-scrubbing cover picker:
    1. python upload_short.py --drive-link "..." --caption "..." --preview-covers
       -- downloads the video, saves several candidate cover frames to
       cover_previews/, and exits without posting.
    2. Look at the saved frames, then re-run with
       --cover-timestamp-ms <ms> --yes (or without --yes to still confirm)
       to actually publish using that frame.

Usage:
    python upload_short.py --drive-link "https://drive.google.com/file/d/XXXX/view" --caption "some caption"
"""
import argparse
import json
import subprocess
import tempfile
import textwrap
import time
import re
from pathlib import Path

import requests

TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
CREATOR_INFO_URL = "https://open.tiktokapis.com/v2/post/publish/creator_info/query/"
INIT_URL = "https://open.tiktokapis.com/v2/post/publish/video/init/"
STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"
DEFAULT_TOKENS_PATH = Path(__file__).parent / "tokens.json"
MAX_CHUNK_SIZE = 64 * 1024 * 1024


def resolve_drive_file_id(url_or_id: str) -> str:
    for pattern in (r"/d/([a-zA-Z0-9_-]+)", r"[?&]id=([a-zA-Z0-9_-]+)"):
        match = re.search(pattern, url_or_id)
        if match:
            return match.group(1)
    return url_or_id


def download_from_drive(drive_link: str, dest_dir: Path) -> Path:
    import gdown

    file_id = resolve_drive_file_id(drive_link)
    dest_path = dest_dir / f"{file_id}.mp4"
    gdown.download(id=file_id, output=str(dest_path), quiet=False)
    if not dest_path.exists():
        raise RuntimeError(
            f"Download failed for Drive file {file_id}. Confirm sharing is set to "
            "'Anyone with the link' and the link points to a single file."
        )
    return dest_path


def load_tokens(tokens_path: Path) -> dict:
    if not tokens_path.exists():
        raise SystemExit(f"No tokens file at {tokens_path}. Run oauth_setup.py first.")
    return json.loads(tokens_path.read_text(encoding="utf-8"))


def refresh_access_token(tokens_path: Path) -> str:
    """Always refreshes rather than tracking expiry locally -- simpler, and
    avoids posting with a token that expired seconds ago. TikTok may rotate
    the refresh_token itself on use, so the response is always written back.
    """
    tokens = load_tokens(tokens_path)
    resp = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": tokens["client_key"],
            "client_secret": tokens["client_secret"],
            "grant_type": "refresh_token",
            "refresh_token": tokens["refresh_token"],
        },
        timeout=30,
    )
    data = resp.json()
    if resp.status_code != 200 or "access_token" not in data:
        raise RuntimeError(f"Token refresh failed ({resp.status_code}): {data}. Re-run oauth_setup.py.")
    tokens.update(data)
    tokens_path.write_text(json.dumps(tokens, indent=2), encoding="utf-8")
    return tokens["access_token"]


def query_creator_info(access_token: str) -> dict:
    resp = requests.post(
        CREATOR_INFO_URL,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"},
        timeout=30,
    )
    data = resp.json()
    error = data.get("error", {})
    if resp.status_code != 200 or error.get("code") not in (None, "ok"):
        raise RuntimeError(f"creator_info query failed ({resp.status_code}): {data}")
    return data["data"]


def get_video_duration_s(video_path: Path) -> float:
    result = subprocess.run(
        [
            "ffprobe", "-v", "error", "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1", str(video_path),
        ],
        capture_output=True, text=True, check=True,
    )
    return float(result.stdout.strip())


def extract_cover_candidates(video_path: Path, out_dir: Path, count: int) -> list[tuple[int, Path]]:
    """Save `count` evenly-spaced candidate cover-frame images so one can be
    picked visually before posting -- same idea as the Facebook automation's
    frame-scrubbing cover picker, just done as a separate preview pass here
    since the Content Posting API only takes a millisecond timestamp
    (video_cover_timestamp_ms), not an uploaded image. Skips the first/last 5%
    of the video, where cold-approach clips are usually still on a title card
    or a blurry transition rather than a representative frame.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    for old in out_dir.glob("cover_*.png"):
        old.unlink()
    duration_s = get_video_duration_s(video_path)
    start, end = duration_s * 0.05, duration_s * 0.95
    candidates = []
    for i in range(count):
        t = start + (end - start) * i / max(count - 1, 1)
        ms = int(t * 1000)
        out_path = out_dir / f"cover_{i}_{ms}ms.png"
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(t), "-i", str(video_path), "-frames:v", "1", str(out_path)],
            capture_output=True, check=True,
        )
        candidates.append((ms, out_path))
    return candidates


def plan_chunks(video_size: int) -> tuple[int, int]:
    """TikTok's FILE_UPLOAD source requires chunk_size between 5MB and 64MB
    except for videos small enough to send as a single chunk. Short-form
    videos here are almost always well under 64MB, so this only actually
    splits for the rare oversized file.
    """
    if video_size <= MAX_CHUNK_SIZE:
        return video_size, 1
    total_chunk_count = -(-video_size // MAX_CHUNK_SIZE)  # ceil division
    return MAX_CHUNK_SIZE, total_chunk_count


def init_video_publish(
    access_token: str,
    video_size: int,
    chunk_size: int,
    total_chunk_count: int,
    caption: str,
    privacy_level: str,
    cover_timestamp_ms: int | None,
) -> tuple[str, str]:
    post_info = {
        "title": caption,
        "privacy_level": privacy_level,
        "disable_duet": False,
        "disable_comment": False,
        "disable_stitch": False,
    }
    if cover_timestamp_ms is not None:
        post_info["video_cover_timestamp_ms"] = cover_timestamp_ms
    body = {
        "post_info": post_info,
        "source_info": {
            "source": "FILE_UPLOAD",
            "video_size": video_size,
            "chunk_size": chunk_size,
            "total_chunk_count": total_chunk_count,
        },
    }
    resp = requests.post(
        INIT_URL,
        headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"},
        json=body,
        timeout=30,
    )
    data = resp.json()
    error = data.get("error", {})
    if resp.status_code != 200 or error.get("code") not in (None, "ok"):
        raise RuntimeError(f"publish/video/init failed ({resp.status_code}): {data}")
    return data["data"]["publish_id"], data["data"]["upload_url"]


def upload_video_chunks(upload_url: str, video_path: Path, video_size: int, chunk_size: int, total_chunk_count: int) -> None:
    with open(video_path, "rb") as f:
        for i in range(total_chunk_count):
            start = i * chunk_size
            end = min(start + chunk_size, video_size) - 1
            f.seek(start)
            chunk = f.read(end - start + 1)
            resp = requests.put(
                upload_url,
                headers={
                    "Content-Range": f"bytes {start}-{end}/{video_size}",
                    "Content-Type": "video/mp4",
                },
                data=chunk,
                timeout=180,
            )
            if resp.status_code not in (200, 201):
                raise RuntimeError(f"Chunk {i + 1}/{total_chunk_count} upload failed ({resp.status_code}): {resp.text}")
            print(f"  [ok] uploaded chunk {i + 1}/{total_chunk_count}", flush=True)


def poll_publish_status(access_token: str, publish_id: str, timeout_s: int = 300, interval_s: int = 5) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = requests.post(
            STATUS_URL,
            headers={"Authorization": f"Bearer {access_token}", "Content-Type": "application/json; charset=UTF-8"},
            json={"publish_id": publish_id},
            timeout=30,
        )
        data = resp.json()
        error = data.get("error", {})
        if resp.status_code != 200 or error.get("code") not in (None, "ok"):
            raise RuntimeError(f"status/fetch failed ({resp.status_code}): {data}")
        status = data["data"].get("status")
        print(f"  [status] {status}", flush=True)
        if status == "PUBLISH_COMPLETE":
            return data["data"]
        if status == "FAILED":
            raise RuntimeError(f"TikTok publish failed: {data['data']}")
        time.sleep(interval_s)
    raise TimeoutError(f"Timed out after {timeout_s}s waiting for publish_id={publish_id} to complete")


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish a short video to TikTok via the Content Posting API.")
    parser.add_argument("--drive-link", required=True, help="Google Drive share link (or file ID) for the video")
    caption_group = parser.add_mutually_exclusive_group(required=True)
    caption_group.add_argument("--caption", help="Caption text for the post")
    caption_group.add_argument(
        "--caption-file", help="Path to a text file containing the caption (avoids shell-quoting multi-line captions)"
    )
    parser.add_argument(
        "--privacy-level",
        default="SELF_ONLY",
        choices=["SELF_ONLY", "PUBLIC_TO_EVERYONE", "MUTUAL_FOLLOW_FRIENDS", "FOLLOWER_OF_CREATOR"],
        help="Defaults to SELF_ONLY (private) -- the only option TikTok accepts before the app passes audit "
        "for the video.publish scope. Must also be present in creator_info's privacy_level_options.",
    )
    parser.add_argument(
        "--preview-covers",
        type=int,
        nargs="?",
        const=6,
        default=None,
        metavar="COUNT",
        help="Download the video, save COUNT (default 6) evenly-spaced candidate cover-frame images to "
        "cover_previews/ next to this script, print their timestamps, then exit without posting.",
    )
    parser.add_argument(
        "--cover-timestamp-ms",
        type=int,
        default=None,
        help="Timestamp in milliseconds to use as the cover/thumbnail frame, picked from a --preview-covers run. "
        "Omit to let TikTok auto-select a frame.",
    )
    parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip the final confirmation prompt (use once the caption and cover frame have already been reviewed).",
    )
    parser.add_argument("--tokens-path", default=str(DEFAULT_TOKENS_PATH), help="Path to tokens.json from oauth_setup.py")
    args = parser.parse_args()
    caption = args.caption if args.caption is not None else Path(args.caption_file).read_text(encoding="utf-8")

    # Project-wide pre-flight (qa/preflight_post.py): abort before anything is uploaded.
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "qa"))
    from preflight_post import caption_problems, enforce, vertical_video_problems
    enforce(caption_problems("tiktok", caption), "caption")
    tokens_path = Path(args.tokens_path)

    with tempfile.TemporaryDirectory(prefix="upload_short_") as tmp_dir:
        video_path = download_from_drive(args.drive_link, Path(tmp_dir))
        enforce(vertical_video_problems("tiktok", Path(video_path)), "video file")

        if args.preview_covers:
            preview_dir = Path(__file__).parent / "cover_previews"
            print(f"Extracting {args.preview_covers} candidate cover frames to {preview_dir} ...", flush=True)
            candidates = extract_cover_candidates(video_path, preview_dir, args.preview_covers)
            for ms, path in candidates:
                print(f"  {ms}ms -> {path}", flush=True)
            print(
                "\nNothing was posted. Look at the frames above, then re-run with "
                "--cover-timestamp-ms <ms> to publish using that one.",
                flush=True,
            )
            return

        video_size = video_path.stat().st_size
        chunk_size, total_chunk_count = plan_chunks(video_size)

        print("Refreshing access token...", flush=True)
        access_token = refresh_access_token(tokens_path)

        print("Querying creator info...", flush=True)
        creator_info = query_creator_info(access_token)
        print(f"  [info] posting as {creator_info.get('creator_username')}", flush=True)
        allowed_privacy = creator_info.get("privacy_level_options", [])
        if allowed_privacy and args.privacy_level not in allowed_privacy:
            raise SystemExit(
                f"--privacy-level {args.privacy_level} isn't available for this account/app right now. "
                f"Allowed options: {allowed_privacy}"
            )

        cover_desc = f"{args.cover_timestamp_ms}ms (from cover_previews/)" if args.cover_timestamp_ms is not None else "auto (TikTok default -- no --cover-timestamp-ms given)"
        print("\n" + "=" * 60, flush=True)
        print("READY TO POST", flush=True)
        print(f"  Account:     {creator_info.get('creator_username')}", flush=True)
        print(f"  Privacy:     {args.privacy_level}", flush=True)
        print(f"  Cover frame: {cover_desc}", flush=True)
        print("  Caption:", flush=True)
        print(textwrap.indent(caption.strip(), "    "), flush=True)
        print("=" * 60, flush=True)

        if not args.yes:
            try:
                confirm = input("Post this now? [y/N]: ").strip().lower()
            except EOFError:
                confirm = ""
            if confirm != "y":
                print(
                    "Not confirmed (or running non-interactively without --yes) -- nothing was posted. "
                    "Re-run with --yes once the caption and cover frame above look right.",
                    flush=True,
                )
                return

        print(f"Initializing publish ({video_size} bytes, {total_chunk_count} chunk(s))...", flush=True)
        publish_id, upload_url = init_video_publish(
            access_token, video_size, chunk_size, total_chunk_count, caption, args.privacy_level, args.cover_timestamp_ms
        )
        print(f"  [ok] publish_id={publish_id}", flush=True)

        print("Uploading video...", flush=True)
        upload_video_chunks(upload_url, video_path, video_size, chunk_size, total_chunk_count)

        print("Waiting for TikTok to finish processing...", flush=True)
        result = poll_publish_status(access_token, publish_id)
        print(f"Done. {result}", flush=True)


if __name__ == "__main__":
    main()
