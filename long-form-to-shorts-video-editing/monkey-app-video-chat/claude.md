# Monkey App Video Chat Editing

Single job of this folder: turn a long-form Monkey-app video-chat call recording into finished, hook-optimized 9:16 Shorts with burned-in captions and a dynamic reframe of the call's two-pane layout, ready to hand off to `ig-posting-automation/` for posting.

This editing style (the two-pane reframe logic specifically) only applies to this Monkey-app call-recording format — a landscape recording that normally shows a persistent two-pane layout (main subject's tile + a smaller host tile) but sometimes switches to one person full-screen. A differently-shot long-form source (single fixed camera, screen recording, etc.) would need a different reframe approach, which is why this lives in its own subfolder under `long-form-to-shorts-video-editing/` rather than at that folder's top level.

## Contents
- `download_source.py` — pulls the long-form video from a Drive link (gdown) into `input/`.
- `transcribe.py` — local faster-whisper, word-level timestamps, no API key needed.
- `analyze_hooks.py` — within a given segment window, scores candidate ~3s starts on text signal (direct address/questions/niche hook words) + visual signal (OpenCV face/smile detection) and picks the strongest one.
- `captions.py` — builds the burned-in caption style copied from the reference short: 2-3 word phrases, bold all-caps, white text with a hot-pink karaoke-style sweep across the word currently being spoken. Vertical position shifts by layout (lower-third for a solo shot, pulled up to the seam for a stacked two-person shot) via a `y_at(t)` callback.
- `reframe.py` — the two-pane detection/reframe logic. Classifies each sampled instant as `main` / `host` / `split` / `none`:
  - A full-frame (pane-unrestricted) face check runs first and takes priority whenever a face is large enough to be a full-screen close-up, so a genuine full-screen shot is never mistakenly cropped half-from-one-pane-half-from-the-other.
  - Otherwise checks each pane (host pane detection is upscaled 2x since it's narrow, with strict thresholds to avoid false-positiving on the textured poster/wall background there).
  - When neither is found, a color-histogram comparison against frames already confirmed to be the call layout decides whether this is still the same room (undetected angle -- composite as `split`) or genuinely different content (a meme/reaction cutaway -- `none`, shown full-frame untouched).
  - Each pane's x-position is tracked continuously across the whole clip (a momentary miss holds the nearest real detection rather than a blind static guess) and every crop is bounded to its own pane's actual width, so a half-stack crop can never bleed into the other person's side.
- `render_short.py` — builds the dynamic reframe + burns in captions via ffmpeg's `ass` filter, in one encode pass.
- `run_pipeline.py` — orchestrates all of the above for one or more `--segment start:end` windows.

## Storage
Downloaded source videos are temporary. `run_pipeline.py` deletes the source video from `input/` once it's finished rendering the requested shorts (pass `--keep-source` to retain it) -- these Drive downloads run to ~1GB and shouldn't pile up on disk. Only `work/*_transcript.json` (small) and the finished clips in `output/` persist.

## Current test scope
Testing on the first 2 "girl" segments only. Segment boundaries (which portion of the long-form video belongs to which girl) are identified manually — there's no automatic speaker/person segmentation yet — and passed in via `--segment start:end`. Hook selection *within* each given segment is automatic, though the auto-picked start isn't always visually verified to open on the right person — worth a manual spot-check before trusting a new hook blindly.

## Not yet built (Phase 2)
- Reaction/cutaway clip splicing (like the WWE/anime meme inserts in the reference) and the ID-card-style prop insert — need a local library of the user's own reaction clips, since the reference's clips can't be reused directly.
- Automatic segment/speaker boundary detection.
- The reference's zoom/blur punch transition between caption phrases.
- The reframe pane split (`main_frac=0.72` in `reframe.py`) is a hardcoded estimate of where the source's main/host video tiles divide -- works for this source's layout but may need adjusting for a differently-composed source.
- Face detection is Haar-cascade based (OpenCV, no extra model download) -- it's not identity-aware, so it can't distinguish "this pane-sized face is her" from "this pane-sized face is him" by appearance, only by which pane/position it's in. Good enough for this source's layout but a real limitation if a future source doesn't follow the same left/right convention consistently.

## Scope rules
- This folder only turns a Monkey-app call recording into finished Shorts. It doesn't decide what to post or post it (`ig-posting-automation/`) and doesn't do hook/opener research (`shorts-hook-research/`).
- No CI workflow — runs locally like `ig-posting-automation/` (needs local whisper models + ffmpeg).
