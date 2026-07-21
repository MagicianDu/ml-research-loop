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
    plan1 = _tick(job_path, 1000.0)
    assert plan1["wakeup"]["index"] == 1
    state = td.load_driver_state(td.driver_state_path(td.load_job(job_path)))
    assert state["wakeups_used"] == 1  # burned + persisted before the cap check
    plan2 = _tick(job_path, 2000.0)
    assert plan2["action"] == "stop_budget_exhausted"
    state = td.load_driver_state(td.driver_state_path(td.load_job(job_path)))
    assert state["wakeups_used"] == 2
    assert state["stopped"] == {"stopped": True, "reason": "max_wakeups"}


def test_tick_closes_interrupted_wake_from_previous_session(tmp_path):
    job_path = _prepared_job(tmp_path)
    _tick(job_path, 1000.0)  # opens wake 1; session then "dies" (no explicit close)
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


def _fasttext_job(tmp_path: Path, **overrides) -> dict:
    spec = tmp_path / "spec.json"
    train = tmp_path / "train.csv"
    test = tmp_path / "test.csv"
    for f in (spec, train, test):
        f.write_text("x", encoding="utf-8")
    return _job_dict(
        tmp_path,
        target={"kind": "fasttext", "target_spec": str(spec),
                "train_csv": str(train), "test_csv": str(test),
                "fasttext_binary": str(tmp_path / "fasttext")},
        **overrides,
    )


def _ok_probe(**kwargs):
    return {"binary": {"available": True}}


def _bad_probe(**kwargs):
    return {"binary": {"available": False}}


def test_preflight_missing_lists_each_absent_prerequisite(tmp_path):
    job = td.load_job(_fasttext_job(tmp_path))
    Path(job["target"]["train_csv"]).unlink()
    missing = td._preflight_missing(job, _bad_probe)
    assert any("train_csv" in item for item in missing)
    assert any("fasttext binary" in item for item in missing)
    ok_job = td.load_job(_job_dict(tmp_path))
    assert td._preflight_missing(ok_job, _ok_probe) == []


def test_tick_preflight_failure_is_immediately_permanent(tmp_path):
    job = _fasttext_job(tmp_path)
    Path(job["target"]["test_csv"]).unlink()
    job_path = _write_job(tmp_path, job)
    plan = td.driver_tick(job=job_path, now_fn=lambda: 1000.0,
                          probe_fn=_ok_probe)
    assert plan["action"] == "preflight_failed"
    assert any("test_csv" in item for item in plan["missing"])
    state = td.load_driver_state(td.driver_state_path(td.load_job(job_path)))
    assert state["stopped"] == {"stopped": True, "reason": "preflight_failed"}


def test_tick_phase_a_retry_then_permanent_failure(tmp_path):
    job_path = _write_job(tmp_path, _fasttext_job(tmp_path))

    def exploding_baseline(job, phase_a_dir):
        raise RuntimeError("training crashed")

    plan1 = td.driver_tick(job=job_path, now_fn=lambda: 1000.0,
                           probe_fn=_ok_probe, baseline_fn=exploding_baseline)
    assert plan1["action"] == "phase_a_retry"
    state = td.load_driver_state(td.driver_state_path(td.load_job(job_path)))
    assert state["stopped"]["stopped"] is False  # silent retry, not stopped
    assert state["phase_a"]["attempts"] == 1
    assert "training crashed" in state["phase_a"]["error"]

    plan2 = td.driver_tick(job=job_path, now_fn=lambda: 2000.0,
                           probe_fn=_ok_probe, baseline_fn=exploding_baseline)
    assert plan2["action"] == "preflight_failed"
    assert plan2["reason"] == "phase_a_failed"
    state = td.load_driver_state(td.driver_state_path(td.load_job(job_path)))
    assert state["stopped"] == {"stopped": True, "reason": "phase_a_failed"}
    assert state["phase_a"] == {
        "status": "failed", "attempts": 2,
        "error": state["phase_a"]["error"], "completed_at": None,
    }


def test_tick_phase_a_success_writes_artifact_via_injected_fn(tmp_path):
    job = _fasttext_job(tmp_path)
    job_path = _write_job(tmp_path, job)

    def fake_baseline(job_obj, phase_a_dir):
        report = Path(phase_a_dir) / "fasttext-baseline-report.json"
        report.parent.mkdir(parents=True, exist_ok=True)
        report.write_text(json.dumps({"metric": {"p_at_1": 0.914}}),
                          encoding="utf-8")
        return str(report)

    plan = td.driver_tick(job=job_path, now_fn=lambda: 1000.0,
                          probe_fn=_ok_probe, baseline_fn=fake_baseline)
    assert plan["action"] == "proceed"
    artifact = Path(td.load_job(job_path)["baseline_artifact"])
    assert json.loads(artifact.read_text(encoding="utf-8")) == {
        "metric": {"p_at_1": 0.914}
    }
    state = td.load_driver_state(td.driver_state_path(td.load_job(job_path)))
    assert state["phase_a"]["status"] == "completed"


