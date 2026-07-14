from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib import tournament_search as ts


def _config(**overrides):
    config = {
        "k": 2,
        "initial_rounds_per_arm": 1,
        "halving": 2,
        "epsilon": 0.001,
        "metric": "P@1",
        "direction": "maximize",
        "budgets": {"max_total_rounds": 10, "max_wall_seconds": 3600,
                    "target_value": None},
    }
    config.update(overrides)
    return config


def _baseline(tmp_path: Path, value: float = 0.9) -> dict:
    artifact = tmp_path / "baseline-report.json"
    artifact.write_text(json.dumps({"metric": {"p_at_1": value}}), encoding="utf-8")
    return {"value": value, "artifact": str(artifact)}


def _synthetic_target() -> dict:
    return {"kind": "synthetic", "baseline_value": 0.9,
            "weights": {"a": 0.01, "b": 0.001}, "failure_params": []}


def test_start_tournament_writes_state_with_pending_directions(tmp_path):
    state = ts.start_tournament(
        runtime_root=tmp_path, run_id="run-1", target_id="demo",
        config=_config(), baseline=_baseline(tmp_path),
        target=_synthetic_target(), now_fn=lambda: 1000.0,
    )
    assert state["schema_version"] == ts.TOURNAMENT_SCHEMA_VERSION
    assert state["run_id"] == "run-1"
    assert state["arms"] == []
    assert state["stage"] == {"index": 0, "rounds_per_arm": 1}
    assert state["ledger"] == {"total_rounds_used": 0, "wall_seconds_used": 0.0,
                               "llm_cost_estimate": None}
    assert state["created_at"] == 1000.0
    assert state["stop"] == {"stopped": False, "reason": None}
    assert state["pending_action"] == {"type": "need_direction_proposals", "k": 2}
    on_disk = ts.load_tournament_state(ts.state_path(tmp_path, "run-1"))
    assert on_disk == state


def test_start_tournament_is_atomic_and_leaves_no_temp_files(tmp_path):
    ts.start_tournament(
        runtime_root=tmp_path, run_id="run-1", target_id="demo",
        config=_config(), baseline=_baseline(tmp_path),
        target=_synthetic_target(), now_fn=lambda: 1000.0,
    )
    run_dir = ts.tournament_dir(tmp_path, "run-1")
    leftovers = [p for p in run_dir.iterdir() if p.name != "state.json"]
    assert leftovers == []


def test_start_tournament_rejects_existing_run(tmp_path):
    kwargs = dict(runtime_root=tmp_path, run_id="run-1", target_id="demo",
                  config=_config(), baseline=_baseline(tmp_path),
                  target=_synthetic_target(), now_fn=lambda: 1000.0)
    ts.start_tournament(**kwargs)
    with pytest.raises(FileExistsError, match="already exists"):
        ts.start_tournament(**kwargs)


def test_start_tournament_rejects_missing_baseline_artifact(tmp_path):
    with pytest.raises(FileNotFoundError, match="baseline artifact"):
        ts.start_tournament(
            runtime_root=tmp_path, run_id="run-1", target_id="demo",
            config=_config(),
            baseline={"value": 0.9, "artifact": str(tmp_path / "missing.json")},
            target=_synthetic_target(), now_fn=lambda: 1000.0,
        )


@pytest.mark.parametrize("bad, match", [
    ({"k": 1}, "k must be >= 2"),
    ({"halving": 3}, "halving=2"),
    ({"direction": "sideways"}, "direction"),
    ({"epsilon": 0}, "epsilon"),
    ({"initial_rounds_per_arm": 0}, "initial_rounds_per_arm"),
])
def test_start_tournament_validates_config(tmp_path, bad, match):
    with pytest.raises(ValueError, match=match):
        ts.start_tournament(
            runtime_root=tmp_path, run_id="run-1", target_id="demo",
            config=_config(**bad), baseline=_baseline(tmp_path),
            target=_synthetic_target(), now_fn=lambda: 1000.0,
        )


def _started(tmp_path, **config_overrides):
    return ts.start_tournament(
        runtime_root=tmp_path, run_id="run-1", target_id="demo",
        config=_config(**config_overrides), baseline=_baseline(tmp_path),
        target=_synthetic_target(), now_fn=lambda: 1000.0,
    )


