# Planner Ready Handoff Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add evidence gates and ordered planner actions to `review_research_results` so Codex/Claude can choose the next MCP call more reliably.

**Architecture:** Extend `lib/fusion_service.py` with deterministic helpers that inspect the current research context, dataset profile, failure state, artifacts, and next task patch. Keep the MCP client as the planner and expose the new signals through the existing `experiment_state`.

**Tech Stack:** Python, stdio MCP JSON payloads, pytest, ruff, markdown docs.

---

### Task 1: Planner Handoff State

**Files:**
- Modify: `lib/fusion_service.py`
- Modify: `tests/unit/test_mcp_fusion_tools.py`

- [x] **Step 1: Write failing tests**

Add tests that assert `review_research_results` returns:

- `experiment_state.research_evidence_gate`
- `experiment_state.planner_actions`
- a `run_hypothesis_experiment` action for clean completed runs
- a `research_task` action for partial evidence
- a `get_experiment_logs` action for failed experiments

- [x] **Step 2: Verify tests fail**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest \
  tests/unit/test_mcp_fusion_tools.py::test_review_research_results_returns_planner_actions_for_clean_run \
  tests/unit/test_mcp_fusion_tools.py::test_review_research_results_prioritizes_research_refresh_when_evidence_is_partial \
  tests/unit/test_mcp_fusion_tools.py::test_review_research_results_prioritizes_log_action_for_failures -q
```

Expected: fail because the fields do not exist yet.

- [x] **Step 3: Implement planner handoff helpers**

Add deterministic helpers in `lib/fusion_service.py`:

- `build_research_evidence_gate(result_payload)`
- `build_planner_actions(...)`
- `_resolve_task_file(...)`

- [x] **Step 4: Verify targeted tests pass**

Run the same targeted pytest command and expect pass.

### Task 2: Manifest, Docs, And Acceptance

**Files:**
- Modify: `lib/mcp_service.py`
- Modify: `tests/unit/test_mcp_service.py`
- Modify: `tests/integration/test_mcp_client_acceptance.py`
- Modify: `docs/mcp-client-setup.md`
- Modify: `docs/client-planner-template.md`
- Modify: `docs/hybrid-mcp-architecture.md`
- Modify: `docs/release-checklist.md`

- [x] **Step 1: Expose new planning signals**

Add `research_evidence_gate` and `planner_actions` to the service manifest planning signals.

- [x] **Step 2: Update docs and acceptance tests**

Document the new client loop and assert the manifest includes the new signals.

- [x] **Step 3: Run impacted tests**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest \
  tests/unit/test_mcp_fusion_tools.py \
  tests/unit/test_mcp_service.py \
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
git commit -m "feat: add planner-ready handoff actions"
```
