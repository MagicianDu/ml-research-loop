# Unattended Orchestration (Sub-project 2) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the unattended-orchestration driver layer specified in `docs/superpowers/specs/2026-07-15-unattended-orchestration-design.md`: a deterministic `driver_tick`/`driver_finish` pair (wakeup accounting, budgets, Phase A baseline production, idempotent notification) plus a driver skill, so a cron-woken fresh Claude session can push a tournament job from empty directory to final notification with zero human attention.

**Architecture:** One new module `lib/tournament_driver.py` owns everything countable: job validation, driver-state persistence (same mkstemp+fsync atomic pattern as the tournament engine), burn-on-entry wakeup counting with a `max_wakeups` hard cap, preflight and Phase A (wrapping the existing `run_fasttext_binary_baseline` harness, injectable for tests), auto-start, per-wake budgets, ledger-diff wake accounting, and build-once at-least-once notification. The existing `tournament` MCP tool gains two additive stages (`driver_tick`, `driver_finish`); a fifth repo skill carries the per-wake policy prose. The engine (`lib/tournament_search.py`) is not modified.

**Tech Stack:** Python stdlib only. Reuses `lib/tournament_search.py` (state/step/report), `lib/full_reproduction_harness.py` (`run_fasttext_binary_baseline`, `probe_fasttext_runtime`), `lib/fdp_common.py` (`_is_plain_number`, `_json_clone`), and the established stage-dispatch MCP pattern.

## Global Constraints

- Python 3.10 and 3.13 both pass CI — no 3.12+-only syntax.
- Stdlib only; no new dependencies in `pyproject.toml`.
- Every commit must leave `ruff check lib/ scripts/ ml_intern/ codex_plugin/ tests/` clean and the touched test files passing.
- All tests offline and deterministic: no network, no real fastText binary (inject `baseline_fn`/`probe_fn`), no `time.sleep`; clocks injected via `now_fn`.
- Atomic driver-state writes: `tempfile.mkstemp` + `fsync` + `os.replace`, mirroring `lib/tournament_search.py:save_tournament_state`.
- Spec-fixed semantics: wakeup counting is **burn-on-entry** (increment persisted BEFORE the cap check); `max_wakeups` default 100; per-wake defaults `per_wake_max_rounds=3`, `per_wake_max_minutes=20`; Phase A execution failure → 1st attempt returns `phase_a_retry` (silent), 2nd → permanent `preflight_failed`; missing prerequisites (binary/data/spec) → immediate permanent `preflight_failed`; notification is build-once, at-least-once, `mark_notified` only flips the flag; deadline is a soft limit computed at tick entry (Phase A time counts against it).
- Adding the two MCP stages and the fifth skill is ADDITIVE — do NOT bump `MCP_CONTRACT_VERSION`.
- Every commit message ends with the footer line `Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>`.
- Run tests with the project venv: `.venv/bin/python -m pytest ...`; lint with `.venv/bin/ruff`.

## Verified Touchpoints (checked against the current tree; implementers rely on these, do not re-derive)

- `lib/tournament_search.py` (engine, unchanged): `start_tournament(*, runtime_root, run_id, target_id, config, baseline, target, now_fn=time.time) -> dict`; `load_tournament_state(path) -> dict`; `state_path(runtime_root, run_id) -> Path`; `tournament_dir(runtime_root, run_id) -> Path`; `build_tournament_report(state) -> dict` (keys incl. `winner{arm_id,status,failure_reason,hypothesis,best,improved,accepted_chain}`, `ledger`, `stop`); engine state keys: `state["stop"]["stopped"|"reason"]`, `state["pending_action"]`, `state["ledger"]["total_rounds_used"|"wall_seconds_used"]`, `state["report_written"]`, `state["report_path"]`.
- `lib/full_reproduction_harness.py:574` `run_fasttext_binary_baseline(config: FullReproductionRunConfig, *, train_csv: Path, test_csv: Path, fasttext_binary: Path) -> dict` — writes `<output_dir>/fasttext-baseline-report.json` containing `{"metric": {"p_at_1": ...}}` and returns `{"p_at_1": float, "baseline_report": str, ...}`. `FullReproductionRunConfig(target_spec_path: Path, output_dir: Path, max_train_seconds: int = 300)` is `@dataclass(frozen=True)`.
- `lib/full_reproduction_harness.py:262` `probe_fasttext_runtime(*, explicit_binary: Path | None = None) -> dict` — no training; `result["binary"]["available"]` is the executable check.
- `lib/mcp_service.py`: `TOOL_HANDLERS` maps `"tournament"` to `tournament_tool`; the dispatcher catches `(tournament_search.TournamentStateError, tournament_search.InvalidProposalError, FileExistsError, FileNotFoundError, ValueError)` → `MCPToolError`; `_assert_path_allowed(path, field)` raises `MCPToolError` directly; `SKILL_CONTRACTS` entries carry keys `path/client_role/description/required_tools/planning_signals`; `RECOMMENDED_SKILLS = list(SKILL_CONTRACTS)` (line ~650); `scripts/cli.py:install_skill_package` iterates `mcp_service.RECOMMENDED_SKILLS` and raises `FileNotFoundError` if `skills/<name>/SKILL.md` is missing — so SKILL_CONTRACTS registration and the SKILL.md file MUST land in the same commit.
- Tests that MUST be updated when registering the stage/skill additions: `tests/unit/test_mcp_service.py:8326` (`test_tournament_tool_is_registered`, asserts the exact 6-stage set) and `tests/unit/test_mcp_service.py:1856` (asserts the exact 4-item `recommended_skills` list).
- Canonical fastText inputs for the job template: target spec `docs/reproduction-pilot/full-reproduction-target.json`, binary `.external/fastText/fasttext` (repo-doc convention).
- `tests/unit/test_cli.py` imports `from scripts.cli import build_parser, main` and invokes `exit_code = main([...])` with `capsys`.

