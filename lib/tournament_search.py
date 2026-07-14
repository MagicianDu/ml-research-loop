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
            # No round executes here, so no wall-clock time has genuinely
            # elapsed; reuse the last known elapsed time from the ledger
            # instead of the real wall clock, which would be wildly out of
            # sync with a caller-supplied now_fn used elsewhere (step()).
            frozen_now = state["created_at"] + state["ledger"]["wall_seconds_used"]
            reason = check_stop(state, now=frozen_now)
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
