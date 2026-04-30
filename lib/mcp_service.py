"""Dependency-free MCP stdio service for ml-research-loop."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lib.fusion_service import (
    build_research_context,
    propose_hypotheses,
    read_paper_context,
    review_research_result,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SERVER_NAME = "ml-research-loop"
SERVER_VERSION = "0.1.0"
DEFAULT_PROTOCOL_VERSION = "2024-11-05"
MCP_CONTRACT_VERSION = "2026-04-30.preview.v1"
MCP_SCHEMA_VERSIONS = {
    "service_manifest": MCP_CONTRACT_VERSION,
    "tool_inputs": MCP_CONTRACT_VERSION,
    "tool_outputs": MCP_CONTRACT_VERSION,
    "runtime_artifacts": MCP_CONTRACT_VERSION,
}
MCP_COMPATIBILITY = {
    "status": "preview",
    "breaking_changes": "allowed only with a contract_version change",
    "client_requirement": "check contract_version before planning automated loops",
}
ALLOWED_ROOTS_ENV = "ML_RESEARCH_LOOP_ALLOWED_ROOTS"
REQUIRED_TOOLS = [
    "get_service_manifest",
    "research_task",
    "read_paper",
    "propose_hypotheses",
    "run_hypothesis_experiment",
    "review_research_results",
    "run_next_experiment_from_review",
    "get_experiment_status",
    "get_experiment_result",
    "get_experiment_logs",
    "run_ai_autoresearch",
]
TOOL_CONTRACT_DESCRIPTIONS = {
    "get_service_manifest": "Return the versioned MCP product and planner contract.",
    "research_task": "Return research context, evidence quality, cache metadata, and diagnostics.",
    "read_paper": "Return normalized paper evidence, findings, and experiment hypotheses.",
    "propose_hypotheses": "Convert research context into bounded experiment hypotheses.",
    "run_hypothesis_experiment": "Run bounded autoresearch validation for selected hypotheses.",
    "review_research_results": "Return experiment state, planner actions, and next-round patches.",
    "run_next_experiment_from_review": "Execute the proposed next task patch from a review payload.",
    "get_experiment_status": "Return progress metadata for a task from runtime artifacts.",
    "get_experiment_result": "Return the final task result payload from runtime artifacts.",
    "get_experiment_logs": "Return recent training log tails for debugging failed runs.",
    "run_ai_autoresearch": "Run explicit opt-in server-side LLM autoresearch.",
}


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
            "name": "get_service_manifest",
            "description": (
                "Return the MCP product manifest, client planner contract, "
                "recommended workflows, and release acceptance commands."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            },
        },
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
            "name": "run_ai_autoresearch",
            "description": (
                "Run the server-side LLM autoresearch loop. This is opt-in and uses "
                "the configured provider instead of relying on the MCP client model."
            ),
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
                    "llm_provider": {
                        "type": "string",
                        "enum": ["mock", "minimax", "openai"],
                        "description": "Server-side LLM provider. Use mock for deterministic tests.",
                        "default": "mock",
                    },
                    "llm_model": {
                        "type": "string",
                        "description": "Optional model name for providers that support model selection.",
                    },
                    "mock_response": {
                        "type": "object",
                        "description": "Fixed response used when llm_provider is mock.",
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
                "required": ["task_config", "llm_provider"],
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
        {
            "name": "get_experiment_logs",
            "description": "Return recent per-experiment training log tails for a task.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "runtime_root": {
                        "type": "string",
                        "description": "Optional runtime root. Used to find workdir/<task_id>/logs.",
                    },
                    "workspace": {
                        "type": "string",
                        "description": "Optional explicit workdir containing a logs/ directory.",
                    },
                    "tail_lines": {
                        "type": "integer",
                        "description": "Number of lines to return from each log file, capped at 500.",
                        "default": 80,
                    },
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "read_paper",
            "description": (
                "Read one paper by arXiv ID or URL and return source, evidence snippets, "
                "findings, and hypotheses for downstream experiments."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "identifier": {
                        "type": "string",
                        "description": "arXiv ID or arXiv URL.",
                    },
                    "objective": {
                        "type": "string",
                        "description": "Optional experiment objective used to frame findings.",
                    },
                },
                "required": ["identifier"],
                "additionalProperties": False,
            },
        },
        {
            "name": "research_task",
            "description": (
                "Start a research-planning step and return structured research context, "
                "including query_plan, findings, and source_rankings."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "objective": {"type": "string"},
                    "query": {"type": "string"},
                    "paper_limit": {"type": "integer", "default": 3},
                    "dataset_limit": {"type": "integer", "default": 3},
                    "github_limit": {"type": "integer", "default": 0},
                    "include_papers": {"type": "boolean", "default": True},
                    "include_hf_datasets": {"type": "boolean", "default": True},
                    "include_github_code": {"type": "boolean", "default": False},
                    "query_fanout": {
                        "type": "boolean",
                        "default": True,
                        "description": "Use query_plan variants when a backend returns too few sources.",
                    },
                    "cache_dir": {
                        "type": "string",
                        "description": "Optional directory for JSON research search cache.",
                    },
                },
                "required": ["objective"],
                "additionalProperties": False,
            },
        },
        {
            "name": "propose_hypotheses",
            "description": (
                "Convert research sources into rank-aware hypotheses for autoresearch validation."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "objective": {"type": "string"},
                    "sources": {
                        "type": "array",
                        "items": {"type": "object"},
                        "default": [],
                    },
                },
                "required": ["objective"],
                "additionalProperties": False,
            },
        },
        {
            "name": "run_hypothesis_experiment",
            "description": (
                "Run autoresearch for a task config that may include hypotheses, "
                "or continue from review_research_results via task_patch."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_config": {"type": "string"},
                    "workspace": {"type": "string"},
                    "runtime_root": {"type": "string"},
                    "research_context": {"type": "object"},
                    "hypotheses": {"type": "array", "items": {"type": "object"}},
                    "task_patch": {
                        "type": "object",
                        "description": (
                            "Optional next_task_patch from review_research_results. "
                            "Applies hyperparameter_space, sampling_constraints, budget, "
                            "program_md_overrides, or objective before running."
                        ),
                    },
                    "recommended_search_space": {
                        "type": "object",
                        "description": "Optional recommended_search_space from research_review.",
                    },
                    "max_experiments": {"type": "integer"},
                    "max_duration": {"type": "integer"},
                    "experiment_duration": {"type": "integer", "default": 300},
                    "python": {"type": "string"},
                    "verbose": {"type": "boolean", "default": False},
                },
                "required": ["task_config"],
                "additionalProperties": False,
            },
        },
        {
            "name": "review_research_results",
            "description": (
                "Read and review final autoresearch results, including hypothesis outcomes "
                "and next_task_patch for the following experiment round."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "runtime_root": {"type": "string"},
                    "workspace": {
                        "type": "string",
                        "description": (
                            "Optional workdir containing train.py/program.md for planner handoff."
                        ),
                    },
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "run_next_experiment_from_review",
            "description": (
                "Review a completed task, select code_change_plan.next_experiment_plan."
                "proposed_task_patch when available, and execute the next experiment."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_id": {"type": "string"},
                    "runtime_root": {"type": "string"},
                    "workspace": {
                        "type": "string",
                        "description": (
                            "Optional workdir containing train.py/program.md for planner handoff."
                        ),
                    },
                    "max_experiments": {"type": "integer"},
                    "max_duration": {"type": "integer"},
                    "experiment_duration": {
                        "type": "integer",
                        "description": "Per-experiment timeout in seconds.",
                    },
                    "python": {"type": "string"},
                    "verbose": {"type": "boolean", "default": False},
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
        },
    ]


def get_service_manifest_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return the product contract a Codex/Claude client should follow."""
    return {
        "service_name": SERVER_NAME,
        "version": SERVER_VERSION,
        "contract_version": MCP_CONTRACT_VERSION,
        "schema_versions": dict(MCP_SCHEMA_VERSIONS),
        "compatibility": dict(MCP_COMPATIBILITY),
        "product_status": "preview",
        "architecture": "hybrid_client_planner_server_executor",
        "execution_sandbox": execution_sandbox_policy(),
        "client_model_role": (
            "Codex/Claude acts as the planner: understand the user goal, choose MCP "
            "tools, inspect experiment_state, and decide the next code or parameter move."
        ),
        "mcp_server_role": (
            "The MCP service executes research lookup, hypothesis generation, bounded "
            "experiments, result review, artifact reads, and log summaries."
        ),
        "server_side_llm": {
            "default": "disabled",
            "tool": "run_ai_autoresearch",
            "rule": "Use only when the user explicitly requests server-side autonomous runs.",
        },
        "planning_signals": [
            "cache",
            "evidence_quality",
            "provider_coverage",
            "source_rankings",
            "retrieval_diagnostics",
            "research_evidence_gate",
            "dataset_profile",
            "code_change_plan",
            "code_change_plan.next_experiment_plan",
            "code_change_plan.next_experiment_plan.proposed_task_patch",
            "code_change_plan.next_experiment_plan.dry_run_validation",
            "planner_actions",
            "next_round.task_patch",
        ],
        "required_tools": list(REQUIRED_TOOLS),
        "tool_contracts": build_tool_contracts(REQUIRED_TOOLS),
        "recommended_workflows": [
            {
                "name": "research_to_validation",
                "tools": [
                    "research_task",
                    "propose_hypotheses",
                    "run_hypothesis_experiment",
                    "review_research_results",
                    "run_next_experiment_from_review",
                ],
                "handoff": (
                    "Prefer run_next_experiment_from_review when proposed_task_patch is "
                    "acceptable; otherwise feed experiment_state.next_round.task_patch "
                    "into run_hypothesis_experiment."
                ),
            },
            {
                "name": "failure_debugging",
                "tools": [
                    "review_research_results",
                    "get_experiment_logs",
                    "run_hypothesis_experiment",
                ],
                "handoff": "Inspect failure_summary before expanding the search space.",
            },
        ],
        "runtime_artifacts": [
            "tasks/<task_id>.json",
            "results/<task_id>.json",
            "results/<task_id>-progress.json",
            "workdir/<task_id>/program.md",
            "workdir/<task_id>/logs/*.log",
            "snapshots/<task_id>/<experiment_id>/",
        ],
        "acceptance_commands": [
            "python3 scripts/mcp_client_acceptance.py",
            "python3 scripts/mcp_golden_path.py --max-experiments 1 --experiment-duration 30",
            "python3 scripts/mcp_multi_round_demo.py --rounds 2 --max-experiments 1",
            "python3 scripts/mcp_auto_next_demo.py --max-experiments 1 --experiment-duration 30",
            "python3 scripts/mcp_real_data_demo.py --max-experiments 1 --experiment-duration 30",
        ],
    }