## File Structure

- Create `lib/tournament_driver.py` — job loading/validation, driver-state persistence, `driver_tick`, `driver_finish`, Phase A, helpers. Single responsibility: the deterministic driver layer. (~450 lines.)
- Create `tests/unit/test_tournament_driver.py` — all unit + integration tests for the driver.
- Modify `lib/mcp_service.py` — 2 new tournament stages, schema props, SKILL_CONTRACTS entry; create `skills/ml-research-loop-tournament-driver/SKILL.md` in the same task.
- Modify `tests/unit/test_mcp_service.py` — update the 2 exact-set assertions, add behavioral driver-stage tests.
- Modify `scripts/cli.py` + `tests/unit/test_cli.py` — `driver-tick`/`driver-finish` subcommands.
- Create `examples/tournament-jobs/{README.md,synthetic-demo.json,fasttext-ag-news.json}`; modify `README.md`, `docs/release-notes.md`.

---

### Task 1: Job loading/validation, driver-state model, atomic persistence

**Files:**
- Create: `lib/tournament_driver.py`
- Test: `tests/unit/test_tournament_driver.py`

**Interfaces:**
- Consumes: `lib.fdp_common._is_plain_number`, `lib.fdp_common._json_clone`, `lib.tournament_search.tournament_dir(runtime_root, run_id) -> Path`.
- Produces (later tasks rely on these exact names):
  - `DRIVER_SCHEMA_VERSION = "2026-07-15.tournament-driver.v1"`
  - `MAX_PHASE_A_ATTEMPTS = 2`, `DEFAULT_MAX_WAKEUPS = 100`, `DEFAULT_PER_WAKE_MAX_ROUNDS = 3`, `DEFAULT_PER_WAKE_MAX_MINUTES = 20`
  - `class DriverJobError(ValueError)`
  - `load_job(job: dict | str | Path) -> dict` — validated, defaults-normalized deep copy.
  - `driver_state_path(job: dict) -> Path` — `<runtime_root>/tournament/<run_id>/driver-state.json`
  - `save_driver_state(state: dict, path: Path) -> None` (atomic), `load_driver_state(path: Path) -> dict`
  - `init_driver_state(job: dict, *, now: float) -> dict` with the exact shape asserted in the tests below.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_tournament_driver.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_driver.py -q`
Expected: FAIL/collection error with `ModuleNotFoundError: No module named 'lib.tournament_driver'`.

- [ ] **Step 3: Write the implementation**

Create `lib/tournament_driver.py`:

```python
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
```

(`shutil` is imported now and used by Task 3's Phase A copy; if ruff flags it as unused in this commit, keep the import out until Task 3 — mirror how Task 1/3 of the tournament plan handled `math`.)

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_driver.py -q`
Expected: all PASS.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check lib/tournament_driver.py tests/unit/test_tournament_driver.py
git add lib/tournament_driver.py tests/unit/test_tournament_driver.py
git commit -m "feat: tournament driver job schema and driver-state persistence

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 2: `driver_tick` core — burn-on-entry counting, cap, quiescence, interrupted-wake closure

**Files:**
- Modify: `lib/tournament_driver.py`
- Test: `tests/unit/test_tournament_driver.py`

**Interfaces:**
- Consumes: Task 1's functions; `tournament_search.load_tournament_state`, `tournament_search.state_path`.
- Produces: `driver_tick(*, job, now_fn=time.time, baseline_fn=None, probe_fn=None) -> dict` (this task implements the entry bookkeeping and the `stop_budget_exhausted` / `quiescent` / `finalize` actions; Tasks 3-4 extend the same function with preflight/Phase A/auto-start/proceed). Wake-plan shape produced here and relied on by every later task:
  `{"action": str, "reason": str | None, "wakeup": {"index": int, "max_wakeups": int}, "pending_action": dict | None, "tournament": {"started": bool, "stopped": bool, "stop_reason": str | None}}`
  — `proceed` plans additionally carry `"per_wake_budget"` and `"best_so_far"` (Task 4); `preflight_failed` plans carry `"missing"` (Task 3).
  Wake-history entry shape: `{"wakeup": int, "started_at": float, "ledger_rounds_at_start": int | None, "rounds_executed": int | None, "closed": bool, "exit_reason": str | None}`.
  Also produces the internal helpers `_load_engine_state(job) -> dict | None` and `_close_open_wakes(state, engine_state, *, exit_reason) -> None` reused by `driver_finish`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_tournament_driver.py`:

```python
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
    assert plan1["wakeup"] == {"index": 1, "max_wakeups": 1}
    assert plan1["action"] != "stop_budget_exhausted"  # first wake within cap
    plan2 = _tick(job_path, 2000.0)
    assert plan2["action"] == "stop_budget_exhausted"
    state = td.load_driver_state(td.driver_state_path(td.load_job(job_path)))
    assert state["wakeups_used"] == 2  # the over-cap wake still burned
    assert state["stopped"] == {"stopped": True, "reason": "max_wakeups"}


