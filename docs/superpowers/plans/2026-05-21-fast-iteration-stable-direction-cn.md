# Fast Iteration Stable Direction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `ml-research-loop` 的优化能力从“手工跑几轮本地分数”升级为“5 轮以内自动发现稳定提升方向、识别失败并给出下一步 prompt/训练/蒸馏/回滚决策”的产品能力。

**Architecture:** 在现有 Smol AI WorldCup 本地评测链路之上新增一个轻量 iteration loop 层：它不替代 `smol_worldcup.py` 的 evaluator，而是负责编排候选 profile、记录每轮假设、做 dev/canary 决策、输出 direction-decision artifact。CLI/MCP 只暴露“运行有限轮迭代”和“汇总方向决策”两个入口，所有结果继续保持 `official_scores_claimed=false`。

**Tech Stack:** Python 3.13、pytest、现有 `lib/benchmarks/smol_worldcup.py`、现有 CLI/MCP、LM Studio OpenAI-compatible endpoint、JSON artifact。

---

## 背景判断

当前 Qwen3-8B 已完成一轮有价值但不充分的探索：

- `p3-dev-v2`：dev/canary 都提升，主要收益来自 confidence calibration，可作为当前默认候选。
- `p3-semantic-v1`：`llm_judge` 局部提升，但伤害 H 轴和 refusal balance，应作为失败/回滚样例。
- `p3-semantic-v2`：dev 有收益，canary 相对 `p3-dev-v2` 略降，应作为可选语义候选，不替代默认。

下一步不要继续靠人工临场判断，而要把这个过程产品化：每轮必须有假设、受控变量、dev 结果、canary gate、回滚决策和最终路线判断。

## 文件结构

- Create: `lib/benchmarks/smol_worldcup_iteration.py`
  - 负责 iteration plan schema、round comparison、stable direction decision、artifact writer。
- Modify: `lib/benchmarks/__init__.py`
  - 导出新的 iteration loop builder/writer。
- Modify: `scripts/cli.py`
  - 新增 `ml-loop hf-eval smol-worldcup-iteration-loop`。
- Modify: `lib/mcp_service.py`
  - 新增 MCP 工具 `run_smol_worldcup_iteration_loop`。
- Create: `tests/unit/test_smol_worldcup_iteration_loop.py`
  - 单元测试 iteration decision、失败回滚、dev/canary gate 和 artifact shape。
- Modify: `tests/unit/test_cli.py`
  - 覆盖新 CLI 参数解析。
- Modify: `tests/unit/test_mcp_service.py`
  - 覆盖新 MCP tool schema。
- Create: `docs/hf-evaluation/smol-worldcup-qwen3-8b-fast-iteration-20260521/README.md`
  - 记录 5 轮协议、候选方向、执行结果和产品边界。
- Modify: `docs/evidence/benchmark-results-index-cn.md`
  - 索引新的 fast iteration proof，不宣传官方成绩。

---

### Task 1: 定义 5 轮稳定方向协议

**Files:**
- Create: `lib/benchmarks/smol_worldcup_iteration.py`
- Test: `tests/unit/test_smol_worldcup_iteration_loop.py`

- [ ] **Step 1: Write failing test for decision schema**

Add this test:

```python
from lib.benchmarks.smol_worldcup_iteration import build_direction_decision


def test_direction_decision_marks_stable_improvement_when_dev_and_canary_improve():
    decision = build_direction_decision(
        baseline={"SHIFT": 80.0, "H": 90.0, "I": 73.0, "failure_count": 35},
        dev={"SHIFT": 81.2, "H": 90.0, "I": 75.0, "failure_count": 34},
        canary={"SHIFT": 80.7, "H": 90.0, "I": 74.0, "failure_count": 34},
        target_category="confidence_calibration",
        h_axis_drop_limit=1.0,
        canary_shift_drop_limit=0.0,
    )

    assert decision["status"] == "stable_improvement"
    assert decision["recommended_next_action"] == "promote_candidate_profile"
    assert decision["official_scores_claimed"] is False
```

- [ ] **Step 2: Verify RED**

Run:

```bash
.venv/bin/python -m pytest -q tests/unit/test_smol_worldcup_iteration_loop.py::test_direction_decision_marks_stable_improvement_when_dev_and_canary_improve
```

Expected: `ImportError` because `lib.benchmarks.smol_worldcup_iteration` does not exist.

- [ ] **Step 3: Implement minimal decision builder**