def _directions(n=2):
    return [
        {"arm_id": f"a{i}", "hypothesis": f"hypothesis {i}",
         "first_proposal": {"params": {"a": i}}}
        for i in range(1, n + 1)
    ]


def test_submit_directions_creates_arms_and_queues_first_round(tmp_path):
    _started(tmp_path)
    state = ts.submit_directions(
        runtime_root=tmp_path, run_id="run-1", directions=_directions(2),
    )
    assert [arm["arm_id"] for arm in state["arms"]] == ["a1", "a2"]
    arm = state["arms"][0]
    assert arm["status"] == "active"
    assert arm["best"] == {"value": 0.9, "round_id": None,
                           "artifact": state["baseline"]["artifact"]}
    assert arm["rounds_allocated"] == 1
    assert arm["queued_proposal"] == {"params": {"a": 1}}
    assert Path(arm["workspace"]).is_dir()
    assert state["pending_action"] == {"type": "run_round", "arm_id": "a1",
                                       "round_id": "a1-r1"}
    on_disk = ts.load_tournament_state(ts.state_path(tmp_path, "run-1"))
    assert on_disk == state


@pytest.mark.parametrize("mutate, match", [
    (lambda d: d[:1], "expected 2 directions"),
    (lambda d: [dict(d[0], arm_id="a2")] + d[1:], "arm_id values must be unique"),
    (lambda d: [dict(d[0], hypothesis="")] + d[1:], "hypothesis"),
    (lambda d: [dict(d[0], hypothesis=d[1]["hypothesis"])] + d[1:],
     "hypothesis values must be unique"),
    (lambda d: [dict(d[0], first_proposal={})] + d[1:], "first_proposal"),
])
def test_submit_directions_formal_validation(tmp_path, mutate, match):
    _started(tmp_path)
    with pytest.raises(ValueError, match=match):
        ts.submit_directions(
            runtime_root=tmp_path, run_id="run-1",
            directions=mutate(_directions(2)),
        )


def test_submit_directions_rejected_when_not_pending(tmp_path):
    _started(tmp_path)
    ts.submit_directions(runtime_root=tmp_path, run_id="run-1",
                         directions=_directions(2))
    with pytest.raises(ts.TournamentStateError, match="need_direction_proposals"):
        ts.submit_directions(runtime_root=tmp_path, run_id="run-1",
                             directions=_directions(2))


@pytest.mark.parametrize("value, best, direction, expected", [
    (0.92, 0.90, "maximize", pytest.approx(0.02)),
    (0.90, 0.92, "maximize", pytest.approx(-0.02)),
    (0.30, 0.35, "minimize", pytest.approx(0.05)),
    (0.35, 0.30, "minimize", pytest.approx(-0.05)),
])
def test_signed_delta_is_positive_when_better(value, best, direction, expected):
    assert ts.signed_delta(value, best, direction) == expected


@pytest.mark.parametrize("delta, expected", [
    (0.001, "accept"),      # == epsilon
    (0.01, "accept"),
    (0.0005, "near_tie"),   # 0 < delta < epsilon
    (0.0, "reject"),
    (-0.01, "reject"),
])
def test_classify_delta(delta, expected):
    assert ts.classify_delta(delta, epsilon=0.001) == expected


def _arm(arm_id, best_value, status="active"):
    return {"arm_id": arm_id, "hypothesis": arm_id, "status": status,
            "workspace": "", "best": {"value": best_value, "round_id": None,
                                      "artifact": ""},
            "rounds_used": 1, "rounds_allocated": 1,
            "invalid_proposal_streak": 0, "consecutive_failures": 0,
            "queued_proposal": None, "failure_reason": None, "history": []}


def test_rank_active_arms_direction_aware_and_ignores_dead_arms():
    state = {"config": _config(), "arms": [
        _arm("a1", 0.91), _arm("a2", 0.93), _arm("a3", 0.99, status="failed"),
        _arm("a4", 0.91),
    ]}
    assert ts.rank_active_arms(state) == ["a2", "a1", "a4"]
    state["config"]["direction"] = "minimize"
    assert ts.rank_active_arms(state) == ["a1", "a4", "a2"]


