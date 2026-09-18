# TikTok Posting Automation

Single job of this folder: get a finished Short from a Google Drive link onto TikTok.

## Scripts
- `login_chrome_profile.py` — one-time interactive login: opens a dedicated Chrome profile directory so the TikTok session cookies persist there for later automated runs. Run manually first, before `upload_short.py`.
- `upload_short.py` — downloads a video from a Drive link and posts it to TikTok using the Chrome profile created above. No passwords are handled by this script.
- `post_to_tiktok.bat` — convenience wrapper that calls `upload_short.py` with a specific drive link and caption.

## Important: unverified selectors
Like the Facebook automation, TikTok's upload-composer selectors here are best-effort guesses, not verified against the live site. Every automated step falls back to "pause and ask you to do it by hand in the visible browser window" if its guessed selector doesn't match. Expect to fix selectors against a real run using the debug screenshots (see `--debug-dir`, defaults to `debug_screenshots/`) before this gets fully hands-off.

## content-posting-api/ (parked, not in use)
An earlier pass at this used TikTok's official Content Posting API (OAuth + app
review) instead of browser automation, to avoid any bot-detection ban risk. That
path was shelved because the app-review process (icon, category, hosted Terms of
Service/Privacy Policy, demo video, products/scopes) was too much overhead for now.
`oauth_setup.py` and `upload_short_api.py` are kept in `content-posting-api/` in
case it's worth revisiting later — not wired into `post_to_tiktok.bat`.

## Scope rules
- This folder only handles posting to TikTok. It doesn't decide *what* to post (that's `shorts-hook-research/`) or find outliers (`outlier-tracking/`) — it just takes a finished video and publishes it.
- No GitHub Actions workflow calls these scripts (login is interactive and posting uses a local Chrome profile), so there's no CI path to keep in sync here.
