---
name: post-short
description: Post a finished short to Facebook, Instagram, TikTok and/or YouTube in one batch. Use whenever the user wants to post, publish, upload or cross-post a short or reel.
---

# Post a short (all platforms, one batch)

## Inputs (infer before asking)
- **Drive link** for the video (FB/IG/TikTok download from Drive). For YouTube, the local file path.
- **Base caption.** Write it yourself from the short's hook if none is given, then run it past the `critic`.
- **Platforms.** Default to all four unless the user names some.

## Steps
1. **Write one caption per platform** from the base caption, saved as `posting-automation/<platform>-posting-automation/caption.txt` (`--caption-file` avoids shell quoting).
   - Hashtags: Facebook 1-3 (user rule); IG 3-5; TikTok 3-5.
   - No em dashes.
   - The pre-flight rejects anything else, so get it right the first time.
2. **Pick the cover once and reuse it.** Build the IG/FB/TikTok cover with `python posting-automation/make_cover.py --video <source> --time <s> --center-x <face x> [--lift 1.2] --out posting-automation/ig-posting-automation/cover_<name>.png`: a clean full-bleed frame, no text (user rule). Pick the frame from the SOURCE (no burned captions): her face, eyes open, head level, smiling. `--lift` for a dim room.
   - TikTok: `python upload_short.py --drive-link <L> --caption-file caption.txt --preview-covers`, then choose the frame with a sharp face and a strong reaction (wide eyes, direct look, not neutral).
   - FB/IG: use the same frame as `--cover-image`.
3. **Run each platform** from its folder (the pre-flight runs automatically and exits with code 2 on bad input; fix the input and re-run, never bypass it):
   - Facebook: `python upload_short.py --page-url "https://www.facebook.com/profile.php?id=61576485249329" --drive-link <L> --caption-file caption.txt --cover-image <png>`
   - Instagram: `python upload_short.py --drive-link <L> --caption-file caption.txt --cover-image <png>`
   - TikTok: `python upload_short.py --drive-link <L> --caption-file caption.txt --cover-timestamp-ms <ms>` (confirm first; `--yes` only after the user OKs the cover)
   - YouTube: use the `_youtube.mp4` render (SUBSCRIBE endscreen, see make-short). `python upload_video.py --video <mp4> --title "<title>" --description "<desc>" --privacy private`
4. **The final Publish click stays with the user** (FB/IG never auto-publish). Report what's queued on each platform and where to click.

