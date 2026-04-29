#!/usr/bin/env python3
"""Verify the MCP server through the same stdio path real clients use."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run stdio MCP client acceptance checks")
    parser.add_argument("--python", default=sys.executable, help="Python executable for server")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    project_root = args.project_root.expanduser().resolve()
    env = _client_env(project_root, args.python)
    server = subprocess.Popen(
        [args.python, str(project_root / "scripts" / "mcp_server.py")],
        cwd=project_root,
        env=env,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        init_response = _send_request(
            server,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2024-11-05"},
            },
        )
        tools_response = _send_request(
            server,
            {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
        )
        manifest_response = _send_request(
            server,
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "get_service_manifest",
                    "arguments": {},
                },
            },
        )
    finally:
        _stop_server(server)

    server_info = init_response["result"]["serverInfo"]
    tool_names = sorted(tool["name"] for tool in tools_response["result"]["tools"])
    manifest = json.loads(manifest_response["result"]["content"][0]["text"])
    missing_required_tools = sorted(set(manifest["required_tools"]) - set(tool_names))
    passed = (
        server_info.get("name") == "ml-research-loop"
        and manifest.get("architecture") == "hybrid_client_planner_server_executor"
        and not missing_required_tools
    )
    payload = {
        "status": "passed" if passed else "failed",
        "server_info": server_info,
        "tool_count": len(tool_names),
        "missing_required_tools": missing_required_tools,
        "manifest": manifest,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if passed else 1


def _send_request(server: subprocess.Popen[str], request: dict[str, Any]) -> dict[str, Any]:
    if server.stdin is None or server.stdout is None:
        raise RuntimeError("MCP server pipes are not available")
    server.stdin.write(json.dumps(request, ensure_ascii=False) + "\n")
    server.stdin.flush()
    line = server.stdout.readline()
    if not line:
        stderr = server.stderr.read() if server.stderr is not None else ""
        raise RuntimeError(f"MCP server returned no response. stderr={stderr}")
    response = json.loads(line)
    if "error" in response:
        raise RuntimeError(json.dumps(response["error"], ensure_ascii=False))
    return response


def _stop_server(server: subprocess.Popen[str]) -> None:
    if server.stdin is not None:
        server.stdin.close()
    try:
        server.wait(timeout=2)
    except subprocess.TimeoutExpired:
        server.terminate()
        server.wait(timeout=5)


def _client_env(project_root: Path, python: str) -> dict[str, str]:
    env = dict(os.environ)
    pythonpath_parts = [str(project_root)]
    pythonpath_parts.extend(str(path) for path in _site_packages_paths(project_root))
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    env["ML_RESEARCH_LOOP_PYTHON"] = env.get("ML_RESEARCH_LOOP_PYTHON", python)
    return env


def _site_packages_paths(project_root: Path) -> list[Path]:
    site_packages_root = project_root / ".venv" / "lib"
    if not site_packages_root.exists():
        return []
    return sorted(site_packages_root.glob("python*/site-packages"))


if __name__ == "__main__":
    raise SystemExit(main())
