"""Checks for written content: video scripts, concept docs, captions (.ass), hook research.

These cover the mechanical rules. Taste (is the hook strong, is it charming) is the
critic subagent's job. When the critic flags something mechanical, add it here.
"""
from __future__ import annotations

import re
from pathlib import Path

from checks import check, read_text

TS = r"(\d+):(\d{2})"
SECTION_RX = re.compile(rf"^##\s*\[{TS}\s*-\s*{TS}\]\s*(.*)$")
QUOTE_RX = re.compile(r"\"([^\"]+)\"")
PLACEHOLDER_RX = re.compile(r"\b(TODO|TBD|FIXME|lorem ipsum)\b|\[INSERT|\[PLACEHOLDER|XX:XX|\?\?\?", re.I)

# Invented dialogue from the woman in cold-approach footage (feedback memory: describe her
# reaction directionally, never write or quote her words).
HER_DIALOGUE_RX = [
    re.compile(r"^\s*\**\s*(HER|SHE|GIRL|WOMAN|GIRL ?\d)\s*\**\s*:", re.I),
    # 'she says, "..."' style attribution of her own words (not the host's VO talking about her)
    re.compile(r"\bshe\s+(?:\w+\s+){0,2}(says|said|asks|asked|replies|replied|responds|responded|goes)\b[^\"\n]{0,8}\"", re.I),
    re.compile(r"^\s*REACTION[^:\n]*:.*\"", re.I),
]

MAX_WORDS_PER_SEC = 3.5  # ~210 wpm; faster than this can't be delivered naturally on camera
MAX_HOOK_END = 10        # seconds; research says the hook must land in the first ~5-8s


def _secs(m: str, s: str) -> int:
    return int(m) * 60 + int(s)


def placeholders(text: str) -> list[str]:
    return [f"unfinished placeholder on line {i}: {line.strip()[:60]}"
            for i, line in enumerate(text.splitlines(), 1) if PLACEHOLDER_RX.search(line)][:5]


def her_dialogue(text: str) -> list[str]:
    out = []
    for i, line in enumerate(text.splitlines(), 1):
        if any(rx.search(line) for rx in HER_DIALOGUE_RX):
            out.append(f"line {i} writes or quotes the woman's words; describe her reaction directionally "
                       f"instead (no fabricated dialogue rule): {line.strip()[:70]}")
    return out


@check("script-structure", paths=["script-writing/script_*.md"], exts={".md"})
def script_structure(path: Path) -> list[str]:
    text = read_text(path) or ""
    lines = text.splitlines()
    problems = placeholders(text) + her_dialogue(text)
    if not any("hook_patterns.md" in line for line in lines[:12]):
        problems.append("no citation of the hook_patterns.md + archetype it's built on in the first lines "
                        "(script-writer rule: keep scripts traceable to the research)")
    sections = []  # (start, end, title, body_lines)
    for line in lines:
        m = SECTION_RX.match(line)
        if m:
            sections.append([_secs(m[1], m[2]), _secs(m[3], m[4]), m[5].strip(), []])
        elif line.startswith("## "):
            sections.append([None, None, line[3:], []])
        elif sections:
            sections[-1][3].append(line)
    timed = [s for s in sections if s[0] is not None]
    if not timed:
        return problems + ["no timestamped sections (## [m:ss-m:ss] NAME); pacing can't be checked"]
    if timed[0][0] != 0:
        problems.append(f"first timed section starts at {timed[0][0]}s, not 0:00")
    if "HOOK" not in timed[0][2].upper():
        problems.append(f"first section is '{timed[0][2]}', the script must open on the HOOK")
    elif timed[0][1] > MAX_HOOK_END:
        problems.append(f"hook runs to {timed[0][1]}s; it must land within the first {MAX_HOOK_END}s")
    for prev, cur in zip(timed, timed[1:]):
        if cur[0] != prev[1]:
            problems.append(f"timeline gap/overlap: '{prev[2]}' ends {prev[1]}s but '{cur[2]}' starts {cur[0]}s")
    for start, end, title, body in timed:
        if end <= start:
            problems.append(f"'{title}' has end {end}s <= start {start}s")
            continue
        spoken = " ".join(q for line in body if re.match(r"\s*(VO|LINE)\b", line) for q in QUOTE_RX.findall(line))
        words = len(spoken.split())
        rate = words / (end - start)
        if rate > MAX_WORDS_PER_SEC:
            need = words / 2.8
            problems.append(f"'{title}' packs {words} spoken words into {end - start}s ({rate:.1f} w/s, max "
                            f"{MAX_WORDS_PER_SEC}); cut the VO or give it about {need:.0f}s")
    return problems


