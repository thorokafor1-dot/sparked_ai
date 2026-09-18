# Long-Form Hook Patterns, In-Person Cold Approach

Source: opening ~90 seconds of the 11 highest-scoring `In-Person` outliers in
`outlier-tracking/niche-long-form/data.json`, pulled via `pull_hook_transcripts.py`
(`hook_transcripts.json` has the full raw text). Video Chat/Omegle outliers excluded  - 
different production style than this channel.

## Four hook archetypes found

### A. Zero-setup cold open (no channel intro, no premise)
Chris Bizness (*Walmart Baddies*, 19.6x avg), John Savvy (*I Took Home a Model*, 19.3x subs),
Gully Panmei (*Delhi*), Marvin Goodly (*30 Min Cold Approaching*).
- Video starts **already mid-conversation** with a woman, no branding, no "in this video" framing.
- Chris Bizness specifically opens on a **non-chronological punchline snippet** ("Quick question, are you single... I'll pray for him") *before* cutting to narration that sets up the full scene and replays it in order. That's a teaser-then-context structure, not a straight cold open.
- Fastest way into the "watching a real interaction unfold" feeling, no friction between thumbnail promise and payoff.

### B. Stated premise/challenge, then cut to footage
Alex León (*A Realistic 60 Minutes*, 28.2x avg, the single highest scorer in this set), Brad Dating Lifestyle (*Brazil*, 16.2x avg).
- Opens with the **format/rules of the video stated directly to camera**: a time box ("60 minutes, starting now"), a location tour ("three cities in Brazil"). Creates a countdown/checklist curiosity the viewer can track.
- Brad's version also slots in a **channel/coaching-offer plug** inside this premise block before footage starts, his score (16.2x) is mid-pack in this set, lower than the other premise-led video and lower than every zero-setup cold open here. Weak signal on 2 data points, but worth being cautious about fronting a CTA before any payoff footage.

### C. Teaching/mechanic-first, narration explains the tactic, then shows it land
Coach Kyle, both sampled videos (*Deli*, *Mall*).
- Narration explains the **specific technique** ("you don't need a direct open, just ask a question," "wait for the wider opening so you don't box her in") *before or during* the clip, the viewer gets a takeaway in the first 30 seconds independent of how the interaction turns out.
- Notably the **lowest scores in this set** (5.7x, 4.7x, both qualified only via the flat 30K-view floor, not a multiplier). Coach Kyle is also by far the biggest channel here (581K subs), reads less like "this hook technique underperforms" and more like an established-audience channel where outlier status is harder to hit relative to baseline, since the audience already expects and returns for this exact teaching format. Don't read this as "avoid teaching hooks", read it as "teaching hooks sustain a large channel's baseline rather than spike it."

### D. Curiosity-gap / pain-point hook, no infield footage at all
Zoomology (*How Women React Around Attractive Men*), Honest Improvement (*Fear of Rejection in 48 Hours*).
- Zoomology: **explicit contrast promise** up front, "this is how women react around attractive men, and this is how they react around unattractive men", sets up a before/after the whole video pays off against.
- Honest Improvement: **direct pain-point question to the viewer**, "how many dates have you missed out on this year from fear of rejection", talks to camera, no footage, pure problem-agitation before the solution.
- Both are talking-head/analysis format rather than infield, a different sub-genre than the other three, but both cracked outlier status on the flat view floor, showing pure-value hooks travel too, not just footage-led ones.

## Cross-cutting observations
- **No subscribe-ask in the first 90 seconds** in any of the 11, unlike the Shorts pacing models in `shorts-hook-research/ideation_10_openers.md`, which front-load the subscribe ask before ~0:32. Long-form in this niche appears to let the hook run uninterrupted and ask later.
- **Smaller/mid channels lean on A and B** (cold open, stated challenge) to reach outlier multipliers well beyond their own subscriber base, these are the two highest-scoring videos in the set (28.2x, 19.6x, 19.3x). **The single biggest channel (Coach Kyle) leans on C** and posts the lowest relative scores here, consistent with a teaching hook being a retention/consistency play for an established audience rather than a breakout mechanic for reach.
- Every zero-setup cold open (A) gets to a **flirtatious/tension line within the first one or two exchanges**, none spend time on scene-setting dialogue (weather, small talk) before the charged moment.

## Applied to future videos
- For a video meant to travel beyond the existing audience (Type A/B territory): open on either a punchy mid-interaction snippet (teaser-then-replay, Chris Bizness style) or a stated time/location challenge, skip channel branding in the first 90 seconds entirely.
- For an established-channel retention video: a teaching-first hook (Type C) is fine and expected, but don't expect it to spike outlier multipliers the way A/B do.
- A pure-value/no-footage cold open (Type D) is a viable hook even without infield footage, if there's a genuine contrast or pain-point framing to lead with.
- Don't front-load a subscribe ask or coaching/product plug before the first payoff moment, the one outlier here that did (Brad) scored lowest among the premise-led videos.

## Open questions / next steps
- [ ] Re-run `pull_hook_transcripts.py` next time `outlier-tracking/niche-long-form/data.json` refreshes, to see if these patterns hold on a bigger sample.
- [ ] The 4 skipped candidates (no captions available) were newer/smaller-channel uploads, consider a manual watch-and-transcribe pass on those if they're still relevant later.
