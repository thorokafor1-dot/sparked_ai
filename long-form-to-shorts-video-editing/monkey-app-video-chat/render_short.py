"""Renders one finished short: dynamically reframes the landscape split-screen
source into 9:16 (solo crop tracking whoever has a face on screen, stacked
when both do, full-frame fit when nobody does -- see reframe.py) and burns
in captions in the reference style, all in a single ffmpeg encode.

Usage:
    python render_short.py --video input/X.mp4 --start 12.0 --duration 30 \
        --transcript work/X_transcript.json --out output/short_1.mp4
"""
import argparse
import json
import math
import subprocess
from pathlib import Path

import cv2
import numpy as np

from captions import Word, write_ass_file
from reframe import PositionTrack, Sample, _get_detector, _looks_like_cutaway, detect_regions_over_time, smooth_positions, smooth_states

WORK_DIR = Path(__file__).parent / "work"
OUTPUT_DIR = Path(__file__).parent / "output"

# Shorts have no YouTube interactive end-screen elements (unlike long-form, which needs >= 5s to attach
# one) and the viewer's thumb is already hovering to swipe -- a branded card earns its keep only as a
# quick flash that registers, not a watch-time drag. The reference the user shared ran it for ~1.2s;
# matched here, same ballpark as general short-form practice (roughly 1-2s).
# The channel's own endscreen card, a clean frame lifted from one of the user's published shorts (the
# "1.00" speed badge from that screen recording slides out before this frame), so every short ends the
# same way. Timing copies that short too: cut in, ~0.8s slow push-in, ~0.45s fade to black.
# One high-quality encode for the whole short (the endscreen is joined by stream copy, never re-encoded
# on top). v69 was two veryfast/crf20 passes stacked and came out visibly pixelated at only ~3.7 Mbps.
# Both encodes must share these so the concat copy is valid.
VIDEO_ENC = ["-c:v", "libx264", "-preset", "slow", "-crf", "17", "-profile:v", "high", "-pix_fmt", "yuv420p",
             "-r", "30", "-video_track_timescale", "15360"]
ENDSCREEN_SECS = 1.25
ENDSCREEN_FADE = 0.45
ENDSCREEN_PNG = Path(__file__).parent / "assets" / "endscreen_card.png"
# YouTube Shorts end on the channel's subscribe card instead (prebuilt clip, see make_endscreen_card.py).
ENDSCREEN_YOUTUBE = Path(__file__).parent / "assets" / "endscreen_youtube.mp4"
ENDSCREEN_MAX_SECS = 2.4  # longest endscreen in use (YouTube); the face-on-screen gate exempts up to this

SOLO_W, SOLO_H = 1080, 1920
HALF_W, HALF_H = 1080, 960
DEFAULT_MAIN_FRAC, DEFAULT_HOST_FRAC = 0.36, 0.86  # last-resort fallback if a pane never had a single detection
# When falling back to the default (no trustworthy detection this moment), use a much narrower crop than usual.
# His pane has been seen as narrow as ~22% of the frame width (the far right sliver only) -- a full-width crop
# even centered on a reasonable-looking default position reached back into her side when his pane was that
# narrow. A tight fallback width closer to what that narrowest pane actually allows stays safely inside it
# regardless of how wide or narrow the pane happens to be right now.
DEFAULT_FALLBACK_CROP_W = 320
CROP_CHUNK = 1.5  # seconds between crop cuts. 0.5 (matching the detection sample_interval) tracked fast
# transitions well but cut every half-second -- 60 hard cuts across a 30s clip reads as jittery/jumpy, not like
# an edit. 1.5s is a real editor's minimum hold; smooth_positions() (not a bigger chunk) is what keeps a cut's
# position accurate to that moment instead of reintroducing the old "stale merged-span position" bug.

# A fixed close-up crop width (source pixels), used for every solo AND every
# stacked-half crop alike -- deliberately NOT derived from an estimated pane
# boundary. The app resizes the two panes over time (seen ranging from ~48/52
# up to ~72/28, and sometimes one person goes full-screen), so any crop width
# based on "the pane" kept either bleeding into the other person's side or
# landing on empty background whenever that estimate was stale or wrong. The
# two people are reliably much farther apart than this in every frame seen
# across this source, so a tight, fixed close-up centered on whichever face is
# tracked can never reach the other person, regardless of where the true
# boundary is right now.
FACE_CROP_W = 640

# The host pane has been seen as narrow as ~22% of the frame width, while
# the main pane has never been seen narrower than roughly her half of the
# frame -- so a solo host crop needs a tighter width than a solo main crop
# to stay reliably inside his pane, even when the tracked detection is
# perfectly genuine and fresh (a real detection can still sit close enough
# to a narrow pane's edge that a wide crop reaches past it).
HOST_CROP_W = 380

# Hard floor for the host crop's left edge -- a last resort for when the
# detected center itself is too close to the pane edge for width alone to
# fix (seen: a detection only ~15px from where his pane actually starts,
# so any crop centered on it pulls in mostly her side no matter how narrow).
# His pane has been seen roughly as wide as ~52% of the frame in a genuine
# split moment, so this floor is conservative rather than tight -- it won't
# catch every case, but it stops the crop from ever starting from deep in
# neutral/her territory the way an uncapped center did.
HOST_MIN_X_FRAC = 0.70

# Symmetric ceiling for the main crop's right edge -- her pane has been seen
# as narrow as ~48% of the frame width during a genuine split moment, so a
# main detection sitting close to that edge can otherwise pull a wide crop's
# right side into his territory the same way a host detection near his
# pane's edge pulled left into hers.
MAIN_MAX_X_FRAC = 0.55

# The stacked-half crops get a narrower width still. Even a "confidently
# tracked" position can sit close to the (unknown, shifting) pane boundary
# -- fine for a solo shot (worst case: slightly off-center, still one
# texture), but in a stacked half it can visibly mix both people's
# backgrounds in one frame. Less margin for error, so less width -- but
# 380 read as too tight/close-up on both faces at once (user feedback);
# widened to 460 for more breathing room now that adaptive chunking,
# denser sampling, and the min_separation checks make a stale/wrong
# position in a stacked half much less likely than when 380 was chosen.
SPLIT_FACE_CROP_W = 520
# When the real pane edge is measured (see _pane_edge_finder), the blind caps above aren't needed: a crop
# can widen right up to the edge without ever reaching the other person. The user found every shot "quite
# zoomed in" at the blind caps (stacked halves ~2.1x, his solo ~2.8x into the source). SPLIT_WIDE_W puts a
# stacked half at ~1.3x, close to how the call itself frames them.
SPLIT_WIDE_W = 820
PANE_EDGE_MARGIN = 12  # px kept clear of a measured pane edge

# The source app draws a yellow "Friend" button along the bottom of her pane (and a "Send Message" bar
# under his). A solo crop that keeps the full source height shows it as a platform-UI-looking
# smudge at the bottom edge, so solo crops drop this many source pixels off the bottom (a ~6% zoom).
SOLO_TRIM_BOTTOM = 70
# Where the face centre sits in a stacked half (fraction of the half's height from its top). Slightly
# above middle keeps eyes + forehead clear of the seam caption and leaves room for chin and hand.
SPLIT_FACE_Y_FRAC = 0.46

# Caption vertical position (ASS \pos y, measured from the top): lower-third
# for a solo shot, but pulled up to the seam between the two halves for a
# stacked two-person shot, so it never overlaps either face -- matches how
# the reference short repositions captions by layout, not a fixed spot.
# 1500 (not lower) keeps the caption's bottom edge above y=1536, clear of the
# title/caption overlay Shorts, TikTok and Reels draw over the bottom 20%
# (enforced by qa's caption-safe-zone gate).
SOLO_CAPTION_Y = 1500
SPLIT_CAPTION_Y = 1010


def _face_crop(
    face_x: float,
    target_w: int,
    target_h: int,
    frame_w: int,
    frame_h: int,
    crop_w: int = FACE_CROP_W,
    min_x_frac: float = 0.0,
    max_x_frac: float = 1.0,
    face_y: float | None = None,
) -> str:
    """Crops a fixed-width close-up centered on face_x (clamped to stay
    within the frame), then scales/crops to the exact target size. Not
    bounded to any pane -- see FACE_CROP_W. min_x_frac/max_x_frac hard-floor
    or hard-ceiling the crop's left/right edge (as a fraction of frame_w)
    regardless of face_x -- for a detection that's centered close enough to
    a narrow pane's edge that even a narrow width still reaches past it.
    Seen both ways: a host detection only ~15px from where his pane starts
    (min_x_frac), and symmetrically a main detection whose crop's right edge
    reached past where her pane ends when it's narrow (max_x_frac).

    Solo targets (full 9:16) keep the source height minus SOLO_TRIM_BOTTOM. Stacked halves are wider
    than tall, so a full-height sliver would centre-crop away whatever sits off the vertical middle
    (her eyes, when she leans into the camera): they take a window of the half's own aspect, placed
    on face_y (source pixels) when known."""
    crop_w = min(crop_w, frame_w)
    x = _crop_x(face_x, crop_w, frame_w, min_x_frac, max_x_frac)
    if target_h == SOLO_H:
        crop_h, y = frame_h - SOLO_TRIM_BOTTOM, 0
    else:
        crop_h = min(frame_h, round(crop_w * target_h / target_w))
        cy = face_y if face_y is not None else frame_h / 2
        y = int(max(0, min(round(cy - crop_h * SPLIT_FACE_Y_FRAC), frame_h - crop_h)))
    return (
        f"crop={crop_w}:{crop_h}:{x}:{y},"
        f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
        f"crop={target_w}:{target_h},setsar=1"
    )


def _crop_x(face_x: float, crop_w: int, frame_w: int, min_x_frac: float = 0.0, max_x_frac: float = 1.0) -> int:
    x = round(face_x - crop_w / 2)
    min_x = frame_w * min_x_frac
    max_x = frame_w * max_x_frac - crop_w
    x = int(max(min_x, max(0, min(x, min(max_x, frame_w - crop_w)))))
    return int(min(x, frame_w - crop_w))


def _none_crop() -> str:
    """No one detected -- show the full source frame, letterboxed, rather
    than guessing at a crop that could land on empty background."""
    return (
        f"scale={SOLO_W}:{SOLO_H}:force_original_aspect_ratio=decrease,"
        f"pad={SOLO_W}:{SOLO_H}:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
    )