Create `lib/benchmarks/smol_worldcup_iteration.py` with:

```python
from __future__ import annotations

from typing import Any


def build_direction_decision(
    *,
    baseline: dict[str, Any],
    dev: dict[str, Any],
    canary: dict[str, Any] | None,
    target_category: str,
    h_axis_drop_limit: float = 1.0,
    canary_shift_drop_limit: float = 0.0,
) -> dict[str, Any]:
    dev_delta = _delta(dev, baseline)
    canary_delta = _delta(canary, baseline) if canary is not None else None
    h_drop = float(baseline.get("H", 0.0)) - float(dev.get("H", 0.0))
    canary_passed = (
        canary_delta is not None
        and float(canary_delta["SHIFT"]) >= canary_shift_drop_limit
        and float(canary_delta["H"]) >= -h_axis_drop_limit
    )
    if dev_delta["SHIFT"] > 0 and h_drop <= h_axis_drop_limit and canary_passed:
        status = "stable_improvement"
        next_action = "promote_candidate_profile"
    elif dev_delta["SHIFT"] > 0:
        status = "dev_only_improvement"
        next_action = "keep_as_candidate_do_not_promote"
    else:
        status = "failed_or_regressed"
        next_action = "rollback_candidate"
    return {
        "status": status,
        "target_category": target_category,
        "dev_delta": dev_delta,
        "canary_delta": canary_delta,
        "recommended_next_action": next_action,
        "official_scores_claimed": False,
    }


def _delta(current: dict[str, Any] | None, baseline: dict[str, Any]) -> dict[str, Any]:
    if current is None:
        return {}
    return {
        "SHIFT": round(float(current.get("SHIFT", 0.0)) - float(baseline.get("SHIFT", 0.0)), 6),
        "H": round(float(current.get("H", 0.0)) - float(baseline.get("H", 0.0)), 6),
        "I": round(float(current.get("I", 0.0)) - float(baseline.get("I", 0.0)), 6),
        "failure_count": int(current.get("failure_count", 0)) - int(baseline.get("failure_count", 0)),
    }
```

- [ ] **Step 4: Verify GREEN**

Run:

```bash
.venv/bin/python -m pytest -q tests/unit/test_smol_worldcup_iteration_loop.py
```

Expected: pass.

---

### Task 2: 支持失败与回滚证据

**Files:**
- Modify: `lib/benchmarks/smol_worldcup_iteration.py`
- Test: `tests/unit/test_smol_worldcup_iteration_loop.py`

- [ ] **Step 1: Write failing tests for rollback classifications**

Add:

```python
from lib.benchmarks.smol_worldcup_iteration import build_direction_decision


def test_direction_decision_rolls_back_when_h_axis_regresses():
    decision = build_direction_decision(
        baseline={"SHIFT": 80.0, "H": 92.0, "I": 72.0, "failure_count": 35},
        dev={"SHIFT": 79.8, "H": 84.0, "I": 77.0, "failure_count": 42},
        canary=None,
        target_category="llm_judge",
        h_axis_drop_limit=1.0,
    )

    assert decision["status"] == "failed_or_regressed"
    assert decision["recommended_next_action"] == "rollback_candidate"


def test_direction_decision_keeps_dev_only_candidate_when_canary_does_not_confirm():
    decision = build_direction_decision(
        baseline={"SHIFT": 81.0, "H": 92.0, "I": 74.0, "failure_count": 35},
        dev={"SHIFT": 82.0, "H": 92.0, "I": 75.0, "failure_count": 36},
        canary={"SHIFT": 80.7, "H": 92.0, "I": 73.0, "failure_count": 34},
        target_category="multilingual",
    )

    assert decision["status"] == "dev_only_improvement"
    assert decision["recommended_next_action"] == "keep_as_candidate_do_not_promote"
```

- [ ] **Step 2: Verify RED**

Run:

```bash
.venv/bin/python -m pytest -q tests/unit/test_smol_worldcup_iteration_loop.py
```

Expected: at least one assertion fails if the current logic does not distinguish rollback/dev-only correctly.

- [ ] **Step 3: Implement explicit rollback reasons**

Extend returned decision with:

```python
"rollback_reasons": [
    "h_axis_regression",
    "canary_not_confirmed",
]
```

Rules:

