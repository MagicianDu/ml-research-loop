# FastText P3 Client Patch Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first P3 loop where Codex/Claude proposes a bounded fastText hyperparameter change and ML Research Loop executes, evaluates, compares, and archives the result.

**Architecture:** Keep the MCP server as executor and the client model as planner. The server accepts a constrained fastText proposal object, validates it against an allowlist, runs the selected fastText-compatible binary, compares against an existing baseline report, writes patch/proof artifacts, and returns a continue/stop handoff. This is hyperparameter-proposal execution, not arbitrary code self-modification.

**Tech Stack:** Python stdlib, existing `lib/full_reproduction_harness.py`, `scripts/full_reproduction_run.py`, MCP stdio service, pytest, ruff.

---

### Task 1: Core FastText Patch Round

**Files:**
- Modify: `lib/full_reproduction_harness.py`
- Test: `tests/integration/test_full_reproduction_harness.py`

- [ ] **Step 1: Write failing tests**

Add a test that creates a fake fastText binary whose `test` score improves when the training command includes `-wordNgrams 2`. The test must call `run_fasttext_patch_round(...)` with a baseline report, assert `delta > 0`, and assert these artifacts exist: `patch-proposal.json`, `patch-diff.patch`, `improvement-report.json`, `logs/fasttext-patch-train.log`, `logs/fasttext-patch-test.log`, and `client-handoff.json`.

- [ ] **Step 2: Run RED**

Run:

```bash
.venv/bin/python -m pytest tests/integration/test_full_reproduction_harness.py::test_run_fasttext_patch_round_compares_to_baseline_and_archives_artifacts -q
```

Expected: fail because `run_fasttext_patch_round` is not defined.

- [ ] **Step 3: Implement minimal core**

Add:

- `FASTTEXT_PATCH_ALLOWED_ARGS`
- proposal validation for `-lr`, `-epoch`, `-wordNgrams`, `-dim`, `-minCount`, `-loss`
- fixed deterministic args `-thread 1 -seed 0`
- `run_fasttext_patch_round(...)`
- `improvement-report.json`, `patch-diff.patch`, and `client-handoff.json`

- [ ] **Step 4: Run GREEN**

Run the same targeted test and then:

```bash
.venv/bin/python -m pytest tests/integration/test_full_reproduction_harness.py -q
```

### Task 2: CLI and Release Gate

**Files:**
- Modify: `scripts/full_reproduction_run.py`
- Modify: `scripts/release_check.py`
- Test: `tests/integration/test_full_reproduction_harness.py`

- [ ] **Step 1: Write failing CLI test**

Add a CLI test for:

```bash
python scripts/full_reproduction_run.py \
  --target-spec docs/reproduction-pilot/full-reproduction-target.json \
  --output-dir <tmp>/cli-patch-round \
  --run-fasttext-patch-round \
  --ag-news-train-csv <tmp>/train.csv \
  --ag-news-test-csv <tmp>/test.csv \
  --fasttext-binary <tmp>/fasttext \
  --baseline-report <tmp>/baseline/fasttext-baseline-report.json \
  --fasttext-proposal <tmp>/proposal.json \
  --json
```

Expected: fail because the CLI mode does not exist.

- [ ] **Step 2: Implement CLI**

Add `--run-fasttext-patch-round`, `--baseline-report`, and `--fasttext-proposal`. Validate required arguments before calling `run_fasttext_patch_round`.

- [ ] **Step 3: Extend release gate**

Add a release-check command `full-reproduction-fasttext-patch-round` using fixture CSVs, fake fastText binary, baseline report from the existing binary baseline output, and a proposal JSON.

### Task 3: MCP and Skills Contract

**Files:**
- Modify: `lib/mcp_service.py`
- Modify: `tests/unit/test_mcp_service.py`
- Modify: `skills/ml-research-loop-experiment-optimizer/SKILL.md`
- Modify: `skills/ml-research-loop-reproduction/SKILL.md`

- [ ] **Step 1: Write failing MCP tests**

Add tests that `tools/list` exposes `run_fasttext_patch_round`, the service manifest includes it in `required_tools`, and direct tool execution returns an `improvement_report` without claiming official scores.

- [ ] **Step 2: Implement MCP tool**

Add a path-checked MCP handler that accepts:

- `target_spec`
- `output_dir`
- `ag_news_train_csv`
- `ag_news_test_csv`
- `fasttext_binary`
- `baseline_report`
- `proposal`
- optional `max_train_seconds`

- [ ] **Step 3: Update skills**

Document that reproduction/optimizer clients use `run_fasttext_patch_round` after a trusted fastText baseline, and that they must keep `official_scores_claimed=false` unless an official scorer proof exists.

### Task 4: Docs, Verification, Commit

**Files:**
- Modify: `README.md`
- Modify: `docs/evidence/benchmark-results-index-cn.md`
- Modify: `docs/evidence/autonomous-product-proof-matrix-cn.md`
- Modify: `docs/reproduction-pilot/full-reproduction-fasttext-target-cn.md`

- [ ] **Step 1: Update Chinese docs**

Describe P3 as “可信 baseline 上的受控客户端 proposal loop”，not as fully automatic research replacement.

- [ ] **Step 2: Verify**

Run:

```bash
.venv/bin/ruff check .
.venv/bin/python -m pytest tests/integration/test_full_reproduction_harness.py tests/unit/test_mcp_service.py -q
.venv/bin/python scripts/release_check.py --json
.venv/bin/python -m pytest -q
```

- [ ] **Step 3: Review and commit**

Review diff for overclaims, large artifacts, and path/security issues. Commit and push after all checks pass.
