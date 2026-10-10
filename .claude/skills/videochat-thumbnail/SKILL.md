---
name: videochat-thumbnail
description: Build YouTube thumbnails for video-chat / e-date flirting long-forms in the split call layout, grounded in the video-chat outlier patterns. Use when the user wants a thumbnail, thumbnail options or a thumbnail strategy for a video chat (Monkey App, Omegle-style) video.
---

# Video chat e-date thumbnail

Strategy and the outlier evidence are in `thumbnail-creation/videochat_thumbnail_strategy.md`. Read its archetype table first. Tools and setup are in `thumbnail-creation/claude.md`. All commands below run from `thumbnail-creation/`.

## Inputs (infer them, don't ask)
- **Title**: from the video's `package.md` or concept doc. It decides the archetype. If there is no title yet, pick one from `video-ideation/video-ideas/monkey-app-video-chat/videochat_title_formats.md`, where each format has its proving model video and paired archetype.
- **Text** (follow the strategy's "Sparked text system"): grep the transcript for his best line and her real reaction to it (`--his-line` + `--bubble`). Otherwise use the video's mechanic (count, timer, checklist) or a reveal. Never use a generic invite line (PULL UP, COME OVER, LINK ME). If nothing real fits, go text-free.
- **Gimmick or count** (if the title has one) for the headline or his panel.

## Steps
1. **References (only after an outlier refresh, or about monthly for the inspiration channels):** `python pull_channel_thumbs.py --set videochat --channels v:UUlHWMDoSsk v:imny7n9lcME v:1tVFTg0up1w v:PKzB1_QB4s8 "Lil Praisey" @edtki v:vDyDb4hkSe0` (pin a channel by one of its video IDs: a name search hit "Jameer Live"). Then `python pull_videochat_refs.py`, then view `work/videochat_refs/sheet_*.jpg`. If a new pattern shows up in 3 or more, update the strategy table.
2. **Pick the archetype** (A classic, B standout girl, C gimmick, D online-to-real, E dating show / verdict) from the title format.
3. **Her panel:**
   - Real frame: `extract_candidates.py` on the moment, keeping only frames with sharpness of 100+.
   - Or AI: `python generate_woman.py --pose screen --look <latina|brunette|blonde|black> --out work/woman_<slug>.png`. Pick `--look` to match the archetype of the girl who stars in the video (Latina star means `--look latina`; archetype only, never a lookalike), and use a different look from the last upload. Generate 3 in one batch and keep the most real-looking one (pores, flyaways, and still 9-10/10 glam). Add `--extra` lighting that breaks the genre's pink/purple (warm amber, sunset, teal); see "Casting, colour" in the strategy.
4. **His panel:** a photo from `reference/self/videochat/` whose expression fits the archetype. Skip files marked "(don't use)".
5. **Compose 2-3 variants**, changing the woman, bubble or emoji between them:
   ```
   python compose_videochat_thumb.py --woman work/woman_<slug>.png --me "reference/self/videochat/<photo>.JPG" \
     --me-flip --woman-flip --his-line "<his real line>" --bubble "<her real reaction>" --emoji "😍" [--headline "PART 2"] [--no-badge] \
     --out output/vc_<slug>_v1.jpg
   ```
   Make sure her eyes point across the divider toward him. Flip her (`--woman-flip`) if they don't.
6. **Gates:** `python ../qa/run_checks.py --level full output/vc_<slug>_*.jpg`. Then do the strategy's mobile check, then run the `critic` on the finals only.
7. **Show 2-3 finals** (an `*options*` grid is fine) and auto-open them.

## Gotchas (keep this list updated)
- gpt-image-1 moderation blocks bikini, lying-on-bed and over-the-shoulder body shots. Fitted tank-top selfies pass.
- gpt-image-1 often turns her gaze the wrong way, so check every generation, and check for a hallucinated picture-in-picture.
- The headline sits along the bottom of his panel and the emoji goes in the top corner that clears his face, so neither collides with her bubble or the bottom-left badge.
- `--headline` and `--his-line` both use the bottom of his panel, so the composer refuses both at once.
- Never the smirk emoji, and never the app's name in any text.
- Export JPG at about quality 90. YouTube rejects anything over 2MB.

## Concept mocks for un-shot ideas (no image generation, no OpenAI)
The user doesn't want OpenAI spent on mocks. Run `python mock_videochat_thumbs.py --spec ../video-ideation/video-ideas/monkey-app-video-chat/mocks_spec.json --out output/mocks`. It reuses AI women already generated (`work/real_*.png`, `work/real2_*.png`, `work/screen_*.png`, `work/woman_selfie.png`) and the creator's reference photos, then draws each idea's mechanic. The available widgets are bingo, before_after, vs, scorecard, buttons, skip, tags, comment and mask.
- Each mock's packaging starts from the idea's model thumbnail, plus one upgrade borrowed from a better-performing thumbnail.
- Use a different woman, photo and colour grade per mock.
- Bubble text on a mock is a placeholder.
- Publish the board as an artifact with the model and upgrade-source thumbnails beside each mock (2026-10-09 board: https://claude.ai/artifact/GJzqaztUGXC89iQc5eukyA). Mocks skip the critic; finals don't.
- **Master folder of baddies (user's own, reuse it):** `C:/Users/kacey/OneDrive/Pictures/Baddies forThumbnails (monkey video chat)`. It holds the full-size pins named `pin_<pinId>`, plus `Mock thumbnails/`. It also has look subfolders, e.g. `Blondes/`. To rebuild the pool from it, run `python ingest_pins.py --from "<that folder>"`, then `--from "<that folder>/Blondes" --look blonde` for each look subfolder (the scan is not recursive). It's read-only, so the files are never deleted, and it dedupes by pin ID. Save newly pulled pins there first, as `pin_<pinId>.jpg`.
- **Pinterest pins as mock women (mock-only):** the user's public profile feed is `https://www.pinterest.com/kaceyokafor/feed.rss`. It lists only the newest ~24 pins; a board feed `/<user>/<board>.rss` does the same per board. Pull the `i.pinimg.com` image URLs, using `/736x/` for full size, into `reference/women_pool/pins_inbox/`, then run `python ingest_pins.py [--look latina]`. Pick pins with a classy expression (no tongue-out or lip-bite). `--final` refuses any pin.
