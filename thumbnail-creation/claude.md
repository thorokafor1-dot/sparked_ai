# Thumbnail Creation

Single job of this folder: produce a finished YouTube thumbnail for a long-form video, built from real frames in that video plus packaging cues pulled from the genuine in-person cold-approach outliers in `outlier-tracking/`.

## One-time setup: pulling reference photos from Google Photos
`pull_google_photos.py` needs its own OAuth client (Google Photos Picker API), separate from any other Google API credentials elsewhere in this repo. Credentials live in `.env` (gitignored), not a downloaded `client_secret.json` file, so the raw client secret never sits in a file that gets read back into a conversation:
1. In Google Cloud Console, create/reuse a project, enable the **Google Photos Picker API**, then under APIs & Services > Credentials create an **OAuth client ID** of type **Web application** with `http://localhost:8080/` as an Authorized redirect URI.
2. Add its Client ID and Client Secret to `thumbnail-creation/.env` yourself (same file `OPENAI_API_KEY` already lives in):
   ```
   GOOGLE_OAUTH_CLIENT_ID=...
   GOOGLE_OAUTH_CLIENT_SECRET=...
   ```
3. If the OAuth consent screen is in **Testing** mode, add the account as a test user (Console > OAuth consent screen > Test users).
4. Run `python pull_google_photos.py --setup` once, a real browser opens for you to log in and approve access, saves `token.json` here (gitignored, only a short-lived token pair, not the client secret). Needs an actual human login, can't be scripted.
5. Run `python pull_google_photos.py --out reference/self/`, it opens a picker session and prints a URL, open that URL and select 1-3 clear, well-lit, full-face photos, the script waits, then downloads whatever was picked.

## Contents
- `download_source.py`, same gdown pattern as `long-form-to-shorts-video-editing/download_source.py`, pulls the long-form source from a Drive link into `input/`.
- `extract_candidates.py`, samples frames across a source video (or a bounded window of it) and scores them on face presence/size + a smile-detection bonus, writing top candidates to `work/frames/`. For a long source, bound the scan (`--start`/window) to the segment you actually need instead of scanning the whole file.
- `restore_faces.py`, runs GFPGAN face restoration on one frame. Reach for this when a frame is the *right* moment (best/strongest reaction) but too motion-blurred or low-quality to use as-is, sharpening/denoising in `make_thumbnail.py` can't recover detail a blurry source never captured, but GFPGAN's learned face prior actually reconstructs plausible sharp detail (eyes, teeth, skin texture). Slow on CPU (~10-30s/frame); don't run it on frames that are already sharp. Needs `models/GFPGANv1.4.pth` (auto-downloaded on first use, ~350MB, gitignored).
- `make_thumbnail.py`, composites a chosen frame (or two, side by side) into a finished thumbnail: exposure lift for dark footage, a light natural touch-up (or `--produced-grade` for the heavier vignette/warm-cast look), optional caption. See its module docstring for the full option set (`--frame2` for a two-panel layout, `--fit1/--fit2 contain` to letterbox a frame instead of cropping into it, `--focus-x/-y` to aim the crop).
- `openai_regenerate.py` / `regenerate_scene.py` / `mask_composite.py`, heavier AI-regeneration path (OpenAI `gpt-image-1` edit endpoint, or local Stable Diffusion img2img) for when a frame's real problem is genuine motion blur/noise no amount of restoration can fix. See "Getting AI remakes right" below before reaching for these, the elaborate per-panel masking they implement is usually the wrong first move.
- `generate_concept_mockup.py`, same masked-edit approach as `openai_regenerate.py`, generalized for a video idea that has no footage shot yet: takes a real reference photo of the creator (`reference/self/`) and a text scenario instead of an existing frame, so the AI only invents the background/setting, never the creator's actual likeness. Feeds `video-ideation/strategist/`'s idea-dashboard pipeline.
- `generate_woman.py` + `compose_videochat_thumb.py`, Monkey App / video-chat compilation thumbnails in the channel's classic split layout (AI-generated woman left, creator's posed LED-room photo right, speech bubble, Monkey badge). Gotcha: gpt-image-1's output moderation blocks bikini, lying-on-bed and over-the-shoulder body shots ("sexual"), even with `moderation="low"`. Fitted tank-top selfies pass. Use `--pose screen` + `--me-flip` + `--woman-flip` (gpt-image-1 turns her gaze the wrong way despite the prompt, so check her eyes point across the divider at him) so they face each other like a real call; the bubble auto-places in the top corner that clears her face (haar face detect). The "screen" pose once hallucinated a fake picture-in-picture of another guy, the prompt now forbids it, still eyeball each generation.
- `videochat_thumbnail_strategy.md` + `pull_videochat_refs.py`, the video-chat e-date thumbnail strategy (outlier pattern table, archetypes, copy rules) and the script that rebuilds its reference board from the Video Chat outliers (`work/videochat_refs/`). `pull_channel_thumbs.py` pulls named inspiration channels' recent thumbnails scored against each channel's median, for the text-trend review. The composer's `--his-line`, `--emoji`, `--headline` and `--no-badge` flags implement it. Playbook: `.claude/skills/videochat-thumbnail/`.
- `pull_google_photos.py`, one-time-setup OAuth script that pulls the creator's chosen reference photo(s) out of their personal Google Photos library via the Photos Picker API, see setup steps above.

