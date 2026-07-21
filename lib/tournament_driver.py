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
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

from lib.fdp_common import _is_plain_number, _json_clone
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


def _preflight_missing(
    job: dict[str, Any],
    probe_fn: Callable[..., dict[str, Any]] | None,
) -> list[str]:
    target = job["target"]
    kind = target.get("kind")
    if kind == "synthetic":
        return []
    if kind != "fasttext":
        return [f"unknown target kind {kind!r}"]
    missing: list[str] = []
    for key in ("target_spec", "train_csv", "test_csv"):
        value = target.get(key)
        if not value or not Path(value).expanduser().is_file():
            missing.append(f"target.{key} not found: {value}")
    if probe_fn is None:
        from lib.full_reproduction_harness import probe_fasttext_runtime
        probe_fn = probe_fasttext_runtime
    binary = target.get("fasttext_binary")
    probe = probe_fn(explicit_binary=Path(binary) if binary else None)
    if not probe.get("binary", {}).get("available"):
        missing.append(f"fasttext binary not executable: {binary}")
    return missing


def _default_fasttext_baseline(job: dict[str, Any], phase_a_dir: Path) -> str:
    from lib.full_reproduction_harness import (
        FullReproductionRunConfig,
        run_fasttext_binary_baseline,
    )
    target = job["target"]
    config = FullReproductionRunConfig(
        target_spec_path=Path(target["target_spec"]),
        output_dir=Path(phase_a_dir),
        max_train_seconds=int(target.get("max_train_seconds", 300)),
    )
    result = run_fasttext_binary_baseline(
        config,
        train_csv=Path(target["train_csv"]),
        test_csv=Path(target["test_csv"]),
        fasttext_binary=Path(target["fasttext_binary"]),
    )
    return str(result["baseline_report"])


