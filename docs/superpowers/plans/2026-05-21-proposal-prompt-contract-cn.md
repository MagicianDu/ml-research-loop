# Proposal Prompt Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把调研报告中的 proposal prompt 思路产品化为可验证的客户端规划器契约，让 Codex/Claude 基于 artifacts 生成结构化 proposal，并让 MCP/CLI 负责校验、上下文打包和反思归档。

**Architecture:** 新增一个独立 `lib/proposal_contract.py`，只做 schema、上下文打包、proposal 校验和 reflection artifact，不执行实验、不调用 LLM。CLI/MCP 暴露同一组只读/校验工具，skills/docs 描述客户端使用流程；实验执行仍由现有 `run_client_patch_experiment`、`apply_client_code_patch`、`run_fasttext_multi_proposal_loop` 等工具完成。

**Tech Stack:** Python 3.13、标准库 JSON/Path、pytest、现有 `scripts/cli.py`、`lib/mcp_service.py`、现有 MCP schema 风格。

---

## 文件结构

- Create: `lib/proposal_contract.py`
  - 负责 proposal prompt contract、context builder、proposal validator、reflection builder、artifact writer。
- Create: `tests/unit/test_proposal_contract.py`
  - 覆盖 contract shape、context artifact、proposal validation、reflection failure labels。
- Modify: `scripts/cli.py`
  - 新增 `proposal context`、`proposal validate`、`proposal reflect` 三个子命令。
- Modify: `tests/unit/test_cli.py`
  - 覆盖新 parser 和 CLI 执行路径。
- Modify: `lib/mcp_service.py`
  - 新增 MCP tools：`build_proposal_context`、`validate_client_proposal_contract`、`write_proposal_reflection`。
- Modify: `tests/unit/test_mcp_service.py`
  - 覆盖 tools/list schema 与 tool handler 输出。
- Modify: `docs/mcp-client-setup.md`
  - 加入 Codex/Claude 使用 proposal contract 的最短路径。
- Modify: `skills/ml-research-loop-planner/SKILL.md`
  - 加入“先 build context，再让客户端生成 proposal，再 validate，再执行实验”的 SOP。
- Modify: `skills/ml-research-loop-experiment-optimizer/SKILL.md`
  - 加入 proposal/reflection/rollback 约束。
- Modify: `docs/research/proposal-prompt-and-auto-research-methods-cn.md`
  - 增补本轮实现状态。

## 并行切片

第一波可以并行：

- Task 1：核心 contract 库和单元测试，只写 `lib/proposal_contract.py` 与 `tests/unit/test_proposal_contract.py`。
- Task 4：客户端文档和 skills SOP，只写 docs/skills 文件。

第二波在 Task 1 完成后：

- Task 2：CLI 集成。
- Task 3：MCP 集成。

---

### Task 1: Proposal Contract Core

