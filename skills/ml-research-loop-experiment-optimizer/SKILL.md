---
name: ml-research-loop-experiment-optimizer
description: Use when improving model metrics through ML Research Loop reviews, experiment trees, patch proposals, or multi-round experiment decisions
---

# ML Research Loop Experiment Optimizer

## Purpose

Use this skill after a task has results and the next step is to improve a metric. The client model reasons over review state; MCP executes bounded experiments and guarded patches.

Canonical architecture: Codex/Claude may use Research Memory Layer to recall historical configurations, failures, rollbacks, and patch outcomes, but current execution still goes through MCP guardrails and current runtime artifacts remain the source of truth.

## Start From Review

Call `review_research_results` and inspect:

- `best_result`, metric name, and metric direction.
- `experiment_tree.best_node_id` and `experiment_tree.recommended_next_action`.
- `metric_stop_policy.decision`, `reason_category`, and `current_best`.
- `failure_diagnostics.category_counts` and `recommended_recovery`.
- `code_change_plan.next_experiment_plan`.
- `research_evidence_gate` and `dataset_profile`.
- `reproduction.readiness` when the task is reproduction-oriented.
- memory suggestions (`suggest_from_memory`) and `audit_memory_trace` output
  when memory tools are available.

If the next action is a client-generated proposal, build or request the current
proposal context first with `build_proposal_context` when the manifest exposes
that workflow. Include artifact manifest, resource constraints, prior proposal
history, rollback summary, and memory-card evidence; pass `memory_store` and a
targeted memory query when reusable proposal reflections exist. Codex/Claude
should generate only proposal JSON from the artifact bundle, not a success
claim. Before execution, validate it with `validate_client_proposal_contract`
and require an accepted result, one primary variable, an allowed change surface,
an explicit rollback condition, and `official_scores_claimed=false`.

## Action Choices

- Use `run_next_experiment_from_review` when the proposed task patch is bounded and does not need client code edits.
- Use validated proposal JSON as the handoff format before
  `run_client_patch_experiment`, `apply_client_code_patch`, or
  `run_fasttext_multi_proposal_loop`. If validation rejects the proposal,
  rewrite it or stop for operator review; do not partially execute it.
- Use `run_smol_worldcup_proposal_round` when the accepted proposal targets a
  Smol WorldCup local prompt/profile/model-choice diagnostic. Treat its output
  as local evidence only; do not submit or claim Hugging Face official scores.
- Use `summarize_proposal_search` when several proposals or proposal families
  exist. Set branch budget and diversity constraints, then prefer
  canary/holdout-supported candidates over dev-only gains when deciding what to
  continue.
- Use `retrieve_research_memory` and `suggest_from_memory` only after checking
  artifact provenance, metric direction, dataset compatibility, known failures,
  and claim boundary.
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

- proposal validation rejection: inspect missing fields, disallowed
  `change_surface`, broad `change_spec`, or forbidden score claims; regenerate a
  narrower proposal from the same context instead of executing it.
- `stale` patch: refresh `review_research_results` and regenerate the proposal.
- `syntax/test failure`: do not rerun the same patch; inspect rollback output and simplify the diff.
- `metric regression`: read `metric_stop_policy`, keep the previous best result, and try a smaller local change or stop.
- sandbox violation: do not bypass; move artifacts under an allowed root or update `ML_RESEARCH_LOOP_ALLOWED_ROOTS`.
- fastText patch rejection: inspect `patch-proposal.json`, keep the baseline
  report unchanged, and generate a narrower allowlisted proposal.
- fastText multi-round failure: keep the previous best metric, inspect the
  failed round error, and do not promote failed or invalid proposals.
- proposal reflection: after an evaluated proposal, call
  `write_proposal_reflection` when available. Record dev/canary/holdout deltas,
  side effects, failure labels, rollback decision, and whether memory recording
  is recommended. When useful, pass `memory_store` or run
  `ml-loop proposal reflect --memory-store` so the result becomes a reusable
  research memory card. External Graphiti/cognee syncing remains opt-in.
- memory conflict: if historical memory suggests a patch that conflicts with
  current evidence, stale SEARCH REGION values, sandbox rules, or resource
  budget, trust the current review and artifacts first.

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

When memory recording is available, use `record_research_memory` to store both
successful and failed rounds:
metric deltas, config values, rollback decision, preflight errors, test
failures, and proof bundle refs. Failed rounds are reusable evidence, not noise.

Never upgrade a local proposal diagnostic into a stable release claim or
official score. A dev-only gain is a candidate direction; promotion requires the
configured canary/holdout or external validation gate.
