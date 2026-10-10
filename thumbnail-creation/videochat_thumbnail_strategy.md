# Video Chat E-Date Thumbnail Strategy

What the video-chat flirting outliers do on their thumbnails, what Sparked takes from that, and what it skips. The playbook that applies this is `.claude/skills/videochat-thumbnail/SKILL.md`.

**Source:** `outlier-tracking/niche-long-form/data.json`, rows with format "Video Chat", filtered to flirting and dating-show content (celebrity/streamer cameos, trolling and exposés dropped). This was a manual review of 35 flirting thumbnails plus 6 dating-show thumbnails on 2026-10-09 (MarcusT, Jameer, Jay Throck, Yunus Akin, France Fit, Teige, Fabss, Ejay, ItsMP3, Zaen Azzuri, 100calebb; dating shows: Kalogeras Sisters, Family Friendly, Quenlin Blackwell, Corey2U). Refresh the board with `python pull_videochat_refs.py`, which writes `work/videochat_refs/sheet_*.jpg` and `index.txt`.

## What the outliers do

| Pattern | Share of 35 | Sparked rule |
|---|---|---|
| **Split call frame**: two side-by-side panels with a thin divider, like the app's own screen | 35/35 | **Always.** This is the format signal: a viewer knows "video chat" before reading the title. |
| **She looks straight into the lens.** Front-camera selfie angle, glam makeup, hand on cheek or lying back, pink/purple LED bedroom | ~30/35 | **Always.** She is the main draw. Use `generate_woman.py` or a sharp real frame. |
| **He reacts on camera.** Confident smile or smirk, hand-on-chin "thinker", or a genuine shocked or laughing face, looking at the lens | 35/35 | **Always.** Match his expression to the story: confident for best-of videos, shocked for a "she's a goddess" story. |
| **App UI chrome**: platform badge, report/skip icons, yellow "Friend" button, "Stranger:" chat line | ~30/35 | Badge **on** by default (the channel's classic layout). Never put the app's name in text. See open question below. |
| **One short line from her**: a speech bubble or chat line of 1-3 words | 14/35 | **Yes, one bubble**, taken from something a girl actually said in the video (see Copy rules). |
| **Emoji**, 1-2 of them, most often the purple devil, heart-eyes, hot face or a red heart | ~15/35 | **Max one.** Prefer heart-eyes, a heart or fire. Never the smirk emoji. |
| **Headline of 1-3 words**: yellow or white, heavy black stroke, along the top or bottom edge | ~15/35 | **Only when it carries the title's hook**: a series marker ("PART 2"), a count, or the gimmick. Never a restatement of the title. |
| **His gimmick is visible**: Spider-Man suit, dyed dreads, physique, tattoo | 9/35 | **If the title has a gimmick, the thumbnail must show it.** It is the promise. |
| **Circle inset and red arrow** zooming on one detail | 4/35, including MarcusT's top three (scores 216, 115, 105) | Use it for a single-standout-girl story, pointing at her reaction or a prop, never at a body part. |
| **Verdict mechanic** (dating shows): dating-app ✕ / ❤ buttons under the panels, a one-word answer ("YES"), a "You" label, sometimes the stranger pixelated so the click is "who is he, did he pass?" | 2/3 Kalogeras (scores 152, 148) | Use the **mechanic** on any e-date with a judgment (rating, ranking, "would she date me"), but never Kalogeras as a model video: female hosts with 8.9M subs (user, 2026-10-09). Male, comparable-size models only. |
| **Lineup vs. her**: several suited contestants (roses) or a group of guys opposite one woman | 2/6 dating shows | Use it for wingman, friends or "who gets the date" formats. She stays the biggest face. |
| **Timer or score badge** (e.g. "01:17") | 2/35 | Use it on challenge and game formats (strategist: "show the score, the rule or the stakes"). |

Her side of the frame was left in 18 thumbnails and right in 17, so position doesn't matter. Keep her **left** (read first, the channel's existing layout).

Dating shows are an e-date format with a game on top, so they belong in the reference set. Only celebrity cameos are filtered out (their clicks come from the famous name, not the thumbnail).

## What Sparked skips (brand, audience 18-35 men, cool and mature)
- Body-part insets, censor-blur teases, tongue-out shots, flashing bait. These carry the raunchiest outliers (Jaiden, C4, Zaen) but contradict the brand and risk age-restriction.
- Juvenile copy: "YES DADDY", "GYATT", "GET FLASHED", "W RIZZ".
- Trolling and fake-skip angles. Sparked videos are about flirting that works, not pranks.
- Three or more stacked emoji and stickers. One clear read at phone size beats a busy collage.

## Archetypes (pick by the video's title format)