def test_apply_stage_end_prunes_half_and_doubles_allocation():
    state = {"config": _config(k=4), "stage": {"index": 0, "rounds_per_arm": 3},
             "arms": [_arm("a1", 0.94), _arm("a2", 0.92), _arm("a3", 0.91),
                      _arm("a4", 0.90)]}
    for arm in state["arms"]:
        arm["rounds_used"] = arm["rounds_allocated"] = 3
    ts.apply_stage_end(state)
    by_id = {arm["arm_id"]: arm for arm in state["arms"]}
    assert by_id["a1"]["status"] == "active"
    assert by_id["a2"]["status"] == "active"
    assert by_id["a3"]["status"] == "pruned"
    assert by_id["a4"]["status"] == "pruned"
    assert state["stage"] == {"index": 1, "rounds_per_arm": 6}
    assert by_id["a1"]["rounds_allocated"] == 9   # 3 used + 6 new
    assert by_id["a3"]["rounds_allocated"] == 3   # pruned arms unchanged


def test_apply_stage_end_with_single_survivor_keeps_it():
    state = {"config": _config(), "stage": {"index": 2, "rounds_per_arm": 4},
             "arms": [_arm("a1", 0.94)]}
    state["arms"][0]["rounds_used"] = state["arms"][0]["rounds_allocated"] = 4
    ts.apply_stage_end(state)
    assert state["arms"][0]["status"] == "active"
    assert state["arms"][0]["rounds_allocated"] == 12  # 4 used + 8 new
    assert state["stage"] == {"index": 3, "rounds_per_arm": 8}


def _stop_state(**overrides):
    state = {
        "config": _config(),
        "created_at": 1000.0,
        "arms": [_arm("a1", 0.91)],
        "ledger": {"total_rounds_used": 1, "wall_seconds_used": 0.0,
                   "llm_cost_estimate": None},
    }
    state.update(overrides)
    return state


def test_check_stop_none_when_no_condition_met():
    assert ts.check_stop(_stop_state(), now=1010.0) is None


def test_check_stop_target_reached_maximize_and_minimize():
    state = _stop_state()
    state["config"]["budgets"]["target_value"] = 0.91
    assert ts.check_stop(state, now=1010.0) == "target_reached"
    state["config"]["direction"] = "minimize"
    state["config"]["budgets"]["target_value"] = 0.5
    assert ts.check_stop(state, now=1010.0) is None  # 0.91 > 0.5, not reached


def test_check_stop_all_arms_failed():
    state = _stop_state(arms=[_arm("a1", 0.91, status="failed"),
                              _arm("a2", 0.91, status="pruned")])
    assert ts.check_stop(state, now=1010.0) == "all_arms_failed"


def test_check_stop_rounds_and_time_budgets():
    state = _stop_state()
    state["ledger"]["total_rounds_used"] = 10
    assert ts.check_stop(state, now=1010.0) == "max_total_rounds"
    state["ledger"]["total_rounds_used"] = 1
    assert ts.check_stop(state, now=1000.0 + 3600.0) == "max_wall_seconds"


def test_check_stop_precedence_target_beats_everything():
    state = _stop_state(arms=[_arm("a1", 0.95)])
    state["config"]["budgets"]["target_value"] = 0.95
    state["ledger"]["total_rounds_used"] = 10
    assert ts.check_stop(state, now=1000.0 + 9999.0) == "target_reached"


class _ScriptedExecutor:
    """Returns scripted values per call; script entries are floats or 'boom'."""

    def __init__(self, script, invalid_params=("bad",)):
        self.script = list(script)
        self.invalid_params = set(invalid_params)
        self.calls = []

    def validate_proposal(self, arm, proposal):
        params = proposal.get("params") or {}
        if self.invalid_params & set(params):
            raise ts.InvalidProposalError("scripted invalid proposal")

    def run_one_round(self, arm, proposal, round_dir):
        self.calls.append((arm["arm_id"], dict(proposal), Path(round_dir)))
        entry = self.script.pop(0)
        if entry == "boom":
            raise ts.ExecutorRoundError("scripted failure")
        artifact = Path(round_dir) / "eval.json"
        artifact.write_text(json.dumps({"value": entry}), encoding="utf-8")
        return {"value": float(entry), "artifacts": str(artifact)}


