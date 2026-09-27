"""One-time interactive OAuth login for the YouTube Data API v3.

Opens Google's consent screen in your browser, catches the redirect on a local
server, and saves the resulting access/refresh token pair to token.json next
to this script (gitignored). upload_video.py reads that file and refreshes
the access token automatically -- re-run this script only if token.json is
lost or the refresh token is revoked.

Requires client_secret.json (a "Web application" OAuth client downloaded from
Google Cloud Console, with http://localhost:8080/ added as an Authorized
redirect URI) in this same folder -- see claude.md for the one-time Cloud
Console setup steps. Also gitignored; never commit it.

Usage:
    python oauth_setup.py
"""
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube.force-ssl",  # needed for thumbnails().set()
]

CLIENT_SECRETS_PATH = Path(__file__).parent / "client_secret.json"
TOKEN_PATH = Path(__file__).parent / "token.json"


def main() -> None:
    if not CLIENT_SECRETS_PATH.exists():
        raise SystemExit(
            f"Missing {CLIENT_SECRETS_PATH}. Download the OAuth client JSON from "
            "Google Cloud Console (APIs & Services > Credentials > your Web application "
            "OAuth client) and save it there first -- see claude.md."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS_PATH), SCOPES)
    creds = flow.run_local_server(port=8080)

    TOKEN_PATH.write_text(creds.to_json())
    print(f"Saved: {TOKEN_PATH}")


if __name__ == "__main__":
    main()
