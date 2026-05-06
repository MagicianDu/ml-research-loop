"""Tests for task_protocol.py."""

from pathlib import Path

import pytest

from lib.task_protocol import (
    TaskDefinition,
    DatasetConfig,
    MetricConfig,
    HyperparamSpace,
    BudgetConfig,
    BaseCodeConfig,
    ProgramMdOverrides,
    TaskStatus,
    TaskResult,
    MetricDirection,
    write_task,
    read_task,
    write_result,
    read_result,
    write_progress,
    read_progress,
    ensure_dirs,
)


@pytest.fixture
def temp_workspace(tmp_path, monkeypatch):
    """Set up temporary workspace for tests."""
    monkeypatch.setenv("ML_RESEARCH_LOOP_ROOT", str(tmp_path))
    from lib import task_protocol
    task_protocol.WORKSPACE_ROOT = tmp_path
    task_protocol.TASKS_DIR = tmp_path / "tasks"
    task_protocol.RESULTS_DIR = tmp_path / "results"
    ensure_dirs()
    return tmp_path


class TestTaskDefinition:
    def test_to_dict_from_dict_roundtrip(self):
        task = TaskDefinition(
            task_id="test-001",
            objective="minimize val_bpb",
            dataset=DatasetConfig(name="test", path="/data/test.bin"),
            metric=MetricConfig(name="val_bpb", direction=MetricDirection.MINIMIZE),
            hyperparameter_space={
                "lr": HyperparamSpace(type="log_uniform", min=1e-5, max=1e-2),
                "depth": HyperparamSpace(type="choice", values=[4, 6, 8]),
            },
            budget=BudgetConfig(max_experiments=50),
            base_code=BaseCodeConfig(
                train_py_url="file:///base/train.py",
                prepare_py_url="file:///base/prepare.py",
            ),
        )

        data = task.to_dict()
        restored = TaskDefinition.from_dict(data)

        assert restored.task_id == task.task_id
        assert restored.objective == task.objective
        assert restored.dataset.name == task.dataset.name
        assert restored.metric.direction == task.metric.direction
        assert "lr" in restored.hyperparameter_space
        assert restored.budget.max_experiments == 50

    def test_research_context_and_hypotheses_roundtrip(self):
        task = TaskDefinition(
            task_id="research-test-001",
            objective="minimize val_bpb with research context",
            dataset=DatasetConfig(name="test", path="/data/test.bin"),
            metric=MetricConfig(name="val_bpb", direction=MetricDirection.MINIMIZE),
            hyperparameter_space={},
            budget=BudgetConfig(max_experiments=1),
            base_code=BaseCodeConfig(
                train_py_url="file:///base/train.py",
                prepare_py_url="file:///base/prepare.py",
            ),
            research_context={
                "objective": "minimize val_bpb",
                "sources": [
                    {
                        "source_type": "paper",
                        "title": "ALiBi",
                        "url": "https://arxiv.org/abs/2108.12409",
                    }
                ],
            },
            hypotheses=[
                {
                    "hypothesis_id": "hyp-001",
                    "title": "Try ALiBi",
                    "rationale": "Research-backed positional bias.",
                    "expected_metric": "val_bpb",
                    "expected_direction": "minimize",
                }
            ],
        )

        restored = TaskDefinition.from_dict(task.to_dict())

        assert restored.research_context["sources"][0]["title"] == "ALiBi"
        assert restored.hypotheses[0]["hypothesis_id"] == "hyp-001"

    def test_sampling_constraints_roundtrip(self):
        task = TaskDefinition(
            task_id="sampling-test-001",
            objective="minimize val_bpb",
            dataset=DatasetConfig(name="test", path="/data/test.bin"),
            metric=MetricConfig(name="val_bpb", direction=MetricDirection.MINIMIZE),
            hyperparameter_space={},
            budget=BudgetConfig(max_experiments=1),
            base_code=BaseCodeConfig(
                train_py_url="file:///base/train.py",
                prepare_py_url="file:///base/prepare.py",
            ),
            sampling_constraints={
                "avoid_params": [{"lr": 0.01, "depth": 4}],
            },
        )

        restored = TaskDefinition.from_dict(task.to_dict())

        assert restored.sampling_constraints == {
            "avoid_params": [{"lr": 0.01, "depth": 4}],
        }

    def test_reproduction_spec_roundtrip(self):
        task = TaskDefinition(
            task_id="repro-test-001",
            objective="reproduce a local training result",
            dataset=DatasetConfig(name="test", path="/data/test.bin"),
            metric=MetricConfig(name="val_bpb", direction=MetricDirection.MINIMIZE),
            hyperparameter_space={},
            budget=BudgetConfig(max_experiments=1),
            base_code=BaseCodeConfig(
                train_py_url="file:///base/train.py",
                prepare_py_url="file:///base/prepare.py",
            ),
            reproduction_spec={
                "mode": "local_command",
                "command": ["python", "train.py"],
                "timeout_seconds": 60,
                "required_files": ["train.py", "program.md"],
            },
        )

        restored = TaskDefinition.from_dict(task.to_dict())

        assert restored.reproduction_spec == {
            "mode": "local_command",
            "command": ["python", "train.py"],
            "timeout_seconds": 60,
            "required_files": ["train.py", "program.md"],
        }
        assert restored.to_dict()["reproduction_spec"] == restored.reproduction_spec

    def test_program_md_overrides_roundtrip(self):
        task = TaskDefinition(
            task_id="override-test-001",
            objective="minimize val_bpb",
            dataset=DatasetConfig(name="test", path="/data/test.bin"),
            metric=MetricConfig(name="val_bpb", direction=MetricDirection.MINIMIZE),
            hyperparameter_space={},
            budget=BudgetConfig(max_experiments=1),
            base_code=BaseCodeConfig(
                train_py_url="file:///base/train.py",
                prepare_py_url="file:///base/prepare.py",
            ),
            program_md_overrides=ProgramMdOverrides(
                focus_areas=["local refinement"],
                forbidden_changes=["do not edit prepare.py"],
                hints=["Continue from exp-002."],
            ),
        )

        restored = TaskDefinition.from_dict(task.to_dict())

        assert restored.program_md_overrides.focus_areas == ["local refinement"]
        assert restored.program_md_overrides.forbidden_changes == ["do not edit prepare.py"]
        assert restored.program_md_overrides.hints == ["Continue from exp-002."]

    def test_legacy_task_without_research_fields_still_roundtrips(self):
        restored = TaskDefinition.from_dict({
            "task_id": "legacy-001",
            "objective": "minimize val_bpb",
            "dataset": {"name": "test", "path": "/data/test.bin"},
            "metric": {"name": "val_bpb", "direction": "minimize"},
            "hyperparameter_space": {},
            "budget": {},
            "base_code": {
                "train_py_url": "file:///base/train.py",
                "prepare_py_url": "file:///base/prepare.py",
            },
        })

        assert restored.research_context is None
        assert restored.hypotheses == []
        assert restored.sampling_constraints == {}
        assert restored.reproduction_spec is None
        assert restored.program_md_overrides == ProgramMdOverrides()


