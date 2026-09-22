"""Weekly automated refresh for the General Long/Short Form Outliers swipe files.

Runs unattended via GitHub Actions (.github/workflows/general_long_form_curation.yml
and general_short_form_curation.yml). Each run:

  1. Scans for fresh candidates: views >= 500,000, published in the last 90 days,
     English title, real (not a Short) for long-form / a Short for short-form. This
     is a simpler, purely absolute-view bar than general_outlier_finder.py's
     relative-outlier multiplier logic -- that script is still the *manual*
     discovery tool for the human/Claude-curated batches; this one is the automated
     weekly top-up with the bar actually requested for these tabs (see the 2026-09
     session that moved General Long/Short Form to a 500K-views standard).
  2. Prunes existing entries whose published_at is more than 90 days old, and any
     whose video has gone unavailable.
  3. Drops new candidates that are already in the file (by video ID), duplicates of
     each other, or match known AI-content-mill / spam channel patterns.
  4. Sends the survivors to Claude (Anthropic API) to pick the best ones and write
     full cold-approach adaptations (pattern/trigger/thumbnail/formula/why/
     translation/ca_title/ca_thumbnail/notes), matching the schema and quality bar
     of the hand-curated entries already in this file.
  5. Rewrites SWIPE_FILE = [...] with pruned-old + curated-new entries and
     regenerates data.json the normal way.

Needs YOUTUBE_API_KEY and ANTHROPIC_API_KEY (GitHub Actions secrets in CI; reads
outlier-tracking/.env for local runs). Costs a handful of Claude API calls per run,
each with a bounded prompt (candidates are capped at MAX_CANDIDATES_TO_CLAUDE).
"""
import argparse
import base64
import json
import os
import re
import subprocess
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, _THIS_DIR)
sys.path.insert(0, os.path.join(_THIS_DIR, "general-long-form"))
sys.path.insert(0, os.path.join(_THIS_DIR, "general-short-form"))

from common import (  # noqa: E402
    build_youtube_client,
    execute_request,
    get_video_stats,
    get_channel_stats,
    is_short_video,
    is_english_title,
    pick_thumbnail,
)

LOOKBACK_DAYS = 90
MIN_VIEWS = 500_000
MAX_CANDIDATES_TO_CLAUDE = 40
MAX_NEW_ENTRIES_PER_RUN = 8

SPAM_CHANNEL_HINTS = [
    "drama", "story tv", "theater", "heartthrob", "heartbeat", "pureberry",
    "sweet drama", "love story", "warm chapter", "movie planet", "cts timepass",
]

REQUIRED_FIELDS = [
    "niche", "pattern", "trigger", "thumbnail", "formula", "why",
    "translation", "ca_title", "ca_thumbnail", "notes",
]


def _load_local_env() -> None:
    """Local-run convenience only -- CI sets these as real env vars via secrets."""
    env_path = os.path.join(_THIS_DIR, ".env")
    if not os.path.exists(env_path):
        return
    for line in open(env_path, encoding="utf-8"):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


def _is_spam_channel(channel: str) -> bool:
    c = channel.lower()
    return any(hint in c for hint in SPAM_CHANNEL_HINTS)


def _tab_config(tab: str) -> Dict[str, Any]:
    if tab == "long-form":
        from general_outlier_finder import KEYWORDS  # noqa: E402
        return {
            "module_path": os.path.join(_THIS_DIR, "general-long-form", "general_outlier_swipe_file.py"),
            "data_path": os.path.join(_THIS_DIR, "general-long-form", "data.json"),
            "keywords": KEYWORDS,
            "want_short": False,
            "label": "General Long Form Outliers",
        }
    elif tab == "short-form":
        from general_shorts_finder import KEYWORDS  # noqa: E402
        return {
            "module_path": os.path.join(_THIS_DIR, "general-short-form", "general_shorts_swipe_file.py"),
            "data_path": os.path.join(_THIS_DIR, "general-short-form", "data.json"),
            "keywords": KEYWORDS,
            "want_short": True,
            "label": "General Short Form Outliers",
        }
    raise ValueError(f"Unknown tab '{tab}'")


