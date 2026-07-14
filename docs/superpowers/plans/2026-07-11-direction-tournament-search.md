# Direction Tournament Search Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the successive-halving direction tournament engine specified in `docs/superpowers/specs/2026-07-11-direction-tournament-search-design.md`: K LLM-proposed directions each run their own greedy fixed-budget chain, weak directions are pruned at stage boundaries, and a deterministic state machine owns everything except the two LLM touchpoints.

**Architecture:** One new module `lib/tournament_search.py` holds the state model (atomic `state.json` with an explicit `pending_action`), pure decision functions (ε accept/reject, ranking, pruning, stop checks), the `step()` state machine, and two `ArmExecutor` implementations (synthetic for tests/demos, fastText wrapping the existing `run_fasttext_patch_round`). A single stage-dispatched MCP tool `tournament` and a CLI mirror `ml-loop tournament` expose it. No LLM calls anywhere in this module.

**Tech Stack:** Python stdlib only (json/os/math/time/pathlib). Reuses `lib/fdp_common._is_plain_number`, the `os.replace` atomic-write pattern from `lib/experiment_store.py:69`, `lib/full_reproduction_harness.run_fasttext_patch_round`, and the stage-dispatch MCP tool pattern from `lib/mcp_service.py` (`gate_policy_tool`, line ~11078).

## Global Constraints

- Python 3.10 and 3.13 both pass CI — no 3.12+-only syntax.
- Stdlib only; no new dependencies in `pyproject.toml`.
- Every commit must leave `ruff check lib/ scripts/ ml_intern/ codex_plugin/ tests/` clean and the touched test files passing.
- All tests offline and deterministic: no network, no real fastText binary, no `time.sleep`; clocks injected via `now_fn`.
- Atomic state writes: temp file + `os.replace`, same pattern as `lib/experiment_store.py:69`.
- Thresholds fixed by the spec: near-tie repeat only when `0 < delta < epsilon`, at most one repeat per round; `consecutive_failures >= 2` fails an arm; `invalid_proposal_streak >= 3` fails an arm; prune keeps `max(1, ceil(active/2))`; survivor stage rounds double; v1 validates `halving == 2`.
- Stop-check precedence (documented order): `target_reached` → `all_arms_failed` → `max_total_rounds` → `max_wall_seconds`. LLM cost is ledger-only, never a stop trigger.
- Adding the `tournament` MCP tool is additive: do NOT bump `MCP_CONTRACT_VERSION`.
- Every commit message ends with the footer line `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Run tests with the project venv: `source .venv/bin/activate` first (or `.venv/bin/python -m pytest`).

## File Structure

- `lib/tournament_search.py` — new: schema/persistence, pure decisions, engine ops (`start_tournament`, `submit_directions`, `submit_proposal`, `step`, `build_tournament_report`), executor protocol + `SyntheticArmExecutor` + `FastTextArmExecutor` + `build_arm_executor` factory.
- `tests/unit/test_tournament_search.py` — new: all unit + integration tests for the engine and executors.
- `lib/mcp_service.py` — modify: import block, `REQUIRED_TOOLS`, `TOOL_CONTRACT_DESCRIPTIONS`, `tool_definitions()` schema entry, `tournament_tool` dispatcher, `TOOL_HANDLERS`.
- `tests/unit/test_mcp_service.py` — modify: behavioral tests for the `tournament` tool.
- `scripts/cli.py` — modify: `ml-loop tournament` subcommand group + dispatch.
- `tests/unit/test_cli.py` — modify: CLI behavioral tests.
- `README.md`, `docs/release-notes.md` — modify: document the new tool.

---

### Task 1: State model, atomic persistence, and `start_tournament`

**Files:**
- Create: `lib/tournament_search.py`
- Test: `tests/unit/test_tournament_search.py`

**Interfaces:**
- Consumes: `lib/fdp_common._is_plain_number(value) -> bool`.
- Produces (later tasks rely on these exact names):
  - `TOURNAMENT_SCHEMA_VERSION: str = "2026-07-11.tournament.v1"`
  - `MAX_CONSECUTIVE_FAILURES = 2`, `MAX_INVALID_PROPOSALS = 3`
  - `class TournamentStateError(ValueError)`
  - `tournament_dir(runtime_root: Path, run_id: str) -> Path` → `<runtime_root>/tournament/<run_id>`
  - `state_path(runtime_root: Path, run_id: str) -> Path` → `.../state.json`
  - `save_tournament_state(state: dict, path: Path) -> None` (atomic)
  - `load_tournament_state(path: Path) -> dict`
  - `refresh_pending(state: dict) -> None` (v1 of the derivation; extended in later tasks)
  - `start_tournament(*, runtime_root: Path, run_id: str, target_id: str, config: dict, baseline: dict, target: dict, now_fn: Callable[[], float] = time.time) -> dict`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_tournament_search.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_search.py -q`
Expected: FAIL / collection error with `ModuleNotFoundError` or `AttributeError` (module does not exist yet).

- [ ] **Step 3: Write the implementation**

Create `lib/tournament_search.py`:

```python
"""Direction tournament search engine.

Successive-halving tournament over per-direction greedy chains. The client
LLM appears at exactly two points (initial K directions, per-round
proposals); everything else -- scheduling, epsilon accept/reject, stage-end
ranking and pruning, budget ledger, stop conditions -- is this deterministic
state machine, driven off an atomically-written state.json whose
`pending_action` field tells any external driver what is needed next.

Spec: docs/superpowers/specs/2026-07-11-direction-tournament-search-design.md
"""

from __future__ import annotations

import json
import math
import os
import time
from pathlib import Path
from typing import Any, Callable

from lib.fdp_common import _is_plain_number

TOURNAMENT_SCHEMA_VERSION = "2026-07-11.tournament.v1"
MAX_CONSECUTIVE_FAILURES = 2
MAX_INVALID_PROPOSALS = 3
_DIRECTIONS = ("maximize", "minimize")


class TournamentStateError(ValueError):
    """Raised when an operation does not match the tournament's pending state."""


def tournament_dir(runtime_root: Path, run_id: str) -> Path:
    return Path(runtime_root).expanduser().resolve() / "tournament" / run_id


def state_path(runtime_root: Path, run_id: str) -> Path:
    return tournament_dir(runtime_root, run_id) / "state.json"


def save_tournament_state(state: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(tmp_path, path)


def load_tournament_state(path: Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object in {path}")
    return payload


def refresh_pending(state: dict[str, Any]) -> None:
    """Derive and store pending_action from the current state (deterministic)."""
    if state["stop"]["stopped"]:
        state["pending_action"] = (
            None if state.get("report_written") else {"type": "finalize"}
        )
        return
    if not state["arms"]:
        state["pending_action"] = {
            "type": "need_direction_proposals",
            "k": state["config"]["k"],
        }
        return
    eligible = [
        arm for arm in state["arms"]
        if arm["status"] == "active" and arm["rounds_used"] < arm["rounds_allocated"]
    ]
    if eligible:
        # Round-robin: least-run arm first so an early stop leaves a fair
        # snapshot across directions; arm_id breaks ties deterministically.
        arm = min(eligible, key=lambda a: (a["rounds_used"], a["arm_id"]))
        if arm.get("queued_proposal") is not None:
            state["pending_action"] = {
                "type": "run_round",
                "arm_id": arm["arm_id"],
                "round_id": f"{arm['arm_id']}-r{arm['rounds_used'] + 1}",
            }
        else:
            state["pending_action"] = {
                "type": "need_round_proposal",
                "arm_id": arm["arm_id"],
            }
        return
    state["pending_action"] = {"type": "stage_end"}


def _validate_config(config: dict[str, Any]) -> None:
    if not isinstance(config.get("k"), int) or config["k"] < 2:
        raise ValueError("config.k must be >= 2")
    if not isinstance(config.get("initial_rounds_per_arm"), int) or (
        config["initial_rounds_per_arm"] < 1
    ):
        raise ValueError("config.initial_rounds_per_arm must be >= 1")
    if config.get("halving") != 2:
        raise ValueError("v1 supports halving=2 only")
    if not _is_plain_number(config.get("epsilon")) or config["epsilon"] <= 0:
        raise ValueError("config.epsilon must be a number > 0")
    if config.get("direction") not in _DIRECTIONS:
        raise ValueError("config.direction must be 'maximize' or 'minimize'")
    budgets = config.get("budgets")
    if not isinstance(budgets, dict):
        raise ValueError("config.budgets must be an object")
    for key in ("max_total_rounds", "max_wall_seconds"):
        if not _is_plain_number(budgets.get(key)) or budgets[key] <= 0:
            raise ValueError(f"config.budgets.{key} must be a number > 0")
    target_value = budgets.get("target_value")
    if target_value is not None and not _is_plain_number(target_value):
        raise ValueError("config.budgets.target_value must be a number or null")


def start_tournament(
    *,
    runtime_root: Path,
    run_id: str,
    target_id: str,
    config: dict[str, Any],
    baseline: dict[str, Any],
    target: dict[str, Any],
    now_fn: Callable[[], float] = time.time,
) -> dict[str, Any]:
    """Create a new tournament run; fails if the run already exists."""
    if not run_id or not isinstance(run_id, str):
        raise ValueError("run_id must be a non-empty string")
    _validate_config(config)
    if not _is_plain_number(baseline.get("value")):
        raise ValueError("baseline.value must be a number")
    artifact = Path(str(baseline.get("artifact", ""))).expanduser()
    if not artifact.is_file():
        raise FileNotFoundError(f"baseline artifact not found: {artifact}")
    if not isinstance(target, dict) or not target.get("kind"):
        raise ValueError("target.kind is required")
    path = state_path(runtime_root, run_id)
    if path.exists():
        raise FileExistsError(
            f"{path} already exists; use status/step to resume, or pick a new run_id"
        )
    state: dict[str, Any] = {
        "schema_version": TOURNAMENT_SCHEMA_VERSION,
        "run_id": run_id,
        "target_id": target_id,
        "config": config,
        "target": target,
        "baseline": {"value": float(baseline["value"]), "artifact": str(artifact)},
        "arms": [],
        "stage": {"index": 0, "rounds_per_arm": config["initial_rounds_per_arm"]},
        "ledger": {
            "total_rounds_used": 0,
            "wall_seconds_used": 0.0,
            "llm_cost_estimate": None,
        },
        "created_at": float(now_fn()),
        "stop": {"stopped": False, "reason": None},
        "pending_action": None,
        "report_written": False,
    }
    refresh_pending(state)
    save_tournament_state(state, path)
    return state
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_search.py -q`
Expected: all PASS.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check lib/tournament_search.py tests/unit/test_tournament_search.py
git add lib/tournament_search.py tests/unit/test_tournament_search.py
git commit -m "feat: tournament state model, atomic persistence, start_tournament

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: `submit_directions`

**Files:**
- Modify: `lib/tournament_search.py`
- Test: `tests/unit/test_tournament_search.py`

**Interfaces:**
- Consumes: Task 1's `load_tournament_state`, `save_tournament_state`, `state_path`, `tournament_dir`, `refresh_pending`, `TournamentStateError`.
- Produces: `submit_directions(*, runtime_root: Path, run_id: str, directions: list[dict]) -> dict`. Each direction: `{"arm_id": str, "hypothesis": str, "first_proposal": dict}`. Arm dict shape (relied on by every later task):
  `{"arm_id", "hypothesis", "status": "active", "workspace": str, "best": {"value": float, "round_id": None, "artifact": str}, "rounds_used": 0, "rounds_allocated": int, "invalid_proposal_streak": 0, "consecutive_failures": 0, "queued_proposal": dict|None, "failure_reason": None, "history": []}`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_tournament_search.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_search.py -q -k submit_directions`
Expected: FAIL with `AttributeError: ... has no attribute 'submit_directions'`.

- [ ] **Step 3: Write the implementation**

Append to `lib/tournament_search.py`:

```python
def submit_directions(
    *,
    runtime_root: Path,
    run_id: str,
    directions: list[dict[str, Any]],
) -> dict[str, Any]:
    """Formal validation + arm creation; semantic distinctness is the LLM's job."""
    path = state_path(runtime_root, run_id)
    state = load_tournament_state(path)
    pending = state.get("pending_action") or {}
    if pending.get("type") != "need_direction_proposals":
        raise TournamentStateError(
            "tournament is not waiting for need_direction_proposals"
        )
    k = state["config"]["k"]
    if not isinstance(directions, list) or len(directions) != k:
        raise ValueError(f"expected {k} directions, got {len(directions or [])}")
    arm_ids = [str(d.get("arm_id") or "") for d in directions]
    hypotheses = [str(d.get("hypothesis") or "").strip() for d in directions]
    if any(not arm_id for arm_id in arm_ids):
        raise ValueError("every direction needs a non-empty arm_id")
    if len(set(arm_ids)) != len(arm_ids):
        raise ValueError("arm_id values must be unique")
    if any(not hypothesis for hypothesis in hypotheses):
        raise ValueError("every direction needs a non-empty hypothesis")
    if len(set(hypotheses)) != len(hypotheses):
        raise ValueError("hypothesis values must be unique")
    for direction in directions:
        proposal = direction.get("first_proposal")
        if not isinstance(proposal, dict) or not proposal:
            raise ValueError("every direction needs a non-empty first_proposal object")

    run_dir = tournament_dir(runtime_root, run_id)
    initial_rounds = state["config"]["initial_rounds_per_arm"]
    for direction in directions:
        arm_id = str(direction["arm_id"])
        workspace = run_dir / "arms" / arm_id
        workspace.mkdir(parents=True, exist_ok=True)
        state["arms"].append({
            "arm_id": arm_id,
            "hypothesis": str(direction["hypothesis"]).strip(),
            "status": "active",
            "workspace": str(workspace),
            "best": {
                "value": state["baseline"]["value"],
                "round_id": None,
                "artifact": state["baseline"]["artifact"],
            },
            "rounds_used": 0,
            "rounds_allocated": initial_rounds,
            "invalid_proposal_streak": 0,
            "consecutive_failures": 0,
            "queued_proposal": dict(direction["first_proposal"]),
            "failure_reason": None,
            "history": [],
        })
    refresh_pending(state)
    save_tournament_state(state, path)
    return state
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_search.py -q`
Expected: all PASS.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check lib/tournament_search.py tests/unit/test_tournament_search.py
git add lib/tournament_search.py tests/unit/test_tournament_search.py
git commit -m "feat: tournament submit_directions with formal validation

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Pure decision functions (delta, ranking, stage-end pruning)

**Files:**
- Modify: `lib/tournament_search.py`
- Test: `tests/unit/test_tournament_search.py`

**Interfaces:**
- Produces:
  - `signed_delta(value: float, best: float, direction: str) -> float` — positive means "better", for both directions.
  - `classify_delta(delta: float, epsilon: float) -> str` — `"accept"` iff `delta >= epsilon`; `"near_tie"` iff `0 < delta < epsilon`; else `"reject"`.
  - `rank_active_arms(state: dict) -> list[str]` — active arm_ids best-first (direction-aware), ties broken by arm_id.
  - `apply_stage_end(state: dict) -> None` — prunes bottom arms to `max(1, ceil(active/2))`, increments `stage.index`, doubles `stage.rounds_per_arm`, adds the new per-stage rounds to each survivor's `rounds_allocated`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_tournament_search.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_search.py -q -k "signed_delta or classify or rank_active or stage_end"`
