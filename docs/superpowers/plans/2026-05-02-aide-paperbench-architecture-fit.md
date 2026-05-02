# AIDE PaperBench Architecture Fit Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Absorb the useful AIDE and PaperBench architecture patterns into the existing ml-intern x autoresearch MCP service without replacing the current MCP contract or execution model.

**Architecture:** Keep Codex/Claude as the default planner and `lib/mcp_service.py` as the stable product boundary. Add lightweight internal models for experiment-tree search and reproduction grading behind the existing task/result artifacts, while avoiding direct dependency on AIDE, PaperBench, nanoeval, alcatraz, Docker, GPU, or server-side LLMs in the default path.

**Tech Stack:** Python dataclasses, stdio MCP service, JSON runtime artifacts, pytest, ruff, markdown docs.

---

## Fit Decisions

- AIDE should contribute the pattern, not the package: solution-tree nodes, draft/debug/improve selection, best-node tracking, and tree artifacts are useful; the Kaggle-specific prompts, Streamlit UI, and interpreter runtime do not fit the current MCP service boundary.
- PaperBench should contribute the evaluation discipline, not the full stack: rubric trees, reproduction stages, code-only grading, run group/run id metadata, and monitor hooks are useful; nanoeval/alcatraz container orchestration, full dataset payloads, and GPU-first assumptions are too heavy for the default product path.
- Current project boundaries stay fixed:
  - `lib/mcp_service.py` remains the public MCP contract surface.
  - `lib/fusion_service.py` remains the research-to-experiment handoff and review-intelligence layer.
  - `scripts/autoresearch_run.py` remains the bounded experiment executor.
  - `lib/task_protocol.py` remains the runtime task/result schema owner.
- New capabilities must be additive and optional. Existing `run_hypothesis_experiment`, `review_research_results`, `run_client_patch_experiment`, and `apply_client_code_patch` behavior must remain backward compatible under the current preview contract until an explicit contract-version bump.

## File Structure

- Create `lib/experiment_tree.py`
  - Owns the lightweight AIDE-inspired `ExperimentNode`, `ExperimentTree`, best-node selection, and next-action recommendation.
- Create `lib/reproduction_protocol.py`
  - Owns the PaperBench-inspired `RubricTask`, `ReproductionSpec`, `ReproductionReport`, and grade aggregation helpers.
- Modify `lib/task_protocol.py`
  - Adds optional fields for `experiment_tree`, `reproduction_spec`, and `grade_report` without requiring them for existing tasks.
- Modify `lib/fusion_service.py`
  - Builds experiment-tree summaries from existing `TaskResult.experiments`.
  - Builds reproduction-readiness and rubric-grade summaries for `review_research_results`.
- Modify `lib/mcp_service.py`
  - Exposes new state only through existing review/manifest payloads first; add new tools only after the state model is stable.
- Modify `scripts/autoresearch_run.py`
  - Writes tree-friendly metadata per experiment while preserving current result JSON shape.
- Modify `docs/hybrid-mcp-architecture.md`
  - Records the fit-first upstream integration rule.
- Modify `docs/productization-todos.md`
  - Adds the next product track for experiment-tree intelligence and reproduction grading.
- Test files:
  - `tests/unit/test_experiment_tree.py`
  - `tests/unit/test_reproduction_protocol.py`
  - `tests/unit/test_task_protocol.py`
  - `tests/unit/test_mcp_fusion_tools.py`
  - `tests/unit/test_mcp_service.py`
  - `tests/integration/test_mcp_real_task_code_benchmark.py`

## Non-Goals

- Do not vendor AIDE or PaperBench source code.
- Do not add a hard runtime dependency on Docker, nanoeval, alcatraz, GPU, Streamlit, or a hosted LLM provider.
- Do not replace the current `TaskDefinition` / `TaskResult` schema with upstream schemas.
- Do not make the default experiment path call `run_ai_autoresearch` or any server-side LLM implicitly.
- Do not claim PaperBench-level paper replication until fresh-run reproduction and rubric scoring are implemented and tested locally.

### Task 1: Add AIDE-Style Experiment Tree Model

