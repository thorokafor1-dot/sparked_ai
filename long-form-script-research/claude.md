# Long-Form Script Research

Single job of this folder: research what keeps viewers watching a long-form video from the hook to the end (pacing, re-hooks, open loops, chaptering, payoff and CTA placement), using FULL transcripts of outliers. `long-form-hook-research/` covers only the first ~90 seconds; this folder covers everything after.

## Two sample pools, kept separate in every output
- **Niche** (`source: niche`): top-scored rows per format from `outlier-tracking/niche-long-form/data.json`, plus the `niche_authorities` group in `channels.json` (the user's reference creators: Coach Kyle, Todd V, Jameer, Jay Throck and others).
- **General** (`source: general`): recent outliers (ratio vs own channel median >= 1.8, 1M+ views, last 365 days) from big channels whose audience is men 18-35 (the target; teen-skewing channels go under `_excluded` in channels.json), in three groups: `social_experiment`, `mens_self_improvement`, `story_explainer`, plus `craft_only` (structure only, never tone or topics; currently Ryan Trahan). Edit `channels.json` to change who's studied.

## Pipeline
1. `find_general_outliers.py [--group <name>]` uses yt-dlp, no API quota. Writes `general_candidates.json`; `--group` rescans one group and merges.
2. `pull_full_transcripts.py --source niche|general|all [--whisper]` saves `transcripts/<vid>.json` once per video, so reruns skip done ones.
3. `analyze_retention.py` writes `retention_metrics.json` (per-video and per-bucket medians) and `skeletons.md` (timestamped beat sheet per video).
4. `analyze_retention.py` also writes `beat_maps/<infield|video-chat|explainer>.md`: per-category replay curve plus ranked reference videos with peaks/dips as % of runtime. This is what the script-writer models each script on (2 references per script, gated by `script-structure`). New sample groups must be added to `CATEGORY` in the analyzer; it prints UNMAPPED otherwise.
5. `retention_playbook.md` is the human-readable synthesis the `script-writer` agent reads. Regenerate it from steps 2-3 when the sample changes materially.

## Retention signals
- **Competitors:** real retention curves are private, and no tool (free or paid) can read them. The proxy is YouTube's public "Most replayed" heatmap (100 points, via yt-dlp `heatmap`), stored per transcript. `analyze_retention.py` quotes what was said at the top 3 replay peaks and the 3 deepest dips. Videos under roughly 100K views usually have no heatmap.
- **Our own channel is excluded.** The user is a small creator and their data is not model data. `channel-analytics/` (skill `retention-report`) is a separate diagnostic and never feeds the playbook.

## Gotchas
- YouTube 429s caption requests after a burst, on both the caption API and yt-dlp subs. Don't run the channel scan and the transcript pull at the same time. Rerun later (it resumes) or pass `--whisper` (slow on CPU: about 1x realtime for a 20-minute video).
- Faceless AI "stoic / female psychology" voiceover channels score high in niche data, but they aren't the user's format (on-camera creator). Read them for pacing only, never for persona or delivery.
- Never quote a woman's lines from infield transcripts into scripts (memory: no fabricated dialogue). Skeletons are for structure only.

## Quality gates
- `script-research` in `qa/checks_data.py`: every transcript has meta and non-empty, time-ordered segments; `retention_playbook.md` cites both pools and has no placeholders.
