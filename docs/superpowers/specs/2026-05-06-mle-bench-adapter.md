# MLE-bench Adapter Spec

## Goal

Build a first MLE-bench-facing adapter that proves ML Research Loop can produce benchmark-shaped ML engineering artifacts: task config, workspace, submission file, run metadata, and a benchmark report.

This spike is not an official MLE-bench leaderboard submission. It is the compatibility layer that lets us run one deterministic MLE-bench-shaped task locally, then later swap in real MLE-bench competitions and grading.

## External Contract

Reference behavior from official MLE-bench docs:

- MLE-bench is agent-agnostic and expects agents to produce submissions for competitions.
- `run_agent.py` creates a run-group directory with per-competition logs, code, and submission.
- Completed run groups can be compiled with `experiments/make_submission.py` and graded with `mlebench grade`.
- A useful smoke split is `spaceship-titanic.txt`.

Primary references:

- https://github.com/openai/mle-bench
- https://github.com/openai/mle-bench/blob/main/agents/README.md

## Scope

### In

- A dependency-free adapter module under `lib/benchmarks/`.
- A CLI/demo script that runs a deterministic MLE-bench-shaped local fixture.
- A fixture competition with:
  - `competition_id`
  - instructions/description
  - train/test/sample submission CSV files
  - metric direction
- Output artifacts:
  - ML Research Loop task JSON
  - workspace path
  - submission CSV
  - metadata JSON
  - benchmark report JSON
  - feedback-bundle-compatible runtime path
- Unit and integration tests.

### Out

- No Kaggle API integration.
- No official MLE-bench Docker image build.
- No official leaderboard claim.
- No GPU assumptions.

## Product Requirements

1. A user can run one command from the MLE worktree and get a valid benchmark-shaped output.
2. The report must say clearly whether the run is `official_mle_bench=false`.
3. The report must preserve enough information for a future official adapter:
   - `competition_id`
   - `run_group`
   - `submission_path`
   - `metadata_path`
   - `grade_command_hint`
   - `task_file`
   - `result_file`
   - `best_metric`
4. The adapter should reuse existing `ml-loop demo` / autoresearch capabilities where possible instead of creating another experiment runner.
5. The implementation must be deterministic and pass without network access.

## Acceptance

- `python scripts/mle_bench_adapter_demo.py --runtime-root <tmp> --json` exits 0.
- The JSON payload includes `status=completed`, `official_mle_bench=false`, `submission_path`, `metadata_path`, and `benchmark_report_path`.
- `submission.csv` exists and matches the fixture sample submission columns.
- `benchmark_report.json` includes a non-null `best_metric`.
- New tests pass under Python 3.13.
- Existing full test suite remains green.
