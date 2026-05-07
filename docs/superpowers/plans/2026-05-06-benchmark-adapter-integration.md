# Benchmark Adapter Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Integrate the MLE-bench and PaperBench compatibility spikes into one branch with shared exports, docs, tests, and demo-level validation.

**Architecture:** Keep benchmark adapters dependency-free under `lib/benchmarks/`. Treat each public benchmark direction as a separate adapter module, while exposing both through `lib/benchmarks/__init__.py` and documenting that the current milestone proves compatibility shape, not official scores.

**Tech Stack:** Python standard library, existing ML Research Loop demo runner, existing reproduction protocol, pytest, ruff, Markdown docs.

---

## File Structure

- Create: `docs/superpowers/specs/2026-05-06-benchmark-adapter-integration.md`
  - Integration scope, acceptance criteria, and follow-up public benchmark path.
- Create: `docs/superpowers/plans/2026-05-06-benchmark-adapter-integration.md`
  - Task checklist for this integration.
- Create: `docs/benchmark-adapter-roadmap-cn.md`
  - Chinese product-facing explanation of current compatibility layer and the gap to official public benchmark runs.
- Create/merge: `lib/benchmarks/__init__.py`
  - Re-export MLE-bench and PaperBench adapter helpers.
- Create: `lib/benchmarks/mle_bench.py`
  - Deterministic MLE-bench-shaped fixture, submission writer, report builder.
- Create: `lib/benchmarks/paperbench.py`
  - Deterministic PaperBench-shaped fixture, reproduction spec mapping, grading report builder.
- Create: `scripts/mle_bench_adapter_demo.py`
  - CLI demo for MLE-bench-shaped artifacts.
- Create: `scripts/paperbench_adapter_demo.py`
  - CLI demo for PaperBench-shaped artifacts.
- Modify: `examples/README.md`
  - Add both adapter demo commands.
- Modify: `docs/development-roadmap-cn.md`
  - Add benchmark adapter path after P12.
- Modify: `docs/productization-todos.md`
  - Add P13-P15 public benchmark proof TODOs.
- Test: `tests/unit/test_mle_bench_adapter.py`
- Test: `tests/unit/test_paperbench_adapter.py`
- Test: `tests/integration/test_mle_bench_adapter_demo.py`
- Test: `tests/integration/test_paperbench_adapter_demo.py`

### Task 1: Prepare Integration Worktree

**Files:**
- Worktree: `.worktrees/benchmark-adapter-integration`

- [x] **Step 1: Verify `.worktrees` is ignored**

Run:

```bash
git check-ignore -q .worktrees && echo ignored
```

Expected: `ignored`

- [x] **Step 2: Create the integration worktree**

Run:

```bash
git worktree add .worktrees/benchmark-adapter-integration -b codex/benchmark-adapter-integration main
```

Expected: worktree created from `main`.

### Task 2: Merge MLE-bench Spike

**Files:**
- Create: `lib/benchmarks/mle_bench.py`
- Create/merge: `lib/benchmarks/__init__.py`
- Create: `scripts/mle_bench_adapter_demo.py`
- Create: `tests/unit/test_mle_bench_adapter.py`
- Create: `tests/integration/test_mle_bench_adapter_demo.py`
- Modify: `examples/README.md`
- Modify: `docs/development-roadmap-cn.md`

- [x] **Step 1: Merge the branch**

Run:

```bash
git merge --no-ff codex/mle-bench-spike
```

Expected: merge completes or reports only straightforward documentation/export conflicts.

- [x] **Step 2: Run focused validation**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest \
  tests/unit/test_mle_bench_adapter.py \
  tests/integration/test_mle_bench_adapter_demo.py -q
```

Expected: MLE adapter tests pass.

### Task 3: Merge PaperBench Spike

**Files:**
- Create: `lib/benchmarks/paperbench.py`
- Merge: `lib/benchmarks/__init__.py`
- Create: `scripts/paperbench_adapter_demo.py`
- Create: `tests/unit/test_paperbench_adapter.py`
- Create: `tests/integration/test_paperbench_adapter_demo.py`
- Modify: `examples/README.md`
- Modify: `docs/development-roadmap-cn.md`

- [x] **Step 1: Merge the branch**

Run:

```bash
git merge --no-ff codex/paperbench-spike
```

Expected: conflict in shared docs or `lib/benchmarks/__init__.py` is resolved by preserving both adapter families.

- [x] **Step 2: Resolve `lib/benchmarks/__init__.py` with both export sets**

Use:

```python
"""Benchmark adapter helpers."""

