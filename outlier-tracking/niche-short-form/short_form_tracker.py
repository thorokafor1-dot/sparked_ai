"""Thresholds and scoring for the Niche Specific Short Form Outliers output
(outlier-tracking/niche-short-form/data.json). Imported by outlier-tracking/youtube_outliers.py,
which does the actual YouTube scan shared with niche-long-form/long_form_tracker.py
(one scan, both formats scored here).
"""
import os
from typing import List

SHORTS_LOOKBACK_DAYS = int(os.getenv("SHORTS_LOOKBACK_DAYS", "90"))
# Absolute view count that alone qualifies a short as an outlier.
SHORTS_HIGH_VIEW_THRESHOLD = int(os.getenv("SHORTS_HIGH_VIEW_THRESHOLD", "300000"))
# Minimum views before the ratio-based signals below are allowed to trigger, so a video
# published hours ago with a handful of views can't produce an artificially huge ratio.
SHORTS_MIN_VIEW_THRESHOLD = int(os.getenv("SHORTS_MIN_VIEW_THRESHOLD", "50000"))
# Views per day since publish that alone qualifies a short as an outlier (catches a
# recent viral spike even before it clears the absolute view floor).
SHORTS_VELOCITY_THRESHOLD = float(os.getenv("SHORTS_VELOCITY_THRESHOLD", "15000"))
# How many times a channel's own average views a short must clear to be an outlier.
SHORTS_AVERAGE_MULTIPLIER_THRESHOLD = float(os.getenv("SHORTS_AVERAGE_MULTIPLIER_THRESHOLD", "10"))
# How many times a channel's subscriber count a short's views must clear.
SHORTS_SUBSCRIBER_MULTIPLIER_THRESHOLD = float(os.getenv("SHORTS_SUBSCRIBER_MULTIPLIER_THRESHOLD", "5"))
# Minimum subscribers before the views-vs-subscribers signal applies, so new/tiny
# channels don't produce inflated ratios from a near-zero denominator.
MIN_SUBSCRIBER_THRESHOLD = int(os.getenv("MIN_SUBSCRIBER_THRESHOLD", "100"))
# Separate, more generous per-channel cap for Shorts — the shorts tab needs more volume
# than long-form, and a handful of prolific creators shouldn't crowd it out at the same
# tight cap used for long-form videos.
SHORTS_PER_CHANNEL_CAP = int(os.getenv("SHORTS_PER_CHANNEL_CAP", "5"))


def is_outlier_short(view_count: int, days_since_published: float, subscriber_count: int = 0,
                      channel_total_views: int = 0, channel_video_count: int = 0) -> tuple[bool, str, float]:
    """Score a short against four independent signals and return the strongest one.

    Mirrors the long-form design: any one signal qualifies. Velocity catches a recent
    spike even before the absolute floor; the channel-average and subscriber signals
    reuse the long-form logic but with higher bars, since Shorts naturally get more
    algorithmic reach than a channel's typical video.
    """
    candidates: List[tuple[float, str]] = []
    days_since_published = max(days_since_published, 1.0)

    # Signal 1: absolute view floor.
    if view_count >= SHORTS_HIGH_VIEW_THRESHOLD:
        candidates.append((view_count / SHORTS_HIGH_VIEW_THRESHOLD, f"Over {SHORTS_HIGH_VIEW_THRESHOLD:,} views"))

    # Signal 2: view velocity — catches a recent spike even before the absolute floor.
    if view_count >= SHORTS_MIN_VIEW_THRESHOLD:
        velocity = view_count / days_since_published
        if velocity >= SHORTS_VELOCITY_THRESHOLD:
            candidates.append((velocity / SHORTS_VELOCITY_THRESHOLD, f"{velocity:,.0f} views/day"))

    # Signal 3: views vs. this channel's own average views per video.
    if view_count >= SHORTS_MIN_VIEW_THRESHOLD and channel_video_count > 0 and channel_total_views > 0:
        avg_views = channel_total_views / channel_video_count
        if avg_views > 0:
            multiplier = view_count / avg_views
            if multiplier >= SHORTS_AVERAGE_MULTIPLIER_THRESHOLD:
                candidates.append((multiplier, f"{multiplier:.1f}x channel average views"))

    # Signal 4: views vs. subscriber count — reached far beyond the existing audience.
    if view_count >= SHORTS_MIN_VIEW_THRESHOLD and subscriber_count >= MIN_SUBSCRIBER_THRESHOLD:
        sub_multiplier = view_count / subscriber_count
        if sub_multiplier >= SHORTS_SUBSCRIBER_MULTIPLIER_THRESHOLD:
            candidates.append((sub_multiplier, f"{sub_multiplier:.1f}x subscriber count in views"))

    if not candidates:
        return False, "", 0.0

    score, reason = max(candidates, key=lambda c: c[0])
    return True, reason, round(score, 2)