class TestWorkspaceRoot:
    def test_workspace_root_defaults_to_project_root_when_env_missing(self, monkeypatch):
        from lib import task_protocol

        monkeypatch.delenv("ML_RESEARCH_LOOP_ROOT", raising=False)
        root = task_protocol.resolve_workspace_root()
        expected_root = Path(task_protocol.__file__).resolve().parents[1]

        assert root == expected_root
        assert (root / "pyproject.toml").exists()

    def test_workspace_root_uses_env_override(self, tmp_path, monkeypatch):
        from lib import task_protocol

        monkeypatch.setenv("ML_RESEARCH_LOOP_ROOT", str(tmp_path))

        assert task_protocol.resolve_workspace_root() == tmp_path.resolve()


class TestTaskResult:
    def test_to_dict_from_dict_roundtrip(self):
        result = TaskResult(
            task_id="test-001",
            status=TaskStatus.COMPLETED,
            best_result={"val": 0.85, "params": {"lr": 0.001}},
            experiments=[
                {"experiment_id": "exp-1", "accepted": True, "metrics": {"val_bpb": 0.85}},
                {"experiment_id": "exp-2", "accepted": False, "metrics": {"val_bpb": 0.90}},
            ],
            summary={"total_experiments": 2, "accepted": 1},
            finished_at="2026-04-27T10:00:00Z",
        )

        data = result.to_dict()
        restored = TaskResult.from_dict(data)

        assert restored.task_id == result.task_id
        assert restored.status == TaskStatus.COMPLETED
        assert restored.best_result["val"] == 0.85
        assert len(restored.experiments) == 2

    def test_research_lineage_roundtrip(self):
        result = TaskResult(
            task_id="test-001",
            status=TaskStatus.COMPLETED,
            research_context={
                "sources": [
                    {
                        "source_type": "paper",
                        "title": "ALiBi",
                        "url": "https://arxiv.org/abs/2108.12409",
                    }
                ]
            },
            hypotheses=[
                {
                    "hypothesis_id": "hyp-001",
                    "title": "Try ALiBi",
                    "rationale": "Research-backed positional bias.",
                }
            ],
        )

        data = result.to_dict()
        restored = TaskResult.from_dict(data)

        assert data["research_context"]["sources"][0]["title"] == "ALiBi"
        assert restored.research_context["sources"][0]["source_type"] == "paper"
        assert restored.hypotheses[0]["hypothesis_id"] == "hyp-001"

    def test_experiment_tree_and_grade_report_roundtrip(self):
        result = TaskResult(
            task_id="test-001",
            status=TaskStatus.COMPLETED,
            experiment_tree={
                "best_node_id": "exp-001",
                "nodes": {"exp-001": {"stage": "draft"}},
            },
            grade_report={
                "score": 0.5,
                "num_leaf_nodes": 2,
                "num_invalid_leaf_nodes": 0,
            },
        )

        data = result.to_dict()
        restored = TaskResult.from_dict(data)

        assert restored.experiment_tree["best_node_id"] == "exp-001"
        assert restored.grade_report["score"] == 0.5


