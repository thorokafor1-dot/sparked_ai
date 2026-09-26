# IG Posting Automation

Single job of this folder: get a finished Short/Reel from a Google Drive link onto Instagram.

## Scripts
- `login_chrome_profile.py`, one-time interactive login: opens a dedicated Chrome profile directory so Instagram session cookies persist there for later automated runs. Run manually first, before `upload_short.py`.
- `upload_short.py`, downloads a video from a Drive link and posts it to Instagram using the Chrome profile created above. No passwords are handled by this script.
- `post_to_instagram.bat`, convenience wrapper that calls `upload_short.py` with a specific drive link, caption file, and Chrome profile directory.

## Quality gates (automatic, `qa/preflight_post.py`)
The upload script runs a pre-flight on its own inputs and exits with code 2, before anything is downloaded or uploaded, if a check fails:
- Caption: not empty, no em dash, no placeholders, within the character limit, no repeated hashtags. Hashtag limits: Facebook 1-3 (the user's rule), IG/TikTok 30 max.
- Video file: 9:16, at least 1280px tall, has audio, within the platform's length limit, h264.
- YouTube (`upload_video.py`): title 1-100 chars, no `<`/`>`, description and tag limits, and the thumbnail must pass `thumbnail-specs`.
Never bypass a failed pre-flight. Fix the input and re-run. Publish itself stays a human click.

## Scope rules
- This folder only handles posting to Instagram. It doesn't decide *what* to post (that's `shorts-hook-research/`) or find outliers (`outlier-tracking/`), it just takes a finished video and publishes it.
- No GitHub Actions workflow calls these scripts (login is interactive and posting uses a local Chrome profile), so there's no CI path to keep in sync here.
