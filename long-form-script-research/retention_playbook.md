# Long-Form Retention Playbook

What keeps men 18-35 watching after the hook, built only from outlier videos (never from our own channel's analytics). Covers 0:30 to the end; the opening 30 to 90 seconds lives in `long-form-hook-research/<type>/hook_patterns.md`.

**Evidence base (2026-10-01):** 40 full transcripts. Niche (25): In-Person, Video Chat and Explainer outliers plus the reference creators (Coach Kyle, Todd V, Coach Knox, Trey Star, Social Stoic, Jameer, Jay Throck). General (15): Max Fosh and Yes Theory (3 each), Hormozi, Iman Gadzhi, Mark Manson, HealthyGamer, Ali Abdaal, Jeff Nippard, Johnny Harris, plus Ryan Trahan as craft-only (structure, never tone or topics). Teen-skewing channels (Airrack, MrBeast, Beta Squad, Niko) are excluded. 27 videos carry YouTube's public "Most replayed" heatmap, which shows exactly which seconds viewers rewatch and which they skip. Numbers come from `retention_metrics.json`; quotes from `skeletons.md`.

## 1. What gets rewatched vs skipped (heatmap evidence)

The heatmap is the closest thing to a retention graph for other people's videos. Across all 17, the pattern is consistent.

**Rewatch peaks land on:**
| Moment type | Evidence |
|---|---|
| Playful role-play / future projection | Todd V's top peak (1.0): "Is this the part where we get married and have 2.2 kids or should we start with a drink first?" and the Vegas chapel follow-up (0.62) |
| Her pushback or test, and his answer | Dylan McKnight's peak (1.0) is her "who dared you?" challenge; Jay Throck's (1.0) is "why'd you skip me last time" answered with "you made me nervous" |
| Bold framing of the interaction itself | Todd V (1.0): "You seem like you could be an interesting person. I've known you for 30 seconds, so..." |
| The moment the interaction starts | Coach Kyle's top peak (1.0) is the first line of the approach, after his setup |
| A concrete reveal or number | Jeff Nippard: "how many of 9,000 are under 12%?" then "one person" (0.81); the 30% body fat reveal (0.97) |
| A drama twist late in the video | Jeff Nippard's highest point (1.0) is a story twist at 29:21 of 34 minutes |
| A named, quotable rule | Hormozi's "111 rule" (0.85) |
| The answer to the video's central question | Johnny Harris (1.0): "it comes down to the numbers", at 36:49 of 44 |
| The live payoff in front of real people | Max Fosh: the stuntman fight (1.0 at 81% of runtime), the kid's roast punchline (1.0), the exploding card (1.0 at 93%); Yes Theory's drift standoff (1.0 at 81%) |

**Skip dips land on:**
| Moment type | Evidence |
|---|---|
| Sponsor reads | Jay Throck skincare (0.0), Ali Abdaal card (0.03), Johnny Harris Ground News (0.02) |
| Logistics small talk | Jay Throck "where you staying? Arizona" (0.01), Dylan McKnight "why'd you move to Provo" (0.006), name explanations (0.006), Kalogeras "are y'all sisters" (0.0) |
| Coach lecturing in the abstract between clips | Coach Kyle "it's okay to ask questions..." (0.0), Todd V's "step-by-step system" preamble at 1:03 (0.0), Coach Knox basketball analogy (0.0) |
| Like-goal or engagement begging | Dylan McKnight "if this video gets 10,000 likes we'll return" (0.016) |
| The wrap-up and moral | Iron Mindset's last 4 minutes (all three lowest points), Yes Theory's reflective conclusion (0.0, 0.02), Ali Abdaal's late tangent (0.0) |
| Context setup before the story moves | Jeff Nippard's early "I'm always tired" context (0.006) |
| Preparation, building and travel | Max Fosh building props (0.0), rehearsing (0.0), fixing a door (0.004); Yes Theory "our fourth mode of transportation" (0.0), "riding the boat for many hours" (0.015) |
| Explaining the premise at length | Max Fosh's "would that be against the rules?" premise setup (0.008) |

**Rule:** every stretch of a script is either friction (tension, a test, a reveal, a payoff) or it's on borrowed time. Logistics, explanation without footage, sponsor/CTA and the wrap-up are where viewers skip, in every niche and every big channel.

## 2. Pacing numbers (bucket medians)

| Bucket | Words/min | Secs between re-hooks | Notes |
|---|---|---|---|
| Niche In-Person (infield) | 156 | ~170 | Footage carries it; re-hooks are rare and it shows in the dips |
| Niche Video Chat | 135 | ~220 | Lowest structure of any bucket |
| General social experiment (Max Fosh, Yes Theory) | 156 | ~110 | Same pace as infield; the difference is structure, not speed |
| Niche reference coaches (Kyle, Todd V) | 226-246 | 37-56 | Fast talk, frequent "here's where this goes" turns |
| General men's self-improvement | 220 | 40 | Fastest re-hook cadence measured |
| General story/explainer | 202 | 140 | Fewer turns, bigger payoffs, numbered chapters |

Takeaways:
- **Voiceover and breakdown segments run at 200-240 wpm** in every high-performing talking-head bucket. A slow, thoughtful breakdown is the sound of a dip. For our scripts, aim for 190-210 wpm: the `script-structure` gate caps at 3.5 words/sec (210 wpm) so lines stay natural to perform, and the editor's tightening of pauses closes the rest of the gap.
- **A re-hook every 40-60 seconds** is the cadence of the fastest-retaining talking-head channels. Infield videos that go 3 minutes without one show long flat stretches in their heatmaps.
- **Infield footage itself runs at about 150 wpm**, because conversations breathe. That's fine as long as the clip is friction, not small talk.

## 3. Structures that hold attention to the end (general outliers)

1. **The ladder (escalation built into the format).** Jeff Nippard goes 50% to 5% body fat; Ryan Trahan goes cheapest room to most expensive. Each rung is a payoff, and the viewer can see how many rungs are left. Heatmap peaks sit across the whole video, not just the start.
2. **Numbered chapters with a name per chapter.** Hormozi ("number three"), Ali Abdaal ("system number three"), Iman Gadzhi. The number tells viewers where they are; the name makes it quotable (the "111 rule" peak).
3. **The withheld answer.** Johnny Harris asks why deportations rose and pays it off at 82% of the runtime, which is the video's highest peak. The question is restated in passing so it never goes cold.
4. **A deadline open loop.** Ryan Trahan: "only I can experience this, at least until 7 p.m. ... I'm throwing my party at 7." A timed promise pulls viewers through the middle.
5. **The late twist.** Jeff Nippard saves an interpersonal drama beat for the final 15%, where most videos sag. It became the top peak.
6. **Real human chemistry as the payoff of a premise.** Yes Theory's top peak is a spontaneous exchange with locals, not the narration.
7. **Prep fast, climax at about 80%.** Max Fosh and Yes Theory compress setup into quick montage with narration, the prep stretches are still their lowest points, and the live payoff lands at 81-93% of the runtime. Social experiments talk at the same pace as infield (156 wpm), so what separates them is that every scene points at a promised climax.

## 4. Niche-specific findings

- **The best infield peaks are her test plus his playful answer**, not the opener and not the number close. Script the setup so the viewer knows a test is coming.
- **The coach's top peak is the moment the interaction starts.** Coach Kyle's breakdown peaks when he says "let's get into this interaction" and the footage begins, then dips when he talks between clips. Breakdown commentary should be short and anchored on a clip, not freestanding.
- **Video chat compilations have the least structure** of any bucket (no list markers, almost no re-hooks) and the flattest heatmaps between the funny peaks. A structure (ladder, rating, running score) is the open lane in video chat.
- **Faceless "stoic female psychology" explainers** rank high on views but sag through the last 15% every time. Their peaks are concrete body-language signs and an example dialogue; their dips are the philosophical wrap-up. Borrow the concreteness, not the voice.

## 5. Apply to Sparked

Translating the above for an on-camera cold-approach and e-date channel, men 18-35:

1. **Cut every logistics exchange that has no friction.** Where she's from, what she studies, names, goodbyes: cut or compress to a 1-second jump cut. Keep them only when they set up a tease.
2. **Build each video as a ladder.** For example: approaches ranked by difficulty, a running score across e-dates, the boldest line saved for last. Say the ladder out loud early ("each one gets harder") so viewers know rungs remain.
3. **Mark the test before it happens.** A line like "watch what she does when I say this" before a tease turns the highest-rewatch moment type into a promise.
4. **Re-hook every 40-60 seconds in breakdown/explainer segments, every clip in infield.** Use concrete turns ("and that's when it flips", "here's the line that saved it"), not "stick around".
5. **Talking-head breakdown at 190-210 wpm (the gate's cap), anchored on a clip.** Never more than about 20 seconds of commentary without cutting back to footage.
6. **Name the move.** One quotable name per technique (Hormozi's "111 rule" effect). Names get rewatched and clipped.
7. **Hold one answer back.** Ask a question in the first minute ("does she say yes?", "what's the line that works on every e-date?") and pay it off past the 75% mark.
8. **Put the strongest interaction in the final 20%, never the wrap-up.** End on a peak and go straight to a specific next-video CTA. No moralizing summary, no like-goals.
9. **Sponsor or self-promo goes after a strong peak and stays under 30 seconds,** because every sponsor read in the sample is a 0.0-0.04 dip.
10. **Show the walk-up, not the walk.** Travel to the spot, scouting, gearing up the mic: montage it in under 10 seconds or cut it. Social experiments prove prep is the lowest-retention footage even on 10M-view channels.
11. **Promise one climax and land it at about 80%.** For example "the hardest approach of my life" or "the e-date that went off the rails", teased early and played near the end, with the ladder (rule 2) climbing toward it.

## 6. How to refresh
Run the `script-research` skill. Read the "Most replayed" peaks and dips in `retention_metrics.json` first; they're the strongest evidence here. The regex device counts in the metrics (open loops, re-hooks) are rough proxies, so treat them as directional.
