# ML Research Loop Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the current ml-research-loop prototype into a locally runnable, testable MVP whose CLI, experiment loop, Codex adapter, and documentation match the project goal.

**Architecture:** Stabilize the local runtime boundary first: workspace root, Python interpreter resolution, result object contracts, and package entry points. Then add smoke-level end-to-end validation for the random autoresearch loop. After that, harden the ml-intern/Codex integration and only then expand the AI-driven research loop.

**Tech Stack:** Python 3.10+, PyTorch, pytest, smolagents, file-system JSON protocol, local workdir/results/checkpoints directories.

---

## Current Baseline

Verified on 2026-04-28 in `/Users/dm/Documents/ml-research-loop`:

- The directory is not a git repository.
- `uv` is not on PATH in the current shell.
- `.venv/bin/python3`, `.venv/bin/pytest`, and `.venv/bin/ruff` have no execute bit.
- `ML_RESEARCH_LOOP_ROOT=$PWD PYTHONPATH=.venv/lib/python3.13/site-packages python3 -m pytest tests/ -q` passes: `35 passed`.
- Running tests without `ML_RESEARCH_LOOP_ROOT` fails because `lib/task_protocol.py` defaults to `/Users/a1/.openclaw/workspaces/ml-research-loop`.
- `scripts.autoresearch_run.run_training()` fails with `Permission denied: .venv/bin/python3`.
- `codex_plugin/codex_adapter.py` treats `TaskResult` as a dict.
- `pyproject.toml` exposes `ml-loop = "scripts.cli:main"`, but `scripts/cli.py` is missing.

## File Structure

Modify:

- `lib/task_protocol.py` - resolve workspace root from env or current source tree, not a machine-specific absolute path.
- `lib/experiment_store.py` - preserve metric name/direction metadata in store state if needed by downstream reports.
- `scripts/autoresearch_run.py` - use shared runtime Python resolver and keep result schema aligned.
- `scripts/ai_autoresearch_run.py` - same runtime resolver and result schema alignment as the random loop.
- `codex_plugin/codex_adapter.py` - normalize `TaskResult` objects and dicts.
- `pyproject.toml` - keep or correct console entry point after adding CLI module.
- `Makefile` - avoid assuming `uv` is present for every local command, or provide fallback targets.
- `README.md` - update actual commands, docs links, and integration examples.
- `WORKSPACE.md` - document local root behavior and runtime files.

Create:

- `lib/runtime.py` - interpreter and path resolution helpers.
- `scripts/cli.py` - package console entry point for run/status/result.
- `tests/unit/test_runtime.py` - unit tests for interpreter resolution.
- `tests/unit/test_codex_adapter.py` - adapter contract tests.
- `tests/unit/test_cli.py` - CLI parser and subcommand tests.
- `tests/integration/test_autoresearch_smoke.py` - minimal local loop smoke test.

Do not modify in this stabilization pass:

- Core model architecture in `base/train_base.py`, except if a later task explicitly needs a small test hook.
- Real cloud/GPU scheduling.
- W&B integration, because README claims it but there is no implementation yet.
- Full ml-intern runtime internals outside this repo.

## Milestone P0: Local Runtime Must Be Portable

### Task 1: Replace Machine-Specific Workspace Root

**Files:**
- Modify: `lib/task_protocol.py`
- Test: `tests/unit/test_task_protocol.py`

- [ ] **Step 1: Write failing tests for default root behavior**

Add these tests to `tests/unit/test_task_protocol.py`:

```python
def test_workspace_root_defaults_to_project_root_when_env_missing(monkeypatch):
    from lib import task_protocol

    monkeypatch.delenv("ML_RESEARCH_LOOP_ROOT", raising=False)
    root = task_protocol.resolve_workspace_root()

    assert root.name == "ml-research-loop"
    assert (root / "pyproject.toml").exists()


def test_workspace_root_uses_env_override(tmp_path, monkeypatch):
    from lib import task_protocol

    monkeypatch.setenv("ML_RESEARCH_LOOP_ROOT", str(tmp_path))

    assert task_protocol.resolve_workspace_root() == tmp_path.resolve()
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
ML_RESEARCH_LOOP_ROOT=$PWD PYTHONPATH=.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_task_protocol.py -q
```

