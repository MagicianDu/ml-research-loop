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

## client patch optimization

When Codex or Claude wants to propose its own one-parameter SEARCH REGION move,
call `run_client_patch_experiment` with a `change_proposal` built from the
latest `experiment_state.current_code.search_region`. Inspect
`patch_execution.mode == "task_patch_only"` and `loop_decision` before the next
round.

Run the repeatable client-patch smoke:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/mcp_client_patch_demo.py --max-experiments 1 --experiment-duration 30
```

When Codex or Claude needs to apply a true workspace code diff, call
`apply_client_code_patch` with a workspace-relative unified diff, `allowed_files`,
and a small `test_command`. The repeatable real task/code benchmark validates
this direct patch path against the local real-data fixture:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/mcp_real_task_code_benchmark.py --max-experiments 1 --experiment-duration 30
```

## provider quality

Run the provider-quality benchmark pack to verify paper-heavy and dataset-heavy
research payloads include provider counts, cache hits, rate-limit diagnostics,
evidence citations, source rankings, and recovery hints:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
python3 scripts/mcp_provider_quality_benchmark.py
```

## failed-run debugging

When `review_research_results` returns failed experiments, call
`get_experiment_logs`, inspect `failure_summary`, and only then run
`run_next_experiment_from_review` or a patched `run_hypothesis_experiment`.
