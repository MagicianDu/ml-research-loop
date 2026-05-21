# Smol WorldCup 评测严谨性 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 为 Smol AI WorldCup 本地评测补齐 leakage audit、dev/canary split 和独立 judge 配置，降低泄题、同集调参和自评偏差风险。

**Architecture:** 在现有 `lib/benchmarks/smol_worldcup.py` 内增加小而明确的评测严谨性工具函数，CLI/MCP 只暴露必要参数和 artifact 输出。所有新能力默认保持 `official_scores_claimed=false`，并在文档中明确“当前 canary 从此版本后才可作为未来 untouched holdout”。

**Tech Stack:** Python 3.13、pytest、现有 MCP stdio 工具、现有 Hugging Face dataset viewer adapter。

---

### Task 1: Leakage Audit

**Files:**
- Modify: `lib/benchmarks/smol_worldcup.py`
- Modify: `scripts/cli.py`
- Modify: `lib/mcp_service.py`
- Test: `tests/unit/test_smol_worldcup_baseline.py`
- Test: `tests/unit/test_hf_external_eval.py`

- [x] **Step 1: Write failing tests**

Add tests asserting `audit_smol_worldcup_prompt_leakage` reports pass for normal prompts and fails when a generated prompt contains `answer_key` / `grading_rule` / `test_case` / `correct_answer`.

- [x] **Step 2: Verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_smol_worldcup_baseline.py::test_prompt_leakage_audit_detects_evaluation_only_terms -q
```

Expected: fail because the audit function does not exist yet.

- [x] **Step 3: Implement audit**

Add `build_smol_worldcup_prompt_leakage_audit(rows, prompt_profile=...)` and `write_smol_worldcup_prompt_leakage_audit(...)`. The audit must build model prompts through the same `_build_model_messages` path used by real eval, check forbidden evaluation-only terms, and return `status=passed` only when `leak_count=0`.

- [x] **Step 4: Verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_smol_worldcup_baseline.py tests/unit/test_hf_external_eval.py -q
```

Expected: pass.

### Task 2: Deterministic Dev/Canary Split

**Files:**
- Modify: `lib/benchmarks/smol_worldcup.py`
- Modify: `scripts/cli.py`
- Modify: `lib/mcp_service.py`
- Test: `tests/unit/test_smol_worldcup_baseline.py`
- Test: `tests/unit/test_cli.py`

- [x] **Step 1: Write failing tests**

Add tests for deterministic `dev` and `canary` row selection. The split must be stable by row id, expose `evaluation_split` in output artifacts, and reject unsupported split names.

- [x] **Step 2: Verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_smol_worldcup_baseline.py::test_model_eval_supports_deterministic_dev_canary_split -q
```

Expected: fail because split selection is not implemented.

- [x] **Step 3: Implement split**

Add `evaluation_split` to baseline/model eval writers with choices `all`, `dev`, `canary`. Use deterministic modulo by row id hash, default canary fraction `0.2`, and preserve current default behavior as `all`.

- [x] **Step 4: Verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_smol_worldcup_baseline.py tests/unit/test_cli.py -q
```

Expected: pass.

### Task 3: Independent Judge Guardrails

**Files:**
- Modify: `lib/benchmarks/smol_worldcup.py`
- Modify: `scripts/cli.py`
- Modify: `lib/mcp_service.py`
- Test: `tests/unit/test_smol_worldcup_baseline.py`
- Test: `tests/unit/test_hf_external_eval.py`

- [x] **Step 1: Write failing tests**

Add tests for `judge_independence` metadata: same model/base URL should be marked `self_judge`, different model or different endpoint should be marked `independent_judge_configured`.

- [x] **Step 2: Verify RED**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_smol_worldcup_baseline.py::test_model_eval_records_judge_independence_metadata -q
```

Expected: fail because metadata is absent.

- [x] **Step 3: Implement guardrail**

Add `judge_independence` metadata to model eval output. Preserve `judge_mode=openai-compatible`, but report self-judge risk when judge and subject are identical. Do not block same-model smoke runs; mark them honestly.

- [x] **Step 4: Verify GREEN**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_smol_worldcup_baseline.py tests/unit/test_hf_external_eval.py -q
```

Expected: pass.

### Task 4: Docs And Release Verification

**Files:**
- Modify: `docs/hf-evaluation/smol-worldcup-p3-round-003-judge/README.md`
- Modify: `docs/hf-evaluation/hf-external-eval-track-cn.md`
- Modify: `docs/evidence/benchmark-results-index-cn.md`
- Modify: `skills/ml-research-loop-planner/SKILL.md`
- Modify: `skills/ml-research-loop-operator/SKILL.md`

- [x] **Step 1: Update docs**

Document that current historical round-001/002/003 used all 125 public rows, so newly created canary split only counts as a future untouched holdout after this version.

- [x] **Step 2: Run final verification**

Run:

```bash
.venv/bin/python -m pytest tests/unit/test_smol_worldcup_baseline.py tests/unit/test_cli.py tests/unit/test_hf_external_eval.py tests/unit/test_mcp_service.py tests/unit/test_skill_packages.py -q
.venv/bin/python -m ruff check lib/benchmarks/smol_worldcup.py lib/mcp_service.py scripts/cli.py scripts/hf_smol_worldcup_model_eval.py tests/unit/test_smol_worldcup_baseline.py tests/unit/test_cli.py tests/unit/test_hf_external_eval.py
.venv/bin/python -m pytest -q
.venv/bin/python scripts/release_check.py --skip-golden-path --json
git diff --check
```

Expected: all pass. If warnings remain, report them explicitly.