Expected: FAIL with `AttributeError`.

- [ ] **Step 3: Write the implementation**

Append to `lib/tournament_search.py`:

```python
def signed_delta(value: float, best: float, direction: str) -> float:
    """Positive result always means `value` is better than `best`."""
    return value - best if direction == "maximize" else best - value


def classify_delta(delta: float, epsilon: float) -> str:
    if delta >= epsilon:
        return "accept"
    if 0 < delta < epsilon:
        return "near_tie"
    return "reject"


def rank_active_arms(state: dict[str, Any]) -> list[str]:
    direction = state["config"]["direction"]
    active = [arm for arm in state["arms"] if arm["status"] == "active"]
    reverse = direction == "maximize"
    ranked = sorted(
        active,
        key=lambda arm: (
            -arm["best"]["value"] if reverse else arm["best"]["value"],
            arm["arm_id"],
        ),
    )
    return [arm["arm_id"] for arm in ranked]


def apply_stage_end(state: dict[str, Any]) -> None:
    """Prune bottom arms to ceil(active/2) (min 1); double next stage's rounds."""
    ranked = rank_active_arms(state)
    keep = max(1, math.ceil(len(ranked) / 2))
    pruned_ids = set(ranked[keep:])
    for arm in state["arms"]:
        if arm["arm_id"] in pruned_ids:
            arm["status"] = "pruned"
    state["stage"]["index"] += 1
    state["stage"]["rounds_per_arm"] *= 2
    for arm in state["arms"]:
        if arm["status"] == "active":
            arm["rounds_allocated"] += state["stage"]["rounds_per_arm"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_search.py -q`
Expected: all PASS.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check lib/tournament_search.py tests/unit/test_tournament_search.py
git add lib/tournament_search.py tests/unit/test_tournament_search.py
git commit -m "feat: tournament pure decision functions (delta, rank, prune)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: `check_stop` with documented precedence

**Files:**
- Modify: `lib/tournament_search.py`
- Test: `tests/unit/test_tournament_search.py`

**Interfaces:**
- Produces: `check_stop(state: dict, *, now: float) -> str | None` — returns the stop reason or None; does NOT mutate state. Reasons (exact strings, precedence order): `"target_reached"`, `"all_arms_failed"`, `"max_total_rounds"`, `"max_wall_seconds"`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_tournament_search.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_search.py -q -k check_stop`
Expected: FAIL with `AttributeError`.

- [ ] **Step 3: Write the implementation**

Append to `lib/tournament_search.py`:

```python
def check_stop(state: dict[str, Any], *, now: float) -> str | None:
    """Return the first triggered stop reason, in documented precedence order:
    target_reached > all_arms_failed > max_total_rounds > max_wall_seconds.
    LLM cost is a ledger-only estimate and never triggers a stop here."""
    config = state["config"]
    budgets = config["budgets"]
    direction = config["direction"]
    target_value = budgets.get("target_value")
    if target_value is not None:
        for arm in state["arms"]:
            if arm["status"] != "active":
                continue
            if signed_delta(arm["best"]["value"], float(target_value), direction) >= 0:
                return "target_reached"
    if state["arms"] and not any(
        arm["status"] == "active" for arm in state["arms"]
    ):
        return "all_arms_failed"
    if state["ledger"]["total_rounds_used"] >= budgets["max_total_rounds"]:
        return "max_total_rounds"
    if now - state["created_at"] >= budgets["max_wall_seconds"]:
        return "max_wall_seconds"
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_search.py -q`
Expected: all PASS.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check lib/tournament_search.py tests/unit/test_tournament_search.py
git add lib/tournament_search.py tests/unit/test_tournament_search.py
git commit -m "feat: tournament stop conditions with documented precedence

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: Executor protocol and `step()` round execution

**Files:**
- Modify: `lib/tournament_search.py`
- Test: `tests/unit/test_tournament_search.py`

**Interfaces:**
- Produces:
  - `class InvalidProposalError(ValueError)` and `class ExecutorRoundError(RuntimeError)`.
  - Executor protocol (duck-typed; documented in module): `validate_proposal(arm: dict, proposal: dict) -> None` (raises `InvalidProposalError`) and `run_one_round(arm: dict, proposal: dict, round_dir: Path) -> dict` returning `{"value": float, "artifacts": str | None}` (raises `ExecutorRoundError` on a failed run).
  - `step(*, runtime_root: Path, run_id: str, executor: Any | None = None, now_fn: Callable[[], float] = time.time) -> dict` — executes exactly one pending deterministic action (`run_round` in this task; `stage_end`/`finalize` wired in Task 6). When `executor is None`, it is built from `state["target"]` via `build_arm_executor` (factory lands in Task 7; until then tests always inject).
  - Round record shape appended to `arm["history"]`: `{"round_id", "proposal", "value": float|None, "repeat_value": float|None, "effective_value": float|None, "decision": "accepted"|"rejected"|"failed", "artifacts": str|None, "error": str|None, "completed_at": float}`.
  - Round artifacts live in `<run_dir>/arms/<arm_id>/rounds/<round_id>/`; the engine writes `round-result.json` there on completion (its absence next to an existing dir marks an interrupted round).

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_tournament_search.py`. `_ScriptedExecutor` is the shared fake used by Tasks 5-7:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_search.py -q -k step`
Expected: FAIL with `AttributeError` (`InvalidProposalError` / `step` missing). Note `test_step_failed_round_counts...` also needs Task 6's `submit_proposal`; it will keep failing until Task 6 — mark it `@pytest.mark.xfail(reason="submit_proposal lands in the next task", strict=True)` for this commit and remove the marker in Task 6.

- [ ] **Step 3: Write the implementation**

Append to `lib/tournament_search.py`:

```python
class InvalidProposalError(ValueError):
    """Proposal failed executor preflight; the round was NOT consumed."""


class ExecutorRoundError(RuntimeError):
    """The experiment ran and failed; the round IS consumed."""


def _find_arm(state: dict[str, Any], arm_id: str) -> dict[str, Any]:
    for arm in state["arms"]:
        if arm["arm_id"] == arm_id:
            return arm
    raise TournamentStateError(f"unknown arm_id {arm_id!r}")


def _record_round(
    state: dict[str, Any],
    arm: dict[str, Any],
    record: dict[str, Any],
) -> None:
    arm["history"].append(record)
    arm["rounds_used"] += 1
    arm["queued_proposal"] = None
    state["ledger"]["total_rounds_used"] += 1


def _fail_round(
    state: dict[str, Any],
    arm: dict[str, Any],
    *,
    round_id: str,
    proposal: dict[str, Any],
    error: str,
    now: float,
) -> None:
    _record_round(state, arm, {
        "round_id": round_id, "proposal": proposal, "value": None,
        "repeat_value": None, "effective_value": None, "decision": "failed",
        "artifacts": None, "error": error, "completed_at": now,
    })
    arm["consecutive_failures"] += 1
    if arm["consecutive_failures"] >= MAX_CONSECUTIVE_FAILURES:
        arm["status"] = "failed"
        arm["failure_reason"] = "consecutive_round_failures"