def _ready(tmp_path, script, k=2, **config_overrides):
    """Start + submit directions; returns (executor, run kwargs)."""
    ts.start_tournament(
        runtime_root=tmp_path, run_id="run-1", target_id="demo",
        config=_config(k=k, **config_overrides), baseline=_baseline(tmp_path),
        target=_synthetic_target(), now_fn=lambda: 1000.0,
    )
    ts.submit_directions(runtime_root=tmp_path, run_id="run-1",
                         directions=_directions(k))
    return _ScriptedExecutor(script), dict(runtime_root=tmp_path, run_id="run-1")


def test_step_accept_round_updates_best_and_ledger(tmp_path):
    executor, kwargs = _ready(tmp_path, script=[0.92])
    state = ts.step(executor=executor, now_fn=lambda: 1010.0, **kwargs)
    arm = state["arms"][0]
    record = arm["history"][0]
    assert record["decision"] == "accepted"
    assert record["value"] == 0.92
    assert record["repeat_value"] is None
    assert arm["best"]["value"] == 0.92
    assert arm["best"]["round_id"] == "a1-r1"
    assert arm["best"]["artifact"] == record["artifacts"]
    assert arm["rounds_used"] == 1
    assert arm["queued_proposal"] is None
    assert state["ledger"]["total_rounds_used"] == 1
    assert state["ledger"]["wall_seconds_used"] == pytest.approx(10.0)
    # a2 still has its queued first proposal -> next pending is a2's round
    assert state["pending_action"] == {"type": "run_round", "arm_id": "a2",
                                       "round_id": "a2-r1"}


def test_step_reject_round_keeps_best(tmp_path):
    executor, kwargs = _ready(tmp_path, script=[0.85])
    state = ts.step(executor=executor, now_fn=lambda: 1010.0, **kwargs)
    arm = state["arms"][0]
    assert arm["history"][0]["decision"] == "rejected"
    assert arm["best"]["value"] == 0.9
    assert arm["best"]["round_id"] is None


def test_step_near_tie_runs_one_repeat_and_averages(tmp_path):
    # epsilon=0.001; first run +0.0006 (near tie), repeat +0.0018 -> avg +0.0012 -> accept
    executor, kwargs = _ready(tmp_path, script=[0.9006, 0.9018])
    state = ts.step(executor=executor, now_fn=lambda: 1010.0, **kwargs)
    record = state["arms"][0]["history"][0]
    assert record["decision"] == "accepted"
    assert record["repeat_value"] == 0.9018
    assert record["effective_value"] == pytest.approx(0.9012)
    assert state["arms"][0]["best"]["value"] == pytest.approx(0.9012)
    assert len(executor.calls) == 2
    assert executor.calls[1][2].name == "repeat"


def test_step_near_tie_repeat_can_still_reject(tmp_path):
    # first +0.0006, repeat -0.0002 -> avg +0.0002 < epsilon -> reject
    executor, kwargs = _ready(tmp_path, script=[0.9006, 0.8998])
    state = ts.step(executor=executor, now_fn=lambda: 1010.0, **kwargs)
    assert state["arms"][0]["history"][0]["decision"] == "rejected"
    assert state["arms"][0]["best"]["value"] == 0.9


def test_step_failed_round_counts_and_two_failures_kill_arm(tmp_path):
    executor, kwargs = _ready(tmp_path, script=["boom", 0.92, "boom"],
                              initial_rounds_per_arm=2)
    state = ts.step(executor=executor, now_fn=lambda: 1010.0, **kwargs)  # a1 fails
    arm = state["arms"][0]
    assert arm["history"][0]["decision"] == "failed"
    assert arm["consecutive_failures"] == 1
    assert arm["rounds_used"] == 1
    assert arm["status"] == "active"
    # a2 succeeds (round-robin goes to a2 next), resets nothing on a1
    state = ts.step(executor=executor, now_fn=lambda: 1020.0, **kwargs)
    # a1's second round needs a proposal now (first_proposal consumed)
    assert state["pending_action"] == {"type": "need_round_proposal",
                                       "arm_id": "a1"}
    ts.submit_proposal(arm_id="a1", proposal={"params": {"a": 3}},
                       executor=executor, **kwargs)
    state = ts.step(executor=executor, now_fn=lambda: 1030.0, **kwargs)  # a1 fails again
    arm = state["arms"][0]
    assert arm["consecutive_failures"] == 2
    assert arm["status"] == "failed"
    assert arm["failure_reason"] == "consecutive_round_failures"