def test_synthetic_baseline_auto_written(tmp_path):
    job_path = _write_job(tmp_path, _job_dict(tmp_path))  # no artifact on disk
    plan = td.driver_tick(job=job_path, now_fn=lambda: 1000.0)
    assert plan["action"] == "proceed"
    artifact = Path(td.load_job(job_path)["baseline_artifact"])
    assert json.loads(artifact.read_text(encoding="utf-8")) == {
        "metric": {"value": 0.9}
    }


def test_tick_auto_starts_tournament_and_returns_proceed_plan(tmp_path):
    job_path = _write_job(tmp_path, _job_dict(tmp_path))
    plan = td.driver_tick(job=job_path, now_fn=lambda: 1000.0)
    assert plan["action"] == "proceed"
    assert plan["tournament"] == {"started": True, "stopped": False,
                                  "stop_reason": None}
    assert plan["pending_action"] == {"type": "need_direction_proposals", "k": 3}
    assert plan["per_wake_budget"] == {"max_rounds": 3,
                                       "deadline_at": 1000.0 + 20 * 60}
    assert plan["best_so_far"] == {"winner": None, "total_rounds_used": 0}
    job = td.load_job(job_path)
    engine = ts.load_tournament_state(
        ts.state_path(Path(job["runtime_root"]), "run-1"))
    assert engine["baseline"] == {
        "value": 0.9, "artifact": str(Path(job["baseline_artifact"]))}
    state = td.load_driver_state(td.driver_state_path(job))
    assert state["tournament_started"] is True
    assert state["wake_history"][-1]["ledger_rounds_at_start"] == 0


def test_tick_adopts_engine_state_from_crash_window_without_restart(tmp_path):
    # Simulate a crash between start_tournament writing state.json and the
    # driver persisting tournament_started=True: the engine state exists on
    # disk but the driver's own flag is still False. driver_tick must adopt
    # the existing engine state instead of re-invoking start_tournament, which
    # would raise FileExistsError and burn wakeups until a misleading stop.
    job = td.load_job(_job_dict(tmp_path))
    rr = Path(job["runtime_root"])
    artifact = Path(job["baseline_artifact"])
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_text(json.dumps({"metric": {"value": 0.9}}), encoding="utf-8")

    # Engine state on disk, as a crashed auto-start would have left it.
    ts.start_tournament(
        runtime_root=rr,
        run_id=job["run_id"],
        target_id=job["target_id"],
        config=job["tournament_config"],
        baseline={"value": 0.9, "artifact": str(artifact)},
        target=job["target"],
        now_fn=lambda: 1000.0,
    )
    assert ts.state_path(rr, job["run_id"]).exists()

    # Driver state with tournament_started still False (never persisted).
    driver_state = td.init_driver_state(job, now=1000.0)
    assert driver_state["tournament_started"] is False
    td.save_driver_state(driver_state, td.driver_state_path(job))

    # The next wake must not raise FileExistsError; it adopts the engine state.
    plan = td.driver_tick(job=job, now_fn=lambda: 2000.0)
    assert plan["action"] == "proceed"
    assert plan["tournament"] == {"started": True, "stopped": False,
                                  "stop_reason": None}

    state = td.load_driver_state(td.driver_state_path(job))
    assert state["tournament_started"] is True


def test_tick_second_wake_reports_existing_progress(tmp_path):
    job_path = _write_job(tmp_path, _job_dict(tmp_path))
    td.driver_tick(job=job_path, now_fn=lambda: 1000.0)
    job = td.load_job(job_path)
    rr = Path(job["runtime_root"])
    ts.submit_directions(runtime_root=rr, run_id="run-1", directions=[
        {"arm_id": f"a{i}", "hypothesis": f"h{i}",
         "first_proposal": {"params": {p: 1}}}
        for i, p in ((1, "a"), (2, "b"), (3, "c"))
    ])
    ts.step(runtime_root=rr, run_id="run-1", now_fn=lambda: 1100.0)  # a1 round
    plan = td.driver_tick(job=job_path, now_fn=lambda: 2000.0)
    assert plan["action"] == "proceed"
    assert plan["best_so_far"]["total_rounds_used"] == 1
    assert plan["best_so_far"]["winner"]["arm_id"] == "a1"
    state = td.load_driver_state(td.driver_state_path(job))
    assert state["wake_history"][-1]["ledger_rounds_at_start"] == 1


