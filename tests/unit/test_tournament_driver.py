from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib import tournament_driver as td
from lib import tournament_search as ts


def _job_dict(tmp_path: Path, **overrides) -> dict:
    job = {
        "job_id": "job-1",
        "runtime_root": str(tmp_path / "rt"),
        "run_id": "run-1",
        "target_id": "synthetic-demo",
        "target": {"kind": "synthetic", "baseline_value": 0.9,
                   "weights": {"a": 0.01, "b": 0.001, "c": -0.01}},
        "tournament_config": {
            "k": 3, "initial_rounds_per_arm": 1, "halving": 2,
            "epsilon": 0.001, "metric": "score", "direction": "maximize",
            "budgets": {"max_total_rounds": 12, "max_wall_seconds": 86400,
                        "target_value": 0.92},
        },
        "baseline_artifact": str(tmp_path / "rt" / "baseline.json"),
        "driver": {"max_wakeups": 5, "per_wake_max_rounds": 3,
                   "per_wake_max_minutes": 20},
        "notify": {"on_stop": True},
    }
    job.update(overrides)
    return job


def _write_job(tmp_path: Path, job: dict) -> Path:
    path = tmp_path / "job.json"
    path.write_text(json.dumps(job), encoding="utf-8")
    return path


def test_load_job_accepts_dict_and_file_and_normalizes_defaults(tmp_path):
    raw = _job_dict(tmp_path)
    del raw["driver"]
    del raw["notify"]
    loaded = td.load_job(raw)
    assert loaded["driver"] == {"max_wakeups": 100, "per_wake_max_rounds": 3,
                                "per_wake_max_minutes": 20}
    assert loaded["notify"] == {"on_stop": True}
    assert raw.get("driver") is None  # input not mutated
    from_file = td.load_job(_write_job(tmp_path, _job_dict(tmp_path)))
    assert from_file["driver"]["max_wakeups"] == 5


@pytest.mark.parametrize("mutate, match", [
    (lambda j: j.pop("job_id"), "job.job_id"),
    (lambda j: j.pop("runtime_root"), "job.runtime_root"),
    (lambda j: j.pop("target"), "job.target"),
    (lambda j: j.pop("baseline_artifact"), "job.baseline_artifact"),
    (lambda j: j.update(driver={"max_wakeups": 0}), "max_wakeups"),
    (lambda j: j.update(driver={"per_wake_max_rounds": -1}), "per_wake_max_rounds"),
])
def test_load_job_validates(tmp_path, mutate, match):
    job = _job_dict(tmp_path)
    mutate(job)
    with pytest.raises(td.DriverJobError, match=match):
        td.load_job(job)


def test_load_job_rejects_missing_or_invalid_file(tmp_path):
    with pytest.raises(td.DriverJobError, match="not found"):
        td.load_job(tmp_path / "missing.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{nope", encoding="utf-8")
    with pytest.raises(td.DriverJobError, match="not valid JSON"):
        td.load_job(bad)


def test_driver_state_roundtrip_is_atomic(tmp_path):
    job = td.load_job(_job_dict(tmp_path))
    state = td.init_driver_state(job, now=1000.0)
    assert state == {
        "schema_version": td.DRIVER_SCHEMA_VERSION,
        "job_id": "job-1",
        "created_at": 1000.0,
        "wakeups_used": 0,
        "max_wakeups": 5,
        "phase_a": {"status": "pending", "attempts": 0, "error": None,
                    "completed_at": None},
        "tournament_started": False,
        "wake_history": [],
        "notification": {"required": False, "sent": False, "payload": None,
                         "built_at": None},
        "stopped": {"stopped": False, "reason": None},
    }
    path = td.driver_state_path(job)
    assert path == ts.tournament_dir(Path(job["runtime_root"]), "run-1") / "driver-state.json"
    td.save_driver_state(state, path)
    assert td.load_driver_state(path) == state
    leftovers = [p for p in path.parent.iterdir() if p.name != "driver-state.json"]
    assert leftovers == []


def _tick(job_path, t, **kwargs):
    return td.driver_tick(job=job_path, now_fn=lambda: float(t), **kwargs)


def _prepared_job(tmp_path, **overrides) -> Path:
    """Job whose baseline artifact already exists (skips Phase A)."""
    job = _job_dict(tmp_path, **overrides)
    artifact = Path(job["baseline_artifact"])
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps({"metric": {"value": 0.9}}), encoding="utf-8")
    return _write_job(tmp_path, job)


def test_tick_burns_wakeup_on_entry_and_persists_before_cap_check(tmp_path):
    job_path = _prepared_job(tmp_path, driver={"max_wakeups": 1,
                                               "per_wake_max_rounds": 3,
                                               "per_wake_max_minutes": 20})
    with pytest.raises(NotImplementedError):
        _tick(job_path, 1000.0)  # proceed path lands in Task 3/4
    state = td.load_driver_state(td.driver_state_path(td.load_job(job_path)))
    assert state["wakeups_used"] == 1  # burned + persisted despite the crash
    plan2 = _tick(job_path, 2000.0)
    assert plan2["action"] == "stop_budget_exhausted"
    state = td.load_driver_state(td.driver_state_path(td.load_job(job_path)))
    assert state["wakeups_used"] == 2
    assert state["stopped"] == {"stopped": True, "reason": "max_wakeups"}


def test_tick_closes_interrupted_wake_from_previous_session(tmp_path):
    job_path = _prepared_job(tmp_path)
    with pytest.raises(NotImplementedError):
        _tick(job_path, 1000.0)  # opens wake 1, session then "dies" (no finish)
    with pytest.raises(NotImplementedError):
        _tick(job_path, 2000.0)  # wake 2 must close wake 1 as interrupted
    state = td.load_driver_state(td.driver_state_path(td.load_job(job_path)))
    first = state["wake_history"][0]
    assert first["closed"] is True
    assert first["exit_reason"] == "interrupted"
    assert state["wake_history"][1]["closed"] is False


def test_tick_quiescent_after_stopped_and_notified(tmp_path):
    job_path = _prepared_job(tmp_path)
    job = td.load_job(job_path)
    path = td.driver_state_path(job)
    state = td.init_driver_state(job, now=900.0)
    state["stopped"] = {"stopped": True, "reason": "max_wakeups"}
    state["notification"] = {"required": True, "sent": True,
                             "payload": {"x": 1}, "built_at": 950.0}
    td.save_driver_state(state, path)
    plan = _tick(job_path, 1000.0)
    assert plan["action"] == "quiescent"
    # wakeups still burn while quiescent (self-quenching, spec)
    assert td.load_driver_state(path)["wakeups_used"] == 1


def test_tick_finalize_when_stopped_but_notification_unsent(tmp_path):
    job_path = _prepared_job(tmp_path)
    job = td.load_job(job_path)
    path = td.driver_state_path(job)
    state = td.init_driver_state(job, now=900.0)
    state["stopped"] = {"stopped": True, "reason": "preflight_failed"}
    state["notification"] = {"required": True, "sent": False,
                             "payload": {"x": 1}, "built_at": 950.0}
    td.save_driver_state(state, path)
    plan = _tick(job_path, 1000.0)
    assert plan["action"] == "finalize"