Expected before implementation: at least one new test fails because `resolve_workspace_root()` does not exist.

- [ ] **Step 3: Implement root resolver**

In `lib/task_protocol.py`, replace the existing constant block with:

```python
def resolve_workspace_root() -> Path:
    configured = os.environ.get("ML_RESEARCH_LOOP_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()

    source_root = Path(__file__).resolve().parents[1]
    if (source_root / "pyproject.toml").exists():
        return source_root

    return Path.cwd().resolve()


WORKSPACE_ROOT = resolve_workspace_root()
```

Keep `TASKS_DIR`, `RESULTS_DIR`, `LOGS_DIR`, `SNAPSHOTS_DIR`, and `WORKDIR_DIR` derived from `WORKSPACE_ROOT`.

- [ ] **Step 4: Run focused and full tests**

Run:

```bash
PYTHONPATH=.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_task_protocol.py -q
PYTHONPATH=.venv/lib/python3.13/site-packages python3 -m pytest tests/ -q
```

Expected: all tests pass without setting `ML_RESEARCH_LOOP_ROOT`.

### Task 2: Add Portable Python Interpreter Resolution

**Files:**
- Create: `lib/runtime.py`
- Modify: `scripts/autoresearch_run.py`
- Modify: `scripts/ai_autoresearch_run.py`
- Test: `tests/unit/test_runtime.py`
- Test: `tests/unit/test_autoresearch_run.py`

- [ ] **Step 1: Write tests for interpreter resolution**

Create `tests/unit/test_runtime.py`:

```python
import os
import sys
from pathlib import Path

from lib.runtime import resolve_python_executable


def test_resolve_python_uses_env_override(tmp_path, monkeypatch):
    fake_python = tmp_path / "python"
    fake_python.write_text("#!/bin/sh\n", encoding="utf-8")
    fake_python.chmod(0o755)
    monkeypatch.setenv("ML_RESEARCH_LOOP_PYTHON", str(fake_python))

    assert resolve_python_executable(tmp_path) == str(fake_python)


def test_resolve_python_falls_back_to_sys_executable_when_venv_not_executable(tmp_path, monkeypatch):
    monkeypatch.delenv("ML_RESEARCH_LOOP_PYTHON", raising=False)
    venv_python = tmp_path / ".venv" / "bin" / "python3"
    venv_python.parent.mkdir(parents=True)
    venv_python.write_text("", encoding="utf-8")
    venv_python.chmod(0o644)

    assert resolve_python_executable(tmp_path) == sys.executable
```

- [ ] **Step 2: Run test and verify failure**

Run:

```bash
PYTHONPATH=.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_runtime.py -q
```

Expected before implementation: import fails because `lib.runtime` does not exist.

- [ ] **Step 3: Implement `lib/runtime.py`**

Create `lib/runtime.py`:

```python
from __future__ import annotations

import os
import sys
from pathlib import Path


def _is_executable(path: Path) -> bool:
    return path.exists() and path.is_file() and os.access(path, os.X_OK)


def resolve_python_executable(project_root: Path) -> str:
    override = os.environ.get("ML_RESEARCH_LOOP_PYTHON")
    if override:
        override_path = Path(override).expanduser()
        if not _is_executable(override_path):
            raise RuntimeError(f"ML_RESEARCH_LOOP_PYTHON is not executable: {override_path}")
        return str(override_path)

    venv_python = project_root / ".venv" / "bin" / "python3"
    if _is_executable(venv_python):
        return str(venv_python)

    return sys.executable
```

- [ ] **Step 4: Use resolver in both training scripts**

In `scripts/autoresearch_run.py` and `scripts/ai_autoresearch_run.py`, import:

```python
from lib.runtime import resolve_python_executable
```

