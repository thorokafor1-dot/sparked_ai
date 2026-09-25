# TikTok Posting Automation

Single job of this folder: get a finished Short from a Google Drive link onto TikTok.

Uses TikTok's official Content Posting API, not browser automation like the
Facebook/Instagram folders here. Browser automation was tried first (it's what those
two folders use) but TikTok's bot detection blocked login itself in the dedicated
automation Chrome profile — Facebook and Instagram never had this problem. The
Content Posting API sidesteps that entirely, at the cost of needing a one-time
developer app registration and OAuth login before it can post.

## One-time setup
1. Register an app at https://developers.tiktok.com/apps (app name: "Sparked TikTok
   Posting API", registered under "Individual") and add the "Content Posting API"
   product, requesting the `user.info.basic` and `video.publish` scopes.
2. TikTok requires an HTTPS redirect_uri — plain `http://localhost` is rejected.
   `oauth_setup.py`'s default (`https://sparked.thorokafor.com/tiktok-oauth-callback.html`)
   points at a tiny static page in `landing-page/` that immediately forwards the
   browser to the local callback server on `http://localhost:8722/callback` with the
   same query string, so the rest of the flow is unchanged. Register that exact URL
   as the app's Redirect URI.
3. **Production vs. Sandbox have separate credentials.** `TIKTOK_CLIENT_KEY` /
   `TIKTOK_CLIENT_SECRET` (User-level env vars) are the Production app's. Testing
   before the app is approved has to go through the app's **Sandbox** tab instead —
   its own separate Client key/secret are stored as `TIKTOK_SANDBOX_CLIENT_KEY` /
   `TIKTOK_SANDBOX_CLIENT_SECRET`. Sandbox also needs its own copy of every
   Basic Information field (redirect URI, scopes, products) and its own
   **Target Users** entry (Sandbox settings → Add account) for the account being
   tested with.
4. Run `oauth_setup.py` once, passing the Sandbox credentials explicitly until the
   app is approved:
   ```
   python oauth_setup.py --client-key $env:TIKTOK_SANDBOX_CLIENT_KEY --client-secret $env:TIKTOK_SANDBOX_CLIENT_SECRET
   ```
   Opens TikTok's consent screen in your browser, catches the redirect via the relay
   page above, and saves tokens to `tokens.json` next to the scripts (gitignored).
   Note: `$env:VAR` in PowerShell can read a stale cached value if the var was just
   set — use `[Environment]::GetEnvironmentVariable("VAR", "User")` instead, which
   always reads live from the registry.
5. **Unaudited apps can only post to accounts that are themselves set to Private**
   (Settings and privacy → Privacy → Private account in the TikTok app) — separate
   from `upload_short.py`'s own `--privacy-level SELF_ONLY` default. Posting fails
   with `unaudited_client_can_only_post_to_private_accounts` otherwise.

### App review status (in progress)
TikTok's app-review form (Basic Information + App review sections) needs: app icon
(1024x1024px — not yet provided), category (dropdown options not yet captured),
description (drafted: "Automates posting finished short videos to the Sparked Thor
TikTok account using TikTok's Content Posting API."), Terms of Service URL
(https://sparked.thorokafor.com/tos.html — live, verified HTTP 200), Privacy Policy
URL (https://sparked.thorokafor.com/privacy.html — live, verified HTTP 200),
Platforms (check Web only), Products (Login Kit + Content Posting API), Scopes
(`user.info.basic` + `video.publish` only), and a demo video of the full OAuth +
posting flow working in Sandbox mode (needs `oauth_setup.py` + `upload_short.py` to
actually succeed first). Review typically takes anywhere from several days to ~6
weeks per TikTok's own FAQ, and posts stay private-only (`SELF_ONLY`) even after
approval until a separate compliance audit passes.

The real landing page lives in `landing-page/` at the repo root (`index.html`,
`tos.html`, `privacy.html`), auto-deployed to https://sparked.thorokafor.com via
Vercel on push to `main`. Two standalone Claude Artifact pages
(https://claude.ai/artifact/SmrjD5Mp4ZniZXyqBTHXGg and .../DpYRqNq1vpAUqSrijKH9eK)
and an Artifact version of the full landing page
(https://claude.ai/artifact/Go27R6Nwetnk1Wi74fp6A6) were drafted earlier before the
real Vercel-hosted site existed — all superseded, no longer needed for the TikTok
form.

## Scripts
- `oauth_setup.py` — one-time interactive OAuth login (see above). Re-run only if
  `tokens.json` is lost or the refresh token is revoked.
- `upload_short.py` — downloads a video from a Drive link and publishes it to TikTok
  via the Content Posting API: query creator info, init a chunked `FILE_UPLOAD`
  publish, upload the video bytes, poll publish status. Always refreshes the access
  token from the saved refresh token before posting. Never posts without review:
  - `--preview-covers [N]` downloads the video, saves N (default 6) evenly-spaced
    candidate cover-frame PNGs to `cover_previews/` (gitignored), and exits without
    posting — look at them, then pass `--cover-timestamp-ms <ms>` from the chosen
    file's name on the real run (omit to let TikTok auto-pick a frame).
  - Before actually publishing, it always prints the final account, privacy level,
    cover frame choice, and full caption (hashtags included, since TikTok has no
    separate hashtag field — they're just part of the caption text), then requires
    typing `y` at a prompt. Pass `--yes` to skip that prompt once it's already been
    reviewed (e.g. reviewed in chat, then re-run with `--yes` to actually post).
- `post_to_tiktok.bat` — convenience wrapper for `upload_short.py`.

## Important: audit status gates privacy_level
Until the TikTok app passes audit for the `video.publish` scope, the API only accepts
`privacy_level=SELF_ONLY` (post visible only to your own account) — this is TikTok's
restriction, not a limitation of this code. `upload_short.py` defaults to `SELF_ONLY`
and cross-checks `--privacy-level` against the account's actual
`privacy_level_options` (from creator_info) before attempting to publish, failing
fast with the allowed list instead of posting the wrong visibility.

## browser-automation/ (parked, not in use)
`login_chrome_profile.py` and `upload_short.py` there are the Facebook/Instagram-style
Playwright approach. Kept in case TikTok's bot detection or account restrictions ever
loosen up enough to revisit it — not wired into `post_to_tiktok.bat`.

## Scope rules
- This folder only handles posting to TikTok. It doesn't decide *what* to post
  (that's `shorts-hook-research/`) or find outliers (`outlier-tracking/`) — it just
  takes a finished video and publishes it.
- No GitHub Actions workflow calls these scripts (OAuth login is interactive and
  `tokens.json` is a local secret), so there's no CI path to keep in sync here.
