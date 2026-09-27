"""Dynamic reframing: the source is a landscape 1920x1080 call recording that
normally shows a persistent two-pane layout (main subject's tile on the
left, a smaller host tile on the right) but sometimes switches to one
person full-screen instead. Copying the reference short's behavior means
switching composition over time instead of one static crop:
  - "main"  -- only the left pane has a face (or a full-screen face centers
    left of the pane boundary) -> crop tight to it, fill 9:16
  - "host"  -- same, but on the right -> crop tight to it, fill 9:16
  - "split" -- both panes have a face at once -> stack host on top, main on
    bottom (matches the reference's two-up shots)
  - "none"  -- kept as a last-resort fallback (full source frame, no
    face-bias) but not reachable from real detections anymore -- an earlier
    version routed a confident big face through a color-histogram check
    first, meant to catch genuine cutaways/reaction inserts and show them
    full-frame instead of cropped. Dropped it: the correlation swung enough
    frame-to-frame that it misrouted real footage of her/him to that
    fallback too, which is worse than the cutaway case it was meant to
    handle. A confidently-detected face is trusted outright now.

Some stretches of the source are reaction-insert cutaways spliced in (e.g. a
clip of an audience applauding, or an unrelated podcast clip) rather than
the actual call footage -- not disjoint files, just spliced into the same
recording. Trusting a confident face detection outright (see "none" above)
let these slip through as a fabricated "split" (two strangers from an
insert, at plausible main/host x-positions, stacked as if they were the two
call participants) or a solo crop on a random third person entirely -- both
seen in this source. Two checks run before any face search, on whichever of
these two measured signals a given cutaway happens to trip:
  - a dark top margin (letterboxing from the original clip) -- the call's
    top few percent of frame is always the wall/ceiling behind whoever's on
    camera, consistently bright (>100 mean gray); a checked cutaway (movie
    audience shot) measured 9-13.
  - oversaturated color -- the call's lighting is consistently neutral
    (grey walls, skin tones), measured 54-73 mean saturation across a wide
    spread of samples; a checked cutaway (a podcast clip on a red/purple
    graffiti set) measured 145-147.
Either match routes straight to "none" (full source frame, letterboxed, no
face-bias) -- the right call for content that was never part of the
two-pane layout to begin with, not a pane-tracking problem. This is
specific to what's actually been seen in this source, not a general
cutaway classifier -- unlike the color-histogram check mentioned above
(dropped for measuring unstable frame-to-frame, even on the same real
shot), each of these is a single scalar compared against one fixed
threshold, not a correlation against a reference frame, but a cutaway
matching neither signal would still slip through.

A full-screen close-up (not just someone sitting in their normal pane) is
recognized by running BOTH the main- and host-restricted searches on every
sample and checking how far apart their results land, not by face size --
size was tried first and rejected: a wide-but-still-two-pane shot can
detect a larger face than a genuine full-screen one, since size only tracks
camera zoom, not whether a second pane exists. The two search regions
deliberately overlap (main ends at 72%, host starts at 55%) so a pane that
resizes past the nominal boundary still gets caught -- but that same
overlap means one real face straddling it gets picked up by both searches
at once. A genuine two-person moment has always measured a large gap
between the two results (roughly 850-1250px, seen repeatedly across this
clip); the same-face-caught-twice case measured 116-156px -- a wide,
unambiguous gap between the two clusters. Below ~350px it's one face
straddling the search boundary (full-screen, or close enough to it that
there's no real adjacent content to bleed into); at or above it, it's two
different people.

Face detection uses YuNet (cv2.FaceDetectorYN), not a Haar cascade. Haar was
the original choice and worked most of the time, but it confidently
false-positived on a specific piece of wall art in his room (a framed lion
poster) during a stretch where he was genuinely off-camera -- the crop
locked onto the poster and produced a shot with no one in it. Before
swapping detectors, five different ways of rejecting that one false
positive from the raw Haar output were tried and measured directly against
it: capping detected face size, requiring a sub-detected eye pair, checking
skin-color fraction inside the box, checking position stability across
frames, and reading the cascade's own confidence weight. All five gave the
poster and a genuine face statistically indistinguishable scores -- it's an
unusually face-like image by every one of those signals, so no amount of
threshold-tuning on that classifier was going to fix it. Actually measuring
YuNet frame-by-frame across the same stretch showed a clean signal instead:
confident real-face detections on either side of a sharp ~3.5s gap that
correctly reports no face at all during it, which is what let the
none/stale-position fallback logic downstream (see PositionTrack.near)
finally do its job instead of being fed a confident wrong answer. Needs
models/face_detection_yunet.onnx alongside this file (small, gitignored
like thumbnail-creation/models/ -- fetch it from the opencv_zoo GitHub repo,
models/face_detection_yunet/face_detection_yunet_2023mar.onnx, if missing).

Face position is sampled with OpenCV every sample_interval seconds and
majority-vote smoothed so a single spurious detection (or a single spurious
miss) can't flip the state on its own. render_short.py then sub-chunks the
clip at a matching interval and looks up each chunk's own state directly
from these samples -- deliberately not merged into multi-second segments,
since that washed out fast transitions (e.g. a ~1s zoom into full-screen)
into one wrong, frozen crop for the whole span. Each pane's x-position is
tracked continuously across the whole clip too: a momentary miss holds the
nearest real detection in time rather than falling back to a blind static
guess, so the crop follows wherever she actually is.
"""
from dataclasses import dataclass
from pathlib import Path

