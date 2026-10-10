"""Which of our videos get clicked? Thumbnail CTR ranking from the YouTube Reporting API.

The Analytics API doesn't serve impressions/CTR, so this uses the bulk Reporting API's
channel_reach_basic_a1 report (daily rows per video: thumbnail impressions + CTR). On first run
it creates the reporting job; YouTube then drops one daily report file roughly every 24h.
Every run downloads any new files into reports/reach_raw/ (cached, never re-downloaded),
aggregates all days on file, and ranks videos by impression-weighted CTR.

    python ctr.py                    # rank everything on file
    python ctr.py --min-impressions 500

Writes reports/ctr_<date>.md (read this) and reports/ctr_<date>.json.
Needs token.json from oauth_setup.py and the YouTube Reporting API enabled on the Cloud project.
"""
from __future__ import annotations

import argparse
import csv
import datetime as dt
import io
import json
from collections import defaultdict

from googleapiclient.discovery import build

from retention import REPORTS, list_videos, services

REPORT_TYPE = "channel_reach_basic_a1"
JOB_NAME = "sparked-ctr"
RAW = REPORTS / "reach_raw"


def ensure_job(yr) -> str:
    for j in yr.jobs().list().execute().get("jobs", []):
        if j["reportTypeId"] == REPORT_TYPE:
            return j["id"]
    job = yr.jobs().create(body={"reportTypeId": REPORT_TYPE, "name": JOB_NAME}).execute()
    print(f"Created reporting job {job['id']}. First data arrives in ~24-48h.")
    return job["id"]


def sync_reports(yr, job_id: str) -> int:
    RAW.mkdir(parents=True, exist_ok=True)
    new, req = 0, yr.jobs().reports().list(jobId=job_id)
    while req:
        resp = req.execute()
        for r in resp.get("reports", []):
            # one file per data day; a later regenerated file for the same day replaces the older one
            path = RAW / f"{r['startTime'][:10]}.csv"
            stamp = RAW / f"{r['startTime'][:10]}.created"
            if path.exists() and stamp.exists() and stamp.read_text() >= r["createTime"]:
                continue
            content = yr._http.request(r["downloadUrl"])[1]
            path.write_bytes(content)
            stamp.write_text(r["createTime"])
            new += 1
        req = yr.jobs().reports().list_next(req, resp)
    return new


def aggregate(min_impr: int) -> tuple[dict, list[str]]:
    totals = defaultdict(lambda: [0, 0.0])  # video -> [impressions, clicks]
    days = sorted(p.stem for p in RAW.glob("*.csv"))
    for day in days:
        for row in csv.DictReader(io.StringIO((RAW / f"{day}.csv").read_text(encoding="utf-8"))):
            n = int(row["video_thumbnail_impressions"] or 0)
            totals[row["video_id"]][0] += n
            totals[row["video_id"]][1] += n * float(row["video_thumbnail_impressions_ctr"] or 0)
    return {v: t for v, t in totals.items() if t[0] >= min_impr}, days


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--min-impressions", type=int, default=100, help="Hide videos below this (CTR on tiny samples is noise)")
    args = parser.parse_args()

    yt, yta = services()
    yr = build("youtubereporting", "v1", credentials=yta._http.credentials)
    new = sync_reports(yr, ensure_job(yr))
    totals, days = aggregate(args.min_impressions)
    print(f"{new} new report file(s), {len(days)} day(s) on file, {len(totals)} video(s) ranked")
    if not totals:
        return

    meta = {v["id"]: v for v in list_videos(yt, 0, list(totals))[0]}
    ranked = sorted(({"id": vid, "impressions": n, "ctr": clicks / n,
                      "title": meta.get(vid, {}).get("title", "(not found)"),
                      "short": meta.get(vid, {}).get("short"), "published": meta.get(vid, {}).get("published", "")}
                     for vid, (n, clicks) in totals.items()), key=lambda r: -r["ctr"])

    today = dt.date.today().isoformat()
    (REPORTS / f"ctr_{today}.json").write_text(json.dumps({"days": days, "videos": ranked}, indent=1), encoding="utf-8")
    md = REPORTS / f"ctr_{today}.md"
    lines = [f"# Thumbnail CTR ranking, {today}", "",
             f"Data days: {days[0]} to {days[-1]} ({len(days)} days). Min {args.min_impressions} impressions. "
             "CTR is impression-weighted across all days on file.", "",
             "| # | CTR | Impressions | Type | Published | Title |", "|---|---|---|---|---|---|"]
    for i, r in enumerate(ranked, 1):
        kind = "short" if r["short"] else "long" if r["short"] is not None else "?"
        lines.append(f"| {i} | {r['ctr']:.1%} | {r['impressions']:,} | {kind} | {r['published']} | "
                     f"[{r['title'].replace('|', '/')}](https://youtu.be/{r['id']}) |")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(md)


if __name__ == "__main__":
    main()
