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
python3 scripts/mcp_golden_path.py --max-experiments 1 --experiment-duration 30
```

The final JSON summary must report `status: passed`.

## Manual Spot Checks

- Confirm MCP tools include:
  - `read_paper`
  - `research_task`
  - `propose_hypotheses`
  - `run_hypothesis_experiment`
  - `run_ai_autoresearch`
  - `review_research_results`
- Confirm the golden-path result contains:
  - `research_context.sources`
  - `review.research_review.next_task_patch.budget`
  - `review.experiment_state.planner_handoff`
  - `review.experiment_state.current_code.search_region`
  - `hypotheses`
  - `experiments[*].hypothesis_id`
  - `review.research_review.experiment_strategy`
  - `review.research_review.recommended_search_space`
  - `review.research_review.next_task_patch`
- Confirm `docs/mcp-client-setup.md` and `examples/mcp/` have placeholder paths,
  not machine-local absolute paths.

## Known Local Caveat

On this machine, `/usr/bin/make` currently exits with Xcode license error 69 before
executing Makefile targets. Use `python3 scripts/release_check.py` as the release
gate until the macOS Xcode license is accepted outside this project.