**Files:**
- Create: `lib/proposal_contract.py`
- Test: `tests/unit/test_proposal_contract.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_proposal_contract.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.proposal_contract import (
    build_proposal_context,
    build_proposal_reflection,
    validate_client_proposal,
    write_proposal_context,
)


def test_build_proposal_context_writes_non_executing_contract(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    baseline.write_text('{"SHIFT": 80.0, "H": 90.0, "failure_count": 12}', encoding="utf-8")
    current.write_text('{"SHIFT": 81.2, "H": 90.5, "failure_count": 10}', encoding="utf-8")

    payload = build_proposal_context(
        objective="Improve local diagnostic SHIFT without hurting H.",
        output_dir=tmp_path / "proposal-context",
        baseline_report=baseline,
        current_report=current,
        allowed_change_surfaces=["prompt_profile", "routing"],
        max_proposals=3,
    )

    assert payload["status"] == "ready_for_client_proposal"
    assert payload["executes_tool"] is False
    assert payload["official_scores_claimed"] is False
    assert payload["contract"]["required_fields"] == [
        "proposal_id",
        "hypothesis",
        "evidence_used",
        "change_surface",
        "change_spec",
        "expected_effect",
        "validation_plan",
        "risk_assessment",
        "next_if_success",
        "next_if_failure",
        "claim_boundary",
    ]
    assert payload["inputs"]["baseline_report"]["metrics"]["SHIFT"] == 80.0
    assert payload["inputs"]["current_report"]["metrics"]["SHIFT"] == 81.2
    assert "Codex/Claude" in payload["prompt_markdown"]
    assert Path(payload["context_file"]).exists()
    assert Path(payload["prompt_file"]).exists()


def test_validate_client_proposal_accepts_single_variable_contract() -> None:
    proposal = {
        "proposal_id": "round-005-confidence-v1",
        "hypothesis": "Tighter confidence wording will reduce overconfident wrong answers.",
        "evidence_used": [{"artifact": "current_report", "observation": "confidence errors"}],
        "change_surface": "prompt_profile",
        "change_spec": {
            "single_primary_variable": True,
            "target": "confidence_calibration_prompt",
            "allowed_scope": "one prompt block",
        },
        "expected_effect": {
            "primary_metric": "SHIFT",
            "target_categories": ["confidence_calibration"],
            "expected_direction": "increase",
        },
        "validation_plan": {
            "first_split": "dev",
            "promotion_split": "canary",
            "rollback_if": ["H_drop_gt_1", "SHIFT_delta_lt_0"],
        },
        "risk_assessment": {"overfit_risk": "medium", "leakage_risk": "low"},
        "next_if_success": "promote_candidate_profile",
        "next_if_failure": "rollback_candidate",
        "claim_boundary": "local diagnostic proposal only",
    }

    result = validate_client_proposal(
        proposal,
        allowed_change_surfaces=["prompt_profile", "routing"],
    )

    assert result["status"] == "accepted"
    assert result["executes_tool"] is False
    assert result["normalized_proposal"]["proposal_id"] == "round-005-confidence-v1"


def test_validate_client_proposal_rejects_missing_fields_and_broad_change() -> None:
    result = validate_client_proposal(
        {
            "proposal_id": "bad",
            "hypothesis": "Change many things.",
            "change_surface": "training_recipe",
            "change_spec": {"single_primary_variable": False},
        },
        allowed_change_surfaces=["prompt_profile"],
    )

    assert result["status"] == "rejected"
    assert "missing_required_fields" in result["failure_labels"]
    assert "change_surface_not_allowed" in result["failure_labels"]
    assert "not_single_primary_variable" in result["failure_labels"]


def test_build_proposal_reflection_labels_canary_failure(tmp_path: Path) -> None:
    proposal = {"proposal_id": "round-006-semantic-v2", "change_surface": "routing"}
    evaluation = {
        "dev_delta": {"SHIFT": 0.9, "H": 0.0, "failure_count": 1},
        "canary_delta": {"SHIFT": -0.3, "H": 0.0, "failure_count": -1},
        "rollback_reasons": ["canary_not_confirmed"],
    }

    reflection = build_proposal_reflection(
        proposal=proposal,
        evaluation=evaluation,
        output_dir=tmp_path / "reflection",
    )

    assert reflection["status"] == "needs_rollback_or_more_evidence"
    assert reflection["failure_labels"] == ["canary_not_confirmed"]
    assert reflection["recommended_next_action"] == "rollback_or_keep_as_candidate"
    assert reflection["memory_update_recommended"] is True
    assert Path(reflection["reflection_file"]).exists()
```

- [ ] **Step 2: Verify RED**

Run:

```bash
.venv/bin/python -m pytest -q tests/unit/test_proposal_contract.py
```

Expected: fail with `ModuleNotFoundError: No module named 'lib.proposal_contract'`.

- [ ] **Step 3: Implement minimal core module**

Create `lib/proposal_contract.py` with these public functions:

```python
from __future__ import annotations

import json
from pathlib import Path
from typing import Any


CONTRACT_VERSION = "2026-05-21.proposal-contract.v1"
DEFAULT_CHANGE_SURFACES = [
    "prompt_profile",
    "routing",
    "decoding",
    "data",
    "training_recipe",
    "code_patch",
    "model_choice",
]
REQUIRED_PROPOSAL_FIELDS = [
    "proposal_id",
    "hypothesis",
    "evidence_used",
    "change_surface",
    "change_spec",
    "expected_effect",
    "validation_plan",
    "risk_assessment",
    "next_if_success",
    "next_if_failure",
    "claim_boundary",
]


def build_proposal_context(
    *,
    objective: str,
    output_dir: str | Path,
    baseline_report: str | Path | None = None,
    current_report: str | Path | None = None,
    previous_proposals: str | Path | None = None,
    memory_cards: str | Path | None = None,
    allowed_change_surfaces: list[str] | None = None,
    max_proposals: int = 3,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    allowed = allowed_change_surfaces or ["prompt_profile", "routing", "decoding"]
    payload: dict[str, Any] = {
        "status": "ready_for_client_proposal",
        "contract_version": CONTRACT_VERSION,
        "objective": objective,
        "allowed_change_surfaces": allowed,
        "max_proposals": max_proposals,
        "inputs": {
            "baseline_report": _artifact_payload(baseline_report),
            "current_report": _artifact_payload(current_report),
            "previous_proposals": _artifact_payload(previous_proposals),
            "memory_cards": _artifact_payload(memory_cards),
        },
        "contract": proposal_contract_schema(allowed_change_surfaces=allowed),
        "prompt_markdown": "",
        "executes_tool": False,
        "official_scores_claimed": False,
        "claim_boundary": (
            "client-side proposal planning only; MCP/evaluator must decide success"
        ),
    }
    payload["prompt_markdown"] = render_proposal_prompt(payload)
    return _write_context_payload(payload, output)


def write_proposal_context(**kwargs: Any) -> dict[str, Any]:
    return build_proposal_context(**kwargs)


def proposal_contract_schema(
    *,
    allowed_change_surfaces: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "version": CONTRACT_VERSION,
        "required_fields": list(REQUIRED_PROPOSAL_FIELDS),
        "allowed_change_surfaces": allowed_change_surfaces or list(DEFAULT_CHANGE_SURFACES),
        "rules": [
            "one primary variable per proposal",
            "do not claim official scores",
            "dev improvements require canary/holdout confirmation before promotion",
            "failed proposals and rollback reasons must be preserved",
        ],
    }


def validate_client_proposal(
    proposal: dict[str, Any],
    *,
    allowed_change_surfaces: list[str] | None = None,
) -> dict[str, Any]:
    allowed = allowed_change_surfaces or list(DEFAULT_CHANGE_SURFACES)
    missing = [field for field in REQUIRED_PROPOSAL_FIELDS if field not in proposal]
    labels: list[str] = []
    if missing:
        labels.append("missing_required_fields")
    if proposal.get("change_surface") not in allowed:
        labels.append("change_surface_not_allowed")
    change_spec = proposal.get("change_spec")
    if not isinstance(change_spec, dict) or change_spec.get("single_primary_variable") is not True:
        labels.append("not_single_primary_variable")
    if proposal.get("official_scores_claimed") is True:
        labels.append("official_score_claim_forbidden")
    status = "accepted" if not labels else "rejected"
    return {
        "status": status,
        "contract_version": CONTRACT_VERSION,
        "failure_labels": labels,
        "missing_required_fields": missing,
        "allowed_change_surfaces": allowed,
        "normalized_proposal": dict(proposal),
        "executes_tool": False,
        "official_scores_claimed": False,
    }


def build_proposal_reflection(
    *,
    proposal: dict[str, Any],
    evaluation: dict[str, Any],
    output_dir: str | Path,
) -> dict[str, Any]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    failure_labels = _failure_labels(evaluation)
    if failure_labels:
        status = "needs_rollback_or_more_evidence"
        next_action = "rollback_or_keep_as_candidate"
    else:
        status = "candidate_supported"
        next_action = "promote_candidate_if_canary_confirmed"
    payload = {
        "status": status,
        "contract_version": CONTRACT_VERSION,
        "proposal_id": proposal.get("proposal_id"),
        "proposal": proposal,
        "evaluation": evaluation,
        "failure_labels": failure_labels,
        "recommended_next_action": next_action,
        "memory_update_recommended": True,
        "executes_tool": False,
        "official_scores_claimed": False,
        "claim_boundary": "proposal reflection only; not an official score claim",
    }
    json_path = output / "proposal-reflection.json"
    md_path = output / "proposal-reflection.md"
    json_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    md_path.write_text(_reflection_markdown(payload), encoding="utf-8")
    payload["reflection_file"] = str(json_path)
    payload["markdown_file"] = str(md_path)
    return payload
```

Add helper functions `_artifact_payload`, `_write_context_payload`, `render_proposal_prompt`, `_failure_labels`, and `_reflection_markdown` with deterministic JSON loading and markdown output.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
.venv/bin/python -m pytest -q tests/unit/test_proposal_contract.py
```

Expected: all tests pass.

---

### Task 2: CLI Integration

**Files:**
- Modify: `scripts/cli.py`
- Modify: `tests/unit/test_cli.py`

- [ ] **Step 1: Write failing CLI parser/execution tests**

Add parser coverage to `tests/unit/test_cli.py`:

```python
    proposal_context_args = parser.parse_args([
        "proposal",
        "context",
        "--objective",
        "Improve local metric",
        "--output-dir",
        "/tmp/proposal-context",
        "--baseline-report",
        "/tmp/baseline.json",
        "--current-report",
        "/tmp/current.json",
        "--allowed-change-surface",
        "prompt_profile",
        "--json",
    ])
    assert proposal_context_args.command == "proposal"
    assert proposal_context_args.proposal_command == "context"
    assert proposal_context_args.allowed_change_surface == ["prompt_profile"]