def _state_at(samples: list[Sample], t: float) -> str:
    """Nearest sample's state, unsmoothed by segment merging -- crop type
    needs to follow the actual moment-to-moment reality (e.g. a zoom into
    full-screen happening over ~1s), not a multi-second majority vote that
    would wash out a fast transition like that into one wrong, frozen crop.
    A tiny epsilon on the comparison absorbs float drift in the sample
    timestamps themselves (each is built by repeatedly adding
    sample_interval, so by t=129.8 the actual stored value can be
    129.80000000000024, not exactly 129.8) -- confirmed directly: querying
    with the clean value 129.8 read that drifted sample's timestamp as
    "in the future" and silently fell back to the previous, stale sample
    one full interval earlier instead, changing "main" to "split" for a
    query that should have landed exactly on the newer sample."""
    if not samples:
        return "none"
    best = samples[0]
    for s in samples:
        if s.t > t + 1e-6:
            break
        best = s
    return best.state


NONE_EXIT_GRACE = 0.5  # seconds of held "none" past a detected cutaway's end (see _build_crop_plan)
SETTLE_SUBCHUNK = 0.15  # seconds -- the grace window itself is sub-chunked this fine (see _build_crop_plan)
SETTLE_FALLBACK_GAP = 2.5  # bounded fallback lookback for a "settle" chunk -- see _settle_layout
POSITION_SPREAD_THRESHOLD = 400  # px -- see _adaptive_chunks
MIN_ADAPTIVE_CHUNK = 0.3  # seconds -- floor on how far _adaptive_chunks will keep halving a chunk. Also gates
# whether a chunk gets checked for instability at all, not just how far recursion goes -- confirmed directly: a
# genuine ~660px main_x spread went unchecked in a 0.4s chunk when this was 0.5, because that chunk was already
# narrower than the floor (a leftover remainder from an earlier split elsewhere, not itself a result of recursing
# past the floor) and so skipped the spread check entirely rather than being deemed stable.


BOUNDARY_PAD = 0.2  # seconds -- see _position_spread's `pad` argument


def _position_spread(samples: list[Sample], start: float, end: float, state: str, pad: float = 0.0) -> float:
    """Max spread of the position attribute(s) relevant to `state` among
    raw samples falling within [start, end). A chunk gets one static crop
    for its whole span -- a large spread here means the source itself
    changed meaningfully partway through, which that single position
    can't represent. `pad` extends the window by this many seconds on each
    side, pulling in the nearest sample(s) just outside the chunk's own
    boundary -- confirmed directly: two adjacent chunks were each
    internally rock-stable (his position, then her position) with no
    spread inside either one, but the source flipped from one to the other
    right at the exact instant between them, so the crop used for the
    first chunk's own last fraction of a second was already wrong. Without
    `pad`, a chunk right up against a transition like that looks perfectly
    stable from the inside and never gets flagged."""
    attrs = ["host_x"] if state == "host" else ["main_x"] if state == "main" else ["main_x", "host_x"]
    spread = 0.0
    for attr in attrs:
        vals = [
            getattr(s, attr) for s in samples if start - pad <= s.t < end + pad and getattr(s, attr) is not None
        ]
        if len(vals) >= 2:
            spread = max(spread, max(vals) - min(vals))
    return spread


def _state_changes_within(samples: list[Sample], start: float, end: float, pad: float = BOUNDARY_PAD) -> bool:
    """True if the raw (smoothed) per-sample state isn't the same value
    throughout [start-pad, end+pad) -- used for "none" chunks, which have
    no position to check a spread on. Confirmed directly: a "none" chunk's
    own 1.5s span can span the real end of a cutaway partway through --
    the chunk still commits to one static "none" (raw, uncropped) render
    for its whole duration, so real footage that resumes mid-chunk was
    shown unmodified instead of transitioning to settle/main, letting the
    other person's pane bleed in at the frame edge exactly like the
    horizontal layout this pipeline otherwise goes out of its way to
    avoid."""
    states = {s.state for s in samples if start - pad <= s.t < end + pad}
    return len(states) > 1


def _adaptive_chunks(
    samples: list[Sample],
    start: float,
    end: float,
    opening_end: float,
    min_chunk: float = MIN_ADAPTIVE_CHUNK,
    pad: float = BOUNDARY_PAD,
) -> list[tuple[float, float, str]]:
    """Recursively halves a chunk whose own tracked position drifts more
    than POSITION_SPREAD_THRESHOLD within its own span -- confirmed
    directly against the source: a "main" chunk's position, taken from
    early in its 1.5s span, no longer matched what was actually on screen
    by the chunk's own later half, because the source flipped from a
    full-screen shot of one person to a full-screen shot of the other
    within that single static-crop chunk. Also halves a "none" chunk that
    spans a genuine state change (see _state_changes_within) -- a "none"
    chunk has no position to check a spread on, but can be just as
    internally inconsistent as a "main" one. Recursion stops at min_chunk
    (finer than that starts reading as jumpy cuts rather than tracking) or
    once a half is stable, so this only adds cuts where the source is
    actually this volatile -- the rest of the clip keeps the normal
    CROP_CHUNK cadence.

    `pad` halves on every recursive call rather than staying fixed --
    confirmed directly against the source: a real transition (say, her
    position jumping to his) got correctly isolated into its own tiny
    sub-chunk one level down, but with a constant pad every deeper
    recursive call could still "see" that same distant sample near its own
    edge and kept re-splitting, cutting one continuous, slowly-panning
    shot into 3-4 needless hard cuts that read as a flickering, jump-cut
    mess instead of a held shot -- the actual positions in each piece
    (909, 894, 871, 855) were barely different, just noise from a slow
    pan, not a real scene change. A shrinking pad still catches a genuine
    transition right at a boundary (that's what needed multiple levels to
    isolate in the first place) without letting it keep contaminating
    sub-chunks once they're already well clear of it."""
    mid = (start + end) / 2
    state = "main" if mid < opening_end else _state_at(samples, mid)
    if (end - start) > min_chunk:
        # A real layout change (split -> her full-screen close-up) can move the tracked x by less than
        # the spread threshold (short_3: 380px), so the chunk kept "split" over the close-up. A smoothed
        # state change is already blip-filtered, so it is a real transition worth isolating too. Call
        # layouts only: meme ("none") edges have their own frame-accurate refiner, and halving there
        # dragged the meme span 0.4s into the call footage (v7).
        layouts = {s.state for s in samples if start - pad <= s.t < end + pad} - {"none"}
        unstable = (
            _position_spread(samples, start, end, state, pad=pad) > POSITION_SPREAD_THRESHOLD
            or len(layouts) > 1
            if state in ("main", "host", "split")
            else _state_changes_within(samples, start, end, pad=pad)
            if state == "none"
            else False
        )
        if unstable:
            half = (start + end) / 2
            return _adaptive_chunks(samples, start, half, opening_end, min_chunk, pad / 2) + _adaptive_chunks(
                samples, half, end, opening_end, min_chunk, pad / 2
            )
    return [(start, end, state)]


MERGE_POSITION_THRESHOLD = 150  # px -- see _merge_similar_chunks


def _near_position(samples: list[Sample], mid: float, attr: str, max_gap: float = 0.75) -> float | None:
    """Standalone nearest-sample lookup, same idea as PositionTrack.near()
    but usable here without constructing a full PositionTrack (this runs
    before frame_w is known)."""
    best_x, best_dist = None, None
    for s in samples:
        x = getattr(s, attr)
        if x is None:
            continue
        d = abs(s.t - mid)
        if best_dist is None or d < best_dist:
            best_dist, best_x = d, x
    if best_dist is not None and best_dist <= max_gap:
        return best_x
    return None


def _merge_similar_chunks(
    samples: list[Sample], plan: list[tuple[float, float, str]]
) -> list[tuple[float, float, str]]:
    """Merges adjacent same-state chunks whose own resolved position is
    nearly identical -- confirmed directly: _adaptive_chunks' recursive
    halving can correctly isolate a genuine instability into its own
    sub-chunk, but the chunks on either side of that split are never
    compared against each other or their other neighbors -- two chunks
    landing on the literal same position (both measured at 246px) stayed
    separate, producing a hard cut with no visible reason, since nothing
    about the frame actually changed across it. That reads as a stray,
    glitchy jump cut, not a real scene change. Only merges when the
    resolved positions are this close (not just "under the instability
    threshold" loosely) -- an earlier version of this pipeline merged
    same-state spans unconditionally and that produced actively wrong
    crops for spans that turned out not to be uniform after all (see
    _build_crop_plan's docstring); this only merges pairs already
    confirmed near-identical, so the merged span's own midpoint lookup
    lands on essentially the same value either half would have used.

    Checking only the two chunks' own midpoints isn't quite enough on its
    own, though -- confirmed directly: two adjacent "split" chunks each
    passed the midpoint check, but a real transition (her position, then
    his) landed in the gap between the two midpoints, inside neither
    chunk's own sampled point, so nothing caught it. _position_spread
    over the full proposed merged span (not just its two endpoints) is
    the same check _adaptive_chunks already trusts to find instability
    -- reusing it here means a merge can't hide a transition that a fresh
    split of the same span would have caught."""
    if not plan:
        return plan
    merged = [plan[0]]
    for start, end, state in plan[1:]:
        p_start, p_end, p_state = merged[-1]
        if state == p_state and state in ("main", "host", "split"):
            attrs = ["main_x", "host_x"] if state == "split" else ["host_x" if state == "host" else "main_x"]
            prev_mid = (p_start + p_end) / 2
            cur_mid = (start + end) / 2
            close = all(
                (pv := _near_position(samples, prev_mid, a)) is not None
                and (cv := _near_position(samples, cur_mid, a)) is not None
                and abs(pv - cv) <= MERGE_POSITION_THRESHOLD
                for a in attrs
            )
            if close and _position_spread(samples, p_start, end, state) <= MERGE_POSITION_THRESHOLD:
                merged[-1] = (p_start, end, state)
                continue
        merged.append((start, end, state))
    return merged


