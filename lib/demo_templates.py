"""Deterministic demo templates for preview onboarding."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any


DATASET_SIZE_BYTES = 4096
VOCAB_SIZE = 64
SEQ_LEN = 64

DEMO_TEMPLATES: dict[str, dict[str, Any]] = {
    "byte-lm-smoke": {
        "name": "byte-lm-smoke",
        "description": "One-experiment local byte language-model smoke test.",
        "task_id": "demo-byte-lm-smoke",
        "task_type": "byte_language_model",
        "estimated_seconds": 60,
        "max_experiments": 1,
        "experiment_duration": 30,
        "hyperparameter_space": {
            "batch_size": {"type": "choice", "values": [1]},
            "depth": {"type": "choice", "values": [1]},
            "dim": {"type": "choice", "values": [16]},
            "window_size": {"type": "choice", "values": [64]},
        },
    },
    "byte-lm-depth-sweep": {
        "name": "byte-lm-depth-sweep",
        "description": "Two-experiment byte LM template for metric comparison.",
        "task_id": "demo-byte-lm-depth-sweep",
        "task_type": "byte_language_model",
        "estimated_seconds": 90,
        "max_experiments": 2,
        "experiment_duration": 30,
        "hyperparameter_space": {
            "batch_size": {"type": "choice", "values": [1]},
            "depth": {"type": "choice", "values": [1, 2]},
            "dim": {"type": "choice", "values": [16]},
            "window_size": {"type": "choice", "values": [64]},
        },
    },
    "paper-guided-byte-lm": {
        "name": "paper-guided-byte-lm",
        "description": "Paper-guided byte LM template with evidence and reproduction fields.",
        "task_id": "demo-paper-guided-byte-lm",
        "task_type": "byte_language_model",
        "estimated_seconds": 60,
        "max_experiments": 1,
        "experiment_duration": 30,
        "hyperparameter_space": {
            "batch_size": {"type": "choice", "values": [1]},
            "depth": {"type": "choice", "values": [1]},
            "dim": {"type": "choice", "values": [16]},
            "window_size": {"type": "choice", "values": [64]},
        },
        "research_context": {
            "query": "compact transformer byte language model",
            "sources": [
                {
                    "source_type": "paper",
                    "title": "Attention Is All You Need",
                    "url": "https://arxiv.org/abs/1706.03762",
                    "summary": "Transformer attention architecture reference for sequence modeling.",
                }
            ],
            "provider_coverage": {
                "papers": "fixture",
                "datasets": "local",
                "code": "local",
            },
        },
        "hypotheses": [
            {
                "id": "paper-guided-byte-lm-h1",
                "hypothesis_id": "paper-guided-byte-lm-h1",
                "title": "Compact attention model can fit a small byte distribution",
                "expected_metric": "val_bpb",
            }
        ],
        "reproduction_spec": {
            "paper": {
                "title": "Attention Is All You Need",
                "url": "https://arxiv.org/abs/1706.03762",
            },
            "required_files": [
                "train.py",
                "program.md",
                "logs/exp-001.log",
            ],
        },
        "program_md_overrides": {
            "focus_areas": [
                "Verify that the local byte dataset is used instead of synthetic fallback.",
                "Report val_bpb and the exact task/result artifact paths.",
            ],
            "forbidden_changes": [
                "Do not edit code outside the AUTORESEARCH SEARCH REGION.",
            ],
        },
    },
}


def list_demo_templates() -> list[dict[str, Any]]:
    """Return public metadata for deterministic demo templates."""
    return [
        {
            key: value
            for key, value in template.items()
            if key
            in {
                "name",
                "description",
                "task_id",
                "task_type",
                "estimated_seconds",
                "max_experiments",
                "experiment_duration",
            }
        }
        for template in DEMO_TEMPLATES.values()
    ]


def materialize_demo_template(
    *,
    template_name: str,
    runtime_root: Path,
    project_root: Path,
    max_experiments: int | None = None,
    experiment_duration: int | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """Write a demo task config and deterministic local dataset."""
    template = _get_template(template_name)
    project_root = project_root.expanduser().resolve()
    runtime_root = runtime_root.expanduser().resolve()
    task_id = str(template["task_id"])
    max_experiments = max_experiments or int(template["max_experiments"])
    experiment_duration = experiment_duration or int(template["experiment_duration"])

    task_dir = runtime_root / "tasks"
    data_dir = runtime_root / "data"
    workspace = runtime_root / "workdir" / task_id
    task_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    dataset_file = data_dir / f"demo_bytes_{VOCAB_SIZE}_{SEQ_LEN}.bin"
    task_file = task_dir / f"{task_id}.json"
    if task_file.exists() and not force:
        raise FileExistsError(str(task_file))

    dataset_file.write_bytes(_demo_bytes(DATASET_SIZE_BYTES))
    task = _build_task(
        template=template,
        project_root=project_root,
        task_id=task_id,
        dataset_file=dataset_file,
        max_experiments=max_experiments,
        experiment_duration=experiment_duration,
    )
    task_file.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return {
        "status": "initialized",
        "template": _public_template(template),
        "runtime_root": str(runtime_root),
        "task_id": task_id,
        "task_file": str(task_file),
        "dataset_file": str(dataset_file),
        "workspace": str(workspace),
        "run_command": _render_run_command(
            task_file=task_file,
            workspace=workspace,
            runtime_root=runtime_root,
            max_experiments=max_experiments,
            experiment_duration=experiment_duration,
        ),
    }


def run_demo_template(
    *,
    template_name: str,
    runtime_root: Path,
    project_root: Path,
    max_experiments: int | None = None,
    experiment_duration: int | None = None,
    force: bool = True,
    python_executable: str = sys.executable,
) -> dict[str, Any]:
    """Materialize and run a deterministic demo template through autoresearch."""
    if force:
        _reset_demo_run_artifacts(
            runtime_root=runtime_root,
            task_id=str(_get_template(template_name)["task_id"]),
        )
    initialized = materialize_demo_template(
        template_name=template_name,
        runtime_root=runtime_root,
        project_root=project_root,
        max_experiments=max_experiments,
        experiment_duration=experiment_duration,
        force=force,
    )
    project_root = project_root.expanduser().resolve()
    runtime_root = Path(initialized["runtime_root"])
    task_file = Path(initialized["task_file"])
    workspace = Path(initialized["workspace"])
    experiment_duration = experiment_duration or int(
        DEMO_TEMPLATES[template_name]["experiment_duration"]
    )
    max_experiments = max_experiments or int(DEMO_TEMPLATES[template_name]["max_experiments"])

    env = {
        **os.environ,
        "ML_RESEARCH_LOOP_ROOT": str(runtime_root),
        "ML_RESEARCH_LOOP_PYTHON": python_executable,
        "PYTHONPATH": _pythonpath_for_project(project_root),
    }
    proc = subprocess.run(
        [
            python_executable,
            str(project_root / "scripts" / "autoresearch_run.py"),
            "--task-config",
            str(task_file),
            "--workspace",
            str(workspace),
            "--max-experiments",
            str(max_experiments),
            "--experiment-duration",
            str(experiment_duration),
        ],
        cwd=project_root,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=max(90, experiment_duration + 60),
    )
    result_file = runtime_root / "results" / f"{initialized['task_id']}.json"
    result = _read_json(result_file) if result_file.exists() else {}
    best_metric = _best_metric(result)
    status = result.get("status") or ("failed" if proc.returncode else "completed")
    return {
        "status": status,
        "template": initialized["template"],
        "runtime_root": str(runtime_root),
        "task_id": initialized["task_id"],
        "task_file": initialized["task_file"],
        "dataset_file": initialized["dataset_file"],
        "workspace": initialized["workspace"],
        "result_file": str(result_file),
        "best_metric": best_metric,
        "best_result": result.get("best_result"),
        "summary": result.get("summary"),
        "returncode": proc.returncode,
        "stdout_tail": "\n".join(proc.stdout.splitlines()[-20:]),
    }


def _reset_demo_run_artifacts(runtime_root: Path, task_id: str) -> None:
    """Remove stale task-specific artifacts before a force-rerun."""
    runtime_root = runtime_root.expanduser().resolve()
    for file_path in [
        runtime_root / "results" / f"{task_id}.json",
        runtime_root / "results" / f"{task_id}-progress.json",
    ]:
        if file_path.exists():
            file_path.unlink()
    for dir_path in [
        runtime_root / "workdir" / task_id,
        runtime_root / "snapshots" / task_id,
        runtime_root / "checkpoints" / task_id,
    ]:
        if dir_path.exists():
            shutil.rmtree(dir_path)


def _get_template(template_name: str) -> dict[str, Any]:
    try:
        return DEMO_TEMPLATES[template_name]
    except KeyError as exc:
        names = ", ".join(DEMO_TEMPLATES)
        raise ValueError(f"Unknown demo template: {template_name}. Available: {names}") from exc


def _public_template(template: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in template.items()
        if key
        in {
            "name",
            "description",
            "task_id",
            "task_type",
            "estimated_seconds",
            "max_experiments",
            "experiment_duration",
        }
    }


def _build_task(
    *,
    template: dict[str, Any],
    project_root: Path,
    task_id: str,
    dataset_file: Path,
    max_experiments: int,
    experiment_duration: int,
) -> dict[str, Any]:
    task = {
        "task_id": task_id,
        "objective": "minimize val_bpb on a deterministic local byte dataset",
        "dataset": {
            "name": template["name"],
            "path": str(dataset_file),
            "type": "binary",
            "vocab_size": VOCAB_SIZE,
            "max_seq_len": SEQ_LEN,
        },
        "metric": {"name": "val_bpb", "direction": "minimize", "threshold": 0.0},
        "hyperparameter_space": deepcopy(template["hyperparameter_space"]),
        "budget": {
            "max_experiments": max_experiments,
            "max_duration_minutes": 5,
            "experiment_duration_seconds": experiment_duration,
        },
        "base_code": {
            "train_py_url": f"file://{project_root / 'base' / 'train_base.py'}",
            "prepare_py_url": f"file://{project_root / 'base' / 'prepare.py'}",
        },
    }
    for key in [
        "research_context",
        "hypotheses",
        "reproduction_spec",
        "program_md_overrides",
    ]:
        if key in template:
            task[key] = deepcopy(template[key])
    return task


def _demo_bytes(length: int) -> bytes:
    return bytes((index * 17 + 11) % VOCAB_SIZE for index in range(length))


def _render_run_command(
    *,
    task_file: Path,
    workspace: Path,
    runtime_root: Path,
    max_experiments: int,
    experiment_duration: int,
) -> str:
    return " ".join([
        f'ML_RESEARCH_LOOP_ROOT="{runtime_root}"',
        'ml-loop run',
        f'--task-config "{task_file}"',
        f'--workspace "{workspace}"',
        f"--max-experiments {max_experiments}",
        f"--experiment-duration {experiment_duration}",
    ])


def _pythonpath_for_project(project_root: Path) -> str:
    parts = [str(project_root)]
    site_packages = project_root / ".venv" / "lib"
    if site_packages.exists():
        parts.extend(str(path) for path in sorted(site_packages.glob("python*/site-packages")))
    if os.environ.get("PYTHONPATH"):
        parts.append(os.environ["PYTHONPATH"])
    return os.pathsep.join(parts)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _best_metric(result: dict[str, Any]) -> dict[str, Any] | None:
    best = result.get("best_result")
    if not isinstance(best, dict) or best.get("val") is None:
        return None
    return {
        "name": "val_bpb",
        "value": best.get("val"),
        "experiment_id": best.get("experiment_id"),
    }
