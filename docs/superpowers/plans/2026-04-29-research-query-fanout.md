# Research Query Fanout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `research_task.query_plan` actively improve retrieval by trying query variants when the primary query returns too few sources.

**Architecture:** Add a small fanout collector in `lib/fusion_service.py` that wraps the existing backend-specific search calls and cache helper. Preserve the existing response shape for single-query paths while adding per-source query provenance.

**Tech Stack:** Python, stdio MCP schema, pytest, markdown docs.

---

### Task 1: Query Fanout Retrieval

**Files:**
- Modify: `lib/fusion_service.py`
- Modify: `lib/mcp_service.py`
- Modify: `ml_intern/tools/run_autoresearch.py`
- Modify: `tests/unit/test_mcp_fusion_tools.py`
- Modify: `tests/unit/test_mcp_service.py`

- [x] **Step 1: Write failing fanout test**

Add a test where `search_papers("tiny stories")` returns `[]`, the keyword-expansion query returns one source, and the source includes `metadata.query_variant` / `metadata.query_reason`.

- [x] **Step 2: Verify the test fails**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest \
  tests/unit/test_mcp_fusion_tools.py::test_research_task_fans_out_to_query_expansion_when_primary_is_empty -q
```

Expected: fail because only the primary query is called.

- [x] **Step 3: Implement fanout collector**

Add `_collect_source_variants()` and `_annotate_query_variant()` in `lib/fusion_service.py`; thread `query_fanout` through MCP and ml-intern tool wrappers.

- [x] **Step 4: Verify targeted tests pass**

Run the fanout test plus existing research-task/cache/schema tests.

### Task 2: Docs, Release, Commit

**Files:**
- Modify: `README.md`
- Modify: `docs/mcp-client-setup.md`
- Modify: `docs/release-checklist.md`
- Create: `docs/superpowers/specs/2026-04-29-research-query-fanout-design.md`

- [x] **Step 1: Document query fanout**

Document `query_fanout`, query provenance metadata, and cache behavior.

- [x] **Step 2: Run full release gate**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON=$(which python3) python3 scripts/release_check.py --json
```

- [x] **Step 3: Commit**

Commit with:

```bash
git commit -m "feat: add research query fanout"
```
