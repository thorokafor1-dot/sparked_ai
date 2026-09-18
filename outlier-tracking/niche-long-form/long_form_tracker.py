"""Thresholds and scoring for the Niche Specific Long Form Outliers output
(outlier-tracking/niche-long-form/data.json). Imported by outlier-tracking/youtube_outliers.py,
which does the actual YouTube scan shared with niche-short-form/short_form_tracker.py
(one scan, both formats scored here).
"""
import os
from typing import List

# Absolute view count that alone qualifies a video as an outlier, regardless of channel size.
HIGH_VIEW_THRESHOLD = int(os.getenv("HIGH_VIEW_THRESHOLD", "30000"))
# Minimum views a video must have before the ratio-based signals below are allowed to
# trigger, so a video with a handful of views can't qualify just from a huge ratio.
MIN_VIEW_THRESHOLD = int(os.getenv("MIN_VIEW_THRESHOLD", "5000"))
# Minimum subscribers before the views-vs-subscribers signal applies, so new/tiny
# channels don't produce inflated ratios from a near-zero denominator.
MIN_SUBSCRIBER_THRESHOLD = int(os.getenv("MIN_SUBSCRIBER_THRESHOLD", "100"))
# How many times a channel's own average views a video must clear to be an outlier.
AVERAGE_MULTIPLIER_THRESHOLD = float(os.getenv("OUTLIER_MULTIPLIER_THRESHOLD", "8"))
# How many times a channel's subscriber count a video's views must clear — signals the
# video pulled in viewers well beyond the channel's existing audience.
SUBSCRIBER_MULTIPLIER_THRESHOLD = float(os.getenv("SUBSCRIBER_MULTIPLIER_THRESHOLD", "3"))
# Cap how many outliers from the same channel land in the sheet, to keep results diverse.
PER_CHANNEL_CAP = int(os.getenv("PER_CHANNEL_CAP", "3"))


def is_outlier(view_count: int, subscriber_count: int, channel_total_views: int = 0, channel_video_count: int = 0) -> tuple[bool, str, float]:
    """Score a video against three independent outlier signals and return the strongest one.

    Any single signal is enough to qualify: a raw view floor (catches big, on-topic hits
    regardless of channel size), views vs. the channel's own average (catches a channel's
    own breakout), and views vs. subscriber count (catches videos that pulled well beyond
    the channel's existing audience — the strongest signal a thumbnail/title did the work).
    """
    candidates: List[tuple[float, str]] = []

    # Signal 1: absolute view floor — always evaluated so every outlier gets a comparable score.
    if view_count >= HIGH_VIEW_THRESHOLD:
        candidates.append((view_count / HIGH_VIEW_THRESHOLD, f"Over {HIGH_VIEW_THRESHOLD:,} views"))

    # Signal 2: views vs. this channel's own average views per video.
    if view_count >= MIN_VIEW_THRESHOLD and channel_video_count > 0 and channel_total_views > 0:
        avg_views = channel_total_views / channel_video_count
        if avg_views > 0:
            multiplier = view_count / avg_views
            if multiplier >= AVERAGE_MULTIPLIER_THRESHOLD:
                candidates.append((multiplier, f"{multiplier:.1f}x channel average views"))

    # Signal 3: views vs. subscriber count — reached far beyond the existing audience.
    if view_count >= MIN_VIEW_THRESHOLD and subscriber_count >= MIN_SUBSCRIBER_THRESHOLD:
        sub_multiplier = view_count / subscriber_count
        if sub_multiplier >= SUBSCRIBER_MULTIPLIER_THRESHOLD:
            candidates.append((sub_multiplier, f"{sub_multiplier:.1f}x subscriber count in views"))

    if not candidates:
        return False, "", 0.0

    score, reason = max(candidates, key=lambda c: c[0])
    return True, reason, round(score, 2)