def test_tick_closes_interrupted_wake_from_previous_session(tmp_path):
    job_path = _prepared_job(tmp_path)
    _tick(job_path, 1000.0)  # opens wake 1, session then "dies" (no finish)
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_driver.py -q -k tick`
Expected: FAIL with `AttributeError: ... 'driver_tick'`.

- [ ] **Step 3: Write the implementation**

Append to `lib/tournament_driver.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_driver.py -q`
Expected: the four new tests PASS (none of them reach `_prepare_and_proceed`... except `test_tick_burns_wakeup_on_entry_and_persists_before_cap_check`'s FIRST tick, which does reach it. Adjust that test's first assertion to tolerate the stub: wrap the first `_tick` call in `pytest.raises(NotImplementedError)` and read `wakeups_used == 1` from the persisted state instead of from the plan — the burn-on-entry save happens before the stub raises, which is exactly the crash semantics the spec demands. Rewrite that test as:)

```python
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
```

(Task 4 removes the `pytest.raises` wrapper once `proceed` works; a note in Task 4's Step 1 covers this. `test_tick_closes_interrupted_wake_from_previous_session` likewise wraps both `_tick` calls in `pytest.raises(NotImplementedError)` for now — the closure assertions still hold because closure and burn persist before the stub raises. Same removal in Task 4.)

Expected after adjustment: all PASS.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check lib/tournament_driver.py tests/unit/test_tournament_driver.py
git add lib/tournament_driver.py tests/unit/test_tournament_driver.py
git commit -m "feat: driver_tick burn-on-entry accounting, cap, quiescence

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 3: Preflight and Phase A

**Files:**
- Modify: `lib/tournament_driver.py`
- Test: `tests/unit/test_tournament_driver.py`

**Interfaces:**
- Consumes: Task 2's `_prepare_and_proceed` stub position, `_wake_plan`; `lib.full_reproduction_harness.run_fasttext_binary_baseline` / `FullReproductionRunConfig` / `probe_fasttext_runtime` (verified signatures in the plan header).
- Produces:
  - `_preflight_missing(job, probe_fn) -> list[str]` — empty for synthetic; for fastText checks `target.target_spec`/`target.train_csv`/`target.test_csv` file existence and binary executability via `probe_fn` (default `probe_fasttext_runtime`).
  - `_ensure_baseline(job, *, baseline_fn) -> None` — creates `job["baseline_artifact"]`; synthetic writes `{"metric": {"value": target.baseline_value}}`; fastText calls `baseline_fn(job, phase_a_dir)` (default wraps the harness and copies its report to the artifact path). `baseline_fn(job: dict, phase_a_dir: Path) -> str` returns the produced report path.
  - `_baseline_value_from_artifact(path: Path) -> float` — accepts `metric.p_at_1`, `metric.value`, or top-level `value`; raises `DriverJobError` otherwise.
  - Inside `_prepare_and_proceed`: the `preflight_failed` / `phase_a_retry` actions with the spec's retry semantics (1st execution failure → `phase_a_retry`, 2nd → permanent; missing prerequisites → immediately permanent).

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_tournament_driver.py`:

```python
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

    td.driver_tick(job=job_path, now_fn=lambda: 1000.0,
                   probe_fn=_ok_probe, baseline_fn=fake_baseline)
    artifact = Path(td.load_job(job_path)["baseline_artifact"])
    assert json.loads(artifact.read_text(encoding="utf-8")) == {
        "metric": {"p_at_1": 0.914}
    }
    state = td.load_driver_state(td.driver_state_path(td.load_job(job_path)))
    assert state["phase_a"]["status"] == "completed"


def test_synthetic_baseline_auto_written(tmp_path):
    job_path = _write_job(tmp_path, _job_dict(tmp_path))  # no artifact on disk
    td.driver_tick(job=job_path, now_fn=lambda: 1000.0)
    artifact = Path(td.load_job(job_path)["baseline_artifact"])
    assert json.loads(artifact.read_text(encoding="utf-8")) == {
        "metric": {"value": 0.9}
    }


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
```

Note: the success-path tests above end inside `_prepare_and_proceed` after Phase A; auto-start/proceed still raises `NotImplementedError` until Task 4. Wrap the two success-path tick calls (`test_tick_phase_a_success_writes_artifact_via_injected_fn`, `test_synthetic_baseline_auto_written`) in `pytest.raises(NotImplementedError)` for this commit — the artifact/state assertions run after the call and still verify persistence (everything is saved before the stub raises). Task 4 removes those wrappers.

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_driver.py -q -k "preflight or phase_a or baseline_value or synthetic_baseline"`
Expected: FAIL with `AttributeError: ... '_preflight_missing'`.

- [ ] **Step 3: Write the implementation**

In `lib/tournament_driver.py`, add the helpers and replace `_prepare_and_proceed`'s body:

```python
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
```

Replace `_prepare_and_proceed`'s `raise NotImplementedError(...)` body with:

```python
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
    raise NotImplementedError("auto-start/proceed lands in the next task")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_driver.py -q`
Expected: all PASS (with the two documented `pytest.raises(NotImplementedError)` wrappers still in place).

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check lib/tournament_driver.py tests/unit/test_tournament_driver.py
git add lib/tournament_driver.py tests/unit/test_tournament_driver.py
git commit -m "feat: driver preflight and Phase A baseline production

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 4: Auto-start and the `proceed` plan

**Files:**
- Modify: `lib/tournament_driver.py`
- Test: `tests/unit/test_tournament_driver.py`

**Interfaces:**
- Consumes: `tournament_search.start_tournament` (exact signature in plan header), `tournament_search.build_tournament_report`.
- Produces: the completed `_prepare_and_proceed` — auto-starts the tournament when needed and returns the `proceed` plan with `"per_wake_budget": {"max_rounds": int, "deadline_at": float}` (deadline = wake `started_at` + `per_wake_max_minutes*60`, so Phase A time counts against it) and `"best_so_far": {"winner": {...} | None, "total_rounds_used": int}`. Also updates the open wake entry's `ledger_rounds_at_start` once the engine exists.

- [ ] **Step 1: Update the Task 2/3 stub-tolerant tests, then write the new failing tests**

Remove the `pytest.raises(NotImplementedError)` wrappers added in Tasks 2-3 (four call sites: `test_tick_burns_wakeup_on_entry_and_persists_before_cap_check` first tick, both ticks in `test_tick_closes_interrupted_wake_from_previous_session`, and the tick calls in `test_tick_phase_a_success_writes_artifact_via_injected_fn` / `test_synthetic_baseline_auto_written`); assert on the returned plan where natural (e.g. the burn test's first tick now returns `plan1["wakeup"]["index"] == 1`). Then append:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_driver.py -q`
Expected: the new tests and the un-wrapped Task 2/3 tests FAIL with `NotImplementedError` from the stub tail.