def build_tool_contracts(tool_names: list[str]) -> dict[str, dict[str, str]]:
    """Return the public contract metadata clients should pin for each tool."""
    return {
        tool_name: {
            "input_schema_version": MCP_CONTRACT_VERSION,
            "output_schema_version": MCP_CONTRACT_VERSION,
            "stability": "preview",
            "description": TOOL_CONTRACT_DESCRIPTIONS[tool_name],
        }
        for tool_name in tool_names
    }


def run_fresh_demo_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Run the repeatable synthetic demo in a subprocess."""
    _assert_execution_paths_allowed(arguments, require_task_config=False)
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
    return _run_autoresearch_subprocess(
        arguments=arguments,
        script_name="autoresearch_run.py",
        ai_mode=False,
    )


def _run_autoresearch_subprocess(
    arguments: dict[str, Any],
    script_name: str,
    ai_mode: bool,
) -> dict[str, Any]:
    task_config = arguments.get("task_config")
    if not task_config:
        raise MCPToolError({"status": "failed", "error": "task_config is required"})
    _assert_execution_paths_allowed(arguments, require_task_config=True)

    experiment_duration = int(arguments.get("experiment_duration", 300))
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / script_name),
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
    if ai_mode:
        llm_provider = str(arguments.get("llm_provider") or "mock")
        if llm_provider == "mock":
            cmd.append("--mock")
            if arguments.get("mock_response") is not None:
                cmd.extend([
                    "--mock-response",
                    json.dumps(arguments["mock_response"], ensure_ascii=False),
                ])
        else:
            cmd.extend(["--llm-provider", llm_provider])
            if arguments.get("llm_model"):
                cmd.extend(["--llm-model", str(arguments["llm_model"])])

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


def run_ai_autoresearch_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Run server-side LLM autoresearch in a subprocess."""
    return _run_autoresearch_subprocess(
        arguments=arguments,
        script_name="ai_autoresearch_run.py",
        ai_mode=True,
    )


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


