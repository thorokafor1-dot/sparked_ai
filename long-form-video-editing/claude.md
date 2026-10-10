# Long-Form Video Editing

Single job: render finished 16:9 long-form YouTube edits. Each video gets its own subfolder with its own edit definition, because the formats differ too much for one shared pipeline.

## Subfolders
- `talking-head-infield/`: talking head plus spliced infield clips (e.g. "10 Conversation Starters").
  - The edit lives in `edl.py` (edit decision list). `render.py --out output/<name>_vN.mp4` jump-cuts pauses, normalises every segment to 1080p30 / 48k, concatenates, then runs one loudnorm pass. Infield clip audio is street-noise cleaned by DeepFilterNet first (`tools/denoise.py`, 18 dB max reduction, cached in `work/denoised/`); `--no-denoise` uses the raw audio, `--denoise-atten` sets the strength. Every source then gets `PEAK_TAMER` (a post-gain compressor for shouts and laughs). Tame all sources together: taming only one source shifts the average and pushes the others over the 8 LU spike gate.
  - Timestamps come from `work/*.txt` transcripts (`transcribe.py`). Script timestamps have been wrong before (see the `edl.py` docstring), so always verify against the transcript.
  - **One EDL module per take.** `render.py --edl edl_take2` loads that module's camera, mic, sync file, optional second angle (`ANGLE2`, `ANGLE2_SYNC`), caption words and mic thresholds (`SILENCE_DB`, `QUIET_VOICE_DB`). `edl.py` is take 1 and the default. A new take means a new module, not a code change.
  - **Second angle:** the side camera is cropped 1.33x and warm-graded (`SIDE_VF`) to match the main angle. Delivery (cards, intro, close, CTA) stays on the main angle. Explanation pieces cut to the side up to `SIDE_SHARE` (25%) of talking-head time, never twice in a row and never under 1.5s. Force a piece with `angle="side"` or `"main"`. The log prints the achieved share.
  - **Sync and thresholds:** sync each camera to the mic with `sync_mic.py --cam --mic --out`. A mic that isn't noise-gated needs `SILENCE_DB` above its noise floor (the take-2 mic sat at -55 dB, so it uses -46). Otherwise pauses go undetected and dozens of CUT WARNINGs appear.
  - **Final mix runs as two passes** (picture, then sound) that are stream-copied together. In a single graph, take 2 lost 33s of audio samples. `--reuse-segments` redoes only that final pass.
  - **Carrying an edit to a new take:** `retarget_edl.py` word-matches the reference EDL into a new take's transcript. It only works when the new take re-reads the script closely. A paraphrased take (take 2) needs a hand-built EDL from its transcript.
- `monkey-app-longform-01/`: Monkey App long-form. `render.py` builds from `edit.json` (crop, name/age badge lift, punch-ins, SFX and a ducked music bed). Pieces are cached by their parameters, so re-renders only redo what changed.

## Quality gates (automatic, see `qa/checks_video.py`)
Every render in `*/output/` or `*/out/` must pass these before it's presented (only the newest `_vN` gets checked):
- `video-specs`: 16:9 at 1080p or higher, h264/yuv420p, AAC.
- `video-content`: no black screen over 0.5s, no frozen picture over 3s, no dead air over 2s (outside the last 1.5s), and -14 LUFS (allowed -18 to -10).
Open the render automatically for the user once it passes.

## Scope rules
- Raw footage (`raw/`, `input/`), `work/` and `output/` are gitignored. Only code and edit definitions are committed.
- Scripts come from `script-writing/`. This folder executes an edit and doesn't rewrite the script. If the script and footage disagree, fix the EDL and note it in its docstring.
- Shorts are cut in `long-form-to-shorts-video-editing/`, not here.