def test_step_recovers_interrupted_round_as_failed(tmp_path):
    executor, kwargs = _ready(tmp_path, script=[0.92])
    run_dir = ts.tournament_dir(tmp_path, "run-1")
    (run_dir / "arms" / "a1" / "rounds" / "a1-r1").mkdir(parents=True)
    state = ts.step(executor=executor, now_fn=lambda: 1010.0, **kwargs)
    record = state["arms"][0]["history"][0]
    assert record["decision"] == "failed"
    assert record["error"] == "interrupted"
    assert executor.calls == []  # executor never invoked for the corrupt round


def test_step_errors_when_waiting_for_submission(tmp_path):
    ts.start_tournament(
        runtime_root=tmp_path, run_id="run-1", target_id="demo",
        config=_config(), baseline=_baseline(tmp_path),
        target=_synthetic_target(), now_fn=lambda: 1000.0,
    )
    with pytest.raises(ts.TournamentStateError, match="requires a submission"):
        ts.step(runtime_root=tmp_path, run_id="run-1",
                executor=_ScriptedExecutor([]), now_fn=lambda: 1010.0)


def test_submit_proposal_queues_valid_proposal(tmp_path):
    executor, kwargs = _ready(tmp_path, script=[0.92, 0.93],
                              initial_rounds_per_arm=2)
    ts.step(executor=executor, now_fn=lambda: 1010.0, **kwargs)   # a1 r1
    ts.step(executor=executor, now_fn=lambda: 1020.0, **kwargs)   # a2 r1
    state = ts.submit_proposal(arm_id="a1", proposal={"params": {"a": 2}},
                               executor=executor, **kwargs)
    assert state["arms"][0]["queued_proposal"] == {"params": {"a": 2}}
    assert state["arms"][0]["invalid_proposal_streak"] == 0
    assert state["pending_action"] == {"type": "run_round", "arm_id": "a1",
                                       "round_id": "a1-r2"}


def test_submit_proposal_wrong_arm_or_state_rejected(tmp_path):
    executor, kwargs = _ready(tmp_path, script=[])
    # pending is run_round (first proposals queued), not need_round_proposal
    with pytest.raises(ts.TournamentStateError, match="need_round_proposal"):
        ts.submit_proposal(arm_id="a1", proposal={"params": {"a": 2}},
                           executor=executor, **kwargs)


def test_submit_proposal_invalid_streak_kills_arm_after_three(tmp_path):
    executor, kwargs = _ready(tmp_path, script=[0.92, 0.93],
                              initial_rounds_per_arm=2)
    ts.step(executor=executor, now_fn=lambda: 1010.0, **kwargs)
    ts.step(executor=executor, now_fn=lambda: 1020.0, **kwargs)
    for attempt in range(1, 4):
        with pytest.raises(ts.InvalidProposalError):
            ts.submit_proposal(arm_id="a1", proposal={"params": {"bad": 1}},
                               executor=executor, **kwargs)
        state = ts.load_tournament_state(ts.state_path(**kwargs))
        arm = state["arms"][0]
        if attempt < 3:
            assert arm["invalid_proposal_streak"] == attempt
            assert arm["status"] == "active"
        else:
            assert arm["status"] == "failed"
            assert arm["failure_reason"] == "invalid_proposals"
    # pending moved on to the surviving arm
    assert state["pending_action"]["arm_id"] == "a2"


