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

A face large enough to be a full-screen close-up (not just someone sitting
in their normal pane) is detected first, unrestricted by the pane split, and
takes priority -- otherwise a genuine full-screen shot would get its face
cropped from one pane and the empty rest of the frame from the other,
bleeding one person's background into what should be the other person's
half.

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

import cv2

FACE_CASCADE = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")

MAIN_FRAC = 0.72  # fraction of frame width that is the main-subject pane; the rest is the host pane


@dataclass
class Sample:
    t: float
    state: str
    main_x: float | None
    host_x: float | None


def _largest_face_center_x(faces) -> float | None:
    if len(faces) == 0:
        return None
    x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
    return x + w / 2


def detect_regions_over_time(
    video_path: str, start: float, duration: float, main_frac: float = MAIN_FRAC, sample_interval: float = 0.5
) -> tuple[list[Sample], int, int]:
    """Returns (samples, frame_width, frame_height)."""
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
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

        # The app sometimes puts one person full-screen (spanning both nominal
        # panes, not confined to the 72/28 split) rather than showing the
        # persistent two-pane layout -- an unrestricted full-frame pass catches
        # this: a face this large (close, filling much of the screen) can only
        # be a full-screen solo shot, never a normal pane-constrained one, so
        # it takes priority over the pane-based checks below and is never
        # composited as a stacked split (which would otherwise crop half of it
        # from one pane and half from the wrong side of the other).
        full_faces = FACE_CASCADE.detectMultiScale(gray, 1.2, 9, minSize=(150, 150))
        big_face = max(full_faces, key=lambda f: f[2] * f[3]) if len(full_faces) else None
        # A histogram check used to gate this on "does it also look like the
        # call layout" (to route genuine cutaways/reaction inserts full-frame
        # instead of cropped). Dropped it: the correlation was unstable
        # frame-to-frame even for the exact same real shot, repeatedly
        # misrouting real footage of her/him to the full-frame fallback
        # (visible as an unzoomed, pillarboxed shot with black bars). A
        # confidently-detected face is trusted outright now -- the tradeoff
        # is a rare genuine cutaway also gets a face-crop instead of shown
        # full-frame, which is a smaller problem than misjudging real content.
        if big_face is not None and big_face[2] > frame_w * 0.15:
            fx, fy, fw, fh = big_face
            center = fx + fw / 2
            if center < split_x:
                state, main_x, host_x = "main", center, None
            else:
                state, main_x, host_x = "host", None, center
            samples.append(Sample(t, state, main_x, host_x))
            t += sample_interval
            continue

        main_gray = gray[:, :split_x]
        main_faces = FACE_CASCADE.detectMultiScale(main_gray, 1.2, 7, minSize=(50, 50))
        main_x = _largest_face_center_x(main_faces)

        # The host pane is much narrower, so faces in it are smaller -- Haar
        # cascades miss small faces more often. Upscale just that strip 2x
        # before detecting, mapping the result back to source pixel coords.
        # minNeighbors is kept strict (not loosened) -- a looser threshold
        # caught more real small faces but also false-positived on the
        # textured poster/wall behind him, producing crops centered on
        # nothing. Better to occasionally miss a real small face (falls back
        # to a full-frame shot) than confidently crop into empty background.
        # Search starts earlier than the nominal split (overlapping the main
        # search) since the app resizes the panes over time -- his pane can
        # extend well past the 72% mark, and a search that only looked right
        # of the nominal boundary would miss him whenever it has.
        host_search_x = int(frame_w * 0.55)
        host_gray = gray[:, host_search_x:]
        host_gray_up = cv2.resize(host_gray, None, fx=2.0, fy=2.0, interpolation=cv2.INTER_LINEAR)
        host_faces_up = FACE_CASCADE.detectMultiScale(host_gray_up, 1.1, 8, minSize=(70, 70))
        host_x = _largest_face_center_x(host_faces_up)
        if host_x is not None:
            host_x = host_search_x + host_x / 2.0

        if main_x is not None and host_x is not None:
            state = "split"
        elif main_x is not None:
            state = "main"
        elif host_x is not None:
            state = "host"
        else:
            # Neither face was confidently detected this instant, and no
            # full-screen face either. This is a continuous two-person call
            # recording, not disjoint clips, so this almost always still
            # means both people are on screen, just not confidently matched --
            # default to the stacked composite (using held/default positions)
            # rather than a raw full-frame letterbox, which would show both
            # panes tiny and side-by-side -- exactly the flat, non-vertical
            # look this whole reframe exists to avoid.
            state = "split"
        samples.append(Sample(t, state, main_x, host_x))
        t += sample_interval
    cap.release()
    return samples, frame_w, frame_h


def smooth_states(samples: list[Sample], radius: int = 2) -> list[Sample]:
    """Majority-vote over a +/-radius window, so a single spurious detection
    (or a single spurious miss) can't flip the state on its own -- it needs
    several consecutive samples to agree. main_x/host_x are left untouched;
    those are independent per-instant measurements consumed separately by
    PositionTrack, not by state classification."""
    states = [s.state for s in samples]
    smoothed = []
    for i, s in enumerate(samples):
        window = states[max(0, i - radius) : i + radius + 1]
        majority = max(set(window), key=window.count)
        smoothed.append(Sample(s.t, majority, s.main_x, s.host_x))
    return smoothed


def smooth_positions(samples: list[Sample], radius: int = 3) -> list[Sample]:
    """Averages main_x/host_x over a +/-radius window of nearby real
    detections (gaps ignored, not zero-filled), separately from state
    smoothing. Raw per-instant face-detection coordinates wobble by a few
    pixels frame to frame even for someone sitting still -- cropping on that
    raw jitter directly reads as a shaky, jumpy edit. Smoothing first makes
    every crop position (and any cut built from these samples) track the
    person's actual movement, not detector noise."""

    def _avg_field(i: int, attr: str) -> float | None:
        window = [getattr(s, attr) for s in samples[max(0, i - radius) : i + radius + 1]]
        vals = [v for v in window if v is not None]
        return sum(vals) / len(vals) if vals else None

    smoothed = []
    for i, s in enumerate(samples):
        smoothed.append(Sample(s.t, s.state, _avg_field(i, "main_x"), _avg_field(i, "host_x")))
    return smoothed


class PositionTrack:
    """A continuous face-x lookup built from sparse samples: a momentary
    detection miss holds the nearest real detection in time (forward or
    backward) instead of falling back to a blind static guess. Only used
    when nothing was ever detected anywhere in the whole clip."""

    def __init__(self, samples: list[Sample], attr: str, frame_w: int, default_frac: float):
        raw = [(s.t, getattr(s, attr)) for s in samples]
        self._raw = raw  # kept as-is (with gaps) so .near() can tell a real detection from a held one
        filled = [x for _, x in raw]
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
        self._track = [(t, x if x is not None else default) for (t, _), x in zip(raw, filled)]

    def at(self, t: float) -> float:
        if not self._track:
            return 0.0
        best = self._track[0][1]
        for st, x in self._track:
            if st > t:
                break
            best = x
        return best

    def near(self, t: float, max_gap: float = 2.0) -> float | None:
        """Returns the position only if an actual detection (not a held or
        default value) exists within max_gap seconds of t -- used to avoid
        ever cropping on a position that's really just a stale guess."""
        best_x, best_dist = None, None
        for st, x in self._raw:
            if x is None:
                continue
            d = abs(st - t)
            if best_dist is None or d < best_dist:
                best_dist, best_x = d, x
        if best_dist is not None and best_dist <= max_gap:
            return best_x
        return None
