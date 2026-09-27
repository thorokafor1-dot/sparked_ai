"""Uploads a finished video to YouTube via the official Data API v3
(videos.insert, resumable upload) and, if given, sets a custom thumbnail
(thumbnails.set). Requires a one-time login via oauth_setup.py first (see
that file), which saves credentials to token.json next to this script. This
script always refreshes the access token before use if it's expired.

Defaults to privacyStatus=private -- pass --privacy unlisted or --privacy
public once you've reviewed the upload in YouTube Studio.

Usage:
    python upload_video.py --video path\\to\\video.mp4 --title "..." \\
        --description "..." --tags "tag1,tag2,tag3" --thumbnail path\\to\\thumb.jpg \\
        --privacy private
"""
import argparse
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]
TOKEN_PATH = Path(__file__).parent / "token.json"


def _load_credentials() -> Credentials:
    if not TOKEN_PATH.exists():
        raise SystemExit(f"Missing {TOKEN_PATH}. Run oauth_setup.py first.")
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())
    return creds


def upload(
    video_path: str,
    title: str,
    description: str,
    tags: list[str],
    privacy: str,
    category_id: str,
    thumbnail_path: str | None,
) -> str:
    youtube = build("youtube", "v3", credentials=_load_credentials())

    body = {
        "snippet": {
            "title": title,
            "description": description,
            "tags": tags,
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy,
            "selfDeclaredMadeForKids": False,
        },
    }
    media = MediaFileUpload(video_path, chunksize=-1, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            print(f"Uploaded {int(status.progress() * 100)}%")
    video_id = response["id"]
    print(f"Video created: https://youtu.be/{video_id} (privacy={privacy})")

    if thumbnail_path:
        try:
            youtube.thumbnails().set(
                videoId=video_id, media_body=MediaFileUpload(thumbnail_path)
            ).execute()
            print("Thumbnail set.")
        except HttpError as e:
            print(
                f"Thumbnail upload failed ({e.status_code if hasattr(e, 'status_code') else e}). "
                "Custom thumbnails require the channel to have verified a phone number "
                "at youtube.com/verify -- do that, then re-run just the thumbnail step, "
                "or set it manually in YouTube Studio."
            )

    print(f"Edit in Studio: https://studio.youtube.com/video/{video_id}/edit")
    return video_id


def main() -> None:
    parser = argparse.ArgumentParser(description="Upload a video to YouTube via the Data API v3.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--description", default="")
    parser.add_argument("--tags", default="", help="Comma-separated tags")
    parser.add_argument("--thumbnail", default=None)
    parser.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    parser.add_argument("--category-id", default="22", help="YouTube category ID (default 22 = People & Blogs)")
    args = parser.parse_args()

    # Project-wide pre-flight (qa/preflight_post.py): abort before anything is uploaded.
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "qa"))
    from preflight_post import enforce, youtube_problems
    enforce(youtube_problems(args.title, args.description, args.tags, args.thumbnail, args.video), "YouTube upload")

    tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    upload(args.video, args.title, args.description, tags, args.privacy, args.category_id, args.thumbnail)


if __name__ == "__main__":
    main()