@pytest.mark.parametrize("payload, expected", [
    ({"metric": {"p_at_1": 0.914}}, 0.914),
    ({"metric": {"value": 0.9}}, 0.9),
    ({"value": 0.5}, 0.5),
])
def test_baseline_value_from_artifact(tmp_path, payload, expected):
    p = tmp_path / "b.json"
    p.write_text(json.dumps(payload), encoding="utf-8")
    assert td._baseline_value_from_artifact(p) == expected
    p.write_text(json.dumps({"nope": 1}), encoding="utf-8")
    with pytest.raises(td.DriverJobError, match="baseline"):
        td._baseline_value_from_artifact(p)


def _run_to_engine_stop(tmp_path):
    """Drive a tiny tournament to target_reached; returns job_path."""
    job = _job_dict(tmp_path)
    job["tournament_config"]["k"] = 2
    job["tournament_config"]["budgets"]["target_value"] = 0.91
    job_path = _write_job(tmp_path, job)
    td.driver_tick(job=job_path, now_fn=lambda: 1000.0)
    rr = Path(td.load_job(job_path)["runtime_root"])
    ts.submit_directions(runtime_root=rr, run_id="run-1", directions=[
        {"arm_id": "a1", "hypothesis": "h1", "first_proposal": {"params": {"a": 1}}},
        {"arm_id": "a2", "hypothesis": "h2", "first_proposal": {"params": {"b": 1}}},
    ])
    ts.step(runtime_root=rr, run_id="run-1", now_fn=lambda: 1100.0)  # a1 -> 0.91 target
    ts.step(runtime_root=rr, run_id="run-1", now_fn=lambda: 1200.0)  # finalize
    return job_path


def test_finish_closes_wake_with_ledger_diff(tmp_path):
    job_path = _run_to_engine_stop(tmp_path)
    result = td.driver_finish(job=job_path, now_fn=lambda: 1300.0)
    assert result["status"] == "closed"
    assert result["wake"]["closed"] is True
    assert result["wake"]["rounds_executed"] == 1
    assert result["wake"]["exit_reason"] == "engine_stopped"


def test_finish_builds_notification_exactly_once(tmp_path):
    job_path = _run_to_engine_stop(tmp_path)
    first = td.driver_finish(job=job_path, now_fn=lambda: 1300.0)
    payload = first["notification"]["payload"]
    assert first["notification"]["required"] is True
    assert first["notification"]["sent"] is False
    assert payload["stop_reason"] == "target_reached"
    assert payload["winner"]["arm_id"] == "a1"
    assert payload["rounds_used"] == 1
    assert payload["wakeups_used"] == 1
    assert payload["report_path"]  # finalize ran, report written
    second = td.driver_finish(job=job_path, now_fn=lambda: 1400.0)
    assert second["notification"]["payload"] == payload  # not rebuilt
    state = td.load_driver_state(td.driver_state_path(td.load_job(job_path)))
    assert state["notification"]["built_at"] == 1300.0  # first build time kept


def test_finish_mark_notified_flips_flag_only(tmp_path):
    job_path = _run_to_engine_stop(tmp_path)
    td.driver_finish(job=job_path, now_fn=lambda: 1300.0)
    result = td.driver_finish(job=job_path, mark_notified=True,
                              now_fn=lambda: 1400.0)
    assert result["status"] == "notified"
    state = td.load_driver_state(td.driver_state_path(td.load_job(job_path)))
    assert state["notification"]["sent"] is True
    # wake history untouched by the mark call (no double close, no new entry)
    assert len(state["wake_history"]) == 1


def test_finish_without_stop_closes_wake_without_notification(tmp_path):
    job_path = _write_job(tmp_path, _job_dict(tmp_path))
    td.driver_tick(job=job_path, now_fn=lambda: 1000.0)
    result = td.driver_finish(job=job_path, now_fn=lambda: 1100.0)
    assert result["status"] == "closed"
    assert result["wake"]["exit_reason"] == "per_wake_budget"
    assert result["notification"] == {"required": False, "sent": False,
                                      "payload": None}


class _Clock:
    def __init__(self, start=1000.0):
        self.t = start

    def __call__(self):
        self.t += 1.0
        return self.t


_FAMILIES = {"a1": "a", "a2": "b", "a3": "c"}


