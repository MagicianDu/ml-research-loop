# Product Examples

These examples are the supported product smoke flows for Codex and Claude MCP
clients.

## synthetic

Run the deterministic synthetic MCP loop:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/mcp_golden_path.py --max-experiments 1 --experiment-duration 30
```

## local real-data

Run the reusable fixture task from `examples/tasks/mcp-real-data-task.json` with
a generated local byte dataset:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/mcp_real_data_demo.py --max-experiments 1 --experiment-duration 30
```

## paper-guided

Ask the MCP client to call `research_task`, then `propose_hypotheses`, then
`run_hypothesis_experiment`. The planner should inspect `evidence_citations`,
`provider_coverage_gate`, and `code_change_plan.next_experiment_plan` before
using `run_next_experiment_from_review`.

## failed-run debugging

When `review_research_results` returns failed experiments, call
`get_experiment_logs`, inspect `failure_summary`, and only then run
`run_next_experiment_from_review` or a patched `run_hypothesis_experiment`.