- [ ] **Step 3: Write the implementation**

Replace `_prepare_and_proceed`'s trailing `raise NotImplementedError(...)` with:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_driver.py -q`
Expected: all PASS, zero `NotImplementedError` tolerance remaining.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check lib/tournament_driver.py tests/unit/test_tournament_driver.py
git add lib/tournament_driver.py tests/unit/test_tournament_driver.py
git commit -m "feat: driver auto-start and proceed wake plan

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 5: `driver_finish` — ledger-diff accounting and build-once notification

**Files:**
- Modify: `lib/tournament_driver.py`
- Test: `tests/unit/test_tournament_driver.py`

**Interfaces:**
- Consumes: `_close_open_wakes`, `_load_engine_state`, `tournament_search.build_tournament_report`.
- Produces: `driver_finish(*, job, mark_notified: bool = False, now_fn=time.time) -> dict` returning `{"status": "closed" | "notified" | "noop", "wake": <closed entry or None>, "notification": {"required": bool, "sent": bool, "payload": dict | None}}`. Notification payload shape (built exactly once): `{"job_id", "stop_reason", "winner": {arm_id, hypothesis, best, improved, status} | None, "rounds_used": int, "wakeups_used": int, "wall_seconds_used": float, "report_path": str | None, "runtime_root": str, "run_id": str}`.

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_tournament_driver.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_driver.py -q -k finish`
Expected: FAIL with `AttributeError: ... 'driver_finish'`.

- [ ] **Step 3: Write the implementation**

Append to `lib/tournament_driver.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_driver.py -q`
Expected: all PASS.

- [ ] **Step 5: Lint and commit**

```bash
.venv/bin/ruff check lib/tournament_driver.py tests/unit/test_tournament_driver.py
git add lib/tournament_driver.py tests/unit/test_tournament_driver.py
git commit -m "feat: driver_finish ledger-diff accounting and build-once notification

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 6: Multi-wake unattended lifecycle integration test

**Files:**
- Test: `tests/unit/test_tournament_driver.py` (test-only task; a reviewer can reject it independently if the scenario is weak)

**Interfaces:**
- Consumes: everything from Tasks 1-5 plus the engine's `submit_directions`/`submit_proposal`/`step`/`load_tournament_state`.
- Produces: `_drive_one_wake(job_path, clock) -> dict` test helper — the scripted stand-in for the LLM session, reused by Task 7's MCP smoke reasoning if needed.

