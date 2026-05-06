"""Read-only feasibility probes for official benchmark harnesses."""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any


CommandLookup = Callable[[str], str | None]


def build_official_harness_probe(
    *,
    mle_bench_repo: str | Path | None = None,
    paperbench_repo: str | Path | None = None,
    paperbench_data_dir: str | Path | None = None,
    env: Mapping[str, str] | None = None,
    command_lookup: CommandLookup | None = None,
) -> dict[str, Any]:
    """Return read-only readiness for official MLE-bench and PaperBench harnesses."""
    env_map = dict(os.environ if env is None else env)
    lookup = command_lookup or shutil.which
    harnesses = [
        _probe_mle_bench(
            repo=_path_from_value(mle_bench_repo or env_map.get("MLE_BENCH_REPO")),
            env=env_map,
            command_lookup=lookup,
        ),
        _probe_paperbench(
            repo=_path_from_value(paperbench_repo or env_map.get("PAPERBENCH_REPO")),
            data_dir=_path_from_value(paperbench_data_dir or env_map.get("PAPERBENCH_DATA_DIR")),
            env=env_map,
            command_lookup=lookup,
        ),
    ]
    blocking_issue_count = sum(
        1
        for harness in harnesses
        for check in harness["required_checks"]
        if check["status"] != "available"
    )
    return {
        "status": "ready" if blocking_issue_count == 0 else "needs_setup",
        "read_only": True,
        "official_scores_claimed": False,
        "harnesses": harnesses,
        "blocking_issue_count": blocking_issue_count,
        "next_actions": _next_actions(harnesses),
    }


def _probe_mle_bench(
    *,
    repo: Path | None,
    env: Mapping[str, str],
    command_lookup: CommandLookup,
) -> dict[str, Any]:
    checks = [
        _command_check("git", command_lookup),
        _command_check("git-lfs", command_lookup),
        _command_check("docker", command_lookup),
        _command_check("mlebench", command_lookup),
        _repo_check(
            "official_repo",
            repo,
            expected_children=["mlebench", "environment/Dockerfile", "experiments"],
            detail="Set MLE_BENCH_REPO or pass --mle-bench-repo.",
        ),
        _kaggle_credentials_check(env),
    ]
    return {
        "name": "mle_bench",
        "display_name": "MLE-bench official harness",
        "status": _status_from_checks(checks),
        "read_only": True,
        "official": True,
        "reference_url": "https://github.com/openai/mle-bench",
        "required_checks": checks,
        "optional_checks": [],
        "known_costs": [
            "Official competition data hydration can be large and long-running.",
            "This probe does not run mlebench prepare, Docker builds, grading, or downloads.",
        ],
        "safe_next_command": "python scripts/benchmark_harness_probe.py --json",
        "blocked_commands": [
            "mlebench prepare",
            "mlebench grade",
            "experiments/make_submission.py",
        ],
    }


def _probe_paperbench(
    *,
    repo: Path | None,
    data_dir: Path | None,
    env: Mapping[str, str],
    command_lookup: CommandLookup,
) -> dict[str, Any]:
    project_path = repo / "project" / "paperbench" if repo else None
    checks = [
        _command_check("git", command_lookup),
        _command_check("git-lfs", command_lookup),
        _command_check("uv", command_lookup),
        _command_check("docker", command_lookup),
        _repo_check(
            "official_repo",
            project_path,
            expected_children=["paperbench", "pyproject.toml"],
            detail="Set PAPERBENCH_REPO or pass --paperbench-repo.",
        ),
        _path_check(
            "official_data",
            data_dir,
            detail="Set PAPERBENCH_DATA_DIR or pass --paperbench-data-dir after hydrating official data.",
        ),
        _openai_credentials_check(env),
    ]
    optional_checks = [
        _command_check("nvidia-smi", command_lookup, required=False),
    ]
    return {
        "name": "paperbench",
        "display_name": "PaperBench official harness",
        "status": _status_from_checks(checks),
        "read_only": True,
        "official": True,
        "reference_url": "https://github.com/openai/frontier-evals/tree/main/project/paperbench",
        "required_checks": checks,
        "optional_checks": optional_checks,
        "known_costs": [
            "Official paper reproduction and grading can require containers, API credentials, and significant runtime.",
            "This probe does not run uv sync, Docker builds, grading, API calls, or data downloads.",
        ],
        "safe_next_command": "python scripts/benchmark_harness_probe.py --json",
        "blocked_commands": [
            "uv sync",
            "paperbench direct-submission grading",
            "Docker execution",
        ],
    }


