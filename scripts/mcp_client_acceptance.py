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
EXPECTED_CONTRACT_VERSION = "2026-04-30.preview.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run stdio MCP client acceptance checks")
    parser.add_argument("--python", default=sys.executable, help="Python executable for server")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument(
        "--expected-contract-version",
        default=EXPECTED_CONTRACT_VERSION,
        help="MCP service contract version expected by this client.",
    )
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
    compatibility_check = check_manifest_compatibility(
        manifest=manifest,
        tool_names=tool_names,
        expected_contract_version=args.expected_contract_version,
    )
    missing_required_tools = compatibility_check["missing_required_tools"]
    missing_tool_contracts = compatibility_check["missing_tool_contracts"]
    passed = (
        server_info.get("name") == "ml-research-loop"
        and compatibility_check["status"] == "compatible"
        and manifest.get("architecture") == "hybrid_client_planner_server_executor"
    )
    payload = {
        "status": "passed" if passed else "failed",
        "server_info": server_info,
        "tool_count": len(tool_names),
        "missing_required_tools": missing_required_tools,
        "missing_tool_contracts": missing_tool_contracts,
        "compatibility_check": compatibility_check,
        "manifest": manifest,
    }
    print(json.dumps(payload, ensure_ascii=False))
    return 0 if passed else 1


def check_manifest_compatibility(
    *,
    manifest: dict[str, Any],
    tool_names: list[str],
    expected_contract_version: str = EXPECTED_CONTRACT_VERSION,
) -> dict[str, Any]:
    """Return a client-facing compatibility and migration report."""
    required_tools = [
        str(tool_name)
        for tool_name in manifest.get("required_tools", [])
    ]
    tool_contracts = (
        manifest.get("tool_contracts")
        if isinstance(manifest.get("tool_contracts"), dict)
        else {}
    )
    recommended_skills = [
        str(skill_name)
        for skill_name in manifest.get("recommended_skills", [])
    ]
    skill_contracts = (
        manifest.get("skill_contracts")
        if isinstance(manifest.get("skill_contracts"), dict)
        else {}
    )
    schema_versions = (
        manifest.get("schema_versions")
        if isinstance(manifest.get("schema_versions"), dict)
        else {}
    )
    actual_contract_version = manifest.get("contract_version")
    missing_required_tools = sorted(set(required_tools) - set(tool_names))
    missing_tool_contracts = sorted(set(required_tools) - set(tool_contracts))
    missing_skill_contracts = sorted(set(recommended_skills) - set(skill_contracts))
    schema_mismatches = [
        {
            "schema": schema_name,
            "expected": expected_contract_version,
            "actual": schema_versions.get(schema_name),
        }
        for schema_name in (
            "service_manifest",
            "tool_inputs",
            "tool_outputs",
            "runtime_artifacts",
        )
        if schema_versions.get(schema_name) != expected_contract_version
    ]
    tool_contract_mismatches = _tool_contract_mismatches(
        required_tools=required_tools,
        tool_contracts=tool_contracts,
        expected_contract_version=expected_contract_version,
    )
    skill_contract_mismatches = _skill_contract_mismatches(
        recommended_skills=recommended_skills,
        skill_contracts=skill_contracts,
        expected_contract_version=expected_contract_version,
    )
    version_mismatch = actual_contract_version != expected_contract_version
    migration_required = bool(
        version_mismatch
        or missing_required_tools
        or missing_tool_contracts
        or missing_skill_contracts
        or schema_mismatches
        or tool_contract_mismatches
        or skill_contract_mismatches
    )
    return {
        "status": "incompatible" if migration_required else "compatible",
        "expected_contract_version": expected_contract_version,
        "actual_contract_version": actual_contract_version,
        "missing_required_tools": missing_required_tools,
        "missing_tool_contracts": missing_tool_contracts,
        "missing_skill_contracts": missing_skill_contracts,
        "schema_mismatches": schema_mismatches,
        "tool_contract_mismatches": tool_contract_mismatches,
        "skill_contract_mismatches": skill_contract_mismatches,
        "migration_required": migration_required,
        "migration_hints": _migration_hints(
            version_mismatch=version_mismatch,
            missing_required_tools=missing_required_tools,
            missing_tool_contracts=missing_tool_contracts,
            missing_skill_contracts=missing_skill_contracts,
            schema_mismatches=schema_mismatches,
            tool_contract_mismatches=tool_contract_mismatches,
            skill_contract_mismatches=skill_contract_mismatches,
        ),
    }


def _tool_contract_mismatches(
    *,
    required_tools: list[str],
    tool_contracts: dict[str, Any],
    expected_contract_version: str,
) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    for tool_name in required_tools:
        contract = tool_contracts.get(tool_name)
        if not isinstance(contract, dict):
            continue
        for field in ("input_schema_version", "output_schema_version"):
            if contract.get(field) != expected_contract_version:
                mismatches.append({
                    "tool": tool_name,
                    "field": field,
                    "expected": expected_contract_version,
                    "actual": contract.get(field),
                })
    return mismatches


def _skill_contract_mismatches(
    *,
    recommended_skills: list[str],
    skill_contracts: dict[str, Any],
    expected_contract_version: str,
) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    for skill_name in recommended_skills:
        contract = skill_contracts.get(skill_name)
        if not isinstance(contract, dict):
            continue
        if contract.get("contract_version") != expected_contract_version:
            mismatches.append({
                "skill": skill_name,
                "field": "contract_version",
                "expected": expected_contract_version,
                "actual": contract.get("contract_version"),
            })
    return mismatches


def _migration_hints(
    *,
    version_mismatch: bool,
    missing_required_tools: list[str],
    missing_tool_contracts: list[str],
    missing_skill_contracts: list[str],
    schema_mismatches: list[dict[str, Any]],
    tool_contract_mismatches: list[dict[str, Any]],
    skill_contract_mismatches: list[dict[str, Any]],
) -> list[str]:
    hints: list[str] = []
    if version_mismatch:
        hints.append(
            "contract_version mismatch; refresh the MCP server package or pin a compatible client."
        )
    if missing_required_tools:
        hints.append(
            "missing required MCP tools: " + ", ".join(missing_required_tools)
        )
    if missing_tool_contracts:
        hints.append(
            "missing tool contract metadata: " + ", ".join(missing_tool_contracts)
        )
    if missing_skill_contracts:
        hints.append(
            "missing skill contract metadata: " + ", ".join(missing_skill_contracts)
        )
    if schema_mismatches:
        hints.append(
            "schema_versions mismatch; stop automated planning until the client is migrated."
        )
    if tool_contract_mismatches:
        hints.append(
            "tool contract schema mismatch; regenerate client tool adapters before running loops."
        )
    if skill_contract_mismatches:
        hints.append(
            "skill contract version mismatch; reinstall or refresh the client skill package."
        )
    return hints


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