## Getting AI remakes right
The simple approach beats the elaborate one: composite the full two-panel image first (real frames, `make_thumbnail.py`), then send that *whole* finished image to ChatGPT/`gpt-image-1` with a plain "make this higher quality/photorealistic" prompt -- no manual face-detection masking, no per-panel protect-columns, no moderation-workaround cropping. That one-shot approach produced a cleaner, artifact-free result (no ghosting, no deformed limbs, identity preserved) than the hand-built masking pipeline in `mask_composite.py` did across many attempts. The masking pipeline exists because it's the more *controllable* path when the simple one fails (e.g. moderation blocks a specific frame, or a real person's likeness gets altered and needs to be forced back) -- but reach for it second, not first.

One real gap either way: a consumer ChatGPT image result comes back small (614x342 seen in practice), well under thumbnail resolution. Don't accept that size -- run it through Real-ESRGAN (`models/RealESRGAN_x4plus.pth`, same model `restore_faces.py` uses) to reach true 1920x1080. That upscale held up cleanly (real leaf/light detail, no smearing) because the source was already clean; it won't fix a source that's actually blurry or artifacted going in.

## Known environment gotcha
`gfpgan`'s dependency `basicsr` imports `torchvision.transforms.functional_tensor`, which newer `torchvision` removed. Fixed locally by patching `basicsr/data/degradations.py`'s import to `from torchvision.transforms.functional import rgb_to_grayscale`, if `gfpgan` is reinstalled/upgraded and breaks again, reapply that one-line patch rather than downgrading torchvision (this project's other tools depend on the current version).

## Two-panel layout for vertically-shot source video
Most source clips here are vertical phone video pillarboxed into a 16:9 file (e.g. 817px of real content in a 1920 or 2560-wide frame). A single full-width 16:9 crop needs heavy upscaling and magnifies any softness in the source. Splitting into two side-by-side panels (`--frame2`) roughly halves the needed scale factor per panel and doubles as a natural way to show two different people from the same video. Still pick each panel's frame for real sharpness first (or restore it with `restore_faces.py`), don't rely on the smaller crop alone to fix a bad source frame.

## Picking the frame: strong reaction + genuinely sharp, not just "available"
A calm/neutral expression under-performs a genuine reaction (surprise, big laugh, intense eye contact) even when the calm one is easier to find sharp. Scan a segment for smile/face detection *and* sharpness (`cv2.Laplacian(...).var()`) together, and prefer the strongest reaction whose sharpness can be salvaged (light processing, or `restore_faces.py` if needed) over a safer-but-flatter shot that's merely convenient.

## Outlier reference used for style
Source of truth is `outlier-tracking/niche-long-form/data.json`, filtered to `format == "In-Person"` (not the Video Chat / Omegle / Monkey App rows also in that file, and not the noisier general dashboard mix). A few actual reference thumbnails are saved locally in `reference/` for side-by-side comparison. Winning pattern across genuine in-person/infield entries (Alex León, John Savvy, Marvin Goodly, Coach Kyle, Todd V, Dating With Nishant): natural lighting left alone (no vignette, no warm color-cast overlay), medium/wide framing that keeps body language and context in frame rather than a tight face crop, and minimal or no caption text (a single word, a short stat, or nothing at all). This is deliberately *not* the heavier produced look (bold all-caps drop-shadow caption, warm grade, vignette) seen on compilation/collage-style channels like Brad Dating Lifestyle or ApproachCraft, that pattern doesn't fit this niche's authenticity branding. `--produced-grade` in `make_thumbnail.py` opts into that heavier look if a future video actually calls for it.

## Storage
Downloaded source videos are temporary, same as `long-form-to-shorts-video-editing/`, don't let raw `input/*.mp4` pile up on disk. `models/*.pth` (GFPGAN weights) are also gitignored/local-only. Only the extracted candidate frames (small) and finished thumbnail PNGs in `output/` persist.

## Quality gates (automatic, see `qa/checks_image.py`)
Every image in `output/` (except `*options*`, `*comparison*`, `*sheet*`, `*grid*` boards) must pass `thumbnail-specs` before it's presented:
- 16:9 and at least 1280x720, and under 2MB (YouTube's hard limit; export the final as JPG at about quality 90).
- A clear main face at least 12% of the frame height, with main-face sharpness of 100 or higher. Calibrated on this folder's history: the finals picked (`meet9_FINAL*`) score 350+, and rejected soft drafts score under 70.
- Not so dark that it turns to mud in the feed (mean brightness 30/255 or higher).
Then run the `critic` subagent on the finished thumbnail (it views it at mobile size) before showing it.

## Scope rules
- This folder only builds thumbnails. It doesn't decide what to post (`ig-posting-automation/`), doesn't find outliers (`outlier-tracking/`), and doesn't edit the video itself (`long-form-to-shorts-video-editing/`).
- No CI workflow, runs locally, needs ffmpeg + opencv-python + gfpgan/torch (already in `requirements.txt`).
