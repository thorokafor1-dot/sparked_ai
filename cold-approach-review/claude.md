# Cold Approach Review

Single job: turn the user's real cold-approach audio sessions (Wireless GO `.wav`s) into readable transcripts for coaching review and content mining.

## Pipeline
1. `download_all.py`: pulls each session's `.wav` from Drive into `input/<session>/`. The links are hardcoded because it's a one-off; add new sessions there.
2. `transcribe_all.py [--model-size small]`: produces segment-level `{start, end, text}` JSON in `work/<session>/`. Segment-level is enough for review and faster than word-level.
3. `to_text.py`: flattens the JSON into timestamped `.txt` files in `work/<session>/`. Read these, not the JSON, because they're cheaper.
4. `prep_notes.html`: the review/notes page built from the transcripts.

## Quality gates
- The generic `qa/` checks run on code and notes.
- In any review or notes, her side of the conversation is described directionally. Never quote or invent her words (no-fabricated-dialogue rule).

## Scope rules
- Audio (`input/`) and transcripts (`work/`) stay local and gitignored. They're private recordings of real people.
- Review only. Editing footage belongs in `long-form-video-editing/` / `long-form-to-shorts-video-editing/`, and ideas go to `video-ideation/video_ideas.md`.
