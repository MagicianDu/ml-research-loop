"""Unattended tournament driver (sub-project 2).

Deterministic layer between a cron-woken fresh LLM session and the
tournament engine: wakeup accounting with a hard cap, preflight and
Phase A baseline production, auto-start, per-wake budgets, ledger-diff
wake accounting, and build-once at-least-once notification. The LLM's
touchpoints stay exactly the engine's two proposal points.

Spec: docs/superpowers/specs/2026-07-15-unattended-orchestration-design.md
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from lib.fdp_common import _json_clone
from lib import tournament_search

DRIVER_SCHEMA_VERSION = "2026-07-15.tournament-driver.v1"
MAX_PHASE_A_ATTEMPTS = 2
DEFAULT_MAX_WAKEUPS = 100
DEFAULT_PER_WAKE_MAX_ROUNDS = 3
DEFAULT_PER_WAKE_MAX_MINUTES = 20

_REQUIRED_JOB_KEYS = (
    "job_id", "runtime_root", "run_id", "target_id",
    "target", "tournament_config", "baseline_artifact",
)
_DRIVER_INT_DEFAULTS = {
    "max_wakeups": DEFAULT_MAX_WAKEUPS,
    "per_wake_max_rounds": DEFAULT_PER_WAKE_MAX_ROUNDS,
    "per_wake_max_minutes": DEFAULT_PER_WAKE_MAX_MINUTES,
}


class DriverJobError(ValueError):
    """The job payload/file is missing, unreadable, or invalid."""


def load_job(job: dict[str, Any] | str | Path) -> dict[str, Any]:
    """Load, validate, and default-normalize a job; returns a deep copy."""
    if isinstance(job, (str, Path)):
        path = Path(job).expanduser()
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as error:
            raise DriverJobError(f"job file not found: {path}") from error
        except json.JSONDecodeError as error:
            raise DriverJobError(f"job file is not valid JSON: {path}: {error}") from error
    elif isinstance(job, dict):
        payload = job
    else:
        raise DriverJobError("job must be an object or a path to a JSON file")
    if not isinstance(payload, dict):
        raise DriverJobError("job must be a JSON object")
    normalized = _json_clone(payload)
    for key in _REQUIRED_JOB_KEYS:
        if not normalized.get(key):
            raise DriverJobError(f"job.{key} is required")
    driver = normalized.get("driver") or {}
    if not isinstance(driver, dict):
        raise DriverJobError("job.driver must be an object")
    for key, default in _DRIVER_INT_DEFAULTS.items():
        value = driver.get(key, default)
        if not isinstance(value, int) or isinstance(value, bool) or value < 1:
            raise DriverJobError(f"job.driver.{key} must be an integer >= 1")
        driver[key] = value
    normalized["driver"] = driver
    notify = normalized.get("notify") or {}
    if not isinstance(notify, dict):
        raise DriverJobError("job.notify must be an object")
    notify["on_stop"] = bool(notify.get("on_stop", True))
    normalized["notify"] = notify
    return normalized


def driver_state_path(job: dict[str, Any]) -> Path:
    return tournament_search.tournament_dir(
        Path(job["runtime_root"]), job["run_id"]
    ) / "driver-state.json"


def save_driver_state(state: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=path.parent, prefix=".driver_state_tmp_", suffix=".json",
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, ensure_ascii=False, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


def load_driver_state(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def init_driver_state(job: dict[str, Any], *, now: float) -> dict[str, Any]:
    return {
        "schema_version": DRIVER_SCHEMA_VERSION,
        "job_id": job["job_id"],
        "created_at": float(now),
        "wakeups_used": 0,
        "max_wakeups": job["driver"]["max_wakeups"],
        "phase_a": {"status": "pending", "attempts": 0, "error": None,
                    "completed_at": None},
        "tournament_started": False,
        "wake_history": [],
        "notification": {"required": False, "sent": False, "payload": None,
                         "built_at": None},
        "stopped": {"stopped": False, "reason": None},
    }