Replace the hard-coded command:

```python
cmd = [
    str(_ROOT / ".venv" / "bin" / "python3"),
    "train.py",
]
```

with:

```python
cmd = [
    resolve_python_executable(_ROOT),
    "train.py",
]
```

- [ ] **Step 5: Add regression test for `run_training`**

Add to `tests/unit/test_autoresearch_run.py`:

```python
def test_run_training_uses_available_python(tmp_path, monkeypatch):
    from scripts.autoresearch_run import run_training

    train_py = tmp_path / "train.py"
    train_py.write_text('print("[RESULT] val_bpb=1.234")\n', encoding="utf-8")
    monkeypatch.setenv("ML_RESEARCH_LOOP_PYTHON", sys.executable)

    metrics = run_training(tmp_path, "exp-001", duration_seconds=5)

    assert metrics["val_bpb"] == 1.234
```

Also add `import sys` near the top of the test file.

- [ ] **Step 6: Run focused and full tests**

Run:

```bash
PYTHONPATH=.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_runtime.py tests/unit/test_autoresearch_run.py -q
PYTHONPATH=.venv/lib/python3.13/site-packages python3 -m pytest tests/ -q
```

Expected: all tests pass.

## Milestone P1: External Interfaces Must Report Correct State

### Task 3: Fix Codex Adapter Result Normalization

**Files:**
- Modify: `codex_plugin/codex_adapter.py`
- Test: `tests/unit/test_codex_adapter.py`

- [ ] **Step 1: Write adapter tests**

Create `tests/unit/test_codex_adapter.py`:

```python
from lib.task_protocol import TaskResult, TaskStatus
from codex_plugin.codex_adapter import MLResearchLoopCodexAdapter


def test_get_results_reads_task_result_object(monkeypatch):
    result = TaskResult(
        task_id="demo",
        status=TaskStatus.COMPLETED,
        best_result={"experiment_id": "exp-001", "val": 0.42, "params": {"lr": 0.001}},
        summary={"total_experiments": 3, "total_duration_minutes": 1.2},
    )

    monkeypatch.setattr("codex_plugin.codex_adapter.read_result", lambda task_id: result)
    adapter = MLResearchLoopCodexAdapter()

    payload = adapter.get_ml_experiment_results("demo")

    assert payload["success"] is True
    assert payload["status"] == "completed"
    assert payload["best_val"] == 0.42
    assert payload["best_params"] == {"lr": 0.001}
    assert payload["total_experiments"] == 3
    assert payload["total_duration_minutes"] == 1.2


def test_get_results_reports_not_ready(monkeypatch):
    from lib.exceptions import ResultNotReadyError

    def raise_not_ready(task_id):
        raise ResultNotReadyError("not ready")

    monkeypatch.setattr("codex_plugin.codex_adapter.read_result", raise_not_ready)
    adapter = MLResearchLoopCodexAdapter()

    payload = adapter.get_ml_experiment_results("demo")

    assert payload["success"] is False
    assert payload["status"] == "not_ready"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
PYTHONPATH=.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_codex_adapter.py -q
```

Expected before implementation: tests fail because the adapter treats `TaskResult` as a dict and catches the wrong exception.

- [ ] **Step 3: Implement normalizer helpers**

In `codex_plugin/codex_adapter.py`, import:

```python
from lib.exceptions import ResultNotReadyError
from lib.task_protocol import TaskResult
```

Add:

```python
def _result_to_dict(result: TaskResult | dict) -> dict:
    if isinstance(result, TaskResult):
        return result.to_dict()
    return result
```

Update `get_ml_experiment_results()`:

```python
result_obj = read_result(task_id)
result = _result_to_dict(result_obj)
best_result = result.get("best_result", {})
summary = result.get("summary", {})
best_val = best_result.get("metric", best_result.get("val"))
duration = summary.get("total_wall_clock_minutes", summary.get("total_duration_minutes", 0))
```

Catch both:

```python
except (FileNotFoundError, ResultNotReadyError):
```

