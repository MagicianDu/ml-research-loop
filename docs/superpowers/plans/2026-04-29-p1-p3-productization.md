# P1-P3 MCP Productization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the project from a validated MCP research loop toward product use by adding client-planner instructions, a real-data demo, and minimal observability hardening.

**Architecture:** Keep the hybrid boundary unchanged: Codex/Claude acts as the planner, MCP executes experiments and returns state. P1 is documentation and prompt contract, P2 proves the loop can run on an actual local dataset file, and P3 adds a log-summary MCP tool plus release coverage.

**Tech Stack:** Python stdio MCP service, pytest, ruff, markdown docs.

---

### Task 1: P1 Client Planner Template

**Files:**
- Create: `docs/client-planner-template.md`
- Create: `examples/planner/codex-claude-planner-prompt.md`
- Create: `tests/unit/test_planner_docs.py`

- [x] **Step 1: Write failing doc-contract test**

Assert the planner docs mention `experiment_state`, `next_round.task_patch`, `run_hypothesis_experiment`, `run_ai_autoresearch`, stop rules, and failure handling.

- [x] **Step 2: Run test and verify failure**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_planner_docs.py -q
```

Expected: fail because files do not exist.

- [x] **Step 3: Add planner docs and prompt**

Create Chinese docs and a reusable prompt for Codex/Claude clients.

- [x] **Step 4: Verify P1**

Run the same test and expect pass.

### Task 2: P2 Real Data Demo

**Files:**
- Create: `scripts/mcp_real_data_demo.py`
- Create: `tests/integration/test_mcp_real_data_demo.py`
- Modify: `scripts/autoresearch_run.py`
- Modify: `scripts/ai_autoresearch_run.py`
- Modify: `tests/unit/test_autoresearch_run.py`

- [x] **Step 1: Write failing dataset-path and demo tests**

Assert `run_training(..., data_path=...)` sets `DATA_PATH`, and the real-data demo reports `data_source: real_file`.

- [x] **Step 2: Run tests and verify failure**

Run targeted pytest and expect missing function/script support.

- [x] **Step 3: Pass dataset path into train.py**

Add optional `data_path` to both runners and pass `task.dataset.path`.

- [x] **Step 4: Add real-data MCP demo**

Write a tiny deterministic byte dataset and run one hypothesis experiment against that file.

- [x] **Step 5: Verify P2**

Run targeted integration and unit tests.

### Task 3: P3 MCP Observability And Release Gate

**Files:**
- Modify: `lib/mcp_service.py`
- Modify: `tests/unit/test_mcp_service.py`
- Modify: `scripts/release_check.py`
- Modify: `tests/unit/test_release_check.py`
- Modify: `docs/mcp-client-setup.md`
- Modify: `docs/release-checklist.md`

- [x] **Step 1: Write failing MCP log summary test**

Assert tools/list includes `get_experiment_logs` and the handler returns recent log tails.

- [x] **Step 2: Implement minimal log-summary tool**

Read `workdir/<task_id>/logs/*.log` or supplied workspace logs and return recent file summaries.

- [x] **Step 3: Add real-data and log checks to release gate/docs**

Release check should include the real-data demo; docs should mention log summaries.

- [x] **Step 4: Run full verification**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON=$(which python3) python3 scripts/release_check.py --json
```

Expected: `status: passed`.
