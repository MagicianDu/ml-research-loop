"""
Task Protocol — JSON schema definitions and file I/O for ml-research-loop.
"""

from __future__ import annotations

import json
import os
import shutil
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from lib.exceptions import (
    TaskNotFoundError,
    TaskLockError,
    TaskProtocolError,
    ResultNotReadyError,
)


# ─── Constants ────────────────────────────────────────────────────────────────

def resolve_workspace_root() -> Path:
    """Resolve the workspace root for runtime files."""
    configured = os.environ.get("ML_RESEARCH_LOOP_ROOT")
    if configured:
        return Path(configured).expanduser().resolve()

    source_root = Path(__file__).resolve().parents[1]
    if (source_root / "pyproject.toml").exists():
        return source_root

    return Path.cwd().resolve()


WORKSPACE_ROOT = resolve_workspace_root()

TASKS_DIR = WORKSPACE_ROOT / "tasks"
RESULTS_DIR = WORKSPACE_ROOT / "results"
LOGS_DIR = WORKSPACE_ROOT / "logs"
SNAPSHOTS_DIR = WORKSPACE_ROOT / "snapshots"
WORKDIR_DIR = WORKSPACE_ROOT / "workdir"

LOCK_TIMEOUT_SECONDS = 10
LOCK_POLL_INTERVAL = 0.5


# ─── Enums ───────────────────────────────────────────────────────────────────

class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    BUDGET_EXCEEDED = "budget_exceeded"
    CANCELLED = "cancelled"


class MetricDirection(str, Enum):
    MINIMIZE = "minimize"
    MAXIMIZE = "maximize"


# ─── Dataclasses ──────────────────────────────────────────────────────────────

@dataclass
class DatasetConfig:
    name: str
    path: str
    type: str = "binary"
    vocab_size: int = 8192
    max_seq_len: int = 256
    train_split: int = 0
    val_split: int = 0


@dataclass
class MetricConfig:
    name: str
    direction: MetricDirection
    threshold: Optional[float] = None


@dataclass
class HyperparamSpace:
    """Hyperparameter search space definition."""
    type: str  # "log_uniform" | "uniform" | "choice" | "q_uniform" | "q_log_uniform"
    min: Optional[float] = None
    max: Optional[float] = None
    values: Optional[list] = None
    q: Optional[float] = None


@dataclass
class BudgetConfig:
    max_experiments: int = 50
    max_duration_minutes: int = 120
    max_cost_usd: float = 10.0
    experiment_duration_seconds: int = 300  # 5 minutes


@dataclass
class BaseCodeConfig:
    train_py_url: str
    prepare_py_url: str


@dataclass
class NotificationConfig:
    on_complete: str = "event://autoresearch_experiment_complete"
    on_fail: str = "event://autoresearch_experiment_failed"
    on_budget_exceeded: str = "event://autoresearch_budget_exceeded"


@dataclass
class ProgramMdOverrides:
    focus_areas: list[str] = field(default_factory=list)
    forbidden_changes: list[str] = field(default_factory=list)
    hints: list[str] = field(default_factory=list)