- [ ] **Step 1: Write the integration tests (they should pass immediately if Tasks 1-5 are correct — this task's RED step is running them BEFORE writing, expecting collection success and then genuine failures only if 1-5 have bugs)**

Append to `tests/unit/test_tournament_driver.py`:

```python
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
    build_times = {state["notification"]["built_at"]}
    assert len(build_times) == 1  # built exactly once


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
```

- [ ] **Step 2: Run to verify they pass (or expose real Task 1-5 bugs)**

Run: `.venv/bin/python -m pytest tests/unit/test_tournament_driver.py -q`
Expected: all PASS. If either integration test fails, that is a REAL bug in Tasks 1-5 — debug it (systematic root-cause, not test-tweaking) before proceeding; do not weaken the assertions.

Hand-trace for the first test (verify against your run; `_scripted_proposal` submits `param = len(history)+2`): wake 1 = directions (first proposals a=1/b=1/c=1) + 3 rounds — a1:0.91 accept, a2:0.901 accept (delta == epsilon), a3:0.89 reject — hits the 3-round cap. Wake 2 = stage_end (a3 pruned, survivors' allocation 1+2=3), then round-robin a1:a=3→0.93 accept, a2:b=3→0.903 accept, a1:a=4→0.94 accept — cap again. Wake 3 = a2:b=4→0.904 accept, then a1:a=5→0.95 = target → stopped mid-wake (2 rounds this wake), finalize step writes the report, finish builds the notification once, mark_notified sends; the outer loop exits on `notification.sent` with `wakes == 3`. Total rounds 3+3+2 = 8 ≤ max_total_rounds 12. `wakes >= 3` and `rounds_executed <= 3` follow.

- [ ] **Step 3: Lint and commit**

```bash
.venv/bin/ruff check tests/unit/test_tournament_driver.py
git add tests/unit/test_tournament_driver.py
git commit -m "test: multi-wake unattended lifecycle integration coverage

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 7: MCP stages `driver_tick`/`driver_finish` + fifth skill registration

**Files:**
- Modify: `lib/mcp_service.py` (import, schema entry, dispatcher, SKILL_CONTRACTS)
- Create: `skills/ml-research-loop-tournament-driver/SKILL.md`
- Test: `tests/unit/test_mcp_service.py`

**Interfaces:**
- Consumes: `tournament_driver.load_job` / `driver_tick` / `driver_finish` / `DriverJobError` (exact signatures from Tasks 1-5).
- Produces: MCP tool `tournament` stages grow 6→8; SKILL_CONTRACTS gains `"ml-research-loop-tournament-driver"` (which automatically extends `RECOMMENDED_SKILLS` and makes `ml-loop init-skills` install the new skill — hence the SKILL.md ships in this same commit).

- [ ] **Step 1: Write the failing tests AND update the two exact-set assertions**

In `tests/unit/test_mcp_service.py`:

(a) `test_tournament_tool_is_registered` (~line 8326): change the stage-set assertion to the 8-stage set:

```python
    assert stages == {"start", "status", "submit_directions",
                      "submit_proposal", "step", "report",
                      "driver_tick", "driver_finish"}
```

(b) The `recommended_skills` exact list (~line 1856): append `"ml-research-loop-tournament-driver"` as the fifth entry.

(c) Append new behavioral tests:

```python
def test_tournament_driver_stages_run_synthetic_wake(tmp_path, monkeypatch):
    monkeypatch.setenv("ML_RESEARCH_LOOP_ALLOWED_ROOTS", str(tmp_path))
    job = {
        "job_id": "mcp-job", "runtime_root": str(tmp_path / "rt"),
        "run_id": "run-1", "target_id": "demo",
        "target": {"kind": "synthetic", "baseline_value": 0.9,
                   "weights": {"a": 0.01}},
        "tournament_config": {"k": 2, "initial_rounds_per_arm": 1,
                              "halving": 2, "epsilon": 0.001,
                              "metric": "score", "direction": "maximize",
                              "budgets": {"max_total_rounds": 6,
                                          "max_wall_seconds": 86400,
                                          "target_value": None}},
        "baseline_artifact": str(tmp_path / "rt" / "baseline.json"),
        "driver": {"max_wakeups": 5, "per_wake_max_rounds": 3,
                   "per_wake_max_minutes": 20},
        "notify": {"on_stop": True},
    }
    job_file = tmp_path / "job.json"
    job_file.write_text(json.dumps(job), encoding="utf-8")
    plan = mcp_service.tournament_tool({"stage": "driver_tick",
                                        "job_file": str(job_file)})
    assert plan["action"] == "proceed"
    assert plan["pending_action"]["type"] == "need_direction_proposals"
    finish = mcp_service.tournament_tool({"stage": "driver_finish",
                                          "job": job})
    assert finish["status"] == "closed"
    assert finish["wake"]["exit_reason"] == "per_wake_budget"


def test_tournament_driver_stages_enforce_sandbox_and_require_job(tmp_path, monkeypatch):
    monkeypatch.setenv("ML_RESEARCH_LOOP_ALLOWED_ROOTS", str(tmp_path))
    with pytest.raises(mcp_service.MCPToolError):
        mcp_service.tournament_tool({"stage": "driver_tick"})  # no job
    outside = {"job_id": "x", "runtime_root": "/somewhere/else",
               "run_id": "r", "target_id": "t",
               "target": {"kind": "synthetic", "baseline_value": 0.9,
                          "weights": {"a": 0.01}},
               "tournament_config": {"k": 2, "initial_rounds_per_arm": 1,
                                     "halving": 2, "epsilon": 0.001,
                                     "metric": "m", "direction": "maximize",
                                     "budgets": {"max_total_rounds": 5,
                                                 "max_wall_seconds": 60,
                                                 "target_value": None}},
               "baseline_artifact": "/somewhere/else/b.json"}
    with pytest.raises(mcp_service.MCPToolError):
        mcp_service.tournament_tool({"stage": "driver_tick", "job": outside})
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/unit/test_mcp_service.py -q -k "tournament"`
Expected: the two new tests FAIL (`unknown stage 'driver_tick'` MCPToolError) and the updated registration test FAILS (stage set still 6).

- [ ] **Step 3: Write the implementation**

Five edits to `lib/mcp_service.py`:

(a) Import — extend the existing `from lib import tournament_search` line's neighborhood with:

```python
from lib import tournament_driver
```

(b) Schema entry for `tournament` in `tool_definitions()`: extend `properties.stage.enum` to the 8 values (`..., "driver_tick", "driver_finish"`), AND update the `valid_stages` list at the top of the `tournament_tool` dispatcher function to the same 8 values — the dispatcher rejects unknown stages before any branch runs, so missing this edit makes the new stages unreachable ("unknown stage" MCPToolError). Then add three properties alongside the existing ones:

```python
                    "job": {"type": "object"},
                    "job_file": {"type": "string"},
                    "mark_notified": {"type": "boolean", "default": False},
```

Also extend the tool's `description` (and the identical `TOOL_CONTRACT_DESCRIPTIONS["tournament"]` string — they are the same object, one edit) with: `"; driver_tick=Burn one unattended wakeup, enforce budgets, run preflight/Phase A, auto-start, and return the wake plan.; driver_finish=Close the wake with ledger-diff accounting and build the stop notification once (mark_notified=true only flips the sent flag)."`

(c) Dispatcher — inside `tournament_tool`, BEFORE the existing `runtime_root_raw = payload.get("runtime_root")` block, add the driver-stage branch (driver stages get runtime_root from the job, not from a top-level arg):

```python
    if stage in ("driver_tick", "driver_finish"):
        job_file = payload.get("job_file")
        job_payload = payload.get("job")
        try:
            if job_file:
                job_path = Path(job_file).expanduser().resolve()
                _assert_path_allowed(job_path, "job_file")
                job_obj = tournament_driver.load_job(job_path)
            elif isinstance(job_payload, dict) and job_payload:
                job_obj = tournament_driver.load_job(job_payload)
            else:
                raise MCPToolError({
                    "status": "failed",
                    "error": "job or job_file is required for driver stages",
                    "field": "job",
                })
            _assert_path_allowed(
                Path(job_obj["runtime_root"]).expanduser().resolve(),
                "runtime_root",
            )
            if stage == "driver_tick":
                return tournament_driver.driver_tick(job=job_obj)
            return tournament_driver.driver_finish(
                job=job_obj,
                mark_notified=bool(payload.get("mark_notified", False)),
            )
        except (tournament_driver.DriverJobError, FileNotFoundError,
                ValueError) as error:
            raise MCPToolError({
                "status": "failed",
                "error": str(error),
                "stage": stage,
            }) from error
```

(Note: `MCPToolError` raised inside the `try` (the job-required case and `_assert_path_allowed`) must not be swallowed — `MCPToolError` subclasses `RuntimeError`, not `ValueError`, so the except tuple does not catch it; verify this inheritance in the file and add `except MCPToolError: raise` above the tuple if you find otherwise.)

(d) SKILL_CONTRACTS — add the fifth entry after `"ml-research-loop-operator"`:

```python
    "ml-research-loop-tournament-driver": {
        "path": "skills/ml-research-loop-tournament-driver/SKILL.md",
        "client_role": "unattended_driver",
        "description": (
            "Drive one tournament job unattended per wake: tick, propose, "
            "step, finish, notify once, deregister on stop."
        ),
        "required_tools": [
            "get_service_manifest",
            "tournament",
        ],
        "planning_signals": [
            "execution_metadata",
            "execution_sandbox",
            "compatibility_check",
        ],
    },
```

(e) Create `skills/ml-research-loop-tournament-driver/SKILL.md`:

```markdown
---
name: ml-research-loop-tournament-driver
description: Use when a scheduled/cron wake asks you to drive an ML Research Loop tournament job unattended from a job.json file
---

# ML Research Loop Tournament Driver

## Purpose

Drive exactly one wake of an unattended tournament job. All countable
decisions (wakeup budgets, Phase A, stop conditions, notification
idempotency) live in the MCP `tournament` tool's `driver_tick` /
`driver_finish` stages — your job is only the two reasoning touchpoints
(direction generation, per-round proposals) plus pushing the final
notification and deregistering the schedule when the run stops.

## Per-wake procedure

1. Call `tournament` stage=`driver_tick` with `job_file=<the job path from
   your task prompt>`. Branch on `action`:
   - `proceed`: go to step 2.
   - `finalize`: if `pending_action.type == "finalize"`, call stage=`step`
     once (writes report.json), then go to step 3.
   - `phase_a_retry`: call stage=`driver_finish`, then exit quietly (no
     notification, no deregistration — the next wake retries Phase A).
   - `preflight_failed` / `stop_budget_exhausted`: go to step 3.
   - `quiescent`: exit immediately; do nothing.
2. Work loop — repeat until the engine stops, you have executed
   `per_wake_budget.max_rounds` rounds (each stage=`step` on a `run_round`
   pending action counts as one), or the wall clock passes
   `per_wake_budget.deadline_at` (check between actions; never abandon an
   action midway):
   - `pending_action.type == "need_direction_proposals"`: propose K
     mutually distinct direction hypotheses, each from a different
     parameter family for this target (fastText families: n-gram window,
     learning rate, epochs, dimension — all within the engine's allowlist),
     each with a concrete `first_proposal`. Submit via
     stage=`submit_directions`.
   - `need_round_proposal`: call stage=`status`, read that arm's
     `hypothesis` and `history` (its accepted chain), and propose the next
     single change WITHIN that hypothesis. Submit via
     stage=`submit_proposal`. If the tool returns an invalid-proposal
     error, read the message and correct — the engine kills the arm after
     3 consecutive invalid proposals regardless.
   - anything else (`run_round`/`stage_end`/`finalize`): call stage=`step`.
3. Call stage=`driver_finish`. If the result's `notification.required` is
   true and `sent` is false: push the notification (payload text comes from
   `notification.payload` — do not rewrite the numbers), then call
   stage=`driver_finish` with `mark_notified=true`, then deregister this
   job's scheduled task. If deregistration fails, exit anyway — the driver
   self-quenches (future wakes are quiescent and the wakeup cap is a hard
   ceiling).
4. Exit. Never loop past the per-wake budget; the schedule will wake you
   again.

## Failure rules

- A structured error from `driver_tick` itself (unreadable job file):
  best-effort push an error notification, deregister the schedule, exit.
- Never edit state files by hand; every mutation goes through the tool.
- Never claim benchmark results in notifications beyond what
  `notification.payload` states (`official_scores_claimed=false` culture).

## Manual acceptance (not CI)

```bash
# one wake, by hand, against the offline synthetic demo job:
ml-loop tournament driver-tick --job examples/tournament-jobs/synthetic-demo.json --json
# ... drive stages per the procedure above ...
ml-loop tournament driver-finish --job examples/tournament-jobs/synthetic-demo.json --json
```

Real unattended run: create a Claude Code scheduled task whose prompt is
"Use the ml-research-loop-tournament-driver skill to drive
<absolute path to job.json>", with the interval from your budget planning
(e.g. every 30 minutes).
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/unit/test_mcp_service.py -q && .venv/bin/python -m pytest tests/unit/test_tournament_driver.py -q`
Expected: all PASS.

- [ ] **Step 5: Run the real MCP acceptance check, lint, and commit**

```bash
.venv/bin/python scripts/mcp_client_acceptance.py --python "$(pwd)/.venv/bin/python3"
# Expected: status: passed, tool_count: 95 (unchanged — stages are not tools),
# missing_required_tools: [], missing_tool_contracts: [], and the five skills
# all resolve (install_skill_package iterates RECOMMENDED_SKILLS).
.venv/bin/ruff check lib/ scripts/ ml_intern/ codex_plugin/ tests/
git add lib/mcp_service.py skills/ml-research-loop-tournament-driver/SKILL.md tests/unit/test_mcp_service.py
git commit -m "feat: tournament driver MCP stages and driver skill registration

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

### Task 8: CLI mirror, job examples, docs, full gate

**Files:**
- Modify: `scripts/cli.py`, `README.md`, `docs/release-notes.md`
- Create: `examples/tournament-jobs/README.md`, `examples/tournament-jobs/synthetic-demo.json`, `examples/tournament-jobs/fasttext-ag-news.json`
- Test: `tests/unit/test_cli.py`

**Interfaces:**
- Consumes: `tournament_driver.driver_tick` / `driver_finish` (CLI calls lib directly, sibling-adapter convention — no sandbox, same as the other tournament subcommands); cli.py's `_print_json_payload(payload, compact=args.json)`.
- Produces: `ml-loop tournament driver-tick --job <file> [--json]` and `ml-loop tournament driver-finish --job <file> [--mark-notified] [--json]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_cli.py` (uses the file's existing `from scripts.cli import main` + `exit_code = main([...])` + `capsys` convention):

```python
def test_tournament_driver_cli_wake_roundtrip(tmp_path, capsys):
    job = {
        "job_id": "cli-job", "runtime_root": str(tmp_path / "rt"),
        "run_id": "run-1", "target_id": "demo",
        "target": {"kind": "synthetic", "baseline_value": 0.9,
                   "weights": {"a": 0.01}},
        "tournament_config": {"k": 2, "initial_rounds_per_arm": 1,
                              "halving": 2, "epsilon": 0.001,
                              "metric": "score", "direction": "maximize",
                              "budgets": {"max_total_rounds": 6,
                                          "max_wall_seconds": 86400,
                                          "target_value": None}},
        "baseline_artifact": str(tmp_path / "rt" / "baseline.json"),
        "driver": {"max_wakeups": 5, "per_wake_max_rounds": 3,
                   "per_wake_max_minutes": 20},
        "notify": {"on_stop": True},
    }
    job_file = tmp_path / "job.json"
    job_file.write_text(json.dumps(job), encoding="utf-8")
    assert main(["tournament", "driver-tick", "--job", str(job_file),
                 "--json"]) == 0
    plan = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert plan["action"] == "proceed"
    assert main(["tournament", "driver-finish", "--job", str(job_file),
                 "--json"]) == 0
    fin = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert fin["status"] == "closed"
    assert main(["tournament", "driver-finish", "--job", str(job_file),
                 "--mark-notified", "--json"]) == 0
    marked = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert marked["status"] == "notified"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/unit/test_cli.py -q -k tournament_driver`
Expected: FAIL with argparse error (unknown tournament subcommand `driver-tick`).

- [ ] **Step 3: Write the implementation**

In `scripts/cli.py`:

(a) Import: add `from lib import tournament_driver` next to the existing `from lib import tournament_search`.

(b) Parser registration — inside the existing `tournament_commands` group (after the `report` subcommand):

```python
    tournament_driver_tick = tournament_commands.add_parser("driver-tick")
    tournament_driver_tick.add_argument("--job", type=Path, required=True)
    tournament_driver_tick.add_argument("--json", action="store_true")

    tournament_driver_finish = tournament_commands.add_parser("driver-finish")
    tournament_driver_finish.add_argument("--job", type=Path, required=True)
    tournament_driver_finish.add_argument("--mark-notified",
                                          action="store_true")
    tournament_driver_finish.add_argument("--json", action="store_true")
```

(c) Dispatch — extend the existing `if args.command == "tournament":` block (these two subcommands have no `--runtime-root`/`--run-id`, so add their branches BEFORE any code that reads those attributes):

```python
        if args.tournament_command == "driver-tick":
            payload = tournament_driver.driver_tick(job=args.job)
            _print_json_payload(payload, compact=args.json)
            return 0
        if args.tournament_command == "driver-finish":
            payload = tournament_driver.driver_finish(
                job=args.job, mark_notified=args.mark_notified,
            )
            _print_json_payload(payload, compact=args.json)
            return 0
```

(d) Create `examples/tournament-jobs/synthetic-demo.json`:

```json
{
  "job_id": "synthetic-demo",
  "runtime_root": ".demo_runs/tournament-jobs/synthetic-demo",
  "run_id": "run-1",
  "target_id": "synthetic-demo",
  "target": {
    "kind": "synthetic",
    "baseline_value": 0.9,
    "weights": {"a": 0.01, "b": 0.001, "c": -0.01}
  },
  "tournament_config": {
    "k": 3, "initial_rounds_per_arm": 1, "halving": 2, "epsilon": 0.001,
    "metric": "score", "direction": "maximize",
    "budgets": {"max_total_rounds": 12, "max_wall_seconds": 3600,
                "target_value": 0.93}
  },
  "baseline_artifact": ".demo_runs/tournament-jobs/synthetic-demo/baseline.json",
  "driver": {"max_wakeups": 20, "per_wake_max_rounds": 3,
             "per_wake_max_minutes": 5},
  "notify": {"on_stop": true}
}
```

(e) Create `examples/tournament-jobs/fasttext-ag-news.json`:

```json
{
  "job_id": "fasttext-ag-news-overnight",
  "runtime_root": ".demo_runs/tournament-jobs/fasttext-ag-news",
  "run_id": "run-1",
  "target_id": "fasttext-ag-news",
  "target": {
    "kind": "fasttext",
    "target_spec": "docs/reproduction-pilot/full-reproduction-target.json",
    "train_csv": "data/ag_news/train.csv",
    "test_csv": "data/ag_news/test.csv",
    "fasttext_binary": ".external/fastText/fasttext",
    "max_train_seconds": 900
  },
  "tournament_config": {
    "k": 4, "initial_rounds_per_arm": 2, "halving": 2, "epsilon": 0.0005,
    "metric": "P@1", "direction": "maximize",
    "budgets": {"max_total_rounds": 40, "max_wall_seconds": 86400,
                "target_value": 0.92}
  },
  "baseline_artifact": ".demo_runs/tournament-jobs/fasttext-ag-news/baseline.json",
  "driver": {"max_wakeups": 100, "per_wake_max_rounds": 3,
             "per_wake_max_minutes": 30},
  "notify": {"on_stop": true}
}
```

(f) Create `examples/tournament-jobs/README.md`:

```markdown
# Tournament job files

One job = one tournament run = one scheduled task. `synthetic-demo.json`
runs fully offline (no binary, no data, Phase A auto-writes the baseline)
and is the acceptance path. `fasttext-ag-news.json` is the real-data
template: it expects the fastText binary at `.external/fastText/fasttext`
and full AG News CSVs under `data/ag_news/` (both gitignored,
user-provided); adjust paths, budgets, and `max_wakeups` before use.
`max_wall_seconds` counts from tournament creation — set it day-scale for
unattended runs. See `skills/ml-research-loop-tournament-driver/SKILL.md`
for the per-wake procedure and the scheduled-task prompt.
```

(g) `README.md` — in the Core MCP Tools table, replace the `tournament` row's stage list with the 8 stages:

`| `tournament` | Stage-dispatched direction tournament search (`stage`: start, status, submit_directions, submit_proposal, step, report, driver_tick, driver_finish) — successive-halving over per-direction greedy chains with deterministic pruning, budgets, stop conditions, and an unattended-driver layer (wakeup budgets, Phase A baseline production, build-once stop notification) |`

Also, in the Skills table (the four-row table naming the repo skills), add:

`| `ml-research-loop-tournament-driver` | Unattended per-wake driving of one tournament job (tick, propose, step, finish, notify, deregister) |`

(h) `docs/release-notes.md` — append under the existing `## 2026-07-11 Additions` a sibling heading `## 2026-07-15 Additions` (before `## Migration Notes`):

```markdown
## 2026-07-15 Additions

- Unattended orchestration driver (sub-project 2, spec:
  docs/superpowers/specs/2026-07-15-unattended-orchestration-design.md):
  additive `tournament` stages `driver_tick`/`driver_finish`
  (`lib/tournament_driver.py` — burn-on-entry wakeup accounting with a
  `max_wakeups` hard cap, preflight + Phase A fastText baseline production
  with one silent retry, per-wake round/deadline budgets, ledger-diff wake
  accounting, build-once at-least-once stop notification), CLI mirrors
  `ml-loop tournament driver-tick|driver-finish --job <file>`, a fifth repo
  skill `ml-research-loop-tournament-driver`, and job templates under
  `examples/tournament-jobs/`. Additive only; contract_version unchanged.
  Claim boundary unchanged: local unattended-orchestration capability only,
  no model-quality or benchmark claims; `official_scores_claimed=false`.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/unit/test_cli.py -q -k tournament && .venv/bin/python -m pytest tests/unit/test_mcp_delivery_docs.py -q`
Expected: all PASS.

- [ ] **Step 5: Full gate, lint, and commit**

```bash
.venv/bin/ruff check lib/ scripts/ ml_intern/ codex_plugin/ tests/
.venv/bin/python -m pytest tests/ -q
# Expected: all tests pass (935 pre-existing + the new driver/MCP/CLI tests)
git add scripts/cli.py tests/unit/test_cli.py examples/tournament-jobs/ README.md docs/release-notes.md
git commit -m "feat: tournament driver CLI, job templates, and docs

Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
```

---

## Self-Review Notes (completed during plan writing)

- **Spec coverage:** job file + driver-state (Task 1), burn-on-entry/cap/quiescence/interrupted-closure (Task 2), preflight/Phase A with retry-then-permanent semantics and the immediate-permanent prerequisite branch (Task 3), auto-start + proceed budgets/deadline/best-so-far (Task 4), finish ledger-diff + build-once at-least-once notification + mark_notified-flips-only (Task 5), multi-wake lifecycle + budget-stop + per-wake-cap + notification-once (Task 6), MCP stages + sandbox-via-job + fifth skill + the two exact-set test updates + SKILL.md wake policy incl. the finalize-needs-step nuance and best-effort job-corruption fallback (Task 7), CLI + templates + docs + claim boundary (Task 8). Spec's "v1 范围外" list has no tasks — correct.
- **Cross-task consistency:** `driver_tick(*, job, now_fn, baseline_fn, probe_fn)` / `driver_finish(*, job, mark_notified, now_fn)` signatures identical across Tasks 2-8; wake-plan/wake-entry/notification shapes defined once (Task 2/5 interfaces) and asserted verbatim in Tasks 6-8.
- **Known intentional simplifications:** the deadline is computed by tick but enforced by the session between actions (spec: soft limit); `_drive_one_wake` (tests) checks only the round cap, deadline field is asserted in Task 4's unit test. MCP `driver_tick` uses real `time.time()` (no `now_fn` passthrough) — unattended production wants real time; deterministic tests go through the lib layer directly.
- **Stub sequencing:** Tasks 2-3 park `_prepare_and_proceed` behind `NotImplementedError` with `pytest.raises` wrappers that Task 4 removes — same pattern the tournament plan used for its Task 5/6 xfail handoff, with the wrapper placement chosen so burn/persistence assertions still execute against disk state.
