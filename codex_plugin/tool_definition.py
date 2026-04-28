# codex-plugin/tool_definition.py
"""
Tool interface definitions for ml-research-loop Codex plugin.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class MLExperimentConfig:
    task_id: str
    objective: str
    dataset: dict  # {"name": "...", "path": "..."}
    metric: str
    hyperparameter_space: Optional[dict] = None
    max_experiments: int = 50
    experiment_duration_seconds: int = 300


@dataclass
class MLExperimentStatus:
    task_id: str
    status: str  # "pending" | "running" | "completed" | "failed"
    experiment_index: int
    max_experiments: int
    best_val: Optional[float]
    best_params: Optional[dict]
    progress_pct: float


@dataclass
class MLExperimentResult:
    task_id: str
    status: str
    best_val: float
    best_params: dict
    total_experiments: int
    total_duration_minutes: float
    improvements: list[dict] = field(default_factory=list)
