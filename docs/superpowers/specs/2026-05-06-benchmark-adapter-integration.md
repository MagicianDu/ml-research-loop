# Benchmark Adapter Integration Spec

## Goal

Merge the MLE-bench and PaperBench compatibility spikes into one coherent benchmark adapter layer that moves ML Research Loop closer to proving research reproduction and ML engineering benchmark readiness.

This is an integration milestone, not an official leaderboard submission. All benchmark-shaped outputs must preserve explicit `official_mle_bench=false` or `official_paperbench=false` fields until the project can run the official harnesses.

## Product Target

ML Research Loop should be usable as a Codex/Claude MCP service plus skills package that can:

1. collect research evidence and reproduction requirements;
2. run bounded ML experiments;
3. preserve metrics, logs, patches, and reproduction artifacts;
4. emit benchmark-shaped reports that later map onto public benchmark harnesses.

The benchmark adapter layer is the bridge between current MCP product demos and future public evaluation work.

## External Benchmark Contracts

### MLE-bench Direction

Reference: https://github.com/openai/mle-bench

The adapter should model the shape of an MLE-bench run group:

- competition id;
- fixture instructions and data files;
- submission CSV matching sample-submission columns;
- run-group metadata;
- report path and grading command hint.

Official MLE-bench work remains out of scope for this milestone because it needs real competition hydration, official environment setup, and official grading.

### PaperBench Direction

Reference: https://github.com/openai/frontier-evals/tree/main/project/paperbench

The adapter should model the three PaperBench stages:

- Agent Rollout: a submission codebase exists and required files are checked;
- Reproduction: the submitted codebase runs locally and emits logs/results;
- Grading: rubric leaves are evaluated into a grade report.

Official PaperBench work remains out of scope for this milestone because it needs official paper samples, judge/evaluator setup, and benchmark-specific grading integration.

## Scope

### In

- Merge both spike branches into a single integration branch.
- Export both adapter families from `lib/benchmarks`.
- Preserve deterministic demo scripts:
  - `scripts/mle_bench_adapter_demo.py`
  - `scripts/paperbench_adapter_demo.py`
- Preserve unit and integration tests for both adapters.
- Add one Chinese roadmap document explaining what is proven now and what remains before official benchmark attempts.
- Update examples and productization TODOs so users can discover both compatibility flows.

### Out

- No Kaggle API or official MLE-bench Docker integration.
- No official PaperBench data hydration or judge invocation.
- No leaderboard score claim.
- No new MCP tool contract in this milestone; these remain CLI/demo adapter flows until official harness integration is designed.

## Acceptance

- `ruff check lib/ scripts/ tests/` passes.
- Full `pytest tests/ -q` passes.
- `scripts/mle_bench_adapter_demo.py --runtime-root <tmp> --json` exits 0 and emits:
  - `status=completed`
  - `official_mle_bench=false`
  - `submission_path`
  - `metadata_path`
  - `benchmark_report_path`
  - non-null `best_metric`
- `scripts/paperbench_adapter_demo.py --runtime-root <tmp> --json` exits 0 and emits:
  - `status=passed`
  - `official_paperbench=false`
  - `submission_dir`
  - `reproduction_report_path`
  - `grade_report_path`
  - `benchmark_report_path`
  - positive grading score
- Worktree remains clean after commit.
- Branch is pushed for PR/integration review.

## Follow-Up Milestones

### P13: Benchmark Adapter Productization

- Expose adapter readiness through a CLI command or manifest section.
- Add a combined benchmark smoke script that runs both compatibility demos.
- Add artifact bundle output for benchmark reports.

### P14: Official Harness Feasibility

- Build a read-only official harness probe for MLE-bench and PaperBench.
- Document required credentials, data downloads, environment constraints, and expected runtime cost.
- Decide whether official leaderboard attempts should run locally, in CI, or in a separate evaluation environment.

### P15: Public Proof Run

- Run one official or official-debug benchmark path with a clear public report.
- Preserve all command lines, configs, artifacts, and known limitations.
- Avoid score marketing until the result can be reproduced by a fresh checkout or independent reviewer.
