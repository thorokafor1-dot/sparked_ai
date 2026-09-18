# Thumbnail Creation

Single job of this folder: produce a finished YouTube thumbnail for a long-form video, built from real frames in that video plus packaging cues pulled from the genuine in-person cold-approach outliers in `outlier-tracking/`.

## Contents
- `download_source.py` — same gdown pattern as `long-form-to-shorts-video-editing/download_source.py`, pulls the long-form source from a Drive link into `input/`.
- `extract_candidates.py` — samples frames across a source video (or a bounded window of it) and scores them on face presence/size + a smile-detection bonus, writing top candidates to `work/frames/`. For a long source, bound the scan (`--start`/window) to the segment you actually need instead of scanning the whole file.
- `restore_faces.py` — runs GFPGAN face restoration on one frame. Reach for this when a frame is the *right* moment (best/strongest reaction) but too motion-blurred or low-quality to use as-is — sharpening/denoising in `make_thumbnail.py` can't recover detail a blurry source never captured, but GFPGAN's learned face prior actually reconstructs plausible sharp detail (eyes, teeth, skin texture). Slow on CPU (~10-30s/frame); don't run it on frames that are already sharp. Needs `models/GFPGANv1.4.pth` (auto-downloaded on first use, ~350MB, gitignored).
- `make_thumbnail.py` — composites a chosen frame (or two, side by side) into a finished thumbnail: exposure lift for dark footage, a light natural touch-up (or `--produced-grade` for the heavier vignette/warm-cast look), optional caption. See its module docstring for the full option set (`--frame2` for a two-panel layout, `--fit1/--fit2 contain` to letterbox a frame instead of cropping into it, `--focus-x/-y` to aim the crop).

## Known environment gotcha
`gfpgan`'s dependency `basicsr` imports `torchvision.transforms.functional_tensor`, which newer `torchvision` removed. Fixed locally by patching `basicsr/data/degradations.py`'s import to `from torchvision.transforms.functional import rgb_to_grayscale` — if `gfpgan` is reinstalled/upgraded and breaks again, reapply that one-line patch rather than downgrading torchvision (this project's other tools depend on the current version).

## Two-panel layout for vertically-shot source video
Most source clips here are vertical phone video pillarboxed into a 16:9 file (e.g. 817px of real content in a 1920 or 2560-wide frame). A single full-width 16:9 crop needs heavy upscaling and magnifies any softness in the source. Splitting into two side-by-side panels (`--frame2`) roughly halves the needed scale factor per panel and doubles as a natural way to show two different people from the same video. Still pick each panel's frame for real sharpness first (or restore it with `restore_faces.py`) — don't rely on the smaller crop alone to fix a bad source frame.

## Picking the frame: strong reaction + genuinely sharp, not just "available"
A calm/neutral expression under-performs a genuine reaction (surprise, big laugh, intense eye contact) even when the calm one is easier to find sharp. Scan a segment for smile/face detection *and* sharpness (`cv2.Laplacian(...).var()`) together, and prefer the strongest reaction whose sharpness can be salvaged (light processing, or `restore_faces.py` if needed) over a safer-but-flatter shot that's merely convenient.

## Outlier reference used for style
Source of truth is `outlier-tracking/niche-long-form/data.json`, filtered to `format == "In-Person"` (not the Video Chat / Omegle / Monkey App rows also in that file, and not the noisier general dashboard mix). A few actual reference thumbnails are saved locally in `reference/` for side-by-side comparison. Winning pattern across genuine in-person/infield entries (Alex León, John Savvy, Marvin Goodly, Coach Kyle, Todd V, Dating With Nishant): natural lighting left alone (no vignette, no warm color-cast overlay), medium/wide framing that keeps body language and context in frame rather than a tight face crop, and minimal or no caption text (a single word, a short stat, or nothing at all). This is deliberately *not* the heavier produced look (bold all-caps drop-shadow caption, warm grade, vignette) seen on compilation/collage-style channels like Brad Dating Lifestyle or ApproachCraft — that pattern doesn't fit this niche's authenticity branding. `--produced-grade` in `make_thumbnail.py` opts into that heavier look if a future video actually calls for it.

## Storage
Downloaded source videos are temporary, same as `long-form-to-shorts-video-editing/` — don't let raw `input/*.mp4` pile up on disk. `models/*.pth` (GFPGAN weights) are also gitignored/local-only. Only the extracted candidate frames (small) and finished thumbnail PNGs in `output/` persist.

## Scope rules
- This folder only builds thumbnails. It doesn't decide what to post (`ig-posting-automation/`), doesn't find outliers (`outlier-tracking/`), and doesn't edit the video itself (`long-form-to-shorts-video-editing/`).
- No CI workflow — runs locally, needs ffmpeg + opencv-python + gfpgan/torch (already in `requirements.txt`).
