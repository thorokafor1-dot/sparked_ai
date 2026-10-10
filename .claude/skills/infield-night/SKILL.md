---
name: infield-night
description: Pull a night of raw infield footage (Google Photos share links + Wireless GO mic WAVs on Drive), sync every clip to the mic, transcribe, and triage which clips have real interactions vs nothing. Use when the user shares infield/approach footage links or asks to sort, sync or edit a night of takes.
---

# Infield night: fetch, sync, triage

## Inputs
- One or more `photos.app.goo.gl/...` share links (often one album per clip).
- A Drive folder of Wireless GO WAVs (`0000N_Wireless GO.WAV`). **Always use the mic audio, never the phone audio.**
- **Exception, early archive footage only** (e.g. the March 2026 mall approaches, shot before he used a mic): run `prep_night.py <night> --phone-audio` and skip steps 3-4. Every current session has a mic, so for new footage always ask for the WAV folder if it's missing; never fall back to phone audio on your own.

## Steps
1. Night folder: `long-form-video-editing/infield-night-<YYYY-MM-DD>/` (`raw/` and `work/` are gitignored).
2. Clips: `python tools/gphotos_fetch.py --out <night>/raw <link> [<link> ...]`. Files are named by capture time. Re-running skips files already downloaded.
3. Mic: list the Drive folder with `mcp__claude_ai_Google_Drive__search_files` (`parentId = '<folderId>'`, page through `nextPageToken`). Download each WAV with
   `curl -sL "https://drive.usercontent.google.com/download?id=<id>&export=download&confirm=t" -o <night>/raw/mic/<n>_WirelessGO.wav`
   (run them in parallel; the MCP download returns base64 and can't handle GB files).
4. Write `<night>/mic_chunks.json`: `{"<file>.wav": "<Drive modifiedTime converted to local time>"}`. modifiedTime is the chunk's **end** time. The photo timezone offset is in the album page (`-18000000` = UTC-5).
5. `cd long-form-video-editing/infield-nights && python prep_night.py ../infield-night-<date>` writes `work/<clip>_mic.wav`, the transcripts, `sync.json` and `triage.md`.
6. Read `triage.md`, classify each clip/range as approach, set-up/walking, or dead, and report back before cutting.

## Long-form edit (retention-paced compilation)
The pipeline is the Monkey long-form one (see `.claude/skills/monkey-longform/SKILL.md` for cutaways, captions, music, brand sting and outro rules), running on a combined source. Reference build: `long-form-video-editing/infield-night-2026-04-17/`.
1. Copy that folder's `*.py` plus `sfx/ music/ memes/ emoji/ fonts/ memeclips/ assets/` into the new night folder.
2. Set `SEGMENTS` in `build_source.py` (the kept approach ranges plus margin, with `pre_roll` when the opener was said before the phone started). Run `python build_source.py`. It writes `raw/raw.mkv` (vertical h264 + mic audio), `raw/segments.json` and `work/audio16k.wav`. This takes about real time for the encode.
3. `python transcribe.py && python diarize.py` (about 0.5x real time). Speaker tags are unreliable on a single lav mic (his voice reads 100-165 Hz, plus a talking wingman), so use them only as hints.
4. Write `build_edit.py`: **no intro teaser** for raw infield (user, 2026-10-05: `TEASER = False`, so no brand sting and no teaser bars either; the video opens on the first approach's opener). **No TV glitch transitions** (user, 2026-10-05): approaches join with a dip through black (`DIP`). **No meme cutaways** (`USE_CUTAWAYS = False`): flirty moments get `FLIRT_SFX` instead, a sparkle or a heartbeat placed at the phrase end from `work/speakers.json`, so run step 6 before the final build. Put the best-looking and strongest approach first, standouts about 2-3 min, a `z=` base framing for far shots, `zooms=` pushes, and `CUTAWAYS`. Run it and read the cutaway audit.
5. `python retranscribe.py && python build_edit.py`, then `python fill_quiet.py` (re-transcribes kept clips on level-evened audio to recover the women's quiet lines; review the printed additions).
6. **Two-speaker captions** (user, 2026-10-05): `python speakers.py` tags every caption phrase ME/HER (Resemblyzer voice profile of him + pitch). It's about 70-80% right on its own, so read `work/speakers.txt` against the conversation and put corrections in `SPEAKER_FIX` in `build_edit.py`. Openers and cold reads are his; the wingman and debriefs get his style. render.py draws his lines white/gold at the bottom and hers rose/white higher up.
7. `python render.py`, then `python qa/run_checks.py --level full out/<name>.mp4 edit.json`.

Layout (user, 2026-10-04): the vertical shot full height in the centre, over a blurred and dimmed copy of the same video. Captions use the Monkey long-form style.

## Gotchas
- The Wireless GO splits long recordings into 1 h chunks that butt up exactly. Short stray chunks (under 20 s) are fine; the timeline pads gaps with silence.
- Phone vs mic clock error was about +5 s on 2026-04-17. Pass 1 learns it from the clips that lock in strongly, and pass 2 searches ±15 s around it. One wide search alone mis-locked 3 of 5 clips.
- A clip can start before the mic was switched on (`mic_missing_s` in sync.json). That stretch has no usable audio.
- **Every approach opens on its opener** (user, 2026-10-05), with the walk-up included. The triage ranges can start after the opener (F's started 15 s late). Check the mic just before each range, and append any missing range as an extra `SEGMENTS` entry at the end so no existing source time shifts. Then transcribe only that range and merge it into both transcripts.
- **Far shots from a phone lying on a table: never zoom so far that he's cut out** (user, 2026-10-05: B at 2.2x "you couldn't even see me"). B stays wide. A modest base framing that keeps everyone in frame is fine (`A_BASE = (1.6, 0.33, 0.33)`). The foreground is shown at 608x1080 from 1080 wide, so zooms up to 1.77x cost no quality. Pushes ease from the base (`zoom_from`), and base framing is static.
- **Night footage under ~40 mean luma reads as black** and trips the black-frame gate. `build_edit.py` measures every clip and sets `lift=True` (`render.LIFT`: gamma 1.6).
- **Bar noise breaks the Monkey speech threshold.** The noise floor ran from -40 to -26 dB depending on the venue, so `speech_db()` uses each segment's 20th-percentile RMS + 6 dB. A fixed -44 dB flagged every cut and every gap.
- `check_her_visible.py` checks the zoomed, lifted window the viewer actually sees, on the whole vertical frame, with gaps up to 2 s allowed for handheld swings.
- **Bar noise makes medium.en drop key lines** ("You're very seductive", "Maricela" on 2026-04-17). After `retranscribe.py`, print every clip's caption text. For each beat a cutaway or text pop depends on, run a normalized medium.en pass with `vad_filter=False` on that range and patch the verified words in via `WORD_PATCHES` in `build_edit.py`. If neither model hears a line, don't caption it, and don't add a text pop that claims it ("DALLAS READ: 2 FOR 2" was pulled because her answer couldn't be verified).
- `check_her_visible.py` must read frames sequentially after one seek per clip, and detect at 540 wide. Seeking per sample on this source took over an hour.
- **Resemblyzer on Windows:** `pip install resemblyzer` fails building webrtcvad. Use `pip install webrtcvad-wheels && pip install --no-deps resemblyzer && pip install librosa`.
- **Speakers can't be told apart by loudness or pitch alone:** the girls stand right at the lav. Whisper sentences also mix speakers, so tag at phrase level (pauses > 0.3 s). For a phrase that mixes speakers with no pause, use a `SPEAKER_FIX` time range.
- `ffmpeg drawtext` segfaults on this machine (fontconfig). Use ASS subtitles or PIL for any text.
- Long Photos videos (GBs) take minutes before the first byte. The fetch script waits up to 30 min and never saves a video's still frame in place of the video.
