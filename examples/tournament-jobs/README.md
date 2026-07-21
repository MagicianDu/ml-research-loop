# Tournament job files

One job = one tournament run = one scheduled task. `synthetic-demo.json`
runs fully offline (no binary, no data, Phase A auto-writes the baseline)
and is the acceptance path. `fasttext-ag-news.json` is the real-data
template: it expects the fastText binary at `.external/fastText/fasttext`
and full AG News CSVs under `data/ag_news/` (both gitignored,
user-provided); adjust paths, budgets, and `max_wakeups` before use.
`max_wall_seconds` counts from tournament creation — set it day-scale for
unattended runs. See `skills/ml-research-loop-tournament-driver/SKILL.md`
for the per-wake procedure and the scheduled-task prompt.