import cv2

FACE_MODEL_PATH = str(Path(__file__).parent / "models" / "face_detection_yunet.onnx")
_detector: cv2.FaceDetectorYN | None = None


def _get_detector() -> cv2.FaceDetectorYN:
    global _detector
    if _detector is None:
        # input size is a placeholder -- set per call via setInputSize since
        # this same detector is reused on differently-sized regions (the
        # full frame, then the narrower main/host pane crops).
        _detector = cv2.FaceDetectorYN_create(FACE_MODEL_PATH, "", (320, 320), score_threshold=0.6)
    return _detector


def _best_face(detector: cv2.FaceDetectorYN, bgr_region):
    """Largest detected face in bgr_region as (x, y, w, h, score), or None.
    YuNet takes BGR directly (no grayscale conversion, no manual upscaling
    of narrow regions the way the old Haar cascade needed)."""
    h, w = bgr_region.shape[:2]
    if h == 0 or w == 0:
        return None
    detector.setInputSize((w, h))
    _, faces = detector.detect(bgr_region)
    if faces is None or len(faces) == 0:
        return None
    best = max(faces, key=lambda f: f[2] * f[3])
    return best[0], best[1], best[2], best[3], best[-1]


MAIN_FRAC = 0.72  # fraction of frame width that is the main-subject pane; the rest is the host pane
CUTAWAY_TOP_BAR_FRAC = 0.06  # top strip checked for cutaway letterboxing (see module docstring)
CUTAWAY_TOP_BAR_MAX_MEAN = 40  # real call footage measured 104-130 here; a checked cutaway measured 9-13
CUTAWAY_SAT_MIN_MEAN = 100  # real call footage measured 54-73 here; a checked cutaway measured 145-147


def _looks_like_cutaway(frame) -> bool:
    bar_h = int(frame.shape[0] * CUTAWAY_TOP_BAR_FRAC)
    top_mean = cv2.cvtColor(frame[:bar_h, :], cv2.COLOR_BGR2GRAY).mean()
    if top_mean < CUTAWAY_TOP_BAR_MAX_MEAN:
        return True
    sat_mean = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)[:, :, 1].mean()
    return sat_mean > CUTAWAY_SAT_MIN_MEAN


@dataclass
class Sample:
    t: float
    state: str
    main_x: float | None
    host_x: float | None
    # True when the OTHER side's search found nothing real to bleed into at
    # this sample -- either because it's a genuine full-screen shot (no
    # adjacent pane at all) or because the search caught the same face
    # straddling both regions (see module docstring) and collapsed to one
    # side. Either way there's no real content on the other side right now,
    # so render_short.py can safely skip the pane-edge clamps
    # (MAIN_MAX_X_FRAC/HOST_MIN_X_FRAC) meant to stop a crop from reaching
    # into a narrow pane that actually has someone in it. Confirmed by
    # inspecting the actual source frame at a "main"-state timestamp that
    # was getting clamped: it was a full-screen close-up, not a narrow pane,
    # so the clamp was dragging the crop away from his face for no real
    # bleed risk.
    full_screen: bool = False


