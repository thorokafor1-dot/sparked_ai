# Channel Analytics

Single job: read our OWN channel's performance (not competitors', that's `outlier-tracking/`) and turn it into edit and hook lessons.

## Scripts
- `oauth_setup.py`: one-time browser login. Reuses the posting OAuth client (`posting-automation/youtube-posting-automation/client_secret.json`) but saves its own read-only `token.json` here (gitignored), so the upload token is never touched. The Cloud project needs the **YouTube Analytics API** enabled.
- `retention.py`: pulls each upload's 100-point retention curve and YouTube's relative retention (vs similar-length videos), then reports hook retention (3s for shorts, 30s for long-form), curve shape, the 3 biggest drop-off windows and rewatch spikes. For long-form, each drop and spike quotes what was being said, from the video's captions. Writes `reports/retention_<date>.md` and `.json`. Shape logic adapted from github.com/tanphat235/YouTube_Analyzer.

## How to use the report
- A drop-off window with its quote shows what to cut or tighten next time (small talk, slow setups, long cards). Feed patterns into `long-form-hook-research/` and `shorts-hook-research/`.
- Rewatch spikes show the moments worth making into a short, a thumbnail frame or a title angle.
- Relative retention above 0.5 beats the platform median for that length. Compare medians, not single videos.

## Quality gates
- Numbers come straight from the API, never estimated. Videos without data yet (about 2 to 3 days of lag) are listed as such, not guessed.
- Livestreams and test streams are excluded so they don't skew the medians.

## Gotchas
- Quota: caption quotes cost about 250 units per long-form video (daily limit 10,000). Use `--no-quotes` on big runs.
- Testing-mode OAuth consent tokens expire after 7 days. Re-run `oauth_setup.py` if refresh fails.
- `oauth_setup.py` prints the consent URL instead of opening a browser, so it can be pasted into the Thor Chrome profile. It must listen on port 8080: the posting client is a Web application client and only `http://localhost:8080/` is registered, so any other port fails with `redirect_uri_mismatch`. If 8080 is busy, a stale `oauth_setup.py` is usually holding it. Kill that process rather than changing the port.
