---
name: ml-research-loop-planner
description: Use when planning ML research, paper-guided experiments, model improvement loops, or MCP tool sequences with ML Research Loop
---

# ML Research Loop Planner

## Purpose

Use this skill to turn a research or model-improvement request into a safe ML Research Loop MCP workflow. Codex/Claude is the planner; ML Research Loop MCP is the executor.

## Required First Step

Always call `get_service_manifest` before planning. Stop for operator review if:

- `contract_version` is unknown.
- `compatibility_check.status` is not compatible when client acceptance output is available.
- required tools or `tool_contracts` are missing.
- `execution_sandbox.status` is not enforced.

## Workflow Selection

- Research context: `research_task` or `read_paper` -> inspect `research_evidence_gate`, `provider_coverage`, `deduplication_report`, `cache_summary`, `provider_quality_matrix`, `retrieval_diagnostics`, and `evidence_citations`.
- Hypothesis generation: `propose_hypotheses` after evidence is usable.
- Experiment run: `run_hypothesis_experiment` with bounded `max_experiments` and `experiment_duration`.
- Review: `review_research_results` after every run; read `experiment_state`, `planner_actions`, `code_change_plan`, `experiment_tree`, `failure_diagnostics`, `metric_stop_policy`, and `reproduction.readiness`.
- Automatic next run: `run_next_experiment_from_review` only when the review proposes a safe `next_task_patch`.
- Client parameter patch: `run_client_patch_experiment` for one SEARCH REGION parameter with current value taken from the latest review.
- Code patch: `apply_client_code_patch` only for bounded diffs with syntax/test preflight and rollback.
- Full reproduction patch loop: after `run_fasttext_binary_baseline` produces a
  trusted fastText AG News baseline report, use `run_fasttext_patch_round` when
  Codex/Claude proposes a bounded allowlisted training-argument change. Inspect
  `improvement_report`, `patch_diff`, `client_handoff`, `loop_decision`, and
  keep `official_scores_claimed=false`.
- Benchmark proof: `get_benchmark_harness_probe` -> `plan_benchmark_proof_run`
  before any official/debug benchmark attempt; after an external run, use
  `write_benchmark_proof_publication_bundle` and `write_benchmark_proof_archive`
  to validate and preserve evidence before reporting results.
- Official MLE-bench agent loop: after the operator has prepared data with the
  official harness, call `prepare_official_mle_bench_workspace`, patch
  `solve.py` or `submission.csv` through `run_official_mle_bench_patch_round`
  when you have a bounded unified diff. The patch-round tool applies the diff,
  runs `solve.py`, grades `submission.csv`, and returns
  `official_mle_patch_round` artifacts plus `loop_decision`. Use
  `write_official_mle_bench_patch_round_proof_bundle` after useful patch rounds
  to preserve the patch diff, reports, logs, snapshots, limitations, and hashed
  archive under `official_mle_patch_proof_archive`. Use
  `run_official_mle_bench_round` when no patch is needed. Use
  `grade_official_mle_bench_submission` only when grading a pre-existing
  submission without rerunning the solver.
- PaperBench Codex-assisted review: when official PaperBench real-judge keys
  are unavailable or the operator wants a client-model audit first, call
  `prepare_paperbench_codex_review_bundle`, review the generated packet and
  prompt in Codex/Claude, then persist the review with
  `write_paperbench_codex_review_report`. This is useful evidence for
  reproduction discussion, but it is not an official PaperBench score.
- Long-running autonomous research: create or read a `ResearchCase` before
  starting the loop, summarize it after each bounded round, inspect the
  returned `loop_decision`, and stop to report when
  `requires_human_confirmation=true`. Treat local proof archives as
  non-official evidence unless an explicit publication guard allows a stronger
  claim.

## Safety Rules

- Do not call `run_ai_autoresearch` unless the user explicitly asks for server-side autonomous LLM runs.
- Ask for human confirmation before destructive artifact cleanup, broad code patches, weak-evidence experiments, or unknown contract migration.
- If `research_evidence_gate` says evidence is weak or partial, recover with more `research_task` / `read_paper` calls before experiment changes.
- If `metric_stop_policy.decision == "stop"`, handle its `reason_category` before starting another experiment.
- Never reuse stale SEARCH REGION values. Refresh with `review_research_results` when a patch is rejected as stale.
- Do not treat benchmark proof artifacts as official leaderboard results unless
  the publication/archive payload includes explicit score evidence and a
  non-blocked claim policy.
- Treat `grade_official_mle_bench_submission` as local scorer feedback only:
  `official_scores_claimed=false` remains the default until a publication guard
  explicitly permits a stronger claim.
- Treat `run_official_mle_bench_patch_round` as an execution tool, not a code
  generator: Codex/Claude must inspect the latest round report and generate the
  bounded diff before calling it.
- Treat `write_paperbench_codex_review_report` as a non-official audit record:
  keep `official_scores_claimed=false` and do not describe its
  `codex_review_score` as a PaperBench leaderboard or real-judge result.
- Treat `run_fasttext_patch_round` as a local reproduction-improvement executor:
  the client model chooses the allowlisted hyperparameter proposal, MCP runs and
  archives it, and no artifact may be reported as a full paper reproduction or
  official score.
- Never convert a local proof artifact or autonomous demo result into an
  official score. Keep `official_scores_claimed=false` unless official evidence
  and claim policy explicitly permit otherwise.

## Response Shape

When reporting progress, include: selected MCP tool, `task_id` or `experiment_id`, best metric, artifact paths, evidence status, and next action.
