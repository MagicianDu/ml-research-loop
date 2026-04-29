# Release Checklist

Use this checklist before calling a branch deliverable or merging it into `main`.

## Preconditions

- Worktree is clean except for the release changes under review.
- Python can import this project with `PYTHONPATH=.:.venv/lib/python3.13/site-packages`.
- `ML_RESEARCH_LOOP_PYTHON` points at a working Python executable.
- `GITHUB_TOKEN` is optional and only needed for GitHub code search.

## One-Command Check

Run the make-independent verifier:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON="$(which python3)" \
python3 scripts/release_check.py
```

This command runs:

```bash
ruff check lib/ scripts/ ml_intern/ codex_plugin/ tests/
python3 -m pytest tests/ -q
python3 scripts/mcp_server.py
python3 scripts/mcp_client_acceptance.py --python "$(which python3)"
python3 scripts/mcp_golden_path.py --max-experiments 1 --experiment-duration 30
python3 scripts/mcp_multi_round_demo.py --rounds 2 --max-experiments 1 --experiment-duration 30
python3 scripts/mcp_real_data_demo.py --max-experiments 1 --experiment-duration 30
```

The final JSON summary must report `status: passed`.

## Manual Spot Checks

- Confirm MCP tools include:
  - `get_service_manifest`
  - `read_paper`
  - `research_task`
  - `propose_hypotheses`
  - `run_hypothesis_experiment`
  - `run_ai_autoresearch`
  - `review_research_results`
  - `get_experiment_logs`
- Confirm the golden-path result contains:
  - `research_context.sources`
  - `review.research_review.next_task_patch.budget`
  - `review.experiment_state.planner_handoff`
  - `review.experiment_state.current_code.search_region`
  - `review.experiment_state.research_evidence_gate`
  - `review.experiment_state.dataset_profile`
  - `review.experiment_state.code_change_plan`
  - `review.experiment_state.planner_actions`
  - `hypotheses`
  - `experiments[*].hypothesis_id`
  - `review.research_review.experiment_strategy`
  - `review.research_review.recommended_search_space`
  - `review.research_review.next_task_patch`
- Confirm `research_task` query fanout behavior contains:
  - `query_plan[*].query`
  - `sources[*].metadata.query_variant`
  - `sources[*].metadata.query_reason`
  - `cache.<source>.variants` when cached multi-query retrieval is used
- Confirm the multi-round result contains:
  - `round_count == 2`
  - `rounds[1].input_task_patch == rounds[0].review.experiment_state.next_round.task_patch`
  - `rounds[1].patched_task.hyperparameter_space`
- Confirm the real-data result contains:
  - `data_source == real_file`
  - `review.experiments[0].metrics.val_bpb`
  - `review.experiment_state.dataset_profile.exists == true`
- Confirm `docs/mcp-client-setup.md` and `examples/mcp/` have placeholder paths,
  not machine-local absolute paths.

## Known Local Caveat

On this machine, `/usr/bin/make` currently exits with Xcode license error 69 before
executing Makefile targets. Use `python3 scripts/release_check.py` as the release
gate until the macOS Xcode license is accepted outside this project.