**Files:**
- Create: `lib/experiment_tree.py`
- Create: `tests/unit/test_experiment_tree.py`
- Modify: `lib/fusion_service.py`
- Modify: `tests/unit/test_mcp_fusion_tools.py`

- [x] **Step 1: Write failing tree model tests**

Add `tests/unit/test_experiment_tree.py`:

```python
from lib.experiment_tree import ExperimentTree, build_experiment_tree


def test_build_experiment_tree_selects_best_minimize_node():
    experiments = [
        {"experiment_id": "exp-001", "metric": 1.20, "params": {"lr": 0.001}, "accepted": True},
        {"experiment_id": "exp-002", "metric": 0.95, "params": {"lr": 0.0005}, "accepted": True},
        {"experiment_id": "exp-003", "error_type": "training_timeout", "accepted": False},
    ]

    tree = build_experiment_tree(
        experiments=experiments,
        metric_name="val_bpb",
        metric_direction="minimize",
    )

    assert isinstance(tree, ExperimentTree)
    assert tree.best_node_id == "exp-002"
    assert tree.nodes["exp-001"].stage == "draft"
    assert tree.nodes["exp-002"].stage == "improve"
    assert tree.nodes["exp-003"].stage == "debug"
    assert tree.recommended_next_action["mode"] == "improve_best"
```

Add a focused assertion to `tests/unit/test_mcp_fusion_tools.py` so `review_research_results` returns:

```python
state = payload["research_review"]["experiment_state"]
assert state["experiment_tree"]["best_node_id"] == "exp-002"
assert state["planner_actions"][0]["tool"] in {
    "run_hypothesis_experiment",
    "get_experiment_logs",
}
```

- [x] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest \
  tests/unit/test_experiment_tree.py \
  tests/unit/test_mcp_fusion_tools.py::test_review_research_results_returns_experiment_tree_state -q
```

Expected: fail because `lib.experiment_tree` and the `experiment_tree` review payload do not exist.

- [x] **Step 3: Implement minimal tree model**

Create `lib/experiment_tree.py` with this public surface:

```python
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Literal


Stage = Literal["draft", "improve", "debug"]


@dataclass
class ExperimentNode:
    node_id: str
    stage: Stage
    metric: float | None = None
    params: dict[str, Any] = field(default_factory=dict)
    accepted: bool = False
    parent_id: str | None = None
    error_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExperimentTree:
    nodes: dict[str, ExperimentNode]
    root_ids: list[str]
    best_node_id: str | None
    recommended_next_action: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": {key: node.to_dict() for key, node in self.nodes.items()},
            "root_ids": self.root_ids,
            "best_node_id": self.best_node_id,
            "recommended_next_action": self.recommended_next_action,
        }


def build_experiment_tree(
    experiments: list[dict[str, Any]],
    metric_name: str,
    metric_direction: str,
) -> ExperimentTree:
    nodes: dict[str, ExperimentNode] = {}
    root_ids: list[str] = []
    best_node_id: str | None = None
    best_metric: float | None = None
    last_good_id: str | None = None
    lower_is_better = metric_direction == "minimize"

    for index, experiment in enumerate(experiments):
        node_id = str(experiment.get("experiment_id") or f"exp-{index + 1:03d}")
        metric = experiment.get("metric")
        if metric is None and isinstance(experiment.get("metrics"), dict):
            metric = experiment["metrics"].get(metric_name)
        metric = float(metric) if isinstance(metric, int | float) else None
        error_type = experiment.get("error_type") or experiment.get("error")
        stage: Stage = "draft" if not nodes else "debug" if error_type else "improve"
        parent_id = last_good_id if stage in {"improve", "debug"} else None
        if parent_id is None:
            root_ids.append(node_id)
        accepted = bool(experiment.get("accepted", metric is not None and not error_type))
        nodes[node_id] = ExperimentNode(
            node_id=node_id,
            stage=stage,
            metric=metric,
            params=dict(experiment.get("params") or {}),
            accepted=accepted,
            parent_id=parent_id,
            error_type=str(error_type) if error_type else None,
        )
        if metric is not None and not error_type:
            is_better = best_metric is None or (
                metric < best_metric if lower_is_better else metric > best_metric
            )
            if is_better:
                best_metric = metric
                best_node_id = node_id
            last_good_id = node_id

    failures = [node for node in nodes.values() if node.error_type]
    mode = "debug_failures" if failures else "improve_best"
    return ExperimentTree(
        nodes=nodes,
        root_ids=root_ids,
        best_node_id=best_node_id,
        recommended_next_action={
            "mode": mode,
            "target_node_id": failures[-1].node_id if failures else best_node_id,
        },
    )
