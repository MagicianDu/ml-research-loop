"""Tests for generate_program_md.py."""



from lib.task_protocol import (
    TaskDefinition,
    DatasetConfig,
    MetricConfig,
    HyperparamSpace,
    BudgetConfig,
    BaseCodeConfig,
    MetricDirection,
)
from scripts.generate_program_md import generate_program_md


class TestGenerateProgramMd:
    def test_generates_valid_program_md(self):
        task = TaskDefinition(
            task_id="test-001",
            objective="minimize val_bpb",
            dataset=DatasetConfig(name="test", path="/data/test.bin"),
            metric=MetricConfig(name="val_bpb", direction=MetricDirection.MINIMIZE),
            hyperparameter_space={
                "lr": HyperparamSpace(type="log_uniform", min=1e-5, max=1e-2),
                "depth": HyperparamSpace(type="choice", values=[4, 6, 8]),
            },
            budget=BudgetConfig(max_experiments=50, experiment_duration_seconds=300),
            base_code=BaseCodeConfig(
                train_py_url="file:///base/train.py",
                prepare_py_url="file:///base/prepare.py",
            ),
        )

        program = generate_program_md(task)

        assert "minimize val_bpb" in program
        assert "test" in program
        assert "/data/test.bin" in program
        assert "lr" in program
        assert "depth" in program
        assert "AUTORESEARCH SEARCH REGION" in program
        assert "50 experiments" in program
        assert "5 minutes" in program  # 300 seconds = 5 minutes

    def test_maximize_direction(self):
        task = TaskDefinition(
            task_id="test-002",
            objective="maximize val_accuracy",
            dataset=DatasetConfig(name="test", path="/data/test.bin"),
            metric=MetricConfig(name="val_accuracy", direction=MetricDirection.MAXIMIZE),
            hyperparameter_space={},
            budget=BudgetConfig(),
            base_code=BaseCodeConfig(
                train_py_url="file:///a",
                prepare_py_url="file:///b",
            ),
        )

        program = generate_program_md(task)

        assert "maximize val_accuracy" in program
        assert "lower is worse" in program  # for maximize, higher accuracy is better so lower is worse