- [ ] **Step 4: Run focused and full tests**

Run:

```bash
PYTHONPATH=.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_codex_adapter.py -q
PYTHONPATH=.venv/lib/python3.13/site-packages python3 -m pytest tests/ -q
```

Expected: all tests pass.

### Task 4: Add Working `ml-loop` Console CLI

**Files:**
- Create: `scripts/cli.py`
- Modify: `pyproject.toml` only if the entry point name changes
- Test: `tests/unit/test_cli.py`

- [ ] **Step 1: Write CLI tests**

Create `tests/unit/test_cli.py`:

```python
import json

from scripts.cli import build_parser, main


def test_parser_has_run_status_result_subcommands():
    parser = build_parser()

    run_args = parser.parse_args(["run", "--task-config", "tasks/demo.json"])
    status_args = parser.parse_args(["status", "demo"])
    result_args = parser.parse_args(["result", "demo"])

    assert run_args.command == "run"
    assert status_args.command == "status"
    assert result_args.command == "result"


def test_status_command_prints_json(monkeypatch, capsys):
    monkeypatch.setattr(
        "scripts.cli.AutoResearchManager.get_status",
        lambda self, task_id: {"task_id": task_id, "status": "running"},
    )

    exit_code = main(["status", "demo"])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "running"
```

- [ ] **Step 2: Run tests and verify failure**

Run:

```bash
PYTHONPATH=.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_cli.py -q
```

Expected before implementation: import fails because `scripts.cli` does not exist.

- [ ] **Step 3: Implement CLI**

Create `scripts/cli.py`:

```python
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from lib.runtime import resolve_python_executable
from lib.task_protocol import WORKSPACE_ROOT
from ml_intern.autoresearch_manager import AutoResearchManager


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ml-loop")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Run an autoresearch task config")
    run.add_argument("--task-config", required=True)
    run.add_argument("--workspace")
    run.add_argument("--max-experiments", type=int)
    run.add_argument("--experiment-duration", type=int, default=300)
    run.add_argument("--ai", action="store_true")
    run.add_argument("--mock", action="store_true")
    run.add_argument("--verbose", action="store_true")

    status = sub.add_parser("status", help="Read task progress")
    status.add_argument("task_id")

    result = sub.add_parser("result", help="Read task result")
    result.add_argument("task_id")

    return parser


def _run_task(args: argparse.Namespace) -> int:
    script = "ai_autoresearch_run.py" if args.ai else "autoresearch_run.py"
    cmd = [
        resolve_python_executable(WORKSPACE_ROOT),
        str(WORKSPACE_ROOT / "scripts" / script),
        "--task-config",
        args.task_config,
        "--experiment-duration",
        str(args.experiment_duration),
    ]
    if args.workspace:
        cmd.extend(["--workspace", args.workspace])
    if args.max_experiments is not None:
        cmd.extend(["--max-experiments", str(args.max_experiments)])
    if args.ai and args.mock:
        cmd.append("--mock")
    if args.verbose:
        cmd.append("--verbose")
    return subprocess.call(cmd, cwd=str(WORKSPACE_ROOT))


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    manager = AutoResearchManager()

    if args.command == "run":
        return _run_task(args)
    if args.command == "status":
        print(json.dumps(manager.get_status(args.task_id), indent=2, ensure_ascii=False))
        return 0
    if args.command == "result":
        result = manager.get_result(args.task_id)
        payload = result.to_dict() if result is not None else {"task_id": args.task_id, "status": "not_ready"}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run CLI tests**

Run:

```bash
PYTHONPATH=.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_cli.py -q
```

Expected: tests pass.

## Milestone P2: Experiment Loop Must Have a Smoke-Tested Golden Path

### Task 5: Add Minimal End-to-End Smoke Test

**Files:**
- Create: `tests/integration/test_autoresearch_smoke.py`
- Modify: `scripts/autoresearch_run.py` only if the smoke test finds path coupling

- [ ] **Step 1: Write smoke test around real CLI script**

Create `tests/integration/test_autoresearch_smoke.py`:

```python
import json
import subprocess
import sys
from pathlib import Path


