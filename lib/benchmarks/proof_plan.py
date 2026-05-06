"""Read-only public proof-run planning for official benchmark harnesses."""

from __future__ import annotations

from typing import Any


def build_public_proof_plan(harness_probe: dict[str, Any]) -> dict[str, Any]:
    """Return a safe proof-run decision payload from an official harness probe."""
    missing = _missing_prerequisites(harness_probe)
    ready = harness_probe.get("status") == "ready" and not missing
    return {
        "status": "ready_for_debug_run" if ready else "blocked",
        "read_only": True,
        "official_scores_claimed": False,
        "recommended_environment": _recommended_environment(harness_probe, ready),
        "missing_prerequisites": missing,
        "safe_next_commands": _safe_next_commands(),
        "next_actions": _next_actions(ready),
        "blocked_commands": _blocked_commands(harness_probe, ready),
        "artifact_requirements": _artifact_requirements(),
        "harness_probe": harness_probe,
    }


def _missing_prerequisites(harness_probe: dict[str, Any]) -> list[str]:
    missing: list[str] = []
    for harness in harness_probe.get("harnesses", []):
        harness_name = harness.get("name", "unknown_harness")
        for check in harness.get("required_checks", []):
            if check.get("status") != "available":
                missing.append(f"{harness_name}:{check.get('id', 'unknown_check')}")
    return missing


def _recommended_environment(harness_probe: dict[str, Any], ready: bool) -> str:
    preferred = harness_probe.get("preferred_environment")
    if ready and preferred in {"current_machine", "local_worktree", "external_evaluation_environment"}:
        return str(preferred)
    if ready:
        return "local_worktree"
    return "external_evaluation_environment"


def _safe_next_commands() -> list[str]:
    return [
        "python scripts/benchmark_harness_probe.py --json",
        "python scripts/benchmark_proof_plan.py --json",
    ]


def _next_actions(ready: bool) -> list[str]:
    if ready:
        return [
            "prepare an official debug/small proof run in an isolated worktree before grading",
            "record command lines, configs, logs, reports, and limitations before publishing",
        ]
    return [
        "collect missing official harness prerequisites outside the product checkout",
        "rerun the read-only probe and proof plan after setup changes",
    ]


def _blocked_commands(harness_probe: dict[str, Any], ready: bool) -> list[str]:
    if ready:
        return []
    blocked: list[str] = []
    for harness in harness_probe.get("harnesses", []):
        blocked.extend(str(command) for command in harness.get("blocked_commands", []))
    return sorted(set(blocked))


def _artifact_requirements() -> list[str]:
    return [
        "command_lines",
        "resolved_config",
        "environment_manifest",
        "raw_logs",
        "raw_reports",
        "limitations_note",
        "official_scores_claimed=false",
    ]
