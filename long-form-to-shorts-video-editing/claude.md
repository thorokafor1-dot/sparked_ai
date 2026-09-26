# Long-Form to Shorts Video Editing

Single job of this folder: turn long-form video into finished, hook-optimized 9:16 Shorts with burned-in captions, ready to hand off to `ig-posting-automation/` for posting.

This is a parent category, not a single pipeline, the actual editing approach (especially how to reframe the source into 9:16) depends heavily on how the long-form source is shot, so each distinct source format/style gets its own subfolder with a pipeline tuned to it.

## Subfolders
- `monkey-app-video-chat/`, for long-form Monkey-app video-chat call recordings specifically (landscape, persistent two-pane layout that sometimes switches to one person full-screen). See its own `claude.md` for the pipeline.

## Quality gates (automatic, see `qa/`)
Every render in `*/output/*.mp4` and caption file in `*/work/*.ass` is checked before a turn can end (`python qa/run_checks.py --level full <file>` to run by hand):
- `video-specs`: 1080x1920, h264 + yuv420p, 24-60fps, AAC audio present, audio/video lengths match, 5-180s.
- `video-content`: no black screen over 0.5s, no frozen picture over 3s, no dead air over 2s, loudness -18 to -10 LUFS (target -14), true peak at or below -0.5 dBFS.
- `short-face-on-screen` (monkey-app-video-chat): no stretch of 0.5s or more where the crop shows no face.
- `caption-safe-zone`: captions stay between y=153 and y=1536 on the 1920px frame, clear of the Shorts/TikTok/Reels UI.
A render isn't done until these pass. Look at the frames yourself before calling it finished.

## Scope rules
- This folder (and its subfolders) only turn long-form into finished Shorts. Posting decisions live in `ig-posting-automation/`, hook/opener research in `shorts-hook-research/`.
- Before adding a new source style, check whether an existing subfolder's reframe approach actually fits, don't build a new one if the source is really the same two-pane call format.