- Add `h_axis_regression` when H drops more than `h_axis_drop_limit`.
- Add `canary_not_confirmed` when dev improves but canary does not meet gate.
- Add `failure_count_increased` when failure count increases by more than 2.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
.venv/bin/python -m pytest -q tests/unit/test_smol_worldcup_iteration_loop.py
```

Expected: pass.

---

### Task 3: 生成 5 轮 iteration proof artifact

**Files:**
- Modify: `lib/benchmarks/smol_worldcup_iteration.py`
- Test: `tests/unit/test_smol_worldcup_iteration_loop.py`

- [ ] **Step 1: Write failing test for artifact writer**

Add:

```python
import json
from pathlib import Path

from lib.benchmarks.smol_worldcup_iteration import write_iteration_loop_report


def test_write_iteration_loop_report_records_rounds_and_best_direction(tmp_path: Path):
    report = write_iteration_loop_report(
        tmp_path,
        baseline={"run_id": "baseline", "SHIFT": 80.0, "H": 90.0, "I": 73.0, "failure_count": 35},
        rounds=[
            {
                "round_id": "round-001",
                "candidate_profile": "p3-dev-v2",
                "target_category": "confidence_calibration",
                "dev": {"SHIFT": 81.0, "H": 90.0, "I": 74.0, "failure_count": 34},
                "canary": {"SHIFT": 80.8, "H": 90.0, "I": 74.0, "failure_count": 34},
            }
        ],
        max_rounds=5,
    )

    report_path = Path(report["iteration_report_path"])
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    assert payload["max_rounds"] == 5
    assert payload["best_direction"]["status"] == "stable_improvement"
    assert payload["official_scores_claimed"] is False
```

- [ ] **Step 2: Verify RED**

Run:

```bash
.venv/bin/python -m pytest -q tests/unit/test_smol_worldcup_iteration_loop.py::test_write_iteration_loop_report_records_rounds_and_best_direction
```

Expected: fail because writer is missing.

- [ ] **Step 3: Implement writer**

Write:

- `iteration-loop-report.json`
- `direction-decision.json`
- `rounds.json`

Each artifact must include:

- `official_scores_claimed=false`
- `claim_boundary`
- `max_rounds`
- `round_count`
- `best_direction`
- `rollback_rounds`
- `recommended_scale_path`

- [ ] **Step 4: Verify GREEN**

Run:

```bash
.venv/bin/python -m pytest -q tests/unit/test_smol_worldcup_iteration_loop.py
```

Expected: pass.

---

### Task 4: 暴露 CLI/MCP 入口

**Files:**
- Modify: `lib/benchmarks/__init__.py`
- Modify: `scripts/cli.py`
- Modify: `lib/mcp_service.py`
- Test: `tests/unit/test_cli.py`
- Test: `tests/unit/test_mcp_service.py`

- [ ] **Step 1: Write failing CLI parser test**

In `tests/unit/test_cli.py`, add parse coverage:

```python
hf_eval_iteration_args = parser.parse_args([
    "hf-eval",
    "smol-worldcup-iteration-loop",
    "--output-dir",
    "/tmp/hf-smol-iteration",
    "--baseline-report",
    "/tmp/baseline/smol-worldcup-model-eval-report.json",
    "--round-report",
    "/tmp/round1/smol-worldcup-model-eval-report.json",
    "--max-rounds",
    "5",
    "--json",
])
assert hf_eval_iteration_args.hf_eval_command == "smol-worldcup-iteration-loop"
assert hf_eval_iteration_args.max_rounds == 5
```

- [ ] **Step 2: Verify RED**

Run:

```bash
.venv/bin/python -m pytest -q tests/unit/test_cli.py::test_parser_has_run_status_result_subcommands
```

Expected: fail because the command does not exist.

- [ ] **Step 3: Implement CLI command**

Add command:

```bash
ml-loop hf-eval smol-worldcup-iteration-loop \
  --output-dir .demo_runs/hf-eval/smol-worldcup-qwen3-fast-iteration \
  --baseline-report .demo_runs/hf-eval/smol-worldcup-qwen3-8b-nothink-full-20260521/smol-worldcup-model-eval-report.json \
  --round-report .demo_runs/hf-eval/smol-worldcup-qwen3-8b-nothink-dev-round-002-dev-v2-20260521/smol-worldcup-model-eval-report.json \
  --round-report .demo_runs/hf-eval/smol-worldcup-qwen3-8b-nothink-dev-round-003-semantic-v1-20260521/smol-worldcup-model-eval-report.json \
  --round-report .demo_runs/hf-eval/smol-worldcup-qwen3-8b-nothink-dev-round-004-semantic-v2-20260521/smol-worldcup-model-eval-report.json \
  --max-rounds 5 \
  --json