def _execute_round(
    state: dict[str, Any],
    arm: dict[str, Any],
    round_id: str,
    executor: Any,
    runtime_root: Path,
    now: float,
) -> None:
    proposal = arm["queued_proposal"]
    round_dir = (
        tournament_dir(runtime_root, state["run_id"])
        / "arms" / arm["arm_id"] / "rounds" / round_id
    )
    result_marker = round_dir / "round-result.json"
    if round_dir.exists() and not result_marker.exists():
        _fail_round(state, arm, round_id=round_id, proposal=proposal,
                    error="interrupted", now=now)
        return
    round_dir.mkdir(parents=True, exist_ok=True)
    direction = state["config"]["direction"]
    epsilon = state["config"]["epsilon"]
    try:
        outcome = executor.run_one_round(arm, proposal, round_dir)
    except ExecutorRoundError as error:
        _fail_round(state, arm, round_id=round_id, proposal=proposal,
                    error=str(error), now=now)
        return
    value = float(outcome["value"])
    delta = signed_delta(value, arm["best"]["value"], direction)
    verdict = classify_delta(delta, epsilon)
    repeat_value: float | None = None
    effective = value
    if verdict == "near_tie":
        repeat_dir = round_dir / "repeat"
        repeat_dir.mkdir(exist_ok=True)
        try:
            repeat_outcome = executor.run_one_round(arm, proposal, repeat_dir)
            repeat_value = float(repeat_outcome["value"])
            effective = (value + repeat_value) / 2
            repeat_delta = signed_delta(effective, arm["best"]["value"], direction)
            verdict = "accept" if repeat_delta >= epsilon else "reject"
        except ExecutorRoundError:
            verdict = "reject"
    decision = "accepted" if verdict == "accept" else "rejected"
    record = {
        "round_id": round_id, "proposal": proposal, "value": value,
        "repeat_value": repeat_value, "effective_value": effective,
        "decision": decision, "artifacts": outcome.get("artifacts"),
        "error": None, "completed_at": now,
    }
    _record_round(state, arm, record)
    if decision == "accepted":
        arm["consecutive_failures"] = 0
        arm["best"] = {
            "value": effective,
            "round_id": round_id,
            "artifact": outcome.get("artifacts") or arm["best"]["artifact"],
        }
    result_marker.write_text(
        json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def step(
    *,
    runtime_root: Path,
    run_id: str,
    executor: Any | None = None,
    now_fn: Callable[[], float] = time.time,
) -> dict[str, Any]:
    """Execute exactly one pending deterministic action and persist the state."""
    path = state_path(runtime_root, run_id)
    state = load_tournament_state(path)
    pending = state.get("pending_action")
    if pending is None:
        raise TournamentStateError("tournament is complete; nothing to step")
    if pending["type"] in ("need_direction_proposals", "need_round_proposal"):
        raise TournamentStateError(
            f"pending action {pending['type']!r} requires a submission, not step"
        )
    if executor is None:
        executor = build_arm_executor(state["target"])
    now = float(now_fn())
    if pending["type"] == "run_round":
        arm = _find_arm(state, pending["arm_id"])
        _execute_round(state, arm, pending["round_id"], executor,
                       Path(runtime_root), now)
    elif pending["type"] == "stage_end":
        apply_stage_end(state)
    elif pending["type"] == "finalize":
        _write_report(state, Path(runtime_root))
    else:  # pragma: no cover - defensive
        raise TournamentStateError(f"unknown pending action {pending['type']!r}")
    if not state["stop"]["stopped"]:
        reason = check_stop(state, now=now)
        if reason is not None:
            state["stop"] = {"stopped": True, "reason": reason}
    state["ledger"]["wall_seconds_used"] = round(now - state["created_at"], 3)
    refresh_pending(state)
    save_tournament_state(state, path)
    return state
```

Also add this placeholder at the end of the file so `step` imports cleanly until Tasks 6-7 replace them (`_write_report` is implemented in Task 6, `build_arm_executor` in Task 7):

```python
def _write_report(state: dict[str, Any], runtime_root: Path) -> None:
    raise NotImplementedError("implemented in the finalize task")


def build_arm_executor(target: dict[str, Any]) -> Any:
    raise NotImplementedError("implemented in the executor-factory task")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_search.py -q`
Expected: all PASS except the one `xfail` (submit_proposal test) which must report XFAIL.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check lib/tournament_search.py tests/unit/test_tournament_search.py
git add lib/tournament_search.py tests/unit/test_tournament_search.py
git commit -m "feat: tournament step() round execution with tie-break and crash recovery

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: `submit_proposal`, invalid-proposal streak, finalize/report

**Files:**
- Modify: `lib/tournament_search.py`
- Test: `tests/unit/test_tournament_search.py`

**Interfaces:**
- Consumes: Task 5's `InvalidProposalError`, `_find_arm`, `refresh_pending`, `step` pending flow.
- Produces:
  - `submit_proposal(*, runtime_root: Path, run_id: str, arm_id: str, proposal: dict, executor: Any | None = None) -> dict` — validates via `executor.validate_proposal`; on invalid, persists the incremented streak then re-raises `InvalidProposalError`; 3 consecutive invalids fail the arm (`failure_reason="invalid_proposals"`).
  - `build_tournament_report(state: dict) -> dict` with keys: `schema_version`, `run_id`, `target_id`, `stop`, `baseline`, `config`, `ledger`, `winner` (`{"arm_id", "hypothesis", "best", "improved": bool, "accepted_chain": [round records]}`), `arms` (per-arm `{"arm_id", "status", "failure_reason", "hypothesis", "best", "rounds_used", "rounds_allocated", "delta_vs_baseline"}`).
  - Real `_write_report(state, runtime_root)` replacing the Task 5 placeholder: writes `report.json` next to `state.json`, sets `state["report_written"] = True` and `state["report_path"]`.

- [ ] **Step 1: Write the failing tests**

Remove the `xfail` marker from `test_step_failed_round_counts_and_two_failures_kill_arm`, then append:

```python
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
    # k=2, 1 round each used, stage end prunes a2; budgets not hit yet
    assert state["pending_action"]["type"] in ("run_round", "need_round_proposal",
                                               "finalize")
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_search.py -q -k "submit_proposal or finalize"`
Expected: FAIL with `AttributeError: ... 'submit_proposal'` / `NotImplementedError` from the `_write_report` placeholder.

- [ ] **Step 3: Write the implementation**

Replace the Task 5 `_write_report` placeholder and add `submit_proposal` / `build_tournament_report`:

```python
def submit_proposal(
    *,
    runtime_root: Path,
    run_id: str,
    arm_id: str,
    proposal: dict[str, Any],
    executor: Any | None = None,
) -> dict[str, Any]:
    path = state_path(runtime_root, run_id)
    state = load_tournament_state(path)
    pending = state.get("pending_action") or {}
    if pending.get("type") != "need_round_proposal" or pending.get("arm_id") != arm_id:
        raise TournamentStateError(
            f"tournament is not waiting for need_round_proposal on arm {arm_id!r}"
        )
    if executor is None:
        executor = build_arm_executor(state["target"])
    arm = _find_arm(state, arm_id)
    if not isinstance(proposal, dict) or not proposal:
        raise ValueError("proposal must be a non-empty object")
    try:
        executor.validate_proposal(arm, proposal)
    except InvalidProposalError:
        arm["invalid_proposal_streak"] += 1
        if arm["invalid_proposal_streak"] >= MAX_INVALID_PROPOSALS:
            arm["status"] = "failed"
            arm["failure_reason"] = "invalid_proposals"
        if not state["stop"]["stopped"]:
            reason = check_stop(state, now=time.time())
            if reason is not None:
                state["stop"] = {"stopped": True, "reason": reason}
        refresh_pending(state)
        save_tournament_state(state, path)
        raise
    arm["invalid_proposal_streak"] = 0
    arm["queued_proposal"] = dict(proposal)
    refresh_pending(state)
    save_tournament_state(state, path)
    return state


def build_tournament_report(state: dict[str, Any]) -> dict[str, Any]:
    direction = state["config"]["direction"]
    baseline_value = state["baseline"]["value"]
    rows = []
    for arm in state["arms"]:
        rows.append({
            "arm_id": arm["arm_id"],
            "status": arm["status"],
            "failure_reason": arm["failure_reason"],
            "hypothesis": arm["hypothesis"],
            "best": arm["best"],
            "rounds_used": arm["rounds_used"],
            "rounds_allocated": arm["rounds_allocated"],
            "delta_vs_baseline": signed_delta(
                arm["best"]["value"], baseline_value, direction
            ),
        })
    winner = None
    if state["arms"]:
        best_arm = max(
            state["arms"],
            key=lambda arm: (
                signed_delta(arm["best"]["value"], baseline_value, direction),
                arm["arm_id"],
            ),
        )
        winner = {
            "arm_id": best_arm["arm_id"],
            "hypothesis": best_arm["hypothesis"],
            "best": best_arm["best"],
            "improved": signed_delta(
                best_arm["best"]["value"], baseline_value, direction
            ) > 0,
            "accepted_chain": [
                record for record in best_arm["history"]
                if record["decision"] == "accepted"
            ],
        }
    return {
        "schema_version": TOURNAMENT_SCHEMA_VERSION,
        "run_id": state["run_id"],
        "target_id": state["target_id"],
        "stop": state["stop"],
        "baseline": state["baseline"],
        "config": state["config"],
        "ledger": state["ledger"],
        "winner": winner,
        "arms": rows,
    }


def _write_report(state: dict[str, Any], runtime_root: Path) -> None:
    report = build_tournament_report(state)
    report_path = tournament_dir(runtime_root, state["run_id"]) / "report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    state["report_written"] = True
    state["report_path"] = str(report_path)
```

(Delete the old `_write_report` placeholder; keep the `build_arm_executor` placeholder until Task 7.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_search.py -q`
Expected: all PASS (no xfail remaining).

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check lib/tournament_search.py tests/unit/test_tournament_search.py
git add lib/tournament_search.py tests/unit/test_tournament_search.py
git commit -m "feat: tournament submit_proposal, invalid streak, finalize report

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: `SyntheticArmExecutor`, executor factory, end-to-end integration

**Files:**
- Modify: `lib/tournament_search.py`
- Test: `tests/unit/test_tournament_search.py`

**Interfaces:**
- Produces:
  - `class SyntheticArmExecutor` — `__init__(self, *, baseline_value: float, weights: dict[str, float], failure_params: list[str] | None = None)`; `validate_proposal` raises `InvalidProposalError` if `proposal["params"]` is missing/empty or has keys outside `weights`; `run_one_round` returns `{"value": baseline_value + Σ weights[k]*float(v), "artifacts": <round_dir>/synthetic-eval.json}`, raising `ExecutorRoundError` if any param is in `failure_params`. Fully deterministic.
  - `build_arm_executor(target: dict) -> Any` replacing the placeholder — `kind="synthetic"` → `SyntheticArmExecutor(**fields)`; `kind="fasttext"` → Task 8's `FastTextArmExecutor`; unknown kind → `ValueError`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_tournament_search.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_search.py -q -k "synthetic or factory or end_to_end"`
Expected: FAIL with `AttributeError: ... 'SyntheticArmExecutor'` / `NotImplementedError`.

- [ ] **Step 3: Write the implementation**

Replace the Task 5 `build_arm_executor` placeholder with:

```python
class SyntheticArmExecutor:
    """Deterministic executor: value = baseline + sum(weights[param] * value).

    Used by tests, MCP behavioral tests, and offline demos. `failure_params`
    lets scripts exercise the failed-round path deterministically.
    """

    def __init__(
        self,
        *,
        baseline_value: float,
        weights: dict[str, float],
        failure_params: list[str] | None = None,
    ) -> None:
        self.baseline_value = float(baseline_value)
        self.weights = {str(k): float(v) for k, v in weights.items()}
        self.failure_params = set(failure_params or [])

    def validate_proposal(self, arm: dict[str, Any], proposal: dict[str, Any]) -> None:
        params = proposal.get("params")
        if not isinstance(params, dict) or not params:
            raise InvalidProposalError("proposal.params must be a non-empty object")
        unknown = set(params) - set(self.weights) - self.failure_params
        if unknown:
            raise InvalidProposalError(
                f"unknown synthetic params: {sorted(unknown)}"
            )

    def run_one_round(
        self, arm: dict[str, Any], proposal: dict[str, Any], round_dir: Path
    ) -> dict[str, Any]:
        params = proposal.get("params") or {}
        if self.failure_params & set(params):
            raise ExecutorRoundError("synthetic scripted failure")
        value = self.baseline_value + sum(
            self.weights.get(key, 0.0) * float(val) for key, val in params.items()
        )
        artifact = Path(round_dir) / "synthetic-eval.json"
        artifact.write_text(
            json.dumps({"value": value, "params": params}, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return {"value": value, "artifacts": str(artifact)}


def build_arm_executor(target: dict[str, Any]) -> Any:
    kind = target.get("kind")
    if kind == "synthetic":
        return SyntheticArmExecutor(
            baseline_value=target["baseline_value"],
            weights=target["weights"],
            failure_params=target.get("failure_params"),
        )
    if kind == "fasttext":
        return FastTextArmExecutor(
            target_spec_path=Path(target["target_spec"]),
            train_csv=Path(target["train_csv"]),
            test_csv=Path(target["test_csv"]),
            fasttext_binary=Path(target["fasttext_binary"]),
            max_train_seconds=int(target.get("max_train_seconds", 300)),
        )
    raise ValueError(f"unknown target kind {kind!r}")
```

(`FastTextArmExecutor` does not exist yet; to keep this commit green, add after `SyntheticArmExecutor`:)

```python
class FastTextArmExecutor:  # implemented in the next task
    def __init__(self, **kwargs: Any) -> None:
        raise NotImplementedError("implemented in the fastText executor task")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_search.py -q`
Expected: all PASS.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check lib/tournament_search.py tests/unit/test_tournament_search.py
git add lib/tournament_search.py tests/unit/test_tournament_search.py
git commit -m "feat: synthetic executor, factory, tournament end-to-end integration test

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: `FastTextArmExecutor`

**Files:**
- Modify: `lib/tournament_search.py`
- Test: `tests/unit/test_tournament_search.py`

**Interfaces:**
- Consumes (verified signatures):
  - `lib.full_reproduction_harness.run_fasttext_patch_round(config: FullReproductionRunConfig, *, train_csv: Path, test_csv: Path, fasttext_binary: Path, baseline_report: Path, proposal: dict) -> dict` returning at least `{"status": "completed", "p_at_1": float, "improvement_report": str}`. The improvement report on disk contains `{"metric": {"p_at_1": ...}}`, which `_baseline_report_p_at_1` (harness.py:1768) accepts — so an accepted round's report is directly usable as the next round's `baseline_report`. No format shim needed.
  - `lib.full_reproduction_harness.FullReproductionRunConfig(target_spec_path: Path, output_dir: Path, max_train_seconds: int = 300)`.
  - `lib.full_reproduction_harness._normalize_fasttext_patch_proposal(proposal) -> dict`, raising `ValueError` on any allowlist/shape violation (harness.py:1777).
- Produces: `class FastTextArmExecutor` — `__init__(self, *, target_spec_path: Path, train_csv: Path, test_csv: Path, fasttext_binary: Path, max_train_seconds: int = 300, patch_round_fn=None)` (injectable for offline tests; defaults to the real `run_fasttext_patch_round`). `validate_proposal` maps `ValueError` → `InvalidProposalError`. `run_one_round` uses `arm["best"]["artifact"]` as `baseline_report` (per-arm chains) and `round_dir` as `output_dir`; returns `{"value": result["p_at_1"], "artifacts": result["improvement_report"]}`; maps any `Exception` from the harness to `ExecutorRoundError`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_tournament_search.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_search.py -q -k fasttext_executor`
Expected: FAIL with `NotImplementedError` from the Task 7 stub.

- [ ] **Step 3: Write the implementation**

Replace the `FastTextArmExecutor` stub with:

```python
class FastTextArmExecutor:
    """Runs one guarded fastText AG News patch round per tournament round.

    Chains are per-arm: `arm["best"]["artifact"]` (initially the global
    baseline report, then each accepted round's improvement report -- both
    carry metric.p_at_1) is passed as `baseline_report`. fastText retrains
    from explicit args every round, so reject needs no workspace rollback;
    the engine's best-pointer is the whole chain state. A future train.py
    executor must reset its workspace to the arm best inside run_one_round.
    """

    def __init__(
        self,
        *,
        target_spec_path: Path,
        train_csv: Path,
        test_csv: Path,
        fasttext_binary: Path,
        max_train_seconds: int = 300,
        patch_round_fn: Callable[..., dict[str, Any]] | None = None,
    ) -> None:
        self.target_spec_path = Path(target_spec_path)
        self.train_csv = Path(train_csv)
        self.test_csv = Path(test_csv)
        self.fasttext_binary = Path(fasttext_binary)
        self.max_train_seconds = int(max_train_seconds)
        if patch_round_fn is None:
            from lib.full_reproduction_harness import run_fasttext_patch_round
            patch_round_fn = run_fasttext_patch_round
        self._patch_round_fn = patch_round_fn

    def validate_proposal(self, arm: dict[str, Any], proposal: dict[str, Any]) -> None:
        from lib.full_reproduction_harness import _normalize_fasttext_patch_proposal
        try:
            _normalize_fasttext_patch_proposal(proposal)
        except ValueError as error:
            raise InvalidProposalError(str(error)) from error

    def run_one_round(
        self, arm: dict[str, Any], proposal: dict[str, Any], round_dir: Path
    ) -> dict[str, Any]:
        from lib.full_reproduction_harness import FullReproductionRunConfig
        config = FullReproductionRunConfig(
            target_spec_path=self.target_spec_path,
            output_dir=Path(round_dir),
            max_train_seconds=self.max_train_seconds,
        )
        try:
            result = self._patch_round_fn(
                config,
                train_csv=self.train_csv,
                test_csv=self.test_csv,
                fasttext_binary=self.fasttext_binary,
                baseline_report=Path(arm["best"]["artifact"]),
                proposal=proposal,
            )
        except Exception as error:
            raise ExecutorRoundError(str(error)) from error
        return {
            "value": float(result["p_at_1"]),
            "artifacts": str(result["improvement_report"]),
        }
```

Manual real smoke (documented, NOT in CI — needs a local fastText binary; uses the mini dataset from `prepare_fasttext_mini_dataset`): run a 2-arm × 2-round tournament via the Task 10 CLI against `.demo_runs/tournament-smoke` and confirm `report.json` exists. Record the command in the final task's docs update.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_search.py -q`
Expected: all PASS.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check lib/tournament_search.py tests/unit/test_tournament_search.py
git add lib/tournament_search.py tests/unit/test_tournament_search.py
git commit -m "feat: fastText arm executor wrapping run_fasttext_patch_round

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 9: MCP tool `tournament`

**Files:**
- Modify: `lib/mcp_service.py` (four anchors below)
- Test: `tests/unit/test_mcp_service.py`

**Interfaces:**
- Consumes: every public function from Tasks 1-7 (`start_tournament`, `submit_directions`, `submit_proposal`, `step`, `build_tournament_report`, `load_tournament_state`, `state_path`, `TournamentStateError`, `InvalidProposalError`), plus existing `MCPToolError` and `_assert_path_allowed(path, field)` (lib/mcp_service.py, sandbox check used by execution tools).
- Produces: MCP tool name `"tournament"` with stages `start | status | submit_directions | submit_proposal | step | report`, registered in `REQUIRED_TOOLS`, `TOOL_CONTRACT_DESCRIPTIONS`, `tool_definitions()`, and `TOOL_HANDLERS`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_mcp_service.py`:

```python
def test_tournament_tool_runs_synthetic_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setenv("ML_RESEARCH_LOOP_ALLOWED_ROOTS", str(tmp_path))
    baseline_artifact = tmp_path / "baseline-report.json"
    baseline_artifact.write_text('{"metric": {"p_at_1": 0.9}}', encoding="utf-8")
    base = {"runtime_root": str(tmp_path), "run_id": "mcp-run"}
    started = mcp_service.tournament_tool({
        "stage": "start", **base, "target_id": "demo",
        "config": {"k": 2, "initial_rounds_per_arm": 1, "halving": 2,
                   "epsilon": 0.001, "metric": "P@1", "direction": "maximize",
                   "budgets": {"max_total_rounds": 6, "max_wall_seconds": 3600,
                               "target_value": 0.92}},
        "baseline": {"value": 0.9, "artifact": str(baseline_artifact)},
        "target": {"kind": "synthetic", "baseline_value": 0.9,
                   "weights": {"a": 0.01, "b": 0.001}},
    })
    assert started["pending_action"] == {"type": "need_direction_proposals", "k": 2}
    mcp_service.tournament_tool({
        "stage": "submit_directions", **base,
        "directions": [
            {"arm_id": "a1", "hypothesis": "push a",
             "first_proposal": {"params": {"a": 1}}},
            {"arm_id": "a2", "hypothesis": "push b",
             "first_proposal": {"params": {"b": 1}}},
        ],
    })
    for _ in range(2):
        mcp_service.tournament_tool({"stage": "step", **base})
    status = mcp_service.tournament_tool({"stage": "status", **base})
    assert status["pending_action"] == {"type": "stage_end"}
    assert status["ledger"]["total_rounds_used"] == 2
    mcp_service.tournament_tool({"stage": "step", **base})   # stage_end
    status = mcp_service.tournament_tool({"stage": "status", **base})
    assert status["pending_action"] == {"type": "need_round_proposal",
                                        "arm_id": "a1"}
    mcp_service.tournament_tool({
        "stage": "submit_proposal", **base,
        "arm_id": "a1", "proposal": {"params": {"a": 2}},
    })
    mcp_service.tournament_tool({"stage": "step", **base})   # hits target 0.92
    mcp_service.tournament_tool({"stage": "step", **base})   # finalize
    report = mcp_service.tournament_tool({"stage": "report", **base})
    assert report["winner"]["arm_id"] == "a1"
    assert report["stop"]["reason"] == "target_reached"


def test_tournament_tool_rejects_unknown_stage_and_outside_root(tmp_path, monkeypatch):
    monkeypatch.setenv("ML_RESEARCH_LOOP_ALLOWED_ROOTS", str(tmp_path))
    with pytest.raises(mcp_service.MCPToolError):
        mcp_service.tournament_tool({"stage": "nope",
                                     "runtime_root": str(tmp_path),
                                     "run_id": "x"})
    with pytest.raises(mcp_service.MCPToolError):
        mcp_service.tournament_tool({"stage": "status",
                                     "runtime_root": "/somewhere/else",
                                     "run_id": "x"})


def test_tournament_tool_is_registered():
    tools_by_name = {tool["name"]: tool for tool in mcp_service.tool_definitions()}
    assert "tournament" in tools_by_name
    stages = set(
        tools_by_name["tournament"]["inputSchema"]["properties"]["stage"]["enum"]
    )
    assert stages == {"start", "status", "submit_directions",
                      "submit_proposal", "step", "report"}
    assert tools_by_name["tournament"]["inputSchema"]["required"] == ["stage"]
    assert "tournament" in mcp_service.REQUIRED_TOOLS
    assert "tournament" in mcp_service.TOOL_CONTRACT_DESCRIPTIONS
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_mcp_service.py -q -k tournament`
Expected: FAIL with `AttributeError: ... 'tournament_tool'`.

- [ ] **Step 3: Write the implementation**

Four edits to `lib/mcp_service.py`:

(a) Import block — add after the existing `from lib.memory_adapters import ...` line:

```python
from lib import tournament_search
```

(b) `REQUIRED_TOOLS` (list starting ~line 197) — add `"tournament",` immediately after the `"optimizer_gate",` entry.

(c) `TOOL_CONTRACT_DESCRIPTIONS` (dict starting ~line 293) — add:

```python
    "tournament": (
        "Direction tournament search engine; dispatches by `stage`. Stages -- "
        "start=Create a successive-halving tournament run from a config, baseline "
        "artifact, and target executor spec.; status=Read the state summary and "
        "pending_action.; submit_directions=Submit the K client-planned direction "
        "hypotheses with first proposals.; submit_proposal=Submit one client-planned "
        "proposal for the pending arm round.; step=Execute the one pending "
        "deterministic action (run round / stage-end pruning / finalize report).; "
        "report=Read the final winner, accepted chains, and budget ledger."
    ),
```

(d) `tool_definitions()` — add this entry next to the other stage-dispatched tools (after the `optimizer_gate` schema entry), reusing the exact `TOOL_CONTRACT_DESCRIPTIONS["tournament"]` text as `description`:

```python
        {
            "name": "tournament",
            "description": TOOL_CONTRACT_DESCRIPTIONS["tournament"],
            "inputSchema": {
                "type": "object",
                "properties": {
                    "stage": {"type": "string",
                              "enum": ["start", "status", "submit_directions",
                                       "submit_proposal", "step", "report"]},
                    "runtime_root": {"type": "string"},
                    "run_id": {"type": "string"},
                    "target_id": {"type": "string"},
                    "config": {"type": "object"},
                    "baseline": {"type": "object"},
                    "target": {"type": "object"},
                    "directions": {"type": "array", "items": {"type": "object"}},
                    "arm_id": {"type": "string"},
                    "proposal": {"type": "object"},
                },
                "required": ["stage"],
                "additionalProperties": False,
            },
        },
```

(e) Dispatcher — add next to `gate_policy_tool` (~line 11078):

```python
def tournament_tool(payload: dict[str, Any]) -> dict[str, Any]:
    """Direction tournament dispatcher; routes by `stage` to lib.tournament_search."""
    stage = payload.get("stage")
    valid_stages = ["start", "status", "submit_directions", "submit_proposal",
                    "step", "report"]
    if stage not in valid_stages:
        raise MCPToolError({
            "status": "failed",
            "error": f"unknown stage {stage!r} for tournament",
            "field": "stage",
            "valid_stages": valid_stages,
        })
    runtime_root_raw = payload.get("runtime_root")
    run_id = payload.get("run_id")
    if not runtime_root_raw or not run_id:
        raise MCPToolError({
            "status": "failed",
            "error": "runtime_root and run_id are required",
            "field": "runtime_root",
        })
    runtime_root = Path(runtime_root_raw).expanduser().resolve()
    _assert_path_allowed(runtime_root, "runtime_root")
    try:
        if stage == "start":
            return tournament_search.start_tournament(
                runtime_root=runtime_root,
                run_id=run_id,
                target_id=str(payload.get("target_id") or ""),
                config=payload.get("config") or {},
                baseline=payload.get("baseline") or {},
                target=payload.get("target") or {},
            )
        if stage == "submit_directions":
            return tournament_search.submit_directions(
                runtime_root=runtime_root,
                run_id=run_id,
                directions=payload.get("directions") or [],
            )
        if stage == "submit_proposal":
            return tournament_search.submit_proposal(
                runtime_root=runtime_root,
                run_id=run_id,
                arm_id=str(payload.get("arm_id") or ""),
                proposal=payload.get("proposal") or {},
            )
        if stage == "step":
            return tournament_search.step(
                runtime_root=runtime_root, run_id=run_id,
            )
        state = tournament_search.load_tournament_state(
            tournament_search.state_path(runtime_root, run_id)
        )
        if stage == "report":
            return tournament_search.build_tournament_report(state)
        return state  # stage == "status"
    except (tournament_search.TournamentStateError,
            tournament_search.InvalidProposalError,
            FileExistsError, FileNotFoundError, ValueError) as error:
        raise MCPToolError({
            "status": "failed",
            "error": str(error),
            "stage": stage,
        }) from error
```

(f) `TOOL_HANDLERS` (dict at ~line 11275) — add `"tournament": tournament_tool,` after the `"optimizer_gate": optimizer_gate_tool,` line.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/unit/test_mcp_service.py -q && .venv/bin/python -m pytest tests/unit/test_tournament_search.py -q`
Expected: all PASS (existing manifest/contract tests must stay green — additive change only).

- [ ] **Step 5: Run the real MCP acceptance check, lint, and commit**

```bash
.venv/bin/python scripts/mcp_client_acceptance.py --python "$(pwd)/.venv/bin/python3"
# Expected: status: passed, tool_count: 95, missing_required_tools: []
.venv/bin/ruff check lib/ scripts/ ml_intern/ codex_plugin/ tests/
git add lib/mcp_service.py tests/unit/test_mcp_service.py
git commit -m "feat: tournament MCP tool (stage-dispatched, additive)

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 10: CLI mirror, docs, and full gate

**Files:**
- Modify: `scripts/cli.py`, `README.md`, `docs/release-notes.md`
- Test: `tests/unit/test_cli.py`

**Interfaces:**
- Consumes: the same `lib.tournament_search` functions as Task 9 (CLI calls the lib directly, matching the repo's sibling-adapter convention), plus cli.py's existing `_print_json_payload(payload, compact=...)` helper.
- Produces: `ml-loop tournament <start|status|submit-directions|submit-proposal|step|report>` with `--runtime-root`, `--run-id`, and JSON file inputs `--config-file --baseline-file --target-file / --directions-file / --arm-id --proposal-file`, all printing the resulting payload as JSON.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_cli.py`. The file already does `from scripts.cli import build_parser, main` (line 10) and invokes `exit_code = main([...])` — use `main` directly:

```python
def test_tournament_cli_lifecycle(tmp_path, capsys):
    baseline_artifact = tmp_path / "baseline-report.json"
    baseline_artifact.write_text('{"metric": {"p_at_1": 0.9}}', encoding="utf-8")
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "k": 2, "initial_rounds_per_arm": 1, "halving": 2, "epsilon": 0.001,
        "metric": "P@1", "direction": "maximize",
        "budgets": {"max_total_rounds": 6, "max_wall_seconds": 3600,
                    "target_value": None},
    }), encoding="utf-8")
    baseline_file = tmp_path / "baseline.json"
    baseline_file.write_text(json.dumps(
        {"value": 0.9, "artifact": str(baseline_artifact)}), encoding="utf-8")
    target_file = tmp_path / "target.json"
    target_file.write_text(json.dumps(
        {"kind": "synthetic", "baseline_value": 0.9,
         "weights": {"a": 0.01, "b": 0.001}}), encoding="utf-8")
    directions_file = tmp_path / "directions.json"
    directions_file.write_text(json.dumps([
        {"arm_id": "a1", "hypothesis": "push a",
         "first_proposal": {"params": {"a": 1}}},
        {"arm_id": "a2", "hypothesis": "push b",
         "first_proposal": {"params": {"b": 1}}},
    ]), encoding="utf-8")
    base = ["tournament"]
    common = ["--runtime-root", str(tmp_path), "--run-id", "cli-run"]

    assert main(base + ["start", *common,
                            "--target-id", "demo",
                            "--config-file", str(config_file),
                            "--baseline-file", str(baseline_file),
                            "--target-file", str(target_file), "--json"]) == 0
    assert main(base + ["submit-directions", *common,
                            "--directions-file", str(directions_file),
                            "--json"]) == 0
    assert main(base + ["step", *common, "--json"]) == 0
    assert main(base + ["status", *common, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["ledger"]["total_rounds_used"] == 1
    assert payload["pending_action"]["type"] == "run_round"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_cli.py -q -k tournament`
Expected: FAIL with argparse error (unknown command `tournament`).

- [ ] **Step 3: Write the implementation**

In `scripts/cli.py`:

(a) Import: add `from lib import tournament_search` to the import block.

(b) Parser registration — add alongside the other top-level groups (near the `proposal` group registration):

```python
    tournament = subcommands.add_parser(
        "tournament",
        help="Direction tournament search (successive halving) engine",
    )
    tournament_commands = tournament.add_subparsers(dest="tournament_command",
                                                    required=True)

    def _tournament_common(parser):
        parser.add_argument("--runtime-root", type=Path, required=True)
        parser.add_argument("--run-id", required=True)
        parser.add_argument("--json", action="store_true")

    tournament_start = tournament_commands.add_parser("start")
    _tournament_common(tournament_start)
    tournament_start.add_argument("--target-id", required=True)
    tournament_start.add_argument("--config-file", type=Path, required=True)
    tournament_start.add_argument("--baseline-file", type=Path, required=True)
    tournament_start.add_argument("--target-file", type=Path, required=True)

    tournament_status = tournament_commands.add_parser("status")
    _tournament_common(tournament_status)

    tournament_directions = tournament_commands.add_parser("submit-directions")
    _tournament_common(tournament_directions)
    tournament_directions.add_argument("--directions-file", type=Path,
                                       required=True)

    tournament_proposal = tournament_commands.add_parser("submit-proposal")
    _tournament_common(tournament_proposal)
    tournament_proposal.add_argument("--arm-id", required=True)
    tournament_proposal.add_argument("--proposal-file", type=Path, required=True)

    tournament_step = tournament_commands.add_parser("step")
    _tournament_common(tournament_step)

    tournament_report = tournament_commands.add_parser("report")
    _tournament_common(tournament_report)
```

(c) Dispatch — add alongside the other `if args.command == ...` handlers:

```python
    if args.command == "tournament":
        def _read_json_file(path: Path):
            return json.loads(path.read_text(encoding="utf-8"))

        if args.tournament_command == "start":
            payload = tournament_search.start_tournament(
                runtime_root=args.runtime_root,
                run_id=args.run_id,
                target_id=args.target_id,
                config=_read_json_file(args.config_file),
                baseline=_read_json_file(args.baseline_file),
                target=_read_json_file(args.target_file),
            )
        elif args.tournament_command == "submit-directions":
            payload = tournament_search.submit_directions(
                runtime_root=args.runtime_root,
                run_id=args.run_id,
                directions=_read_json_file(args.directions_file),
            )
        elif args.tournament_command == "submit-proposal":
            payload = tournament_search.submit_proposal(
                runtime_root=args.runtime_root,
                run_id=args.run_id,
                arm_id=args.arm_id,
                proposal=_read_json_file(args.proposal_file),
            )
        elif args.tournament_command == "step":
            payload = tournament_search.step(
                runtime_root=args.runtime_root, run_id=args.run_id,
            )
        elif args.tournament_command == "report":
            state = tournament_search.load_tournament_state(
                tournament_search.state_path(args.runtime_root, args.run_id)
            )
            payload = tournament_search.build_tournament_report(state)
        else:  # status
            payload = tournament_search.load_tournament_state(
                tournament_search.state_path(args.runtime_root, args.run_id)
            )
        _print_json_payload(payload, compact=args.json)
        return 0
```

(d) Docs:
- `README.md` "Core MCP Tools" table — add the row:
  `| `tournament` | Stage-dispatched direction tournament search (`stage`: start, status, submit_directions, submit_proposal, step, report) — successive-halving over per-direction greedy chains with deterministic pruning, budgets, and stop conditions |`
- `docs/release-notes.md` — add under a new `## 2026-07-11 Additions` heading (before `## Migration Notes`):
  `- New additive MCP tool \`tournament\` and CLI \`ml-loop tournament\`: successive-halving direction tournament engine (spec: docs/superpowers/specs/2026-07-11-direction-tournament-search-design.md). Additive only; contract_version unchanged. Manual real-data smoke: run the fastText mini-slice tournament via \`ml-loop tournament\` against \`.demo_runs/tournament-smoke\` with a local fastText binary (not part of CI).`

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/unit/test_cli.py -q -k tournament && .venv/bin/python -m pytest tests/unit/test_mcp_delivery_docs.py -q`
Expected: all PASS.

- [ ] **Step 5: Full gate, lint, and commit**

```bash
.venv/bin/ruff check lib/ scripts/ ml_intern/ codex_plugin/ tests/
.venv/bin/python -m pytest tests/ -q
# Expected: all tests pass (878 pre-existing + the new tournament tests)
git add scripts/cli.py tests/unit/test_cli.py README.md docs/release-notes.md
git commit -m "feat: ml-loop tournament CLI mirror and tool docs

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Self-Review Notes (completed during plan writing)

- **Spec coverage:** state model + pending_action (Tasks 1-2), ε/near-tie/repeat rules (Task 5), prune/allocation math (Task 3), stop precedence incl. cost-is-ledger-only (Task 4), failure/invalid thresholds (Tasks 5-6), crash recovery + idempotency (Task 5), report (Task 6), synthetic + fastText executors and factory (Tasks 7-8), MCP tool with sandbox (Task 9), CLI + docs + manual smoke note (Task 10). The spec's "v1 out of scope" list has no tasks — correct.
- **Types:** arm/round-record/pending shapes defined once in Task 1/2/5 interface blocks and reused verbatim; executor return `{"value", "artifacts"}` consistent across Tasks 5/7/8.
- **Known intentional simplifications** (documented in code comments): near-tie repeats consume wall-clock but not a `total_rounds_used` unit; `submit_proposal` uses real `time.time()` for its stop-check (only `step` needs the injectable clock for tests).
