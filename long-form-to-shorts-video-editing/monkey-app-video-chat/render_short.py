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

# The stacked-half crops get a narrower width still. Even a "confidently
# tracked" position can sit close to the (unknown, shifting) pane boundary
# -- fine for a solo shot (worst case: slightly off-center, still one
# texture), but in a stacked half it can visibly mix both people's
# backgrounds in one frame. Less margin for error, so less width.
SPLIT_FACE_CROP_W = 380

# Caption vertical position (ASS \pos y, measured from the top): lower-third
# for a solo shot, but pulled up to the seam between the two halves for a
# stacked two-person shot, so it never overlaps either face -- matches how
# the reference short repositions captions by layout, not a fixed spot.
SOLO_CAPTION_Y = 1620
SPLIT_CAPTION_Y = 1010


def _face_crop(
    face_x: float, target_w: int, target_h: int, frame_w: int, frame_h: int, crop_w: int = FACE_CROP_W, min_x_frac: float = 0.0
) -> str:
    """Crops a fixed-width close-up centered on face_x (clamped to stay
    within the frame), then scales/crops to the exact target size. Not
    bounded to any pane -- see FACE_CROP_W. min_x_frac hard-floors the crop's
    left edge (as a fraction of frame_w) regardless of face_x -- for a
    detection that's centered close enough to a narrow pane's edge that
    even a narrow width still reaches past it (seen with the host pane:
    a detection can be genuine and only ~15px from where his pane starts,
    so centering on it at all pulls a majority of the crop from before that
    edge no matter how narrow the width gets)."""
    crop_w = min(crop_w, frame_w)
    x = round(face_x - crop_w / 2)
    min_x = frame_w * min_x_frac
    x = int(max(min_x, max(0, min(x, frame_w - crop_w))))
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
    would wash out a fast transition like that into one wrong, frozen crop."""
    if not samples:
        return "none"
    best = samples[0]
    for s in samples:
        if s.t > t:
            break
        best = s
    return best.state


def _build_crop_plan(
    samples: list[Sample], clip_start: float, clip_end: float, opening_end: float, chunk: float = CROP_CHUNK
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
    plan = []
    t = clip_start
    while t < clip_end:
        end = min(t + chunk, clip_end)
        mid = (t + end) / 2
        state = "main" if mid < opening_end else _state_at(samples, mid)
        plan.append((t, end, state))
        t = end
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
        near_main = main_track.near(mid, max_gap=0.75)
        near_host = host_track.near(mid, max_gap=0.75)
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
        ref_main = near_main if near_main is not None else main_track.near(mid, max_gap=2.5)
        ref_host = near_host if near_host is not None else host_track.near(mid, max_gap=2.5)
        min_solo_separation = 400
        if near_main is not None and ref_host is not None and abs(near_main - ref_host) < min_solo_separation:
            near_main = None
        if near_host is not None and ref_main is not None and abs(near_host - ref_main) < min_solo_separation:
            near_host = None

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
                crop = _face_crop(near_main, SOLO_W, SOLO_H, frame_w, frame_h)
            else:
                crop = _face_crop(default_main_x, SOLO_W, SOLO_H, frame_w, frame_h, DEFAULT_FALLBACK_CROP_W)
            v_parts.append(f"[vraw{idx}]{crop}[v{idx}]")
        elif state == "host":
            host_x = near_host if near_host is not None else default_host_x
            crop = _face_crop(host_x, SOLO_W, SOLO_H, frame_w, frame_h, HOST_CROP_W, HOST_MIN_X_FRAC)
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
        t = clip_relative_t + start
        state = "main" if t < opening_end else _state_at(samples, t)
        return SPLIT_CAPTION_Y if state == "split" else SOLO_CAPTION_Y

    ass_path = WORK_DIR / f"{Path(out_path).stem}.ass"
    write_ass_file(clip_words, str(ass_path), y_at=y_at)
    ass_filter_path = str(ass_path).replace("\\", "/").replace(":", "\\:")

    filter_complex, vlabel, alabel = _build_filter_complex(plan, main_track, host_track, frame_w, frame_h, ass_filter_path)
    cmd = [
        "ffmpeg", "-y",
        "-i", video_path,
        "-filter_complex", filter_complex,
        "-map", vlabel, "-map", alabel,
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k",
        out_path,
    ]
    subprocess.run(cmd, check=True)


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
