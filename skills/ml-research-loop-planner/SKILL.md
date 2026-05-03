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

- Research context: `research_task` or `read_paper` -> inspect `research_evidence_gate`, `provider_coverage`, `retrieval_diagnostics`, and `evidence_citations`.
- Hypothesis generation: `propose_hypotheses` after evidence is usable.
- Experiment run: `run_hypothesis_experiment` with bounded `max_experiments` and `experiment_duration`.
- Review: `review_research_results` after every run; read `experiment_state`, `planner_actions`, `code_change_plan`, `experiment_tree`, and `reproduction.readiness`.
- Automatic next run: `run_next_experiment_from_review` only when the review proposes a safe `next_task_patch`.
- Client parameter patch: `run_client_patch_experiment` for one SEARCH REGION parameter with current value taken from the latest review.
- Code patch: `apply_client_code_patch` only for bounded diffs with syntax/test preflight and rollback.

## Safety Rules

- Do not call `run_ai_autoresearch` unless the user explicitly asks for server-side autonomous LLM runs.
- Ask for human confirmation before destructive artifact cleanup, broad code patches, weak-evidence experiments, or unknown contract migration.
- If `research_evidence_gate` says evidence is weak or partial, recover with more `research_task` / `read_paper` calls before experiment changes.
- Never reuse stale SEARCH REGION values. Refresh with `review_research_results` when a patch is rejected as stale.

## Response Shape

When reporting progress, include: selected MCP tool, `task_id` or `experiment_id`, best metric, artifact paths, evidence status, and next action.