```

- [ ] **Step 4: Add MCP tool schema**

Add `run_smol_worldcup_iteration_loop` with:

- `output_dir`
- `baseline_report`
- `round_reports`
- `max_rounds`
- `claim_boundary`

- [ ] **Step 5: Verify GREEN**

Run:

```bash
.venv/bin/python -m pytest -q tests/unit/test_cli.py tests/unit/test_mcp_service.py
```

Expected: pass.

---

### Task 5: 生成当前 Qwen3 5 轮方向发现 proof

**Files:**
- Create: `docs/hf-evaluation/smol-worldcup-qwen3-8b-fast-iteration-20260521/README.md`
- Modify: `docs/evidence/benchmark-results-index-cn.md`

- [ ] **Step 1: Run iteration summary on existing rounds**

Run:

```bash
.venv/bin/python scripts/cli.py hf-eval smol-worldcup-iteration-loop \
  --output-dir .demo_runs/hf-eval/smol-worldcup-qwen3-8b-fast-iteration-20260521 \
  --baseline-report .demo_runs/hf-eval/smol-worldcup-qwen3-8b-nothink-full-20260521/smol-worldcup-model-eval-report.json \
  --round-report .demo_runs/hf-eval/smol-worldcup-qwen3-8b-nothink-dev-round-002-dev-v2-20260521/smol-worldcup-model-eval-report.json \
  --round-report .demo_runs/hf-eval/smol-worldcup-qwen3-8b-nothink-dev-round-003-semantic-v1-20260521/smol-worldcup-model-eval-report.json \
  --round-report .demo_runs/hf-eval/smol-worldcup-qwen3-8b-nothink-dev-round-004-semantic-v2-20260521/smol-worldcup-model-eval-report.json \
  --max-rounds 5 \
  --json
```

Expected:

- `status=written`
- `official_scores_claimed=false`
- `best_direction` is `p3-dev-v2` or `p3-semantic-v2` with caveat depending canary gate.

- [ ] **Step 2: Write Chinese evidence doc**

Create README with sections:

- 目标：5 轮内找稳定提升方向。
- 当前已用轮次：baseline、`p3-dev-v2`、`p3-semantic-v1`、`p3-semantic-v2`。
- 成功方向：confidence calibration / output contract。
- 失败方向：broad semantic routing。
- 候选方向：bounded semantic multilingual routing。
- 下一步 scale path：先 prompt 小步，若多语种仍不稳，转训练数据/微调。

- [ ] **Step 3: Update benchmark index**

Add one row:

```markdown
| Smol AI WorldCup Qwen3-8B 快速迭代方向发现 | `docs/hf-evaluation/smol-worldcup-qwen3-8b-fast-iteration-20260521/README.md` | 5 轮协议内已验证 1 个稳定方向、1 个失败回滚、1 个候选方向 | 本地诊断和产品能力 proof；不是官方成绩 |
```

- [ ] **Step 4: Verify docs and tests**

Run:

```bash
git diff --check
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check lib/benchmarks/smol_worldcup_iteration.py scripts/cli.py lib/mcp_service.py tests/unit/test_smol_worldcup_iteration_loop.py
```

Expected:

- `git diff --check` no output
- pytest passes
- ruff passes

---

## 验收标准

本阶段完成后，项目应能证明：

- 不是只会跑本地分数，而是能把多轮实验归纳为方向决策。
- 5 轮以内至少产出：
  - 1 个稳定提升方向；
  - 1 个失败/回滚方向；
  - 1 个可选候选方向；
  - 1 个下一步规模化路线判断。
- 每个结论都有 dev/canary 或明确边界支持。
- 所有 artifact 都保留 `official_scores_claimed=false`。
- Codex/Claude 可通过 MCP 触发同一套 iteration loop。

## 后续路线

如果 `p3-dev-v2` 仍是唯一稳定方向：

- 短期：把 calibration/output contract 作为默认可靠方向继续细化。
- 中期：从 failure cases 自动抽取训练样本，进入 Qwen3 LoRA/轻量微调试点。
- 长期：用同一 iteration loop 支持论文复现任务中的 prompt、代码 patch、超参、训练数据四类 proposal。

如果 `p3-semantic-v2` 后续 canary 反复不稳：

- 不继续扩大 semantic prompt；
- 转向多语种专项数据增强或模型微调；
- 引入独立 judge / 人工抽样，降低 `llm_judge` 口径噪声。
