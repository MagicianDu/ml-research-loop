"""Dependency-free MCP stdio service for ml-research-loop."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_NAME = "ml-research-loop"
SERVER_VERSION = "0.1.0"
DEFAULT_PROTOCOL_VERSION = "2024-11-05"


class MCPToolError(RuntimeError):
    """Raised when an MCP tool should return an MCP tool-level error."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self.payload = payload
        super().__init__(str(payload))


ToolHandler = Callable[[dict[str, Any]], dict[str, Any]]


def tool_definitions() -> list[dict[str, Any]]:
    """Return the tools exposed through MCP."""
    return [
        {
            "name": "run_fresh_demo",
            "description": (
                "Run a fresh, isolated synthetic autoresearch demo. "
                "Use this to verify the service end-to-end."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "runtime_root": {
                        "type": "string",
                        "description": "Optional isolated runtime root for demo artifacts.",
                    },
                    "max_experiments": {
                        "type": "integer",
                        "description": "Maximum number of demo experiments.",
                        "default": 1,
                    },
                    "experiment_duration": {
                        "type": "integer",
                        "description": "Per-experiment timeout in seconds.",
                        "default": 30,
                    },
                    "python": {
                        "type": "string",
                        "description": "Optional Python executable used by train.py.",
                    },
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "run_autoresearch",
            "description": "Run an autoresearch task JSON config and return the final result payload.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_config": {
                        "type": "string",
                        "description": "Path to a task JSON definition.",
                    },
                    "workspace": {
                        "type": "string",
                        "description": "Optional workdir for generated train.py/program.md.",
                    },
                    "runtime_root": {
                        "type": "string",
                        "description": "Optional runtime root for tasks/results/logs/snapshots.",
                    },
                    "max_experiments": {"type": "integer"},
                    "max_duration": {
                        "type": "integer",
                        "description": "Maximum wall-clock budget in minutes.",
                    },
                    "experiment_duration": {
                        "type": "integer",
                        "description": "Per-experiment timeout in seconds.",
                        "default": 300,
                    },
                    "python": {
                        "type": "string",
                        "description": "Optional Python executable used by train.py.",
                    },
                    "verbose": {"type": "boolean", "default": False},
                },
                "required": ["task_config"],
                "additionalProperties": False,
            },
        },
        {
            "name": "get_experiment_status",
            "description": "Read results/<task_id>-progress.json from a runtime root.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "runtime_root": {
                        "type": "string",
                        "description": "Optional runtime root. Defaults to this project checkout.",
                    },
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "get_experiment_result",
            "description": "Read results/<task_id>.json from a runtime root.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "runtime_root": {
                        "type": "string",
                        "description": "Optional runtime root. Defaults to this project checkout.",
                    },
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
        },
    ]


def run_fresh_demo_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Run the repeatable synthetic demo in a subprocess."""
    max_experiments = int(arguments.get("max_experiments", 1))
    experiment_duration = int(arguments.get("experiment_duration", 30))
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "fresh_demo.py"),
        "--max-experiments",
        str(max_experiments),
        "--experiment-duration",
        str(experiment_duration),
    ]

    runtime_root = arguments.get("runtime_root")
    if runtime_root:
        cmd.extend(["--runtime-root", str(runtime_root)])

    proc = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        env=_subprocess_env(arguments),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=subprocess_timeout(
            arguments,
            experiment_duration=experiment_duration,
            default_experiments=1,
        ),
    )
    if proc.returncode != 0:
        raise MCPToolError({
            "status": "failed",
            "returncode": proc.returncode,
            "stdout": proc.stdout,
        })

    payload = _parse_last_json_object(proc.stdout)
    payload["stdout"] = proc.stdout.strip()
    return payload


def run_autoresearch_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Run an autoresearch task config in a subprocess."""
    task_config = arguments.get("task_config")
    if not task_config:
        raise MCPToolError({"status": "failed", "error": "task_config is required"})

    experiment_duration = int(arguments.get("experiment_duration", 300))
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "autoresearch_run.py"),
        "--task-config",
        str(task_config),
        "--experiment-duration",
        str(experiment_duration),
    ]
    if arguments.get("workspace"):
        cmd.extend(["--workspace", str(arguments["workspace"])])
    if arguments.get("max_experiments") is not None:
        cmd.extend(["--max-experiments", str(arguments["max_experiments"])])
    if arguments.get("max_duration") is not None:
        cmd.extend(["--max-duration", str(arguments["max_duration"])])
    if arguments.get("verbose"):
        cmd.append("--verbose")

    proc = subprocess.run(
        cmd,
        cwd=PROJECT_ROOT,
        env=_subprocess_env(arguments),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=subprocess_timeout(
            arguments,
            experiment_duration=experiment_duration,
            default_experiments=None,
        ),
    )

    payload = _parse_autoresearch_stdout(proc.stdout)
    payload["returncode"] = proc.returncode
    payload["stdout"] = proc.stdout.strip()
    result_file = payload.get("result_file")
    if result_file and Path(result_file).exists():
        payload["result"] = _read_json_file(Path(result_file))
    if proc.returncode != 0:
        raise MCPToolError({"status": "failed", **payload})
    return payload