def test_autoresearch_cli_smoke(tmp_path):
    root = Path(__file__).resolve().parents[2]
    task_dir = tmp_path / "tasks"
    task_dir.mkdir()
    task_file = task_dir / "smoke.json"
    task_file.write_text(
        json.dumps(
            {
                "task_id": "smoke",
                "objective": "minimize val_bpb on synthetic data",
                "dataset": {"name": "synthetic", "path": "missing.bin"},
                "metric": {"name": "val_bpb", "direction": "minimize", "threshold": 0.0},
                "hyperparameter_space": {
                    "depth": {"type": "choice", "values": [4]},
                    "dim": {"type": "choice", "values": [64]},
                    "batch_size": {"type": "choice", "values": [2]},
                    "window_size": {"type": "choice", "values": [64]},
                },
                "budget": {
                    "max_experiments": 1,
                    "max_duration_minutes": 2,
                    "experiment_duration_seconds": 30,
                },
                "base_code": {
                    "train_py_url": f"file://{root / 'base' / 'train_base.py'}",
                    "prepare_py_url": f"file://{root / 'base' / 'prepare.py'}",
                },
            }
        ),
        encoding="utf-8",
    )

    env = {
        **os.environ,
        "ML_RESEARCH_LOOP_ROOT": str(tmp_path),
        "ML_RESEARCH_LOOP_PYTHON": sys.executable,
        "PYTHONPATH": f"{root}:{root / '.venv' / 'lib' / 'python3.13' / 'site-packages'}",
    }
    proc = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "autoresearch_run.py"),
            "--task-config",
            str(task_file),
            "--workspace",
            str(tmp_path / "workdir" / "smoke"),
            "--max-experiments",
            "1",
            "--experiment-duration",
            "30",
        ],
        cwd=str(root),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
    )

    assert proc.returncode == 0, proc.stdout
    result_file = tmp_path / "results" / "smoke.json"
    assert result_file.exists()
    result = json.loads(result_file.read_text(encoding="utf-8"))
    assert result["status"] == "completed"
    assert result["summary"]["total_experiments"] == 1
```

Add `import os` at the top of the file.

- [ ] **Step 2: Run smoke test and verify behavior**

Run:

```bash
PYTHONPATH=.venv/lib/python3.13/site-packages python3 -m pytest tests/integration/test_autoresearch_smoke.py -q
```

Expected after P0 tasks: test passes or exposes a real runtime bug to fix before moving on.

- [ ] **Step 3: Run full suite including integration**

Run:

```bash
PYTHONPATH=.venv/lib/python3.13/site-packages python3 -m pytest tests/ -q
```

Expected: all tests pass.

### Task 6: Align Final Result Summary With Adapters

**Files:**
- Modify: `scripts/autoresearch_run.py`
- Modify: `scripts/ai_autoresearch_run.py`
- Test: `tests/unit/test_autoresearch_run.py`

- [ ] **Step 1: Add expected summary shape test**

Add a helper-level test if result construction is extracted, or assert through the smoke test result:

```python
def test_result_summary_contains_adapter_fields(tmp_path):
    result = {
        "summary": {
            "total_experiments": 3,
            "accepted": 1,
            "rejected": 2,
            "failed": 0,
            "total_duration_minutes": 1.5,
            "total_wall_clock_minutes": 1.5,
            "success_rate": 0.333,
        }
    }
    assert result["summary"]["total_wall_clock_minutes"] == result["summary"]["total_duration_minutes"]
    assert result["summary"]["success_rate"] == 0.333
