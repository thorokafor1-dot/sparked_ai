# IG Posting Automation

Single job of this folder: get a finished Short/Reel from a Google Drive link onto Instagram.

## Scripts
- `login_chrome_profile.py` — one-time interactive login: opens a dedicated Chrome profile directory so Instagram session cookies persist there for later automated runs. Run manually first, before `upload_short.py`.
- `upload_short.py` — downloads a video from a Drive link and posts it to Instagram using the Chrome profile created above. No passwords are handled by this script.
- `post_to_instagram.bat` — convenience wrapper that calls `upload_short.py` with a specific drive link, caption file, and Chrome profile directory.

## Scope rules
- This folder only handles posting to Instagram. It doesn't decide *what* to post (that's `shorts-hook-research/`) or find outliers (`outlier-tracking/`) — it just takes a finished video and publishes it.
- No GitHub Actions workflow calls these scripts (login is interactive and posting uses a local Chrome profile), so there's no CI path to keep in sync here.
