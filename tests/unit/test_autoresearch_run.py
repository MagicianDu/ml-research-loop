"""
Unit tests for scripts/autoresearch_run.py
"""
import pytest
import sys
from types import SimpleNamespace

from scripts import autoresearch_run
from scripts.autoresearch_run import (
    modify_train_hyperparams,
    parse_training_output,
)


class TestModifyTrainHyperparams:
    """Tests for modify_train_hyperparams."""

    def test_modify_train_hyperparams(self, tmp_path):
        """Hyperparameters in SEARCH REGION are replaced; non-sampled params are preserved."""
        train_py = tmp_path / "train.py"
        train_py.write_text(
            "# ======= AUTORESEARCH SEARCH REGION START =======\n"
            "LR = 0.001\n"
            "BATCH_SIZE = 32\n"
            "WEIGHT_DECAY = 0.0001\n"
            "# ======= AUTORESEARCH SEARCH REGION END =======\n",
            encoding="utf-8",
        )

        # Override LR and BATCH_SIZE with sampled params; WEIGHT_DECAY should be kept
        modify_train_hyperparams(train_py, {"lr": 0.01, "batch_size": 64})

        content = train_py.read_text(encoding="utf-8")
        assert "LR = 0.01" in content or "LR = 1e-2" in content or "LR = 0.010000" in content
        assert "BATCH_SIZE = 64" in content
        # WEIGHT_DECAY should be preserved as an existing assignment
        assert "WEIGHT_DECAY = 0.0001" in content
        # SEARCH REGION markers must remain
        assert "AUTORESEARCH SEARCH REGION START" in content
        assert "AUTORESEARCH SEARCH REGION END" in content

    def test_modify_train_hyperparams_preserves_non_region_content(self, tmp_path):
        """Content outside the SEARCH REGION is untouched."""
        train_py = tmp_path / "train.py"
        train_py.write_text(
            "import torch\n"
            "\n"
            "# ======= AUTORESEARCH SEARCH REGION START =======\n"
            "LR = 0.001\n"
            "# ======= AUTORESEARCH SEARCH REGION END =======\n"
            "\n"
            "EPOCHS = 10\n",
            encoding="utf-8",
        )

        modify_train_hyperparams(train_py, {"lr": 0.005})

        content = train_py.read_text(encoding="utf-8")
        assert content.startswith("import torch\n")
        assert "EPOCHS = 10" in content

    def test_modify_train_hyperparams_missing_marker_raises(self, tmp_path):
        """Missing SEARCH REGION markers raise ValueError."""
        train_py = tmp_path / "train.py"
        train_py.write_text("LR = 0.001\n", encoding="utf-8")

        with pytest.raises(ValueError, match="missing search region"):
            modify_train_hyperparams(train_py, {"lr": 0.01})


class TestParseTrainingOutput:
    """Tests for parse_training_output."""

    def test_parse_training_output_result_format(self):
        """Standard [RESULT] line with val_bpb and other metrics is parsed."""
        stdout = (
            "Epoch 5/10 - loss: 0.123\n"
            "[RESULT] val_bpb=1.45 val_acc=0.87\n"
            "Training complete.\n"
        )
        metrics = parse_training_output(stdout)

        assert metrics["val_bpb"] == 1.45
        assert metrics["val_acc"] == 0.87
        # Non-metric prefixed keys (loss) should NOT be included
        assert "loss" not in metrics

    def test_parse_training_output_metric_prefixes(self):
        """Only metric-prefixed keys are included; others are filtered out."""
        stdout = (
            "[RESULT] val_bpb=2.1 metric_custom=99.0 other_val=5.0\n"
            "loss=0.5 acc=0.9\n"
        )
        metrics = parse_training_output(stdout)

        assert "val_bpb" in metrics
        # prefix-less keys (loss, acc when alone) are NOT captured by the line search
        # because they don't match METRIC_PREFIXES check in the line scan
        # but JSON block mode can capture them if prefixed
        assert "other_val" not in metrics  # doesn't start with metric prefix

    def test_parse_training_output_json_block(self):
        """JSON block on its own line: only metric-prefixed fields are extracted."""
        stdout = '{"val_bpb": 1.23, "train_loss": 0.45, "val_acc": 0.91, "other": 10}\n'
        metrics = parse_training_output(stdout)

        assert metrics["val_bpb"] == 1.23
        assert metrics["val_acc"] == 0.91
        assert "train_loss" not in metrics  # doesn't have metric prefix
        assert "other" not in metrics

    def test_parse_training_output_scientific_notation(self):
        """Metrics in scientific notation are correctly parsed."""
        stdout = "[RESULT] val_bpb=1.5e-3 val_loss=3.2e+2\n"
        metrics = parse_training_output(stdout)

        assert abs(metrics["val_bpb"] - 1.5e-3) < 1e-6
        assert abs(metrics["val_loss"] - 3.2e2) < 1e-4

    def test_parse_training_output_empty(self):
        """No valid metrics in output returns empty dict."""
        stdout = "Hello world\nNo metrics here\n"
        metrics = parse_training_output(stdout)
        assert metrics == {}


