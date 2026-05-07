# Public Proof Run Plan Spec

## Goal

Add a read-only public proof-run planning layer for benchmark adapters. It consumes
the official harness probe and tells Codex/Claude whether an official debug or
small proof run can start, what is missing, which environment is recommended,
which commands are safe, and which commands remain blocked.

## Scope

In scope:

- Build a structured proof-run plan from `build_official_harness_probe()`.
- Preserve `official_scores_claimed=false`.
- Return `status=blocked` when official prerequisites are missing.
- Return `status=ready_for_debug_run` only when required harness checks are ready.
- Recommend an external evaluation environment when this machine lacks critical
  official harness dependencies.
- Expose the plan through CLI, script, MCP manifest, and release checks.
- Document the proof-run boundary in Chinese product docs.

Out of scope:

- Downloading official data.
- Installing MLE-bench, PaperBench, `uv`, `git-lfs`, Docker images, or credentials.
- Running official grading, API calls, Docker builds, Kaggle hydration, or
  leaderboard submission.
- Claiming official benchmark scores.

## Product Contract

The proof plan payload must include:

- `status`: `blocked` or `ready_for_debug_run`
- `read_only`: always `true`
- `official_scores_claimed`: always `false`
- `recommended_environment`: `external_evaluation_environment`,
  `local_worktree`, or `current_machine`
- `missing_prerequisites`: list of harness/check identifiers
- `safe_next_commands`: commands limited to read-only checks or setup planning
- `next_actions`: planner-facing setup or official-debug preparation actions
- `blocked_commands`: official run commands that must not be launched until the
  plan is ready
- `artifact_requirements`: command log, config, environment manifest, raw
  report, limitations note, and non-official-score statement
- `harness_probe`: the source probe payload

## Acceptance

- `ml-loop benchmark proof-plan --json` exits 0 and prints the structured plan.
- `python3 scripts/benchmark_proof_plan.py --json` exits 0 and does not run
  official evaluations.
- `get_service_manifest()` includes `benchmark_proof_plan`.
- `scripts/release_check.py --json` includes a cheap
  `benchmark-proof-plan` check.
- Docs explicitly separate this plan from an actual official score.
