"""One-time interactive OAuth login for reading this channel's own analytics.

Reuses the posting OAuth client (posting-automation/youtube-posting-automation/client_secret.json)
but saves a separate read-only token here, so the upload token is never touched.
The Cloud project needs the "YouTube Analytics API" enabled (APIs & Services > Library).

Usage:
    python oauth_setup.py
"""
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

HERE = Path(__file__).parent
SCOPES = [
    "https://www.googleapis.com/auth/yt-analytics.readonly",
    "https://www.googleapis.com/auth/youtube.force-ssl",  # uploads list + auto-caption download for drop-off quotes
]
CLIENT_SECRETS_PATH = HERE.parent / "posting-automation" / "youtube-posting-automation" / "client_secret.json"
TOKEN_PATH = HERE / "token.json"


def main() -> None:
    flow = InstalledAppFlow.from_client_secrets_file(str(CLIENT_SECRETS_PATH), SCOPES)
    # Port 8080: the posting client is a "Web application" OAuth client, which only accepts its
    # registered redirect URI (http://localhost:8080/), so any other port fails with redirect_uri_mismatch.
    # open_browser=False: auto-opening launches whatever Chrome profile is currently default, which may
    # not be the Thor profile signed into this channel. The printed URL gets pasted into the right one.
    creds = flow.run_local_server(port=8080, open_browser=False)
    TOKEN_PATH.write_text(creds.to_json())
    print(f"Saved: {TOKEN_PATH}")


if __name__ == "__main__":
    main()
