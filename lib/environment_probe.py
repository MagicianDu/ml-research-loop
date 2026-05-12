"""Probe research workspace readiness and repair actions."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any


SKIPPED_DIR_NAMES = {".git", ".venv", ".demo_runs", "__pycache__"}
SECRET_NAME_MARKERS = ("TOKEN", "SECRET", "KEY")


def probe_research_environment(
    workspace: Path,
    required_files: list[str],
    required_commands: list[str],
) -> dict[str, Any]:
    """Return a machine-readable readiness report for a research workspace."""

    resolved_workspace = workspace.expanduser().resolve()
    repair_plan: list[dict[str, Any]] = []

    workspace_exists = resolved_workspace.is_dir()
    if not workspace_exists:
        repair_plan.append(
            {
                "kind": "create_workspace",
                "path": str(resolved_workspace),
                "message": "Create or mount the research workspace directory.",
            }
        )

    invalid_required_files = _invalid_required_files(required_files)
    missing_files = _missing_required_files(
        resolved_workspace,
        required_files,
        workspace_exists,
    )
    for file_path in invalid_required_files:
        repair_plan.append(
            {
                "kind": "fix_required_file_path",
                "path": file_path,
                "message": (
                    "Use a normalized workspace-relative required file path "
                    "that does not escape the workspace."
                ),
            }
        )
    for file_path in missing_files:
        repair_plan.append(
            {
                "kind": "create_or_mount_file",
                "path": file_path,
                "message": "Create the required file or mount it relative to the workspace.",
            }
        )

    missing_commands = [command for command in required_commands if shutil.which(command) is None]
    for command in missing_commands:
        repair_plan.append(
            {
                "kind": "install_command",
                "command": command,
                "message": "Install the command or make it discoverable on PATH.",
            }
        )

    secret_risk_files = _find_secret_risk_files(resolved_workspace) if workspace_exists else []
    for file_path in secret_risk_files:
        repair_plan.append(
            {
                "kind": "redact_or_ignore_secret_file",
                "path": file_path,
                "message": "Redact this file from outputs or add it to an ignore policy.",
            }
        )

    blocking_issues = (
        (not workspace_exists)
        or bool(invalid_required_files)
        or bool(missing_files)
        or bool(missing_commands)
    )

    return {
        "status": "blocked" if blocking_issues else "ready",
        "workspace": str(resolved_workspace),
        "invalid_required_files": invalid_required_files,
        "missing_files": missing_files,
        "missing_commands": missing_commands,
        "secret_risk_files": secret_risk_files,
        "repair_plan": repair_plan,
        "official_scores_claimed": False,
    }


def _missing_required_files(
    workspace: Path,
    required_files: list[str],
    workspace_exists: bool,
) -> list[str]:
    if not workspace_exists:
        return [
            file_path
            for file_path in required_files
            if _workspace_relative_path(file_path) is not None
        ]
    return [
        file_path
        for file_path in required_files
        if (relative_path := _workspace_relative_path(file_path)) is not None
        and not (workspace / relative_path).exists()
    ]


def _invalid_required_files(required_files: list[str]) -> list[str]:
    return [
        file_path
        for file_path in required_files
        if _workspace_relative_path(file_path) is None
    ]


def _workspace_relative_path(file_path: str) -> Path | None:
    path = Path(file_path)
    if path.is_absolute():
        return None
    normalized_parts: list[str] = []
    for part in path.parts:
        if part in {"", "."}:
            continue
        if part == "..":
            return None
        normalized_parts.append(part)
    if not normalized_parts:
        return None
    return Path(*normalized_parts)


def _find_secret_risk_files(workspace: Path) -> list[str]:
    risk_files: list[str] = []
    for path in _iter_workspace_files(workspace):
        if _should_skip(path, workspace):
            continue
        if _is_secret_risk_name(path.name):
            risk_files.append(path.relative_to(workspace).as_posix())
    return risk_files


def _iter_workspace_files(workspace: Path) -> list[Path]:
    candidates: list[Path] = []
    for child in sorted(workspace.iterdir()):
        if child.name in SKIPPED_DIR_NAMES:
            continue
        if child.is_file():
            candidates.append(child)
        elif child.is_dir():
            candidates.extend(
                path
                for path in sorted(child.rglob("*"))
                if not _should_skip(path, workspace) and path.is_file()
            )
    return candidates


def _should_skip(path: Path, workspace: Path) -> bool:
    try:
        relative_parts = path.relative_to(workspace).parts
    except ValueError:
        return True
    return any(part in SKIPPED_DIR_NAMES for part in relative_parts)


def _is_secret_risk_name(name: str) -> bool:
    if name == ".env":
        return True
    upper_name = name.upper()
    return any(marker in upper_name for marker in SECRET_NAME_MARKERS)
