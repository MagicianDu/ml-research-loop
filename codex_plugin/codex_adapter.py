# codex_plugin/codex_adapter.py
"""
ml-research-loop Codex plugin adapter.
Wraps ml-research-loop capabilities as Codex-callable tools.
"""

from pathlib import Path
import sys

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from ml_intern.autoresearch_manager import (  # noqa: E402
    AutoResearchManager,
    create_autoresearch_task,
)
from lib.exceptions import ResultNotReadyError  # noqa: E402
from lib.task_protocol import TaskResult, read_progress, read_result  # noqa: E402

WORKSPACE_ROOT = PROJECT_ROOT


def _result_to_dict(result: TaskResult | dict) -> dict:
    """Normalize current TaskResult objects and legacy dict payloads."""
    if isinstance(result, TaskResult):
        return result.to_dict()
    return result


class MLResearchLoopCodexAdapter:
    """
    Codex tool adapter for ml-research-loop.
    Exposes three tools:
      - run_ml_experiment
      - get_ml_experiment_status
      - get_ml_experiment_results
    """

    def __init__(self, workspace_root: Path = WORKSPACE_ROOT):
        self.workspace = workspace_root
        self.manager = AutoResearchManager(workspace_root=workspace_root)

    def run_ml_experiment(self, config: dict) -> dict:
        """
        Launch an ML experiment loop.

        Args:
            config: MLExperimentConfig serialized dict.
                Required keys: task_id, objective, metric
                Optional keys: dataset, hyperparameter_space,
                               max_experiments, experiment_duration_seconds

        Returns:
            dict with keys: success, task_id, status, message
        """
        task_id = config["task_id"]
        objective = config["objective"]
        metric_name = config["metric"]
        dataset = config.get("dataset", {})
        hyperparameter_space = config.get("hyperparameter_space", {})
        max_experiments = config.get("max_experiments", 50)
        experiment_duration = config.get("experiment_duration_seconds", 300)

        # Infer metric direction
        if metric_name in ("val_bpb", "val_loss", "val_perplexity"):
            direction = "minimize"
        else:
            direction = "maximize"

        result_task_id = create_autoresearch_task(
            task_id=task_id,
            objective=objective,
            dataset_path=dataset.get("path", "data/train.bin"),
            metric_name=metric_name,
            metric_direction=direction,
            max_experiments=max_experiments,
            max_duration_minutes=max_experiments * experiment_duration // 60,
            experiment_duration_seconds=experiment_duration,
            hyperparameter_space=hyperparameter_space if hyperparameter_space else None,
        )

        return {
            "success": True,
            "task_id": result_task_id,
            "status": "launched",
            "message": (
                f"ML experiment launched: {result_task_id}. "
                "Use get_ml_experiment_status to monitor progress."
            ),
        }

    def get_ml_experiment_status(self, task_id: str) -> dict:
        """
        Query experiment progress.

        Args:
            task_id: The task identifier.

        Returns:
            dict with keys: success, task_id, status, experiment_index,
                            max_experiments, best_val, best_params,
                            progress_pct, message
        """
        try:
            progress = read_progress(task_id)
            return {
                "success": True,
                "task_id": task_id,
                "status": progress.get("status", "unknown"),
                "experiment_index": progress.get("experiment_index", 0),
                "max_experiments": progress.get("max_experiments", 0),
                "best_val": progress.get("best_val"),
                "best_params": progress.get("best_params"),
                "progress_pct": progress.get("progress_pct", 0.0),
                "message": (
                    f"Experiment {progress.get('experiment_index', 0)}"
                    f"/{progress.get('max_experiments', 0)}, "
                    f"best={progress.get('best_val')}"
                ),
            }
        except FileNotFoundError:
            return {
                "success": False,
                "task_id": task_id,
                "status": "not_found",
                "message": (
                    f"Task {task_id} not found. "
                    "Make sure the task_id is correct."
                ),
            }

    def get_ml_experiment_results(self, task_id: str) -> dict:
        """
        Fetch final experiment results.

        Args:
            task_id: The task identifier.

        Returns:
            dict with keys: success, task_id, status, best_val, best_params,
                            total_experiments, total_duration_minutes,
                            improvements, message
        """
        try:
            result = _result_to_dict(read_result(task_id))
            best_result = result.get("best_result", {})
            summary = result.get("summary", {})
            best_val = best_result.get("metric", best_result.get("val"))
            total_duration = summary.get(
                "total_wall_clock_minutes",
                summary.get("total_duration_minutes", 0),
            )
            return {
                "success": True,
                "task_id": task_id,
                "status": result.get("status", "unknown"),
                "best_val": best_val,
                "best_params": best_result.get("params"),
                "total_experiments": summary.get("total_experiments", 0),
                "total_duration_minutes": total_duration,
                "improvements": best_result.get("improvements", []),
                "message": (
                    f"Best metric="
                    f"{best_val} "
                    f"with {best_result.get('params')}"
                ),
            }
        except (FileNotFoundError, ResultNotReadyError):
            return {
                "success": False,
                "task_id": task_id,
                "status": "not_ready",
                "message": (
                    f"Results for {task_id} not ready yet. "
                    "Use get_ml_experiment_status to check progress."
                ),
            }