```

- [x] **Step 4: Add review payload integration**

In `lib/fusion_service.py`, call `build_experiment_tree()` inside the existing experiment-state builder. Add:

```python
experiment_tree = build_experiment_tree(
    experiments=experiments,
    metric_name=metric_name,
    metric_direction=metric_direction,
).to_dict()
experiment_state["experiment_tree"] = experiment_tree
```

Do not expose a new MCP tool in this task.

- [x] **Step 5: Verify Task 1**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest \
  tests/unit/test_experiment_tree.py \
  tests/unit/test_mcp_fusion_tools.py -q
```

Expected: pass.

### Task 2: Add PaperBench-Style Lightweight Reproduction Protocol

**Files:**
- Create: `lib/reproduction_protocol.py`
- Create: `tests/unit/test_reproduction_protocol.py`
- Modify: `lib/task_protocol.py`
- Modify: `tests/unit/test_task_protocol.py`

- [x] **Step 1: Write failing reproduction protocol tests**

Add `tests/unit/test_reproduction_protocol.py`:

```python
from lib.reproduction_protocol import (
    RubricTask,
    ReproductionSpec,
    build_grade_report,
)


def test_grade_report_aggregates_weighted_leaf_scores():
    rubric = RubricTask(
        id="root",
        requirements="Reproduce the target result",
        weight=1,
        sub_tasks=[
            RubricTask(
                id="code",
                requirements="Implementation exists",
                weight=2,
                task_category="Code Development",
            ),
            RubricTask(
                id="run",
                requirements="Reproduction script runs",
                weight=1,
                task_category="Code Execution",
            ),
        ],
    )
    report = build_grade_report(
        rubric=rubric,
        leaf_scores={"code": 1.0, "run": 0.0},
        grader_log="code exists, run script missing",
    )

    assert report["score"] == 2 / 3
    assert report["num_leaf_nodes"] == 2
    assert report["num_invalid_leaf_nodes"] == 0
```

Add `tests/unit/test_task_protocol.py` coverage that `TaskDefinition.from_dict()` accepts:

```python
"reproduction_spec": {
    "mode": "local_command",
    "command": ["python", "train.py"],
    "timeout_seconds": 60,
}
```

and that `to_dict()` preserves it.

- [x] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest \
  tests/unit/test_reproduction_protocol.py \
  tests/unit/test_task_protocol.py -q
```

Expected: fail because reproduction protocol models do not exist and task schema does not preserve `reproduction_spec`.

- [x] **Step 3: Implement reproduction protocol dataclasses**

Create `lib/reproduction_protocol.py`:

```python
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass(frozen=True)
class RubricTask:
    id: str
    requirements: str
    weight: float
    sub_tasks: list["RubricTask"] = field(default_factory=list)
    task_category: str | None = None
    finegrained_task_category: str | None = None

    def leaf_nodes(self) -> list["RubricTask"]:
        if not self.sub_tasks:
            return [self]
        return [leaf for task in self.sub_tasks for leaf in task.leaf_nodes()]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["sub_tasks"] = [task.to_dict() for task in self.sub_tasks]
        return data


@dataclass(frozen=True)
class ReproductionSpec:
    mode: str
    command: list[str]
    timeout_seconds: int
    required_files: list[str] = field(default_factory=lambda: ["train.py"])

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_grade_report(
    rubric: RubricTask,
    leaf_scores: dict[str, float],
    grader_log: str,
) -> dict[str, Any]:
    leaves = rubric.leaf_nodes()
    total_weight = sum(max(leaf.weight, 0.0) for leaf in leaves)
    weighted = 0.0
    invalid = 0
    graded_nodes = []
    for leaf in leaves:
        raw_score = leaf_scores.get(leaf.id)
        if raw_score is None or raw_score < 0 or raw_score > 1:
            invalid += 1
            score = 0.0
        else:
            score = float(raw_score)
        weighted += max(leaf.weight, 0.0) * score
        graded_nodes.append({**leaf.to_dict(), "score": score})
    return {
        "score": weighted / total_weight if total_weight else 0.0,
        "num_leaf_nodes": len(leaves),
        "num_invalid_leaf_nodes": invalid,
        "graded_task_tree": {**rubric.to_dict(), "graded_leaf_nodes": graded_nodes},
        "grader_log": grader_log,
    }
