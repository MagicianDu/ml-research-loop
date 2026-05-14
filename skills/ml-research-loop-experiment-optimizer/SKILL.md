---
name: ml-research-loop-experiment-optimizer
description: Use when improving model metrics through ML Research Loop reviews, experiment trees, patch proposals, or multi-round experiment decisions
---

# ML Research Loop Experiment Optimizer

## Purpose

Use this skill after a task has results and the next step is to improve a metric. The client model reasons over review state; MCP executes bounded experiments and guarded patches.

## Start From Review

Call `review_research_results` and inspect:

- `best_result`, metric name, and metric direction.
- `experiment_tree.best_node_id` and `experiment_tree.recommended_next_action`.
- `metric_stop_policy.decision`, `reason_category`, and `current_best`.
- `failure_diagnostics.category_counts` and `recommended_recovery`.
- `code_change_plan.next_experiment_plan`.
- `research_evidence_gate` and `dataset_profile`.
- `reproduction.readiness` when the task is reproduction-oriented.

## Action Choices

- Use `run_next_experiment_from_review` when the proposed task patch is bounded and does not need client code edits.
- Use `run_client_patch_experiment` when changing one SEARCH REGION parameter from a fresh current value.
- Use `apply_client_code_patch` for bounded code diffs with preflight checks, rollback, and optional tests.
- Use `run_fasttext_patch_round` after a trusted fastText AG News baseline when
  Codex/Claude proposes an allowlisted fastText training-argument change such
  as `-wordNgrams`, `-lr`, `-epoch`, `-dim`, `-minCount`, or `-loss`.
- Use `write_fasttext_patch_round_proof_bundle` after a useful fastText patch
  round to preserve `improvement-report.json`, `patch-proposal.json`,
  `patch-diff.patch`, logs, `client-handoff.json`, `human-review-report.json`,
  and `proof-manifest.json`.
- Use `run_fasttext_multi_proposal_loop` when the client has multiple
  allowlisted fastText proposals to evaluate. Preserve failed proposal records
  and `rollback_summary` so reviewers can see what was tried and why the best
  metric was kept.
- Use `write_fasttext_release_proof_bundle` after P4/P5 evidence exists to
  create `release-proof-bundle.tar.gz`, `release-proof-bundle.sha256`,
  `release-review-checklist.md`, and `release-proof-manifest.json`.
- Stop or ask for human review when evidence is weak, budget is exhausted, or the contract is unknown.

## Failure Handling

- `stale` patch: refresh `review_research_results` and regenerate the proposal.
- `syntax/test failure`: do not rerun the same patch; inspect rollback output and simplify the diff.
- `metric regression`: read `metric_stop_policy`, keep the previous best result, and try a smaller local change or stop.
- sandbox violation: do not bypass; move artifacts under an allowed root or update `ML_RESEARCH_LOOP_ALLOWED_ROOTS`.
- fastText patch rejection: inspect `patch-proposal.json`, keep the baseline
  report unchanged, and generate a narrower allowlisted proposal.
- fastText multi-round failure: keep the previous best metric, inspect the
  failed round error, and do not promote failed or invalid proposals.

## Loop Decision

After every run, read `loop_decision` or produce one from the review:

- continue when `metric_stop_policy.should_continue == true`.
- debug when `failure_diagnostics` says the failure is actionable.
- recover research when evidence is weak.
- stop when metric improvement is exhausted, failures repeat, or reproduction readiness blocks progress.

For fastText reproduction improvement rounds, report `baseline_p_at_1`,
`p_at_1`, `delta`, `improved`, `within_tolerance`, and `client-handoff.json`.
If the result is useful, write a P4 proof bundle before public reporting. Keep
`official_scores_claimed=false`; this is local reproducibility evidence, not an
official leaderboard result.

For multi-round fastText loops, report proposal count, failure count,
rollback events, best metric, `multi-round-report.json`, and release proof
bundle checksum when packaged. Failed proposals are part of the audit trail.
