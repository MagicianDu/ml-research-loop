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
import time
from pathlib import Path
from typing import Any, Callable

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


def _load_engine_state(job: dict[str, Any]) -> dict[str, Any] | None:
    path = tournament_search.state_path(Path(job["runtime_root"]), job["run_id"])
    if not path.exists():
        return None
    return tournament_search.load_tournament_state(path)


def _close_open_wakes(
    state: dict[str, Any],
    engine_state: dict[str, Any] | None,
    *,
    exit_reason: str,
) -> None:
    """Close any wake entry a dead session left open; rounds via ledger diff."""
    for entry in state["wake_history"]:
        if entry["closed"]:
            continue
        start = entry.get("ledger_rounds_at_start")
        if engine_state is not None and start is not None:
            entry["rounds_executed"] = (
                engine_state["ledger"]["total_rounds_used"] - start
            )
        else:
            entry["rounds_executed"] = 0
        entry["closed"] = True
        entry["exit_reason"] = exit_reason


def _tournament_summary(engine_state: dict[str, Any] | None) -> dict[str, Any]:
    if engine_state is None:
        return {"started": False, "stopped": False, "stop_reason": None}
    return {
        "started": True,
        "stopped": engine_state["stop"]["stopped"],
        "stop_reason": engine_state["stop"]["reason"],
    }


def _wake_plan(
    action: str,
    state: dict[str, Any],
    engine_state: dict[str, Any] | None,
    *,
    reason: str | None = None,
    **extra: Any,
) -> dict[str, Any]:
    plan: dict[str, Any] = {
        "action": action,
        "reason": reason,
        "wakeup": {"index": state["wakeups_used"],
                   "max_wakeups": state["max_wakeups"]},
        "pending_action": (
            engine_state.get("pending_action") if engine_state else None
        ),
        "tournament": _tournament_summary(engine_state),
    }
    plan.update(extra)
    return plan


def driver_tick(
    *,
    job: dict[str, Any] | str | Path,
    now_fn: Callable[[], float] = time.time,
    baseline_fn: Callable[..., str] | None = None,
    probe_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """First call of every wake: burn the wakeup, enforce budgets, prepare."""
    job = load_job(job)
    now = float(now_fn())
    path = driver_state_path(job)
    state = load_driver_state(path) if path.exists() else init_driver_state(job, now=now)
    engine_state = _load_engine_state(job)

    _close_open_wakes(state, engine_state, exit_reason="interrupted")
    state["wakeups_used"] += 1
    state["wake_history"].append({
        "wakeup": state["wakeups_used"],
        "started_at": now,
        "ledger_rounds_at_start": (
            engine_state["ledger"]["total_rounds_used"] if engine_state else None
        ),
        "rounds_executed": None,
        "closed": False,
        "exit_reason": None,
    })
    save_driver_state(state, path)  # burn-on-entry: persisted before any check

    if state["wakeups_used"] > state["max_wakeups"] and not state["stopped"]["stopped"]:
        state["stopped"] = {"stopped": True, "reason": "max_wakeups"}
        save_driver_state(state, path)
        return _wake_plan("stop_budget_exhausted", state, engine_state,
                          reason="max_wakeups")
    if state["stopped"]["stopped"]:
        notification = state["notification"]
        if notification["required"] and not notification["sent"]:
            return _wake_plan("finalize", state, engine_state,
                              reason=state["stopped"]["reason"])
        return _wake_plan("quiescent", state, engine_state,
                          reason=state["stopped"]["reason"])
    if engine_state is not None and engine_state["stop"]["stopped"]:
        return _wake_plan("finalize", state, engine_state,
                          reason=engine_state["stop"]["reason"])
    return _prepare_and_proceed(
        job, state, engine_state, path,
        now=now, baseline_fn=baseline_fn, probe_fn=probe_fn,
    )


def _prepare_and_proceed(
    job: dict[str, Any],
    state: dict[str, Any],
    engine_state: dict[str, Any] | None,
    path: Path,
    *,
    now: float,
    baseline_fn: Callable[..., str] | None,
    probe_fn: Callable[..., dict[str, Any]] | None,
) -> dict[str, Any]:
    raise NotImplementedError("implemented in the preflight/Phase A task")