def _parse_duration_seconds(duration_str: str) -> int:
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", duration_str or "")
    if not m:
        return 0
    h, mi, se = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + se


def _format_duration(seconds: int) -> str:
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def scan_candidates(cfg: Dict[str, Any], existing_vids: set) -> List[Dict[str, Any]]:
    youtube = build_youtube_client()
    if not youtube:
        print("No YouTube API key found. Skipping scan.")
        return []

    published_after = (datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    seen_ids = set()
    candidates: List[Dict[str, Any]] = []

    for keyword in cfg["keywords"]:
        request = youtube.search().list(
            q=keyword, part="snippet", type="video", maxResults=50,
            order="viewCount", publishedAfter=published_after,
            fields="items(id/videoId,snippet/title,snippet/channelTitle,snippet/publishedAt)",
        )
        response = execute_request(request)
        if not response:
            continue

        for item in response.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            if not video_id or video_id in seen_ids or video_id in existing_vids:
                continue

            stats = get_video_stats(youtube, video_id)
            if not stats:
                continue

            view_count = int(stats.get("statistics", {}).get("viewCount", 0) or 0)
            if view_count < MIN_VIEWS:
                continue

            title = stats.get("snippet", {}).get("title", "")
            if not is_english_title(title):
                continue

            channel_title = stats.get("snippet", {}).get("channelTitle", "")
            if _is_spam_channel(channel_title):
                continue

            tags = stats.get("snippet", {}).get("tags", []) or []
            duration = stats.get("contentDetails", {}).get("duration", "")
            thumbnail = pick_thumbnail(stats.get("snippet", {}).get("thumbnails", {}))
            is_short = is_short_video(duration, title, tags, thumbnail.get("width"), thumbnail.get("height"))
            if is_short != cfg["want_short"]:
                continue

            channel_id = stats.get("snippet", {}).get("channelId")
            if not channel_id:
                continue
            channel_stats = get_channel_stats(youtube, channel_id)
            subscriber_count = int(channel_stats.get("statistics", {}).get("subscriberCount", 0) or 0)

            seen_ids.add(video_id)
            duration_secs = _parse_duration_seconds(duration)
            candidates.append({
                "vid": video_id,
                "title": title,
                "channel": channel_title,
                "video_url": f"https://www.youtube.com/watch?v={video_id}",
                "niche_keyword": keyword,
                "views": view_count,
                "subscribers": subscriber_count,
                "published_at": stats.get("snippet", {}).get("publishedAt", "")[:10],
                "thumbnail_url": thumbnail.get("url", ""),
                "duration": _format_duration(duration_secs),
            })
            print(f"Candidate: '{title}' ({channel_title}) - {view_count:,} views")

    candidates.sort(key=lambda c: c["views"], reverse=True)
    return candidates[:MAX_CANDIDATES_TO_CLAUDE]


def prune_stale(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cutoff = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)
    kept = []
    for e in entries:
        date_str = e.get("published_at")
        if not date_str:
            kept.append(e)  # defensive: don't drop entries we can't verify
            continue
        try:
            published = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            kept.append(e)
            continue
        if published >= cutoff:
            kept.append(e)
        else:
            print(f"Pruning (stale, published {date_str}): {e['title'][:60]}")
    return kept


def curate_with_claude(candidates: List[Dict[str, Any]], label: str) -> List[Dict[str, Any]]:
    if not candidates:
        return []

    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("No ANTHROPIC_API_KEY found. Skipping curation, no new entries this run.")
        return []

    intro_text = f"""You are curating the "{label}" tab of a research dashboard for a YouTube channel in the \
cold-approach/dating advice niche (brand name "Sparked"). This tab collects viral video packaging \
(titles + thumbnails) from OUTSIDE the dating niche, each translated into a cold-approach-ready title \
and thumbnail concept, so the creator can use them as reference material for making their own thumbnails \
and titles.

Below are {len(candidates)} real YouTube video candidates, each shown as its actual thumbnail image \
followed by its data (all real, all >=500K views, all published in the last 90 days). Look at each \
thumbnail image directly -- do not guess its contents from the title alone. Select up to \
{MAX_NEW_ENTRIES_PER_RUN} of the BEST ones for this purpose. It is fine to select fewer than \
{MAX_NEW_ENTRIES_PER_RUN}, or zero, if the candidates aren't good -- do not force weak picks just to hit \
a number.

Selection criteria (be strict):
- STRONGLY prefer videos whose thumbnail ACTUALLY SHOWS real photographed people (real footage, real
  faces) -- judge this from the image itself, not the title. This dashboard exists so the creator can
  visually reference real thumbnail composition. REJECT thumbnails that are gaming footage, rendered
  3D/animation, illustrated "horror story" slideshow art, movie posters, or generic stock-photo collage
  text cards -- these have little value as a visual reference even if the title/hook is clever.
- AVOID dark, violent, politically charged, or tragedy-referencing content (no true crime about violent
  offenders, no references to real mass-casualty events, nothing that would read as tasteless next to a
  playful dating-advice brand).
- The packaging pattern (why the title/thumbnail works) must have a genuine, non-forced translation to
  flirting/dating/cold-approach content. Reject anything where the translation would feel like a stretch.
- Prefer variety -- do not pick several near-duplicate entries of the same exact pattern.

For each video you select, write a JSON object with EXACTLY these string fields (no others):
- "vid": the video ID from the candidate data (copy exactly)
- "niche": short label for the video's own niche/genre
- "pattern": what packaging pattern makes the thumbnail/title work (1-2 sentences)
- "trigger": the psychological trigger being pulled (1-2 sentences)
- "thumbnail": a literal description of what's actually in the thumbnail image you looked at
- "formula": the reusable title formula, using [Bracketed Placeholders] for the variable parts
- "why": why this formula/pattern works (1-2 sentences)
- "translation": how to reframe this pattern for cold-approach/dating content (1-2 sentences)
- "ca_title": a concrete example cold-approach title using the translated formula
- "ca_thumbnail": a concrete description of a cold-approach thumbnail using the translated pattern
- "notes": one extra insight, caveat, or reason this is worth testing

Respond with ONLY a JSON array of these objects (no markdown fences, no other text). If none of the \
candidates are good enough, respond with an empty JSON array: []

CANDIDATES (image followed by its data, in order):
"""

    content_blocks: List[Dict[str, Any]] = [{"type": "text", "text": intro_text}]
    headers = {"User-Agent": "Mozilla/5.0"}
    for c in candidates:
        thumb_b64 = None
        try:
            img_req = urllib.request.Request(c["thumbnail_url"], headers=headers)
            with urllib.request.urlopen(img_req, timeout=15) as img_resp:
                img_bytes = img_resp.read()
            thumb_b64 = base64.b64encode(img_bytes).decode("ascii")
        except Exception as e:
            print(f"Could not fetch thumbnail for {c['vid']}: {e}")

        if thumb_b64:
            content_blocks.append({
                "type": "image",
                "source": {"type": "base64", "media_type": "image/jpeg", "data": thumb_b64},
            })
        data_str = json.dumps({k: v for k, v in c.items() if k != "thumbnail_url"}, ensure_ascii=False)
        content_blocks.append({"type": "text", "text": data_str})

    body = json.dumps({
        "model": "claude-sonnet-5",
        "max_tokens": 8000,
        "messages": [{"role": "user", "content": content_blocks}],
    }).encode("utf-8")

    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "Content-Type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.load(resp)
    except Exception as e:
        print(f"Claude API call failed: {e}")
        return []

    text = "".join(block.get("text", "") for block in result.get("content", []) if block.get("type") == "text")
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)

    try:
        picked = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"Could not parse Claude's response as JSON: {e}\nRaw response:\n{text[:2000]}")
        return []

    candidates_by_vid = {c["vid"]: c for c in candidates}
    final_entries = []
    for p in picked:
        vid = p.get("vid")
        c = candidates_by_vid.get(vid)
        if not c:
            print(f"Claude returned an unknown vid, skipping: {vid}")
            continue
        if any(field not in p or not p[field] for field in REQUIRED_FIELDS):
            print(f"Claude's entry for {vid} is missing required fields, skipping.")
            continue

        entry = {
            "title": c["title"],
            "channel": c["channel"],
            "url": c["video_url"],
            "duration": c["duration"],
            "published_at": c["published_at"],
            "niche": p["niche"],
            "views": f"{c['views']:,} views in the last 90 days ({c['subscribers']:,} subscribers) -- "
                     f"a real, high-reach video used here as a proven thumbnail/title/retention example "
                     f"regardless of channel size.",
            "views_num": c["views"],
            "subscribers": c["subscribers"],
            "score": f"{c['views']:,} views",
            "pattern": p["pattern"],
            "trigger": p["trigger"],
            "thumbnail": p["thumbnail"],
            "formula": p["formula"],
            "why": p["why"],
            "translation": p["translation"],
            "ca_title": p["ca_title"],
            "ca_thumbnail": p["ca_thumbnail"],
            "notes": p["notes"],
            "status": "Not Adapted",
        }
        final_entries.append(entry)
        print(f"Curated: {c['title'][:60]}")

    return final_entries


