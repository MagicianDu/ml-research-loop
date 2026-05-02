# ml_intern/tools/run_autoresearch.py
# smolagents Tool classes for ml-intern × autoresearch integration

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Optional

from smolagents import Tool
from lib.fusion_service import (
    build_research_context,
    propose_hypotheses,
    read_paper_context,
    review_research_result,
)
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
            "nullable": True,
        },
        "metric_direction": {
            "type": "string",
            "description": "'minimize' or 'maximize' (default: minimize)",
            "enum": ["minimize", "maximize"],
            "default": "minimize",
            "nullable": True,
        },
        "metric_target": {
            "type": "number",
            "description": "Target value for early stopping (optional). "
                          "When reached, the search stops early.",
            "nullable": True,
        },
        "max_experiments": {
            "type": "integer",
            "description": "Maximum number of experiments (default: 50)",
            "default": 50,
            "nullable": True,
        },
        "experiment_duration_seconds": {
            "type": "integer",
            "description": "Duration per individual experiment in seconds (default: 300 = 5 min)",
            "default": 300,
            "nullable": True,
        },
        "max_duration_minutes": {
            "type": "integer",
            "description": "Maximum total runtime in minutes across all experiments (default: 120)",
            "default": 120,
            "nullable": True,
        },
        "hyperparameter_space": {
            "type": "object",
            "description": "Search space definition as dict of param_name -> spec. "
                          "Spec format: {'type': 'log_uniform'|'uniform'|'choice', "
                          "'min': float, 'max': float} or {'type': 'choice', 'values': [...]}. "
                          "Example: {'lr': {'type': 'log_uniform', 'min': 1e-5, 'max': 1e-2}}",
            "nullable": True,
        },
        "focus_areas": {
            "type": "array",
            "description": "Optional research focus areas to inject into program.md.",
            "nullable": True,
        },
        "forbidden_changes": {
            "type": "array",
            "description": "Optional forbidden changes to inject into program.md.",
            "nullable": True,
        },
        "hints": {
            "type": "array",
            "description": "Optional experiment hints to inject into program.md.",
            "nullable": True,
        },
        "base_train_py_path": {
            "type": "string",
            "description": "Path to custom train.py base file (optional, "
                          "falls back to base/train_base.py)",
            "nullable": True,
        },
        "task_id": {
            "type": "string",
            "description": "Custom task ID (optional, auto-generated if not provided). "
                          "Use if you need a predictable ID.",
            "nullable": True,
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
        focus_areas: Optional[list[str]] = None,
        forbidden_changes: Optional[list[str]] = None,
        hints: Optional[list[str]] = None,
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
            focus_areas: Optional research focus areas for program.md.
            forbidden_changes: Optional forbidden changes for program.md.
            hints: Optional experiment hints for program.md.
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
            focus_areas=focus_areas,
            forbidden_changes=forbidden_changes,
            hints=hints,
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

        return json.dumps(review_research_result(result.to_dict()), indent=2)


class ResearchTaskTool(Tool):
    """Prepare a structured research task for hypothesis generation."""

    name = "research_task"
    description = (
        "Start the ml-intern research-planning step for an ML objective. "
        "Returns query_plan, findings, source_rankings, and hypotheses."
    )
    inputs = {
        "objective": {
            "type": "string",
            "description": "Research objective to investigate.",
            "required": True,
        },
        "query": {
            "type": "string",
            "description": "Optional search query. Defaults to objective.",
            "nullable": True,
        },
        "paper_limit": {
            "type": "integer",
            "description": "Maximum arXiv paper sources to collect.",
            "nullable": True,
        },
        "dataset_limit": {
            "type": "integer",
            "description": "Maximum Hugging Face dataset sources to collect.",
            "nullable": True,
        },
        "github_limit": {
            "type": "integer",
            "description": "Maximum GitHub code sources to collect.",
            "nullable": True,
        },
        "include_papers": {
            "type": "boolean",
            "description": "Whether to include arXiv paper search.",
            "nullable": True,
        },
        "include_hf_datasets": {
            "type": "boolean",
            "description": "Whether to include Hugging Face dataset search.",
            "nullable": True,
        },
        "include_github_code": {
            "type": "boolean",
            "description": "Whether to include GitHub code search.",
            "nullable": True,
        },
        "query_fanout": {
            "type": "boolean",
            "description": "Whether to try query_plan variants when primary search returns too few sources.",
            "nullable": True,
        },
    }
    output_type = "string"

    def forward(
        self,
        objective: str,
        query: Optional[str] = None,
        paper_limit: Optional[int] = None,
        dataset_limit: Optional[int] = None,
        github_limit: Optional[int] = None,
        include_papers: Optional[bool] = None,
        include_hf_datasets: Optional[bool] = None,
        include_github_code: Optional[bool] = None,
        query_fanout: Optional[bool] = None,
    ) -> str:
        return json.dumps(
            build_research_context(
                objective=objective,
                query=query,
                paper_limit=paper_limit or 3,
                dataset_limit=dataset_limit or 3,
                github_limit=github_limit or 0,
                include_papers=True if include_papers is None else include_papers,
                include_hf_datasets=True if include_hf_datasets is None else include_hf_datasets,
                include_github_code=bool(include_github_code),
                query_fanout=True if query_fanout is None else query_fanout,
            ),
            indent=2,
        )


class ReadPaperTool(Tool):
    """Read one paper and turn it into a research brief fragment."""

    name = "read_paper"
    description = (
        "Read one paper by arXiv ID or URL and return source, evidence snippets, "
        "findings, and hypotheses for autoresearch validation."
    )
    inputs = {
        "identifier": {
            "type": "string",
            "description": "arXiv ID or arXiv URL.",
            "required": True,
        },
        "objective": {
            "type": "string",
            "description": "Optional experiment objective used to frame findings.",
            "nullable": True,
        },
    }
    output_type = "string"

    def forward(self, identifier: str, objective: Optional[str] = None) -> str:
        return json.dumps(
            read_paper_context(identifier=identifier, objective=objective),
            indent=2,
        )


class ProposeHypothesesTool(Tool):
    """Convert research sources into autoresearch-ready hypotheses."""

    name = "propose_hypotheses"
    description = "Generate rank-aware research-backed hypotheses for autoresearch validation."
    inputs = {
        "objective": {
            "type": "string",
            "description": "Objective that hypotheses should improve.",
            "required": True,
        },
        "sources": {
            "type": "array",
            "description": "Research sources from papers, HF docs/datasets, or GitHub.",
            "nullable": True,
        },
    }
    output_type = "string"

    def forward(self, objective: str, sources: Optional[list[dict]] = None) -> str:
        return json.dumps(propose_hypotheses(objective, sources or []), indent=2)


class RunHypothesisExperimentTool(Tool):
    """Launch an autoresearch task for a hypothesis-backed experiment."""

    name = "run_hypothesis_experiment"
    description = "Run an autoresearch experiment for a structured hypothesis."
    inputs = RunAutoresearchTool.inputs
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
        focus_areas: Optional[list[str]] = None,
        forbidden_changes: Optional[list[str]] = None,
        hints: Optional[list[str]] = None,
        base_train_py_path: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> str:
        return RunAutoresearchTool().forward(
            objective=objective,
            dataset_path=dataset_path,
            metric_name=metric_name,
            metric_direction=metric_direction,
            metric_target=metric_target,
            max_experiments=max_experiments,
            experiment_duration_seconds=experiment_duration_seconds,
            max_duration_minutes=max_duration_minutes,
            hyperparameter_space=hyperparameter_space,
            focus_areas=focus_areas,
            forbidden_changes=forbidden_changes,
            hints=hints,
            base_train_py_path=base_train_py_path,
            task_id=task_id,
        )


class ReviewResearchResultsTool(Tool):
    """Review final autoresearch results for a research-backed task."""

    name = "review_research_results"
    description = (
        "Read and review final results for a completed hypothesis-backed autoresearch task, "
        "including recommended next search space and next_task_patch."
    )
    inputs = GetAutoresearchResultTool.inputs
    output_type = "string"

    def forward(self, task_id: str) -> str:
        return GetAutoresearchResultTool().forward(task_id)
