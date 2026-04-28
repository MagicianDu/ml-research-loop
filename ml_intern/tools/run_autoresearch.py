# ml_intern/tools/run_autoresearch.py
# smolagents Tool classes for ml-intern × autoresearch integration

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Optional

from smolagents import Tool
from ml_intern.autoresearch_manager import (
    create_autoresearch_task,
    AutoResearchManager,
)

if TYPE_CHECKING:
    pass


class RunAutoresearchTool(Tool):
    """
    Launch an autonomous ML research loop to optimize a neural network training script.

    Uses a fixed time budget per experiment, single-file editing constraint,
    and metric-based acceptance criteria. Best for: architecture search,
    optimizer tuning, hyperparameter optimization on a fixed dataset.

    Returns a task_id for monitoring progress via get_autoresearch_status.
    After completion, use get_autoresearch_result to retrieve the best config.
    """

    name = "run_autoresearch"
    description = """
Run an autonomous experiment loop to optimize a neural network training script.

Uses a fixed time budget per experiment (default 5 minutes), single-file editing constraint,
and metric-based acceptance. Best for: architecture search, optimizer tuning,
hyperparameter optimization on a fixed dataset.

Returns a task_id for monitoring progress via get_autoresearch_status.
After completion, use get_autoresearch_result to retrieve the best config found.

Example:
    task_id = run_autoresearch(
        objective="minimize val_bpb on the TinyStories dataset",
        dataset_path="data/train_8192_256.bin",
        metric_name="val_bpb",
        metric_direction="minimize",
        metric_target=0.85,
        max_experiments=50,
        experiment_duration_seconds=300,
        hyperparameter_space={
            "lr": {"type": "log_uniform", "min": 1e-5, "max": 1e-2},
            "depth": {"type": "choice", "values": [4, 6, 8, 10, 12]},
        }
    )
    """
    inputs = {
        "objective": {
            "type": "string",
            "description": "Description of what to optimize, e.g. 'minimize val_bpb on TinyStories'",
            "required": True,
        },
        "dataset_path": {
            "type": "string",
            "description": "Path to training data binary file",
            "required": True,
        },
        "metric_name": {
            "type": "string",
            "description": "Name of metric to optimize (default: val_bpb)",
            "default": "val_bpb",
        },
        "metric_direction": {
            "type": "string",
            "description": "'minimize' or 'maximize' (default: minimize)",
            "enum": ["minimize", "maximize"],
            "default": "minimize",
        },
        "metric_target": {
            "type": "number",
            "description": "Target value for early stopping (optional). "
                          "When reached, the search stops early.",
        },
        "max_experiments": {
            "type": "integer",
            "description": "Maximum number of experiments (default: 50)",
            "default": 50,
        },
        "experiment_duration_seconds": {
            "type": "integer",
            "description": "Duration per individual experiment in seconds (default: 300 = 5 min)",
            "default": 300,
        },
        "max_duration_minutes": {
            "type": "integer",
            "description": "Maximum total runtime in minutes across all experiments (default: 120)",
            "default": 120,
        },
        "hyperparameter_space": {
            "type": "object",
            "description": "Search space definition as dict of param_name -> spec. "
                          "Spec format: {'type': 'log_uniform'|'uniform'|'choice', "
                          "'min': float, 'max': float} or {'type': 'choice', 'values': [...]}. "
                          "Example: {'lr': {'type': 'log_uniform', 'min': 1e-5, 'max': 1e-2}}",
        },
        "base_train_py_path": {
            "type": "string",
            "description": "Path to custom train.py base file (optional, "
                          "falls back to base/train_base.py)",
        },
        "task_id": {
            "type": "string",
            "description": "Custom task ID (optional, auto-generated if not provided). "
                          "Use if you need a predictable ID.",
        },
    }
    output_type = "string"

    def forward(
        self,
        objective: str,
        dataset_path: str,
        metric_name: str = "val_bpb",
        metric_direction: str = "minimize",
        metric_target: Optional[float] = None,
        max_experiments: int = 50,
        experiment_duration_seconds: int = 300,
        max_duration_minutes: int = 120,
        hyperparameter_space: Optional[dict] = None,
        base_train_py_path: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> str:
        """
        Launch the autoresearch loop.

        Args:
            objective: Description of what to optimize.
            dataset_path: Path to training data binary file.
            metric_name: Name of metric to optimize.
            metric_direction: 'minimize' or 'maximize'.
            metric_target: Target value for early stopping (optional).
            max_experiments: Max number of experiments.
            experiment_duration_seconds: Duration per experiment.
            max_duration_minutes: Total time budget across all experiments.
            hyperparameter_space: Search space definition.
            base_train_py_path: Custom base train.py path.
            task_id: Custom task ID (optional).

        Returns:
            JSON string with task_id and launch status.
        """
        if task_id is None:
            task_id = f"task_{uuid.uuid4().hex[:8]}"

        result_task_id = create_autoresearch_task(
            task_id=task_id,
            objective=objective,
            dataset_path=dataset_path,
            metric_name=metric_name,
            metric_direction=metric_direction,
            metric_target=metric_target,
            max_experiments=max_experiments,
            max_duration_minutes=max_duration_minutes,
            experiment_duration_seconds=experiment_duration_seconds,
            hyperparameter_space=hyperparameter_space,
            base_train_py_path=base_train_py_path,
        )

        return json.dumps({
            "task_id": result_task_id,
            "status": "launched",
            "message": (
                f"Autoresearch task {result_task_id} launched. "
                f"Monitor via get_autoresearch_status(task_id='{result_task_id}'). "
                f"Results via get_autoresearch_result(task_id='{result_task_id}')."
            ),
        })


class GetAutoresearchStatusTool(Tool):
    """
    Get the current status of a running autoresearch task.

    Returns progress information including:
    - current experiment index and total
    - best metric value achieved so far
    - best hyperparameters found
    - elapsed time
    - error message if failed

    Call this repeatedly to track progress of a running task.
    """

    name = "get_autoresearch_status"
    description = """
Get the current status of a running autoresearch task.

Returns progress information including:
- current experiment index and total
- best metric value achieved so far
- best hyperparameters found
- elapsed time
- error message if failed

Call this repeatedly to track progress. Status values:
- 'pending': task created but sub-agent not started
- 'running': experiments in progress
- 'completed': all experiments done, result available
- 'failed': task failed with error
- 'budget_exceeded': max_experiments or max_duration reached
    """
    inputs = {
        "task_id": {
            "type": "string",
            "description": "The task_id returned by run_autoresearch",
            "required": True,
        },
    }
    output_type = "string"

    def forward(self, task_id: str) -> str:
        """
        Get current status of an autoresearch task.

        Args:
            task_id: The task_id returned by run_autoresearch.

        Returns:
            JSON string with task status, progress, best_val, etc.
        """
        manager = AutoResearchManager()
        status = manager.get_status(task_id)
        return json.dumps(status, indent=2)


class GetAutoresearchResultTool(Tool):
    """
    Get the final result of a completed autoresearch task.

    Returns the best experiment found, including:
    - best metric value and hyperparameters
    - total experiments run
    - experiment history summary

    Only call this after task status shows 'completed' or 'budget_exceeded'.
    Use get_autoresearch_status to check if results are ready.
    """

    name = "get_autoresearch_result"
    description = """
Get the final result of a completed autoresearch task.

Returns the best experiment found, including:
- best metric value and hyperparameters
- total experiments run
- experiment history summary

Only call after task status shows 'completed' or 'budget_exceeded'.
Use get_autoresearch_status first to check if results are ready.
    """
    inputs = {
        "task_id": {
            "type": "string",
            "description": "The task_id returned by run_autoresearch",
            "required": True,
        },
    }
    output_type = "string"

    def forward(self, task_id: str) -> str:
        """
        Get final result of a completed autoresearch task.

        Args:
            task_id: The task_id returned by run_autoresearch.

        Returns:
            JSON string with best result, or 'not_ready' if not yet available.
        """
        manager = AutoResearchManager()
        result = manager.get_result(task_id)

        if result is None:
            return json.dumps({
                "task_id": task_id,
                "status": "not_ready",
                "message": (
                    "Result not yet available. "
                    "Check again later or call get_autoresearch_status to confirm completion."
                ),
            })

        return json.dumps(result.to_dict(), indent=2)
