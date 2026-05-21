---
name: ml-research-loop-planner
description: Use when planning ML research, paper-guided experiments, model improvement loops, or MCP tool sequences with ML Research Loop
---

# ML Research Loop Planner

## Purpose

Use this skill to turn a research or model-improvement request into a safe ML Research Loop MCP workflow. Codex/Claude is the planner; ML Research Loop MCP is the executor.

Canonical architecture: Codex/Claude plans, Skills define workflow policy, MCP executes, Runtime Artifacts remain the factual audit source, and Research Memory Layer provides provenance-backed historical context. Memory suggestions never execute directly.

## Required First Step

Always call `get_service_manifest` before planning. Stop for operator review if:

- `contract_version` is unknown.
- `compatibility_check.status` is not compatible when client acceptance output is available.
- required tools or `tool_contracts` are missing.
- `execution_sandbox.status` is not enforced.

## Workflow Selection

- Proposal prompt contract: when the operator asks for model improvement,
  research-iteration proposals, or next-round experiment ideas, first build a
  current artifact bundle with `build_proposal_context` if the manifest exposes
  it. Treat this as a preview/new workflow unless the manifest confirms the
  tool contract. Codex/Claude may then generate proposal JSON from that bundle,
  but must call `validate_client_proposal_contract` before any execution tool.
  Execute only accepted proposals through guarded MCP tools such as
  `run_client_patch_experiment`, `apply_client_code_patch`, or
  `run_fasttext_multi_proposal_loop`. After evaluation, call
  `write_proposal_reflection` when available and preserve success, failure,
  rollback, and side-effect evidence.
- Memory context: if `get_service_manifest` exposes memory tools, call `retrieve_research_memory` for similar paper, dataset, metric, patch, failure, and rollback memories before proposing a new experiment. Use `suggest_from_memory` only as advisory input, and inspect provenance with `audit_memory_trace` before using the suggestion.
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
  keep `official_scores_claimed=false`. After a useful patch round, call
  `write_fasttext_patch_round_proof_bundle` to write `human-review-report.json`,
  `proof-manifest.json`, `artifact-index.json`, and `SHA256SUMS` before using it
  as public proof.
- Multi-round fastText proof loop: after P4 proof exists, use
  `run_fasttext_multi_proposal_loop` when Codex/Claude has several bounded
  proposals to try. Include rejected or failed proposals in the report instead
  of hiding them, inspect `multi-round-report.json`, `rollback_summary`, and
  `client-handoff.json`, then call `write_fasttext_release_proof_bundle` to
  produce `release-proof-bundle.tar.gz`, `release-proof-bundle.sha256`,
  `release-review-checklist.md`, and `release-proof-manifest.json`.
- Benchmark proof: `get_benchmark_harness_probe` -> `plan_benchmark_proof_run`
  before any official/debug benchmark attempt; after an external run, use
  `write_benchmark_proof_publication_bundle` and `write_benchmark_proof_archive`
  to validate and preserve evidence before reporting results.
- Hugging Face external validation: call `get_hf_external_eval_targets` before
  choosing a public competition, leaderboard, or evaluation target. Use
  `write_hf_external_eval_plan` to write the local proof plan for the selected
  target. This is a planning step only; do not upload to Hugging Face or claim
  a leaderboard score until the operator confirms the submission path and proof
  archive.
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
- Memory recording: when memory write tools are available, record useful
  review reports, proof bundles, failed proposals, rollback events, and
  effective configurations with `record_research_memory` after the run is
  reviewed. Use `promote_memory_card` only after a card has become a reusable
  procedure or playbook.

## Safety Rules

- Do not call `run_ai_autoresearch` unless the user explicitly asks for server-side autonomous LLM runs.
- Do not execute a proposal prompt directly. First validate it against the
  proposal contract, confirm the change surface is allowed, and confirm
  `change_spec.single_primary_variable == true`.
- Do not claim a proposal succeeded because Codex/Claude explains it well.
  Success requires evaluator output and the configured dev/canary/holdout gate.
- Preserve rejected proposals, failed proposal rounds, preflight failures,
  metric regressions, and rollback reasons as audit evidence and later memory
  candidates.
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
- Treat `get_hf_external_eval_targets` and `write_hf_external_eval_plan` as
  external-validation planning tools only. They do not verify live submission
  state, upload artifacts, or create official Hugging Face scores.
- Treat `run_fasttext_patch_round` as a local reproduction-improvement executor:
  the client model chooses the allowlisted hyperparameter proposal, MCP runs and
  archives it, and no artifact may be reported as a full paper reproduction or
  official score.
- Treat `write_fasttext_patch_round_proof_bundle` as the required P4 publication
  guard for fastText patch evidence. It records human confirmation and hashes;
  it does not convert local proof into an official score.
- Treat `run_fasttext_multi_proposal_loop` as a bounded executor for multiple
  client proposals. Failed or invalid rounds are evidence, not noise; preserve
  them with rollback state and keep the best reviewed metric.
- Treat `write_fasttext_release_proof_bundle` as the P5 download/review path. It
  packages proof artifacts and checksums for human review; it does not change
  claim boundaries or claim official scores.
- Treat Research Memory Layer as advisory context only. A memory suggestion must
  include artifact provenance and claim boundaries, and it must still be
  executed through guarded MCP tools before being trusted for the current task.
- Never convert a local proof artifact or autonomous demo result into an
  official score. Keep `official_scores_claimed=false` unless official evidence
  and claim policy explicitly permit otherwise.

## Response Shape

When reporting progress, include: selected MCP tool, `task_id` or `experiment_id`, best metric, artifact paths, evidence status, and next action.