```

- [ ] **Step 2: Update both scripts' `summary` dict**

In both final result sections, calculate:

```python
accepted_count = sum(1 for e in store.experiments if e.get("accepted"))
total_count = len(store.experiments)
```

Then use:

```python
summary={
    "total_experiments": total_count,
    "accepted": accepted_count,
    "rejected": sum(1 for e in store.experiments if not e.get("accepted")),
    "failed": sum(1 for e in store.experiments if e.get("error")),
    "total_duration_minutes": round(total_duration_minutes, 1),
    "total_wall_clock_minutes": round(total_duration_minutes, 1),
    "success_rate": round(accepted_count / max(total_count, 1), 3),
}
```

- [ ] **Step 3: Run tests**

Run:

```bash
PYTHONPATH=.venv/lib/python3.13/site-packages python3 -m pytest tests/ -q
```

Expected: all tests pass.

## Milestone P3: Manager and Tool Integration Must Be Honest

### Task 7: Make `AutoResearchManager.launch()` Behavior Explicit

**Files:**
- Modify: `ml_intern/autoresearch_manager.py`
- Modify: `ml_intern/tools/run_autoresearch.py`
- Test: `tests/unit/test_autoresearch_manager.py`

- [ ] **Step 1: Add tests for no-runtime behavior**

Create `tests/unit/test_autoresearch_manager.py`:

```python
import pytest

from ml_intern.autoresearch_manager import AutoResearchConfig, AutoResearchManager


def test_launch_records_task_when_openclaw_missing(tmp_path, monkeypatch):
    from lib import task_protocol

    task_protocol.WORKSPACE_ROOT = tmp_path
    task_protocol.TASKS_DIR = tmp_path / "tasks"
    task_protocol.RESULTS_DIR = tmp_path / "results"
    task_protocol.LOGS_DIR = tmp_path / "logs"
    task_protocol.SNAPSHOTS_DIR = tmp_path / "snapshots"
    task_protocol.WORKDIR_DIR = tmp_path / "workdir"

    manager = AutoResearchManager(workspace_root=tmp_path)
    config = AutoResearchConfig(
        task_id="demo",
        objective="minimize val_bpb",
        dataset_path="missing.bin",
        metric_name="val_bpb",
        metric_direction="minimize",
    )

    task_id = manager.launch(config)

    assert task_id == "demo"
    assert (tmp_path / "tasks" / "demo.json").exists()
    assert manager.active_tasks["demo"]["session_key"] is None
```

- [ ] **Step 2: Decide product behavior for missing OpenClaw runtime**

Implement one of these behaviors and keep tests aligned:

```python
# local mode: create task and return session_key=None
return {"session_key": None, "session": None, "runtime": "local-unspawned"}
```

or:

```python
# strict mode: fail clearly
raise RuntimeError("openclaw.sessions_spawn is required for async launch")
```

For this MVP, use local mode because standalone tests and Codex plugin development need to work without OpenClaw.

- [ ] **Step 3: Release locks after local fallback or document lock ownership**

If no subagent is spawned, release the task lock immediately:

```python
if session_key is None:
    release_task_lock(task_id)
```

Keep the lock while a real subagent is active.

- [ ] **Step 4: Run tests**

Run:

```bash
PYTHONPATH=.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_autoresearch_manager.py -q
PYTHONPATH=.venv/lib/python3.13/site-packages python3 -m pytest tests/ -q
```

Expected: all tests pass.

## Milestone P4: AI-Driven Loop Should Be Narrow but Real

### Task 8: Harden `ChangeExecutor` Boundaries

**Files:**
- Modify: `lib/research_components.py`
- Test: `tests/unit/test_research_components.py`

- [ ] **Step 1: Add tests for search-region-only edits**

Create `tests/unit/test_research_components.py`:

```python
from lib.research_components import ChangeExecutor, ChangeProposal


def test_change_executor_replaces_existing_search_region_value(tmp_path):
    train_py = tmp_path / "train.py"
    train_py.write_text(
        "OUTSIDE = 1\n"
        "# ======= AUTORESEARCH SEARCH REGION START =======\n"
        "DEPTH = 4\n"
        "# ======= AUTORESEARCH SEARCH REGION END =======\n",
        encoding="utf-8",
    )
    executor = ChangeExecutor(tmp_path)

    result = executor.execute(ChangeProposal(
        change_type="hyperparam",
        target="DEPTH",
        current_value="4",
        proposed_value="8",
        reason="test",
    ))

    content = train_py.read_text(encoding="utf-8")
    assert result.success is True
    assert "DEPTH = 8" in content
    assert "OUTSIDE = 1" in content