def get_experiment_logs_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return recent log tails for a task workspace."""
    task_id = _required_string(arguments, "task_id")
    tail_lines = min(500, max(1, int(arguments.get("tail_lines", 80))))
    workspace = _workspace_root(arguments, task_id)
    logs_dir = workspace / "logs"
    logs = []
    if logs_dir.exists():
        for log_file in sorted(logs_dir.glob("*.log")):
            text = log_file.read_text(encoding="utf-8", errors="replace")
            logs.append({
                "file": str(log_file),
                "tail": "\n".join(text.splitlines()[-tail_lines:]),
                "size_bytes": log_file.stat().st_size,
            })
    return {
        "task_id": task_id,
        "workspace": str(workspace),
        "logs_dir": str(logs_dir),
        "log_count": len(logs),
        "logs": logs,
    }


def research_task_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Collect real research context for a user objective."""
    objective = _required_string(arguments, "objective")
    return build_research_context(
        objective=objective,
        query=arguments.get("query"),
        paper_limit=int(arguments.get("paper_limit", 3)),
        dataset_limit=int(arguments.get("dataset_limit", 3)),
        github_limit=int(arguments.get("github_limit", 0)),
        include_papers=bool(arguments.get("include_papers", True)),
        include_hf_datasets=bool(arguments.get("include_hf_datasets", True)),
        include_github_code=bool(arguments.get("include_github_code", False)),
        cache_dir=arguments.get("cache_dir"),
        query_fanout=bool(arguments.get("query_fanout", True)),
    )