def detect_regions_over_time(
    video_path: str, start: float, duration: float, main_frac: float = MAIN_FRAC, sample_interval: float = 0.2
) -> tuple[list[Sample], int, int]:
    """Returns (samples, frame_width, frame_height). sample_interval was
    0.5s originally; tightened to 0.2s after confirming (directly against
    the source) that this call's layout can flip between a full-screen
    shot of one person and a full-screen shot of the other inside a single
    0.5s gap -- a chunk straddling that gap with only one raw sample inside
    it had nothing to compare against, so render_short.py's adaptive
    chunk-splitting (which relies on spotting a spread between nearby
    samples) couldn't see the instability was there at all. Denser
    sampling is what actually closes that gap; a smarter split of already
    too-sparse data can't invent information that was never captured."""
    detector = _get_detector()
    cap = cv2.VideoCapture(video_path)
    frame_w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    split_x = int(frame_w * main_frac)

    samples: list[Sample] = []
    t = start
    while t < start + duration:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if not ok:
            t += sample_interval
            continue

        if _looks_like_cutaway(frame):
            samples.append(Sample(t, "none", None, None))
            t += sample_interval
            continue

        main_bgr = frame[:, :split_x]
        main_face = _best_face(detector, main_bgr)
        main_x = (main_face[0] + main_face[2] / 2) if main_face is not None else None

        # Search starts earlier than the nominal split (overlapping the main
        # search) since the app resizes the panes over time -- his pane can
        # extend well past the 72% mark, and a search that only looked right
        # of the nominal boundary would miss him whenever it has.
        host_search_x = int(frame_w * 0.55)
        host_bgr = frame[:, host_search_x:]
        host_face = _best_face(detector, host_bgr)
        host_x = (host_search_x + host_face[0] + host_face[2] / 2) if host_face is not None else None

        # Both searches finding a result doesn't necessarily mean two people
        # -- see module docstring. A small gap between them means it's the
        # same face caught by both overlapping regions (a full-screen or
        # near-full-screen shot); collapse to whichever side its midpoint
        # falls on rather than reporting a false "split".
        same_face_gap = 350
        if main_x is not None and host_x is not None and abs(main_x - host_x) < same_face_gap:
            center = (main_x + host_x) / 2
            if center < split_x:
                state, main_x, host_x = "main", center, None
            else:
                state, main_x, host_x = "host", None, center
            samples.append(Sample(t, state, main_x, host_x, full_screen=True))
            t += sample_interval
            continue

        if main_x is not None and host_x is not None:
            state = "split"
        elif main_x is not None:
            state = "main"
        elif host_x is not None:
            state = "host"
        else:
            # Neither face was confidently detected this instant. This is a
            # continuous two-person call recording, not disjoint clips, so
            # this almost always still means both people are on screen, just
            # not confidently matched -- default to the stacked composite
            # (using held/default positions) rather than a raw full-frame
            # letterbox, which would show both panes tiny and side-by-side --
            # exactly the flat, non-vertical look this whole reframe exists
            # to avoid.
            state = "split"
        # See Sample.full_screen: true whenever the other side found nothing
        # real to bleed into right now (solo state only -- "split"/"none"
        # never skip the clamp, they don't use it).
        full_screen = (state == "main" and host_x is None) or (state == "host" and main_x is None)
        samples.append(Sample(t, state, main_x, host_x, full_screen))
        t += sample_interval
    cap.release()
    return samples, frame_w, frame_h


def smooth_states(samples: list[Sample], radius: int = 5) -> list[Sample]:
    """Majority-vote over a +/-radius window, so a single spurious detection
    (or a single spurious miss) can't flip the state on its own -- it needs
    several consecutive samples to agree. main_x/host_x are left untouched;
    those are independent per-instant measurements consumed separately by
    PositionTrack, not by state classification. radius is in samples, not
    seconds -- 5 keeps the same ~1s window as the original radius=2 did
    when sample_interval was 0.5s (now 0.2s)."""
    states = [s.state for s in samples]
    full_screens = [s.full_screen for s in samples]
    smoothed = []
    for i, s in enumerate(samples):
        window = states[max(0, i - radius) : i + radius + 1]
        # sorted(), not set(): a tied vote (e.g. 2-2 right at a scene cut)
        # otherwise breaks on set-iteration order, which Python randomizes
        # per process for strings -- the exact same clip could render a
        # different state at a tied sample from one run to the next.
        majority = max(sorted(set(window)), key=window.count)
        # full_screen needs the same majority-vote treatment as state: the
        # big-face pass is a single Haar cascade call per sample and misses
        # a frame here and there even mid-shot (seen: three full-screen
        # samples in a row, one spurious miss, then two more full-screen --
        # same shot throughout). .near() in render_short.py picks whichever
        # raw sample is literally closest in time, so a single missed frame
        # landing right at that lookup silently threw away the full_screen
        # fix. Majority vote makes one spurious miss (or hit) not flip it.
        fs_window = full_screens[max(0, i - radius) : i + radius + 1]
        majority_fs = sum(fs_window) > len(fs_window) / 2
        smoothed.append(Sample(s.t, majority, s.main_x, s.host_x, majority_fs))
    return smoothed