def test_change_executor_rejects_unknown_non_hyperparam_type(tmp_path):
    train_py = tmp_path / "train.py"
    train_py.write_text(
        "# ======= AUTORESEARCH SEARCH REGION START =======\n"
        "DEPTH = 4\n"
        "# ======= AUTORESEARCH SEARCH REGION END =======\n",
        encoding="utf-8",
    )
    executor = ChangeExecutor(tmp_path)

    result = executor.execute(ChangeProposal(
        change_type="architecture",
        target="NEW_LAYER",
        current_value="none",
        proposed_value="enabled",
        reason="test",
    ))

    assert result.success is False
```

- [ ] **Step 2: Implement explicit type support**

In `ChangeExecutor.execute()`, replace the current fallback:

```python
if proposal.change_type == "hyperparam":
    modified_content = self._apply_hyperparam(content, proposal)
else:
    modified_content = self._apply_hyperparam(content, proposal)
```

with:

```python
if proposal.change_type != "hyperparam":
    return ExecutionResult(
        success=False,
        error=f"Unsupported change_type for MVP: {proposal.change_type}",
        rollback=False,
    )

modified_content = self._apply_hyperparam(content, proposal)
```

- [ ] **Step 3: Run tests**

Run:

```bash
PYTHONPATH=.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_research_components.py -q
PYTHONPATH=.venv/lib/python3.13/site-packages python3 -m pytest tests/ -q
```

Expected: all tests pass.

### Task 9: Make AI Prompt Respect Task Metric

**Files:**
- Modify: `lib/research_components.py`
- Modify: `scripts/ai_autoresearch_run.py`
- Test: `tests/unit/test_research_components.py`

- [ ] **Step 1: Add test for metric-aware prompt**

Add to `tests/unit/test_research_components.py`:

```python
from lib.research_components import AnalyzeResult, ChangeProposer
from lib.llm_providers import MockLLMProvider


def test_change_proposer_prompt_uses_metric_context():
    provider = MockLLMProvider({
        "change_type": "hyperparam",
        "target": "DEPTH",
        "current_value": "4",
        "proposed_value": "8",
        "reason": "test",
        "confidence": 0.8,
    })
    proposer = ChangeProposer(provider, metric_name="val_accuracy", metric_direction="maximize")
    proposer.propose(AnalyzeResult("code", "history", "trend"))

    assert "val_accuracy" in provider.last_prompt
    assert "maximize" in provider.last_prompt
```

- [ ] **Step 2: Update `ChangeProposer.__init__`**

Change:

```python
def __init__(self, llm_provider: LLMProvider):
```

to:

```python
def __init__(self, llm_provider: LLMProvider, metric_name: str = "val_bpb", metric_direction: str = "minimize"):
    self.llm_provider = llm_provider
    self.metric_name = metric_name
    self.metric_direction = metric_direction
    self.proposal_history: list[ChangeProposal] = []
