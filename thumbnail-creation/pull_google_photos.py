"""Pulls specific photos out of the creator's personal Google Photos library using
the Google Photos Picker API, the current (2025+) supported path for letting a
user hand an app a handful of their own photos. The older Photos Library API's
broad `photoslibrary.readonly` scope (read the whole library unattended) now
needs a Google security assessment for most apps, the Picker API sidesteps that
by having the user actively pick photos in a Google-hosted UI each run, this
script just creates that picking session, waits for the user to finish, then
downloads whatever they picked.

This exists because generate_concept_mockup.py needs a real, clear, well-lit
solo photo of the creator (reference/self/) as an identity anchor, and no such
photo already existed in this repo's footage library, everything real here is
composed around the woman's reaction with the creator only partially in frame.

One-time setup (see claude.md for the full Cloud Console walkthrough):
1. Google Cloud Console: create/reuse a project, enable the "Google Photos
   Picker API", create an OAuth client ID (Web application, redirect URI
   http://localhost:8080/).
2. Add its Client ID and Client Secret to thumbnail-creation/.env (gitignored,
   same pattern as OPENAI_API_KEY already there) as:
       GOOGLE_OAUTH_CLIENT_ID=...
       GOOGLE_OAUTH_CLIENT_SECRET=...
   Edit .env yourself, this script never needs to display or log those values.
3. If the OAuth consent screen is in Testing mode, add the account as a test
   user (Console > OAuth consent screen > Test users).
4. Run `python pull_google_photos.py --setup` once, a real browser opens for
   you to log in and approve access, saves token.json here (gitignored,
   contains only a short-lived access/refresh token pair, not your client secret).

Usage:
    python pull_google_photos.py --setup          # one-time OAuth login
    python pull_google_photos.py --out reference/self/   # pick + download
"""
import argparse
import os
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

load_dotenv(Path(__file__).parent / ".env")

SCOPES = ["https://www.googleapis.com/auth/photospicker.mediaitems.readonly"]
TOKEN_PATH = Path(__file__).parent / "token.json"
API_BASE = "https://photospicker.googleapis.com/v1"

# Google's fixed OAuth endpoints, not secret, only the client id/secret below are.
_CLIENT_CONFIG_TEMPLATE = {
    "web": {
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost:8080/"],
    }
}


def _client_config() -> dict:
    client_id = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
    client_secret = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")
    if not client_id or not client_secret:
        raise SystemExit(
            "Missing GOOGLE_OAUTH_CLIENT_ID / GOOGLE_OAUTH_CLIENT_SECRET in "
            "thumbnail-creation/.env, add them first, see claude.md."
        )
    config = {"web": dict(_CLIENT_CONFIG_TEMPLATE["web"])}
    config["web"]["client_id"] = client_id
    config["web"]["client_secret"] = client_secret
    return config


def _oauth_setup() -> None:
    flow = InstalledAppFlow.from_client_config(_client_config(), SCOPES)
    creds = flow.run_local_server(port=8080)
    TOKEN_PATH.write_text(creds.to_json())
    print(f"Saved: {TOKEN_PATH}")


def _load_creds() -> Credentials:
    if not TOKEN_PATH.exists():
        raise SystemExit("Missing token.json, run with --setup first.")
    creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        TOKEN_PATH.write_text(creds.to_json())
    return creds


def _create_session(access_token: str) -> dict:
    resp = requests.post(
        f"{API_BASE}/sessions",
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def _poll_session(session_id: str, access_token: str, poll_interval_s: float, timeout_s: float) -> dict:
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        resp = requests.get(
            f"{API_BASE}/sessions/{session_id}",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=30,
        )
        resp.raise_for_status()
        session = resp.json()
        if session.get("mediaItemsSet"):
            return session
        time.sleep(poll_interval_s)
    raise SystemExit(
        "Timed out waiting for photos to be picked. Re-run and make sure to "
        "select photos in the browser tab that opens, then finish/close it."
    )


def _list_media_items(session_id: str, access_token: str) -> list:
    items = []
    page_token = None
    while True:
        params = {"sessionId": session_id, "pageSize": 100}
        if page_token:
            params["pageToken"] = page_token
        resp = requests.get(
            f"{API_BASE}/mediaItems",
            headers={"Authorization": f"Bearer {access_token}"},
            params=params,
            timeout=30,
        )
        resp.raise_for_status()
        data = resp.json()
        items.extend(data.get("mediaItems", []))
        page_token = data.get("nextPageToken")
        if not page_token:
            break
    return items


def _download(item: dict, out_dir: Path, access_token: str) -> Path:
    base_url = item["mediaFile"]["baseUrl"]
    filename = item["mediaFile"].get("filename") or f"{item['id']}.jpg"
    out_path = out_dir / filename
    resp = requests.get(
        f"{base_url}=d",  # =d requests the full original-quality download
        headers={"Authorization": f"Bearer {access_token}"},
        timeout=60,
    )
    resp.raise_for_status()
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(resp.content)
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--setup", action="store_true", help="one-time interactive OAuth login")
    parser.add_argument("--out", default="reference/self", help="folder to save picked photos into")
    parser.add_argument("--poll-interval", type=float, default=3.0)
    parser.add_argument("--timeout", type=float, default=300.0, help="seconds to wait for picking to finish")
    args = parser.parse_args()

    if args.setup:
        _oauth_setup()
        return

    creds = _load_creds()
    session = _create_session(creds.token)
    print("Open this URL and pick 1-3 clear, well-lit, full-face photos of yourself:")
    print(f"  {session['pickerUri']}")
    print("Waiting for you to finish picking...")

    poll_interval = session.get("pollingConfig", {}).get("pollInterval", f"{args.poll_interval}s")
    poll_interval_s = float(str(poll_interval).rstrip("s") or args.poll_interval)
    session = _poll_session(session["id"], creds.token, poll_interval_s, args.timeout)

    items = _list_media_items(session["id"], creds.token)
    if not items:
        raise SystemExit("No photos were picked.")

    out_dir = Path(args.out)
    for item in items:
        path = _download(item, out_dir, creds.token)
        print(f"Saved: {path}")

    print(f"\n{len(items)} photo(s) saved to {out_dir}/")


if __name__ == "__main__":
    sys.exit(main() or 0)
