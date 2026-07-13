"""One-off export: dumps all rows from every tracker tab (Outliers, Shorts Outliers,
General Outlier Models, General Shorts Outliers) as JSON to stdout, so a dashboard can be
built from real current data. Not part of the scheduled pipeline — run manually via its
GitHub Actions workflow.
"""
import json

from youtube_outliers import GOOGLE_SPREADSHEET_ID, GOOGLE_SHEET_NAME, GOOGLE_SHORTS_SHEET_NAME, build_google_sheets_client
from general_outlier_swipe_file import SHEET_NAME as GENERAL_SHEET_NAME
from general_shorts_swipe_file import SHEET_NAME as GENERAL_SHORTS_SHEET_NAME

TABS = [GOOGLE_SHEET_NAME, GOOGLE_SHORTS_SHEET_NAME, GENERAL_SHEET_NAME, GENERAL_SHORTS_SHEET_NAME]


def main() -> None:
    client = build_google_sheets_client()
    if not client:
        print("No Google Sheets client available.")
        return

    spreadsheet = client.open_by_key(GOOGLE_SPREADSHEET_ID) if GOOGLE_SPREADSHEET_ID else client.create("YouTube Outlier Tracker")

    export = {}
    for tab_name in TABS:
        try:
            worksheet = spreadsheet.worksheet(tab_name)
        except Exception as exc:
            print(f"Skipping '{tab_name}': {exc}")
            continue
        export[tab_name] = worksheet.get_all_values()

    print("EXPORT_START")
    print(json.dumps(export))
    print("EXPORT_END")


if __name__ == "__main__":
    main()
