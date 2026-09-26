"""Pre-flight checks the posting scripts run on their own inputs before uploading anything.

Each upload script calls enforce(...) right after it has the caption/title and again once
it has the local video file. Any problem aborts the run with exit code 2 before a browser
opens or an API call is made, so a bad post never reaches the platform.

The final Publish step stays human (see each posting folder's claude.md); this only
catches mechanical mistakes before that point.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import media  # noqa: E402
from checks import EM_DASH  # noqa: E402

HASHTAG_RX = re.compile(r"(?<!\w)#\w+")
PLACEHOLDER_RX = re.compile(r"\b(TODO|TBD|FIXME|lorem ipsum)\b|\[INSERT|\[PLACEHOLDER|\{\{|\}\}|\?\?\?", re.I)

CAPTION_MAX = {"instagram": 2200, "tiktok": 2200, "facebook": 5000}
HASHTAG_RANGE = {"facebook": (1, 3), "instagram": (0, 30), "tiktok": (0, 30)}  # FB 1-3 is the user's rule; IG's 30 is a hard platform cap
SHORT_MAX_SECONDS = {"instagram": 180, "facebook": 180, "tiktok": 600, "youtube": 180}


def text_problems(label: str, text: str) -> list[str]:
    problems = []
    if not text.strip():
        problems.append(f"{label} is empty")
    if EM_DASH in text:
        problems.append(f"{label} contains an em dash; rewrite with a comma, period or parentheses")
    m = PLACEHOLDER_RX.search(text)
    if m:
        problems.append(f"{label} still has a placeholder: '{m.group(0)}'")
    return problems


def caption_problems(platform: str, caption: str) -> list[str]:
    problems = text_problems(f"{platform} caption", caption)
    limit = CAPTION_MAX[platform]
    if len(caption) > limit:
        problems.append(f"{platform} caption is {len(caption)} chars, limit {limit}")
    tags = HASHTAG_RX.findall(caption)
    lo, hi = HASHTAG_RANGE[platform]
    if not lo <= len(tags) <= hi:
        problems.append(f"{platform} caption has {len(tags)} hashtags, use {lo}-{hi}")
    if len(set(t.lower() for t in tags)) != len(tags):
        problems.append(f"{platform} caption repeats a hashtag")
    return problems


def vertical_video_problems(platform: str, path: Path) -> list[str]:
    """Short-form (Reels / TikTok / Shorts) file specs."""
    try:
        v = media.streams(path, "video")
        a = media.streams(path, "audio")
        d = media.duration(path)
    except Exception as e:  # noqa: BLE001
        return [f"could not read video {path.name}: {e}"]
    problems = []
    if not v:
        return ["file has no video stream"]
    w, h = int(v[0].get("width", 0)), int(v[0].get("height", 0))
    if abs(w / max(h, 1) - 9 / 16) > 0.01:
        problems.append(f"video is {w}x{h}, not 9:16 vertical")
    if h < 1280:
        problems.append(f"video height {h}px, upload at least 720x1280 (1080x1920 preferred)")
    if not a:
        problems.append("video has no audio track")
    if d > SHORT_MAX_SECONDS[platform]:
        problems.append(f"video is {d:.0f}s, {platform} short-form limit is {SHORT_MAX_SECONDS[platform]}s")
    if v[0].get("codec_name") not in ("h264", "hevc"):
        problems.append(f"video codec {v[0].get('codec_name')}, re-encode to h264")
    return problems


def youtube_problems(title: str, description: str, tags: str, thumbnail: str | None, video: str) -> list[str]:
    problems = text_problems("YouTube title", title)
    if len(title) > 100:
        problems.append(f"YouTube title is {len(title)} chars, limit 100")
    if EM_DASH in description:
        problems.append("YouTube description contains an em dash")
    if PLACEHOLDER_RX.search(description):
        problems.append("YouTube description still has a placeholder")
    if len(description.encode("utf-8")) > 5000:
        problems.append("YouTube description is over 5000 bytes")
    for label, text in (("title", title), ("description", description)):
        if "<" in text or ">" in text:
            problems.append(f"YouTube {label} contains < or >, which the API rejects")
    if len(tags) > 500:
        problems.append(f"YouTube tags total {len(tags)} chars, limit 500")
    vp = Path(video)
    if not vp.is_file():
        problems.append(f"video file not found: {video}")
    else:
        try:
            v = media.streams(vp, "video")
            if not media.streams(vp, "audio"):
                problems.append("video has no audio track")
            if v and int(v[0].get("height", 0)) < 720 and int(v[0].get("width", 0)) < 720:
                problems.append("video resolution is below 720p")
        except Exception as e:  # noqa: BLE001
            problems.append(f"could not read video: {e}")
    if thumbnail:
        tp = Path(thumbnail)
        if not tp.is_file():
            problems.append(f"thumbnail not found: {thumbnail}")
        else:
            import checks_image
            problems += [f"thumbnail: {p}" for p in checks_image.thumbnail_specs(tp)]
    return problems


def enforce(problems: list[str], what: str = "post") -> None:
    """Abort the posting run if any pre-flight problem was found."""
    if not problems:
        print(f"Pre-flight OK ({what}).", flush=True)
        return
    print(f"PRE-FLIGHT FAILED ({what}), nothing was uploaded. Fix these and re-run:", file=sys.stderr)
    for p in problems:
        print(f"  - {p}", file=sys.stderr)
    sys.exit(2)
