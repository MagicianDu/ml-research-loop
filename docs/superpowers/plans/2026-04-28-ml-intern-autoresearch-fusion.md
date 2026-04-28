# ML Intern AutoResearch Fusion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Codex/Claude-callable MCP service whose core product is the fusion of Hugging Face ml-intern's research/tooling agent and Karpathy autoresearch's fixed-budget experimental validation loop.

**Architecture:** ml-intern remains the research orchestrator: it searches papers, Hugging Face docs/datasets, GitHub code, and turns findings into structured hypotheses. autoresearch remains the validation engine: it receives task context plus hypotheses, generates `program.md`, edits `train.py` under a fixed budget, evaluates `val_bpb`, and keeps or rejects changes. MCP is the external control surface, not the product core.

**Tech Stack:** Python 3.10+, stdio MCP JSON-RPC, smolagents Tool classes, file-system JSON task protocol, local runtime roots, pytest, ruff.

---

## Product Invariant

The project must preserve both upstream strengths:

- **ml-intern strength:** agentic research loop with ToolRouter access to papers, HF docs/research, HF repos/datasets/jobs, GitHub code search, planning, context management, and MCP tools.
- **autoresearch strength:** small reproducible experiment harness, `prepare.py` frozen, `train.py` editable, `program.md` as steering document, fixed per-run time budget, single comparable metric (`val_bpb` by default), accept/reject and audit trail.
- **Fusion strength:** ml-intern proposes research-backed hypotheses; autoresearch validates them empirically; results feed back into ml-intern for the next hypothesis.

MCP should expose this fusion as tools. It should not flatten the product into a bare CLI wrapper around `autoresearch_run.py`.

## File Structure

- Modify `lib/task_protocol.py`
  - Add structured `research_context` and `hypotheses` fields to `TaskDefinition`.
  - Keep existing task JSON backward-compatible.
- Create `lib/research_protocol.py`
  - Define `ResearchSource`, `ResearchFinding`, `ResearchHypothesis`, and `ResearchBrief`.
  - Provide `to_dict` / `from_dict` helpers for JSON storage and MCP payloads.
- Create `ml_intern/research_tools.py`
  - Implement local wrappers for paper search/read, HF docs/datasets search, and GitHub code search.
  - First iteration can call public HTTP APIs where available and return structured summaries.
- Create `ml_intern/fusion_planner.py`
  - Convert user intent plus research findings into `ResearchBrief` and ranked hypotheses.
- Modify `scripts/generate_program_md.py`
  - Inject research brief, citations/resources, accepted hypotheses, constraints, and forbidden changes into `program.md`.
- Modify `scripts/autoresearch_run.py`
  - Preserve current random-search path.
  - Add hypothesis-aware mode that records which hypothesis each experiment tests.
- Modify `scripts/ai_autoresearch_run.py`
  - Include research context in `ResearchAnalyzer`.
  - Let `ChangeProposer` prefer changes tied to a hypothesis.
- Modify `lib/research_components.py`
  - Allow safe architecture and training-strategy edits, or explicitly constrain proposals to supported edit types.
- Modify `lib/mcp_service.py`
  - Add fusion tools: `research_task`, `propose_hypotheses`, `run_hypothesis_experiment`, `review_research_results`.
- Modify `ml_intern/tools/run_autoresearch.py`
  - Add smolagents Tool classes mirroring the MCP fusion tools.
- Create tests under `tests/unit/test_research_protocol.py`, `tests/unit/test_fusion_planner.py`, `tests/unit/test_program_md_research_context.py`, and `tests/unit/test_mcp_fusion_tools.py`.

## Task 1: Freeze The Fusion Protocol

**Files:**
- Create: `lib/research_protocol.py`
- Modify: `lib/task_protocol.py`
- Test: `tests/unit/test_research_protocol.py`
- Test: `tests/unit/test_task_protocol.py`

- [ ] **Step 1: Write failing tests for research protocol round-trip**