def get_experiment_status_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return the progress JSON for a task."""
    task_id = _required_string(arguments, "task_id")
    progress_file = _runtime_root(arguments) / "results" / f"{task_id}-progress.json"
    if not progress_file.exists():
        return {"task_id": task_id, "status": "not_started", "progress_file": str(progress_file)}

    payload = _read_json_file(progress_file)
    payload.setdefault("task_id", task_id)
    payload.setdefault("progress_file", str(progress_file))
    return payload


def get_experiment_result_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return the final result JSON for a task."""
    task_id = _required_string(arguments, "task_id")
    result_file = _runtime_root(arguments) / "results" / f"{task_id}.json"
    if not result_file.exists():
        return {"task_id": task_id, "status": "not_ready", "result_file": str(result_file)}

    payload = _read_json_file(result_file)
    payload.setdefault("result_file", str(result_file))
    return payload


TOOL_HANDLERS: dict[str, ToolHandler] = {
    "run_fresh_demo": run_fresh_demo_tool,
    "run_autoresearch": run_autoresearch_tool,
    "get_experiment_status": get_experiment_status_tool,
    "get_experiment_result": get_experiment_result_tool,
}


def handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    """Handle one JSON-RPC MCP request object."""
    method = request.get("method")
    request_id = request.get("id")

    if isinstance(method, str) and method.startswith("notifications/"):
        return None

    try:
        if method == "initialize":
            params = request.get("params") if isinstance(request.get("params"), dict) else {}
            protocol_version = params.get("protocolVersion", DEFAULT_PROTOCOL_VERSION)
            return _success_response(
                request_id,
                {
                    "protocolVersion": protocol_version,
                    "serverInfo": {"name": SERVER_NAME, "version": SERVER_VERSION},
                    "capabilities": {"tools": {}},
                },
            )
        if method == "tools/list":
            return _success_response(request_id, {"tools": tool_definitions()})
        if method == "tools/call":
            return _handle_tools_call(request_id, request.get("params"))
        if method == "ping":
            return _success_response(request_id, {})
        return _error_response(request_id, -32601, f"Method not found: {method}")
    except Exception as exc:
        return _error_response(request_id, -32603, str(exc))


def _handle_tools_call(request_id: Any, params: Any) -> dict[str, Any]:
    if not isinstance(params, dict):
        return _error_response(request_id, -32602, "tools/call params must be an object")

    tool_name = params.get("name")
    arguments = params.get("arguments", {})
    if not isinstance(arguments, dict):
        return _error_response(request_id, -32602, "tools/call arguments must be an object")
    if not isinstance(tool_name, str):
        return _error_response(request_id, -32602, "tools/call name must be a string")

    handler = TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return _success_response(
            request_id,
            _tool_content({"error": f"Unknown MCP tool: {tool_name}"}, is_error=True),
        )

    try:
        payload = handler(arguments)
    except MCPToolError as exc:
        return _success_response(request_id, _tool_content(exc.payload, is_error=True))

    return _success_response(request_id, _tool_content(payload))


