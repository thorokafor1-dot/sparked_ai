---
name: infield-short
description: Cut finished 9:16 shorts from raw in-person (infield / cold approach) phone footage, opener first, flirty-line SFX, two-speaker captions, only approaches where she is clearly visible. Use when the user wants shorts from infield, daygame, mall, street or bar approach footage.
---

# Infield shorts (phone POV, vertical source)

Renderer: `long-form-to-shorts-video-editing/infield/render_infield_short.py` (spec format in its docstring).
Reference spec: `long-form-to-shorts-video-editing/infield/specs/amanda.json` (mall 2026-03-22, approach C1).

## Steps
1. **Fetch + transcribe** with the `infield-night` skill (mic WAVs normally; `--phone-audio` only for early archive footage).
2. **List approaches** from `work/triage.md` (opener line to her last line) into `APPROACHES` in the night folder's
   `scan_visibility.py` (copy from `long-form-video-editing/infield-mall-2026-03-22/`), run it. Then build a 6-still
   strip per candidate and look: the scan counts bystanders too. Drop anything where the camera sits on racks/street.
   **User rule: only approaches where you can truly see her.**
3. **Verify the words** of every kept line with medium.en on loudnormed audio, `vad_filter=False`,
   `condition_on_previous_text=False` (a long window silently skipped the whole bachata exchange; re-run short windows).
   Small-model words are not trustworthy on a phone mic ("all the raisins").
4. **Write the spec:** `keep` ranges opener first (start where she is already in frame, check YuNet face sizes),
   flirt beats, cut small talk, end ~0.5s after her last positive line. `her` ranges, `patch` with `WORD@t` times
   from medium.en, `sfx` on HIS flirty lines, real flirting stings `flirt_*` (sax lick, wah guitar, whistle; ElevenLabs-generated), **each sound once** per short, the strongest (`flirt_sax1`) on the key twist, with ~1.5s of her reaction kept after it so the sting lands (user, 2026-10-08). **No heartbeat**
   (user, 2026-10-08: "sounds so bad"; the renderer refuses it).
5. **First 2 seconds catch attention (user, 2026-10-08):** open on a cold-open hook, segment 0 = her on screen +
   his strongest flirty line (~2s, sparkle), `dip [1]`, then the opener. Replayed footage is fine: give SFX a
   3rd field with the segment index (`[t, "sparkle", 0]`).
   **No freeze frames (user: "there's a freeze"):** don't use `hold`/`jcut` stills. Cover an opener said off
   camera with `vsub` (live footage of her turning to camera + a silent stretch of her listening), and cut or
   tighten around brief occlusions instead.
   **Fix camera problems in the spec, not by dropping lines:** `hold [a, b, f]` shows a clean still of frame f while
   the audio plays (swing away, arm across the lens; keep holds under ~1s), `push` punches in on her for the opening
   when she is small in the walk-up, `later [i]` dips to black + "LATER" tag when segment i jumps minutes ahead,
   `jcut {video_from, live, still}` when he says the opener before the camera finds her (very common: he walks up
   from behind): his opener audio plays in full, the picture starts where she turns to camera, then a held frame
   with a slow push fills the rest of the line (sammy.json). Several holds per segment are fine.
   **Tighten like the critic does:** trim silences inside his lines (not words), cut his own repeated/filler
   answers, and end on a graceful exit even when she has a boyfriend (no cutting away before her answer).
6. `python render_infield_short.py specs/<name>.json --version N`, then
   `python qa/run_checks.py --level full long-form-to-shorts-video-editing/infield/output/<name>_vN.mp4 long-form-to-shorts-video-editing/infield/work/<name>_vN.ass`.
7. **Self-review** a 1 fps strip of the whole render (and 0.3s steps around every cut/hold) before showing it.
8. Critic subagent on the final, one revision round. Open the render for the user. One short at a time.

