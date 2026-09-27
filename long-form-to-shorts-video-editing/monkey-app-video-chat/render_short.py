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
import subprocess
from pathlib import Path

from captions import Word, write_ass_file
from reframe import PositionTrack, Sample, detect_regions_over_time, smooth_positions, smooth_states

WORK_DIR = Path(__file__).parent / "work"
OUTPUT_DIR = Path(__file__).parent / "output"

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
SPLIT_FACE_CROP_W = 460

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
) -> str:
    """Crops a fixed-width close-up centered on face_x (clamped to stay
    within the frame), then scales/crops to the exact target size. Not
    bounded to any pane -- see FACE_CROP_W. min_x_frac/max_x_frac hard-floor
    or hard-ceiling the crop's left/right edge (as a fraction of frame_w)
    regardless of face_x -- for a detection that's centered close enough to
    a narrow pane's edge that even a narrow width still reaches past it.
    Seen both ways: a host detection only ~15px from where his pane starts
    (min_x_frac), and symmetrically a main detection whose crop's right edge
    reached past where her pane ends when it's narrow (max_x_frac)."""
    crop_w = min(crop_w, frame_w)
    x = round(face_x - crop_w / 2)
    min_x = frame_w * min_x_frac
    max_x = frame_w * max_x_frac - crop_w
    x = int(max(min_x, max(0, min(x, min(max_x, frame_w - crop_w)))))
    x = int(min(x, frame_w - crop_w))
    return (
        f"crop={crop_w}:{frame_h}:{x}:0,"
        f"scale={target_w}:{target_h}:force_original_aspect_ratio=increase,"
        f"crop={target_w}:{target_h},setsar=1"
    )


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
        unstable = (
            _position_spread(samples, start, end, state, pad=pad) > POSITION_SPREAD_THRESHOLD
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
                span = split - start
                n_pieces = max(1, round(span / SETTLE_SUBCHUNK))
                piece = span / n_pieces
                st = start
                for i in range(n_pieces):
                    se = split if i == n_pieces - 1 else start + piece * (i + 1)
                    plan.append((st, se, "settle"))
                    st = se
            if split < end:
                plan.append((split, end, state))
        else:
            plan.append((start, end, state))
    return plan


def _build_filter_complex(
    plan: list[tuple[float, float, str]],
    main_track: PositionTrack,
    host_track: PositionTrack,
    frame_w: int,
    frame_h: int,
    ass_filter_path: str,
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

        if state == "main":
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
            top_crop = _face_crop(near_host, HALF_W, HALF_H, frame_w, frame_h, SPLIT_FACE_CROP_W)
            bot_crop = _face_crop(near_main, HALF_W, HALF_H, frame_w, frame_h, SPLIT_FACE_CROP_W)
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
                top_crop = _face_crop(s_host_x, HALF_W, HALF_H, frame_w, frame_h, SPLIT_FACE_CROP_W)
                bot_crop = _face_crop(s_main_x, HALF_W, HALF_H, frame_w, frame_h, SPLIT_FACE_CROP_W)
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
            v_parts.append(f"[vraw{idx}]{_none_crop()}[v{idx}]")
        concat_inputs.append(f"[v{idx}][a{idx}]")

    n = len(plan)
    v_parts.append(f"{''.join(concat_inputs)}concat=n={n}:v=1:a=1[vcat][aout]")
    v_parts.append(f"[vcat]ass='{ass_filter_path}'[vout]")
    return ";".join(v_parts), "[vout]", "[aout]"


def render(video_path: str, start: float, duration: float, transcript_path: str, out_path: str) -> None:
    all_words = json.loads(Path(transcript_path).read_text(encoding="utf-8"))
    clip_words = [
        Word(w["text"], w["start"] - start, w["end"] - start)
        for w in all_words
        if start <= w["start"] < start + duration
    ]

    WORK_DIR.mkdir(parents=True, exist_ok=True)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)

    samples, frame_w, frame_h = detect_regions_over_time(video_path, start, duration)
    samples = smooth_states(samples)
    samples = smooth_positions(samples)
    opening_end = start + 3.0  # the hook needs to open on the main subject regardless of what got detected there
    plan = _build_crop_plan(samples, clip_start=start, clip_end=start + duration, opening_end=opening_end)
    print(
        f"Reframe plan for {Path(out_path).name}: "
        + ", ".join(f"{st}[{s - start:.1f}-{e - start:.1f}]" for s, e, st in plan)
    )

    main_track = PositionTrack(samples, "main_x", frame_w, DEFAULT_MAIN_FRAC)
    host_track = PositionTrack(samples, "host_x", frame_w, DEFAULT_HOST_FRAC)

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

    filter_complex, vlabel, alabel = _build_filter_complex(plan, main_track, host_track, frame_w, frame_h, ass_filter_path)
    # Normalise to the -14 LUFS the platforms play at (YouTube turns loud videos
    # down but never turns quiet ones up; raw call audio lands around -19 to -21).
    filter_complex += f";{alabel}loudnorm=I=-14:TP=-1.5:LRA=11[anorm]"
    alabel = "[anorm]"
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-filter_complex", filter_complex,
        "-map", vlabel, "-map", alabel,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k", "-ar", "48000",  # loudnorm upsamples to 192kHz internally
        out_path,
    ]
    subprocess.run(cmd, check=True)
    # Sidecar with the exact inputs, so any version can be re-rendered in one command
    # (python render_short.py --video V --start S --duration D --transcript T --out NEW).
    Path(out_path).with_suffix(".render.json").write_text(json.dumps({
        "video": video_path, "start": start, "duration": duration, "transcript": transcript_path,
    }, indent=1), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Render one finished short with dynamic reframing and burned-in captions.")
    parser.add_argument("--video", required=True)
    parser.add_argument("--start", type=float, required=True)
    parser.add_argument("--duration", type=float, default=30.0)
    parser.add_argument("--transcript", required=True)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    render(args.video, args.start, args.duration, args.transcript, args.out)
    print(f"Wrote {args.out}")


if __name__ == "__main__":
    main()
