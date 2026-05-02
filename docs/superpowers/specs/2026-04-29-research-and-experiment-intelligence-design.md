# Research And Experiment Intelligence Design

## Goal

Strengthen the MCP preview in two product-relevant ways: improve ml-intern-side research retrieval quality through cache and evidence metadata, and improve autoresearch-side iteration intelligence through dataset profiling and next-code-change guidance.

## Scope

This is a bounded P5 increment. It does not replace the current MCP tools, introduce a new agent runtime, or make server-side LLM calls implicit. Codex/Claude remains the planner, while MCP returns better structured state for planning.

## Approach

### Research Retrieval

`research_task` and `read_paper` keep their existing response shapes and add optional metadata:

- `cache`: key fields showing cache directory, key, hit/miss status, and source freshness.
- `evidence_quality`: aggregate score, source count, finding count, warning count, top source score, and whether the context is evidence-backed.
- `sources[*].metadata.evidence_quality`: per-source quality score and reasons.

The cache is filesystem JSON under a caller-provided `cache_dir`; if no cache directory is provided, behavior stays uncached. This avoids polluting the checkout during normal MCP calls and makes tests deterministic.

### Experiment Intelligence

`review_research_results` continues to return `research_review` and `experiment_state`, and adds:

- `dataset_profile`: resolved dataset path, existence, size, inferred vocab/sequence length when possible, and risk flags.
- `code_change_plan`: a small deterministic plan for the client model, including recommended edit target, current value, action, and reason.

The plan is intentionally conservative. It uses accepted/rejected experiments, failed-count state, the current search region, and dataset profile. It suggests parameters that are already in the SEARCH REGION so Codex/Claude can modify code safely.

## Data Flow

1. A client calls `research_task` with optional `cache_dir`.
2. MCP collects or reads cached source results, deduplicates and ranks sources, then adds evidence quality metadata.
3. The client calls `run_hypothesis_experiment`.
4. The client calls `review_research_results`.
5. MCP returns dataset profile and code change plan inside `experiment_state`.
6. Codex/Claude uses `next_round.task_patch`, `dataset_profile`, and `code_change_plan` to choose the next MCP call or local code edit.

## Error Handling

- Cache read errors are reported in cache metadata, not hard failures.
- Cache write errors are reported in cache metadata, not hard failures.
- Missing dataset files are represented as `exists: false` with `risks`, not exceptions.
- Missing workspace code returns an empty change plan rather than failing review.

## Testing

Use TDD with targeted unit tests first:

- cache hit/miss behavior for research collection
- evidence-quality metadata on research payloads
- dataset-profile extraction from task/result context
- code-change-plan returned in `experiment_state`

Then run the full release gate:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON=$(which python3) python3 scripts/release_check.py --json
```