```

- [x] **Step 4: Add optional task schema fields**

In `lib/task_protocol.py`, add optional fields:

```python
experiment_tree: Optional[dict] = None
reproduction_spec: Optional[dict] = None
grade_report: Optional[dict] = None
```

Thread them through `TaskDefinition.from_dict()` and `TaskDefinition.to_dict()` only when present. Do not make them required.

- [x] **Step 5: Verify Task 2**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest \
  tests/unit/test_reproduction_protocol.py \
  tests/unit/test_task_protocol.py -q
```

Expected: pass.

### Task 3: Connect Tree And Reproduction State To MCP Review

**Files:**
- Modify: `lib/fusion_service.py`
- Modify: `lib/mcp_service.py`
- Modify: `tests/unit/test_mcp_fusion_tools.py`
- Modify: `tests/unit/test_mcp_service.py`

- [x] **Step 1: Write failing MCP review tests**

Add a test that calls `review_research_results` with a result payload containing experiments and a task config containing `reproduction_spec`. Assert:

```python
state = payload["research_review"]["experiment_state"]
assert state["experiment_tree"]["recommended_next_action"]["mode"] in {
    "improve_best",
    "debug_failures",
}
assert state["reproduction"]["readiness"]["status"] in {
    "ready",
    "missing_required_files",
    "not_configured",
}
assert "reproduction" in payload["research_review"]["planner_actions"][0]["reason"]
```

- [x] **Step 2: Run tests to verify failure**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest \
  tests/unit/test_mcp_fusion_tools.py::test_review_research_results_returns_tree_and_reproduction_state \
  tests/unit/test_mcp_service.py::test_manifest_reports_fit_first_upstream_patterns -q
```

Expected: fail because review state and manifest do not yet report these fields.

- [x] **Step 3: Implement review state integration**

In `lib/fusion_service.py`, add reproduction readiness calculation:

```python
def build_reproduction_readiness(task_payload: dict[str, Any], workspace: str | None) -> dict[str, Any]:
    spec = task_payload.get("reproduction_spec")
    if not spec:
        return {"status": "not_configured", "required_files": [], "missing_files": []}
    required_files = list(spec.get("required_files") or ["train.py"])
    workspace_path = Path(workspace).resolve() if workspace else None
    missing = [
        item for item in required_files
        if workspace_path is None or not (workspace_path / item).exists()
    ]
    return {
        "status": "ready" if not missing else "missing_required_files",
        "mode": spec.get("mode"),
        "command": spec.get("command"),
        "timeout_seconds": spec.get("timeout_seconds"),
        "required_files": required_files,
        "missing_files": missing,
    }
```

Attach it to `experiment_state["reproduction"]`.

- [x] **Step 4: Add manifest capability flags**

In `lib/mcp_service.py`, extend `get_service_manifest` output with:

```python
"upstream_patterns": {
    "aide": {
        "integration_mode": "architecture_pattern",
        "enabled_features": ["experiment_tree", "best_node_tracking"],
        "direct_dependency": False,
    },
    "paperbench": {
        "integration_mode": "architecture_pattern",
        "enabled_features": ["reproduction_spec", "rubric_grade_report"],
        "direct_dependency": False,
    },
}
```

- [x] **Step 5: Verify Task 3**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest \
  tests/unit/test_mcp_fusion_tools.py \
  tests/unit/test_mcp_service.py -q
```

Expected: pass.

### Task 4: Add Bounded Reproduction Demo Path

**Files:**
- Create: `scripts/mcp_reproduction_demo.py`
- Create: `tests/integration/test_mcp_reproduction_demo.py`
- Modify: `scripts/release_check.py`
- Modify: `docs/mcp-client-setup.md`
- Modify: `examples/README.md`