| Archetype | When | Recipe |
|---|---|---|
| **A. Classic e-date split** (default) | Best-of compilations, "e-dates with strangers" | Her glam selfie on the left, him smiling confidently on the right, one bubble, one emoji, badge. No headline. |
| **B. Standout girl** | One girl carries the video ("she's a goddess", part 2 of a story) | Her panel, plus a circle inset of her reaction with a red arrow, his shocked or delighted face, and a headline only for the series marker. |
| **C. Gimmick or challenge** | A count, time box, handicap or costume in the title | Show the gimmick in his panel (outfit, timer or score badge) and put the count in the headline ("10 COUNTRIES"). |
| **E. Dating show / verdict** | Rated, ranked or judged e-dates, wingman and "who gets the date" formats | The split frame plus a ✕ / ❤ verdict row (or a lineup opposite her), with one-word verdict text. Keep it classy: the verdict is about chemistry, never her body. |
| **D. Online to real** | He meets an e-date in person | Left panel is her on screen, right panel is the two of them in person (strategist: "the split sells the arc"). |

The composer covers A and C now (`--bubble`, `--his-line`, `--emoji`, `--headline`). B (circle inset), D (real-life panel) and E (verdict row, lineup) are still manual. Add a flag the second time one is needed.

## Text trends: the direct-inspiration channels (2026-10-09)
Jameer, Jay Throck, Zaen Azzuri, ItsMP3, LilPraisey, Edtki and Teige: their last 24 long-forms each (152 videos, about 125 of them video chat), each scored against its own channel's median views (x = times the median). Rebuild with `python pull_channel_thumbs.py --set videochat --channels v:UUlHWMDoSsk v:imny7n9lcME v:1tVFTg0up1w v:PKzB1_QB4s8 "Lil Praisey" @edtki v:vDyDb4hkSe0` (results in `work/channel_refs/`, plus `index.tsv`). **These channels are the baseline to beat, not a template to copy.**

| Text type | Who uses it | How it performs |
|---|---|---|
| **Her "invite" bubble**: pixel font, white box, 1-3 words, almost always PULL UP / COME OVER / COME HERE / LINK ME / I NEED YOU / WANNA SEE / PAPI | The genre default (Zaen on nearly every video, Jay 8/24, Jameer, ItsMP3) | **Weakest.** Jay's bubble thumbnails sit around 0.5-0.8x, while his no-text ones run 1.0-2.5x. ItsMP3's run 0.4-0.5x. Zaen's two mega-hits (104x, 35x) were carried by the body pose, not the words. Everyone uses the same 7 lines, so the line itself adds no information. |
| **Game mechanic on screen**: checklist with a tick ("GET HER # ✓", "GET FLASHED ✓"), a timer ("01:17.45"), a counter ("37. Brazil ✓", "#67"), a "24 HRS" badge | ItsMP3, Jay, LilPraisey | **Highest ceiling.** ItsMP3 bingo 108x, Jay bingo 2.8x and 1.7x, LilPraisey 24 hours 3.4x. The mechanic is the promise. |
| **Reveal label + red arrow**: "FAKE" pointing at a tattoo, jewelry or grillz | ItsMP3's series, Jay | **Consistently strong**: 5.6x, 4.5x, 2.1x, 2.0x, 1.9x. Dramatic irony: the viewer knows a secret she doesn't. |
| **Two-sided dialogue**: his line plus her reaction, or her before-and-after | ItsMP3 ("Ew WTF!" then "You're HOT", 5.4x), LilPraisey ("LOCK IN" / "YOU'RE CUTE", 2.8x) | **Only 2 of ~85, and both beat their channel median.** It tells a cause-and-effect story in one glance. |
| **Chat-log line**: a red "Stranger:" or "Me:" label in the app's text bar | ItsMP3, Jay (Azar) | Splits on the line. A curiosity line wins ("Stranger: $5 = 👀", 10.3x). A generic invite loses ("STRANGER: COME HERE BAE", 0.6x). |
| **Third character in the call**: his girlfriend on his side, or a viewer in a third panel ("CAN I JOIN?!", "HELP!", "LINK ME") | Jameer | **Strong**: 4.9x, 4.6x, 2.0x. Adds a storyline beyond "guy meets girl". |
| **Big headline** (SHE LEFT ME, 1V1, HOW WE MET) | Jameer and Zaen vlogs | Mid to weak, and it's the vlog format, not video chat. |
| **No text** (emoji only) | Jay's and ItsMP3's best-of compilations | Fine for best-ofs (Jay 2.5x, 2.0x, 1.95x). The faces carry it. |

**Teige and Edtki sharpen the bubble finding.** Her line works when it is a **verdict on him** tied to the video's variable: Teige's "HE WAS SOO FINEE..." 4.9x, "BODY TEA" on the shirtless video 4.5x, "FINE AF" 1.4x. It is weak as a generic invite: Teige's "COME OVER" 0.64x. Edtki puts a pixel invite bubble (PAPI, DADDY, PULL UP) on almost every thumbnail, and his only hits are compilations (14.3x, 6.9x) and "look good" (8.0x), so the bubble is not what drives them. Teige sets her line as yellow quote text, not a pixel box, and his biggest hits show the variable itself: dyed hair with an arrow (5.0x, no text), shirtless (4.5x), "VS" (3.5x).

**Style norms:** text is 1-3 words. The bubble sits at the top of her panel near her head, usually with a heart or emoji. Quotes are in heavy yellow or white type with quote marks (LilPraisey). Reveal labels are white Arial-Black style with a red curved arrow. The app's own text bar is often reused as a chat line.

