# Research Query Fanout Design

## Goal

Close the next ml-intern gap by making `query_plan` operational: `research_task` should try expanded query variants when the primary query returns too few sources.

## Scope

This is a retrieval-quality increment only. It does not add new external providers, does not introduce server-side LLM planning, and does not change the MCP planner/executor boundary.

## Behavior

- `research_task` keeps returning the existing `query_plan`.
- Each backend tries the primary query first.
- If a backend returns fewer than its requested limit and no backend error occurred, it tries the next `query_plan` variant.
- If a backend errors, fanout stops for that backend to avoid multiplying rate-limit or availability failures.
- Returned sources include `metadata.query_variant` and `metadata.query_reason` so clients can audit which query found the evidence.
- `query_fanout` defaults to `true` and can be disabled by clients that require single-query behavior.

## Cache

When `cache_dir` is provided, each query variant uses its own cache key. A single-variant lookup keeps the old cache metadata shape; multi-variant lookups report a `variants` list.

## Testing

- Primary empty, expanded query has evidence.
- Existing cache/evidence quality behavior still passes.
- Partial backend failures still produce a single warning and do not retry failing backends.
- Full release gate still passes.