def read_paper_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Read one paper into a research brief fragment."""
    return read_paper_context(
        identifier=_required_string(arguments, "identifier"),
        objective=arguments.get("objective"),
    )


def propose_hypotheses_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Generate deterministic hypotheses from supplied research sources."""
    objective = _required_string(arguments, "objective")
    sources = arguments.get("sources", [])
    if not isinstance(sources, list):
        raise MCPToolError({"status": "failed", "error": "sources must be a list"})
    return propose_hypotheses(objective, sources)


def run_hypothesis_experiment_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Run autoresearch for a hypothesis-backed task config."""
    if not any(
        key in arguments
        for key in ("research_context", "hypotheses", "task_patch", "recommended_search_space")
    ):
        return run_autoresearch_tool(arguments)

    _assert_execution_paths_allowed(arguments, require_task_config=True)
    injected_config = _write_hypothesis_task_config(arguments)
    run_arguments = dict(arguments)
    run_arguments["task_config"] = str(injected_config)
    run_arguments.pop("research_context", None)
    run_arguments.pop("hypotheses", None)
    run_arguments.pop("task_patch", None)
    run_arguments.pop("recommended_search_space", None)
    return run_autoresearch_tool(run_arguments)


def review_research_results_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Read final results for a hypothesis-backed task."""
    task_id = _required_string(arguments, "task_id")
    payload = {"task_id": task_id}
    if arguments.get("runtime_root"):
        payload["runtime_root"] = arguments["runtime_root"]
    return review_research_result(
        get_experiment_result_tool(payload),
        workspace=arguments.get("workspace"),
        runtime_root=arguments.get("runtime_root"),
    )