def _scripted_proposal(arm_id: str, engine_state: dict) -> dict:
    """Deterministic LLM stand-in: escalate the arm's own family parameter."""
    arm = next(a for a in engine_state["arms"] if a["arm_id"] == arm_id)
    step_count = len(arm["history"]) + 1
    return {"params": {_FAMILIES[arm_id]: step_count + 1}}


def _drive_one_wake(job_path: Path, clock: _Clock) -> dict:
    plan = td.driver_tick(job=job_path, now_fn=clock)
    job = td.load_job(job_path)
    rr, run_id = Path(job["runtime_root"]), job["run_id"]
    if plan["action"] == "proceed":
        rounds = 0
        while rounds < plan["per_wake_budget"]["max_rounds"]:
            engine = ts.load_tournament_state(ts.state_path(rr, run_id))
            if engine["stop"]["stopped"]:
                break
            pending = engine["pending_action"]
            if pending["type"] == "need_direction_proposals":
                ts.submit_directions(runtime_root=rr, run_id=run_id, directions=[
                    {"arm_id": a, "hypothesis": f"push {f}",
                     "first_proposal": {"params": {f: 1}}}
                    for a, f in _FAMILIES.items()
                ])
            elif pending["type"] == "need_round_proposal":
                ts.submit_proposal(
                    runtime_root=rr, run_id=run_id, arm_id=pending["arm_id"],
                    proposal=_scripted_proposal(pending["arm_id"], engine),
                )
            else:
                if pending["type"] == "run_round":
                    rounds += 1
                ts.step(runtime_root=rr, run_id=run_id, now_fn=clock)
    if plan["action"] in ("proceed", "finalize"):
        engine = ts.load_tournament_state(ts.state_path(rr, run_id))
        if engine["stop"]["stopped"] and engine["pending_action"] is not None:
            ts.step(runtime_root=rr, run_id=run_id, now_fn=clock)  # finalize
    fin = td.driver_finish(job=job_path, now_fn=clock)
    if fin["notification"]["required"] and not fin["notification"]["sent"]:
        td.driver_finish(job=job_path, mark_notified=True, now_fn=clock)
    return plan


def test_unattended_lifecycle_completes_across_multiple_wakes(tmp_path):
    job = _job_dict(tmp_path)
    # target 0.95 needs a=5, forcing the run across >=3 wakes at 3 rounds/wake
    job["tournament_config"]["budgets"]["target_value"] = 0.95
    job_path = _write_job(tmp_path, job)
    clock = _Clock()
    wakes = 0
    while wakes < 10:
        wakes += 1
        plan = _drive_one_wake(job_path, clock)
        if plan["action"] in ("quiescent", "stop_budget_exhausted"):
            break
        state = td.load_driver_state(td.driver_state_path(td.load_job(job_path)))
        if state["notification"]["sent"]:
            break
    state = td.load_driver_state(td.driver_state_path(td.load_job(job_path)))
    assert wakes >= 3  # genuinely multi-wake, not a single-session run
    assert state["stopped"]["stopped"] is True
    assert state["notification"]["sent"] is True
    assert state["notification"]["payload"]["stop_reason"] == "target_reached"
    assert state["notification"]["payload"]["winner"]["arm_id"] == "a1"
    for entry in state["wake_history"]:
        assert entry["closed"] is True
        assert entry["rounds_executed"] <= 3  # per-wake cap never exceeded
    built_at_before = state["notification"]["built_at"]
    payload_before = state["notification"]["payload"]
    extra = td.driver_finish(job=job_path, now_fn=clock)
    assert extra["notification"]["payload"] == payload_before  # not rebuilt
    state_after = td.load_driver_state(td.driver_state_path(td.load_job(job_path)))
    assert state_after["notification"]["built_at"] == built_at_before  # timestamp unchanged


def test_unattended_lifecycle_stops_on_wakeup_budget(tmp_path):
    job = _job_dict(tmp_path)
    job["driver"] = {"max_wakeups": 2, "per_wake_max_rounds": 1,
                     "per_wake_max_minutes": 20}
    job["tournament_config"]["budgets"]["target_value"] = None  # never reached
    job_path = _write_job(tmp_path, job)
    clock = _Clock()
    plans = [_drive_one_wake(job_path, clock) for _ in range(3)]
    assert plans[2]["action"] == "stop_budget_exhausted"
    state = td.load_driver_state(td.driver_state_path(td.load_job(job_path)))
    assert state["stopped"] == {"stopped": True, "reason": "max_wakeups"}
    assert state["notification"]["sent"] is True
    assert state["notification"]["payload"]["stop_reason"] == "max_wakeups"