def _tool_content(payload: dict[str, Any] | str, is_error: bool = False) -> dict[str, Any]:
    text = payload if isinstance(payload, str) else json.dumps(payload, ensure_ascii=False)
    result: dict[str, Any] = {"content": [{"type": "text", "text": text}]}
    if is_error:
        result["isError"] = True
    return result


def _success_response(request_id: Any, result: dict[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _error_response(request_id: Any, code: int, message: str) -> dict[str, Any]:
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": code, "message": message},
    }


def _subprocess_env(arguments: dict[str, Any]) -> dict[str, str]:
    env = dict(os.environ)
    env["PYTHONPATH"] = _pythonpath()
    env["ML_RESEARCH_LOOP_PYTHON"] = str(
        arguments.get("python") or env.get("ML_RESEARCH_LOOP_PYTHON") or sys.executable
    )
    if arguments.get("runtime_root"):
        env["ML_RESEARCH_LOOP_ROOT"] = str(arguments["runtime_root"])
    return env


def subprocess_timeout(
    arguments: dict[str, Any],
    experiment_duration: int,
    default_experiments: int | None,
) -> int | None:
    """Compute a subprocess timeout from explicit MCP arguments."""
    if arguments.get("max_duration") is not None:
        return max(120, int(arguments["max_duration"]) * 60 + 90)

    if arguments.get("max_experiments") is not None:
        experiment_count = int(arguments["max_experiments"])
    elif default_experiments is not None:
        experiment_count = default_experiments
    else:
        return None

    return max(120, experiment_duration * experiment_count + 90)


def _pythonpath() -> str:
    parts = [str(PROJECT_ROOT)]
    site_packages_root = PROJECT_ROOT / ".venv" / "lib"
    if site_packages_root.exists():
        parts.extend(str(path) for path in sorted(site_packages_root.glob("python*/site-packages")))
    if os.environ.get("PYTHONPATH"):
        parts.append(os.environ["PYTHONPATH"])
    return os.pathsep.join(parts)


def _runtime_root(arguments: dict[str, Any]) -> Path:
    configured = arguments.get("runtime_root") or os.environ.get("ML_RESEARCH_LOOP_ROOT")
    if configured:
        return Path(str(configured)).expanduser().resolve()
    return PROJECT_ROOT


def _required_string(arguments: dict[str, Any], key: str) -> str:
    value = arguments.get(key)
    if not isinstance(value, str) or not value:
        raise MCPToolError({"status": "failed", "error": f"{key} is required"})
    return value


def _read_json_file(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MCPToolError({"status": "failed", "error": f"Invalid JSON in {path}: {exc}"}) from exc
    if not isinstance(payload, dict):
        raise MCPToolError({"status": "failed", "error": f"Expected JSON object in {path}"})
    return payload


def _parse_last_json_object(stdout: str) -> dict[str, Any]:
    for line in reversed(stdout.splitlines()):
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            return payload
    raise MCPToolError({"status": "failed", "error": "No JSON payload found", "stdout": stdout})


def _parse_autoresearch_stdout(stdout: str) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    for line in stdout.splitlines():
        key, sep, value = line.partition("=")
        if sep and key in {"RESULT_FILE", "STATUS", "BEST_VAL", "EXPERIMENTS"}:
            normalized_key = key.lower()
            if normalized_key == "experiments":
                try:
                    payload[normalized_key] = int(value)
                except ValueError:
                    payload[normalized_key] = value
            elif normalized_key == "best_val":
                try:
                    payload[normalized_key] = float(value)
                except ValueError:
                    payload[normalized_key] = value
            elif normalized_key == "result_file":
                payload["result_file"] = value
            else:
                payload[normalized_key] = value
    return payload
