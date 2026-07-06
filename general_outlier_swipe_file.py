"""One-off writer for the "General Outlier Models" tab: a curated swipe file of viral
YouTube packaging (title + thumbnail psychology) from outside the cold-approach niche,
each translated into a cold-approach-ready title and thumbnail concept.

Entries here must be real, statistically verified outliers — 100x+ a channel's own
average views, published in the last 90 days — found by general_outlier_finder.py
(run via GitHub Actions, since computing that multiplier needs live channel stats from
the YouTube API). That script only surfaces candidates; picking which ones cleanly
translate into a cold-approach idea and writing the analysis below is a manual step.
This file is not a live API pull itself — run it manually whenever new entries are added.
"""
import os

import gspread

from youtube_outliers import GOOGLE_SPREADSHEET_ID, build_google_sheets_client

SHEET_NAME = os.getenv("GENERAL_OUTLIER_SHEET_NAME", "General Outlier Models")

HEADERS = [
    "Original Video Title",
    "Original Channel",
    "Video URL",
    "Original Niche",
    "Views",
    "Core Packaging Pattern",
    "Psychological Trigger",
    "Thumbnail Breakdown",
    "Title Formula",
    "Why It Worked",
    "Cold Approach Translation (Concept)",
    "Cold Approach Title",
    "Cold Approach Thumbnail Concept",
    "Notes",
    "Status",
]

SWIPE_FILE = [
    {
        "title": "Alone, Broke, Over 60… I Sold Everything to Start Over (My Real Story)",
        "channel": "Offended Outcast",
        "url": "https://www.youtube.com/watch?v=RndUKvYAhHs",
        "niche": "Personal Reinvention/Redemption Documentary (Vlog)",
        "views": "3,005,620 (channel averages ~26,046/video — a verified 115.4x outlier, published 2026-04-11, within the last 90 days)",
        "pattern": "A raw, unstyled \"diary\" visual (a plain selfie shot, zero graphics/text) paired with a title that does 100% of the emotional heavy lifting — the plainness of the image itself signals \"this is real, not produced,\" building trust and curiosity at once.",
        "trigger": "Vulnerability/empathy (a man exposing failure at a life stage where reinvention feels impossible) + authenticity signal (unpolished visual = \"this can't be staged\") + a stacked-adjective vulnerability hit (\"alone,\" \"broke,\" \"over 60\" — each independently painful, devastating together).",
        "thumbnail": "A plain, close-cropped selfie-style shot of a man in his 60s (ballcap, glasses, plaid flannel shirt) standing alone on a rural dirt road surrounded by forest, looking directly into the camera with a tired, resigned expression, natural overcast daylight, muted green/earth tones, zero text overlay, zero graphic design — the total absence of typical thumbnail polish is itself the authenticity signal.",
        "formula": "[Stacked vulnerable adjectives, comma-separated] + [age/life-stage marker] + \"… I \" + [drastic action taken] + \" (My Real Story)\"",
        "why": "Each word in the opening stack (\"Alone,\" \"Broke,\" \"Over 60\") is independently a strong emotional hook, and stacking three compounds the stakes before the sentence even finishes; \"My Real Story\" explicitly promises non-fiction, and the deliberately unpolished thumbnail backs that promise visually instead of contradicting it with slick production.",
        "translation": "Reframe the \"stacked vulnerable stats + drastic action + authenticity\" mechanic around social isolation instead of financial/life-stage failure — the same raw, unproduced visual style, the same title structure staking out real, specific vulnerability before revealing the turnaround.",
        "ca_title": "Shy, Friendless, 30 Years Old… I Walked Up To A Stranger To Change My Life (My Real Story)",
        "ca_thumbnail": "Plain, close-cropped selfie-style shot of the creator alone on an ordinary sidewalk or park path, looking directly into the camera with a tired, vulnerable expression (not smiling, not performing), natural daylight, muted/neutral colors, zero text overlay and zero graphic polish — the visual should look like a real diary entry, not a produced thumbnail, so the plainness itself signals honesty.",
        "notes": "Verified via general_outlier_finder.py: 115.4x the channel's own average views, published 2026-04-11 (within the 90-day window). A fundamentally different packaging style than flashy/high-production examples — no graphic design needed, low cost to produce, relies entirely on emotional authenticity. Worth testing as a low-effort, high-frequency format.",
        "status": "Not Adapted",
    },
]


def main() -> None:
    client = build_google_sheets_client()
    if not client:
        print("No Google Sheets output was created.")
        return

    if GOOGLE_SPREADSHEET_ID:
        spreadsheet = client.open_by_key(GOOGLE_SPREADSHEET_ID)
    else:
        spreadsheet = client.create("YouTube Outlier Tracker")

    try:
        worksheet = spreadsheet.worksheet(SHEET_NAME)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = spreadsheet.add_worksheet(title=SHEET_NAME, rows=100, cols=20)

    worksheet.clear()
    worksheet.append_row(HEADERS)

    values = [
        [
            row["title"], row["channel"], row["url"], row["niche"], row["views"],
            row["pattern"], row["trigger"], row["thumbnail"], row["formula"], row["why"],
            row["translation"], row["ca_title"], row["ca_thumbnail"], row["notes"], row["status"],
        ]
        for row in SWIPE_FILE
    ]
    worksheet.append_rows(values, value_input_option="USER_ENTERED")
    worksheet.set_basic_filter()

    print(f"Wrote {len(SWIPE_FILE)} swipe file entries to {spreadsheet.url} ({SHEET_NAME})")


if __name__ == "__main__":
    main()
