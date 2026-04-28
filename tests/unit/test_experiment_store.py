"""Tests for experiment_store.py."""


import pytest

from lib.experiment_store import ExperimentStore
from lib.task_protocol import ensure_dirs


@pytest.fixture
def temp_workdir(tmp_path):
    """Set up temporary workdir for tests."""
    workdir = tmp_path / "workdir"
    workdir.mkdir()
    ensure_dirs()
    return workdir


class TestExperimentStore:
    def test_add_experiment_updates_best(self, temp_workdir):
        store = ExperimentStore(task_id="test-001", workdir=temp_workdir)

        # First experiment - should become best
        updated = store.add_experiment(
            experiment_id="exp-1",
            params={"lr": 0.001},
            metrics={"val_bpb": 0.90},
            accepted=True,
        )
        assert updated is True
        assert store.best_val == 0.90
        assert store.best_params == {"lr": 0.001}
        assert store.best_experiment_id == "exp-1"

    def test_add_experiment_rejects_worse(self, temp_workdir):
        store = ExperimentStore(task_id="test-002", workdir=temp_workdir)

        store.add_experiment(
            experiment_id="exp-1",
            params={"lr": 0.001},
            metrics={"val_bpb": 0.90},
            accepted=True,
        )

        # Second experiment - worse, should be rejected
        updated = store.add_experiment(
            experiment_id="exp-2",
            params={"lr": 0.01},
            metrics={"val_bpb": 0.95},
            accepted=False,
        )
        assert updated is False
        assert store.best_val == 0.90  # Still the first one
        assert store.best_experiment_id == "exp-1"

    def test_add_experiment_accepts_better(self, temp_workdir):
        store = ExperimentStore(task_id="test-003", workdir=temp_workdir)

        store.add_experiment(
            experiment_id="exp-1",
            params={"lr": 0.001},
            metrics={"val_bpb": 0.90},
            accepted=True,
        )

        # Second experiment - better, should be accepted
        updated = store.add_experiment(
            experiment_id="exp-2",
            params={"lr": 0.0005},
            metrics={"val_bpb": 0.85},
            accepted=True,
        )
        assert updated is True
        assert store.best_val == 0.85
        assert store.best_params == {"lr": 0.0005}
        assert store.best_experiment_id == "exp-2"

    def test_persistence_after_save_and_load(self, temp_workdir):
        store = ExperimentStore(task_id="test-004", workdir=temp_workdir)

        store.add_experiment(
            experiment_id="exp-1",
            params={"lr": 0.001},
            metrics={"val_bpb": 0.90},
            accepted=True,
        )

        # Simulate reload
        new_store = ExperimentStore(task_id="test-004", workdir=temp_workdir).load()
        assert new_store.best_val == 0.90
        assert new_store.best_experiment_id == "exp-1"
        assert len(new_store.experiments) == 1

    def test_summary(self, temp_workdir):
        store = ExperimentStore(task_id="test-005", workdir=temp_workdir)

        store.add_experiment(
            experiment_id="exp-1",
            params={},
            metrics={},
            accepted=True,
        )
        store.add_experiment(
            experiment_id="exp-2",
            params={},
            metrics={},
            accepted=False,
            error="training failed",
        )

        summary = store.summary()
        assert summary["total"] == 2
        assert summary["accepted"] == 1
        assert summary["rejected"] == 1
        assert summary["failed"] == 1
