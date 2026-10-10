---
name: monkey-longform
description: Edit a raw Monkey App / video-chat recording into a retention-paced 16:9 long-form compilation (Jammer / Jay Throck style) with SFX, memes, captions and music. Use when the user wants a long-form video made from raw call footage.
---

# Monkey App long-form edit

Details and layout constants: `long-form-video-editing/monkey-app-longform-01/claude.md`. For a new video,
copy the **newest** project folder's scripts and assets (currently `monkey-app-longform-02`, which has the latest render.py) (`*.py`, `sfx/ music/ memes/ emoji/ fonts/`) into
`long-form-video-editing/<new-name>/`, not `raw/ work/ out/`.

## Steps
0. **Make sure it's raw.** Users sometimes send their already-edited/published cut first (burned-in captions,
   cutaways, 1440p MP4). Raw = OBS 1280x720 MKV with browser chrome. One video often spans **2-3 raw files**
   (one session doesn't have enough): download each as `raw/partN.mkv`, list them in `raw/parts.txt`, concat
   with `ffmpeg -f concat -c copy` into `raw/raw.mkv`, and run `python transcribe_parts.py` (transcribes each part
   once, merges on the combined timeline). All other steps then run on `raw/raw.mkv` unchanged.
1. **Source:** Drive files over ~100 MB are too big for the Drive connector. Use `gdown <FILE_ID> -O raw/raw.mkv`
   (no `--fuzzy` in the installed gdown). Check `ffprobe` and grab one frame to confirm the crop still matches.
2. **Privacy scan:** `python scan_chat.py` finds chat bubbles (typed Instagram handles, numbers) and writes
   `work/chat_blur.json`. `render.py` blurs every piece overlapping one. Her badge (name, age, city) is **shown, never blurred** (user, 2026-10-02: ages matter): the real pill is lifted into frame top-left, 1.3x, from `edit["badges"]` (per-girl source span + the pill's right edge in the raw frame, which depends on name length; measure it from a frame). When someone guesses her age, pop her enlarged badge (`fx(..., img="memes/badge_<name>.png")`) on the guess.
3. **Transcribe + tag speakers:** extract `work/audio16k.wav` (mono 16k), `python transcribe.py` (~0.5x realtime
   on CPU, so 60 min takes ~30 min, run in background), then `python diarize.py`.
4. **Map the e-dates** from `work/transcript.txt`. Skip calls with kids, and cut any phone number, handle or
   address said out loud (or, if the moment is worth keeping, like getting her Instagram, keep it with
   `bleep_all=True, nocap=True` on the spelled part). Rank beats: flirt first, small talk cut (user preference).
5. **Write `build_edit.py`:** highlight teaser (max 3 clips, about 10 s, from at least 3 different girls, **flirty highlight moments first**, each clip **ending on a cliffhanger** (cut right after the highlight line, before the reaction; ~2-3 s each), and the **last teaser
   clip never the girl who opens the main video** (build_edit.py asserts it): one strongest flirt beat each, building to the payoff; **every intro frame must clearly show the woman**, so check raw frames and use no zooms there, `teaser=True`, no title card; cut straight into e-date #1) -> one section per girl, **best girl
   first**. Pacing matches Jameer / the user's own edit (measured 2026-09-28): quick girls ~30-45 s, standouts
   ~60-90 s including cutaways, never 2+ min on one girl. Only top beats (with setups). Short calls from the raw stream are
   welcome as 4-8 s **quick hits** between e-dates (user, 2026-09-28), with a glitch opener and a cutaway if it fits.
   Read her Monkey age badge in the raw frame first (`crop=240:60:0:80`) and only use badge-verified adults who
   also look adult. Skip any call where anyone looks underage, whatever the badge says. Split the strongest call into part 1 / part 2 with an open loop ("we're coming back to
   her 👀"), finale = best payoff. Use `python words.py a b ...` for exact word times. Rizz SFX only on the
   creator's lines. **Every beat keeps its setup line** (the question or remark it answers). Read the caption
   flow clip by clip and add the setup wherever a line would land out of nowhere. Do this read-through every time the cut
   changes (print each clip's caption text in order); it's how v18's leftovers were found ("…to eat", a callback to a
   name never heard, "other things" without the rap line). Fix misheard captions per clip with `cap_map`. Look for running gags (same line used on two girls) and cut them back to back. When cutting back to the
   earlier instance, give it the flashback look (`flashback=True`: sepia, grain, vignette, band-limited audio) so it
   reads as the past (user, 2026-09-28).
6. **`python build_edit.py`, then `python retranscribe.py`** (medium.en on kept ranges only, ~12 min).
   Re-run `build_edit.py` (cut snapping uses the new word times) and print captions per clip to review.
   Where medium is wrong, set `cap_src="small"` on that clip or add `caption_fixes`. With two guys on camera (duo calls),
   medium drops whole lines; compare both per clip, and default to small (`setdefault("cap_src", "small")`) if it
   wins most clips, as in monkey-app-longform-02. If neither model is
   sure, `nocap=True`. Never guess her words.
7. **Render:** `python render.py` (it first runs `check_her_visible.py`, a YuNet face check on her pane every 0.2 s of every
   kept clip, plus any punch-in on the guys' pane, and refuses to render if she can't be seen; user, v17. `clip()` already
   drops zooms with cx > 0.5) (pieces cached in `work/pieces/`, only changed pieces re-render; the full
   first run takes ~25 min). Then `python qa/run_checks.py --level full out/<name>.mp4` and fix until clean.
8. **Open the render automatically** (user preference). Write `package.md` (title, thumbnail text, pinned
   comment) and send it through the `critic` agent. The `title-overclaim` gate checks it.

On-screen wording: they're **e-dates**, never calls, and they are not numbered on screen (no "E-DATE #1" banners).
Text pops never restate what was just said; they only add a gag setup, pun or open loop. Never mention "Monkey App" (text, titles,
descriptions) and no "I only flirt" text anywhere.

## Brand look (Sparked: cool, smooth, mature; user feedback on v2)
- **SFX:** none under spoken lines unless something on screen motivates them (a label, a text pop): free-floating
  shimmers/hits read as "label sounds with no labels" (user, first_video v10, `CAT_REMAP` retires rizz/tension/impact).
  Transitions (glitch static) keep their sound. When SFX are used: subtle pools only (soft shimmers `rizz`, low `impact`, soft `whoosh`, `tension`; heartbeats retired as too loud). Every file is
  peak-normalized to -24 dBFS (`norm_sfx`), one sound per moment, at least 4 s apart. No crowd, trombone, boing,
  whistle or arcade sounds (`CAT_REMAP` retires them).
- **Reactions = Jameer-style full-screen cutaways** (reference: Jameer `youtube.com/watch?v=l5k1civJmDo` and the
  user's own edit). The call pauses, a 1-4 s meme clip plays full-screen with its own audio line, then back.
  About one every 15-20 s (user preference), picked to match the line (see `CUTAWAYS` in `build_edit.py`). A TV color-bar glitch
  (with generated static) opens every new call. Library: `memeclips/*.mkv` + `library.json` (what each clip says),
  cut from the user's own published edit. Swears in clips are auto-bleeped (`cut_mutes`), and audio is peak-matched
  (`cut_gain`). Add new clips the same way: extract with `-c:a pcm_s16le`, check for burned-in captions.
- **Text:** Montserrat ExtraBold, white or soft gold, fades only, no bounce or rotation. Few pops, adult voice
  ("SHE CALLED ME BABY", "SAME LINE. DIFFERENT GIRL."), no slang pops ("EMOTIONAL DAMAGE").
- **Voice balance:** the creator's mic records ~5-12 dB quieter than the women. Leveling is per stretch (each lifted toward
  her level, capped) plus a **burst ceiling** (no 100 ms frame over her level + `BURST_HEADROOM` 8 dB), since a flat boost
  turned laughs and mic bumps into loudness spikes (first_video v1-v3). `creator_boost` measures the gap
  (diarized ME vs HER segments) and lifts only his speaking stretches in the final pass (printed each render).
- **Music:** auto-calibrated 22 dB under the creator's voice (`music_gain_db`, printed each render), then ducked.
  The raw mic is quiet (about -28 dBFS), so fixed music volumes come out too loud.
- **Zooms:** eased push-ins (zoompan, about 0.4 s) at 1.35-1.45x.

## Gotchas (keep updated)
- **Deliberate cliffhanger cuts** (teaser ender cut before her reveal, removing an aside mid-exchange): `snap()` would
  extend them into the next words or make neighbouring clips overlap. Pick both points in a real audio dip
  (25 ms RMS profile) and pass `snap_cuts=False` (sets `cut_ok` for the QA mid-speech gate).
- **Read user notes literally against the audio first:** "you cut out the Danny Duncan flag" meant her *line* about
  the flag, not the flag in frame (v17-v19). When a note names a thing, grep the transcript for it before touching visuals.
- **Never cut a sentence before it finishes.** Word timings end early ("I'm Filipi-", "Twenty-tw-": user,
  first_video v4). `snap()` in build_edit.py snaps to words from *both* transcripts, then checks the real audio:
  while 50 ms RMS > -32 dB at a cut, it extends the end (up to 0.8 s) or pulls the start back (up to 0.5 s).
  The build prints every moved clip and warns if any clip still ends mid-speech. v4 had 41 clips cut early.
- **Fill 16:9, never letterbox.** The call view (1280x614) is wider than 16:9. It used to get blurred bands top and
  bottom ("why is the top and bottom blurred", user v16). `frame_chain` now crops the centered 1092x614 window
  (`FILL_W`/`FILL_X`) and scales it to 1920x1080. Zoom targets stay in full-crop coords and are remapped.
- **Atomic piece writes.** Pieces render to `*.part.mkv` and are renamed when done. A killed render once left corrupt
  cached pieces that broke concat.
- **Badge lift:** crop the pill 1 px inside its edges (`BADGE_X/Y/H`), or the wall behind it shows as white specks
  at the rounded corners. It's skipped on punch-ins on the guys' pane (zoom cx > 0.5). The original pill is erased with `delogo`
  first, or its right half pokes out beside the lifted copy ("Wooster", "ce, New" fragments in v15).
- **small.en leaves holes in fast back-and-forth** (several seconds with no words). A beat the user remembers may
  sit in a hole: first_video lost "have you guys ever kissed?" that way (user: "you cut the clip short"). Before
  closing out a section, scan for transcript gaps over ~3 s between kept clips, re-transcribe them with medium.en
  (`vad_filter=False`), patch the words into `work/transcript.json`, and set `cap_src="medium"` on those clips.
- **End-screen hold frame** (`brand_outro_end.mkv`): hold source frame 28 of `brand_outro.mkv` (brightened 3%), not
  ~frame 26: the subscribe click's hand cursor leaves a smeared ghost at the button's right edge on frames 24-27,
  and frozen for 8 s it read as "the mouse pointer burnt in" (user, v23). Check the held frame at full size.
- **Setups the transcript misses:** quiet lines (the cousin's "Y'all are patriots" before "Danny Duncan flag"; the girls'
  mumbled answer before "I don't believe you") need a boosted re-transcribe (`dynaudnorm`, medium.en). Keep a reply
  that can't be transcribed in the cut, uncaptioned, rather than cutting around it (user, v26).
- **Cutaways must match the emotional beat, not just follow a line** (user, v35: "use clips that fit the moment"). Laughs
  only after an actual joke; a compliment or an invite gets a smug/approving beat (Jim smirk, DiCaprio pointing, Gatsby
  toast), a shocking line gets shock, a bluff gets a skeptical stare. `build_edit.py` prints every cutaway with the line
  it follows: read that list and ask "is this the reaction a viewer would have here?" for each one.
- **Cutaways can be literal:** when a line names a thing ("you look like a dentist"), a funny clip *of that thing*
  beats a generic reaction (user swapped Nick Young "???" for Steve Martin's "I'm your DENTIST!", v24). Avoid
  trailer/lyric uploads with burned-in titles; prefer the scene itself.
- **Cutaway fit:** match what the line *implies*, not just its surface. "Are y'all together?" (she means the two
  guys are a couple) wants a horrified "NO" (`michael_scott_no`), not a side-eye (`nicki_excuse_me`: user, v14).
- **Teaser must read as a teaser**, smoothly (user, v22-v27: a "LATER IN THIS VIDEO" banner was "too literal", a sped-up
  tape rewind was "weird"). What works, taken from Jay Throck's outlier opening: after the teaser freeze, hard-cut to the
  app's real **connecting card** for the first girl (purple screen, her photo, "She's 22 from ... Connecting...",
  muted, ~0.9 s), then she connects. The video visibly *starts* there. Find the card by its flat purple frames just
  before her call and list it in `edit["her_offscreen_ok"]`. (Jameer and Jay Throck themselves use no teaser at all.)
  Best teaser beats are often a *reaction with the cause withheld* (Madie's hand over her mouth after hearing his age).
- **Who says what:** confirm the speaker before captioning or panning. In duo calls the cousin (left guy) and Thor
  (far right) both talk; a clip that starts late can cut Thor's line and leave only her reply (Thor's "Kumusta ka?"
  was lost that way, v31). Check the audio profile for his quieter mic before the reply.
- **Teaser -> main transition** (user, v33: "too abrupt", wants "a brief branded screen Sparked Thor with my avatar"):
  the teaser freeze fades to black (`fout`), then the 2 s `brand_sting` (`make_brand_sting.py`: ember background,
  channel avatar `assets/avatar.png` in a gold ring, "Sparked Thor" in the brand fonts, shimmer, fades in/out), then the
  connecting card fades up (`fin`). `fin`/`fout` work on any clip or freeze piece.
- **Teaser bars:** `edit["teaser_bars"]` (h 132) puts cinematic black bars over the whole cold open; they slide off
  over 0.7 s on the connecting card (user, v28: still needed a teaser signal). Built as overlaid black color strips;
  a drawbox with a t-based height blacked out the entire frame (v30, caught by the frozen-picture gate). Teaser
  badges sit below the bar (`badge_y`).
- **First lines of a call: tight and showing the speaker.** Cut dead air between greetings (user, v28: "very slow
  paced"). Thor sits at the far right edge, which the centred 16:9 crop clips; `pan="right"` slides the window right
  so he's in frame while he talks. Foreign greetings get misheard (Tagalog "Kumusta ka?" came out as Spanish
  "Como esta"): fix with `cap_map`.
- **True peak after AAC:** a clip that starts on a hard transient can overshoot ~2.6 dB in the AAC encode even when
  the WAV is at -1.8 dBTP (v30, +0.8). The final limiter runs at 4x oversampling with limit 0.63. To find a peak,
  scan with `ebur128=peak=true:metadata=1` on a full decode (seeking gives false readings, and the metadata is
  cumulative, so the first frame over the limit is the spot).
- **Teaser ender vetting** (user rejected 3 Madie picks, v18-v20): her line, loud (measure 90th-pct RMS vs the
  alternatives), she's looking at the lens (no phones), and it must **not reveal the answer** it teases (her "fine
  one on the left" showed who). A reaction that opens a new question (a guy popping into her frame on "sir") ends best.
- **Teaser energy** (user, v13 "feels flat"): the teaser bed hits from frame one (`seek`, `fade_in` 0.03, vol 0.22, since
  the duck crushes the usual 0.08 under nonstop talk), soft whoosh on each cut, gentle 1.2x push-in on her, three
  different flavours (his line, her pushback, her offer), music cut dead under the payoff line, then a 0.6 s freeze
  on her last frame with a low hit (`keep=True` so the 4 s SFX spacing doesn't strip it) before the glitch.
- **Mix audio in its own pass** (`work/final_audio.wav`), then attach it to the video run. Mixing a separate
  voice WAV inside the heavy video/subtitle graph made ffmpeg drop ~18 s of audio: v7/v8 went out of sync in
  places, while the container still reported full length.
- **Cutaways are loudness-normalized to -27 LUFS** (`cut_gain`), not peak-normalized. Raw meme clips range
  from -7 to -34 LUFS, and peak matching left the Law & Order and El Risitas clips as loudness spikes.
- **Run QA after the file settles.** The gate used to cache "still writing, skip" as a pass. Fixed in
  `qa/checks.py`, but if a render "passes" instantly, re-run the check.
- **Pieces must be frame-exact** (video `-frames:v n`, audio `atrim=end_sample`). Otherwise each piece's video
  rounds up a frame, concat leaves audio gaps, and the audio drifts (v2 was 0.75 s off by the end).
- **QA `loudness spike` gate** (momentary > integrated + 8 LU) is how "SFX too loud" gets caught automatically.
- **AAC pieces + concat -c copy = A/V drift** (each piece keeps ~21 ms of encoder priming; v1 drifted about
  3.5 s by the end). Pieces are now PCM `.mkv`, and AAC is encoded once in the final pass. The QA gate checks
  sample count vs video length.
- **ffmpeg filters lock frame size on the first frame**, so animated `scale` overlays shrink. Pop-in overlays
  are pre-rendered by PIL as fixed-canvas PNG sequences (`overlay_seq`).
- **libass can't draw color emoji.** `render.py` strips emoji from text pops and places Twemoji PNGs beside them;
  add new emoji to `EMOJI_FILES`.
- **Ending = the Sparked end screen** (`memeclips/brand_outro_end.mkv`, 9 s: the branded card plays, then holds on its brightest frame with a slow 6% push-in and a soft music bed so YouTube end-screen elements fit; 8-10 s is the target, a dead still trips the QA freeze gate. Built from `brand_outro.mkv`: "Learn to spark attraction." card and
  subscribe click, 2.2 s, own audio, from the user's upload mGdLijMC6_s @394.23 s). Appended as the last `cut`
  piece in `build_edit.py`, with no music swell under it.
- **Don't overwrite a render the user has open** (Windows file lock). Bump `name` in `build_edit.py` per version.
- **Seeking with `-ss` before `-i` on the MP4 when measuring levels gave false silence.** Measure on a full decode.
- **Whisper word end-times run long.** Captions include a word if it *starts* inside the clip.
