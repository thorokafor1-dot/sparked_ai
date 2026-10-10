---
name: idea-board
description: Build a format's full idea pipeline, from inspiration-channel analysis (thumbnail text trends, title formats) to 10 proven ideas with a twist, zero-cost mock thumbnails and a published idea-board dashboard. Use when the user wants proven video ideas, title formats, thumbnail strategy or an idea dashboard for a content format (video chat, explainer, raw infield / cold approach).
---

# Idea board for one content format

The first run was video-chat e-dates on 2026-10-09. Its outputs show what "done" looks like:
- `thumbnail-creation/videochat_thumbnail_strategy.md`
- `video-ideation/video-ideas/monkey-app-video-chat/videochat_title_formats.md`
- `video-ideation/video-ideas/monkey-app-video-chat/next_recordings_titles.md`
- `video-ideation/idea-boards/videochat_board.html`, published at https://claude.ai/artifact/GJzqaztUGXC89iQc5eukyA

**One format per thread** (user's choice): video chat, explainer and raw infield each get their own session. `<set>` below is `videochat`, `explainer` or `infield`.

## Inputs (infer them, ask only if missing)
- **Inspiration channels for the format.** Check memory first. Cold approach long-form has Coach Kyle, Todd V, Diego Day and Social Stoic. Video chat is in the `videochat-inspiration-channels` memory. For explainer, ask the user.
- **Seed outliers the user names**, e.g. the explainer seed: Dan Bacon "How to Talk to Girls (Don't Ask Questions!)", 441K views, score 14.7, a concept the user already teaches.
- **The format's edit and packaging rules in memory**, e.g. the raw infield rules, the explainer rules, and that the woman is the thumbnail's main draw.

## Steps
1. **Pull the inspiration channels.** Pin each channel by one of its video IDs or by `@handle`, because a name search hits the wrong channel. Run from `thumbnail-creation/`:
   `python pull_channel_thumbs.py --set <set> --channels v:<videoId> @handle ...`
   Then view `work/channel_refs/<set>/*/sheet_*.jpg` and `index.tsv`. "x" in the index means times that channel's median views.
2. **Thumbnail text trends:** read every thumbnail's text, sort it by type, and match each type to its x performance. Find what drives their winners and what's only genre habit. Write `thumbnail-creation/<set>_thumbnail_strategy.md` (pattern table, "what Sparked skips", archetypes, text system). **Beat them, don't copy them.**
3. **Find the gaps:**
   - Search demand: YouTube autocomplete. `video-ideation/demand_check.py` does this, or loop seeds.
   - Words missing from their titles: grep their titles for "flirt", "attractive" and other searched phrases.
   - Formats proven in other niches (`outlier-tracking/*/data.json`).
4. **10 proven ideas with a twist.** Every idea needs all four of these:
   - a **model video**: a male creator of comparable size, never female hosts or mega-influencers, at 2x+ median or outlier score 20+
   - an **upgrade** borrowed from a better-performing thumbnail
   - a **twist** from the gap analysis
   - **what to record**

   Check each one with `python video-ideation/demand_check.py --set <set> --match "<regex>" --seeds "<phrase>" ...`.
5. **Title rules:**
   - Lead with "flirting" / "women" where it's natural (the second channel's proven formula).
   - Statements, not questions. No smirk emoji. Never put words in her mouth. No over-promising.
   - Count only 2+ minute conversations toward any number in a title.
   - Run the `critic` on the final list. Allow 2 rounds at most.
6. **Mocks, with no OpenAI or other paid image generation:**
   - Use `thumbnail-creation/mock_videochat_thumbs.py` with a spec JSON next to the ideas doc.
   - Use women from `reference/women_pool/`. The main source is Pinterest pins, pulled through the user's public feed (see the videochat-thumbnail skill; they are mock-only). Local AI (`generate_woman_local.py`) is the backup: it looks real but tops out around 6-7/10 glam and takes about 9 minutes per image. Use the creator's photos in `reference/self/`.
   - Each mock starts from the packaging of its model thumbnail and adds the upgrade element.
   - Vary the woman, the photo and the colour grade from mock to mock.
   - Bubble text on a mock is a placeholder.
7. **Dashboard:**
   - Copy `video-ideation/idea-boards/videochat_board.html` and swap in the IDEAS array.
   - Use plain sans headings, no cursive.
   - Publish with the images as supporting files: `img/mock_*.jpg` and `img/m_<videoId>.jpg` (the model and upgrade thumbnails, cropped 480x270).
   - Save the HTML back to `video-ideation/idea-boards/<set>_board.html`.

## Gotchas (keep this list updated)
- **The mock script only does the split call layout today.**
  - For explainer, add a single-frame layout: a talking-head frame plus a woman, with the woman as the main draw.
  - For infield, add real-frame layouts, e.g. a two-person street frame from `extract_candidates.py` on real footage.
  - Add a `layout` field to the spec rather than writing a second script.
- **`pull_channel_thumbs.py` without `--set` writes to the `videochat` set.** Always pass `--set` for other formats.
- **The `videochat-title-words` QA check only covers the monkey-app-video-chat folder** (e-date and app-name rules). Other formats need their own banned-word list if they have one.
- **Local generation is about 1-3 minutes per woman on this CPU,** so run batches in the background. Her gaze is set off-lens at her screen for video chat. Explainer and infield may want a different gaze, so check with the user.
