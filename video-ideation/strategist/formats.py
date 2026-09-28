"""Title format detectors shared by the idea authoring and the dashboard. A title can match
several formats (overlap is expected), and the same format can win in several categories,
each category gets its own numbers."""
import re

# id: (label shown in the dashboard, short chip label, regex)
FORMATS = {
    "number-list": ("Numbered list (7 signs, 12 ways)", "Numbered list", r"^\s*\d+\s+\w"),
    "signs": ("'Signs she ...' titles", "Signs", r"\bsigns?\b"),
    "hidden": ("Hidden / secret / most men miss", "Hidden or secret", r"\b(hidden|secretly|secret|most men|99% of men|miss it|always miss)\b"),
    "challenge": ("Challenge with a count or time box (100 girls, 12 hours, 30 days)", "Count or time challenge",
                  r"\b\d{1,4}\s*(girls|women|hours?|hrs|minutes?|mins?|days?|couples|strangers|approaches)\b|hours straight"),
    "i-tried": ("I tried / I tested / I asked", "I tried", r"\bi\s+(tried|tested|asked|cold approached|approached|went|found|gifted|met)\b"),
    "trust-tag": ("Trust tag (Realistic, Uncut, Real Infield)", "Trust tag", r"\b(realistic|uncut|real infield|unedited|raw)\b"),
    "pov": ("POV framing", "POV", r"\bpov\b"),
    "series": ("Numbered series (Part 2, #52, Day 3)", "Series", r"part\s*\d+|#\s*\d+|\bday\s*\d+|\bep\.?\s*\d+"),
    "place": ("Place or origin in the title (city, country, venue)", "Place in title",
              r"\b(india|indian|delhi|toronto|paris|brazil|colombia|colombian|paraguay|america|vegas|miami|russia|russian|pakistan|"
              r"pakistani|walmart|mall|gym|college|campus|public|bars?|club|nightgame|night game|at home|city|countries)\b"),
    "online-to-real": ("Online to real life (met in real life, found love)", "Online to real life",
                       r"real life|to whatsapp|found (my )?love|finding love|dating \d+ girls|my wife|find .* a (man|boyfriend|date)"),
    "how-to": ("How-to", "How-to", r"\bhow to\b"),
    "psychology": ("Psychology or science explained", "Psychology", r"psycholog|explained|science|robert greene"),
    "reaction": ("Her reaction / real reactions", "Reaction", r"\b(reaction|reactions|react)\b"),
    "breakdown": ("Infield breakdown or review", "Breakdown", r"breakdown|\binfield\b|review"),
    "guest": ("Creator or celebrity on the platform", "Guest or celebrity", r"\b(ishowspeed|goes on|guest|expert)\b"),
    "game": ("Game with a visible score or rules", "Game", r"guess|last to|truth or drink|dating show|speed date|difficulty|twist"),
    "tier": ("Tier list or ranking", "Tier list", r"tier list|ranked|ranking"),
    "superlative": ("Best / worst / every / must watch", "Superlative", r"\b(best|worst|every|must watch|ever)\b"),
}
# Packaging guidance specific to each title format, shown next to it in the dashboard instead
# of one generic "how to make a thumbnail" blurb at the bottom of the page. Every idea's own
# thumbnail brief already covers its scene, this is the one extra thing THIS format needs on
# top of the standing rule (woman as main subject, medium/wide, natural light, no dancing).
THUMB_NOTES = {
    "number-list": "Leave room for a number badge, the count is often the hook.",
    "signs": "Show the specific cue named in the title happening on her, not a generic close-up.",
    "hidden": "Bold, high-contrast callout text earns its place here, 'secret'/'hidden' pulls the eye even over a busy frame.",
    "challenge": "Make the count or clock visible (a badge, a scoreboard), it's the whole promise of the title.",
    "i-tried": "A candid, mid-attempt moment reads better than a posed one, the format sells on 'this is really happening'.",
    "trust-tag": "Keep it unstaged and a little rough around the edges, a polished shot undercuts 'Real Infield Uncut'.",
    "pov": "Frame it like the viewer is standing where you are, her reaction faces the camera.",
    "series": "Include a small episode marker (Part 2, #52), it signals a series worth subscribing for.",
    "place": "A recognizable landmark or setting detail is doing real work in this format, don't crop it out.",
    "online-to-real": "A split or before/after framing (screen vs. in-person) sells the arc faster than either half alone.",
    "how-to": "Show the moment of doing the thing, not you explaining it.",
    "psychology": "Clean and minimal, one clear expression, this audience responds to clarity over drama.",
    "reaction": "Her face, mid-reaction, is the entire thumbnail, everything else is secondary.",
    "breakdown": "A paused, slightly annotated feel (a freeze-frame look) matches the 'let's break this down' promise.",
    "guest": "If a recognizable person is in it, keep both faces clearly readable at thumbnail size.",
    "game": "Show the score, the rule, or the stakes visibly, the mechanic is the hook.",
    "tier": "Use the S-F tier board as a graphic overlay, not a plain moment shot, that's the convention tier-list viewers expect.",
    "superlative": "Go bigger and bolder than your usual thumbnail, 'best/worst/every' titles earn a more dramatic treatment.",
}

_COMPILED = {k: re.compile(v[2], re.I) for k, v in FORMATS.items()}


def detect(title: str) -> list:
    return [k for k, rx in _COMPILED.items() if rx.search(title)]


# Formats that make sense to show for each category. A format outside a category's list is never
# shown there even if a few titles happen to match, and one format can be listed in several
# categories (each with that category's own numbers).
RELEVANT = {
    "daygame": ["series", "challenge", "breakdown", "i-tried", "place", "trust-tag", "how-to", "reaction", "game", "pov"],
    "bargame": ["i-tried", "challenge", "breakdown", "place", "trust-tag", "pov", "game", "how-to", "series"],
    "video-chat-edates": ["online-to-real", "game", "series", "challenge", "guest", "place", "i-tried", "how-to", "reaction"],
    "explainer": ["hidden", "psychology", "number-list", "signs", "how-to", "superlative", "place", "i-tried"],
}