## Gates that apply
short-face-on-screen, short-opens-on-her (64px face floor for infield), short-lone-frame (handheld mode: both
jumps must clear 2.5x the local median), short-jumpy-cuts, short-bitrate, short-duration-matches-plan,
infield-caption-speaker (caption colour vs `her` spans), infield-her-visible-when-speaking (her face >= 64px
whenever she talks; >0.3s gap fails), caption-safe-zone, loudness. The critic reads 1 fps thumbnails, so check its
"she's hidden" calls against the detector before adding a hold.

## Gotchas
- Audio dropouts (gate `infield-audio-dropouts`, user heard them as "a weird sound"): two causes, both fixed in the
  renderer. (1) Denoise ONCE on a continuous clean track (`work/clean_<hash>.wav`), never per segment (RNNoise restarts
  cold and gates to silence). (2) Every segment's video and audio are trimmed to exactly the same length, or concat
  pads 40-90 ms of dead silence at each cut. (3) Full-strength RNNoise gates pauses to silence, so a faint
  brown-noise room-tone bed (~-55 dBFS, lowpassed; -70 gets zeroed by AAC) sits under the voice. Weakening RNNoise
  instead brings the hiss back (v21; gate `infield-hiss`).
- The rizz sound: online "rizz sound effect" uploads are nearly all the same classic hit (meme_rizz, overused per the
  user). meme_rizz_bright is the one distinct variant found (Voicemod). Use one per short, on the key twist.
- SFX = rizz meme sounds (user, 2026-10-09): short meme reactions (meme_owen_wow, meme_mmm_hmm, meme_oh_la_la; more on
  voicy.network, direct files at files.voicy.network/public/Content/Clips/Sound/<id>.mp3) placed in the PAUSE after
  his line. Voice memes may never overlap a word start (renderer enforces). Pin the segment index when the line is
  also in the cold-open hook. The classic rizz hit (meme_rizz) is overused; slow-mo song moments missed.
- Background beeps/tones (store scanners) read as "a weird sound effect". Find the frequency as the STFT bin that stays
  loud across frames (not the loudest FFT peak, that's a voice harmonic; sammy: 1523 Hz) and add it + its harmonic to
  `notch`. The voice chain also de-esses: phone-mic "s" sounds hit like a "shhh" after loudnorm.
- Listen, don't just look: the self-review covers AUDIO too. Gate `infield-no-extra-voices` transcribes the mix and
  fails on 3+ uncaptioned words (vocal SFX, lyrics, bystanders); the renderer refuses SFX files with vocals.
  Voice is cleaned per segment with RNNoise (`models/cb.rnnn`, from GregorR/rnnoise-models) + afftdn.
- Rizz moment (user's vision): `slowmo {i: {song, from}}` plays segment i (her smiling reaction) at half speed with a
  slowed + reverbed song, right after the rizz line. Songs live in infield-night-2026-04-17/sfx/ (meme_*, voicy.network).
- SFX: the user wants TikTok-style flirting stings (sax / wah guitar / whistle) that drive the line home, loud enough
  to hear (peak -14 dB). Magic sparkles, harp, bell chime and the heartbeat all missed. New stings: generate with
  ElevenLabs `/v1/sound-generation` (key `ELEVENLABS_API_KEY_SECRET` in sparked-practise-bot/.env) into
  `long-form-video-editing/infield-night-2026-04-17/sfx/flirt_<name>.mp3` and add to `SPARKLES`.
- Patched words: any original word overlapping a patch span is dropped (a mid-point test leaked "AMANDA?" early).
- Speaker is taken from each word's onset; never from a mid-point of a stretched word.
- The phone's own audio needs `highpass=90,afftdn` before loudnorm; mall echo is fine after that.
- Don't package a short around a dance request (memory), even when the dance invite is the payoff.
- One encode only: cuts, holds, push, captions, SFX, loudnorm and endscreen all happen in a single ffmpeg pass.
