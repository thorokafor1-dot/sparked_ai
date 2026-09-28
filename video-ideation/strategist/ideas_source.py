"""Source of truth for video-ideation/strategist/ideas.json (run: python ideas_source.py).
Rewrite the IDEAS list each refresh, it is a judgment call, see the video-idea-dashboard skill.
Builds ideas.json. Evidence rows are looked up from the real
outlier-tracking data by title substring so scores/views/urls are never hand-typed."""
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
niche = json.load(open(ROOT / "outlier-tracking/niche-long-form/data.json", encoding="utf-8"))
general = json.load(open(ROOT / "outlier-tracking/general-long-form/data.json", encoding="utf-8"))


MISSING = []


def find(key, channel=None):
    key_l = key.lower()
    for source, rows in (("niche", niche), ("general", general)):
        hits = [r for r in rows if (key_l in r["title"].lower() or key_l in (r.get("coldTitle") or "").lower()) and (channel is None or channel.lower() in r["channel"].lower())]
        if hits:
            r = max(hits, key=lambda h: h.get("score") or h.get("scoreNum") or 0)
            if source == "niche":
                stat = f'{round(r["score"])}x avg'
                v = r["views"]; views = (f"{v/1e6:.1f}M" if v >= 1e6 else f"{round(v/1e3)}K" if v >= 1e3 else str(v)) + " views"
            else:
                stat = r["scoreRaw"]
                views = None
            return {
                "title": r["title"].strip().replace(" " + chr(0x2014) + " ", ", ").replace(chr(0x2014), ","),
                "channel": r["channel"].strip(),
                "stat": stat,
                "views": views,
                "source": source,
                "url": r["videoUrl"],
                "thumbnail": r["thumbnailUrl"],
                "vid": r["vid"],
                "subs": r.get("subscribers") if source == "niche" else None,
                "score": round(r["score"], 1) if source == "niche" else None,
                "adapted_title": r.get("coldTitle"),
            }
    MISSING.append(key)
    return {"title": key, "channel": "", "stat": "", "views": None, "source": "", "url": "", "thumbnail": "", "vid": "", "adapted_title": None}


PREFIX = ("Use the uploaded photo as the man and keep his face and likeness exactly as in the photo. "
          "Photorealistic candid smartphone-style photo, medium-wide framing, natural lighting, no vignette, "
          "no heavy color grade. A woman is the clear main subject of the frame, ")
SUFFIX = (" The man is present but secondary, at the edge of the frame or slightly behind her. "
          "No text, no logos, no dancing.")


def prompt(woman, scene):
    return f"{PREFIX}{woman}. Scene: {scene}.{SUFFIX}"


