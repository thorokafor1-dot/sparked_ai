"""One-time interactive OAuth login for TikTok's official Content Posting API.

Unlike the Facebook/Instagram automations (which drive a real Chrome window),
this talks to TikTok's API directly -- no browser automation, no bot-detection
risk. In exchange it needs a registered TikTok developer app and a one-time
consent flow:

  1. Register an app at https://developers.tiktok.com/apps and add the
     "Content Posting API" product, requesting the `user.info.basic` and
     `video.publish` scopes.
  2. In the app's settings, add a Redirect URI matching --redirect-uri below
     (default http://localhost:8722/callback). TikTok's current requirements
     for what redirect URIs it accepts (localhost vs. a verified HTTPS domain)
     may have changed since this was written -- check the Developer Portal if
     registering it fails.
  3. Set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET (from the app's Basic
     Information page) as environment variables, or pass --client-key /
     --client-secret.
  4. Run this script. It opens the TikTok consent screen in your default
     browser, catches the redirect on a short-lived local server, exchanges
     the code for an access token + refresh token, and saves both to
     tokens.json next to this script (gitignored).

Until the app passes TikTok's audit for the `video.publish` scope, posts made
with the saved tokens are restricted to privacy_level=SELF_ONLY (visible only
to your own account) -- see upload_short.py.

Usage:
    python oauth_setup.py
"""
import argparse
import base64
import hashlib
import http.server
import json
import os
import secrets
import urllib.parse
import webbrowser
from pathlib import Path

import requests

TOKEN_URL = "https://open.tiktokapis.com/v2/oauth/token/"
AUTH_URL = "https://www.tiktok.com/v2/auth/authorize/"
SCOPES = "user.info.basic,video.publish"
DEFAULT_TOKENS_PATH = Path(__file__).parent / "tokens.json"


def generate_pkce_pair() -> tuple[str, str]:
    code_verifier = base64.urlsafe_b64encode(secrets.token_bytes(64)).rstrip(b"=").decode("ascii")
    digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
    code_challenge = base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")
    return code_verifier, code_challenge


class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        self.server.callback_params = urllib.parse.parse_qs(parsed.query)  # type: ignore[attr-defined]
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.end_headers()
        self.wfile.write(b"<html><body>TikTok login complete. You can close this tab.</body></html>")

    def log_message(self, format: str, *args) -> None:  # noqa: A002 - matches BaseHTTPRequestHandler signature
        pass


def wait_for_callback(port: int) -> dict:
    server = http.server.HTTPServer(("localhost", port), _CallbackHandler)
    server.callback_params = None  # type: ignore[attr-defined]
    print(f"Waiting for TikTok's redirect on http://localhost:{port}/callback ...", flush=True)
    server.handle_request()
    return server.callback_params  # type: ignore[attr-defined]


def exchange_code_for_tokens(client_key: str, client_secret: str, code: str, redirect_uri: str, code_verifier: str) -> dict:
    resp = requests.post(
        TOKEN_URL,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "client_key": client_key,
            "client_secret": client_secret,
            "code": code,
            "grant_type": "authorization_code",
            "redirect_uri": redirect_uri,
            "code_verifier": code_verifier,
        },
        timeout=30,
    )
    data = resp.json()
    if resp.status_code != 200 or "access_token" not in data:
        raise RuntimeError(f"Token exchange failed ({resp.status_code}): {data}")
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="One-time TikTok OAuth login for the Content Posting API.")
    parser.add_argument("--client-key", default=os.getenv("TIKTOK_CLIENT_KEY"), help="TikTok app client key")
    parser.add_argument("--client-secret", default=os.getenv("TIKTOK_CLIENT_SECRET"), help="TikTok app client secret")
    parser.add_argument(
        "--redirect-uri",
        default=os.getenv("TIKTOK_REDIRECT_URI", "http://localhost:8722/callback"),
        help="Must exactly match a Redirect URI registered on the app in the TikTok Developer Portal",
    )
    parser.add_argument(
        "--tokens-path", default=str(DEFAULT_TOKENS_PATH), help="Where to save the resulting tokens JSON"
    )
    args = parser.parse_args()

    if not args.client_key or not args.client_secret:
        raise SystemExit(
            "Missing client key/secret. Set TIKTOK_CLIENT_KEY and TIKTOK_CLIENT_SECRET, or pass "
            "--client-key/--client-secret."
        )

    parsed_redirect = urllib.parse.urlparse(args.redirect_uri)
    port = parsed_redirect.port or 8722

    code_verifier, code_challenge = generate_pkce_pair()
    state = secrets.token_urlsafe(16)
    auth_params = {
        "client_key": args.client_key,
        "response_type": "code",
        "scope": SCOPES,
        "redirect_uri": args.redirect_uri,
        "state": state,
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
    }
    auth_url = f"{AUTH_URL}?{urllib.parse.urlencode(auth_params)}"

    print("Opening TikTok's consent screen in your browser. Log in and approve access.", flush=True)
    webbrowser.open(auth_url)

    params = wait_for_callback(port)
    if "error" in params:
        raise SystemExit(f"TikTok returned an error: {params}")
    if params.get("state", [None])[0] != state:
        raise SystemExit("State mismatch on callback -- possible CSRF, aborting.")
    code = params.get("code", [None])[0]
    if not code:
        raise SystemExit(f"No authorization code in callback: {params}")

    print("Exchanging authorization code for tokens...", flush=True)
    tokens = exchange_code_for_tokens(args.client_key, args.client_secret, code, args.redirect_uri, code_verifier)

    tokens_path = Path(args.tokens_path)
    tokens_path.write_text(
        json.dumps({**tokens, "client_key": args.client_key, "client_secret": args.client_secret}, indent=2),
        encoding="utf-8",
    )
    print(f"Saved tokens to {tokens_path}. Scope granted: {tokens.get('scope')}", flush=True)


if __name__ == "__main__":
    main()
