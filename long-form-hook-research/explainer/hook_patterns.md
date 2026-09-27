# Explainer/Analysis Hook Patterns

Source: opening ~90 seconds of the highest-scoring `Explainer`-format outliers in `outlier-tracking/niche-long-form/data.json`, found via the new `EXPLAINER_KEYWORDS` list in `outlier-tracking/common.py` (this format was almost invisible in niche tracking before that addition, see `../CLAUDE.md`). YouTube's caption API was rate-limited from earlier use this session, so all 8 were pulled via `pull_hook_transcripts.py`'s automatic local yt-dlp + faster-whisper fallback (`../_common.py`).

## Data quality note (important)
Of the 8 candidates pulled, only 2 (`jwBsxc8TYOU`, `R7K9ajASKjM`) turned out to be real English-language audio. 5 more have clickbait English titles ("4 Female Body Language Signs of Attraction Most Men Always Miss") but Urdu, Hindi, or Malayalam narration, aimed at a South Asian audience via English SEO titles. `is_english_title()` in `common.py` only screens the title's script, not the spoken audio, so this bucket needs a manual listen-through before trusting a candidate, the same way video-chat needed a caption-availability sanity check.

That said, these aren't unrelated noise: read against a translation, at least 3 of the non-English ones (`FkKriTS7WA0`, `EeZrRy8WArA`, and the Malayalam `JHVyfBW0VUI`) open with the *same script*, near word-for-word: "at this moment, somewhere in the world, a woman is telling a man how she feels without saying a word, through 4 parts of her body she can't fully control... 90%+ of men miss these signals... it's not pickup artistry, it's evolutionary psychology/research." Different channels, different languages, same template, this reads as a script being deliberately copied/translated across small channels because it already works, which is itself corroborating evidence for the archetype below, not a reason to discard the data. Worth a follow-up: an audio-language check in the pipeline so these get properly bucketed by language rather than skipped or miscounted as independent data points.

## The dominant archetype (now confirmed 3x independently, in 3 languages)
Clean English examples: `12 Subtle Body Language Signs She's Highly Attracted To You` (Affinee) and `Feet Body Language: What Feet Position Reveals About Attraction` (FeetFinder). Same structure independently confirmed via translation in the Urdu/Hindi/Malayalam copies above.

**Curiosity-gap + authority-borrowing, no footage at all.**
- Opens on a direct "you've been missing this" accusation aimed at the viewer: "You've been misreading her this entire time, not because you're not paying attention, because you're paying attention to the wrong things." / "Ever been in a conversation where someone says they're relaxed but something feels off?"
- Immediately borrows scientific authority to make a subjective claim feel objective: "It's not pickup artistry. It's not manipulation. It's neuroscience. It's evolutionary psychology." / "your feet are wired closely to your instinctive brain."
- States a counted, escalating list up front and flags a specific item as the best one ("sign number seven... might be the most important thing you've ever learned"), the same escalation-promise mechanic already found in the general shorts/long-form research (JJEverettRose's "we'll start obvious, end with genius-level insight"), transplanted into a pure-analysis format.
- No infield footage, no channel branding beat, straight from hook into item 1.

This matches the Type D archetype already found incidentally in `../infield/hook_patterns.md` (Zoomology, Honest Improvement) almost exactly, curiosity-gap or pain-point framing, talking-head, no footage. This dedicated pass confirms it rather than finding something new, which is itself useful: Type D isn't a fluke, it's the dominant explainer pattern.

## Applied to future videos
- An explainer video's hook doesn't need footage or branding, it needs a direct "you've been getting this wrong" accusation plus a borrowed-authority reframe (science, psychology, not "tips" or "tricks") within the first 10-15 seconds.
- State the full numbered list up front and flag which item is the strongest, this is the same escalation-promise mechanic proven in both the Shorts and infield research, now confirmed a third time in a different format.
- Before trusting any future explainer candidate from the outlier tracker, listen to a few seconds of actual audio, an English title alone isn't proof of English content in this bucket.

## Open questions / next steps
- [ ] Re-run once the YouTube API daily quota resets (this pass was cut short by a quota error partway through the Explainer keyword list, only 8 of a likely larger set got scored).
- [ ] Investigate an audio-language check for `outlier-tracking/common.py`, or a channel-level exclusion list, once more dubbed-audio channels are identified.