IDEAS = [
    # ---------------- DAYGAME ----------------
    dict(
        id="dg-100-women", category="daygame", potential="High",
        title="I Approached 100 Women In One Day (Uncut, Every Reaction)",
        pattern="Count challenge + 'uncut' trust tag",
        strength="proven",
        evidence=[("cold approach' 100 girls", "Dylan McKnight: same 100-approach challenge structure, one of the highest infield scores in the tracked set."),
                  ("12 Hours Straight", "Time-boxed marathon format from a niche channel."),
                  ("A Realistic 60 Minutes", "'Uncut / realistic' framing is what makes long infield feel trustworthy.")],
        why="A hard number plus 'uncut' promises a scoreboard the viewer can track, which carries a long video. Three different niche channels have landed this exact promise.",
        hook="I have a rule for today: I don't go home until I've talked to 100 women. Here is the scoreboard.",
        thumbnail="A woman's genuine amused/surprised reaction mid-conversation on a busy street, medium-wide. A '100' counter badge added later in the thumbnail tool. Creator visible but secondary.",
        prompt=prompt("laughing with a surprised, genuinely amused expression while listening to someone off-frame", "busy daytime downtown sidewalk, shoppers softly blurred behind her"),
        footage="A full day of approaches with a running tally on screen. If a full 100 is unrealistic, use 50 and change the title number.",
        risk="Needs a dedicated shoot day. Keep the number honest, viewers check it.",
    ),
    dict(
        id="dg-60-min", category="daygame", potential="High",
        title="60 Real Minutes Of Approaching Women: My Actual Success Rate (Uncut)",
        pattern="'Realistic' time-box + real stats",
        strength="proven",
        evidence=[("A Realistic 60 Minutes", "Alex Leon: the exact one-hour, uncut format, a top in-person performer."),
                  ("12 Hours Straight", "Chris Goldy runs the same time-box promise at 12 hours."),],
        why="Showing real numbers, including the misses, is the differentiator from highlight-reel channels. It builds the trust that makes viewers watch a full hour.",
        hook="One hour, one street, no cuts. I'm keeping the real numbers, including the misses.",
        thumbnail="A woman smiling warmly mid-chat on a sunny street, medium-wide, clock or '60:00' timer badge added later. Creator secondary.",
        prompt=prompt("smiling warmly and relaxed, mid-conversation", "sunny pedestrian street with cafes, soft daylight"),
        footage="One continuous hour of approaches (or a strict edit of one hour of real time) with hits and misses included.",
        risk="Copies a proven format closely, so lean on your own numbers and city to feel original.",
    ),
    dict(
        id="dg-intimidating", category="daygame", potential="Medium",
        title="Cold Approaching The Most Intimidating Women At The Mall (Part 1)",
        pattern="Series with 'Part N' + intimidation hook",
        strength="proven",
        evidence=[("Intimidating Baddies In Walmart", "Chris Bizness: the 'intimidating women in a mundane location, Part N' series format."),
                  ("Wholesome Reactions", "simpleGworld: a real-reactions framing on public approaches.")],
        why="'Intimidating' names the viewer's own fear, and 'Part 1' seeds a series so one video promotes the next.",
        hook="These are the women most guys walk right past. Today I'm walking up to every one of them.",
        thumbnail="A stylish, confident woman looking at the camera with a small curious smile, mall background, medium-wide. Creator approaching from the side.",
        prompt=prompt("stylish and confident, looking toward the camera with a small curious smile", "modern shopping mall concourse with warm storefront lighting"),
        footage="A mall shoot focused on the approaches you'd normally hesitate on.",
        risk="Avoid a 'baddies' label that reads as objectifying, keep the tone confident and respectful (brand: cool, mature).",
    ),
    dict(
        id="dg-remember-me", category="daygame", potential="Medium",
        title="I Ran Into A Girl I Approached A Year Ago. Her Reaction",
        pattern="Reunion + 'Her Reaction'",
        strength="adapted",
        evidence=[("Does She Remember Me", "Cross-niche reunion format at multi-million-view reach; the adapted cold-approach title is in the swipe file."),
                  ("Her Reaction", "Real Princess Sophia: 'Her Reaction' reunion title, same emotional payoff.")],
        why="Reunion plus reaction is one of the most repeatable emotional payoffs on the platform, and it maps cleanly to 'the one that got away'.",
        hook="A year ago I approached her once. Today I found out if she remembers.",
        thumbnail="A woman's face caught mid-recognition, eyebrows lifted and a growing smile, medium-wide, street setting.",
        prompt=prompt("eyes wide with a moment of recognition turning into a smile", "city street corner in daylight"),
        footage="Only possible with a real past contact who agrees to be filmed. Do not stage or fabricate.",
        risk="Needs a real, consented reunion. Evidence is cross-niche, not proven in cold approach yet.",
    ),
    dict(
        id="dg-places-tier", category="daygame", potential="High", status="Script written",
        title="Best Places to Cold Approach in Public (TIER LIST)",
        pattern="(TIER LIST) title format",
        strength="adapted",
        evidence=[("Reading Your Worst Approach Stories", "Approach content already performs cross-niche when framed as a game."),
                  ("How to Talk to Any woman", "Broad how-to demand exists in-niche.")],
        why="Coach Knox's tier-list titles show the format is live in dating right now, and nobody is doing it with real in-person footage. Already scripted.",
        hook="I've approached women in every public place. I ranked all eleven, S tier to F tier, based on what actually happened.",
        thumbnail="A woman's reaction with a large S or F tier badge added later, medium-wide, mixed public settings.",
        prompt=prompt("smiling, genuinely engaged in conversation", "sunny outdoor plaza with cafe seating"),
        footage="One representative clip per location (11 locations). Script: script-writing/script_best_places_tier_list.md.",
        risk="Tier placements are still a draft until you correct them against real results.",
    ),
    # ---------------- BARGAME ----------------
    dict(
        id="bg-line-reaction", category="bargame", potential="High",
        title="I Said This At The Bar... Her Reaction",
        pattern="'I said X... Her Reaction' mini-series",
        strength="adapted",
        evidence=[("She CRIED After I Said This", "NanoBaiter: 'after I said this' reaction title at very large reach (cross-niche)."),
                  ("Her Reaction", "Real Princess Sophia: 'Her Reaction' at multi-million reach."),
                  ("POV: She Invited Me Home", "Nightgame POV with a 'Real Infield (Uncut)' trust tag, a top in-person bar-adjacent score.")],
        why="One clip is one episode, so your weekly bar footage becomes a series with almost no extra production. Reaction-first titles are the strongest cross-niche pattern found.",
        hook="One line. One woman. Watch what happens.",
        thumbnail="A woman at a bar mid-reaction (laughing, eyes wide), warm bar lighting, medium-wide, creator half in frame at the edge.",
        prompt=prompt("laughing and visibly surprised, hand near her face", "dimly lit stylish bar with warm ambient lighting, other patrons softly blurred"),
        footage="Any single approach at the bar with a clear, on-camera reaction. Never write words for her, let the clip carry it.",
        risk="Bar-specific niche data is thin, so this is adapted from cross-niche proof.",
    ),
    dict(
        id="bg-10-lines", category="bargame", potential="High",
        title="I Tested 10 Pickup Lines At The Bar (Ranked By Her Reaction)",
        pattern="'I Tested' + ranking",
        strength="adapted",
        evidence=[("Her Reaction", "Reaction-ranking has cross-niche reach."),
                  ("cold approach' 100 girls", "Niche precedent for a numbered test challenge."),
                  ("you'll cringe", "Jak Piggott: numbered self-test with a stakes tag.")],
        why="Ranking gives every clip a reason to exist and viewers stay to see the top of the list. Reuses your weekly bar footage.",
        hook="Ten lines, ten different women. I'm ranking them by what actually happened, not by what I hoped.",
        thumbnail="A woman reacting to someone off-frame at a bar, smiling with raised eyebrows, medium-wide. Rank badge added later.",
        prompt=prompt("amused with raised eyebrows, mid-laugh", "lively bar with string lights and blurred patrons"),
        footage="Ten approaches with a distinct line each, clean audio of your line, her reaction visible.",
        risk="Ranking must reflect real reactions. Describe them directionally, never quote her.",
    ),
    dict(
        id="bg-alone", category="bargame", potential="High",
        title="How To Go To A Bar Alone And Actually Meet Women (Real Footage)",
        pattern="How-to + 'real footage' proof",
        strength="proven",
        evidence=[("How to Go to a Bar Alone", "Gentlemen's Collective: 1.3M views on a 290K channel, the strongest bar-topic demand signal found."),
                  ("Go Out Alone And Meet Girls At Bars", "Same topic, second independent outlier."),],
        why="Real search demand ('go to a bar alone') plus a competitor gap: those videos are talking heads, you can show it happening.",
        hook="Most guys are scared to walk into a bar alone. Here is exactly what I do, filmed live.",
        thumbnail="A woman at the bar smiling at the camera as if just noticing someone arrive, medium-wide, creator entering the frame.",
        prompt=prompt("relaxed, looking over with a friendly curious smile", "bar counter with warm pendant lights"),
        footage="Arrival, first 20 minutes, first conversation, all from one solo night.",
        risk="Top competitors are established channels, so the real-footage angle is the whole edge.",
    ),
    dict(
        id="bg-pov", category="bargame", potential="Medium",
        title="POV: I Talked To Every Woman At The Bar. Real Infield (Uncut)",
        pattern="POV + 'Real Infield (Uncut)' trust tag",
        strength="proven",
        evidence=[("POV: She Invited Me Home", "Empathic Pickup Artist: the top-scoring bar/nightgame POV title in the tracked set."),
                  ("Owen Cook Nightgame", "Nightgame breakdown formats keep resurfacing.")],
        why="POV framing puts the viewer in your seat, and 'uncut' is the trust signal that separates real infield from staged clips.",
        hook="No cuts, no edits. This is one night at the bar, exactly as it happened.",
        thumbnail="A first-person-feeling shot of a woman turning toward the camera with a smile at a bar, medium-wide.",
        prompt=prompt("turning toward the camera with a warm smile", "crowded bar seen from a first-person seated angle"),
        footage="A continuous section of a bar night with mic audio.",
        risk="Do not imply outcomes that did not happen, no fabricated results in the title.",
    ),
    dict(
        id="bg-worst", category="bargame", potential="Medium",
        title="My 5 Worst Bar Approaches Of The Year (And What I'd Change)",
        pattern="Self-deprecating cringe compilation",
        strength="adapted",
        evidence=[("A New Level of Rejection", "Smosh Pit: reading worst approach stories reached ~3M views."),
                  ("you'll cringe", "Jak Piggott: a niche 'you'll cringe' self-test performs."),],
        why="Vulnerability builds trust and rewatch value, and it is cheap to make from misses you already have.",
        hook="Five approaches that went badly. I'm watching them back with you.",
        thumbnail="A woman with a polite, awkward-smile expression at a bar, medium-wide, creator turned slightly away.",
        prompt=prompt("giving a polite, slightly awkward smile", "bar with warm lighting and blurred patrons"),
        footage="Your five clearest misses from weekly bar footage.",
        risk="Show the real reaction, not a dramatized rejection, and never quote her.",
    ),
    # ---------------- VIDEO CHAT E-DATES ----------------
    dict(
        id="vc-10-edates", category="video-chat-edates", potential="High",
        title="I Went On 10 Video Chat E-Dates In One Night (Ranked)",
        pattern="'Dating N girls' + ranking",
        strength="proven",
        evidence=[("DATING 10 GIRLS I MET ON OMEGLE", "RAMESH MAITY: 5.2M views on a 2.3M channel."),
                  ("SPEED DATE ON OMEGLE", "Kalogeras Sisters speed-date format, 4.6M views."),
                  ("Omegle Dating Show", "Family Friendly: dating-show framing, 3.2M views.")],
        why="The largest real data pool in the tracker (174 entries) repeats one promise: several dates, one video. Ranking adds a payoff that keeps people to the end.",
        hook="Ten e-dates in one night. At the end, only one gets a real date.",
        thumbnail="A woman's face on a phone/laptop video call, smiling and engaged, medium framing, soft home lighting. Creator secondary.",
        prompt=prompt("smiling on a video call, seen on a laptop screen in front of the man, engaged and relaxed", "cozy evening room lit by the laptop and a warm lamp"),
        footage="Ten e-dates, each with a clear moment and permission to show it. Blur usernames and personal info.",
        risk="Keep wording 'e-dates', never name the app. Get consent and blur handles/PII.",
    ),
    dict(
        id="vc-real-life", category="video-chat-edates", potential="High",
        title="I Met My Best E-Date In Real Life (First Date Reaction)",
        pattern="Online to real life payoff",
        strength="proven",
        evidence=[("MET IN REAL LIFE", "adarshuc: 6.7M views, the 'met in real life' payoff."),
                  ("FOUND MY Love with 20 HYPEMAN", "adarshuc: 6.0M views, same channel, same arc."),
                  ("OMEGLE TO WHATSAPP", "RAMESH MAITY: 4.9M views on the move from chat to contact.")],
        why="The 'online to real life' arc is the single most repeated winner in this bucket across multiple channels.",
        hook="We met on a video chat. Tonight was our first time in the same room.",
        thumbnail="A woman greeting the camera with a big surprised smile in a real cafe, medium-wide, creator secondary.",
        prompt=prompt("beaming with a surprised happy smile as if meeting someone for the first time", "sunny cafe terrace with soft daylight"),
        footage="Only with her clear consent to film the meeting. Real, not staged.",
        risk="Privacy and consent are non-negotiable, blur PII, and skip if she is not comfortable on camera.",
    ),
    dict(
        id="vc-speed", category="video-chat-edates", potential="Medium",
        title="Speed E-Dating 10 Strangers: Only One Gets A Second Date",
        pattern="Speed-dating elimination",
        strength="proven",
        evidence=[("SPEED DATE ON OMEGLE", "Kalogeras Sisters: 4.6M views."),
                  ("Omegle Dating Show", "Dating-show structure at 3.2M views.")],
        why="A fixed round structure with an eliminator gives the edit a built-in arc and makes every e-date a mini-episode.",
        hook="Ten strangers, three minutes each. One of them gets a second e-date.",
        thumbnail="A woman mid-laugh on a video call with a countdown-style feel, medium framing.",
        prompt=prompt("laughing warmly on a video call, seen on a laptop screen", "tidy desk with a warm lamp in the evening"),
        footage="Ten timed e-dates, consistent framing, screen capture plus your reactions.",
        risk="Keep the tone warm and mature, not mocking. Consent and blurring apply.",
    ),
    dict(
        id="vc-3am", category="video-chat-edates", potential="Medium",
        title="3 AM E-Dates: How Many Women Would Give Me Their Number?",
        pattern="Late-night challenge + count",
        strength="proven",
        evidence=[("RIZZING GIRLS AT 3AM", "MarcusT: 3.4M views on a 2.4M channel, day-numbered challenge."),
                  ("MAKES BADDIES", "Jaiden 28 Medeiros: 'makes X fold' catchphrase, small-channel outlier."),
                  ("IShowSpeed Goes On Omegle", "Creator-goes-on-video-chat drives curiosity at 3.8M views.")],
        why="A time-of-night plus an outcome count is a simple, repeatable series hook.",
        hook="It's 3 AM. Let's see how many of these e-dates end with a number.",
        thumbnail="A woman on a late-night video call, softly lit by the screen, curious smile, medium framing.",
        prompt=prompt("softly lit by a laptop screen, curious and playful smile", "dark bedroom-style setting lit by the screen and a small lamp"),
        footage="A late-night session with a running tally on screen.",
        risk="Source titles lean chaotic and meme-heavy, keep yours calm and mature (brand vibe).",
    ),
    dict(
        id="vc-tier", category="video-chat-edates", potential="High",
        title="Ranking Every Video Chat E-Date I've Had (TIER LIST)",
        pattern="(TIER LIST) applied to your largest footage pool",
        strength="adapted",
        evidence=[("DATING 10 GIRLS I MET ON OMEGLE", "Ranking-style multi-date content already lands at 5M+ views."),
                  ("Truth or Drink", "Graded game structure (severity levels) at 1.7M views, cross-niche.")],
        why="You already own the biggest footage library in this category, and tier lists turn a pile of clips into a debate viewers comment on.",
        hook="I've had a lot of e-dates. I finally ranked them, S tier to F tier.",
        thumbnail="A woman reacting on a video call with a large S badge added later, medium framing.",
        prompt=prompt("delighted and laughing on a video call, seen on a laptop screen", "warm-lit room, evening"),
        footage="Best clip from a range of past e-dates, with consent, PII blurred.",
        risk="No names, no apps, no handles on screen. Rankings should be about the conversation, not people's looks.",
    ),
    # ---------------- EXPLAINER ----------------
    dict(
        id="ex-7-signs", category="explainer", potential="High",
        title="7 Signs She Wants You To Approach Her (Real Footage Proof)",
        pattern="Numbered 'hidden signs' + real proof",
        strength="proven",
        evidence=[("7 Hidden Signs She Secretly Craves You", "Iron Mindset: 594x channel average, the top outlier in the entire tracker."),
                  ("She Always Shows These 3 Signs", "STOIC MASTERY: 437K views on a 27K channel, same 'signs' structure."),
                  ("12 Subtle Body Language Signs", "Affinee: 117x on a tiny channel.")],
        why="'Signs she likes you' is the strongest demand cluster in the data. Most versions are faceless voiceover, you can show every sign happening in your own footage.",
        hook="Seven signs a woman wants you to walk over. I filmed all seven.",
        thumbnail="A woman glancing toward the camera with a small interested smile, medium-wide, creator in the background. Number badge added later.",
        prompt=prompt("glancing over with a small interested smile", "cafe seating area with soft window light"),
        footage="Seven clean moments from your infield footage that each show a real sign, described by you, not scripted for her.",
        risk="Market is crowded with faceless clones. Your footage proof is the only durable edge.",
    ),
    dict(
        id="ex-not-interested", category="explainer", potential="High",
        title="She's Not Interested? Watch This Before You Walk Away (Real Reactions)",
        pattern="'Even when she's not interested' reassurance",
        strength="proven",
        evidence=[("How to Make Her WANT You", "Feminine Connection: 400x channel average."),
                  ("You Think She's Not intrested", "Female Couple Circle: 117x, 'watch this first' hook.")],
        why="It speaks to the exact moment a viewer is about to give up, which is both a strong hook and a clear promise.",
        hook="If you've ever thought a woman wasn't interested and walked away, this is for you.",
        thumbnail="A woman with a neutral-to-warming expression mid-conversation, medium-wide, creator engaged.",
        prompt=prompt("neutral at first, a small warmth beginning at the corners of her smile", "quiet street with soft daylight"),
        footage="Clips where the first response was flat but the interaction went well, described directionally.",
        risk="Do not promise she will always come around. Keep it honest.",
    ),
    dict(
        id="ex-body-lang", category="explainer", potential="Medium",
        title="12 Subtle Body Language Signs She Likes You (I Filmed The Real Ones)",
        pattern="Numbered signs + 'filmed the real ones'",
        strength="proven",
        evidence=[("12 Subtle Body Language Signs", "Affinee: 117x channel average."),
                  ("4 Female Body Language Signs", "Mind Signals: 'signs most men miss' angle."),],
        why="Body-language explainers pull consistent search demand, and visual proof is naturally more watchable than a voiceover.",
        hook="Twelve small signals. I'll show you the real ones from my own footage.",
        thumbnail="A close medium shot of a woman touching her hair with a shy smile, medium-wide with room to show a sign highlight later.",
        prompt=prompt("shy warm smile, touching her hair, leaning slightly toward someone", "quiet cafe, soft daylight"),
        footage="A dozen short clips, each isolating one body-language moment.",
        risk="Keep claims modest: signals are probabilities, not guarantees.",
    ),
    dict(
        id="ex-talk-anyone", category="explainer", potential="Medium",
        title="How To Talk To Any Woman, Anywhere (Real Examples, Uncut)",
        pattern="Broad how-to + real examples",
        strength="proven",
        evidence=[("How to talk to Any woman", "The Dark Needle: ~598K views on a 479K channel."),
                  ("How To Approach A Girl", "Raj Shamani Clips: broad how-to-approach demand."),],
        why="Broad how-to titles capture the largest search audience, real examples make it different from generic advice.",
        hook="You don't need a perfect line. You need these three things, and I'll show each one working.",
        thumbnail="A woman in an easy relaxed conversation, medium-wide, creator engaged, outdoors.",
        prompt=prompt("relaxed and smiling, easy and natural body language", "outdoor plaza in soft daylight"),
        footage="Short clips of the same three skills across different settings.",
        risk="Broad topic means heavy competition, differentiate with your footage and clarity.",
    ),
    dict(
        id="ex-10-seconds", category="explainer", potential="Medium",
        title="How I Create Attraction In The First 10 Seconds (Infield Breakdown)",
        pattern="Infield breakdown",
        strength="proven",
        evidence=[("How To Create Sexual Tension During Cold Approach", "ApproachCraft: an 'infield breakdown' at 30x channel average."),
                  ("Owen Cook Nightgame", "Breakdown-style teaching clips keep performing.")],
        why="Teaching from a real clip bridges the explainer category's huge demand into infield content you already shoot.",
        hook="I'm going to freeze this approach and show you exactly what happens in the first ten seconds.",
        thumbnail="A woman's face lighting up at the start of a conversation, medium-wide, creator entering from the side.",
        prompt=prompt("face lighting up with a spontaneous smile as someone walks up", "sunny city street"),
        footage="Three or four approaches with clear first-ten-second moments to freeze and annotate.",
        risk="Breakdown narration must describe reactions directionally, never invent her words.",
    ),
    dict(
        id="ex-3-signs", category="explainer", potential="Medium",
        title="3 Signs She Wants You To Talk To Her (Most Men Miss #2)",
        pattern="Short numbered list + 'most men miss'",
        strength="proven",
        evidence=[("She Always Shows These 3 Signs", "STOIC MASTERY: 437K views, the 3-signs structure."),
                  ("4 Female Body Language Signs", "'Most men miss' curiosity gap.")],
        why="A short list is the lowest-effort way to enter the top demand cluster and tests the format cheaply before a longer version.",
        hook="Three signs. Almost everyone misses the second one.",
        thumbnail="A woman half-turned toward the camera with a soft smile, medium-wide.",
        prompt=prompt("half-turned toward the camera with a soft interested smile", "cafe window seat in soft light"),
        footage="Three clips, one per sign, each 20 to 30 seconds.",
        risk="'Most men miss' is a curiosity claim, make sure the second sign really is non-obvious.",
    ),
]