def test_finalize_writes_report_with_winner_and_chain(tmp_path):
    executor, kwargs = _ready(tmp_path, script=[0.92, 0.89])
    ts.step(executor=executor, now_fn=lambda: 1010.0, **kwargs)   # a1 accept
    ts.step(executor=executor, now_fn=lambda: 1020.0, **kwargs)   # a2 reject
    state = ts.step(executor=executor, now_fn=lambda: 1030.0, **kwargs)  # stage_end
    # k=2, 1 round each used: a2 (0.89, rejected) pruned, a1 survives with
    # rounds_allocated = 1 (used) + 2 (new stage.rounds_per_arm) = 3, and its
    # queued_proposal was cleared after round 1, so the engine asks for a1's
    # next proposal before it can run another round.
    by_id = {arm["arm_id"]: arm for arm in state["arms"]}
    assert by_id["a2"]["status"] == "pruned"
    assert by_id["a1"]["status"] == "active"
    assert by_id["a1"]["rounds_allocated"] == 3
    assert state["pending_action"] == {"type": "need_round_proposal", "arm_id": "a1"}
    # force a stop via target and finalize (fresh run in its own root)
    second_root = tmp_path / "second"
    second_root.mkdir()
    executor2, kwargs2 = _ready(second_root, script=[0.95])
    state2 = ts.load_tournament_state(ts.state_path(**kwargs2))
    state2["config"]["budgets"]["target_value"] = 0.95
    ts.save_tournament_state(state2, ts.state_path(**kwargs2))
    ts.step(executor=executor2, now_fn=lambda: 1010.0, **kwargs2)  # a1 hits 0.95
    state2 = ts.load_tournament_state(ts.state_path(**kwargs2))
    assert state2["stop"] == {"stopped": True, "reason": "target_reached"}
    assert state2["pending_action"] == {"type": "finalize"}
    state2 = ts.step(executor=executor2, now_fn=lambda: 1040.0, **kwargs2)
    assert state2["report_written"] is True
    assert state2["pending_action"] is None
    report = json.loads(Path(state2["report_path"]).read_text(encoding="utf-8"))
    assert report["winner"]["arm_id"] == "a1"
    assert report["winner"]["improved"] is True
    assert [r["round_id"] for r in report["winner"]["accepted_chain"]] == ["a1-r1"]
    assert report["stop"]["reason"] == "target_reached"
    arm_rows = {row["arm_id"]: row for row in report["arms"]}
    assert arm_rows["a1"]["delta_vs_baseline"] == pytest.approx(0.05)


def test_synthetic_executor_is_deterministic(tmp_path):
    executor = ts.SyntheticArmExecutor(baseline_value=0.9,
                                       weights={"a": 0.01, "b": -0.005})
    arm = _arm("a1", 0.9)
    out = executor.run_one_round(arm, {"params": {"a": 2, "b": 1}}, tmp_path)
    assert out["value"] == pytest.approx(0.9 + 0.02 - 0.005)
    assert Path(out["artifacts"]).is_file()
    with pytest.raises(ts.InvalidProposalError):
        executor.validate_proposal(arm, {"params": {"zzz": 1}})
    with pytest.raises(ts.InvalidProposalError):
        executor.validate_proposal(arm, {"params": {}})


def test_build_arm_executor_factory(tmp_path):
    executor = ts.build_arm_executor(_synthetic_target())
    assert isinstance(executor, ts.SyntheticArmExecutor)
    with pytest.raises(ValueError, match="unknown target kind"):
        ts.build_arm_executor({"kind": "nope"})


