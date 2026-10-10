# Infield night 2026-04-17: long-form edit

A retention-paced 16:9 compilation of one night's raw infield approaches. Playbook: `.claude/skills/infield-night/SKILL.md`.
The pipeline is copied from `monkey-app-longform-02` (cutaways, captions, music, brand sting, outro) and runs on a combined source.

## Files
- `build_source.py`: the kept approach ranges (`SEGMENTS`) concatenated into `raw/raw.mkv` (vertical 1080x1920 h264, synced Wireless GO mic audio), `raw/segments.json`, `work/audio16k.wav`
- `transcribe.py`, `diarize.py`, `retranscribe.py`, `words.py`: same as the Monkey long-form
- `build_edit.py`: the cut list (teaser, approaches C, A, B, E, F), base framing and pushes, auto lift for dark clips, cutaways, music. Writes `edit.json`
- `render.py`: Monkey renderer with the vertical layout (`frame_chain`: the shot full height over a blurred copy of itself) and `LIFT`
- `check_her_visible.py`: face check on the zoomed, lifted window, run by `render.py`
- `triage_notes.md`: what each raw clip contains
- Gitignored: `raw/`, `work/`, `out/`

## Quality gates
- `out/*.mp4` goes through `qa/checks_video.py` (video-specs, video-content): 1920x1080 h264/AAC, -14 LUFS, no black or frozen stretches, no dead air, no loudness spikes, A/V length match
- `render.py` refuses to render if `check_her_visible.py` flags a clip with no visible face
- `build_edit.py` must print no `WARN` lines, and the cutaway audit must show each reaction right after its line
- Spoken personal info (numbers, handles) gets cut or bleeped. Never caption a line the transcript can't support.