## Casting, colour and the strategist's input
From the user and thumbnail strategist Wajdan Waqar Kyani (2026-10-05 to 2026-10-09):
- **Goal is CTR with American men aged 18-35.** She is 9-10/10 and still looks like a real girl (see `generate_woman.py`).
- **Match the star's archetype only, not her likeness.** If the girl who carries the video is Latina, use a Latina AI woman (`--look latina`). Everything else (face, hair, outfit) is free to be whatever is most clickable. Never try to recreate the real girl.
- **Vary her look across videos.** Same look on every upload makes the channel's videos blur together in the feed. Keep a short log of looks used per video in the package doc.
- **Stand out with colour contrast.** About 9 in 10 thumbnails from the inspiration channels share the same pink/purple LED glow, so another purple thumbnail disappears next to them. Pick a dominant colour that breaks the feed (warm amber or sunset orange for the brand's "sunset dating" vibe, teal, or red), and contrast her panel against his: warm vs cool, light vs dark. The text colour must pop against both.

**Wajdan's text ideas, checked against the data:**

| Line | Type | Verdict |
|---|---|---|
| "Fine sh*t" | Her verdict on him | **Yes, the strongest of the three.** Same type as Teige's "HE WAS SOO FINEE" (4.9x) and "FINE AF" (1.4x). Use it only if she really said it, and prefer the clean version "FINE" / "YOU'RE FINE" (brand is mature). |
| "What's your insta?" | Her interest signal | **Good.** She is asking for *him*, which is visible proof it worked (rule 2). Use it only if she said it in the video. |
| "Come pick me up" | Invite | **Weakest type.** Invite bubbles average 0.5-0.8x across Jay Throck, ItsMP3, Teige and Edtki. Skip it. |

## Text or no text (2026-10-09)
- **No text wins when the picture alone tells the story:** her look, his visible gimmick, a clear situation. Examples: Jameer "I RETURNED TO OMEGLE AND SAW MY EX?!" 3.0x, Teige's dyed dreads 5.0x (arrow only), Edtki's Michael Myers 2.5x. Jay Throck's text-free video-chat thumbnails average about 1.0x his median, versus about 0.8x for his speech-bubble ones.
- **Text wins when the hook can't be seen:** a rule, a mechanic, a number, a twist. Example: ItsMP3 bingo 108x (checklist and timer).
- **Generic text does worse than none.**
- Render both with `mock_videochat_thumbs.py --notext`, and upload both to YouTube Test & Compare so watch time picks the winner.

## The Sparked text system (how we beat them)
1. **Retire the invite bubble.** It's the genre's most-used and worst-performing text, and it reads cheap. Never use PULL UP / COME OVER / LINK ME / PAPI.
2. **Her line must be a verdict on him, never an invite** (Teige: "HE WAS SOO FINEE" 4.9x vs "COME OVER" 0.64x).
3. **Signature move: his line then her reaction** (`--his-line` + `--bubble`). Almost nobody does it, it outperforms, and it is literally the brand promise (learn to spark attraction): the viewer sees the line *and* that it worked, and clicks to learn it. Both lines must be real, from the transcript.
4. **If the video has a mechanic, the mechanic is the text**: count, checklist, timer or score (archetypes C and E). This has the highest ceiling of anything measured.
5. **If there's a secret, label it**: reveal label + arrow (dramatic irony). Use it only when it's genuinely in the video (no unverified claims).
6. **Best-of compilations can go text-free**, with one emoji and her eye contact.
7. **Budget:** at most 2 text elements and 7 words in total, and at most 1 emoji. Keep the clean Arial-Black bubble rather than the genre's pixel font. It reads more mature and sets Sparked apart from the copycats.
8. **Specific beats generic.** A line only this video could have ("GUESS MY AGE" / "WAIT, SAY THAT AGAIN") beats any stock line. If you could paste it on another channel's thumbnail, rewrite it.

## Copy rules
- **The bubble and his line quote the video.** Take both from the transcript, 1-4 words each: her real reaction, and the real line of his that caused it. Never invent her words (memories: no fabricated dialogue, no unverified claims). If nothing quotable exists, leave the bubble off.
- **The thumbnail adds to the title, never repeats it.** The title says "e-dates", the thumbnail shows one.
- The app is never named in text. Video titles say "e-dates".
- Classy over crude: if a line would embarrass the guy sending the video to a friend, cut it.

## Mobile check (before the critic)
Look at it at about 320px wide (the feed size). She is the largest face and her eyes read clearly. There are at most three overlay elements in total (bubble, emoji, headline or badge). All text reads in under a second. The two panels read as a call, not a collage.

## Open question for the user
The outliers lean hard on the platform badge (about 30/35), and the classic layout uses it, but the e-date wording rule says never to show "Monkey App" to the audience. The badge is an icon, not the name, so it stays on by default. `--no-badge` turns it off if the user wants the rule to cover icons too.

## Titles
The repeatable title formats, each with its proving model video, are in `video-ideation/video-ideas/monkey-app-video-chat/videochat_title_formats.md`. Each format there maps to an archetype here.