def test_full_tournament_end_to_end_picks_the_right_direction(tmp_path):
    """4 directions, deterministic synthetic metric, target reached in stage 2."""
    target = {"kind": "synthetic", "baseline_value": 0.9,
              "weights": {"a": 0.01, "b": 0.001, "c": -0.01, "d": 0.0},
              "failure_params": []}
    config = _config(k=4, initial_rounds_per_arm=1)
    config["budgets"]["target_value"] = 0.92
    ts.start_tournament(runtime_root=tmp_path, run_id="e2e", target_id="demo",
                        config=config, baseline=_baseline(tmp_path),
                        target=target, now_fn=lambda: 1000.0)
    directions = [
        {"arm_id": "a1", "hypothesis": "push a", "first_proposal": {"params": {"a": 1}}},
        {"arm_id": "a2", "hypothesis": "push b", "first_proposal": {"params": {"b": 1}}},
        {"arm_id": "a3", "hypothesis": "push c", "first_proposal": {"params": {"c": 1}}},
        {"arm_id": "a4", "hypothesis": "push d", "first_proposal": {"params": {"d": 1}}},
    ]
    kwargs = dict(runtime_root=tmp_path, run_id="e2e")
    ts.submit_directions(directions=directions, **kwargs)
    clock = iter(range(1001, 1100))

    def drive():
        return ts.step(now_fn=lambda: float(next(clock)), **kwargs)

    for _ in range(4):        # stage 1: one round per arm (executor from factory)
        state = drive()
    state = drive()           # stage_end
    by_id = {arm["arm_id"]: arm for arm in state["arms"]}
    assert by_id["a1"]["status"] == "active"      # +0.01 accepted
    assert by_id["a2"]["status"] == "active"      # +0.001 accepted (== epsilon)
    assert by_id["a3"]["status"] == "pruned"      # -0.01 rejected
    assert by_id["a4"]["status"] == "pruned"      # +0.0 rejected
    assert state["stage"] == {"index": 1, "rounds_per_arm": 2}
    # stage 2: engine asks for proposals round-robin; feed a1 a winning one
    assert state["pending_action"] == {"type": "need_round_proposal",
                                       "arm_id": "a1"}
    ts.submit_proposal(arm_id="a1", proposal={"params": {"a": 2}}, **kwargs)
    state = drive()           # a1 hits 0.9 + 0.01 (best) ... proposal {"a":2} -> 0.92
    assert state["stop"] == {"stopped": True, "reason": "target_reached"}
    state = drive()           # finalize
    assert state["pending_action"] is None
    report = json.loads(Path(state["report_path"]).read_text(encoding="utf-8"))
    assert report["winner"]["arm_id"] == "a1"
    assert report["ledger"]["total_rounds_used"] == 5
    # resume identity: reloading from disk changes nothing
    reloaded = ts.load_tournament_state(ts.state_path(tmp_path, "e2e"))
    assert reloaded == state


def _fasttext_executor(tmp_path, patch_round_fn):
    return ts.FastTextArmExecutor(
        target_spec_path=tmp_path / "spec.json",
        train_csv=tmp_path / "train.csv",
        test_csv=tmp_path / "test.csv",
        fasttext_binary=tmp_path / "fasttext",
        max_train_seconds=60,
        patch_round_fn=patch_round_fn,
    )


def test_fasttext_executor_maps_arguments_and_result(tmp_path):
    seen = {}

    def fake_patch_round(config, *, train_csv, test_csv, fasttext_binary,
                         baseline_report, proposal):
        seen.update(config=config, train_csv=train_csv, test_csv=test_csv,
                    fasttext_binary=fasttext_binary,
                    baseline_report=baseline_report, proposal=proposal)
        report = Path(config.output_dir) / "improvement-report.json"
        report.write_text(json.dumps({"metric": {"p_at_1": 0.916}}),
                          encoding="utf-8")
        return {"status": "completed", "p_at_1": 0.916,
                "improvement_report": str(report)}

    executor = _fasttext_executor(tmp_path, fake_patch_round)
    arm = _arm("a1", 0.914)
    arm["best"]["artifact"] = str(tmp_path / "baseline-report.json")
    round_dir = tmp_path / "round"
    round_dir.mkdir()
    out = executor.run_one_round(
        arm, {"proposal_id": "p1", "train_args": {"-wordNgrams": 2}}, round_dir,
    )
    assert out == {"value": 0.916,
                   "artifacts": str(round_dir / "improvement-report.json")}
    assert seen["baseline_report"] == Path(arm["best"]["artifact"])
    assert seen["config"].output_dir == round_dir
    assert seen["config"].max_train_seconds == 60
    assert seen["train_csv"] == tmp_path / "train.csv"


def test_fasttext_executor_validate_maps_valueerror(tmp_path):
    executor = _fasttext_executor(tmp_path, patch_round_fn=None)
    with pytest.raises(ts.InvalidProposalError, match="unsupported fastText patch arg"):
        executor.validate_proposal(
            _arm("a1", 0.9),
            {"proposal_id": "p1", "train_args": {"-evil": 1}},
        )


def test_fasttext_executor_maps_harness_crash_to_round_error(tmp_path):
    def exploding(config, **kwargs):
        raise FileNotFoundError("fastText binary is not executable")

    executor = _fasttext_executor(tmp_path, exploding)
    round_dir = tmp_path / "round"
    round_dir.mkdir()
    with pytest.raises(ts.ExecutorRoundError, match="not executable"):
        executor.run_one_round(
            _arm("a1", 0.9),
            {"proposal_id": "p1", "train_args": {"-wordNgrams": 2}}, round_dir,
        )