def _settle_layout(
    mid: float, main_track: PositionTrack, host_track: PositionTrack
) -> tuple[str, float | None, float | None]:
    """Decides how a "settle" chunk actually renders: a genuine stack, or
    solo main/host -- based on which side(s) have a position within a
    bounded lookback, never an unconditional held value. PositionTrack.at()
    never returns None, holding a position however old -- confirmed
    directly: a ~7s-old held host_x, from the last time he was seen many
    seconds before a cutaway, landed on an unrelated part of the room, not
    his face, when used as a settle-window fallback. That's no more
    trustworthy than a blind default guess, just differently wrong. A
    bounded near() only trusts a position that's still plausibly recent; if
    neither side has one, there's no real second person to invent a stacked
    half for. Shared by _build_filter_complex (to render) and render()'s
    y_at (to position the caption to match), so the two stay in sync."""
    main_res = main_track.near(mid, max_gap=0.75) or main_track.near(mid, max_gap=SETTLE_FALLBACK_GAP)
    host_res = host_track.near(mid, max_gap=0.75) or host_track.near(mid, max_gap=SETTLE_FALLBACK_GAP)
    main_x = main_res[0] if main_res is not None else None
    host_x = host_res[0] if host_res is not None else None
    # Both sides having *a* position isn't enough -- confirmed directly:
    # main_x and host_x each came from a real, fresh detection, but from two
    # different moments a fraction of a second apart (his own full-screen
    # solo position, then his position once the real split started) rather
    # than two different people at the same instant. Reused from the
    # existing "split" state's own defense below (same threshold, same
    # reasoning) instead of trusting "both found" alone.
    min_separation = 700
    if main_x is not None and host_x is not None and abs(main_x - host_x) < min_separation:
        host_x = None
    if main_x is not None and host_x is not None:
        return "split", main_x, host_x
    if host_x is not None:
        return "host", None, host_x
    return "main", main_x, None


def _build_crop_plan(
    samples: list[Sample],
    clip_start: float,
    clip_end: float,
    opening_end: float,
    chunk: float = CROP_CHUNK,
    none_grace: float = NONE_EXIT_GRACE,
) -> list[tuple[float, float, str]]:
    """Sub-chunks the whole clip at `chunk`-second intervals and looks up
    each chunk's own state directly, so the crop tracks fast transitions
    instead of freezing on whatever a coarser segment decided seconds of
    footage away. Deliberately NOT merged: an earlier version merged
    adjacent same-state chunks to shrink the filter graph, but
    _build_filter_complex then computed one crop position from the merged
    span's midpoint -- e.g. a 7s "main" block used the position at its
    midpoint for the whole 7s, which could be seconds away (and a
    meaningfully different framing) from where any given moment in that
    span actually was. Every chunk gets looked up and cropped on its own."""
    raw_plan = []
    t = clip_start
    while t < clip_end:
        end = min(t + chunk, clip_end)
        raw_plan.extend(_adaptive_chunks(samples, t, end, opening_end))
        t = end
    raw_plan = _merge_similar_chunks(samples, raw_plan)

    # A cutaway's tail can bleed a fraction of a second past where
    # detection says it ends -- confirmed directly against the source: a
    # genuine 3-frame (0.1s) flash of the wrong person right at a
    # none -> main boundary, from the source itself briefly still showing
    # the cutaway-adjacent layout before settling into whatever the next
    # chunk's crop position was computed from. Sampling finely enough to
    # catch a sub-0.5s flicker directly isn't worth the cost, so a short
    # held grace period after a genuine "none" chunk absorbs that
    # instability instead of risking it landing in a solo crop. Labeled
    # "settle", not "none": the letterboxed full-frame "none" treatment
    # shows the source completely unmodified, which is fine for an actual
    # cutaway (unrelated B-roll) but not here -- the source's own call
    # layout is natively horizontal (side by side), and the grace window is
    # exactly where the real call can already be back on screen, genuinely
    # two-up, before the next chunk's position data has caught up. Showing
    # that raw would put a horizontal her-and-him frame on screen, which
    # the short-form format explicitly should never do. _build_filter_complex
    # renders "settle" as a vertical stack instead (like "split", but never
    # downgraded to solo -- this window is specifically where position data
    # is least trustworthy, so it always uses best-effort/default positions
    # rather than risk a confident-looking wrong solo crop). Only the
    # leading sliver is sacrificed, not the whole next chunk -- losing
    # NONE_EXIT_GRACE seconds to a safe stacked view beats either a jarring
    # wrong-person flash or discarding a full correctly-cropped chunk.
    plan = []
    last_none_end = None
    for start, end, state in raw_plan:
        if state == "none":
            last_none_end = end
            plan.append((start, end, state))
            continue
        grace_end = last_none_end + none_grace if last_none_end is not None else None
        if grace_end is not None and start < grace_end:
            split = min(grace_end, end)
            if split > start:
                # The grace window itself gets sub-chunked, not treated as
                # one static crop -- confirmed directly: even within a
                # single 0.5s settle window, the source shifted enough that
                # one static settle crop tracked a real person for a
                # fraction of a second and framed empty background for the
                # rest. Each sub-chunk gets its own _settle_layout lookup.
                # Split into an even number of equal-sized pieces (not
                # fixed-size steps that leave a remainder) -- confirmed
                # directly: a fixed SETTLE_SUBCHUNK step left a ~0.05s
                # (1-2 frame) sliver at the end of the window, short enough
                # that its own crop lookup could easily land on a different
                # position than its neighbors purely from being such an
                # oddly-timed slice -- reading as exactly the kind of
                # single stray off frame sandwiched between two real
                # shots that a viewer would notice.
                plan.append((start, split, "settle"))
            if split < end:
                plan.append((split, end, state))
        else:
            plan.append((start, end, state))
    return plan


MIN_SHOT = 0.7      # seconds -- a non-cutaway shot shorter than this reads as a flash, not an edit
CUT_JUMP = 320      # px -- adjacent same-person shots whose tracked positions differ less than this are ONE shot
PAN_STEP = 0.4      # seconds between pan keypoints inside a solo shot


def _shot_pos(state: str, t: float, main_track: PositionTrack, host_track: PositionTrack) -> float | None:
    """The tracked x that identifies who a shot is on (split uses the bottom/main half)."""
    res = (host_track if state == "host" else main_track).near(t, 0.75)
    return res[0] if res is not None else None


def _boundary_jump(a: tuple, b: tuple, main_track: PositionTrack, host_track: PositionTrack) -> float | None:
    """Position change across the cut between adjacent chunks a and b (None if either side is untracked)."""
    # probe just inside each chunk; never past its far edge (a 0.05s sliver must not read the next shot)
    pa = _shot_pos(a[2], a[1] - min(0.1, (a[1] - a[0]) / 2), main_track, host_track)
    pb = _shot_pos(b[2], b[0] + min(0.1, (b[1] - b[0]) / 2), main_track, host_track)
    return None if pa is None or pb is None else abs(pa - pb)


def _cutaway_edge_refiner(video_path: str):
    """Returns fn(boundary, entering_cutaway) -> the time (within +-0.8s) where the source really flips
    between the call and the cutaway, found frame by frame with the same _looks_like_cutaway test the
    detector uses. The detector's smoothed state can be several tenths of a second off, and the gap
    shows up as either a flash of zoomed meme or a sliver of call footage inside the meme letterbox."""
    def refine(boundary: float, entering: bool) -> float:
        cap = cv2.VideoCapture(video_path)
        # On the true 30fps grid (as _refine_pan_snap): an unaligned grid returned a boundary exactly half a
        # frame off a real frame, which trim then resolved the wrong way, leaving one zoomed meme frame at
        # the start of the next solo shot (confirmed: v67 at 0:08).
        f0 = round(boundary * 30)
        times = [(f0 + k) / 30 for k in range(-24, 25)]
        flags = []
        for t in times:
            cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
            ok, frame = cap.read()
            flags.append(_looks_like_cutaway(frame) if ok else None)
        cap.release()
        if any(f is None for f in flags):
            return boundary
        # best split index k: frames before k are on one side, frames from k on are on the other
        before, after = (False, True) if entering else (True, False)
        best_k = max(range(len(times) + 1), key=lambda k: sum(f == before for f in flags[:k]) + sum(f == after for f in flags[k:]))
        return times[best_k] if best_k < len(times) else boundary
    return refine


def _split_at_jumps(plan, main_track: PositionTrack, host_track: PositionTrack):
    """Cuts a solo/split shot where the tracked person genuinely changes (her -> him). Without this, the
    smooth pan would sweep across the empty wall between them instead of cutting. The cut goes exactly
    midway between the two detection samples that disagree, which is where a nearest-sample lookup
    flips, so the shot on each side reads a consistent position."""
    out = []
    for s, e, st in plan:
        if st not in ("main", "host", "split") or e - s < 0.3:
            out.append((s, e, st))
            continue
        raw = [(t, x) for t, x, _ in (host_track if st == "host" else main_track)._raw if x is not None]
        cut_at = [
            (raw[i - 1][0] + raw[i][0]) / 2
            for i in range(1, len(raw))
            if abs(raw[i][1] - raw[i - 1][1]) > CUT_JUMP and s < (raw[i - 1][0] + raw[i][0]) / 2 < e
        ]
        prev = s
        for c in cut_at:
            out.append((prev, c, st))
            prev = c
        out.append((prev, e, st))
    return out


def _simplify_plan(
    plan: list[tuple[float, float, str]],
    main_track: PositionTrack,
    host_track: PositionTrack,
    refine_edge=None,
) -> list[tuple[float, float, str]]:
    """Removes cuts a viewer would read as jumpy rather than as an edit.

    Every cut between two chunks of the same person is a hard jump in framing, so
    adjacent same-state chunks are one shot unless the position really jumps
    (CUT_JUMP: her -> him). Inside a shot the crop pans smoothly instead (see
    _solo_pan_crop), so tracking is kept without the cuts. Settle windows are
    resolved to the layout they will actually render as first, so they merge with
    the shot around them instead of being their own flash. Non-cutaway chunks shorter
    than MIN_SHOT (e.g. a 0.2s stacked-split blip between two solo shots) are absorbed
    into the neighbour they are closest to, when that neighbour is the same person."""
    plan = [
        (s, e, _settle_layout((s + e) / 2, main_track, host_track)[0] if st == "settle" else st)
        for s, e, st in plan
    ]
    if refine_edge is not None:
        i = 0
        while i < len(plan) - 1:
            (s1, e1, st1), (s2, e2, st2) = plan[i], plan[i + 1]
            if (st1 == "none") != (st2 == "none"):
                nb = refine_edge(e1, entering=(st2 == "none"))
                if s1 + 0.05 < nb < e2 - 0.05:
                    plan[i], plan[i + 1] = (s1, nb, st1), (nb, e2, st2)
                elif st1 == "none" and nb >= e2 - 0.05 and i + 2 < len(plan) and nb < plan[i + 2][1] - 0.05:
                    # The meme really runs past the whole short chunk after it (the 0.5s "settle" grace):
                    # short_5_v3 kept 0.5-0.7s of meme letterbox/torso as call crops at 0:07.5 and 0:37.5
                    # because an edge landing at/after that chunk's end was rejected. Swallow it instead.
                    plan[i] = (s1, nb, st1)
                    plan[i + 2] = (nb, plan[i + 2][1], plan[i + 2][2])
                    del plan[i + 1]
            i += 1
    plan = _split_at_jumps(plan, main_track, host_track)
    changed = True
    while changed:
        changed = False
        out = [plan[0]]
        for c in plan[1:]:
            p = out[-1]
            same = p[2] == c[2] and (
                c[2] == "none" or ((j := _boundary_jump(p, c, main_track, host_track)) is not None and j <= CUT_JUMP)
            )
            if same:
                out[-1] = (p[0], c[1], p[2])
                changed = True
            else:
                out.append(c)
        plan = out
        for i, c in enumerate(plan):
            if c[2] == "none" or c[1] - c[0] >= MIN_SHOT:
                continue
            options = []
            for k in (i - 1, i + 1):
                if 0 <= k < len(plan) and plan[k][2] != "none":
                    j = _boundary_jump(plan[k], c, main_track, host_track) if k < i else _boundary_jump(c, plan[k], main_track, host_track)
                    if j is not None and j <= CUT_JUMP:
                        options.append((j, k))
            if options:
                _, k = min(options)
                plan[i] = (c[0], c[1], plan[k][2])
                changed = True
                break
    return [c for c in plan if c[1] - c[0] > 0.02]


