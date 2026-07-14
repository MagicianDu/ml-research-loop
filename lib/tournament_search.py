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
import os
import tempfile
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
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=path.parent,
        prefix=".tournament_tmp_",
        suffix=".json",
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2, sort_keys=True)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    except Exception:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


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