```

Add an execution test:

```python
def test_cli_proposal_context_writes_artifacts(tmp_path: Path, capsys) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    baseline.write_text('{"metric": 1}', encoding="utf-8")
    current.write_text('{"metric": 2}', encoding="utf-8")
    output_dir = tmp_path / "context"

    exit_code = main([
        "proposal",
        "context",
        "--objective",
        "Improve metric",
        "--output-dir",
        str(output_dir),
        "--baseline-report",
        str(baseline),
        "--current-report",
        str(current),
        "--json",
    ])

    printed = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert printed["status"] == "ready_for_client_proposal"
    assert (output_dir / "proposal-context.json").exists()
```

- [ ] **Step 2: Verify RED**

Run:

```bash
.venv/bin/python -m pytest -q tests/unit/test_cli.py::test_parser_has_run_status_result_subcommands tests/unit/test_cli.py::test_cli_proposal_context_writes_artifacts
```

Expected: parser rejects `proposal` because the command does not exist.

- [ ] **Step 3: Implement CLI commands**

In `scripts/cli.py` import:

```python
from lib.proposal_contract import (
    build_proposal_context,
    build_proposal_reflection,
    validate_client_proposal,
)
```

Add parser:

```python
    proposal = subcommands.add_parser(
        "proposal",
        help="Build and validate client-side proposal prompt contracts",
    )
    proposal_commands = proposal.add_subparsers(dest="proposal_command", required=True)
    proposal_context = proposal_commands.add_parser("context")
    proposal_context.add_argument("--objective", required=True)
    proposal_context.add_argument("--output-dir", type=Path, required=True)
    proposal_context.add_argument("--baseline-report", type=Path)
    proposal_context.add_argument("--current-report", type=Path)
    proposal_context.add_argument("--previous-proposals", type=Path)
    proposal_context.add_argument("--memory-cards", type=Path)
    proposal_context.add_argument("--allowed-change-surface", action="append")
    proposal_context.add_argument("--max-proposals", type=int, default=3)
    proposal_context.add_argument("--json", action="store_true")

    proposal_validate = proposal_commands.add_parser("validate")
    proposal_validate.add_argument("--proposal", type=Path, required=True)
    proposal_validate.add_argument("--allowed-change-surface", action="append")
    proposal_validate.add_argument("--json", action="store_true")

    proposal_reflect = proposal_commands.add_parser("reflect")
    proposal_reflect.add_argument("--proposal", type=Path, required=True)
    proposal_reflect.add_argument("--evaluation", type=Path, required=True)
    proposal_reflect.add_argument("--output-dir", type=Path, required=True)
    proposal_reflect.add_argument("--json", action="store_true")
```

Add `_run_proposal(args)` and route from `main`.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
.venv/bin/python -m pytest -q tests/unit/test_cli.py
```

Expected: pass.

---

### Task 3: MCP Integration

**Files:**
- Modify: `lib/mcp_service.py`
- Modify: `tests/unit/test_mcp_service.py`

- [ ] **Step 1: Write failing MCP tests**

In `tests/unit/test_mcp_service.py`, extend `test_tools_list_exposes_research_loop_tools`:

```python
        "build_proposal_context",
        "validate_client_proposal_contract",
        "write_proposal_reflection",
```

Add:

```python
def test_build_proposal_context_tool_writes_artifacts(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    baseline.write_text('{"SHIFT": 1}', encoding="utf-8")
    current.write_text('{"SHIFT": 2}', encoding="utf-8")

    payload = mcp_service.build_proposal_context_tool({
        "objective": "Improve local metric",
        "output_dir": str(tmp_path / "context"),
        "baseline_report": str(baseline),
        "current_report": str(current),
        "allowed_change_surfaces": ["prompt_profile"],
    })

    assert payload["status"] == "ready_for_client_proposal"
    assert payload["executes_tool"] is False
    assert payload["official_scores_claimed"] is False


def test_validate_client_proposal_contract_tool_rejects_invalid_surface() -> None:
    payload = mcp_service.validate_client_proposal_contract_tool({
        "proposal": {
            "proposal_id": "bad",
            "hypothesis": "Change too much",
            "change_surface": "training_recipe",
            "change_spec": {"single_primary_variable": False},
        },
        "allowed_change_surfaces": ["prompt_profile"],
    })

    assert payload["status"] == "rejected"
    assert "change_surface_not_allowed" in payload["failure_labels"]
```

- [ ] **Step 2: Verify RED**

Run:

```bash
.venv/bin/python -m pytest -q tests/unit/test_mcp_service.py::test_tools_list_exposes_research_loop_tools tests/unit/test_mcp_service.py::test_build_proposal_context_tool_writes_artifacts tests/unit/test_mcp_service.py::test_validate_client_proposal_contract_tool_rejects_invalid_surface
```

Expected: new functions/tools missing.

- [ ] **Step 3: Implement MCP tools**

In `lib/mcp_service.py` import the proposal helpers, add names to `REQUIRED_TOOLS`, `TOOL_CONTRACT_DESCRIPTIONS`, `SKILL_CONTRACTS` required tool lists, `tool_definitions()`, and `TOOL_HANDLERS`.

Add handlers:

```python
def build_proposal_context_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    objective = str(arguments.get("objective") or "").strip()
    if not objective:
        raise MCPToolError({"status": "failed", "error": "objective is required"})
    output_dir = _resolve_allowed_path(arguments.get("output_dir"), must_exist=False)
    return build_proposal_context(
        objective=objective,
        output_dir=output_dir,
        baseline_report=arguments.get("baseline_report"),
        current_report=arguments.get("current_report"),
        previous_proposals=arguments.get("previous_proposals"),
        memory_cards=arguments.get("memory_cards"),
        allowed_change_surfaces=arguments.get("allowed_change_surfaces"),
        max_proposals=int(arguments.get("max_proposals", 3)),
    )
```

Use existing allowed-root helpers for output paths and path inputs where practical.

- [ ] **Step 4: Verify GREEN**

Run:

```bash
.venv/bin/python -m pytest -q tests/unit/test_mcp_service.py
```

Expected: pass.

---

### Task 4: Client Docs and Skills

**Files:**
- Modify: `docs/mcp-client-setup.md`
- Modify: `skills/ml-research-loop-planner/SKILL.md`
- Modify: `skills/ml-research-loop-experiment-optimizer/SKILL.md`
- Modify: `docs/research/proposal-prompt-and-auto-research-methods-cn.md`

- [ ] **Step 1: Add docs test expectations**

Extend existing docs/skill tests if they assert required tool names:

```python
assert "build_proposal_context" in doc
assert "validate_client_proposal_contract" in doc
assert "write_proposal_reflection" in doc
```

- [ ] **Step 2: Update client setup docs**

Add a Chinese section:

```markdown
## Proposal Prompt Contract 工作流

1. 调用 `build_proposal_context` 生成 artifact bundle。
2. Codex/Claude 只基于该 bundle 生成 proposal JSON，不直接声明成功。
3. 调用 `validate_client_proposal_contract` 做 schema、action space、single-variable 校验。
4. 校验通过后，再选择 `run_client_patch_experiment`、`apply_client_code_patch` 或 `run_fasttext_multi_proposal_loop` 执行。
5. 执行后调用 `write_proposal_reflection`，把 dev/canary、失败标签和 rollback 结论写成 evidence。
```

- [ ] **Step 3: Update skills**

Update planner/optimizer skills so they always instruct clients to:

- build context before proposing;
- validate proposal before executing;
- preserve failed proposals;
- write reflection after evaluation;
- never treat local diagnostics as official scores.

- [ ] **Step 4: Verify docs references**

Run:

```bash
.venv/bin/python -m pytest -q tests/unit/test_skill_packages.py tests/unit/test_mcp_delivery_docs.py tests/unit/test_planner_docs.py
```

Expected: pass.

---

### Task 5: Final Verification and Commit

**Files:**
- All files changed above.

- [ ] **Step 1: Run targeted tests**

Run:

```bash
.venv/bin/python -m pytest -q \
  tests/unit/test_proposal_contract.py \
  tests/unit/test_cli.py \
  tests/unit/test_mcp_service.py \
  tests/unit/test_skill_packages.py \
  tests/unit/test_mcp_delivery_docs.py \
  tests/unit/test_planner_docs.py
```

Expected: pass.

- [ ] **Step 2: Run diff check**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 3: Commit**

Run:

```bash
git add \
  lib/proposal_contract.py \
  scripts/cli.py \
  lib/mcp_service.py \
  tests/unit/test_proposal_contract.py \
  tests/unit/test_cli.py \
  tests/unit/test_mcp_service.py \
  docs/mcp-client-setup.md \
  skills/ml-research-loop-planner/SKILL.md \
  skills/ml-research-loop-experiment-optimizer/SKILL.md \
  docs/research/proposal-prompt-and-auto-research-methods-cn.md \
  docs/superpowers/plans/2026-05-21-proposal-prompt-contract-cn.md
git commit -m "实现 proposal prompt contract 骨架"
```

Expected: commit succeeds on `codex/proposal-methods-research`.