## Scheduling (default: schedule, don't post now)
The user schedules uploads. Each platform runs on its own; FB and IG stay separate, never cross-posted through Business Suite (user, 2026-10-02).
- Facebook: add `--schedule "YYYY-MM-DD HH:MM"` (local time). It fills Scheduling options -> Date/Time; the user clicks "Schedule for later", then the final button.
- Instagram: add `--schedule "YYYY-MM-DD HH:MM"`. It turns on "Schedule content" and sets date/time; the dialog's Share button becomes Schedule (the user's click).
- YouTube: `upload_video.py ... --publish-at "YYYY-MM-DD HH:MM"` uploads private and auto-publishes. Show the user the thumbnail frame AND the designed cover BEFORE uploading (user rule).
- TikTok: run `python posting-automation/tiktok-posting-automation/prep_studio_upload.py --video <mp4> --cover <png>` (pre-flight, caption to clipboard emoji-safe, cover copied next to the video, Explorer + TikTok Studio opened). **Always paste the full TikTok caption (description + hashtags) in chat as a copy-paste code block in the same reply, unasked (user rule, 2026-10-04).** The user drives the upload (and Studio's own scheduler) and says when they reach the cover screen.
- `--debug-port <n>` on the FB/IG scripts exposes Chrome DevTools: probe or fix selectors live with `playwright.chromium.connect_over_cdp("http://localhost:<n>")` while the script waits, instead of re-uploading. That's how both schedule steps were verified.

## Gotchas (keep this list updated)
- **YouTube Shorts: skip `--thumbnail` for webcam/video-chat shorts (2026-10-04).** The pre-flight's `thumbnail-specs` face-sharpness gate (tuned for long-form thumbnails) rejects soft webcam frames (scored 9 vs 20+). The API thumbnail only affects search/embeds anyway; the Shorts feed uses the in-app frame picker, so upload without it and give the user the picker timestamp.
- **Run the browser posting scripts ONE AT A TIME, and with `run_in_background` + `timeout: 7200000` (2026-10-02).** The default 30-min background limit killed the FB script while the draft waited for the user's click, and that closed its browser and lost the draft. Running FB and IG at once slowed both: FB's Create-reel dialog took >20s, the retry opened a second dialog over the video, and IG's post-cover Next was swallowed (IG now retries it).
- **Caption hook must match the game's real logic (2026-10-02):** the critic suggested "keep a straight face or it's a kiss", which inverts what he actually said (keep a straight face and you owe me a kiss). Check any critic rewrite against the transcript before using it; quote his real words.
- **FB cover picker:** the preview tiles aren't clickable. It's a hidden `<input type=range>` (0-1000) that has to be set through the native value setter plus input/change events. This is already handled in `upload_short.py`.
- **FB/IG Chrome sessions expire:** run `login_chrome_profile.py` once to fix.
- **IG local file:** `upload_short.py --video <mp4>` posts a fresh render directly (no Drive round-trip). IG Chrome profile is `--profile-directory "Profile 4"` (account sparked_thor).
- **IG flow (verified 2026-10-01):** an expired session lands on login; the script now waits up to 5 min for the user to log in (never click by generic text there, it opened someone else's post). A "video posts are now shared as reels" OK notice can cover the crop screen; it's dismissed first. The cover is set through the cover screen's own `input[type=file][accept*=image]`. Captions with emoji need UTF-8 stdout (handled in the script).
- **Covers (user, 2026-10-02):** a clean frame from the video, her filling the full 9:16 cover. NO text, NO blurred padding (`make_cover.py` with no --line1/--top-pad). Pick an eyes-open, head-level frame by eye (sharpest-by-score picked a mid-blink), cropped from the source so no burned captions.
- **FB (2026-10-01):** the Page URL is `profile.php?id=61576485249329` (`/SparkedThor` is not ours). The script waits for login and takes `--video`. **Cover bug FIXED 2026-10-02:** the Edit thumbnail dialog's file input accepts `.png,.jpg,.jpeg` (not `image/*`), so the old selector never matched; the script now sets that input, confirms the button flips to Remove, then Saves.
- **YouTube gets its own render:** `render_short.py ... --endscreen youtube --out <name>_youtube.mp4` (the SUBSCRIBE card). Keep the default brand-endscreen file for IG/FB/TikTok. Always hand the user the best frame's timestamp for the app's Shorts thumbnail picker (see below); otherwise YouTube auto-picks a random frame. On a Short the TITLE is the on-video caption (the description is hidden), so the comment-bait question goes in the title: `<hook> <emoji> <comment question> 👇`, 100 chars max. A YouTube "draft" means `--privacy private`; the user flips it public in Studio. Pass the description through UTF-8 (`PYTHONIOENCODING=utf-8`) because it carries emoji.
- **YouTube Shorts thumbnail (2026-10-01):** the Shorts feed and Studio use the frame picked in the YouTube app's Shorts thumbnail picker, and there's no API for it. `thumbnails.set` succeeds but only changes the served /vi/ image (search, embeds), so Studio stays blank. So: pick the best frame of the actual video (her eyes open, head level, sharp) and give the user the exact timestamp to select in the app. Optionally also `--video-id <id> --thumbnail <jpg>` with that same frame, caption-free. IG/FB use the designed cover.
- **TikTok, for now (2026-10-02):** the API can't post publicly. tokens.json is the Sandbox app, and the Production review was never submitted (it still needs a 1024px icon and a demo video). Least friction: the user uploads in TikTok Studio web (tiktok.com/tiktokstudio/upload) in their normal Chrome. Prep it for them: copy the caption to the clipboard, open Explorer with the mp4 selected, and open the upload page. Cover: Edit cover, then Upload cover with the IG/FB cover PNG, then Save. On their short right-hand monitor the Save button is off-screen, so zoom the page to 80% first. Post stays the user's click.
- **TikTok privacy:** posts are `SELF_ONLY` until the app passes TikTok's audit (see the tiktok folder's claude.md).