def _command_check(
    command: str,
    command_lookup: CommandLookup,
    required: bool = True,
) -> dict[str, Any]:
    resolved = command_lookup(command)
    return {
        "id": f"command:{command}",
        "kind": "command",
        "required": required,
        "status": "available" if resolved else "missing",
        "command": command,
        "resolved": resolved,
    }


def _repo_check(
    check_id: str,
    path: Path | None,
    expected_children: list[str],
    detail: str,
) -> dict[str, Any]:
    check = _path_check(check_id, path, detail=detail)
    if check["status"] != "available":
        check["expected_children"] = expected_children
        return check
    missing = [child for child in expected_children if not (path / child).exists()]
    check["expected_children"] = expected_children
    check["missing_children"] = missing
    check["status"] = "available" if not missing else "missing"
    if missing:
        check["detail"] = f"Missing expected official harness files: {', '.join(missing)}"
    return check


def _path_check(
    check_id: str,
    path: Path | None,
    detail: str,
) -> dict[str, Any]:
    if path is None:
        return {
            "id": check_id,
            "kind": "path",
            "required": True,
            "status": "missing",
            "path": None,
            "detail": detail,
        }
    expanded = path.expanduser().resolve()
    return {
        "id": check_id,
        "kind": "path",
        "required": True,
        "status": "available" if expanded.exists() else "missing",
        "path": str(expanded),
        "detail": "found" if expanded.exists() else detail,
    }


def _kaggle_credentials_check(env: Mapping[str, str]) -> dict[str, Any]:
    has_env_pair = bool(env.get("KAGGLE_USERNAME") and env.get("KAGGLE_KEY"))
    kaggle_json = _kaggle_json_path(env)
    has_json = kaggle_json.exists()
    source = "env_pair" if has_env_pair else "kaggle_json" if has_json else None
    return {
        "id": "credentials:kaggle",
        "kind": "credential",
        "required": True,
        "status": "available" if source else "missing",
        "source": source,
        "detail": (
            "Kaggle credential source detected without exposing values."
            if source
            else "Provide KAGGLE_USERNAME/KAGGLE_KEY or a Kaggle API token file."
        ),
    }


def _openai_credentials_check(env: Mapping[str, str]) -> dict[str, Any]:
    source = (
        "GRADER_OPENAI_API_KEY"
        if env.get("GRADER_OPENAI_API_KEY")
        else "OPENAI_API_KEY"
        if env.get("OPENAI_API_KEY")
        else None
    )
    return {
        "id": "credentials:paperbench_grader",
        "kind": "credential",
        "required": True,
        "status": "available" if source else "missing",
        "source": source,
        "detail": (
            "Grader API credential source detected without exposing values."
            if source
            else "Provide GRADER_OPENAI_API_KEY or OPENAI_API_KEY for official grading."
        ),
    }


def _kaggle_json_path(env: Mapping[str, str]) -> Path:
    config_dir = env.get("KAGGLE_CONFIG_DIR")
    if config_dir:
        return Path(config_dir).expanduser() / "kaggle.json"
    home = env.get("HOME")
    return Path(home).expanduser() / ".kaggle" / "kaggle.json" if home else Path(".missing-kaggle-json")


def _path_from_value(value: str | Path | None) -> Path | None:
    if value is None or str(value).strip() == "":
        return None
    return Path(value)


def _status_from_checks(checks: list[dict[str, Any]]) -> str:
    return "ready" if all(check["status"] == "available" for check in checks) else "needs_setup"


def _next_actions(harnesses: list[dict[str, Any]]) -> list[str]:
    actions: list[str] = []
    for harness in harnesses:
        missing = [
            check
            for check in harness["required_checks"]
            if check["status"] != "available"
        ]
        if missing:
            labels = ", ".join(check["id"] for check in missing[:4])
            actions.append(f"{harness['name']}: resolve missing prerequisites: {labels}.")
    if not actions:
        actions.append("Prerequisites look ready; run an official debug/small proof path next.")
    return actions