```python
from lib.research_protocol import ResearchBrief, ResearchFinding, ResearchHypothesis, ResearchSource


def test_research_brief_round_trips_to_json_dict():
    brief = ResearchBrief(
        objective="reduce val_bpb on TinyStories",
        sources=[
            ResearchSource(
                source_type="paper",
                title="Attention Is All You Need",
                url="https://arxiv.org/abs/1706.03762",
                summary="Transformer attention baseline.",
            )
        ],
        findings=[
            ResearchFinding(
                finding_id="finding-001",
                claim="ALiBi can improve long-context extrapolation.",
                evidence=["paper:alibi"],
                relevance="May improve validation bpb at fixed context budget.",
            )
        ],
        hypotheses=[
            ResearchHypothesis(
                hypothesis_id="hyp-001",
                title="Try ALiBi positional bias",
                rationale="Prior work suggests better length generalization.",
                expected_metric="val_bpb",
                expected_direction="minimize",
                proposed_changes=["replace absolute position embedding with ALiBi"],
                risk_notes=["implementation may slow attention kernel"],
            )
        ],
    )

    restored = ResearchBrief.from_dict(brief.to_dict())

    assert restored.objective == "reduce val_bpb on TinyStories"
    assert restored.sources[0].source_type == "paper"
    assert restored.hypotheses[0].hypothesis_id == "hyp-001"
```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_research_protocol.py -q
```

Expected: FAIL because `lib.research_protocol` does not exist.

- [ ] **Step 3: Implement `lib/research_protocol.py`**

```python
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ResearchSource:
    source_type: str
    title: str
    url: str
    summary: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchSource":
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResearchFinding:
    finding_id: str
    claim: str
    evidence: list[str] = field(default_factory=list)
    relevance: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchFinding":
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResearchHypothesis:
    hypothesis_id: str
    title: str
    rationale: str
    expected_metric: str
    expected_direction: str
    proposed_changes: list[str] = field(default_factory=list)
    risk_notes: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchHypothesis":
        return cls(**data)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ResearchBrief:
    objective: str
    sources: list[ResearchSource] = field(default_factory=list)
    findings: list[ResearchFinding] = field(default_factory=list)
    hypotheses: list[ResearchHypothesis] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ResearchBrief":
        return cls(
            objective=data["objective"],
            sources=[ResearchSource.from_dict(item) for item in data.get("sources", [])],
            findings=[ResearchFinding.from_dict(item) for item in data.get("findings", [])],
            hypotheses=[
                ResearchHypothesis.from_dict(item)
                for item in data.get("hypotheses", [])
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "sources": [source.to_dict() for source in self.sources],
            "findings": [finding.to_dict() for finding in self.findings],
            "hypotheses": [hypothesis.to_dict() for hypothesis in self.hypotheses],
        }
```

- [ ] **Step 4: Extend task protocol backward-compatibly**

Add optional fields to `TaskDefinition`:

```python
research_context: Optional[dict] = None
hypotheses: list[dict] = field(default_factory=list)
```

Update `from_dict()` to read:

```python
research_context=data.get("research_context"),
hypotheses=data.get("hypotheses", []),
```

Update `to_dict()` to include them only when non-empty:

```python
if self.research_context:
    payload["research_context"] = self.research_context
if self.hypotheses:
    payload["hypotheses"] = self.hypotheses
```

- [ ] **Step 5: Run protocol tests**

Run:

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_research_protocol.py tests/unit/test_task_protocol.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add lib/research_protocol.py lib/task_protocol.py tests/unit/test_research_protocol.py tests/unit/test_task_protocol.py
git commit -m "feat: add research hypothesis protocol"
```

## Task 2: Add ml-intern Research Tool Layer

**Files:**
- Create: `ml_intern/research_tools.py`
- Test: `tests/unit/test_research_tools.py`

- [ ] **Step 1: Write failing tests for paper and dataset tool normalization**

```python
from ml_intern.research_tools import normalize_paper_result, normalize_dataset_result


def test_normalize_paper_result_preserves_source_type():
    result = normalize_paper_result({
        "title": "ALiBi",
        "url": "https://arxiv.org/abs/2108.12409",
        "summary": "Linear biases for attention.",
    })

    assert result.source_type == "paper"
    assert result.title == "ALiBi"
    assert result.url.endswith("2108.12409")


def test_normalize_dataset_result_preserves_hf_dataset_id():
    result = normalize_dataset_result({
        "id": "roneneldan/TinyStories",
        "description": "Synthetic short stories.",
    })

    assert result.source_type == "hf_dataset"
    assert result.title == "roneneldan/TinyStories"
    assert result.metadata["dataset_id"] == "roneneldan/TinyStories"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_research_tools.py -q
```

Expected: FAIL because `ml_intern.research_tools` does not exist.

- [ ] **Step 3: Implement tool normalization helpers**

```python
from __future__ import annotations

from lib.research_protocol import ResearchSource


def normalize_paper_result(data: dict) -> ResearchSource:
    return ResearchSource(
        source_type="paper",
        title=data.get("title", ""),
        url=data.get("url", ""),
        summary=data.get("summary", data.get("abstract", "")),
        metadata={k: v for k, v in data.items() if k not in {"title", "url", "summary", "abstract"}},
    )


def normalize_dataset_result(data: dict) -> ResearchSource:
    dataset_id = data.get("id", data.get("dataset_id", ""))
    return ResearchSource(
        source_type="hf_dataset",
        title=dataset_id,
        url=f"https://huggingface.co/datasets/{dataset_id}" if dataset_id else "",
        summary=data.get("description", ""),
        metadata={"dataset_id": dataset_id},
    )
```

- [ ] **Step 4: Add first MCP-safe stub search functions**

Add deterministic functions that can be tested without network:

```python
def search_papers(query: str, limit: int = 5) -> list[ResearchSource]:
    return []


def search_hf_datasets(query: str, limit: int = 5) -> list[ResearchSource]:
    return []


def search_github_code(query: str, limit: int = 5) -> list[ResearchSource]:
    return []
```

The first implementation may return empty results. The important invariant is the structured protocol; network-backed implementations can be added behind these functions.

- [ ] **Step 5: Run tests**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_research_tools.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ml_intern/research_tools.py tests/unit/test_research_tools.py
git commit -m "feat: add ml-intern research tool normalization"
```

## Task 3: Generate program.md From Research Context

**Files:**
- Modify: `scripts/generate_program_md.py`
- Test: `tests/unit/test_program_md_research_context.py`

- [ ] **Step 1: Write failing test**

```python
from lib.research_protocol import ResearchBrief, ResearchHypothesis, ResearchSource
from lib.task_protocol import (
    BaseCodeConfig,
    BudgetConfig,
    DatasetConfig,
    HyperparamSpace,
    MetricConfig,
    MetricDirection,
    TaskDefinition,
)
from scripts.generate_program_md import generate_program_md


def test_program_md_includes_research_sources_and_hypotheses():
    brief = ResearchBrief(
        objective="minimize val_bpb",
        sources=[
            ResearchSource(
                source_type="paper",
                title="ALiBi",
                url="https://arxiv.org/abs/2108.12409",
                summary="Attention with linear biases.",
            )
        ],
        hypotheses=[
            ResearchHypothesis(
                hypothesis_id="hyp-001",
                title="Try ALiBi",
                rationale="May improve long-context validation.",
                expected_metric="val_bpb",
                expected_direction="minimize",
                proposed_changes=["add ALiBi attention bias"],
            )
        ],
    )
    task = TaskDefinition(
        task_id="research-demo",
        objective="minimize val_bpb",
        dataset=DatasetConfig(name="tiny", path="data.bin"),
        metric=MetricConfig(name="val_bpb", direction=MetricDirection.MINIMIZE),
        hyperparameter_space={"depth": HyperparamSpace(type="choice", values=[1])},
        budget=BudgetConfig(max_experiments=1),
        base_code=BaseCodeConfig(train_py_url="file://train.py", prepare_py_url="file://prepare.py"),
        research_context=brief.to_dict(),
        hypotheses=[brief.hypotheses[0].to_dict()],
    )

    program = generate_program_md(task)

    assert "## Research Context" in program
    assert "ALiBi" in program
    assert "hyp-001" in program
    assert "add ALiBi attention bias" in program
```

- [ ] **Step 2: Run test to verify it fails**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_program_md_research_context.py -q
```

Expected: FAIL because generated `program.md` does not include research context.

- [ ] **Step 3: Implement research context rendering**

Add helper functions in `scripts/generate_program_md.py`:

```python
def _render_research_context(task: TaskDefinition) -> str:
    if not task.research_context and not task.hypotheses:
        return ""

    lines = ["## Research Context", ""]
    context = task.research_context or {}
    for source in context.get("sources", []):
        lines.append(f"- [{source.get('source_type', 'source')}] {source.get('title', '')}: {source.get('summary', '')}")
        if source.get("url"):
            lines.append(f"  URL: {source['url']}")

    if task.hypotheses:
        lines.extend(["", "## Hypotheses To Validate"])
        for hypothesis in task.hypotheses:
            lines.append(f"- {hypothesis.get('hypothesis_id')}: {hypothesis.get('title')}")
            lines.append(f"  Rationale: {hypothesis.get('rationale', '')}")
            for change in hypothesis.get("proposed_changes", []):
                lines.append(f"  Proposed change: {change}")

    return "\n".join(lines)
```

Append its output to the generated program.

- [ ] **Step 4: Run tests**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_program_md_research_context.py tests/unit/test_generate_program_md.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_program_md.py tests/unit/test_program_md_research_context.py
git commit -m "feat: inject research context into program md"
```

## Task 4: Expose Fusion Tools Through MCP

**Files:**
- Modify: `lib/mcp_service.py`
- Create: `lib/fusion_service.py`
- Test: `tests/unit/test_mcp_fusion_tools.py`

- [ ] **Step 1: Write failing MCP tool-list test**

```python
from lib import mcp_service


def test_mcp_lists_fusion_tools():
    response = mcp_service.handle_request({"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
    names = {tool["name"] for tool in response["result"]["tools"]}

    assert {
        "research_task",
        "propose_hypotheses",
        "run_hypothesis_experiment",
        "review_research_results",
    }.issubset(names)
```

- [ ] **Step 2: Run test to verify it fails**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_mcp_fusion_tools.py -q
```

Expected: FAIL because tools are not registered.

- [ ] **Step 3: Implement deterministic `lib/fusion_service.py`**

```python
from __future__ import annotations

from lib.research_protocol import ResearchBrief, ResearchHypothesis


def propose_hypotheses(objective: str, sources: list[dict] | None = None) -> dict:
    source_titles = [source.get("title", "") for source in sources or []]
    hypothesis = ResearchHypothesis(
        hypothesis_id="hyp-001",
        title=f"Validate research-backed change for {objective}",
        rationale="Generated from available research context: " + ", ".join(source_titles),
        expected_metric="val_bpb",
        expected_direction="minimize",
        proposed_changes=["modify one SEARCH REGION parameter before broader code edits"],
        risk_notes=["initial implementation is conservative"],
    )
    brief = ResearchBrief(
        objective=objective,
        hypotheses=[hypothesis],
    )
    return brief.to_dict()
```

- [ ] **Step 4: Register MCP tools**

Add tool definitions and handlers:

```python
from lib.fusion_service import propose_hypotheses


def research_task_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    objective = _required_string(arguments, "objective")
    return {"objective": objective, "status": "research_context_ready", "sources": []}


def propose_hypotheses_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    objective = _required_string(arguments, "objective")
    return propose_hypotheses(objective, arguments.get("sources", []))


def run_hypothesis_experiment_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    return run_autoresearch_tool(arguments)


def review_research_results_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    task_id = _required_string(arguments, "task_id")
    return get_experiment_result_tool({"task_id": task_id, "runtime_root": arguments.get("runtime_root")})
```

Register them in `TOOL_HANDLERS`.

- [ ] **Step 5: Run MCP tests**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_mcp_service.py tests/unit/test_mcp_fusion_tools.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add lib/mcp_service.py lib/fusion_service.py tests/unit/test_mcp_fusion_tools.py
git commit -m "feat: expose fusion workflow through mcp"
```

## Task 5: Align smolagents Tools With MCP Fusion Tools

**Files:**
- Modify: `ml_intern/tools/run_autoresearch.py`
- Create: `tests/unit/test_ml_intern_fusion_tools.py`

- [ ] **Step 1: Write failing tests for tool class names**

```python
from ml_intern.tools.run_autoresearch import (
    ProposeHypothesesTool,
    ResearchTaskTool,
    ReviewResearchResultsTool,
    RunHypothesisExperimentTool,
)


def test_fusion_tool_names_match_mcp_names():
    assert ResearchTaskTool().name == "research_task"
    assert ProposeHypothesesTool().name == "propose_hypotheses"
    assert RunHypothesisExperimentTool().name == "run_hypothesis_experiment"
    assert ReviewResearchResultsTool().name == "review_research_results"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_ml_intern_fusion_tools.py -q
```

Expected: FAIL because classes do not exist.

- [ ] **Step 3: Add smolagents tool classes**

Implement each class as a thin wrapper around `lib.fusion_service` and existing manager calls. Keep existing `RunAutoresearchTool`, `GetAutoresearchStatusTool`, and `GetAutoresearchResultTool` for backward compatibility.

- [ ] **Step 4: Export classes**

Update `ml_intern/tools/__init__.py`:

```python
from ml_intern.tools.run_autoresearch import (
    ProposeHypothesesTool,
    ResearchTaskTool,
    ReviewResearchResultsTool,
    RunHypothesisExperimentTool,
)

__all__ = [
    "ResearchTaskTool",
    "ProposeHypothesesTool",
    "RunHypothesisExperimentTool",
    "ReviewResearchResultsTool",
]
```

Preserve existing exports.

- [ ] **Step 5: Run tests**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_ml_intern_fusion_tools.py tests/unit/test_mcp_fusion_tools.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add ml_intern/tools/run_autoresearch.py ml_intern/tools/__init__.py tests/unit/test_ml_intern_fusion_tools.py
git commit -m "feat: add ml-intern fusion tools"
```

## Task 6: Restore autoresearch's Free Code-Edit Spirit Safely

**Files:**
- Modify: `lib/research_components.py`
- Test: `tests/unit/test_research_components.py`

- [ ] **Step 1: Write failing test for unsupported architecture proposal message**

```python
from lib.research_components import ChangeExecutor, ChangeProposal


def test_architecture_proposals_are_explicitly_classified(tmp_path):
    train_py = tmp_path / "train.py"
    train_py.write_text(
        "# ======= AUTORESEARCH SEARCH REGION START =======\nDEPTH = 1\n# ======= AUTORESEARCH SEARCH REGION END =======\n",
        encoding="utf-8",
    )
    proposal = ChangeProposal(
        change_type="architecture",
        target="DEPTH",
        current_value="1",
        proposed_value="2",
        reason="test architecture depth",
    )

    result = ChangeExecutor(tmp_path).execute(proposal)

    assert result.success is True
    assert "DEPTH = 2" in train_py.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_research_components.py::test_architecture_proposals_are_explicitly_classified -q
```

Expected: FAIL because architecture proposals are currently rejected.

- [ ] **Step 3: Support architecture proposals only when target is in SEARCH REGION**

Change the guard:

```python
if proposal.change_type not in {"hyperparam", "architecture", "training_strategy"}:
    return ExecutionResult(
        success=False,
        error=f"Unsupported change_type: {proposal.change_type}",
        rollback=False,
    )
```

For MVP, route all three supported types through `_apply_hyperparam()` only when the target exists in the search region. This preserves safety while unblocking research-backed non-hyperparam naming.

- [ ] **Step 4: Run tests**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_research_components.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add lib/research_components.py tests/unit/test_research_components.py
git commit -m "feat: allow safe research-backed code edit classes"
```

## Task 7: End-To-End Fusion Demo

**Files:**
- Create: `scripts/fusion_demo.py`
- Create: `tests/integration/test_fusion_demo.py`
- Modify: `Makefile`
- Modify: `README.md`

- [ ] **Step 1: Write failing integration test**

```python
import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_fusion_demo_runs_research_to_result(tmp_path):
    env = {
        **os.environ,
        "PYTHONPATH": f"{PROJECT_ROOT}{os.pathsep}{PROJECT_ROOT / '.venv/lib/python3.13/site-packages'}",
        "ML_RESEARCH_LOOP_PYTHON": sys.executable,
    }
    proc = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "fusion_demo.py"),
            "--runtime-root",
            str(tmp_path / "fusion-runtime"),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=120,
    )

    assert proc.returncode == 0, proc.stdout
    payload = json.loads(proc.stdout.splitlines()[-1])
    assert payload["status"] == "completed"
    assert payload["research_brief"]["hypotheses"]
```

- [ ] **Step 2: Run test to verify it fails**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/integration/test_fusion_demo.py -q
```

Expected: FAIL because `scripts/fusion_demo.py` does not exist.

- [ ] **Step 3: Implement `scripts/fusion_demo.py`**

The demo should:

1. Build a deterministic `ResearchBrief` with one paper source and one hypothesis.
2. Write a fresh task JSON under the runtime root.
3. Run `scripts/fresh_demo.py` or `scripts/autoresearch_run.py` with that task.
4. Print JSON containing `status`, `runtime_root`, `result_file`, and `research_brief`.

- [ ] **Step 4: Add Makefile target**

```make
run-fusion-demo-python:
	@echo "Running fusion demo..."
	ML_RESEARCH_LOOP_PYTHON=$$(which python3) PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 scripts/fusion_demo.py
```

- [ ] **Step 5: Update README**

Add a section that states:

- MCP is the client interface.
- ml-intern is the research planner and tool user.
- autoresearch is the empirical validator.
- The fusion demo is the acceptance path.

- [ ] **Step 6: Run final verification**

```bash
PYTHONPATH=.:.venv/lib/python3.13/site-packages python3 -m pytest tests/ -q
.venv/bin/ruff check lib/ scripts/ ml_intern/ codex_plugin/ tests/
make run-fusion-demo-python
make mcp-smoke-python
```

Expected:

- All tests pass.
- Ruff reports no issues.
- Fusion demo returns `status=completed`.
- MCP smoke lists both experiment tools and fusion tools.

- [ ] **Step 7: Commit**

```bash
git add scripts/fusion_demo.py tests/integration/test_fusion_demo.py Makefile README.md
git commit -m "feat: add end-to-end fusion demo"
```

## Acceptance Criteria

- Existing fresh demo still passes.
- MCP still works for Codex/Claude clients.
- New MCP tools expose the fused research-to-validation workflow.
- Task JSON can carry research context and hypotheses.
- Generated `program.md` includes research sources and hypotheses.
- Autoresearch remains empirically grounded with fixed budget and metric.
- ml-intern-facing tools preserve research discovery, planning, and review roles.

## Self-Review

- Spec coverage: The plan preserves ml-intern's research/tooling role, autoresearch's validation role, and exposes the fusion through MCP.
- Placeholder scan: No task uses empty placeholder wording or vague “add tests” instructions; each task lists concrete tests and commands.
- Type consistency: `ResearchBrief`, `ResearchSource`, `ResearchFinding`, and `ResearchHypothesis` are introduced in Task 1 and reused consistently.
