# YouTube Posting Automation

Single job of this folder: get a finished video onto YouTube, using the official
YouTube Data API v3 (not browser automation). YouTube's own API is a much more
reliable path here than TikTok's or Instagram's -- proper OAuth, no bot-detection
fights, resumable upload built in.

## One-time setup
1. In Google Cloud Console, create (or reuse) a project, enable the **YouTube Data
   API v3**, then under APIs & Services > Credentials create an **OAuth client ID**
   of type **Web application**, with `http://localhost:8080/` added as an
   Authorized redirect URI (required for this client type -- a Desktop app client
   would skip this step, but this project uses a Web application client).
2. Download that client's JSON and save it as `client_secret.json` in this folder
   (gitignored, never commit it).
3. If the OAuth consent screen is still in **Testing** mode, add the channel owner's
   Google account as a test user (Console > OAuth consent screen > Test users) --
   otherwise the login will be blocked, and Testing-mode refresh tokens expire after
   7 days and need `oauth_setup.py` re-run.
4. Run `python oauth_setup.py` once -- opens a real browser for you to log in as the
   channel owner and approve access, then saves `token.json` here (gitignored).
   This step needs an actual human login in a browser; it can't be scripted for you.
5. Custom thumbnails (`thumbnails.set`) additionally require the channel to have
   verified a phone number at youtube.com/verify -- do this once if not done already,
   or uploads will succeed but the thumbnail step will fail with a clear message.

## Scripts
- `oauth_setup.py` -- one-time interactive OAuth login (see above). Re-run only if
  `token.json` is lost or the refresh token is revoked/expired.
- `upload_video.py` -- uploads a video (`videos.insert`, resumable) with title,
  description, tags, category, and privacy status, then sets a custom thumbnail
  (`thumbnails.set`) if `--thumbnail` is given. Defaults to `--privacy private`.

## Quality gates (automatic, `qa/preflight_post.py`)
The upload script runs a pre-flight on its own inputs and exits with code 2, before anything is downloaded or uploaded, if a check fails:
- Caption: not empty, no em dash, no placeholders, within the character limit, no repeated hashtags. Hashtag limits: Facebook 1-3 (the user's rule), IG/TikTok 30 max.
- Video file: 9:16, at least 1280px tall, has audio, within the platform's length limit, h264.
- YouTube (`upload_video.py`): title 1-100 chars, no `<`/`>`, description and tag limits, and the thumbnail must pass `thumbnail-specs`.
Never bypass a failed pre-flight. Fix the input and re-run. Publish itself stays a human click.

## Scope rules
- This folder only handles posting to YouTube. It doesn't decide what to post,
  build the thumbnail (`thumbnail-creation/`), or find outliers (`outlier-tracking/`)
  -- it just takes finished assets and publishes them.
- No CI workflow calls these scripts (OAuth login is interactive and both
  `client_secret.json` and `token.json` are local secrets), so there's no CI path to
  keep in sync here.
