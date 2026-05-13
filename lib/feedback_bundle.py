"""Preview feedback diagnostics bundle helpers."""

from __future__ import annotations

import json
import os
import platform
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib import mcp_service


BUNDLE_VERSION = "2026-05-06.preview-feedback.v1"
MAX_ARTIFACTS = 20
MAX_LOG_FILES = 8

TOKEN_PATTERNS = [
    re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"),
    re.compile(r"github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-(?:proj-)?[A-Za-z0-9_-]{10,}"),
    re.compile(
        r"(?i)\b(api[_-]?key|token|secret|password)\s*=\s*([^\s,;]+)",
    ),
]


def redact_text(text: str, home: Path | None = None) -> str:
    """Redact machine-local paths and common API token shapes from text."""
    home_path = str((home or Path.home()).expanduser())
    redacted = text.replace(home_path, "~")
    for pattern in TOKEN_PATTERNS:
        if pattern.groups >= 2:
            redacted = pattern.sub(lambda match: f"{match.group(1)}=[REDACTED_TOKEN]", redacted)
        else:
            redacted = pattern.sub("[REDACTED_TOKEN]", redacted)
    return redacted


def build_feedback_bundle(
    *,
    project_root: Path,
    runtime_root: Path | None = None,
    task_id: str | None = None,
    log_lines: int = 80,
    python_executable: str = sys.executable,
    include_git: bool = True,
) -> dict[str, Any]:
    """Build a redacted diagnostic payload that users can attach to preview issues."""
    project_root = project_root.expanduser().resolve()
    runtime_root = runtime_root.expanduser().resolve() if runtime_root else None
    diagnostics: list[str] = []
    task_payload = _collect_task(runtime_root, task_id, diagnostics)
    bundle = {
        "bundle_version": BUNDLE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "service": {
            "server_name": mcp_service.SERVER_NAME,
            "server_version": mcp_service.SERVER_VERSION,
            "contract_version": mcp_service.MCP_CONTRACT_VERSION,
        },
        "environment": _collect_environment(python_executable),
        "git": _collect_git(project_root) if include_git else {},
        "runtime": {
            "runtime_root": str(runtime_root) if runtime_root else None,
            "exists": runtime_root.exists() if runtime_root else False,
        },
        "task": task_payload,
        "artifacts": _collect_artifacts(runtime_root, task_id),
        "logs": _collect_logs(runtime_root, log_lines),
        "diagnostics": diagnostics,
    }
    return _redact_value(bundle)