def _pan_expr(
    times: list[float], xs: list[int], force_snap: list[bool] | None = None, snap_times: list[float | None] | None = None
) -> str:
    """Piecewise-linear x(t) through the keypoints (t is seconds from the chunk start). force_snap[i],
    when given, overrides whether the segment from keypoint i to i+1 snaps instead of interpolating --
    needed because clamping (a crop pinned against a frame edge) can shrink an underlying jump between
    two genuinely different positions down under CUT_JUMP even though the real, pre-clamp difference
    was well over it, letting a real person-swap read as one continuous sweep. Confirmed directly: a
    ~550->~230 raw jump (clearly two different framings) clamped to a post-crop delta of just 292, well
    under CUT_JUMP, and interpolated smoothly across the room instead of snapping.

    snap_times[i], when given (not None), overrides WHERE a snapping segment actually snaps -- the naive
    midpoint between two sparse (0.4s-apart) keypoints can land a few frames before the source's real cut,
    showing a sliver of whatever the new crop position actually points at while the old content is still
    playing there (confirmed directly: a glimpse of the source app's own UI chrome for a couple of frames).
    See _refine_pan_snap."""
    expr = str(xs[-1])
    for i in range(len(xs) - 2, -1, -1):
        snap = force_snap[i] if force_snap is not None else abs(xs[i + 1] - xs[i]) > CUT_JUMP
        if snap:
            # a real person switch inside the keypoints: snap at the midpoint, never sweep across the room
            snap_t = snap_times[i] if snap_times is not None and snap_times[i] is not None else (times[i] + times[i + 1]) / 2
            seg = f"if(lt(t,{snap_t:.3f}),{xs[i]},{xs[i + 1]})"
        elif xs[i] == xs[i + 1]:
            seg = str(xs[i])
        else:
            seg = f"{xs[i]}+({xs[i + 1] - xs[i]})*(t-{times[i]:.3f})/{times[i + 1] - times[i]:.3f}"
        expr = f"if(lt(t,{times[i + 1]:.3f}),{seg},{expr})"
    return expr


def _raw_attr_lookup(raw_samples, attr: str, t: float, max_gap: float, bounds: tuple[float, float] | None = None):
    """Nearest genuinely-detected (x, full_screen) for attr ("main_x"/"host_x") within max_gap of t,
    straight from the RAW (pre-smoothing) samples -- never from a PositionTrack, whose own ._raw is
    built from smooth_positions's output and is NOT raw in that sense: it bleeds a real detection's
    value forward for up to its +/-7-sample averaging window (~1.4s) into what were genuinely None gaps
    in the original data, and (via its own-value-anchored-average) can also drift an otherwise-stable
    run toward a DIFFERENT person's position up to 300px away, if that's where the SAME track's very
    next real detection happens to be -- confirmed directly: a full-screen solo shot's tracked x drifted
    ~150px over its own 1.5s duration toward the next shot's different person, dragging the crop
    steadily off his face although he never actually moved that whole time. Used for BOTH the shot's own
    position (bypassing that drift) and checking the OTHER track for real adjacent content (bypassing a
    stale detection read as still-current). bounds, when given, excludes samples outside [lo, hi] --
    used for a chunk's OWN track, so its last keypoint (right at c_end) can't grab the very next chunk's
    identity just because that raw sample happens to land a fraction of a second closer than this
    chunk's own last real detection -- confirmed directly: it produced a sudden last-instant sweep
    toward the wrong person's position before the actual cut."""
    best = None
    for s in raw_samples:
        v = getattr(s, attr)
        if v is None:
            continue
        if bounds is not None and not (bounds[0] <= s.t < bounds[1]):
            continue
        d = abs(s.t - t)
        if d <= max_gap and (best is None or d < best[0]):
            best = (d, v, s.full_screen)
    return (best[1], best[2]) if best else None


def _refine_pan_snap(video_path: str, t0: float, t1: float) -> float:
    """Frame-accurate replacement for the naive (t0+t1)/2 snap point: scans every source frame in
    [t0, t1] (a single ~0.4s PAN_STEP gap) for the one with the biggest jump from its predecessor --
    the real cut -- and snaps there instead. Falls back to the midpoint if the frames can't be read.

    Seek times are snapped to the TRUE 30fps frame grid (multiples of 1/30 from t=0), not an arbitrary
    grid starting at t0 and stepping by 1/30 -- confirmed directly: starting from an unaligned t0 can
    step clean over the one real-cut frame entirely (every sampled time lands between two real frames,
    a fraction of a frame to either side of the actual cut), silently missing a 58-point spike and
    picking some much smaller nearby wobble instead."""
    cap = cv2.VideoCapture(video_path)
    fps = 30
    # One frame of padding on each side: a cut landing exactly at i0 (or i1) needs the frame just
    # before (or after) it in the comparison too, or that one real transition -- the biggest diff in
    # the whole window -- never gets compared against anything and silently drops out of consideration.
    i0, i1 = int(round(t0 * fps)) - 1, int(round(t1 * fps)) + 1
    times = [k / fps for k in range(i0, i1 + 1)]
    grays = []
    for t in times:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        grays.append(cv2.cvtColor(cv2.resize(frame, (108, 192)), cv2.COLOR_BGR2GRAY).astype(np.float32) if ok else None)
    cap.release()
    diffs = [
        (i, float(np.mean(np.abs(grays[i] - grays[i - 1]))))
        for i in range(1, len(grays)) if grays[i] is not None and grays[i - 1] is not None
    ]
    if not diffs:
        return (t0 + t1) / 2
    best_i = max(diffs, key=lambda p: p[1])[0]
    return times[best_i]


def _solo_pan_crop(
    role: str, c_start: float, c_end: float, main_track: PositionTrack, host_track: PositionTrack,
    frame_w: int, frame_h: int, raw_samples, video_path: str, opening_end: float | None = None,
    pane_edge_at=None,
) -> str | None:
    """Solo (main/host) crop whose x follows the tracked face smoothly across the chunk instead of
    sitting at one midpoint value, so a long shot never needs a cut just to re-centre. None when nothing
    was detected anywhere in the span (caller falls back to the static default crop).

    A version of this once special-cased the opening hook to a single static crop, reasoning that
    _build_crop_plan forces it to render as "main" regardless of what was actually detected, so a
    per-keypoint pan could follow the source into a real transition the hook is supposed to play through.
    Reverted: a static reference taken early in the hook stopped covering her real position once the
    source cut to a genuine two-pane split a second later -- confirmed directly, a 0.4-0.5s no-face gap
    that dynamic per-keypoint tracking never had. Dynamic tracking is right; the resulting extra cut is
    handled at the source instead, by marking it a known seam (see _hook_seam_span), not by breaking face
    tracking to avoid it."""
    attr = "main_x" if role == "main" else "host_x"
    other_attr = "host_x" if role == "main" else "main_x"
    crop_w = min(FACE_CROP_W if role == "main" else HOST_CROP_W, frame_w)
    n = max(1, math.ceil((c_end - c_start) / PAN_STEP))
    times = [c_start + (c_end - c_start) * i / n for i in range(n + 1)]
    pts = []  # (x, full_screen) or None
    for t in times:
        t = min(max(t, c_start + 0.02), c_end - 0.02)  # a keypoint sitting exactly on a shot edge can read the neighbour's sample
        res = _raw_attr_lookup(raw_samples, attr, t, 0.75, bounds=(c_start, c_end))
        if res is None:
            pts.append(None)
            continue
        ref = _raw_attr_lookup(raw_samples, other_attr, t, 2.5)
        if ref is not None and abs(res[0] - ref[0]) < 400:  # same false-positive guard the static path uses
            pts.append(None)
            continue
        pts.append(res)
    if all(p is None for p in pts):
        return None
    for i, p in enumerate(pts):  # hold the nearest real reading through gaps
        if p is None:
            pts[i] = next((pts[k] for k in range(i - 1, -1, -1) if pts[k] is not None), None) or                 next(q for q in pts[i + 1:] if q is not None)
    # Snap decisions use the RAW (pre-clamp) face position, not the clamped crop x -- see _pan_expr.
    force_snap = [abs(pts[i + 1][0] - pts[i][0]) > CUT_JUMP for i in range(len(pts) - 1)]
    snap_abs = [_refine_pan_snap(video_path, times[i], times[i + 1]) if force_snap[i] else None for i in range(len(pts) - 1)]
    snap_times = [None if a is None else a - c_start for a in snap_abs]
    # Pane-edge clamp: only when the OTHER person is really on screen in this same continuous stretch,
    # i.e. bounded to this chunk AND to the stretch between the pan's own snaps. Bounded to the chunk
    # only, the tail of a real split that ended at a snap inside the chunk still read as "adjacent
    # content right now" for up to 0.75s past it, clamping the new full-screen shot off-centre and then
    # releasing it into a visible pan to centre although he never moved. Confirmed directly: the
    # opening hook cut to him full-screen at a stable x~931 and still panned 416->611 over ~0.8s.
    edges = [c_start] + [a for a in snap_abs if a is not None] + [c_end]
    for i, t in enumerate(times):
        t = min(max(t, c_start + 0.02), c_end - 0.02)
        lo = max(e for e in edges[:-1] if e <= t) if any(e <= t for e in edges[:-1]) else c_start
        hi = min(e for e in edges[1:] if e > t) if any(e > t for e in edges[1:]) else c_end
        if _raw_attr_lookup(raw_samples, other_attr, t, 0.75, bounds=(lo, hi)) is not None:
            pts[i] = (pts[i][0], False)
    # A measured pane edge replaces the blind clamps: the crop can then use the full solo width right up
    # to the edge (HOST_CROP_W's narrow width only exists for when the edge is unknown).
    edges = [pane_edge_at(min(max(t, c_start + 0.02), c_end - 0.02)) if pane_edge_at and not fs else None
             for t, (_, fs) in zip(times, pts)]
    if role == "host" and all(fs or e is not None for (_, fs), e in zip(pts, edges)):
        crop_w = min(FACE_CROP_W, frame_w)
    xs = []
    for (x, fs), e in zip(pts, edges):
        if role == "main":
            hi = 1.0 if fs else (e - PANE_EDGE_MARGIN) / frame_w if e is not None else MAIN_MAX_X_FRAC
            xs.append(_crop_x(x, crop_w, frame_w, 0.0, hi))
        else:
            lo = 0.0 if fs else (e + PANE_EDGE_MARGIN) / frame_w if e is not None else HOST_MIN_X_FRAC
            xs.append(_crop_x(x, crop_w, frame_w, lo, 1.0))
    x_expr = (
        str(xs[0]) if len(set(xs)) == 1
        else "'" + _pan_expr([t - c_start for t in times], xs, force_snap, snap_times) + "'"
    )
    return (
        f"crop={crop_w}:{frame_h - SOLO_TRIM_BOTTOM}:{x_expr}:0,"
        f"scale={SOLO_W}:{SOLO_H}:force_original_aspect_ratio=increase,"
        f"crop={SOLO_W}:{SOLO_H},setsar=1"
    )


