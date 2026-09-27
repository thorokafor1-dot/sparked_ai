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
    creds = flow.run_local_server(port=8080)
    TOKEN_PATH.write_text(creds.to_json())
    print(f"Saved: {TOKEN_PATH}")


if __name__ == "__main__":
    main()