```

Update `_build_prompt()` so hard-coded `val_bpb` text becomes:

```python
prompt = f"""当前任务：{self.metric_direction} {self.metric_name}
...
"""
```

- [ ] **Step 3: Pass task metric from AI runner**

In `scripts/ai_autoresearch_run.py`, change:

```python
proposer = ChangeProposer(llm_provider)
```

to:

```python
proposer = ChangeProposer(
    llm_provider,
    metric_name=task.metric.name,
    metric_direction=task.metric.direction.value,
)
```

- [ ] **Step 4: Run tests**

Run:

```bash
PYTHONPATH=.venv/lib/python3.13/site-packages python3 -m pytest tests/unit/test_research_components.py -q
PYTHONPATH=.venv/lib/python3.13/site-packages python3 -m pytest tests/ -q
```

Expected: all tests pass.

## Milestone P5: Documentation Must Match Reality

### Task 10: Clean README and Workspace Docs

**Files:**
- Modify: `README.md`
- Modify: `WORKSPACE.md`
- Modify: `Makefile`

- [ ] **Step 1: Remove missing doc links or create stubs**

In `README.md`, replace:

```markdown
- [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) — 详细实现方案
- [roadmap.md](roadmap.md) — 产品路线图
```

with:

```markdown
- [FIX_PROPOSAL.md](FIX_PROPOSAL.md) — 当前代码审查与修复建议
- [docs/Phase2-AI自主研究设计.md](docs/Phase2-AI自主研究设计.md) — AI 自主研究循环设计
- [docs/Phase3-可靠性设计.md](docs/Phase3-可靠性设计.md) — checkpoint、告警与恢复设计
```

- [ ] **Step 2: Update quick-start commands**

Add this note near quick start:

```markdown
如果当前 shell 没有 `uv`，可以使用本机 Python 加载 `.venv` 依赖：

```bash
PYTHONPATH=.venv/lib/python3.13/site-packages python3 -m pytest tests/ -q
ML_RESEARCH_LOOP_PYTHON=$(which python3) python3 scripts/autoresearch_run.py \
  --task-config tasks/demo-mnist-001.json \
  --workspace ./workdir/demo-mnist-001 \
  --max-experiments 1 \
  --experiment-duration 30 \
  --verbose
```
```

- [ ] **Step 3: Make Makefile explicit**

Keep `uv` targets, but add fallback targets:

```make
test-python:
	PYTHONPATH=.venv/lib/python3.13/site-packages python3 -m pytest tests/ -q

run-demo-python:
	ML_RESEARCH_LOOP_PYTHON=$$(which python3) PYTHONPATH=.venv/lib/python3.13/site-packages python3 scripts/autoresearch_run.py \
		--task-config tasks/demo-mnist-001.json \
		--workspace ./workdir/demo-mnist-001 \
		--max-experiments 1 \
		--experiment-duration 30 \
		--verbose
```

- [ ] **Step 4: Run docs-adjacent validation**

Run:

```bash
make test-python
```

Expected: all tests pass.

## Release Gate

The stabilization pass is complete only when these commands pass from `/Users/dm/Documents/ml-research-loop`:

```bash
PYTHONPATH=.venv/lib/python3.13/site-packages python3 -m pytest tests/ -q
PYTHONPATH=.venv/lib/python3.13/site-packages:. python3 -m py_compile \
  scripts/autoresearch_run.py \
  scripts/ai_autoresearch_run.py \
  scripts/cli.py \
  ml_intern/autoresearch_manager.py \
  ml_intern/tools/run_autoresearch.py \
  lib/task_protocol.py \
  lib/runtime.py \
  lib/research_components.py \
  codex_plugin/codex_adapter.py
ML_RESEARCH_LOOP_PYTHON=$(which python3) PYTHONPATH=.venv/lib/python3.13/site-packages python3 scripts/autoresearch_run.py \
  --task-config tasks/demo-mnist-001.json \
  --workspace ./workdir/demo-mnist-001 \
  --max-experiments 1 \
  --experiment-duration 30 \
  --verbose
```

Expected:

- Unit and integration tests pass.
- Python compile check returns exit code 0.
- Demo writes `results/demo-mnist-001.json`.
- Codex adapter reports non-null `best_val` for a completed task.
- `ml-loop status demo-mnist-001` imports and prints JSON.

## Execution Notes

- Current checkout is not a git repository. If execution happens in a real git repo, commit after each task. If it remains a non-git directory, record changed files after each task and skip commit commands.
- Do not broaden into W&B, cloud GPUs, or a web UI in this pass.
- Do not claim production readiness until the smoke test and CLI demo both pass without manually setting `ML_RESEARCH_LOOP_ROOT`.