def rewrite_swipe_file(module_path: str, entries: List[Dict[str, Any]]) -> None:
    with open(module_path, encoding="utf-8") as f:
        src = f.read()

    start_marker = "SWIPE_FILE = [\n"
    end_marker = "]\n\n\ndef _score_num"
    start_idx = src.index(start_marker) + len(start_marker)
    end_idx = src.index(end_marker)

    def jstr(s: str) -> str:
        return json.dumps(s, ensure_ascii=False)

    blocks = []
    for e in entries:
        b = "    {\n"
        for key, value in e.items():
            if isinstance(value, str):
                b += f"        {jstr(key)}: {jstr(value)},\n"
            else:
                b += f"        {jstr(key)}: {value},\n"
        b += "    },\n"
        blocks.append(b)

    new_src = src[:start_idx] + "".join(blocks) + src[end_idx:]
    with open(module_path, "w", encoding="utf-8") as f:
        f.write(new_src)


def main() -> None:
    parser = argparse.ArgumentParser(description="Weekly automated general-tab curation refresh.")
    parser.add_argument("--tab", required=True, choices=["long-form", "short-form"])
    args = parser.parse_args()

    _load_local_env()
    cfg = _tab_config(args.tab)

    import importlib.util
    spec = importlib.util.spec_from_file_location("target_module", cfg["module_path"])
    target_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(target_module)
    existing_entries = target_module.SWIPE_FILE

    existing_vids = {re.search(r"[?&]v=([\w-]{6,})", e["url"]).group(1) for e in existing_entries}
    print(f"Existing entries: {len(existing_entries)}")

    kept_entries = prune_stale(existing_entries)
    print(f"After pruning stale (>{LOOKBACK_DAYS}d old): {len(kept_entries)}")

    candidates = scan_candidates(cfg, existing_vids)
    print(f"Fresh candidates found (>= {MIN_VIEWS:,} views, not already in file): {len(candidates)}")

    new_entries = curate_with_claude(candidates, cfg["label"])
    print(f"New entries curated by Claude: {len(new_entries)}")

    final_entries = kept_entries + new_entries
    rewrite_swipe_file(cfg["module_path"], final_entries)
    print(f"Wrote {len(final_entries)} total entries to {cfg['module_path']}")

    subprocess.run([sys.executable, cfg["module_path"]], check=True)


if __name__ == "__main__":
    main()