exec((Path(__file__).parent / "ideas_revisions.py").read_text(encoding="utf-8"))
exec((Path(__file__).parent / "ideas_expansion.py").read_text(encoding="utf-8"))

out = {
    "generated": date.today().isoformat(),
    "source": "outlier-tracking niche-long-form (In-Person / Video Chat / Explainer formats) + general-long-form, scored by extract_patterns.py",
    "headline_finding": (
        "Explainer/psychology titles have the strongest outliers in the tracker (top 594x channel average) and video chat e-date "
        "content has by far the most data (174 entries), while bar-specific data is thin (11 entries). Most explainer winners are "
        "faceless voiceover, so on-camera real-footage proof is the differentiation. Bar ideas lean on cross-niche reaction and "
        "ranking patterns, not direct bar outliers."
    ),
    "style_rules_note": (
        "Every thumbnail brief has a woman as the main visual focus (standing rule, no exceptions). Titles never name the app used "
        "for video chat, always say e-dates. No fabricated dialogue, no dance angle."
    ),
    "categories": {},
}
labels = {"daygame": "Daygame", "bargame": "Bargame", "video-chat-edates": "Video chat e-dates", "explainer": "Explainers"}
for cat in labels:
    out["categories"][cat] = {"label": labels[cat], "ideas": []}
for idea in IDEAS:
    ev = []
    for key, note in idea.pop("evidence"):
        row = find(key)
        row["note"] = note
        ev.append(row)
    idea["evidence"] = ev
    out["categories"][idea["category"]]["ideas"].append(idea)

out["parked"] = PARKED
for cat, d in out["categories"].items():
    d["count"] = len(d["ideas"])

for _i in IDEAS:
    if _i["strength"] == "proven":
        _strong = [e for e in _i["evidence"] if e["source"] == "niche" and (e["score"] or 0) >= 20]
        if len(_strong) < 2:
            sys.exit(f"{_i['id']} is labelled proven but has {len(_strong)} niche evidence row(s) at 20x or more")
from collections import Counter  # noqa: E402
_per = Counter(i["category"] for i in IDEAS)
assert all(v == 10 for v in _per.values()) and len(_per) == 4, f"expected 10 ideas in each of 4 categories, got {dict(_per)}"

dest = ROOT / "video-ideation/strategist/ideas.json"
dest.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
if MISSING:
    sys.exit(f"missing evidence: {MISSING}")
print("wrote", dest, sum(d["count"] for d in out["categories"].values()), "ideas")
