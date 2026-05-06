from __future__ import annotations

import json
from types import SimpleNamespace
from pathlib import Path

from lib.demo_templates import (
    DEMO_TEMPLATES,
    list_demo_templates,
    materialize_demo_template,
    run_demo_template,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_list_demo_templates_exposes_stable_entry_points() -> None:
    templates = list_demo_templates()

    names = [template["name"] for template in templates]
    assert names == [
        "byte-lm-smoke",
        "byte-lm-depth-sweep",
        "paper-guided-byte-lm",
    ]
    assert all(template["estimated_seconds"] <= 90 for template in templates)
    assert all(template["task_type"] == "byte_language_model" for template in templates)


def test_materialize_demo_template_writes_dataset_task_and_run_command(tmp_path: Path) -> None:
    payload = materialize_demo_template(
        template_name="byte-lm-smoke",
        runtime_root=tmp_path / "runtime",
        project_root=PROJECT_ROOT,
        max_experiments=1,
        experiment_duration=30,
    )

    task_file = Path(payload["task_file"])
    dataset_file = Path(payload["dataset_file"])
    task = json.loads(task_file.read_text(encoding="utf-8"))

    assert payload["status"] == "initialized"
    assert payload["template"]["name"] == "byte-lm-smoke"
    assert dataset_file.exists()
    assert dataset_file.read_bytes()[:8] == bytes([11, 28, 45, 62, 15, 32, 49, 2])
    assert task["task_id"] == "demo-byte-lm-smoke"
    assert task["dataset"]["path"] == str(dataset_file)
    assert task["base_code"]["train_py_url"] == f"file://{PROJECT_ROOT / 'base' / 'train_base.py'}"
    assert task["budget"]["max_experiments"] == 1
    assert task["budget"]["experiment_duration_seconds"] == 30
    assert "ml-loop run" in payload["run_command"]


def test_paper_guided_template_includes_research_context_and_reproduction_spec(
    tmp_path: Path,
) -> None:
    payload = materialize_demo_template(
        template_name="paper-guided-byte-lm",
        runtime_root=tmp_path / "runtime",
        project_root=PROJECT_ROOT,
        max_experiments=1,
        experiment_duration=30,
    )

    task = json.loads(Path(payload["task_file"]).read_text(encoding="utf-8"))

    assert task["research_context"]["query"] == "compact transformer byte language model"
    assert task["hypotheses"][0]["id"] == "paper-guided-byte-lm-h1"
    assert task["reproduction_spec"]["paper"]["title"] == "Attention Is All You Need"
    assert task["program_md_overrides"]["focus_areas"]


def test_unknown_demo_template_raises_clear_error(tmp_path: Path) -> None:
    assert "byte-lm-smoke" in DEMO_TEMPLATES

    try:
        materialize_demo_template(
            template_name="missing",
            runtime_root=tmp_path / "runtime",
            project_root=PROJECT_ROOT,
            max_experiments=1,
            experiment_duration=30,
        )
    except ValueError as exc:
        assert "Unknown demo template: missing" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_run_demo_template_force_removes_stale_result_before_launch(
    tmp_path: Path,
    monkeypatch,
) -> None:
    runtime_root = tmp_path / "runtime"
    stale_result = runtime_root / "results" / "demo-byte-lm-smoke.json"
    stale_workdir = runtime_root / "workdir" / "demo-byte-lm-smoke"
    stale_result.parent.mkdir(parents=True)
    stale_workdir.mkdir(parents=True)
    stale_result.write_text(
        json.dumps({"task_id": "demo-byte-lm-smoke", "status": "completed"}),
        encoding="utf-8",
    )
    (stale_workdir / "stale.txt").write_text("old", encoding="utf-8")

    def fake_run(argv, cwd, env, text, stdout, stderr, timeout):
        assert not stale_result.exists()
        assert not stale_workdir.exists()
        result_file = Path(env["ML_RESEARCH_LOOP_ROOT"]) / "results" / "demo-byte-lm-smoke.json"
        result_file.parent.mkdir(parents=True, exist_ok=True)
        result_file.write_text(
            json.dumps({
                "task_id": "demo-byte-lm-smoke",
                "status": "completed",
                "best_result": {"experiment_id": "exp-001", "val": 1.23},
            }),
            encoding="utf-8",
        )
        return SimpleNamespace(returncode=0, stdout="STATUS=completed\n")

    monkeypatch.setattr("lib.demo_templates.subprocess.run", fake_run)

    payload = run_demo_template(
        template_name="byte-lm-smoke",
        runtime_root=runtime_root,
        project_root=PROJECT_ROOT,
        max_experiments=1,
        experiment_duration=30,
        python_executable="python3",
    )

    assert payload["status"] == "completed"
    assert payload["best_metric"]["value"] == 1.23
