# Planner Ready Handoff Design

## Goal

Make each `review_research_results` response easier for Codex/Claude to drive by adding explicit evidence gates and ordered planner actions.

## Scope

This increment stays inside the current hybrid architecture. MCP still executes tools and returns state; Codex/Claude remains the planner. The service does not implicitly call a server-side LLM and does not edit user code.

## Response Additions

`experiment_state` gains:

- `research_evidence_gate`: a compact assessment of whether the attached research context is usable as evidence, including source count, finding count, warning count, and a recommended action.
- `planner_actions`: ordered client-side next steps. Each action has an `action_id`, `tool` when an MCP call is appropriate, `arguments`, `reason`, and `requires_client_edit`.

Action ordering is conservative:

1. If experiments failed, inspect logs before launching new runs.
2. If research context has no evidence or has warnings, refresh research context.
3. If a real dataset path is missing, fix the dataset path before tuning.
4. Otherwise continue with `run_hypothesis_experiment` using `next_round.task_patch`.

## Error Handling

Missing research context is treated as `refresh_research`, not as an exception. Missing runtime paths omit unavailable action arguments, and dataset/code fixes are represented as client-edit actions rather than hard failures.

## Testing

Use TDD:

- Assert clean completed runs return a `run_hypothesis_experiment` action with `task_patch`.
- Assert partial or empty research context returns a `research_task` refresh action.
- Assert failed experiments return `get_experiment_logs` as the first action.

Then rerun the MCP acceptance and full release gate.
