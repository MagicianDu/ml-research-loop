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
