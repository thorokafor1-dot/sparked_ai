# Long-Form Video Editing

Single job: render finished 16:9 long-form YouTube edits. Each video gets its own subfolder with its own edit definition, because the formats differ too much for one shared pipeline.

## Subfolders
- `talking-head-infield/`: talking head plus spliced infield clips (e.g. "10 Conversation Starters").
  - The edit lives in `edl.py` (edit decision list). `render.py --out output/<name>_vN.mp4` jump-cuts pauses, normalises every segment to 1080p30 / 48k, concatenates, then runs one loudnorm pass.
  - Timestamps come from `work/*.txt` transcripts (`transcribe.py`). Script timestamps have been wrong before (see the `edl.py` docstring), so always verify against the transcript.
- `monkey-app-longform-01/`: Monkey App long-form. `render.py` builds from `edit.json` (crop, name-badge blur, punch-ins, SFX and a ducked music bed). Pieces are cached by their parameters, so re-renders only redo what changed.

## Quality gates (automatic, see `qa/checks_video.py`)
Every render in `*/output/` or `*/out/` must pass these before it's presented (only the newest `_vN` gets checked):
- `video-specs`: 16:9 at 1080p or higher, h264/yuv420p, AAC.
- `video-content`: no black screen over 0.5s, no frozen picture over 3s, no dead air over 2s (outside the last 1.5s), and -14 LUFS (allowed -18 to -10).
Open the render automatically for the user once it passes.

## Scope rules
- Raw footage (`raw/`, `input/`), `work/` and `output/` are gitignored. Only code and edit definitions are committed.
- Scripts come from `script-writing/`. This folder executes an edit and doesn't rewrite the script. If the script and footage disagree, fix the EDL and note it in its docstring.
- Shorts are cut in `long-form-to-shorts-video-editing/`, not here.