def _pane_edge_finder(video_path: str):
    """Returns fn(t) -> x of the vertical seam between the two call panes at source time t, or None when
    there isn't one (full-screen shot). The seam is a perfectly straight full-height line, so it shows up as
    the one column where a strong horizontal step exists on most rows (measured on this source: 82-95% of
    rows at the seam vs under 30% anywhere else)."""
    cap = cv2.VideoCapture(video_path)
    cache: dict = {}

    def find(t: float):
        key = round(t * 30)
        if key in cache:
            return cache[key]
        cap.set(cv2.CAP_PROP_POS_MSEC, key / 30 * 1000)
        ok, frame = cap.read()
        x = None
        if ok:
            g = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY).astype(np.float32)
            strong = (np.abs(np.diff(g, axis=1)) > 12).mean(axis=0)
            w = g.shape[1]
            lo, hi = int(w * 0.3), int(w * 0.85)
            i = lo + int(np.argmax(strong[lo:hi]))
            if strong[i] >= 0.6:
                x = i + 1
        cache[key] = x
        return x
    return find


def _face_y_finder(video_path: str):
    """Returns fn(c_start, c_end, face_x) -> median face-centre y (source pixels) of the face near
    face_x over the chunk, or None. Tracks only carry x; a stacked half needs y so the face lands in
    frame instead of on a centre-cropped guess."""
    cap = cv2.VideoCapture(video_path)
    detector = _get_detector()
    cache: dict = {}

    def find(c_start: float, c_end: float, face_x: float):
        key = (round(c_start, 2), round(c_end, 2), round(face_x))
        if key in cache:
            return cache[key]
        ys = []
        for k in range(5):
            cap.set(cv2.CAP_PROP_POS_MSEC, (c_start + (c_end - c_start) * (k + 0.5) / 5) * 1000)
            ok, frame = cap.read()
            if not ok:
                continue
            h, w = frame.shape[:2]
            detector.setInputSize((w, h))
            _, faces = detector.detect(frame)
            near = [f for f in (faces if faces is not None else []) if abs(f[0] + f[2] / 2 - face_x) < 260]
            if near:
                f = max(near, key=lambda f: f[2] * f[3])
                ys.append(float(f[1] + f[3] / 2))
        cache[key] = sorted(ys)[len(ys) // 2] if ys else None
        return cache[key]

    return find


FLIP_JUMP = 150  # px; smaller than CUT_JUMP -- see _expand_flip_flops

# How much x-distance apart two solo full-screen detections need to be, inside one nominal main/host
# chunk, before it's treated as a genuine person-swap (see _expand_flip_flops) rather than the same
# person shifting position. Smaller than CUT_JUMP: CUT_JUMP was tuned for one person's own face moving
# within a pane, but two different people's *enlarged, near-full-screen* faces can land only 150-300px
# apart in x (both centred-ish in frame) -- confirmed directly against the source (a clean identity swap
# at exactly one sample boundary, no gradual motion either side of it).


def _recover_hidden_splits(plan, raw_samples, opening_end: float, video_path: str):
    """smooth_states majority-votes state over a +/-1s window, so a real, brief two-person "split"
    moment sandwiched between two solo shots can get outvoted by its neighbours and relabelled
    "main"/"host" -- confirmed directly: raw detections show a clean ~0.9s window with BOTH a real
    main_x and host_x (non-full-screen -- an actual two-pane frame, not an enlarged single face) sitting
    inside what the simplified plan calls one flat "main" chunk. Carve it back out here using its own
    real positions -- no identity guessing needed, both people are already correctly assigned -- so
    _expand_flip_flops's later cross-chunk pass sees the genuine split it borders instead of two solo
    chunks with nothing recognisable between them."""
    # Two consecutive chunks the earlier chunking pass split apart at an arbitrary boundary, but which
    # carry the SAME state, are really one continuous span -- scanning them separately made the window
    # search blind to a real split sample sitting just past the artificial boundary, leaving a ~0.2s gap
    # with no detection on either side that a stale static crop then rendered as empty background
    # (confirmed directly: the flash was exactly that gap). Coalescing first lets the window search (and
    # its padding) see the whole span at once.
    coalesced = []
    for c_start, c_end, state in plan:
        if coalesced and coalesced[-1][2] == state and state in ("main", "host") and abs(coalesced[-1][1] - c_start) < 1e-6:
            coalesced[-1] = (coalesced[-1][0], c_end, state)
        else:
            coalesced.append((c_start, c_end, state))
    plan = coalesced

    out = []
    for orig_start, c_end, state in plan:
        # the opening hook is a deliberate override (always "main", regardless of what was actually
        # detected -- see render()) -- never second-guess it back to a real split here.
        if state not in ("main", "host") or c_end <= opening_end:
            out.append((orig_start, c_end, state))
            continue
        c_start = max(orig_start, opening_end)
        if c_start > orig_start:
            out.append((orig_start, c_start, state))  # the protected leading sliver, untouched
        splits = sorted(
            s.t for s in raw_samples
            if c_start <= s.t < c_end and s.state == "split"
            and s.main_x is not None and s.host_x is not None and not s.full_screen
        )
        if not splits:
            out.append((c_start, c_end, state))
            continue
        windows = [[splits[0], splits[0]]]
        for t in splits[1:]:
            (windows[-1].__setitem__(1, t) if t - windows[-1][1] <= 0.5 else windows.append([t, t]))
        cur = c_start
        pieces = []
        for w0, w1 in windows:
            # The true content transition can land anywhere inside the 0.2s gap either side of the last
            # confirmed real sample -- a fixed +/-0.1s pad is really just guessing the gap's midpoint.
            # Confirmed directly: that guess landed a frame or two early, so the solo crop right after the
            # boundary pointed at a position the footage hadn't actually reached yet -- one frame of blank
            # background (a poster, a wall) between the real split and the next real solo shot. Refine to
            # the frame-accurate cut the same way _refine_pan_snap does, but ONLY across this specific gap
            # (never a blanket scan of every boundary -- that's confirmed to invent cuts where a shot was
            # already smooth, see _refine_all_boundaries's docstring).
            w_start = _refine_pan_snap(video_path, max(cur, w0 - 0.25), w0) if w0 - 0.25 > cur else max(cur, w0 - 0.1)
            w_end = _refine_pan_snap(video_path, w1, min(c_end, w1 + 0.25)) if w1 + 0.25 < c_end else min(c_end, w1 + 0.1)
            if w_end - w_start < 0.4:  # a genuine split window can be a bit shorter than MIN_SHOT
                continue  # too short to trust on its own -- leave it merged into the surrounding solo state
            # Emit the solo lead-in only once its split is accepted, and never leave a gap: short_5_v1
            # (2026-10-04) appended (cur, w_start) for a split that was then rejected, without advancing
            # cur, so the next window re-appended the same stretch -- 27s of repeated footage. A lead-in
            # too short to be its own shot is absorbed into the split instead of silently dropped.
            if w_start - cur >= MIN_SHOT:
                pieces.append((cur, w_start, state))
            else:
                w_start = cur
            pieces.append((w_start, w_end, "split"))
            cur = w_end
        if c_end - cur >= MIN_SHOT:
            pieces.append((cur, c_end, state))
        elif pieces:
            pieces[-1] = (pieces[-1][0], c_end, pieces[-1][2])  # absorb a tiny leftover, don't drop it
        out.extend(pieces if pieces else [(c_start, c_end, state)])
    # coalesce adjacent same-state pieces (e.g. the opening hook's protected leading sliver butting
    # up against an identical "main" piece right after it) -- same state, no reason for a boundary.
    merged = []
    for s, e, st in out:
        if merged and merged[-1][2] == st and abs(merged[-1][1] - s) < 1e-6:
            merged[-1] = (merged[-1][0], e, st)
        else:
            merged.append((s, e, st))
    return merged


def _demote_hollow_splits(plan, raw_samples):
    """A stacked "split" chunk whose source drops one person for 2+ consecutive raw samples (0.4s) renders
    that stretch with one half pointed at an empty pane sliver (short_5_v2 0:07, flagged by the user: the
    top half showed her blanket next to his poster while he was off-screen). Smoothing had outvoted the
    brief full-screen run. Rather than add a split -> solo -> split flicker inside ~1s, render the whole
    chunk solo on her ("main"): losing his face briefly reads fine, an empty half does not."""
    out = []
    for c_start, c_end, state in plan:
        if state == "split":
            run = longest = 0
            for s in sorted((s for s in raw_samples if c_start <= s.t < c_end), key=lambda s: s.t):
                run = run + 1 if (s.state != "split" or s.full_screen) else 0
                longest = max(longest, run)
            if longest >= 2:
                state = "main"
        out.append((c_start, c_end, state))
    return out


def _expand_flip_flops(
    video_path: str, plan, raw_samples, main_track: PositionTrack, host_track: PositionTrack, opening_end: float
):
    """The app enlarges whoever is talking to near-full-screen and shrinks the other to an unusable
    sliver. Two failure modes follow from that:

    1. A single "main"/"host" chunk can hide an internal identity swap -- both people's enlarged x can
       land under CUT_JUMP apart (they're both roughly centre-frame when enlarged), so it reads to the
       rest of the pipeline as one person panning, not a cut. Split at the jump (below) so it renders as
       a clean cut instead of a smeared pan across two unrelated scenes.
    2. A genuine brief two-person "split" moment between two solo shots can vanish entirely: smooth_states
       majority-votes state over a +/-1s window, and a real ~0.8s split sandwiched between two full-screen
       shots gets outvoted and relabelled "main"/"host" like its neighbours. _recover_hidden_splits (below)
       finds it back from the raw detections directly.

    An EARLIER version of this also tried to paper over the resulting solo-to-solo cuts with a "stack":
    the currently-enlarged person live, the other half filled with a frozen photo of them from the nearest
    real split moment (position alone can't tell two enlarged faces apart, so identity was resolved by
    colour-histogram match against reference crops). That is deliberately NOT done any more -- the user
    flagged it three times running, on three different chunks, at every duration tried (0.9s, 1.7s, 2.7s):
    a held still photo reads as "a photo", not the person, no matter how cleanly it's animated, because
    real people never hold perfectly still (blink, breathe, micro-expression) the way a frozen frame does.
    Inventing "both visible" out of footage that only ever shows one of them at a time was the wrong
    trade -- a clean solo cut, matching what the source itself actually shows, is the honest answer."""
    plan = _recover_hidden_splits(plan, raw_samples, opening_end, video_path)

    # Split each main/host chunk at internal full-screen identity jumps, so a real person-swap inside
    # one nominal chunk renders as a clean cut instead of _solo_pan_crop sweeping across it as if it
    # were one person moving.
    out = []
    for c_start, c_end, state in plan:
        if state not in ("main", "host") or c_end - c_start < 2 * MIN_SHOT:
            out.append((c_start, c_end, state))
            continue
        attr = "main_x" if state == "main" else "host_x"
        pts = sorted(
            (s.t, getattr(s, attr)) for s in raw_samples
            if c_start <= s.t < c_end and getattr(s, attr) is not None and s.full_screen
        )
        # A FLIP_JUMP-sized gap between two raw samples proves a real identity swap happened somewhere
        # in that 0.2s window -- same guaranteed-real-transition reasoning as _refine_split_boundaries,
        # so frame-accurate refinement is safe here too. Confirmed directly: this split used to land the
        # boundary at the LATER sample's own timestamp (not even a midpoint), up to a full 0.2s after the
        # true cut -- a transitional frame belonging to neither person flashed right before the new shot.
        cut_ts = [
            _refine_pan_snap(video_path, pts[k][0], pts[k + 1][0])
            for k in range(len(pts) - 1) if abs(pts[k + 1][1] - pts[k][1]) > FLIP_JUMP
        ]
        bounds = [c_start]
        for ct in cut_ts:
            if ct - bounds[-1] >= MIN_SHOT and c_end - ct >= MIN_SHOT:
                bounds.append(ct)
        bounds.append(c_end)
        for j in range(len(bounds) - 1):
            out.append((bounds[j], bounds[j + 1], state))
    return out, {}


def _build_filter_complex(
    plan: list[tuple[float, float, str]],
    main_track: PositionTrack,
    host_track: PositionTrack,
    frame_w: int,
    frame_h: int,
    ass_filter_path: str,
    raw_samples,
    opening_end: float,
    video_path: str,
    face_y_at=None,
    pane_edge_at=None,
) -> tuple[str, str, str]:
    v_parts = []
    concat_inputs = []
    for idx, (c_start, c_end, state) in enumerate(plan):
        mid = (c_start + c_end) / 2
        v_parts.append(f"[0:v]trim=start={c_start}:end={c_end},setpts=PTS-STARTPTS[vraw{idx}]")
        v_parts.append(f"[0:a]atrim=start={c_start}:end={c_end},asetpts=PTS-STARTPTS[a{idx}]")

        # A tracked position more than 0.75s old can be stale in a way no
        # crop math fixes -- the app resizes the panes over time, so a
        # position valid when a pane was wide can fall past its edge a
        # couple seconds later once it's narrowed. This applies to EVERY
        # state, not just "split": a solo host/main crop trusting a stale or
        # boundary-adjacent position bled into the other person's side just
        # as visibly as a stacked one did. Not-fresh always falls back to
        # the track's own default (a position deliberately far from either
        # pane edge), never to a smoothed/held value that can itself be the
        # stale one.
        # .near() returns (position, full_screen) -- full_screen is True when
        # the detection came from the unrestricted "big face" full-frame pass
        # (one person spanning the whole screen) rather than a pane-
        # restricted search. A full-screen face has no pane boundary to
        # bleed past -- the other person isn't even on screen -- so it must
        # skip the MAIN_MAX_X_FRAC/HOST_MIN_X_FRAC clamps below, which are
        # only meant to stop a genuine narrow-pane detection's crop from
        # reaching into the other person's pane. Confirmed via the source
        # frame directly: a "main" chunk getting clamped turned out to be a
        # full-screen close-up, and the clamp was just dragging the crop off
        # his face for no real bleed risk.
        near_main_res = main_track.near(mid, max_gap=0.75)
        near_host_res = host_track.near(mid, max_gap=0.75)
        near_main, main_full_screen = near_main_res if near_main_res is not None else (None, False)
        near_host, host_full_screen = near_host_res if near_host_res is not None else (None, False)
        default_main_x = frame_w * DEFAULT_MAIN_FRAC
        default_host_x = frame_w * DEFAULT_HOST_FRAC

        # A "fresh" detection can still be wrong on its own (a false
        # positive near the edge of a pane), not just stale -- solo states
        # have no second position to compare against the way "split" does,
        # so build one here: a broader-window reference for roughly where
        # the other person currently is. Any candidate too close to that
        # reference is rejected even though it passed the freshness check,
        # since a real detection of one specific person should never land
        # right on top of where the other one roughly is.
        ref_main_res = near_main_res if near_main_res is not None else main_track.near(mid, max_gap=2.5)
        ref_host_res = near_host_res if near_host_res is not None else host_track.near(mid, max_gap=2.5)
        ref_main = ref_main_res[0] if ref_main_res is not None else None
        ref_host = ref_host_res[0] if ref_host_res is not None else None
        min_solo_separation = 400
        if near_main is not None and ref_host is not None and abs(near_main - ref_host) < min_solo_separation:
            near_main = None
        if near_host is not None and ref_main is not None and abs(near_host - ref_main) < min_solo_separation:
            near_host = None

        # near_main/near_host and their full_screen flags come from two
        # INDEPENDENT PositionTrack lookups -- each can pull its nearest raw
        # sample from a different sub-second moment within the gap window.
        # That let a stale "full_screen=True" (recorded when the other side
        # was genuinely empty a moment earlier) survive alongside a fresh,
        # real detection on the other side found right now -- seen directly
        # in the source: this stretch flips between a full-screen shot and a
        # real ~48/52 split within a fraction of a second. If near_host is
        # confidently found at all, there IS real adjacent content near_main
        # could bleed into regardless of what an older sample once said, so
        # full_screen can't be trusted here -- and symmetrically for host.
        if near_main is not None and near_host is not None:
            main_full_screen = False
            host_full_screen = False

        if state == "split":
            # Even two "confident, recent" detections can still be wrong --
            # seen with a host detection that was genuinely fresh (not
            # stale) but still landed close to his pane's edge, likely a
            # false positive from widening the host search area to catch
            # him when his pane expands (which also means it now searches
            # through a chunk of neutral/her-side background when his pane
            # is narrow instead). No amount of narrowing the crop or
            # tightening the time window fixes a wrong detection, so the
            # real defense is requiring a large separation before trusting
            # it's genuinely two different people -- solo crops have been
            # reliable all session, so it's safer to fall back to solo more
            # often than to risk another mixed-background stack.
            min_separation = 700
            if near_main is None and near_host is None:
                state = "main"  # neither confidently tracked -- fall back to whichever default, prefer her
            elif near_host is None:
                state = "main"
            elif near_main is None:
                state = "host"
            elif abs(near_main - near_host) < min_separation:
                state = "main"

        if state in ("main", "host") and (pan := _solo_pan_crop(state, c_start, c_end, main_track, host_track, frame_w, frame_h, raw_samples, video_path, opening_end, pane_edge_at)):
            v_parts.append(f"[vraw{idx}]{pan}[v{idx}]")
        elif state == "main":
            if near_main is not None:
                max_x_frac = 1.0 if main_full_screen else MAIN_MAX_X_FRAC
                crop = _face_crop(near_main, SOLO_W, SOLO_H, frame_w, frame_h, FACE_CROP_W, 0.0, max_x_frac)
            else:
                crop = _face_crop(
                    default_main_x, SOLO_W, SOLO_H, frame_w, frame_h, DEFAULT_FALLBACK_CROP_W, 0.0, MAIN_MAX_X_FRAC
                )
            v_parts.append(f"[vraw{idx}]{crop}[v{idx}]")
        elif state == "host":
            if near_host is not None:
                host_x = near_host
                min_x_frac = 0.0 if host_full_screen else HOST_MIN_X_FRAC
            else:
                host_x = default_host_x
                min_x_frac = HOST_MIN_X_FRAC
            crop = _face_crop(host_x, SOLO_W, SOLO_H, frame_w, frame_h, HOST_CROP_W, min_x_frac)
            v_parts.append(f"[vraw{idx}]{crop}[v{idx}]")
        elif state == "split":
            # Use the raw nearby detections directly (near_main/near_host),
            # not the smoothed .at() value -- smoothing blends in samples up
            # to 1.5s away that can belong to a differently-sized pane,
            # which is exactly the staleness this branch exists to avoid.
            v_parts.append(f"[vraw{idx}]split=2[vraw{idx}a][vraw{idx}b]")
            seams = [pane_edge_at(c_start + (c_end - c_start) * k / 4) for k in (1, 2, 3)] if pane_edge_at else []
            seams = [e for e in seams if e is not None]
            seam = sorted(seams)[len(seams) // 2] if len(seams) >= 2 and max(seams) - min(seams) < 20 else None
            if seam is not None and near_main < seam < near_host:
                # widen each half right up to the measured seam (see SPLIT_WIDE_W)
                top_w = min(SPLIT_WIDE_W, frame_w - seam - PANE_EDGE_MARGIN)
                bot_w = min(SPLIT_WIDE_W, seam - PANE_EDGE_MARGIN)
                top_lo, bot_hi = (seam + PANE_EDGE_MARGIN) / frame_w, (seam - PANE_EDGE_MARGIN) / frame_w
            else:
                top_w = bot_w = SPLIT_FACE_CROP_W
                top_lo, bot_hi = 0.0, 1.0
            top_crop = _face_crop(near_host, HALF_W, HALF_H, frame_w, frame_h, top_w, top_lo,
                                  face_y=face_y_at(c_start, c_end, near_host) if face_y_at else None)
            bot_crop = _face_crop(near_main, HALF_W, HALF_H, frame_w, frame_h, bot_w, 0.0, bot_hi,
                                  face_y=face_y_at(c_start, c_end, near_main) if face_y_at else None)
            v_parts.append(f"[vraw{idx}a]{top_crop}[top{idx}]")
            v_parts.append(f"[vraw{idx}b]{bot_crop}[bot{idx}]")
            v_parts.append(f"[top{idx}][bot{idx}]vstack=2[v{idx}]")
        elif state == "settle":
            # Renders as a genuine stack only when there's real evidence of
            # both people nearby (see _settle_layout) -- never the raw
            # "none" full-frame fallback below, which shows the source's
            # own native horizontal side-by-side layout when both are on
            # screen, exactly what this format must never show -- but also
            # never an invented stack when only one person is actually
            # confirmed nearby, which just showed empty background (a
            # poster, a wall) in the other half instead of a face.
            layout, s_main_x, s_host_x = _settle_layout(mid, main_track, host_track)
            if layout == "split":
                v_parts.append(f"[vraw{idx}]split=2[vraw{idx}a][vraw{idx}b]")
                top_crop = _face_crop(s_host_x, HALF_W, HALF_H, frame_w, frame_h, SPLIT_FACE_CROP_W,
                                      face_y=face_y_at(c_start, c_end, s_host_x) if face_y_at else None)
                bot_crop = _face_crop(s_main_x, HALF_W, HALF_H, frame_w, frame_h, SPLIT_FACE_CROP_W,
                                      face_y=face_y_at(c_start, c_end, s_main_x) if face_y_at else None)
                v_parts.append(f"[vraw{idx}a]{top_crop}[top{idx}]")
                v_parts.append(f"[vraw{idx}b]{bot_crop}[bot{idx}]")
                v_parts.append(f"[top{idx}][bot{idx}]vstack=2[v{idx}]")
            elif layout == "host":
                crop = _face_crop(s_host_x, SOLO_W, SOLO_H, frame_w, frame_h, HOST_CROP_W, HOST_MIN_X_FRAC)
                v_parts.append(f"[vraw{idx}]{crop}[v{idx}]")
            else:  # "main", including neither side confirmed at all
                x = s_main_x if s_main_x is not None else default_main_x
                crop_w = FACE_CROP_W if s_main_x is not None else DEFAULT_FALLBACK_CROP_W
                crop = _face_crop(x, SOLO_W, SOLO_H, frame_w, frame_h, crop_w, 0.0, MAIN_MAX_X_FRAC)
                v_parts.append(f"[vraw{idx}]{crop}[v{idx}]")
        else:  # "none" -- structurally not the two-pane layout either, a genuine cutaway
            # Meme/reaction inserts: the whole clip stays visible (never cropped, it is the joke), sitting
            # on a blurred, zoomed copy of itself so the 9:16 frame is filled instead of leaving ~60% of
            # it as black bars around a thin strip.
            v_parts.append(f"[vraw{idx}]split=2[mbg{idx}][mfg{idx}]")
            v_parts.append(
                f"[mbg{idx}]scale={SOLO_W}:{SOLO_H}:force_original_aspect_ratio=increase,"
                f"crop={SOLO_W}:{SOLO_H},boxblur=40:6,eq=brightness=-0.12,setsar=1[mbgb{idx}]"
            )
            v_parts.append(f"[mfg{idx}]scale={SOLO_W}:-2,setsar=1[mfgs{idx}]")
            v_parts.append(f"[mbgb{idx}][mfgs{idx}]overlay=(W-w)/2:(H-h)/2[v{idx}]")
        concat_inputs.append(f"[v{idx}][a{idx}]")

    n = len(plan)
    v_parts.append(f"{''.join(concat_inputs)}concat=n={n}:v=1:a=1[vcat][aout]")
    v_parts.append(f"[vcat]ass='{ass_filter_path}'[vout]")
    return ";".join(v_parts), "[vout]", "[aout]"


def _realign_hook_boundary(plan, raw_samples, clip_start: float, opening_end: float):
    """The forced-main hook (see render()) always ends at opening_end, but if the source itself already
    cut to different content before then, the final stretch of the hook plays pixels the crop was never
    built for -- the crop still frames the ORIGINAL subject while the frame itself already shows someone
    else, which can clear right down to background with nobody in it at all ("a frame where the screen
    hasn't adjusted yet" -- the user's own description, confirmed directly: a single frame of bare wall
    and a poster, no face, right before the hook's fixed boundary). Marking it a known seam and leaving
    the QA gate to ignore it was treating the symptom; moving the actual boundary to where the content
    actually changes removes the mismatch instead of hiding it from the checker.

    Shortening the hook's effective end doesn't stick through _build_crop_plan/_simplify_plan (their
    merge pass folds it straight back into the next chunk), so this runs LAST, directly on the already-
    finalised plan, where nothing downstream can undo it."""
    if len(plan) < 2:
        return plan
    s0, e0, st0 = plan[0]
    s1, e1, st1 = plan[1]
    if not (abs(s0 - clip_start) < 1e-3 and abs(e0 - opening_end) < 1e-3 and st0 in ("main", "host") and st1 in ("main", "host")):
        return plan
    within = [s for s in raw_samples if s0 <= s.t < e0]
    if not within or not any(s.state == "split" for s in within) or opening_end - within[-1].t >= 1.0:
        return plan
    boundary = min(within[-1].t + 0.1, e0)
    if boundary - s0 < MIN_SHOT or e1 - boundary < MIN_SHOT:
        return plan
    return [(s0, boundary, st0), (boundary, e1, st1)] + plan[2:]


_BOUNDARY_SEARCH = 0.3  # seconds either side of a nominal split<->solo boundary to look for the true cut


def _refine_split_boundaries(plan, video_path: str):
    """General prevention for the recurring "one frame not adjusted yet at a cut" report. Every chunk
    boundary becomes a real ffmpeg trim/concat seam, and sparse 0.2s raw-sample timing can place our
    computed boundary a frame or two away from where the source itself actually cuts -- the two segments
    joined at a slightly-off seam briefly disagree with the real footage (a blank stretch of background,
    a sliver of transitional layout) right at the cut. _realign_hook_boundary and the padding fix in
    _recover_hidden_splits each fixed ONE instance of this by hand; this is the general version.

    A FIRST version of this ran on every ordinary boundary and made things worse (confirmed directly:
    cuts jumped 10->17, reading as LESS smooth) -- a generic "is this really a hard cut" confidence test,
    run on an arbitrary narrow window, is too easily satisfied by ordinary talking-head motion (a head
    turn, a gesture) that was never a scene change, so it invented new cuts at boundaries that were
    already smooth. This version is scoped instead of gated: it only ever touches a boundary between a
    "split" chunk and an adjacent solo ("main"/"host") chunk. Those two are fundamentally different
    screen layouts -- a real transition is GUARANTEED to exist somewhere in the gap, no confidence test
    needed, only pinpointing exactly where -- so there's no risk of inventing a cut that shouldn't exist,
    the failure mode that sank the first version. A "main"<->"main" pan is deliberately left untouched."""
    if len(plan) < 2:
        return plan
    out = [plan[0]]
    for i in range(1, len(plan)):
        prev_s, prev_e, prev_st = out[-1]
        cur_s, cur_e, cur_st = plan[i]
        touching = abs(prev_e - cur_s) < 1e-6
        is_split_edge = {prev_st, cur_st} == {"split", "main"} or {prev_st, cur_st} == {"split", "host"}
        if touching and is_split_edge and prev_e - prev_s >= MIN_SHOT and cur_e - cur_s >= MIN_SHOT:
            lo, hi = max(prev_s, prev_e - _BOUNDARY_SEARCH), min(cur_e, cur_s + _BOUNDARY_SEARCH)
            if hi - lo > 0.05:
                refined = _refine_pan_snap(video_path, lo, hi)
                if MIN_SHOT <= refined - prev_s and cur_e - refined >= MIN_SHOT:
                    out[-1] = (prev_s, refined, prev_st)
                    cur_s = refined
        out.append((cur_s, cur_e, cur_st))
    return out


def _hook_seam_span(raw_samples, clip_start: float, opening_end: float) -> tuple[float, float] | None:
    """The forced-main hook window (see render()) is a deliberate override: show the opening subject for
    the full ~3s regardless of what the source actually does. But cropping only chooses which part of
    each frame to show -- it can't hide a real cut in the underlying footage. If the source itself
    already cut to something else (a real two-pane split, or a different full-screen person) before the
    nominal 3s is up, the last stretch of the hook plays pixels that have already moved on while still
    being cropped for the ORIGINAL subject, and then the next chunk starts fresh right at the fixed
    boundary -- two real transitions landing within a fifth of a second of each other. Tried shortening
    the forced window to end where the source itself last confirms the opening subject instead: doesn't
    work, the plan's own merge pass folds the shortened chunk straight back into the one after it, so the
    boundary the crop math sees stops matching the boundary this function computes. Marking the seam as a
    known, unavoidable transition (the same mechanism a meme cutaway's own internal edit already uses) is
    the honest fix -- not a blanket cut-detector exemption, one specific span with a specific cause.

    Dynamic per-keypoint tracking (see _solo_pan_crop) follows the source faithfully through the WHOLE
    hook, including into that real split -- which is correct for keeping her face on screen, but it means
    the snap into the split and the snap out of it at the fixed boundary are BOTH real, both inside the
    hook. The span covers from where the split starts to well past the boundary, not just its tail."""
    within = [s for s in raw_samples if clip_start <= s.t < opening_end]
    if not within:
        return None
    has_split = any(s.state == "split" for s in within)
    if not has_split or opening_end - within[-1].t >= 1.0:
        return None
    # Covers the whole hook, not just from the first split sample: the snap into it (see _solo_pan_crop)
    # can land a little before the first raw sample that's actually labelled "split" -- confirmed
    # directly, a cut still showed up just outside a tighter span.
    return (clip_start, opening_end + 1.0)


def _detect_cached(video_path: str, start: float, duration: float):
    """detect_regions_over_time takes ~90s per 30s clip, and re-rendering a version (new crop rules, same
    footage) doesn't change the detections, so cache them next to the transcript. The cache is dropped
    when the source video or reframe.py (the detector) is newer than it."""
    cache = WORK_DIR / f"{Path(video_path).stem}_{start:.2f}_{duration:.2f}_samples.json"
    newest_dep = max(Path(video_path).stat().st_mtime, Path(__file__).with_name("reframe.py").stat().st_mtime)
    if cache.exists() and cache.stat().st_mtime > newest_dep:
        d = json.loads(cache.read_text(encoding="utf-8"))
        return [Sample(**x) for x in d["samples"]], d["frame_w"], d["frame_h"]
    samples, frame_w, frame_h = detect_regions_over_time(video_path, start, duration)
    cache.write_text(json.dumps({
        "frame_w": frame_w, "frame_h": frame_h,
        "samples": [{"t": x.t, "state": x.state, "main_x": None if x.main_x is None else float(x.main_x),
                     "host_x": None if x.host_x is None else float(x.host_x), "full_screen": bool(x.full_screen)}
                    for x in samples],
    }), encoding="utf-8")
    return samples, frame_w, frame_h


def _append_endscreen(main_path: Path, frame_w: int, frame_h: int, style: str = "brand") -> None:
    """Appends the channel's endscreen card (ENDSCREEN_PNG) to the end of the rendered short in place.
    Silent; push-in and fade-out matched to the user's own published short. Upscaled before zoompan,
    which otherwise rounds its crop offsets to whole pixels and visibly jitters on a still."""
    if style == "youtube":
        if not ENDSCREEN_YOUTUBE.exists():
            import make_endscreen_card
            make_endscreen_card.build_youtube()
        _concat_endscreen(main_path, ENDSCREEN_YOUTUBE)
        return
    frames = round(ENDSCREEN_SECS * 30)
    clip = WORK_DIR / "endscreen_clip.mp4"
    vf = (f"scale={frame_w * 4}:{frame_h * 4},zoompan=z='1+0.12*on/{frames}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
          f":d={frames}:s={frame_w}x{frame_h}:fps=30,fade=t=out:st={ENDSCREEN_SECS - ENDSCREEN_FADE:.2f}:d={ENDSCREEN_FADE}"
          ",format=yuv420p,setsar=1")
    subprocess.run([
        "ffmpeg", "-y", "-loop", "1", "-framerate", "30", "-t", f"{ENDSCREEN_SECS}", "-i", str(ENDSCREEN_PNG),
        "-f", "lavfi", "-t", f"{ENDSCREEN_SECS}", "-i", "anullsrc=r=48000:cl=stereo",
        "-vf", vf, "-map", "0:v", "-map", "1:a",
        *VIDEO_ENC,
        "-c:a", "aac", "-b:a", "128k", "-ar", "48000", "-shortest", str(clip),
    ], check=True)
    _concat_endscreen(main_path, clip)


def _concat_endscreen(main_path: Path, clip: Path) -> None:
    combined = WORK_DIR / "with_endscreen.mp4"
    concat_list = WORK_DIR / "endscreen_concat.txt"
    concat_list.write_text(
        f"file '{main_path.resolve().as_posix()}'\nfile '{clip.resolve().as_posix()}'\n", encoding="utf-8"
    )
    subprocess.run([
        "ffmpeg", "-y", "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c:v", "copy",
        "-c:a", "aac", "-b:a", "128k", "-ar", "48000", str(combined),
    ], check=True)
    combined.replace(main_path)


def render(video_path: str, start: float, duration: float, transcript_path: str, out_path: str,
           endscreen: str = "brand") -> None:
    all_words = json.loads(Path(transcript_path).read_text(encoding="utf-8"))
    clip_words = [
        Word(w["text"], w["start"] - start, w["end"] - start)
        for w in all_words
        if start <= w["start"] < start + duration
    ]

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    raw_samples, frame_w, frame_h = _detect_cached(video_path, start, duration)
    samples = smooth_states(raw_samples)
    samples = smooth_positions(samples)
    opening_end = start + 3.0  # the hook needs to open on the main subject regardless of what got detected there
    plan = _build_crop_plan(samples, clip_start=start, clip_end=start + duration, opening_end=opening_end)
    main_track = PositionTrack(samples, "main_x", frame_w, DEFAULT_MAIN_FRAC)
    host_track = PositionTrack(samples, "host_x", frame_w, DEFAULT_HOST_FRAC)
    n_before = len(plan)
    plan = _simplify_plan(plan, main_track, host_track, _cutaway_edge_refiner(video_path))
    # Flip-flop detection needs the true raw (pre-smoothing) positions -- smooth_positions anchors to
    # each sample's own value but still blends in nearby ones up to 300px away, which can smear a real
    # sub-CUT_JUMP identity swap into a gradual drift instead of the clean single-sample jump it is.
    plan, _ = _expand_flip_flops(video_path, plan, raw_samples, main_track, host_track, opening_end)
    plan = _realign_hook_boundary(plan, raw_samples, start, opening_end)
    plan = _refine_split_boundaries(plan, video_path)
    plan = _demote_hollow_splits(plan, raw_samples)
    # Every cut on a real frame time: a boundary sitting between two frames is resolved by trim's own
    # rounding, which can hand one frame of the outgoing shot to the incoming one (a one-frame flash).
    plan = [(round(s * 30) / 30, round(e * 30) / 30, st) for s, e, st in plan]
    plan = [c for c in plan if c[1] > c[0]]
    # The plan must tile the clip exactly; overlapping chunks replay footage (short_5_v1: +27s) and gaps drop it.
    seams = [(round(a[1] - start, 2), round(b[0] - start, 2)) for a, b in zip(plan, plan[1:]) if abs(b[0] - a[1]) > 0.02]
    if seams:
        raise RuntimeError(f"crop plan has gaps/overlaps at {seams[:5]} (clip-relative); refusing to render")
    print(
        f"Reframe plan for {Path(out_path).name} ({n_before} chunks -> {len(plan)} shots): "
        + ", ".join(f"{st}[{s - start:.1f}-{e - start:.1f}]" for s, e, st in plan)
    )

    def y_at(clip_relative_t: float) -> int:
        # Looks up the chunk's actual planned state, not a fresh sample
        # lookup -- a "settle" chunk can render as a vertical stack or a
        # solo crop (see _settle_layout) but a raw re-lookup here would see
        # whatever the underlying sample's true state is (often "main"),
        # which can disagree and place the caption at the wrong position
        # for what's actually on screen.
        t = clip_relative_t + start
        state = next((st for s, e, st in plan if s <= t < e), "main")
        if state == "settle":
            state = _settle_layout(t, main_track, host_track)[0]
        return SPLIT_CAPTION_Y if state == "split" else SOLO_CAPTION_Y

    # No captions during a genuine cutaway ("none" -- a meme/reaction insert,
    # not the call) -- captions there draw attention away from the insert
    # itself, which is the whole point of cutting to it. Not applied to
    # "settle": that's still the real call, just mid-transition, so the
    # words being said there still need captioning like anywhere else.
    caption_words = [
        w for w in clip_words if next((st for s, e, st in plan if s <= w.start + start < e), "main") != "none"
    ]
    ass_path = WORK_DIR / f"{Path(out_path).stem}.ass"
    write_ass_file(caption_words, str(ass_path), y_at=y_at)
    ass_filter_path = str(ass_path).replace("\\", "/").replace(":", "\\:")

    filter_complex, vlabel, alabel = _build_filter_complex(
        plan, main_track, host_track, frame_w, frame_h, ass_filter_path, raw_samples, opening_end, video_path,
        _face_y_finder(video_path), _pane_edge_finder(video_path),
    )
    # Normalise to the -14 LUFS the platforms play at (YouTube turns loud videos
    # down but never turns quiet ones up; raw call audio lands around -19 to -21).
    # single-pass loudnorm is dynamic and overshoots on a sudden laugh or shout (+0.4 dBTP, an 8 LU spike
    # on the kiss moment), so tame peaks before it and hard-limit after it (0.79 = -2 dB sample peak; 0.84 still hit -0.3 dBTP after AAC on short_3)
    filter_complex += (f";{alabel}acompressor=threshold=-18dB:ratio=3:attack=5:release=120,"
                       "loudnorm=I=-14:TP=-1.5:LRA=11,alimiter=limit=0.79:level=false[anorm]")
    alabel = "[anorm]"
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        # Lanczos for every scale in the graph: the solo crops are upscaled ~1.7x, and the default
        # bicubic resizer reads soft and blocky at that ratio.
        "-filter_complex", "sws_flags=lanczos+accurate_rnd;" + filter_complex,
        "-map", vlabel, "-map", alabel,
        *VIDEO_ENC,
        "-c:a", "aac", "-b:a", "128k", "-ar", "48000",  # loudnorm upsamples to 192kHz internally
        out_path,
    ]
    subprocess.run(cmd, check=True)
    _append_endscreen(Path(out_path), SOLO_W, SOLO_H, endscreen)
    # Sidecar with the exact inputs, so any version can be re-rendered in one command
    # (python render_short.py --video V --start S --duration D --transcript T --out NEW).
    meme_spans = [[round(s - start, 3), round(e - start, 3)] for s, e, st in plan if st == "none"]
    cutaway_spans = list(meme_spans)
    hook_seam = _hook_seam_span(raw_samples, start, opening_end)
    if hook_seam is not None:
        cutaway_spans.append([round(hook_seam[0] - start, 3), round(hook_seam[1] - start, 3)])
    Path(out_path).with_suffix(".render.json").write_text(json.dumps({
        "video": video_path, "start": start, "duration": duration, "transcript": transcript_path,
        # clip-relative spans where a cut is real but ours to ignore: a meme's own internal edit, or a
        # source transition the forced-main hook window deliberately plays through (see _hook_seam_span)
        "cutaways": cutaway_spans,
        # the "none" (meme insert) spans alone, without the hook seam: what the face and
        # call-as-cutaway gates need
        "memes": meme_spans,
        # stacked two-person spans, for the short-split-both-faces gate
        "splits": [[round(s - start, 3), round(e - start, 3)] for s, e, st in plan if st == "split"],
    }, indent=1), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render one finished short with dynamic reframing and burned-in captions.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--start", type=float, required=True)
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--transcript", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--endscreen", choices=["brand", "youtube"], default="brand",
                        help="brand: 'Follow for more' card (IG/FB/TikTok); youtube: the SUBSCRIBE card")
    args = parser.parse_args()
    render(args.video, args.start, args.duration, args.transcript, args.out, args.endscreen)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
