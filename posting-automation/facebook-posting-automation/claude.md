# Facebook Posting Automation

Single job of this folder: get a finished Short/Reel from a Google Drive link onto the Sparked Thor Facebook Page as a Reel.

## Scripts
- `login_chrome_profile.py` — one-time interactive login: opens a dedicated Chrome profile directory so the Facebook session cookies persist there for later automated runs. Log in with an account that's an admin/editor of the Sparked Thor Page. Run manually first, before `upload_short.py`.
- `upload_short.py` — downloads a video from a Drive link and posts it as a Reel to the Sparked Thor Page using the Chrome profile created above. No passwords are handled by this script. Requires `--page-url` pointing at the Page (not a personal profile).
- `post_to_facebook.bat` — convenience wrapper that calls `upload_short.py` with a specific drive link, caption, cover image, and page URL.

## Important: unverified selectors
Unlike the Instagram automation, Facebook's Reel-composer selectors here are best-effort guesses, not verified against the live site. Every automated step falls back to "pause and ask you to do it by hand in the visible browser window" if its guessed selector doesn't match. Expect to do more manual steps here than with IG until the selectors get validated against a real run and tightened up.

Because this posts as a Page rather than a personal profile, `upload_short.py` also has one **loud checkpoint** right after the composer opens: it prints a warning and pauses for a fixed ~20s so you can look at the browser and confirm it's actually posting as the Page before automation continues. It doesn't block on a terminal keypress -- this script normally runs as a background process with no interactive stdin, so `input()` would just hit EOF and fall through instantly. There's no reliable way to verify "posting as" via a selector, and getting that wrong is worse than a normal missed one, but the real safety net is still the final pre-Publish review at the end of the run -- Publish is never clicked automatically.

## Scope rules
- This folder only handles posting to Facebook. It doesn't decide *what* to post (that's `shorts-hook-research/`) or find outliers (`outlier-tracking/`) — it just takes a finished video and publishes it.
- No GitHub Actions workflow calls these scripts (login is interactive and posting uses a local Chrome profile), so there's no CI path to keep in sync here.
