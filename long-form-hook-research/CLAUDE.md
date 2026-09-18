# Long-Form Hook Research

Single job of this folder: research what makes long-form videos hook viewers in the opening ~90 seconds, and collect it as reference material, separate from outlier tracking. Mirrors `shorts-hook-research/`'s scope, for the long-form format.

Split into 3 subfolders, one per content type this channel actually produces, since the hook mechanics genuinely differ by format (confirmed, not assumed, see each subfolder's `hook_patterns.md`):

- `infield/` - real street/daytime cold approach footage. Zero-setup cold opens and stated-premise/challenge hooks outperform; branded intros hurt.
- `video-chat/` - Omegle/Monkey app content. The opposite finding: branded series intros don't cost reach here, the video-level premise/gimmick matters more than any single opening line.
- `explainer/` - talking-head/analysis content, no footage. Curiosity-gap + borrowed-authority ("it's not tricks, it's psychology") hooks dominate, same escalation-promise mechanic as the countdown formats, just applied without footage.

Each subfolder has its own `pull_hook_transcripts.py` (filters `outlier-tracking/niche-long-form/data.json` by its `format` field) and its own `hook_patterns.md`.

## Shared code
- `_common.py` - `fetch_hook_transcript(vid, window_seconds)`, used by all 3 subfolders' pullers. Tries YouTube's caption API first; on any failure (rate limit, IP block, no captions), falls back to a local yt-dlp download + faster-whisper transcription rather than skipping the video. Audio downloads go through a temp directory and are deleted after transcribing, nothing persists to disk.

## `general-long-form/` is a different kind of reference, not a 4th subfolder
`outlier-tracking/general-long-form/`'s swipe file is title/thumbnail packaging psychology from outside the niche (a proposal-reveal formula, a karma-clip formula, etc.), each translated into a cold-approach concept. That's a different axis than this folder's opening-seconds pacing/structure research, and it's largely format-agnostic (a packaging trick works whether you shoot it as infield, video-chat, or explainer), so it doesn't get split by content type the way the 3 subfolders above do. Treat it as a secondary, adjacent-niche reference for titles/thumbnails specifically, not for hook structure.

## Discovery note
The niche keyword lists in `outlier-tracking/common.py` (`KEYWORDS`, `VIDEO_CHAT_KEYWORDS`, `EXPLAINER_KEYWORDS`) are what determine whether a format even gets found. Explainer content was almost invisible in niche tracking until `EXPLAINER_KEYWORDS` was added, the original list was tuned for action/footage terms and barely matched talking-head/analysis phrasing. If a future content type undersamples the same way, the fix is a new keyword bucket in `common.py`, not a new scoring metric, the view-floor/channel-average/subscriber-multiplier scoring in `long_form_tracker.py` already applies the same way across all formats.

## Scope rules
- Pure research/ideation notes, doesn't post anything, doesn't score/track outliers itself (reads `outlier-tracking/niche-long-form/data.json` as its source of candidates, doesn't duplicate that logic).
- To refresh a subfolder: rerun its `pull_hook_transcripts.py` after `outlier-tracking`'s niche-long-form data updates, then have Claude (or the `hook-researcher` subagent) regenerate that subfolder's `hook_patterns.md` from the new transcripts.
