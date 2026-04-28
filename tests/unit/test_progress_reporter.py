"""
Unit tests for lib/progress_reporter.py
"""
import json
from unittest.mock import patch

from lib.progress_reporter import ProgressReporter


class TestProgressReporter:
    """Tests for ProgressReporter."""

    def test_init_and_report(self, tmp_path):
        """init() creates progress file; report() updates it; content is correct."""
        # Monkey-patch RESULTS_DIR to tmp_path so we don't pollute real results/
        with patch("lib.progress_reporter.RESULTS_DIR", tmp_path):
            reporter = ProgressReporter(task_id="test-task")
            reporter.init(max_experiments=10)

            progress_file = tmp_path / "test-task-progress.json"
            assert progress_file.exists()

            # Verify init content
            data = json.loads(progress_file.read_text(encoding="utf-8"))
            assert data["task_id"] == "test-task"
            assert data["status"] == "running"
            assert data["experiment_index"] == 0
            assert data["max_experiments"] == 10
            assert data["progress_pct"] == 0.0

            # Report a few experiments
            reporter.report(
                experiment_index=3,
                best_val=0.42,
                best_params={"lr": 0.001},
                best_experiment_id="exp-003",
                last_accepted=True,
                last_val=0.42,
                elapsed_minutes=5.0,
                experiment_id="exp-003",
            )

            data = json.loads(progress_file.read_text(encoding="utf-8"))
            assert data["experiment_index"] == 3
            assert data["best_val"] == 0.42
            assert data["best_params"] == {"lr": 0.001}
            assert data["best_experiment_id"] == "exp-003"
            assert data["last_accepted"] is True
            assert data["progress_pct"] == 30.0
            assert data["elapsed_minutes"] == 5.0
            assert data["stuck_streak"] == 0  # accepted, so reset

    def test_doom_loop_warning(self, tmp_path):
        """Continuous rejections set doom_loop_warning=True and increment stuck_streak."""
        with patch("lib.progress_reporter.RESULTS_DIR", tmp_path):
            reporter = ProgressReporter(task_id="doom-test")
            reporter.init(max_experiments=10)

            progress_file = tmp_path / "doom-test-progress.json"

            # Simulate 5 consecutive rejected experiments
            for i in range(1, 6):
                reporter.report(
                    experiment_index=i,
                    best_val=0.5 if i > 1 else None,
                    best_params={"lr": 0.001},
                    best_experiment_id="exp-001",
                    last_accepted=False,
                    last_val=0.6,
                    elapsed_minutes=float(i),
                    experiment_id=f"exp-{i:03d}",
                )
                data = json.loads(progress_file.read_text(encoding="utf-8"))
                assert data["stuck_streak"] == i

            # After 5 consecutive rejections, doom_loop_warning should be True
            data = json.loads(progress_file.read_text(encoding="utf-8"))
            assert data["doom_loop_warning"] is True
            assert data["stuck_streak"] == 5

            # A successful experiment resets stuck_streak and doom_loop_warning
            reporter.report(
                experiment_index=6,
                best_val=0.3,
                best_params={"lr": 0.002},
                best_experiment_id="exp-006",
                last_accepted=True,
                last_val=0.3,
                elapsed_minutes=6.0,
                experiment_id="exp-006",
            )
            data = json.loads(progress_file.read_text(encoding="utf-8"))
            assert data["stuck_streak"] == 0
            assert data["doom_loop_warning"] is False

    def test_estimated_time_remaining(self, tmp_path):
        """Estimated time remaining is computed from avg time per completed experiment."""
        with patch("lib.progress_reporter.RESULTS_DIR", tmp_path):
            reporter = ProgressReporter(task_id="eta-test")
            reporter.init(max_experiments=10)

            progress_file = tmp_path / "eta-test-progress.json"

            # After 2 experiments in 4 minutes total, avg=2 min/exp
            # remaining = 10 - 2 = 8 exp × 2 min = 16 min
            reporter.report(
                experiment_index=2,
                best_val=0.5,
                best_params={},
                best_experiment_id="exp-002",
                last_accepted=True,
                last_val=0.5,
                elapsed_minutes=4.0,
                experiment_id="exp-002",
            )

            data = json.loads(progress_file.read_text(encoding="utf-8"))
            assert data["estimated_time_remaining_minutes"] == 16.0

            # At the end, no ETA needed
            reporter.report(
                experiment_index=10,
                best_val=0.1,
                best_params={},
                best_experiment_id="exp-010",
                last_accepted=True,
                last_val=0.1,
                elapsed_minutes=20.0,
                experiment_id="exp-010",
            )
            data = json.loads(progress_file.read_text(encoding="utf-8"))
            assert data["estimated_time_remaining_minutes"] == 0.0