from lib.benchmarks.mle_bench import (
    MLEBenchFixture,
    build_mle_bench_report,
    materialize_mle_bench_fixture,
    write_mle_bench_submission,
)
from lib.benchmarks.paperbench import (
    PaperBenchFixture,
    build_paperbench_report,
    build_reproduction_spec,
    grade_paperbench_fixture,
    materialize_paperbench_fixture,
    write_json,
)

__all__ = [
    "MLEBenchFixture",
    "PaperBenchFixture",
    "build_mle_bench_report",
    "build_paperbench_report",
    "build_reproduction_spec",
    "grade_paperbench_fixture",
    "materialize_mle_bench_fixture",
    "materialize_paperbench_fixture",
    "write_json",
    "write_mle_bench_submission",
]
```

- [x] **Step 3: Run focused validation**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest \
  tests/unit/test_mle_bench_adapter.py \
  tests/unit/test_paperbench_adapter.py \
  tests/integration/test_mle_bench_adapter_demo.py \
  tests/integration/test_paperbench_adapter_demo.py -q
```

Expected: both adapter families pass.

### Task 4: Add Product-Facing Benchmark Roadmap

**Files:**
- Create: `docs/benchmark-adapter-roadmap-cn.md`
- Modify: `README.md`
- Modify: `docs/productization-todos.md`
- Modify: `docs/development-roadmap-cn.md`
- Modify: `examples/README.md`

- [x] **Step 1: Create the Chinese roadmap**

Write a short document with these sections:

```markdown
# Benchmark Adapter Roadmap

## 当前已证明

...

## 尚未证明

...

## 下一步路线

...
```

- [x] **Step 2: Link the roadmap from README**

Add one bullet near the existing product docs:

```markdown
- Benchmark adapter roadmap: [docs/benchmark-adapter-roadmap-cn.md](docs/benchmark-adapter-roadmap-cn.md)
```

- [x] **Step 3: Add P13-P15 TODOs**

Append:

```markdown
## P13: Benchmark Adapter Productization

- [ ] Add a combined benchmark compatibility smoke.
- [ ] Surface benchmark readiness through CLI or manifest output.

## P14: Official Harness Feasibility

- [ ] Add read-only official harness probes for MLE-bench and PaperBench.
- [ ] Document required credentials, data, runtime, and cost.

## P15: Public Proof Run

- [ ] Run one official or official-debug benchmark path.
- [ ] Publish artifacts and limitations without overstating scores.
```

### Task 5: Final Verification And Commit

**Files:**
- All merged and new files.

- [x] **Step 1: Run lint**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m ruff check lib/ scripts/ tests/
```

Expected: `All checks passed!`

- [x] **Step 2: Run full tests**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON=/opt/homebrew/Caskroom/miniforge/base/bin/python3 \
/opt/homebrew/Caskroom/miniforge/base/bin/python3 -m pytest tests/ -q
```

Expected: full suite passes.

- [x] **Step 3: Run both adapter demos**

Run:

```bash
RUNTIME_ROOT=$(mktemp -d /tmp/mlrl-mle-integration.XXXXXX)
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON=/opt/homebrew/Caskroom/miniforge/base/bin/python3 \
/opt/homebrew/Caskroom/miniforge/base/bin/python3 scripts/mle_bench_adapter_demo.py \
  --runtime-root "$RUNTIME_ROOT" --json

RUNTIME_ROOT=$(mktemp -d /tmp/mlrl-paperbench-integration.XXXXXX)
PYTHONPATH=.:.venv/lib/python3.13/site-packages \
ML_RESEARCH_LOOP_PYTHON=/opt/homebrew/Caskroom/miniforge/base/bin/python3 \
/opt/homebrew/Caskroom/miniforge/base/bin/python3 scripts/paperbench_adapter_demo.py \
  --runtime-root "$RUNTIME_ROOT" --json
```

Expected: MLE returns `status=completed`; PaperBench returns `status=passed`.

- [x] **Step 4: Review and commit**

Run:

```bash
git diff --check
git status --short
git add .
git commit -m "Integrate benchmark adapter spikes"
git push -u origin codex/benchmark-adapter-integration
```

Expected: clean branch pushed for review.