IDEATION_SECTIONS = ["concept", "title", "thumbnail", "footage plan", "hook plan", "open questions"]


@check("ideation-doc-sections", paths=["video-ideation/ideation_*.md"], exts={".md"})
def ideation_sections(path: Path) -> list[str]:
    text = read_text(path) or ""
    heads = [h.lower() for h in re.findall(r"^##\s+(.+)$", text, re.M)]
    missing = [s for s in IDEATION_SECTIONS if not any(h.startswith(s) for h in heads)]
    problems = her_dialogue(text)  # TBDs are normal in a planning doc, they live under Open Questions
    if missing:
        problems.append(f"concept doc missing section(s): {', '.join(missing)} (see video-ideation/claude.md Doc pattern)")
    return problems


OVERCLAIM = re.compile(r"\b(every (girl|woman|one|time|single)|everyone|all of them|all (the )?girls|always|never fails)\b", re.I)


@check("title-overclaim", paths=["video-ideation/ideation_*.md", "long-form-video-editing/*/package.md"], exts={".md"})
def title_overclaim(path: Path) -> list[str]:
    """Titles promising 'every girl' etc. when the cut only shows it a couple of times (critic catch, 2026-09-26).
    Mark a title line '(verified)' once the count in the edit has been checked."""
    problems = []
    for line in (read_text(path) or "").splitlines():
        if re.search(r"\btitle", line, re.I) or line.lstrip().startswith(("-", "*", "1", "2", "3")):
            m = OVERCLAIM.search(line)
            if m and "(verified)" not in line.lower():
                problems.append(f"title claims '{m.group(0)}': count it in the edit, then fix the claim "
                                f"or mark the line (verified): {line.strip()[:80]}")
    return problems


def _ass_time(t: str) -> float:
    h, m, s = t.split(":")
    return int(h) * 3600 + int(m) * 60 + float(s)


@check("caption-safe-zone", paths=["long-form-to-shorts-video-editing/**/*.ass"], exts={".ass"})
def caption_safe_zone(path: Path) -> list[str]:
    """9:16 captions must avoid the platform UI: bottom ~20% (title, channel, caption) and top ~8%."""
    text = read_text(path) or ""
    res_y = int((re.search(r"PlayResY:\s*(\d+)", text) or [0, 1920])[1])
    res_x = int((re.search(r"PlayResX:\s*(\d+)", text) or [0, 1080])[1])
    problems = []
    if (res_x, res_y) != (1080, 1920):
        problems.append(f"PlayRes is {res_x}x{res_y}, shorts captions must be authored at 1080x1920")
    style_font = {m[0]: int(float(m[1])) for m in re.findall(r"^Style:\s*([^,]+),[^,]*,([\d.]+)", text, re.M)}
    low, high, bad_y = int(res_y * 0.08), int(res_y * 0.80), set()
    events = []
    for line in text.splitlines():
        if not line.startswith("Dialogue:"):
            continue
        parts = line.split(",", 9)
        start, end, style, body = _ass_time(parts[1]), _ass_time(parts[2]), parts[3], parts[9]
        events.append((start, end))
        if not re.sub(r"\{[^}]*\}", "", body).strip():
            problems.append(f"empty caption at {parts[1]}")
        m = re.search(r"\\pos\(\s*[\d.]+\s*,\s*([\d.]+)\s*\)", body)
        if m:
            y = float(m[1])  # alignment 2: anchor is the text's bottom edge
            top = y - style_font.get(style, 80)
            if y > high or top < low:
                bad_y.add(int(y))
    if bad_y:
        problems.append(f"captions positioned at y={sorted(bad_y)} sit in the platform UI zone (keep text between "
                        f"y={low} and y={high} on a {res_y}px frame; the bottom 20% is covered by the title/caption "
                        f"overlay on Shorts, TikTok and Reels)")
    for (s1, e1), (s2, _) in zip(events, events[1:]):
        if e1 <= s1:
            problems.append(f"caption with non-positive duration at {s1:.2f}s")
            break
    return problems[:8]


@check("hook-patterns-doc", paths=["long-form-hook-research/*/hook_patterns.md", "shorts-hook-research/*.md"],
       exts={".md"}, exclude=["**/claude.md", "**/CLAUDE.md"])
def hook_patterns_doc(path: Path) -> list[str]:
    text = read_text(path) or ""
    problems = placeholders(text)
    low = text.lower()
    if "archetype" not in low:
        problems.append("no named archetypes; the doc must name hook archetypes with real examples")
    return problems
