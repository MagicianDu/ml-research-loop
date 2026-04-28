"""
ExperimentStore — atomic read/write for experiments.json.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from lib.task_protocol import now_iso, SNAPSHOTS_DIR


@dataclass
class ExperimentStore:
    """
    Manages experiment records for a single task.
    File format: workdir/experiments.json
    """
    task_id: str
    workdir: Path
    direction: str = "minimize"  # "minimize" or "maximize"
    best_val: Optional[float] = None
    best_params: Optional[dict] = None
    best_experiment_id: Optional[str] = None
    experiments: list[dict] = field(default_factory=list)

    _file_path: Path = field(init=False, repr=False)

    def __post_init__(self):
        self._file_path = self.workdir / "experiments.json"

    def load(self) -> "ExperimentStore":
        """Load existing records from file."""
        if not self._file_path.exists():
            return self
        try:
            data = json.loads(self._file_path.read_text(encoding="utf-8"))
            self.best_val = data.get("best_val")
            self.best_params = data.get("best_params")
            self.best_experiment_id = data.get("best_experiment_id")
            self.experiments = data.get("experiments", [])
        except (json.JSONDecodeError, KeyError):
            pass
        return self

    def save(self) -> None:
        """Atomically write experiments.json using temp file + rename."""
        data = {
            "task_id": self.task_id,
            "best_val": self.best_val,
            "best_params": self.best_params,
            "best_experiment_id": self.best_experiment_id,
            "experiments": self.experiments,
        }
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=self.workdir,
            prefix=".experiments_tmp_",
            suffix=".json",
        )
        try:
            with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp_path, self._file_path)
        except Exception:
            if os.path.exists(tmp_path):
                os.unlink(tmp_path)
            raise

    def add_experiment(
        self,
        experiment_id: str,
        params: dict,
        metrics: dict,
        accepted: bool,
        duration_seconds: Optional[float] = None,
        error: Optional[str] = None,
        **extra,
    ) -> bool:
        """
        Add experiment record. Update best if accepted and improved.
        Returns True if best was updated.
        """
        snapshot_dir = SNAPSHOTS_DIR / self.task_id / experiment_id

        record = {
            "experiment_id": experiment_id,
            "params": params,
            "metrics": metrics,
            "accepted": accepted,
            "timestamp": now_iso(),
            "duration_seconds": duration_seconds,
            "snapshot_path": str(snapshot_dir) if snapshot_dir.exists() else None,
            "error": error,
            **extra,
        }
        self.experiments.append(record)

        # Determine if this updates best (respects direction)
        val = metrics.get("val", metrics.get("val_bpb", None))
        updated = False

        if val is not None and accepted:
            if self.best_val is None:
                updated = True
            elif self.direction == "minimize":
                updated = val < self.best_val
            else:  # maximize
                updated = val > self.best_val

            if updated:
                self.best_val = val
                self.best_params = params
                self.best_experiment_id = experiment_id

        self.save()
        return updated

    def summary(self) -> dict:
        """Return experiment summary statistics."""
        return {
            "total": len(self.experiments),
            "accepted": sum(1 for e in self.experiments if e.get("accepted")),
            "rejected": sum(1 for e in self.experiments if not e.get("accepted")),
            "failed": sum(1 for e in self.experiments if e.get("error")),
            "best_val": self.best_val,
            "best_params": self.best_params,
            "best_experiment_id": self.best_experiment_id,
        }

    def to_dict(self) -> dict:
        """Return full store state as a dict (for checkpoint serialization)."""
        return {
            "task_id": self.task_id,
            "best_val": self.best_val,
            "best_params": self.best_params,
            "best_experiment_id": self.best_experiment_id,
            "experiments": self.experiments,
        }