@dataclass
class TaskDefinition:
    task_id: str
    objective: str
    dataset: DatasetConfig
    metric: MetricConfig
    hyperparameter_space: dict[str, HyperparamSpace]
    budget: BudgetConfig
    base_code: BaseCodeConfig
    notification: NotificationConfig = field(default_factory=NotificationConfig)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    created_by: str = "ml-intern-main"
    program_md_overrides: ProgramMdOverrides = field(default_factory=ProgramMdOverrides)
    research_context: Optional[dict] = None
    hypotheses: list[dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> "TaskDefinition":
        return cls(
            task_id=data["task_id"],
            objective=data["objective"],
            dataset=DatasetConfig(**data["dataset"]),
            metric=MetricConfig(
                name=data["metric"]["name"],
                direction=MetricDirection(data["metric"]["direction"]),
                threshold=data["metric"].get("threshold"),
            ),
            hyperparameter_space={
                k: HyperparamSpace(**v) for k, v in data.get("hyperparameter_space", {}).items()
            },
            budget=BudgetConfig(**data["budget"]),
            base_code=BaseCodeConfig(**data["base_code"]),
            notification=NotificationConfig(**data.get("notification", {})),
            created_at=data.get("created_at", datetime.now(timezone.utc).isoformat()),
            created_by=data.get("created_by", "ml-intern-main"),
            research_context=data.get("research_context"),
            hypotheses=data.get("hypotheses", []),
        )

    def to_dict(self) -> dict:
        payload = {
            "task_id": self.task_id,
            "objective": self.objective,
            "dataset": asdict(self.dataset),
            "metric": {
                "name": self.metric.name,
                "direction": self.metric.direction.value,
                "threshold": self.metric.threshold,
            },
            "hyperparameter_space": {
                k: asdict(v) for k, v in self.hyperparameter_space.items()
            },
            "budget": asdict(self.budget),
            "base_code": asdict(self.base_code),
            "notification": asdict(self.notification),
            "created_at": self.created_at,
            "created_by": self.created_by,
        }
        if self.research_context:
            payload["research_context"] = self.research_context
        if self.hypotheses:
            payload["hypotheses"] = self.hypotheses
        return payload


@dataclass
class TaskResult:
    task_id: str
    status: TaskStatus
    best_result: Optional[dict] = None
    experiments: list[dict] = field(default_factory=list)
    summary: Optional[dict] = None
    research_context: Optional[dict] = None
    hypotheses: list[dict] = field(default_factory=list)
    finished_at: Optional[str] = None
    error: Optional[str] = None

    def to_dict(self) -> dict:
        data = {
            "task_id": self.task_id,
            "status": self.status.value if isinstance(self.status, TaskStatus) else self.status,
        }
        if self.best_result:
            data["best_result"] = self.best_result
        if self.experiments:
            data["experiments"] = self.experiments
        if self.summary:
            data["summary"] = self.summary
        if self.research_context:
            data["research_context"] = self.research_context
        if self.hypotheses:
            data["hypotheses"] = self.hypotheses
        if self.finished_at:
            data["finished_at"] = self.finished_at
        if self.error:
            data["error"] = self.error
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "TaskResult":
        data = dict(data)
        data["status"] = TaskStatus(data["status"])
        return cls(**data)


# ─── File Operations ─────────────────────────────────────────────────────────

def ensure_dirs() -> None:
    """Ensure all required directories exist."""
    for d in [TASKS_DIR, RESULTS_DIR, LOGS_DIR, SNAPSHOTS_DIR, WORKDIR_DIR]:
        d.mkdir(parents=True, exist_ok=True)


def write_task(task: TaskDefinition, overwrite: bool = False) -> Path:
    """Write TaskDefinition to tasks/<task_id>.json."""
    ensure_dirs()
    task_file = TASKS_DIR / f"{task.task_id}.json"

    if task_file.exists() and not overwrite:
        raise TaskLockError(f"Task file already exists: {task_file}")

    text = json.dumps(task.to_dict(), indent=2, ensure_ascii=False)
    task_file.write_text(text, encoding="utf-8")
    return task_file


def read_task(task_id: str) -> TaskDefinition:
    """Read task definition from tasks/<task_id>.json."""
    task_file = TASKS_DIR / f"{task_id}.json"
    if not task_file.exists():
        raise TaskNotFoundError(f"Task not found: {task_id}")

    try:
        data = json.loads(task_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise TaskProtocolError(f"Invalid JSON in {task_file}: {e}") from e

    return TaskDefinition.from_dict(data)


def read_result(task_id: str) -> TaskResult:
    """Read task result. Raises ResultNotReadyError if not available."""
    result_file = RESULTS_DIR / f"{task_id}.json"
    if not result_file.exists():
        raise ResultNotReadyError(f"Result not ready for task: {task_id}")

    try:
        data = json.loads(result_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        raise TaskProtocolError(f"Invalid JSON in {result_file}: {e}") from e

    return TaskResult.from_dict(data)


def write_result(result: TaskResult) -> None:
    """Write task result to results/<task_id>.json."""
    ensure_dirs()
    result_file = RESULTS_DIR / f"{result.task_id}.json"
    text = json.dumps(result.to_dict(), indent=2, ensure_ascii=False)
    result_file.write_text(text, encoding="utf-8")


def acquire_task_lock(task_id: str, timeout: float = LOCK_TIMEOUT_SECONDS) -> Path:
    """Acquire exclusive lock for a task. Returns lock file path."""
    lock_file = TASKS_DIR / f"{task_id}.lock"
    start = time.monotonic()

    while lock_file.exists():
        if time.monotonic() - start > timeout:
            raise TaskLockError(f"Lock timeout for task {task_id} after {timeout}s")
        time.sleep(LOCK_POLL_INTERVAL)

    lock_file.write_text(
        f"{os.getpid()}\n{datetime.now(timezone.utc).isoformat()}",
        encoding="utf-8"
    )
    return lock_file


def release_task_lock(task_id: str) -> None:
    """Release task lock."""
    lock_file = TASKS_DIR / f"{task_id}.lock"
    if lock_file.exists():
        lock_file.unlink()


def write_progress(task_id: str, progress: dict) -> None:
    """Write real-time progress to results/<task_id>-progress.json."""
    ensure_dirs()
    progress_file = RESULTS_DIR / f"{task_id}-progress.json"
    text = json.dumps(progress, indent=2, ensure_ascii=False)
    progress_file.write_text(text, encoding="utf-8")


def read_progress(task_id: str) -> dict:
    """Read progress file. Returns empty dict if not available."""
    progress_file = RESULTS_DIR / f"{task_id}-progress.json"
    if not progress_file.exists():
        return {}
    return json.loads(progress_file.read_text(encoding="utf-8"))


def snapshot_code(task_id: str, experiment_id: str, workdir: Path) -> Path:
    """Snapshot train.py and program.md to snapshots/<task_id>/<experiment_id>/."""
    ensure_dirs()
    snapshot_dir = SNAPSHOTS_DIR / task_id / experiment_id
    snapshot_dir.mkdir(parents=True, exist_ok=True)

    for fname in ["train.py", "program.md"]:
        src = workdir / fname
        if src.exists():
            shutil.copy2(src, snapshot_dir / fname)

    return snapshot_dir


def now_iso() -> str:
    """Return current UTC time as ISO format string."""
    return datetime.now(timezone.utc).isoformat()
