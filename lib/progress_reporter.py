"""
ProgressReporter — writes real-time progress to results/<task_id>-progress.json.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Optional

from lib.task_protocol import RESULTS_DIR


@dataclass
class ProgressReport:
    task_id: str
    status: str  # "running" | "completed" | "failed"
    experiment_index: int
    max_experiments: int
    best_val: Optional[float] = None
    best_params: Optional[dict] = None
    best_experiment_id: Optional[str] = None
    last_accepted: bool = False
    last_val: Optional[float] = None
    progress_pct: float = 0.0
    elapsed_minutes: Optional[float] = None
    error: Optional[str] = None
    doom_loop_warning: bool = False
    stuck_streak: int = 0  # 连续失败的实验数
    recent_experiments: list = field(default_factory=list)  # 最近实验ID列表
    estimated_time_remaining_minutes: Optional[float] = None


class ProgressReporter:
    """Writes experiment progress to shared progress file for ml-intern polling."""

    DOOM_LOOP_THRESHOLD = 5  # 连续失败次数阈值

    def __init__(self, task_id: str):
        self.task_id = task_id
        self._progress_file = RESULTS_DIR / f"{task_id}-progress.json"
        self._current_index = 0
        self._max_experiments = 1
        self._recent_experiments: list[tuple[str, bool]] = []  # (experiment_id, accepted)
        self._stuck_streak = 0

    def init(self, max_experiments: int) -> None:
        """Initialize progress file."""
        self._max_experiments = max_experiments
        self._recent_experiments = []
        self._stuck_streak = 0
        self._write(ProgressReport(
            task_id=self.task_id,
            status="running",
            experiment_index=0,
            max_experiments=max_experiments,
            progress_pct=0.0,
        ))

    def report(
        self,
        experiment_index: int,
        best_val: Optional[float],
        best_params: Optional[dict],
        best_experiment_id: Optional[str],
        last_accepted: bool,
        last_val: Optional[float],
        elapsed_minutes: Optional[float] = None,
        experiment_id: Optional[str] = None,
    ) -> None:
        """Report current experiment progress."""
        self._current_index = experiment_index
        pct = round(experiment_index / self._max_experiments * 100, 1) if self._max_experiments else 0.0

        # Doom loop detection
        if experiment_id is not None:
            self._recent_experiments.append((experiment_id, last_accepted))
            if len(self._recent_experiments) > self.DOOM_LOOP_THRESHOLD:
                self._recent_experiments.pop(0)

        if not last_accepted:
            self._stuck_streak += 1
        else:
            self._stuck_streak = 0

        doom_loop_warning = (
            len(self._recent_experiments) >= self.DOOM_LOOP_THRESHOLD
            and all(not accepted for _, accepted in self._recent_experiments)
        )

        recent_exp_ids = [eid for eid, _ in self._recent_experiments]

        # Estimated time remaining
        estimated_time_remaining = None
        if elapsed_minutes is not None and experiment_index > 0:
            avg_time_per_exp = elapsed_minutes / experiment_index
            remaining = self._max_experiments - experiment_index
            estimated_time_remaining = round(avg_time_per_exp * remaining, 1)

        self._write(ProgressReport(
            task_id=self.task_id,
            status="running",
            experiment_index=experiment_index,
            max_experiments=self._max_experiments,
            best_val=best_val,
            best_params=best_params,
            best_experiment_id=best_experiment_id,
            last_accepted=last_accepted,
            last_val=last_val,
            progress_pct=pct,
            elapsed_minutes=elapsed_minutes,
            doom_loop_warning=doom_loop_warning,
            stuck_streak=self._stuck_streak,
            recent_experiments=recent_exp_ids,
            estimated_time_remaining_minutes=estimated_time_remaining,
        ))

    def complete(self, best_val: Optional[float], best_params: Optional[dict]) -> None:
        """Mark task as completed."""
        self._write(ProgressReport(
            task_id=self.task_id,
            status="completed",
            experiment_index=self._current_index,
            max_experiments=self._max_experiments,
            best_val=best_val,
            best_params=best_params,
            progress_pct=100.0,
        ))

    def fail(self, error: str) -> None:
        """Mark task as failed."""
        self._write(ProgressReport(
            task_id=self.task_id,
            status="failed",
            experiment_index=self._current_index,
            max_experiments=self._max_experiments,
            error=error,
        ))

    def _write(self, report: ProgressReport) -> None:
        self._progress_file.parent.mkdir(parents=True, exist_ok=True)
        self._progress_file.write_text(
            json.dumps(asdict(report), indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
