# Retrieval Diagnostics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Return structured retrieval diagnostics and recovery hints from `research_task`, then surface those hints to Codex/Claude through `research_evidence_gate`.

**Architecture:** Extend the existing `build_research_context()` path with a diagnostics accumulator passed into `_collect_source_variants()`. Keep diagnostics additive and deterministic so existing clients remain compatible.

**Tech Stack:** Python, stdio MCP JSON payloads, pytest, markdown docs.

---

### Task 1: Research Retrieval Diagnostics

**Files:**
- Modify: `tests/unit/test_mcp_fusion_tools.py`
- Modify: `lib/fusion_service.py`

- [x] **Step 1: Write the failing diagnostics test**

Add assertions to the partial-context test so it expects `retrieval_diagnostics.backends.papers.status == "failed"`, a warning-bearing attempted query, a successful dataset backend, and top-level recovery hints.

- [x] **Step 2: Run the targeted test and confirm red**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest \
  tests/unit/test_mcp_fusion_tools.py::test_research_task_returns_partial_context_when_one_backend_fails -q
```

Expected: fail because `retrieval_diagnostics` is not returned yet.

- [x] **Step 3: Implement diagnostics accumulator**

Add per-backend diagnostics recording to `_collect_source_variants()`, add summary/recovery helpers, and include `retrieval_diagnostics` in the `research_task` payload.

- [x] **Step 4: Surface recovery hints in review handoff**

Add `retrieval_recovery` from `research_context.retrieval_diagnostics.recommended_recovery` to `build_research_evidence_gate()`.

- [x] **Step 5: Run focused tests and confirm green**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest \
  tests/unit/test_mcp_fusion_tools.py::test_research_task_returns_partial_context_when_one_backend_fails \
  tests/unit/test_mcp_fusion_tools.py::test_review_research_results_prioritizes_research_refresh_when_evidence_is_partial -q
```

### Task 2: Product Docs and Release

**Files:**
- Modify: `README.md`
- Modify: `docs/mcp-client-setup.md`
- Modify: `docs/release-checklist.md`
- Modify: `docs/client-planner-template.md`
- Modify: `docs/hybrid-mcp-architecture.md`
- Modify: `lib/mcp_service.py`
- Modify: `tests/unit/test_mcp_service.py`

- [x] **Step 1: Add diagnostics to the service manifest**

Add `retrieval_diagnostics` to `planning_signals` and assert it in `test_service_manifest_describes_hybrid_planner_contract`.

- [x] **Step 2: Document client usage**

Document that clients should inspect `retrieval_diagnostics` when `research_task.status == "research_context_partial"` or `research_evidence_gate.recommended_action == "refresh_research"`.

- [x] **Step 3: Run impacted tests**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest \
  tests/unit/test_mcp_fusion_tools.py \
  tests/unit/test_mcp_service.py \
  tests/unit/test_ml_intern_fusion_tools.py \
  tests/integration/test_mcp_client_acceptance.py -q
```

- [x] **Step 4: Run full release gate**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON=$(which python3) python3 scripts/release_check.py --json
```

- [x] **Step 5: Commit**

Commit with:

```bash
git commit -m "feat: add retrieval diagnostics"
```
