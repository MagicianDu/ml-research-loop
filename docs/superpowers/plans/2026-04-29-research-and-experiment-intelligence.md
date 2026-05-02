# Research And Experiment Intelligence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve research evidence quality and autoresearch next-iteration intelligence without changing the MCP client contract.

**Architecture:** Add optional filesystem caching and deterministic evidence-quality metadata to the research layer. Add dataset profiling and code-change planning to `review_research_results` so Codex/Claude can make better next-round edits while MCP remains the executor.

**Tech Stack:** Python stdio MCP service, JSON cache files, pytest, ruff, markdown docs.

---

### Task 1: Research Cache And Evidence Quality

**Files:**
- Modify: `ml_intern/research_tools.py`
- Modify: `lib/fusion_service.py`
- Modify: `lib/mcp_service.py`
- Modify: `tests/unit/test_research_tools.py`
- Modify: `tests/unit/test_mcp_fusion_tools.py`
- Modify: `.gitignore`

- [x] **Step 1: Write failing cache tests**

Add unit tests for `cached_search()` and `research_task` with a `cache_dir`.

- [x] **Step 2: Verify cache tests fail**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest \
  tests/unit/test_research_tools.py::test_cached_search_reuses_json_cache \
  tests/unit/test_mcp_fusion_tools.py::test_research_task_reports_cache_and_evidence_quality -q
```

Expected: fail because cache helpers and payload fields are missing.

- [x] **Step 3: Implement cache helpers and payload metadata**

Implement JSON cache helper functions and thread optional `cache_dir` through `research_task`.

- [x] **Step 4: Verify Task 1**

Run the same targeted tests and expect pass.

### Task 2: Dataset Profile And Code Change Plan

**Files:**
- Modify: `lib/fusion_service.py`
- Modify: `tests/unit/test_mcp_fusion_tools.py`

- [x] **Step 1: Write failing experiment-intelligence tests**

Assert `review_research_results` returns `experiment_state.dataset_profile` and `experiment_state.code_change_plan`.

- [x] **Step 2: Verify experiment-intelligence tests fail**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest \
  tests/unit/test_mcp_fusion_tools.py::test_review_research_results_profiles_dataset_and_suggests_code_change -q
```

Expected: fail because the new state fields are missing.

- [x] **Step 3: Implement dataset profiling and deterministic change planning**

Use task config from the runtime root when available, workspace search region, best result, failed experiments, and dataset file metadata.

- [x] **Step 4: Verify Task 2**

Run the targeted test and expect pass.

### Task 3: Docs, Release Gate, And Commit

**Files:**
- Modify: `README.md`
- Modify: `docs/mcp-client-setup.md`
- Modify: `docs/release-checklist.md`
- Modify: `scripts/mcp_client_acceptance.py`
- Modify: `tests/integration/test_mcp_client_acceptance.py`

- [x] **Step 1: Document the new planning signals**

Document cache/evidence quality, dataset profile, and code-change plan.

- [x] **Step 2: Add acceptance assertions**

Update the client acceptance script/test to verify the manifest advertises these planning signals.

- [x] **Step 3: Run full release check**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON=$(which python3) python3 scripts/release_check.py --json
```

Expected: `status: passed`.

- [x] **Step 4: Commit**

Commit message:

```bash
git commit -m "feat: improve research evidence and experiment planning"
```