def smooth_positions(samples: list[Sample], radius: int = 7) -> list[Sample]:
    """Averages main_x/host_x over a +/-radius window of nearby real
    detections (gaps ignored, not zero-filled), separately from state
    smoothing. Raw per-instant face-detection coordinates wobble by a few
    pixels frame to frame even for someone sitting still -- cropping on that
    raw jitter directly reads as a shaky, jumpy edit. radius is in samples,
    not seconds -- 7 keeps roughly the same ~1.5s window as the original
    radius=3 did when sample_interval was 0.5s (now 0.2s). Smoothing first makes
    every crop position (and any cut built from these samples) track the
    person's actual movement, not detector noise."""

    def _avg_field(i: int, attr: str) -> float | None:
        window = [getattr(s, attr) for s in samples[max(0, i - radius) : i + radius + 1]]
        vals = [v for v in window if v is not None]
        if not vals:
            return None
        # A plain average blends across a genuine scene change inside the
        # window (e.g. a "split" sample's main_x -- her position in a
        # two-pane layout -- averaged with the next sample's "main" main_x
        # once it cuts to his full-screen close-up) into a physically
        # meaningless midpoint that matches neither person -- confirmed
        # directly: this produced a crop centered between her split
        # position and his full-screen position, landing on a poster edge
        # neither of them was ever near. Anchor to this sample's own raw
        # value (the most trustworthy reading for "right now") when it has
        # one, else the window's median, and only average window values
        # actually close to that anchor -- jitter smooths as before, a
        # same-window scene change no longer drags the average toward a
        # position that belonged to a different person or layout entirely.
        own = getattr(samples[i], attr)
        anchor = own if own is not None else sorted(vals)[len(vals) // 2]
        max_jump = 300
        close = [v for v in vals if abs(v - anchor) <= max_jump]
        return sum(close) / len(close) if close else anchor

    smoothed = []
    for i, s in enumerate(samples):
        smoothed.append(Sample(s.t, s.state, _avg_field(i, "main_x"), _avg_field(i, "host_x"), s.full_screen))
    return smoothed


class PositionTrack:
    """A continuous face-x lookup built from sparse samples: a momentary
    detection miss holds the nearest real detection in time (forward or
    backward) instead of falling back to a blind static guess. Only used
    when nothing was ever detected anywhere in the whole clip."""

    def __init__(self, samples: list[Sample], attr: str, frame_w: int, default_frac: float):
        raw = [(s.t, getattr(s, attr), s.full_screen) for s in samples]
        self._raw = raw  # kept as-is (with gaps) so .near() can tell a real detection from a held one
        filled = [x for _, x, _ in raw]
        last = None
        for i in range(len(filled)):
            if filled[i] is not None:
                last = filled[i]
            elif last is not None:
                filled[i] = last
        nxt = None
        for i in range(len(filled) - 1, -1, -1):
            if filled[i] is not None:
                nxt = filled[i]
            elif nxt is not None:
                filled[i] = nxt
        default = frame_w * default_frac
        self._track = [(t, x if x is not None else default) for (t, _, _), x in zip(raw, filled)]

    def at(self, t: float) -> float:
        # Epsilon absorbs float drift in the sample timestamps (each is
        # built by repeatedly adding sample_interval, so the stored value
        # for "129.8" can actually be 129.80000000000024) -- see
        # render_short._state_at, which had the identical bug: querying
        # with a clean value read the drifted sample as "in the future"
        # and silently fell back to the previous, stale one.
        if not self._track:
            return 0.0
        best = self._track[0][1]
        for st, x in self._track:
            if st > t + 1e-6:
                break
            best = x
        return best

    def near(self, t: float, max_gap: float = 2.0) -> tuple[float, bool] | None:
        """Returns (position, full_screen) only if an actual detection (not
        a held or default value) exists within max_gap seconds of t -- used
        to avoid ever cropping on a position that's really just a stale
        guess. The full_screen flag lets a caller skip pane-edge clamps that
        only make sense for a genuine pane-restricted detection."""
        best_x, best_fs, best_dist = None, None, None
        for st, x, fs in self._raw:
            if x is None:
                continue
            d = abs(st - t)
            if best_dist is None or d < best_dist:
                best_dist, best_x, best_fs = d, x, fs
        if best_dist is not None and best_dist <= max_gap:
            return best_x, best_fs
        return None
