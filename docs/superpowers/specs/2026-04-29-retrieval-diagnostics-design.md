# Retrieval Diagnostics Design

## Goal

Make `research_task` failures and sparse retrieval results actionable for Codex/Claude clients by returning structured diagnostics and recovery hints.

## Scope

This is an ml-intern-side research quality increment. It does not add a new external provider, does not retry rate-limited services automatically, and does not change the hybrid planner/executor boundary.

## Behavior

- `research_task` returns a top-level `retrieval_diagnostics` object.
- Diagnostics are grouped by enabled backend: `papers`, `hf_datasets`, and `github_code`.
- Each backend records attempted query variants with query text, query reason, source count, cache metadata when available, and warning text when a backend fails.
- Backend status is one of:
  - `ready`: enough sources were collected for the requested limit.
  - `partial`: some sources were collected but the backend stopped before the requested limit.
  - `empty`: attempts completed without warnings but no sources were found.
  - `failed`: the backend warning stopped retrieval before sources were collected.
- The top-level summary records source count, attempted query count, failed backend count, empty backend count, warning count, and whether cached results were used.
- `recommended_recovery` gives deterministic client-facing hints such as retrying failed backends later, broadening the query, enabling more source types, or keeping `cache_dir` for repeatability.
- `review_research_results` exposes retrieval recovery hints through `experiment_state.research_evidence_gate`.

## Testing

- A failed paper backend plus successful dataset backend returns backend diagnostics and recovery hints.
- Existing query fanout, cache, evidence quality, and planner action behavior remains compatible.
- Full release gate still passes.
