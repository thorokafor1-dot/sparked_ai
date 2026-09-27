# Long-Form Hook Patterns, In-Person Cold Approach

Source: opening ~90 seconds of the 14 highest-scoring `In-Person` outliers in
`outlier-tracking/niche-long-form/data.json`, pulled via `pull_hook_transcripts.py`
(`hook_transcripts.json` has the full raw text; captions were rate-limited for most of
these, so the local yt-dlp + faster-whisper fallback in `../_common.py` did most of the
work). Video Chat/Omegle outliers excluded, different production style, see `../video-chat/`.

## Data quality notes (read before trusting the archetypes below)
- 2 of the 14 (`1h_aQaOPcXk`, `Swe3QF9e3Ok`) are non-English audio under English-adjacent
  titles, excluded from the analysis below, same issue found in `../explainer/`.
- `mW-05ce9MrE` ("$2 Flirty Vietnamese Ear Cleaning... ASMR") is a false positive, an
  ASMR massage video that matched on the word "flirty" alone. Worth tightening
  `is_relevant_tags()` in `outlier-tracking/common.py` if this keeps showing up.
- `v3IwRHApHU8` and `QjRvFKZSPqo` ("crisis of men refusing to approach," "why modern
  dating feels harder than ever") are talking-head commentary/reaction videos about the
  topic, not real infield footage, tagged `In-Person` only because they matched a
  keyword, not because of their actual content. They also open on the *same verbatim
  line* ("Since men don't approach women anymore, I guess I should start going up to
  men...") on two different channels, a reused/syndicated clip, the same pattern found
  in the explainer bucket's templated scripts. Excluded from the archetypes below, but
  worth a note: only Video Chat has a content-based Format override
  (`is_video_chat_content`) in the pipeline, there's no equivalent check to catch
  "this is commentary, not footage" for In-Person.

## Five hook archetypes found (usable sample: 9 real infield-footage videos + 1 no-footage)

### A. Zero-setup cold open (no channel intro, no premise)
`RgDCIvRnfcI` (*POV: She Invited Me Home*, 58.6x subs, the single highest score in this
entire dataset), Chris Bizness (*Walmart Baddies*, 19.6x avg), simpleGworld (*Wholesome
Reactions*, 19.6x subs), John Savvy (*I Took Home a Model*, 19.5x subs).
- Video starts **already mid-conversation** with a woman, no branding, no "in this video" framing.
- Chris Bizness specifically opens on a **non-chronological punchline snippet** ("Quick question, are you single... I'll pray for him") *before* cutting to narration that sets up the full scene and replays it in order, a teaser-then-context structure, not a straight cold open.
- Fastest way into the "watching a real interaction unfold" feeling, no friction between thumbnail promise and payoff, and now confirmed as the single strongest pattern in the whole set (the top score by a wide margin).

### B. Stated premise/challenge, then cut to footage
Alex León (*A Realistic 60 Minutes*, 28.6x avg), Chris Goldy (*12 Hours Straight in Toronto*, 14.3x avg).
- Opens with the **format/rules of the video stated directly to camera**: a time box ("60 minutes, starting now" / "12 hours straight"). Creates a countdown/checklist curiosity the viewer can track.
- Chris Goldy's version adds a **vulnerability beat inside the premise** ("I stepped out of the car and felt anxious... I'm naturally an introvert"), stakes the challenge on his own discomfort before any footage, not just the format.

### C. Teaching/mechanic-first, narration explains the tactic, then shows it land
`NUQS-v1DWZM` (*How To Create Sexual Tension During Cold Approach*, 30.3x subs), Coach Kyle (both prior-pass videos, *Deli* and *Mall*, no longer in this refreshed top-15 but referenced for contrast).
- Narration explains the **specific technique** before or during the clip, viewer gets a takeaway in the first 30 seconds independent of outcome.
- **Revises the earlier finding.** The previous pass (Coach Kyle only, both low-scoring) read this as "teaching hooks sustain a big channel's baseline rather than spike reach." `NUQS-v1DWZM` breaks that: a 1,470-subscriber channel hit 30.3x with the same teaching-first structure, the 2nd-highest score in this whole set. The variable isn't channel size, it's likely specificity, "sexual tension" is itself a curiosity-driving promise, versus Coach Kyle's more generic "here's a technique" framing. Don't treat teaching-first as a reach-limiter, treat *vague* teaching as one.

### D. Curiosity-gap / pain-point hook, no infield footage at all
Honest Improvement (*Fear of Rejection in 48 Hours*, 13.6x avg); Zoomology (*How Women React Around Attractive Men*) from the prior pass, no longer in this refreshed top-15 but the pattern holds.
- Honest Improvement: **direct pain-point question to the viewer**, "how many dates have you missed out on this year from fear of rejection," talks to camera, no footage, pure problem-agitation before the solution.
- A different sub-genre than the footage-led archetypes, but still reaches outlier status on the flat view floor, pure-value hooks travel too.

### E. Vulnerability/self-deprecating stakes-setting (new this pass)
Brad Dating Lifestyle (*Colombian Girls Are NEXT LEVEL*, 11.9x avg).
- Opens with a self-deprecating credibility claim before any footage: "this was actually during the time I was the fattest and least attractive, so watch this video to the end and then you tell me the looks matter."
- Sets up a prove-it-to-yourself frame (the viewer is implicitly betting on whether looks matter) that the footage then resolves, a persuasion device closer to the general-long-form swipe file's "vulnerability + payoff" packaging than anything else found in infield footage so far.

## Cross-cutting observations
- **No subscribe-ask in the first 90 seconds** in any of these, unlike the Shorts pacing models in `shorts-hook-research/ideation_10_openers.md`, which front-load the subscribe ask before ~0:32. Long-form in this niche appears to let the hook run uninterrupted and ask later.
- **The single highest score in the whole dataset (58.6x) is a pure zero-setup cold open** on a 711-subscriber channel, the strongest confirmation yet that Type A is the highest-ceiling pattern for reach.
- **Teaching-first hooks aren't inherently a reach-limiter** (see revised Type C above), specificity of the promise matters more than whether the hook teaches or shows.
- Every zero-setup cold open (A) gets to a **charged line within the first one or two exchanges**, none spend time on scene-setting dialogue before the tension.
- **Format tagging has real gaps**: at least 2 of 14 candidates this pass were commentary videos wrongly bucketed as In-Person, and 1 was an outright unrelated ASMR video. Treat every fresh pull as needing a quick eyeball pass, not just a caption-availability check.

## Applied to future videos
- For a video meant to travel beyond the existing audience (Type A/B territory): open on either a punchy mid-interaction snippet (teaser-then-replay, Chris Bizness style) or a stated time/location challenge, skip channel branding in the first 90 seconds entirely.
- A teaching-first hook (Type C) can still spike reach on a small channel, if the promise is specific ("sexual tension," not "a technique"). Vague teaching hooks are the actual risk, not teaching hooks in general.
- A pure-value/no-footage cold open (Type D) is a viable hook even without infield footage, if there's a genuine contrast or pain-point framing to lead with.
- A self-deprecating "prove me wrong" stakes-setting beat (Type E) is worth testing as a premise-block addition, distinct from Type B's format-rules framing.
- Don't front-load a subscribe ask or coaching/product plug before the first payoff moment.

## Open questions / next steps
- [ ] Re-run `pull_hook_transcripts.py` next time `outlier-tracking/niche-long-form/data.json` refreshes, to see if Type C's revised reading and Type E hold on a bigger sample.
- [ ] Consider tightening `is_relevant_tags()` for the ASMR false positive, and whether a content-based override (like Video Chat's) is worth building for "commentary about the niche" vs "actual footage in the niche."
