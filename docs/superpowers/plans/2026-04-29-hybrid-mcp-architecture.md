# Hybrid MCP Architecture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Solidify the hybrid Codex/Claude planner plus MCP executor architecture and return enough post-run state for client-side model iteration.

**Architecture:** The MCP server remains the execution boundary. `review_research_results` becomes the handoff point by returning both deterministic `research_review` and compact `experiment_state`, while `run_ai_autoresearch` stays the explicit server-side LLM path.

**Tech Stack:** Python MCP stdio service, pytest, ruff, markdown docs.

---

### Task 1: Planner State Contract

**Files:**
- Modify: `tests/unit/test_mcp_fusion_tools.py`
- Modify: `lib/fusion_service.py`
- Modify: `lib/mcp_service.py`

- [x] **Step 1: Write the failing test**

Add a test that calls `review_research_results` with `runtime_root` and `workspace`, then asserts the payload includes `experiment_state.planner_handoff`, `current_code.search_region`, `recent_experiments`, `failure_summary`, `artifacts`, and `next_round.task_patch`.

- [x] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_mcp_fusion_tools.py::test_review_research_results_returns_codex_planner_state -q
```

Expected: FAIL with missing `experiment_state`.

- [x] **Step 3: Implement minimal state builder**

Add `build_experiment_state()` to `lib/fusion_service.py`, pass `workspace` through `review_research_results`, and keep provider/model choices outside the default execution path.

- [x] **Step 4: Run test to verify it passes**

Run the same pytest command and expect PASS.

### Task 2: Documentation And Release Gates

**Files:**
- Create: `docs/hybrid-mcp-architecture.md`
- Modify: `README.md`
- Modify: `docs/mcp-client-setup.md`
- Modify: `docs/release-checklist.md`
- Modify: `tests/integration/test_mcp_golden_path.py`

- [x] **Step 1: Document the product requirement**

Create the Chinese architecture doc that defines the client planner, MCP executor, and explicit server-side LLM boundaries.

- [x] **Step 2: Document client usage**

Update MCP client docs so Codex/Claude users know to inspect `experiment_state` after each review and feed `next_round.task_patch` into the next run.

- [x] **Step 3: Add golden-path assertion**

Assert the MCP golden path returns `review.experiment_state.planner_handoff` and a non-empty search region.

- [x] **Step 4: Run verification**

Run targeted tests, ruff, then full `scripts/release_check.py --json`.