def write_feedback_bundle(bundle: dict[str, Any], output_dir: Path) -> dict[str, Any]:
    """Write feedback bundle JSON and markdown files."""
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "feedback-bundle.json"
    markdown_path = output_dir / "feedback-bundle.md"

    sanitized = _redact_value(bundle)
    json_path.write_text(
        json.dumps(sanitized, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_feedback_markdown(sanitized), encoding="utf-8")
    return {
        "status": "written",
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
    }


def render_feedback_markdown(bundle: dict[str, Any]) -> str:
    """Render a compact human-readable bundle summary."""
    bundle = _redact_value(bundle)
    service = bundle.get("service", {})
    environment = bundle.get("environment", {})
    git = bundle.get("git", {})
    runtime = bundle.get("runtime", {})
    task = bundle.get("task", {})
    artifacts = bundle.get("artifacts", {})
    logs = bundle.get("logs", [])
    diagnostics = bundle.get("diagnostics", [])

    lines = [
        "# ML Research Loop Preview Feedback Bundle",
        "",
        f"- bundle_version: `{bundle.get('bundle_version')}`",
        f"- generated_at: `{bundle.get('generated_at')}`",
        f"- contract_version: `{service.get('contract_version')}`",
        f"- python: `{environment.get('python_version')}`",
        f"- python_executable: `{environment.get('python_executable')}`",
        f"- git_branch: `{git.get('branch')}`",
        f"- git_commit: `{git.get('commit')}`",
        f"- git_dirty: `{git.get('dirty')}`",
        f"- runtime_root: `{runtime.get('runtime_root')}`",
        f"- task_id: `{task.get('task_id')}`",
        f"- task_status: `{task.get('status')}`",
        "",
        "## Result Artifacts",
        "",
    ]
    for path in artifacts.get("results", []):
        lines.append(f"- `{path}`")
    if not artifacts.get("results"):
        lines.append("- none")

    lines.extend(["", "## Diagnostics", ""])
    if diagnostics:
        lines.extend(f"- {item}" for item in diagnostics)
    else:
        lines.append("- none")

    lines.extend(["", "## Log Tails", ""])
    if logs:
        for item in logs:
            lines.extend([
                f"### `{item.get('path')}`",
                "",
                "```text",
                item.get("tail", ""),
                "```",
                "",
            ])
    else:
        lines.append("- none")

    return "\n".join(lines).rstrip() + "\n"


def _collect_environment(python_executable: str) -> dict[str, Any]:
    return {
        "python_executable": python_executable,
        "python_version": platform.python_version(),
        "platform": platform.platform(),
        "cwd": str(Path.cwd()),
        "env": {
            "ML_RESEARCH_LOOP_ROOT": os.environ.get("ML_RESEARCH_LOOP_ROOT"),
            "ML_RESEARCH_LOOP_ALLOWED_ROOTS": os.environ.get("ML_RESEARCH_LOOP_ALLOWED_ROOTS"),
            "ML_RESEARCH_LOOP_PYTHON": os.environ.get("ML_RESEARCH_LOOP_PYTHON"),
            "PYTHONPATH": os.environ.get("PYTHONPATH"),
        },
    }


def _collect_git(project_root: Path) -> dict[str, Any]:
    return {
        "branch": _git_output(project_root, ["rev-parse", "--abbrev-ref", "HEAD"]),
        "commit": _git_output(project_root, ["rev-parse", "--short", "HEAD"]),
        "dirty": bool(_git_output(project_root, ["status", "--porcelain"])),
        "remote": _git_output(project_root, ["remote", "get-url", "origin"]),
    }


def _git_output(project_root: Path, args: list[str]) -> str | None:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=project_root,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout.strip()


def _collect_task(
    runtime_root: Path | None,
    task_id: str | None,
    diagnostics: list[str],
) -> dict[str, Any]:
    if not task_id:
        return {}
    payload: dict[str, Any] = {"task_id": task_id}
    if runtime_root is None:
        diagnostics.append("task_id was provided, but runtime_root is missing")
        return payload

    result_file = runtime_root / "results" / f"{task_id}.json"
    payload["result_file"] = str(result_file)
    if not result_file.exists():
        diagnostics.append(f"result file not found for task_id={task_id}")
        return payload

    try:
        result = json.loads(result_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        diagnostics.append(f"result file is not valid JSON: {exc}")
        return payload

    payload.update({
        "status": result.get("status"),
        "best_result": result.get("best_result"),
        "summary": result.get("summary"),
        "error": result.get("error"),
    })
    return payload


def _collect_artifacts(runtime_root: Path | None, task_id: str | None) -> dict[str, list[str]]:
    if runtime_root is None or not runtime_root.exists():
        return {"tasks": [], "results": [], "workdirs": [], "snapshots": []}

    artifact_patterns = {
        "tasks": ["tasks", f"{task_id}.json"] if task_id else ["tasks", "*.json"],
        "results": ["results", f"{task_id}.json"] if task_id else ["results", "*.json"],
        "workdirs": ["workdir", task_id] if task_id else ["workdir", "*"],
        "snapshots": ["snapshots", task_id] if task_id else ["snapshots", "*"],
    }
    artifacts: dict[str, list[str]] = {}
    for label, parts in artifact_patterns.items():
        root = runtime_root / parts[0]
        pattern = parts[1]
        if not root.exists():
            artifacts[label] = []
            continue
        matches = sorted(root.glob(pattern))
        artifacts[label] = [str(path) for path in matches[:MAX_ARTIFACTS]]
    return artifacts


def _collect_logs(runtime_root: Path | None, log_lines: int) -> list[dict[str, str]]:
    if runtime_root is None or not runtime_root.exists():
        return []
    candidates = sorted({
        *runtime_root.glob("logs/*.log"),
        *runtime_root.glob("workdir/**/logs/*.log"),
    })
    logs = []
    for path in candidates[:MAX_LOG_FILES]:
        text = path.read_text(encoding="utf-8", errors="replace")
        lines = text.splitlines()
        logs.append({
            "path": str(path),
            "tail": "\n".join(lines[-max(1, log_lines):]),
        })
    return logs


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact_value(item) for key, item in value.items()}
    return value
