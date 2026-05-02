# Next Experiment Plan Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a concrete `next_experiment_plan` to `experiment_state.code_change_plan` so Codex/Claude can make safer, more specific next-round code or hyperparameter edits.

**Architecture:** Reuse existing `research_review.recommended_search_space`, `experiment_strategy`, `best_result`, task metric metadata, and parsed SEARCH REGION. Keep the feature additive and deterministic.

**Tech Stack:** Python, stdio MCP JSON payloads, pytest, markdown docs.

---

### Task 1: Planner Payload

**Files:**
- Modify: `tests/unit/test_mcp_fusion_tools.py`
- Modify: `lib/fusion_service.py`

- [x] **Step 1: Write failing next-experiment-plan test**

Extend the clean planner-action review test to assert `code_change_plan.next_experiment_plan` includes `mode`, `metric`, `target_param`, `candidate_values`, `best_params`, `stop_conditions`, `edit_policy`, and `rationale`.

- [x] **Step 2: Run targeted test and confirm red**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest \
  tests/unit/test_mcp_fusion_tools.py::test_review_research_results_returns_planner_actions_for_clean_run -q
```

Expected: fail because `next_experiment_plan` does not exist yet.

- [x] **Step 3: Implement next experiment plan builder**

Add helper functions in `lib/fusion_service.py` and attach the plan only when `recommended_action == "tune_search_region"`.

- [x] **Step 4: Run focused tests**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest \
  tests/unit/test_mcp_fusion_tools.py::test_review_research_results_returns_planner_actions_for_clean_run \
  tests/unit/test_mcp_fusion_tools.py::test_review_research_results_recommends_dataset_fix_for_missing_real_file \
  tests/unit/test_mcp_fusion_tools.py::test_review_research_results_prioritizes_log_action_for_failures -q
```

### Task 2: Client Docs and Release

**Files:**
- Modify: `README.md`
- Modify: `docs/mcp-client-setup.md`
- Modify: `docs/client-planner-template.md`
- Modify: `docs/hybrid-mcp-architecture.md`
- Modify: `docs/release-checklist.md`

- [x] **Step 1: Document `next_experiment_plan`**

Document that clients should read `code_change_plan.next_experiment_plan` before manually editing SEARCH REGION parameters.

- [x] **Step 2: Run impacted tests**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest \
  tests/unit/test_mcp_fusion_tools.py \
  tests/unit/test_mcp_service.py \
  tests/unit/test_planner_docs.py \
  tests/integration/test_mcp_client_acceptance.py -q
```

- [x] **Step 3: Run full release gate**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON=$(which python3) python3 scripts/release_check.py --json
```

- [x] **Step 4: Commit**

Commit with:

```bash
git commit -m "feat: add next experiment plan"
```