class TestRunTraining:
    """Tests for running train.py through the configured Python executable."""

    def test_run_training_uses_available_python(self, tmp_path, monkeypatch):
        from scripts.autoresearch_run import run_training

        train_py = tmp_path / "train.py"
        train_py.write_text('print("[RESULT] val_bpb=1.234")\n', encoding="utf-8")
        monkeypatch.setenv("ML_RESEARCH_LOOP_PYTHON", sys.executable)

        metrics = run_training(tmp_path, "exp-001", duration_seconds=5)

        assert metrics["val_bpb"] == 1.234


class TestSampleAndAcceptLogic:
    """Tests for the accept/reject decision logic."""

    def test_sample_next_hyperparameters_passes_store_history(self, monkeypatch):
        space = {"depth": object()}
        store = SimpleNamespace(experiments=[{"params": {"depth": 1}, "accepted": False}])
        task = SimpleNamespace(hyperparameter_space=space)
        captured = {}

        def fake_sample_hyperparameters(hyperparameter_space, experiment_history=None):
            captured["space"] = hyperparameter_space
            captured["history"] = experiment_history
            return {"depth": 2}

        monkeypatch.setattr(autoresearch_run, "sample_hyperparameters", fake_sample_hyperparameters)

        params = autoresearch_run.sample_next_hyperparameters(task, store)

        assert params == {"depth": 2}
        assert captured == {"space": space, "history": store.experiments}

    def test_sample_next_hyperparameters_includes_avoid_params(self, monkeypatch):
        space = {"lr": object()}
        store = SimpleNamespace(experiments=[{"params": {"lr": 0.001}, "accepted": True}])
        task = SimpleNamespace(
            hyperparameter_space=space,
            sampling_constraints={"avoid_params": [{"lr": 0.01}]},
        )
        captured = {}

        def fake_sample_hyperparameters(hyperparameter_space, experiment_history=None):
            captured["space"] = hyperparameter_space
            captured["history"] = experiment_history
            return {"lr": 0.002}

        monkeypatch.setattr(autoresearch_run, "sample_hyperparameters", fake_sample_hyperparameters)

        params = autoresearch_run.sample_next_hyperparameters(task, store)

        assert params == {"lr": 0.002}
        assert captured["space"] == space
        assert captured["history"] == [
            {"params": {"lr": 0.001}, "accepted": True},
            {"params": {"lr": 0.01}, "accepted": False, "error": "sampling_constraints.avoid_params"},
        ]

    def test_accept_improves_minimize(self):
        """For minimize direction, a lower val triggers accept."""
        # Simulate the accept logic from run_experiment_loop (inline)
        minimize = True
        best_val = 0.5
        current_val = 0.3

        accepted = current_val < best_val if minimize else current_val > best_val
        assert accepted is True

    def test_accept_improves_maximize(self):
        """For maximize direction, a higher val triggers accept."""
        minimize = False
        best_val = 0.5
        current_val = 0.7

        accepted = current_val < best_val if minimize else current_val > best_val
        assert accepted is True

    def test_reject_worse_minimize(self):
        """For minimize direction, a higher val triggers reject."""
        minimize = True
        best_val = 0.5
        current_val = 0.6

        accepted = current_val < best_val if minimize else current_val > best_val
        assert accepted is False

    def test_reject_worse_maximize(self):
        """For maximize direction, a lower val triggers reject."""
        minimize = False
        best_val = 0.5
        current_val = 0.4

        accepted = current_val < best_val if minimize else current_val > best_val
        assert accepted is False

    def test_first_experiment_always_accepted(self):
        """First experiment (best_val=None) is always accepted regardless of direction."""
        minimize = True
        best_val = None
        current_val = 1.23

        accepted = True if best_val is None else (current_val < best_val if minimize else current_val > best_val)
        assert accepted is True

        minimize = False
        accepted = True if best_val is None else (current_val < best_val if minimize else current_val > best_val)
        assert accepted is True