- [x] **Step 1: Write failing integration test**

Add `tests/integration/test_mcp_reproduction_demo.py`:

```python
import json
import subprocess
import sys


def test_mcp_reproduction_demo_runs():
    proc = subprocess.run(
        [sys.executable, "scripts/mcp_reproduction_demo.py", "--json"],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
        check=True,
    )
    payload = json.loads(proc.stdout)
    assert payload["status"] == "passed"
    assert payload["reproduction"]["readiness"]["status"] == "ready"
    assert payload["grade_report"]["score"] >= 0
```

- [x] **Step 2: Run test to verify failure**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest \
  tests/integration/test_mcp_reproduction_demo.py -q
```

Expected: fail because the demo script is missing.

- [x] **Step 3: Implement deterministic local reproduction demo**

Create `scripts/mcp_reproduction_demo.py` that:

1. Creates an isolated `.demo_runs/reproduction-<id>` runtime root.
2. Writes a tiny task config with `reproduction_spec`.
3. Runs `run_hypothesis_experiment`.
4. Calls `review_research_results`.
5. Builds a deterministic local grade report with `build_grade_report()`.
6. Prints JSON containing `status`, `experiment_id`, `best_metric`, `reproduction`, and `grade_report`.

The script must not require Docker, GPU, external network, or LLM credentials.

- [x] **Step 4: Add release gate and docs**

Add the demo to `scripts/release_check.py` with label `mcp-reproduction-demo`. Document the flow in `docs/mcp-client-setup.md` and `examples/README.md`.

- [x] **Step 5: Verify Task 4**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest \
  tests/integration/test_mcp_reproduction_demo.py -q
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON=$(which python3) \
  python3 scripts/release_check.py --json
```

Expected: integration test passes and release check returns `"status": "passed"`.

### Task 5: Documentation And Compatibility Review

**Files:**
- Modify: `docs/hybrid-mcp-architecture.md`
- Modify: `docs/productization-todos.md`
- Modify: `README.md`
- Modify: `docs/release-checklist.md`

- [x] **Step 1: Document fit-first rule**

Add this requirement to `docs/hybrid-mcp-architecture.md`:

```markdown
## Upstream Pattern Integration Rule

AIDE and PaperBench are architecture references, not replacement runtimes. New work may absorb their experiment-tree search, reproduction, rubric, and grading patterns only when the feature is represented through this project's existing MCP contract, task protocol, runtime artifact layout, and release gate. Direct dependency on upstream packages requires a separate compatibility decision and must not enter the default Codex/Claude planner path.
```

- [x] **Step 2: Add productization TODO track**

Add a new section to `docs/productization-todos.md`:

```markdown
## P6: Experiment Tree And Reproduction Intelligence

- [ ] Add lightweight AIDE-style experiment tree state.
- [ ] Add lightweight PaperBench-style reproduction specs and rubric grade reports.
- [ ] Add MCP review payloads that expose tree and reproduction state without changing existing tool inputs.
- [ ] Add a deterministic reproduction demo to the release gate.
```

- [x] **Step 3: Update release checklist**

Document that release readiness requires:

```markdown
- `get_service_manifest` reports upstream pattern integration as direct_dependency=false.
- `review_research_results` returns experiment tree state for real task/code benchmark runs.
- Reproduction demo passes without Docker, GPU, external network, or LLM credentials.
```

- [ ] **Step 4: Verify docs and full gate**

Run:

```bash
git diff --check
PYTHONPATH=.:.venv/lib/python3.13/site-packages ML_RESEARCH_LOOP_PYTHON=$(which python3) \
  python3 scripts/release_check.py --json
```

Expected: no whitespace errors and release check returns `"status": "passed"`.

## Self-Review Checklist

- The plan preserves the current MCP service boundary and does not replace it with AIDE or PaperBench runtime assumptions.
- AIDE reuse is limited to experiment-tree state and search-policy concepts.
- PaperBench reuse is limited to reproduction/rubric/grading concepts.
- Default paths remain deterministic and do not require Docker, GPU, external network, or server-side LLM credentials.
- Backward compatibility is preserved by adding optional fields and review/manifest state before adding new tools.