def _ensure_baseline(
    job: dict[str, Any],
    *,
    baseline_fn: Callable[..., str] | None,
) -> None:
    artifact = Path(job["baseline_artifact"]).expanduser()
    artifact.parent.mkdir(parents=True, exist_ok=True)
    target = job["target"]
    if target["kind"] == "synthetic":
        artifact.write_text(
            json.dumps({"metric": {"value": float(target["baseline_value"])}},
                       sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return
    phase_a_dir = tournament_search.tournament_dir(
        Path(job["runtime_root"]), job["run_id"]
    ) / "phase-a"
    phase_a_dir.mkdir(parents=True, exist_ok=True)
    produce = baseline_fn or _default_fasttext_baseline
    report_path = produce(job, phase_a_dir)
    shutil.copyfile(report_path, artifact)


def _baseline_value_from_artifact(path: Path) -> float:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    metric = payload.get("metric") if isinstance(payload, dict) else None
    candidates = []
    if isinstance(metric, dict):
        candidates.extend([metric.get("p_at_1"), metric.get("value")])
    if isinstance(payload, dict):
        candidates.append(payload.get("value"))
    for candidate in candidates:
        if _is_plain_number(candidate):
            return float(candidate)
    raise DriverJobError(f"baseline artifact has no readable metric: {path}")


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
    if not state["tournament_started"]:
        missing = _preflight_missing(job, probe_fn)
        if missing:
            state["stopped"] = {"stopped": True, "reason": "preflight_failed"}
            state["phase_a"]["status"] = "failed"
            save_driver_state(state, path)
            return _wake_plan("preflight_failed", state, engine_state,
                              reason="preflight_failed", missing=missing)
        artifact = Path(job["baseline_artifact"]).expanduser()
        if not artifact.is_file():
            try:
                _ensure_baseline(job, baseline_fn=baseline_fn)
            except Exception as error:
                phase_a = state["phase_a"]
                phase_a["attempts"] += 1
                phase_a["error"] = str(error)[-500:]
                if phase_a["attempts"] >= MAX_PHASE_A_ATTEMPTS:
                    phase_a["status"] = "failed"
                    state["stopped"] = {"stopped": True,
                                        "reason": "phase_a_failed"}
                    save_driver_state(state, path)
                    return _wake_plan("preflight_failed", state, engine_state,
                                      reason="phase_a_failed")
                phase_a["status"] = "failed_once"
                save_driver_state(state, path)
                return _wake_plan("phase_a_retry", state, engine_state,
                                  reason="phase_a_execution_failed")
            state["phase_a"]["status"] = "completed"
            state["phase_a"]["completed_at"] = now
        elif state["phase_a"]["status"] == "pending":
            state["phase_a"]["status"] = "not_needed"
        save_driver_state(state, path)
    if not state["tournament_started"]:
        artifact = Path(job["baseline_artifact"]).expanduser()
        value = _baseline_value_from_artifact(artifact)
        tournament_search.start_tournament(
            runtime_root=Path(job["runtime_root"]),
            run_id=job["run_id"],
            target_id=job["target_id"],
            config=job["tournament_config"],
            baseline={"value": value, "artifact": str(artifact)},
            target=job["target"],
            now_fn=lambda: now,
        )
        state["tournament_started"] = True
        engine_state = _load_engine_state(job)
    if state["wake_history"]:
        state["wake_history"][-1]["ledger_rounds_at_start"] = (
            engine_state["ledger"]["total_rounds_used"]
        )
    save_driver_state(state, path)
    report = tournament_search.build_tournament_report(engine_state)
    winner = report["winner"]
    best_so_far = {
        "winner": (
            {"arm_id": winner["arm_id"], "best": winner["best"],
             "improved": winner["improved"], "status": winner["status"]}
            if winner else None
        ),
        "total_rounds_used": engine_state["ledger"]["total_rounds_used"],
    }
    started_at = state["wake_history"][-1]["started_at"]
    return _wake_plan(
        "proceed", state, engine_state,
        per_wake_budget={
            "max_rounds": job["driver"]["per_wake_max_rounds"],
            "deadline_at": started_at + job["driver"]["per_wake_max_minutes"] * 60,
        },
        best_so_far=best_so_far,
    )


def _build_notification_payload(
    job: dict[str, Any],
    state: dict[str, Any],
    engine_state: dict[str, Any] | None,
    stop_reason: str | None,
) -> dict[str, Any]:
    winner = None
    rounds_used = 0
    wall_seconds = 0.0
    report_path = None
    if engine_state is not None:
        report = tournament_search.build_tournament_report(engine_state)
        if report["winner"]:
            w = report["winner"]
            winner = {"arm_id": w["arm_id"], "hypothesis": w["hypothesis"],
                      "best": w["best"], "improved": w["improved"],
                      "status": w["status"]}
        rounds_used = engine_state["ledger"]["total_rounds_used"]
        wall_seconds = engine_state["ledger"]["wall_seconds_used"]
        report_path = engine_state.get("report_path")
    return {
        "job_id": job["job_id"],
        "stop_reason": stop_reason,
        "winner": winner,
        "rounds_used": rounds_used,
        "wakeups_used": state["wakeups_used"],
        "wall_seconds_used": wall_seconds,
        "report_path": report_path,
        "runtime_root": job["runtime_root"],
        "run_id": job["run_id"],
    }


def driver_finish(
    *,
    job: dict[str, Any] | str | Path,
    mark_notified: bool = False,
    now_fn: Callable[[], float] = time.time,
) -> dict[str, Any]:
    """Last call of every wake: close the ledger; build/flip the notification."""
    job = load_job(job)
    now = float(now_fn())
    path = driver_state_path(job)
    if not path.exists():
        raise DriverJobError(f"no driver state for job {job['job_id']!r}; run driver_tick first")
    state = load_driver_state(path)
    notification = state["notification"]

    if mark_notified:
        if notification["required"]:
            notification["sent"] = True
        save_driver_state(state, path)
        return {"status": "notified", "wake": None,
                "notification": {k: notification[k]
                                 for k in ("required", "sent", "payload")}}

    engine_state = _load_engine_state(job)
    engine_stopped = bool(engine_state and engine_state["stop"]["stopped"])
    if engine_stopped:
        exit_reason = "engine_stopped"
    elif state["stopped"]["stopped"]:
        exit_reason = state["stopped"]["reason"]
    else:
        exit_reason = "per_wake_budget"
    _close_open_wakes(state, engine_state, exit_reason=exit_reason)
    closed = state["wake_history"][-1] if state["wake_history"] else None

    stop_reason = (
        engine_state["stop"]["reason"] if engine_stopped
        else state["stopped"]["reason"]
    )
    should_notify = (
        job["notify"]["on_stop"]
        and (engine_stopped or state["stopped"]["stopped"])
        and not notification["required"]
    )
    if should_notify:
        if engine_stopped and not state["stopped"]["stopped"]:
            state["stopped"] = {"stopped": True, "reason": stop_reason}
        notification["required"] = True
        notification["payload"] = _build_notification_payload(
            job, state, engine_state, stop_reason,
        )
        notification["built_at"] = now
    save_driver_state(state, path)
    return {"status": "closed", "wake": closed,
            "notification": {k: notification[k]
                             for k in ("required", "sent", "payload")}}
