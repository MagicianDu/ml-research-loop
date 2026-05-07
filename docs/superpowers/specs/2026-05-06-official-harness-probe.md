# Official Harness Probe Spec

## Goal

Add read-only feasibility probes for official MLE-bench and PaperBench harnesses so ML Research Loop can say what is locally ready before anyone attempts a long-running public benchmark run.

This milestone must not run official evaluations, download benchmark datasets, build Docker images, call external APIs, or claim benchmark scores.

## External Contracts

### MLE-bench

Official source: https://github.com/openai/mle-bench

The probe should reflect these requirements at a high level:

- official repo or package commands are needed for `mlebench prepare` and `mlebench grade`;
- Git LFS is required for released data artifacts;
- Kaggle credentials are required for competition data hydration;
- Docker support is part of the official environment path;
- full data preparation can be large and long-running, so the probe only reports readiness.

### PaperBench

Official source: https://github.com/openai/frontier-evals/tree/main/project/paperbench

The probe should reflect these requirements at a high level:

- official repo checkout is needed under `project/paperbench`;
- `uv sync` is the expected dependency setup path;
- Git LFS is used for official sample data;
- OpenAI-compatible grader credentials may be needed for grading;
- Docker/container execution and GPU/runtime resources may be needed for full reproduction, so the probe only reports readiness.

## Scope

### In

- A dependency-free Python probe module under `lib/benchmarks/`.
- A direct script:
  - `scripts/benchmark_harness_probe.py --json`
- A CLI entry:
  - `ml-loop benchmark probe --json`
- MCP manifest exposure under `benchmark_harness_probe`.
- Release-check inclusion because this probe is read-only and cheap.
- Unit tests with fake commands/env and integration smoke for the script.
- Docs that keep compatibility demos separate from official benchmark readiness.

### Out

- No official benchmark evaluation.
- No `mlebench prepare`, `mlebench grade`, `uv sync`, Docker build, data download, or API call.
- No score comparison or leaderboard claim.

## Acceptance

- Probe payload has:
  - `read_only=true`
  - `official_scores_claimed=false`
  - harness entries for `mle_bench` and `paperbench`
  - command checks
  - repo/data checks
  - credential checks without printing secret values
  - `blocking_issue_count`
  - `next_actions`
- CLI and script return JSON without requiring official repos to exist.
- Missing prerequisites produce `status=needs_setup`, not a crash.
- Simulated complete prerequisites produce `status=ready` in unit tests.
- `release_check.py --json` includes and passes the read-only probe.
