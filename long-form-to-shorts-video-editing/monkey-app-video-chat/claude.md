# Monkey App Video Chat Editing

Single job of this folder: turn a long-form Monkey-app video-chat call recording into finished, hook-optimized 9:16 Shorts with burned-in captions and a dynamic reframe of the call's two-pane layout, ready to hand off to `ig-posting-automation/` for posting.

This editing style (the two-pane reframe logic specifically) only applies to this Monkey-app call-recording format, a landscape recording that normally shows a persistent two-pane layout (main subject's tile + a smaller host tile) but sometimes switches to one person full-screen. A differently-shot long-form source (single fixed camera, screen recording, etc.) would need a different reframe approach, which is why this lives in its own subfolder under `long-form-to-shorts-video-editing/` rather than at that folder's top level.

## Contents
- `download_source.py`, pulls the long-form video from a Drive link (gdown) into `input/`.
- `transcribe.py`, local faster-whisper, word-level timestamps, no API key needed.
- `analyze_hooks.py`, within a given segment window, scores candidate ~3s starts on text signal (direct address/questions/niche hook words) + visual signal (OpenCV face/smile detection) and picks the strongest one.
- `captions.py`, builds the burned-in caption style copied from the reference short: 2-3 word phrases, bold all-caps, white text with a hot-pink karaoke-style sweep across the word currently being spoken. Vertical position shifts by layout (lower-third for a solo shot, pulled up to the seam for a stacked two-person shot) via a `y_at(t)` callback.
- `reframe.py`, the two-pane detection logic (YuNet face detector, `models/face_detection_yunet.onnx`). Every 0.2s it searches the main (left) and host (right) regions and classifies the instant as `main` / `host` / `split` / `none`:
  - Two results closer than ~350px are one face straddling both search regions (full-screen shot), not a split.
  - `none` = a meme/reaction cutaway spliced into the call. Since 2026-10-02 spotted by ORB-matching his room's two posters against `assets/host_room_ref.png` (visible in every call layout, never in a meme); the old dark-top-margin / saturation test is only a fallback when that asset is missing, because it misread her warm-lit room as a meme. Re-grab the ref frame if he films in a different room.
  - States and positions are smoothed (`smooth_states`, `smooth_positions`) and looked up through `PositionTrack`.
- `render_short.py`, builds the crop plan and burns in captions via ffmpeg's `ass` filter, in one encode pass. The plan is simplified so it never cuts without a reason: adjacent chunks of the same person are one shot whose crop pans smoothly (`_solo_pan_crop`), it cuts only where the tracked person really switches (`CUT_JUMP`), sub-0.7s blips are absorbed (`MIN_SHOT`), and cutaway edges snap to the real frame. Meme cutaways get no captions and fill the frame with a blurred backdrop. Detections are cached in `work/*_samples.json`. Every render writes `<name>.render.json` (inputs plus the `cutaways` spans).
- `verify_face_presence.py` / `verify_cuts.py` / `verify_transitions.py`, the checks behind the gates below (face on screen, cut rhythm, boundary contact sheets).
- `find_moments.py`, Claude scores the whole transcript in overlapping windows against a fixed 0-100 rubric (hook, payoff, flirt priority, stands alone), then takes the global top N, dedupes overlaps and snaps edges to word boundaries. Mechanics borrowed from OpenShorts (github.com/mutonby/openshorts).
- `run_pipeline.py`, orchestrates all of the above, either for `--segment start:end` windows or `--auto N` (Claude's N best moments).

## Quality gates
Renders in `output/` must pass (run automatically by the hooks, or `python qa/run_checks.py --level full <file>`): `video-specs`, black/frozen/silent/loudness checks, `short-face-on-screen` (no stretch of 0.5s+ without a face in the crop; the endscreen's own no-face tail is exempt, occlusion gaps that come back in the same place are ignored), `short-jumpy-cuts` (no shot under 0.5s, no burst of 4+ hard cuts in 2s; cuts inside a meme or the opening hook's own known seam are ignored -- see `_hook_seam_span` in render_short.py), `short-frozen-half` (a stacked half with motion on only one side), and `short-lone-frame` (a single frame with a large jump on BOTH sides -- "the cut wasn't adjusted yet"; see render_short.py's `_refine_pan_snap`/`_refine_split_boundaries` for the fix pattern and verify_lone_frames.py for the check).

## Storage
Downloaded source videos are temporary. `run_pipeline.py` deletes the source video from `input/` once it's finished rendering the requested shorts (pass `--keep-source` to retain it) -- these Drive downloads run to ~1GB and shouldn't pile up on disk. Only `work/*_transcript.json` (small) and the finished clips in `output/` persist.

## Current test scope
Testing on the first 2 "girl" segments only. Segment boundaries (which portion of the long-form video belongs to which girl) are identified manually, there's no automatic speaker/person segmentation yet, and passed in via `--segment start:end`. Hook selection *within* each given segment is automatic, though the auto-picked start isn't always visually verified to open on the right person, worth a manual spot-check before trusting a new hook blindly.

## Not yet built (Phase 2)
- Reaction/cutaway clip splicing (like the WWE/anime meme inserts in the reference) and the ID-card-style prop insert, need a local library of the user's own reaction clips, since the reference's clips can't be reused directly.
- Automatic speaker boundary detection (moment selection is automated via `--auto`, but the transcript still has no speaker labels).
- The reference's zoom/blur punch transition between caption phrases.
- The reframe pane split (`main_frac=0.72` in `reframe.py`) is a hardcoded estimate of where the source's main/host video tiles divide -- works for this source's layout but may need adjusting for a differently-composed source.
- Face detection is Haar-cascade based (OpenCV, no extra model download) -- it's not identity-aware, so it can't distinguish "this pane-sized face is her" from "this pane-sized face is him" by appearance, only by which pane/position it's in. Good enough for this source's layout but a real limitation if a future source doesn't follow the same left/right convention consistently.

## Scope rules
- This folder only turns a Monkey-app call recording into finished Shorts. It doesn't decide what to post or post it (`ig-posting-automation/`) and doesn't do hook/opener research (`shorts-hook-research/`).
- No CI workflow, runs locally like `ig-posting-automation/` (needs local whisper models + ffmpeg).
