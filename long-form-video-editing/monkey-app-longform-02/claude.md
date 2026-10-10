# Monkey App long-form edit (Jammer / Jay Throck style)

Turns a raw OBS screen recording of Monkey App calls into a retention-paced 16:9 compilation
with punch-in zooms, word-by-word captions, rotated SFX, meme/emoji pops and ducked music.
Playbook: `.claude/skills/monkey-longform/SKILL.md`.

## Files
- `transcribe.py`: faster-whisper small.en, word timestamps -> `work/transcript.json`
- `diarize.py`: tags ME/HER per word by pitch (creator ~100-145 Hz, women ~190-285 Hz; split at 165)
- `words.py START END ...`: prints word timings (`@time` + M/H) for picking exact cuts
- `build_edit.py`: the cut list. Clips, fx cues, sections, music. Writes `edit.json`
- `retranscribe.py`: medium.en on only the kept ranges, for caption accuracy
- `render.py [edit.json] [--preview A B]`: renders `out/<name>.mp4`
- Assets: `sfx/<category>_<id>.mp3` (Mixkit, free for YouTube; retired loud ones in `sfx_unused/`), `clips/` reaction clips (Mixkit stock), `music/` (Mixkit, not Content ID registered),
  `memes/` (imgflip stills), `emoji/` (Twemoji PNGs), `fonts/` (Montserrat, OFL)
- Gitignored: `raw/`, `work/`, `out/`

## Layout constants (render.py)
Browser recording 1280x720: Monkey video area is `crop=1280:614:0:72`. Her name/age badge sits in the
top-left 330x80 of that crop and is always blurred. Zoom presets are `(zoom, cx, cy)` in crop coordinates.

## Quality gates
Outputs in `out/*.mp4` go through `qa/checks_video.py` (video-specs, video-content):
- 1920x1080 h264 yuv420p, AAC audio, -14 LUFS, true peak under -0.5 dBTP
- no dead air under -50 dB, no black or frozen stretches, no loudness spikes (momentary > integrated + 8 LU)
- audio and video the same length, both declared and as real sample count (catches AAC concat drift)
`package.md` goes through `title-overclaim` (qa/checks_text.py) and the critic agent.
Manual, per video: phone numbers, handles or other personal info spoken on the call are cut entirely;
no calls with minors.