def run_next_experiment_from_review_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute the next patch proposed by review_research_results."""
    _assert_execution_paths_allowed(arguments, require_task_config=False)
    review_payload = review_research_results_tool(arguments)
    experiment_state = (
        review_payload.get("experiment_state")
        if isinstance(review_payload.get("experiment_state"), dict)
        else {}
    )
    selected_patch, selected_patch_source = _select_review_task_patch(experiment_state)
    run_arguments = _run_next_action_arguments(experiment_state)
    if not run_arguments.get("task_config"):
        raise MCPToolError({
            "status": "failed",
            "error": "review payload does not contain a runnable next experiment action",
        })
    run_arguments["task_patch"] = selected_patch
    for key in ("max_experiments", "max_duration", "experiment_duration", "python", "verbose"):
        if key in arguments:
            run_arguments[key] = arguments[key]
    run_payload = run_hypothesis_experiment_tool(run_arguments)
    return {
        "status": run_payload.get("status"),
        "selected_patch_source": selected_patch_source,
        "selected_patch": selected_patch,
        "review": review_payload,
        "run": run_payload,
    }


def _select_review_task_patch(experiment_state: dict[str, Any]) -> tuple[dict[str, Any], str]:
    code_change_plan = (
        experiment_state.get("code_change_plan")
        if isinstance(experiment_state.get("code_change_plan"), dict)
        else {}
    )
    next_experiment_plan = (
        code_change_plan.get("next_experiment_plan")
        if isinstance(code_change_plan.get("next_experiment_plan"), dict)
        else {}
    )
    proposed_patch = next_experiment_plan.get("proposed_task_patch")
    if isinstance(proposed_patch, dict) and proposed_patch:
        return proposed_patch, "proposed_task_patch"
    next_round = (
        experiment_state.get("next_round")
        if isinstance(experiment_state.get("next_round"), dict)
        else {}
    )
    task_patch = next_round.get("task_patch")
    if isinstance(task_patch, dict) and task_patch:
        return task_patch, "next_round.task_patch"
    raise MCPToolError({
        "status": "failed",
        "error": "review payload does not contain a proposed task patch",
    })


def _run_next_action_arguments(experiment_state: dict[str, Any]) -> dict[str, Any]:
    planner_actions = experiment_state.get("planner_actions")
    if not isinstance(planner_actions, list):
        return {}
    for action in planner_actions:
        if not isinstance(action, dict):
            continue
        if action.get("tool") != "run_hypothesis_experiment":
            continue
        arguments = action.get("arguments")
        if isinstance(arguments, dict):
            return dict(arguments)
    return {}


TOOL_HANDLERS: dict[str, ToolHandler] = {
    "get_service_manifest": get_service_manifest_tool,
    "run_fresh_demo": run_fresh_demo_tool,
    "run_autoresearch": run_autoresearch_tool,
    "run_ai_autoresearch": run_ai_autoresearch_tool,
    "get_experiment_status": get_experiment_status_tool,
    "get_experiment_result": get_experiment_result_tool,
    "get_experiment_logs": get_experiment_logs_tool,
    "read_paper": read_paper_tool,
    "research_task": research_task_tool,
    "propose_hypotheses": propose_hypotheses_tool,
    "run_hypothesis_experiment": run_hypothesis_experiment_tool,
    "review_research_results": review_research_results_tool,
    "run_next_experiment_from_review": run_next_experiment_from_review_tool,
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


def execution_sandbox_policy() -> dict[str, Any]:
    """Return the path policy enforced for MCP tools that execute code."""
    return {
        "status": "enforced",
        "allowed_roots_env": ALLOWED_ROOTS_ENV,
        "default_allowed_roots": ["project_root", "ML_RESEARCH_LOOP_ROOT"],
        "rules": [
            "execution task_config/runtime_root/workspace paths must be inside allowed roots",
            "workspace must stay inside runtime_root when both are provided",
        ],
    }


def _assert_execution_paths_allowed(
    arguments: dict[str, Any],
    require_task_config: bool,
) -> None:
    runtime_root = _safe_runtime_root(arguments)
    if require_task_config or arguments.get("task_config"):
        task_config = Path(_required_string(arguments, "task_config")).expanduser().resolve()
        _assert_path_allowed(task_config, "task_config")

    workspace_value = arguments.get("workspace")
    if workspace_value:
        workspace = Path(str(workspace_value)).expanduser().resolve()
        if not _is_relative_to(workspace, runtime_root):
            raise MCPToolError(_path_security_error(
                field="workspace",
                path=workspace,
                error="workspace must stay inside runtime_root for execution tools",
            ))
        _assert_path_allowed(workspace, "workspace")


def _safe_runtime_root(arguments: dict[str, Any]) -> Path:
    root = _runtime_root(arguments)
    _assert_path_allowed(root, "runtime_root")
    return root


def _assert_path_allowed(path: Path, field: str) -> None:
    if any(_is_relative_to(path, root) for root in _allowed_execution_roots()):
        return
    raise MCPToolError(_path_security_error(
        field=field,
        path=path,
        error="execution path is outside allowed roots",
    ))


def _path_security_error(field: str, path: Path, error: str) -> dict[str, Any]:
    return {
        "status": "failed",
        "error": error,
        "field": field,
        "path": str(path),
        "allowed_roots": [str(root) for root in _allowed_execution_roots()],
        "security_policy": execution_sandbox_policy(),
    }


def _allowed_execution_roots() -> list[Path]:
    roots = [PROJECT_ROOT]
    configured_runtime = os.environ.get("ML_RESEARCH_LOOP_ROOT")
    if configured_runtime:
        roots.append(Path(configured_runtime))
    configured_allowed = os.environ.get(ALLOWED_ROOTS_ENV)
    if configured_allowed:
        roots.extend(
            Path(item)
            for item in configured_allowed.split(os.pathsep)
            if item.strip()
        )

    resolved: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        resolved_root = root.expanduser().resolve()
        key = str(resolved_root)
        if key in seen:
            continue
        seen.add(key)
        resolved.append(resolved_root)
    return resolved


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _runtime_root(arguments: dict[str, Any]) -> Path:
    configured = arguments.get("runtime_root") or os.environ.get("ML_RESEARCH_LOOP_ROOT")
    if configured:
        return Path(str(configured)).expanduser().resolve()
    return PROJECT_ROOT


def _workspace_root(arguments: dict[str, Any], task_id: str) -> Path:
    configured = arguments.get("workspace")
    if configured:
        return Path(str(configured)).expanduser().resolve()
    return _runtime_root(arguments) / "workdir" / task_id


def _write_hypothesis_task_config(arguments: dict[str, Any]) -> Path:
    task_config = Path(_required_string(arguments, "task_config")).expanduser().resolve()
    task_payload = _read_json_file(task_config)

    task_patch = arguments.get("task_patch")
    recommended_search_space = arguments.get("recommended_search_space")
    if task_patch is not None:
        if not isinstance(task_patch, dict):
            raise MCPToolError({"status": "failed", "error": "task_patch must be an object"})
        _apply_task_patch(task_payload, task_patch)
    if recommended_search_space is not None:
        if not isinstance(recommended_search_space, dict):
            raise MCPToolError({
                "status": "failed",
                "error": "recommended_search_space must be an object",
            })
        _apply_task_patch(task_payload, _task_patch_from_recommended_search_space(recommended_search_space))

    research_context = arguments.get("research_context")
    if research_context is not None:
        if not isinstance(research_context, dict):
            raise MCPToolError({"status": "failed", "error": "research_context must be an object"})
        task_payload["research_context"] = research_context

    hypotheses = arguments.get("hypotheses")
    if hypotheses is None and isinstance(research_context, dict):
        hypotheses = research_context.get("hypotheses")
    if hypotheses is not None:
        if not isinstance(hypotheses, list):
            raise MCPToolError({"status": "failed", "error": "hypotheses must be a list"})
        task_payload["hypotheses"] = hypotheses

    task_id = str(task_payload.get("task_id") or task_config.stem)
    task_dir = _safe_runtime_root(arguments) / "tasks"
    task_dir.mkdir(parents=True, exist_ok=True)
    injected_config = task_dir / f"{task_id}-hypothesis.json"
    injected_config.write_text(
        json.dumps(task_payload, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    return injected_config


def _apply_task_patch(task_payload: dict[str, Any], task_patch: dict[str, Any]) -> None:
    allowed_keys = {
        "objective",
        "hyperparameter_space",
        "sampling_constraints",
        "budget",
        "program_md_overrides",
    }
    for key, value in task_patch.items():
        if key not in allowed_keys:
            continue
        if key in {"budget", "program_md_overrides"}:
            existing = task_payload.get(key)
            if isinstance(existing, dict) and isinstance(value, dict):
                task_payload[key] = {**existing, **value}
            else:
                task_payload[key] = value
        else:
            task_payload[key] = value


def _task_patch_from_recommended_search_space(search_space: dict[str, Any]) -> dict[str, Any]:
    patch: dict[str, Any] = {}
    parameter_hints = search_space.get("parameter_hints", {})
    avoid_params = search_space.get("avoid_params", [])
    if parameter_hints:
        patch["hyperparameter_space"] = parameter_hints
    if avoid_params:
        patch["sampling_constraints"] = {"avoid_params": avoid_params}
    return patch


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
