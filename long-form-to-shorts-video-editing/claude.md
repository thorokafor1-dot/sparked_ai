# Long-Form to Shorts Video Editing

Single job of this folder: turn long-form video into finished, hook-optimized 9:16 Shorts with burned-in captions, ready to hand off to `ig-posting-automation/` for posting.

This is a parent category, not a single pipeline — the actual editing approach (especially how to reframe the source into 9:16) depends heavily on how the long-form source is shot, so each distinct source format/style gets its own subfolder with a pipeline tuned to it.

## Subfolders
- `monkey-app-video-chat/` — for long-form Monkey-app video-chat call recordings specifically (landscape, persistent two-pane layout that sometimes switches to one person full-screen). See its own `claude.md` for the pipeline.

## Scope rules
- This folder (and its subfolders) only turn long-form into finished Shorts. Posting decisions live in `ig-posting-automation/`, hook/opener research in `shorts-hook-research/`.
- Before adding a new source style, check whether an existing subfolder's reframe approach actually fits — don't build a new one if the source is really the same two-pane call format.