class TestFileOperations:
    def test_write_and_read_task(self, temp_workspace):
        task = TaskDefinition(
            task_id="write-test-001",
            objective="test",
            dataset=DatasetConfig(name="test", path="/data/test.bin"),
            metric=MetricConfig(name="val_bpb", direction=MetricDirection.MINIMIZE),
            hyperparameter_space={},
            budget=BudgetConfig(),
            base_code=BaseCodeConfig(train_py_url="file:///a", prepare_py_url="file:///b"),
        )

        path = write_task(task)
        assert path.exists()

        restored = read_task("write-test-001")
        assert restored.task_id == "write-test-001"
        assert restored.objective == "test"

    def test_write_and_read_result(self, temp_workspace):
        result = TaskResult(
            task_id="result-test-001",
            status=TaskStatus.COMPLETED,
        )

        write_result(result)

        restored = read_result("result-test-001")
        assert restored.task_id == "result-test-001"
        assert restored.status == TaskStatus.COMPLETED

    def test_write_and_read_progress(self, temp_workspace):
        progress_data = {
            "task_id": "progress-test-001",
            "status": "running",
            "experiment_index": 5,
            "max_experiments": 50,
            "best_val": 0.85,
            "progress_pct": 10.0,
        }

        write_progress("progress-test-001", progress_data)

        restored = read_progress("progress-test-001")
        assert restored["experiment_index"] == 5
        assert restored["best_val"] == 0.85
        assert restored["progress_pct"] == 10.0

    def test_read_nonexistent_task_raises(self, temp_workspace):
        from lib.exceptions import TaskNotFoundError
        with pytest.raises(TaskNotFoundError):
            read_task("nonexistent-task")


class TestMetricDirection:
    def test_minimize_direction(self):
        assert MetricDirection.MINIMIZE.value == "minimize"
        assert MetricDirection.MAXIMIZE.value == "maximize"
