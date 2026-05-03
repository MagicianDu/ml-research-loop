"""Dependency-free MCP stdio service for ml-research-loop."""

from __future__ import annotations

import ast
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from collections.abc import Callable
from pathlib import Path
from typing import Any

from lib.fusion_service import (
    build_research_context,
    propose_hypotheses,
    read_paper_context,
    review_research_result,
)
from lib.research_components import parse_search_region


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
TRAINING_ERROR_TYPES = {
    "training_startup_failed": "startup_failed",
    "training_timeout": "timeout",
    "training_nonzero_exit": "nonzero_exit",
    "training_missing_metric": "missing_metric",
}
REQUIRED_TOOLS = [
    "get_service_manifest",
    "research_task",
    "read_paper",
    "propose_hypotheses",
    "run_hypothesis_experiment",
    "review_research_results",
    "run_client_patch_experiment",
    "apply_client_code_patch",
    "run_next_experiment_from_review",
    "get_experiment_status",
    "get_experiment_result",
    "get_experiment_logs",
    "list_runtime_artifacts",
    "archive_runtime_artifacts",
    "clean_runtime_artifacts",
    "run_ai_autoresearch",
]
TOOL_CONTRACT_DESCRIPTIONS = {
    "get_service_manifest": "Return the versioned MCP product and planner contract.",
    "research_task": "Return research context, evidence quality, cache metadata, and diagnostics.",
    "read_paper": "Return normalized paper evidence, findings, and experiment hypotheses.",
    "propose_hypotheses": "Convert research context into bounded experiment hypotheses.",
    "run_hypothesis_experiment": "Run bounded autoresearch validation for selected hypotheses.",
    "review_research_results": "Return experiment state, planner actions, and next-round patches.",
    "run_client_patch_experiment": "Validate a client-generated SEARCH REGION proposal and run it as a bounded experiment.",
    "apply_client_code_patch": "Apply a guarded client-generated unified diff inside a workspace with rollback.",
    "run_next_experiment_from_review": "Execute the proposed next task patch from a review payload.",
    "get_experiment_status": "Return progress metadata for a task from runtime artifacts.",
    "get_experiment_result": "Return the final task result payload from runtime artifacts.",
    "get_experiment_logs": "Return recent training log tails for debugging failed runs.",
    "list_runtime_artifacts": "List runtime tasks, results, workdirs, snapshots, and archives.",
    "archive_runtime_artifacts": "Move one task's runtime artifacts into archive/.",
    "clean_runtime_artifacts": "Delete one task's runtime artifacts after explicit confirmation.",
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
            "name": "list_runtime_artifacts",
            "description": "List runtime artifact counts and discovered task IDs.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "runtime_root": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "archive_runtime_artifacts",
            "description": "Archive one task's runtime artifacts under archive/<task-id>-<timestamp>.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "runtime_root": {"type": "string"},
                    "task_id": {"type": "string"},
                },
                "required": ["task_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "clean_runtime_artifacts",
            "description": "Delete one task's runtime artifacts. Requires confirm=true.",
            "inputSchema": {
                "type": "object",
                "properties": {
                    "runtime_root": {"type": "string"},
                    "task_id": {"type": "string"},
                    "confirm": {"type": "boolean", "default": False},
                },
                "required": ["task_id", "confirm"],
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
            "name": "run_client_patch_experiment",
            "description": (
                "Validate a Codex/Claude-generated single-parameter SEARCH REGION "
                "proposal, convert it to a bounded task_patch, run autoresearch, "
                "and optionally return a post-run review and loop decision."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task_config": {"type": "string"},
                    "workspace": {
                        "type": "string",
                        "description": "Workdir containing the current train.py SEARCH REGION.",
                    },
                    "runtime_root": {"type": "string"},
                    "change_proposal": {
                        "type": "object",
                        "description": (
                            "Client-generated proposal with change_type, target, "
                            "current_value, proposed_value, reason, and confidence."
                        ),
                    },
                    "max_experiments": {"type": "integer"},
                    "max_duration": {"type": "integer"},
                    "experiment_duration": {"type": "integer", "default": 300},
                    "python": {"type": "string"},
                    "verbose": {"type": "boolean", "default": False},
                    "include_final_review": {
                        "type": "boolean",
                        "default": False,
                        "description": (
                            "When true, review the post-run result and return a stop/continue "
                            "loop decision."
                        ),
                    },
                },
                "required": ["task_config", "workspace", "change_proposal"],
                "additionalProperties": False,
            },
        },
        {
            "name": "apply_client_code_patch",
            "description": (
                "Apply a Codex/Claude-generated unified diff to files under a workspace. "
                "The server preflights paths and hunks, writes only inside the workspace, "
                "runs Python syntax checks by default, and rolls back on failure."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "workspace": {
                        "type": "string",
                        "description": "Workspace root that owns the files in the patch.",
                    },
                    "runtime_root": {
                        "type": "string",
                        "description": "Optional runtime root. Workspace must stay inside it.",
                    },
                    "patch": {
                        "type": "string",
                        "description": "Unified diff using workspace-relative a/ and b/ paths.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional client-facing reason for this patch.",
                    },
                    "allowed_files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional allowlist of workspace-relative files.",
                    },
                    "run_syntax_check": {
                        "type": "boolean",
                        "default": True,
                        "description": "Compile changed Python files after applying the patch.",
                    },
                    "test_command": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": (
                            "Optional argv to run from the workspace after syntax checks. "
                            "Failures roll back the patch."
                        ),
                    },
                    "test_timeout_seconds": {
                        "type": "integer",
                        "default": 60,
                        "description": "Timeout for test_command.",
                    },
                    "task_id": {
                        "type": "string",
                        "description": (
                            "Optional task id used when include_post_patch_review is true."
                        ),
                    },
                    "include_post_patch_review": {
                        "type": "boolean",
                        "default": False,
                        "description": (
                            "When true, call review_research_results after a successful patch."
                        ),
                    },
                    "initial_review": {
                        "type": "object",
                        "description": (
                            "Optional pre-patch review payload for metric-aware loop_decision."
                        ),
                    },
                },
                "required": ["workspace", "patch"],
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
                    "include_final_review": {
                        "type": "boolean",
                        "default": False,
                        "description": (
                            "When true, review the post-run result and return a stop/continue "
                            "loop decision."
                        ),
                    },
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
            "cache.cache_scope",
            "cache.freshness_seconds",
            "evidence_quality",
            "evidence_quality.source_class_counts",
            "evidence_citations.source_trace",
            "source.metadata.source_id",
            "provider_coverage",
            "source_rankings",
            "retrieval_diagnostics",
            "research_evidence_gate",
            "dataset_profile",
            "experiment_tree",
            "loop_policy",
            "reproduction.readiness",
            "execution_metadata",
            "code_change_plan",
            "code_change_plan.next_experiment_plan",
            "code_change_plan.next_experiment_plan.proposed_task_patch",
            "code_change_plan.next_experiment_plan.dry_run_validation",
            "code_change_plan.next_experiment_plan.diff_preview",
            "code_change_plan.next_experiment_plan.execution_guardrails",
            "run_next_experiment_from_review.final_review",
            "run_next_experiment_from_review.loop_decision",
            "run_client_patch_experiment.patch_execution",
            "run_client_patch_experiment.loop_decision",
            "apply_client_code_patch.patch_execution",
            "apply_client_code_patch.post_patch_review",
            "apply_client_code_patch.loop_decision",
            "planner_actions",
            "next_round.task_patch",
        ],
        "upstream_patterns": {
            "aide": {
                "integration_mode": "architecture_pattern",
                "enabled_features": ["experiment_tree", "best_node_tracking", "loop_policy"],
                "direct_dependency": False,
            },
            "paperbench": {
                "integration_mode": "architecture_pattern",
                "enabled_features": ["reproduction_spec", "rubric_grade_report"],
                "direct_dependency": False,
            },
        },
        "execution_metadata_contract": {
            "required_fields": [
                "started_at",
                "finished_at",
                "wall_time_seconds",
                "python_executable",
                "timeout_policy",
                "execution_sandbox",
                "sandbox_roots",
                "artifact_retention",
            ],
            "timeout_policy_fields": [
                "timeout_enforced",
                "subprocess_timeout_seconds",
                "experiment_duration_seconds",
                "max_experiments",
                "max_duration_minutes",
                "test_timeout_seconds",
            ],
        },
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
                    "run_client_patch_experiment",
                    "apply_client_code_patch",
                ],
                "handoff": (
                    "Prefer run_next_experiment_from_review when proposed_task_patch is "
                    "acceptable; use apply_client_code_patch only for explicit client-generated "
                    "code diffs that need workspace mutation and rollback."
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
            {
                "name": "client_patch_optimization",
                "tools": [
                    "review_research_results",
                    "run_client_patch_experiment",
                    "apply_client_code_patch",
                    "review_research_results",
                ],
                "handoff": (
                    "Use when the client model wants to adjust one SEARCH REGION "
                    "parameter itself or apply a bounded code diff. Parameter-only "
                    "moves should use task_patch_only; code diffs must pass preflight "
                    "and syntax checks."
                ),
            },
        ],
        "runtime_artifacts": [
            "tasks/<task_id>.json",
            "results/<task_id>.json",
            "results/<task_id>-progress.json",
            "workdir/<task_id>/program.md",
            "workdir/<task_id>/logs/*.log",
            "snapshots/<task_id>/<experiment_id>/",
            "archive/<task_id>-<timestamp>/",
        ],
        "acceptance_commands": [
            "python3 scripts/mcp_client_acceptance.py",
            "python3 scripts/mcp_golden_path.py --max-experiments 1 --experiment-duration 30",
            "python3 scripts/mcp_multi_round_demo.py --rounds 2 --max-experiments 1",
            "python3 scripts/mcp_auto_next_demo.py --max-experiments 1 --experiment-duration 30",
            "python3 scripts/mcp_client_patch_demo.py --max-experiments 1 --experiment-duration 30",
            "python3 scripts/mcp_provider_quality_benchmark.py",
            "python3 scripts/mcp_real_task_code_benchmark.py --max-experiments 1 --experiment-duration 30",
            "python3 scripts/mcp_real_data_demo.py --max-experiments 1 --experiment-duration 30",
            "python3 scripts/mcp_reproduction_demo.py --max-experiments 1 --experiment-duration 30 --json",
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
    started_at = _utc_now()
    start_time = time.monotonic()
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

    timeout_seconds = subprocess_timeout(
        arguments,
        experiment_duration=experiment_duration,
        default_experiments=1,
    )
    proc = run_mcp_subprocess(
        cmd,
        cwd=PROJECT_ROOT,
        env=_subprocess_env(arguments),
        timeout_seconds=timeout_seconds,
    )
    if proc.returncode != 0:
        raise MCPToolError({
            "status": "failed",
            "error_type": "nonzero_exit",
            "returncode": proc.returncode,
            "stdout": proc.stdout,
        })

    payload = _parse_last_json_object(proc.stdout)
    payload["stdout"] = proc.stdout.strip()
    payload["execution_metadata"] = _execution_metadata(
        arguments,
        started_at=started_at,
        start_time=start_time,
        command=cmd,
        timeout_seconds=timeout_seconds,
        experiment_duration=experiment_duration,
        default_experiments=1,
        task_id=str(payload.get("task_id") or "fresh-demo"),
    )
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
    started_at = _utc_now()
    start_time = time.monotonic()
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

    timeout_seconds = subprocess_timeout(
        arguments,
        experiment_duration=experiment_duration,
        default_experiments=None,
    )
    proc = run_mcp_subprocess(
        cmd,
        cwd=PROJECT_ROOT,
        env=_subprocess_env(arguments),
        timeout_seconds=timeout_seconds,
    )

    payload = _parse_autoresearch_stdout(proc.stdout)
    payload["returncode"] = proc.returncode
    payload["stdout"] = proc.stdout.strip()
    result_file = payload.get("result_file")
    if result_file and Path(result_file).exists():
        payload["result"] = _read_json_file(Path(result_file))
    if proc.returncode != 0:
        raise MCPToolError({"status": "failed", "error_type": "nonzero_exit", **payload})
    training_error_type = _training_error_type_from_payload(payload)
    if training_error_type:
        raise MCPToolError({"status": "failed", "error_type": training_error_type, **payload})
    payload["execution_metadata"] = _execution_metadata(
        arguments,
        started_at=started_at,
        start_time=start_time,
        command=cmd,
        timeout_seconds=timeout_seconds,
        experiment_duration=experiment_duration,
        default_experiments=None,
        task_id=_task_id_from_run_payload(payload) or _task_id_from_task_config(arguments),
        workspace=arguments.get("workspace"),
    )
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


def list_runtime_artifacts_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return artifact counts and task IDs for a runtime root."""
    runtime_root = _safe_runtime_root(arguments)
    artifacts = {
        kind: _artifact_dir_summary(runtime_root / kind)
        for kind in ("tasks", "results", "workdir", "snapshots", "archive")
    }
    return {
        "runtime_root": str(runtime_root),
        "task_ids": _runtime_task_ids(runtime_root),
        "artifacts": artifacts,
    }


def archive_runtime_artifacts_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Move one task's artifacts into archive/ without deleting the archive."""
    runtime_root = _safe_runtime_root(arguments)
    task_id = _required_string(arguments, "task_id")
    archive_root = runtime_root / "archive" / f"{task_id}-{_archive_timestamp()}"
    moved_groups = _move_task_artifact_groups(
        groups=_task_artifact_groups(runtime_root, task_id),
        destination_root=archive_root,
    )
    return {
        "status": "archived",
        "runtime_root": str(runtime_root),
        "task_id": task_id,
        "archive_root": str(archive_root),
        "archived_count": moved_groups,
    }


def clean_runtime_artifacts_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Delete one task's runtime artifacts after explicit confirmation."""
    if arguments.get("confirm") is not True:
        raise MCPToolError({
            "status": "failed",
            "error": "confirm=true is required to clean runtime artifacts",
        })
    runtime_root = _safe_runtime_root(arguments)
    task_id = _required_string(arguments, "task_id")
    deleted_groups = _delete_task_artifact_groups(_task_artifact_groups(runtime_root, task_id))
    return {
        "status": "cleaned",
        "runtime_root": str(runtime_root),
        "task_id": task_id,
        "deleted_count": deleted_groups,
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


def run_client_patch_experiment_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Validate and run a client-generated single-parameter patch proposal."""
    started_at = _utc_now()
    start_time = time.monotonic()
    _assert_execution_paths_allowed(arguments, require_task_config=True)
    workspace = Path(_required_string(arguments, "workspace")).expanduser().resolve()
    proposal = _required_change_proposal(arguments)
    patch_execution = _validate_client_patch_proposal(workspace, proposal)
    initial_review = _initial_review_for_client_patch(arguments)

    run_arguments = {
        key: arguments[key]
        for key in (
            "task_config",
            "workspace",
            "runtime_root",
            "max_experiments",
            "max_duration",
            "experiment_duration",
            "python",
            "verbose",
        )
        if key in arguments
    }
    run_arguments["task_patch"] = patch_execution["task_patch"]
    run_payload = run_hypothesis_experiment_tool(run_arguments)
    payload = {
        "status": run_payload.get("status"),
        "patch_execution": patch_execution,
        "run": run_payload,
    }
    if arguments.get("include_final_review"):
        task_id = _task_id_from_run_payload(run_payload) or _task_id_from_task_config(arguments)
        review_arguments = _review_arguments_for_task(arguments, task_id)
        final_review = review_research_results_tool(review_arguments)
        if initial_review:
            payload["initial_review"] = initial_review
        payload["final_review"] = final_review
        payload["loop_decision"] = build_loop_decision(
            initial_review=initial_review or _review_seed_from_run(run_payload, arguments),
            final_review=final_review,
        )
    payload["execution_metadata"] = _execution_metadata(
        arguments,
        started_at=started_at,
        start_time=start_time,
        timeout_seconds=subprocess_timeout(
            arguments,
            experiment_duration=_int_or_none(arguments.get("experiment_duration")) or 300,
            default_experiments=None,
        ),
        experiment_duration=_int_or_none(arguments.get("experiment_duration")),
        default_experiments=None,
        task_id=_task_id_from_run_payload(run_payload) or _task_id_from_task_config(arguments),
        workspace=workspace,
    )
    return payload


def apply_client_code_patch_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Apply a guarded client-generated unified diff inside a workspace."""
    started_at = _utc_now()
    start_time = time.monotonic()
    _assert_execution_paths_allowed(arguments, require_task_config=False)
    workspace = Path(_required_string(arguments, "workspace")).expanduser().resolve()
    patch_text = _required_string(arguments, "patch")
    run_syntax_check = bool(arguments.get("run_syntax_check", True))
    allowed_files = _normalized_allowed_patch_files(arguments.get("allowed_files"))
    test_command = _normalized_test_command(arguments.get("test_command"))
    test_timeout_seconds = _normalized_test_timeout(arguments.get("test_timeout_seconds", 60))
    include_post_patch_review = bool(arguments.get("include_post_patch_review"))
    execution = _base_code_patch_execution(patch_text)

    file_patches = _parse_client_unified_diff(patch_text)
    planned_changes = _preflight_client_code_patch(
        workspace=workspace,
        file_patches=file_patches,
        allowed_files=allowed_files,
    )
    changed_files = sorted(planned_changes)
    execution["changed_files"] = changed_files
    execution["preflight"] = {
        "status": "passed",
        "checked_files": changed_files,
    }

    backups = {
        relative_path: (workspace / relative_path).read_text(encoding="utf-8")
        for relative_path in changed_files
    }
    for relative_path, new_text in planned_changes.items():
        target_file = workspace / relative_path
        target_file.write_text(new_text, encoding="utf-8")
    execution["apply"] = {
        "status": "applied",
        "changed_files": changed_files,
    }

    if run_syntax_check:
        syntax_check = _syntax_check_changed_python_files(workspace, changed_files)
        execution["syntax_check"] = syntax_check
        if syntax_check["status"] != "passed":
            _rollback_client_code_patch(workspace, backups)
            execution["rollback"] = {
                "performed": True,
                "restored_files": sorted(backups),
            }
            raise MCPToolError({
                "status": "failed",
                "error_type": "syntax_check_failed",
                "error": syntax_check["error"],
                "patch_execution": execution,
            })
    else:
        execution["syntax_check"] = {
            "status": "skipped",
            "checked_files": [],
        }

    test_check = _run_client_code_patch_test_command(
        workspace=workspace,
        command=test_command,
        timeout_seconds=test_timeout_seconds,
        env=_subprocess_env(arguments),
    )
    execution["test_check"] = test_check
    if test_check["status"] != "passed" and test_check["status"] != "skipped":
        _rollback_client_code_patch(workspace, backups)
        execution["rollback"] = {
            "performed": True,
            "restored_files": sorted(backups),
        }
        raise MCPToolError({
            "status": "failed",
            "error_type": "test_check_failed",
            "error": test_check["error"],
            "patch_execution": execution,
        })

    payload = {
        "status": "applied",
        "patch_execution": execution,
        "execution_metadata": _execution_metadata(
            arguments,
            started_at=started_at,
            start_time=start_time,
            timeout_seconds=None,
            test_timeout_seconds=test_timeout_seconds,
            workspace=workspace,
        ),
    }
    if include_post_patch_review:
        task_id = _required_string(arguments, "task_id")
        review_arguments = {
            "task_id": task_id,
            "workspace": str(workspace),
        }
        if arguments.get("runtime_root"):
            review_arguments["runtime_root"] = str(arguments["runtime_root"])
        post_patch_review = review_research_results_tool(review_arguments)
        payload["post_patch_review"] = post_patch_review
        initial_review = arguments.get("initial_review")
        if isinstance(initial_review, dict):
            payload["loop_decision"] = build_loop_decision(
                initial_review=initial_review,
                final_review=post_patch_review,
            )
    return payload


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
    started_at = _utc_now()
    start_time = time.monotonic()
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
    payload = {
        "status": run_payload.get("status"),
        "selected_patch_source": selected_patch_source,
        "selected_patch": selected_patch,
        "review": review_payload,
        "run": run_payload,
    }
    if arguments.get("include_final_review"):
        final_review = review_research_results_tool({
            "task_id": _required_string(arguments, "task_id"),
            **({"runtime_root": arguments["runtime_root"]} if arguments.get("runtime_root") else {}),
            **({"workspace": arguments["workspace"]} if arguments.get("workspace") else {}),
        })
        payload["final_review"] = final_review
        payload["loop_decision"] = build_loop_decision(
            initial_review=review_payload,
            final_review=final_review,
        )
    payload["execution_metadata"] = _execution_metadata(
        arguments,
        started_at=started_at,
        start_time=start_time,
        timeout_seconds=subprocess_timeout(
            arguments,
            experiment_duration=_int_or_none(arguments.get("experiment_duration")) or 300,
            default_experiments=None,
        ),
        experiment_duration=_int_or_none(arguments.get("experiment_duration")),
        default_experiments=None,
        task_id=_required_string(arguments, "task_id"),
        workspace=arguments.get("workspace"),
    )
    return payload


def build_loop_decision(
    initial_review: dict[str, Any],
    final_review: dict[str, Any],
) -> dict[str, Any]:
    """Return a deterministic stop/continue decision from two review payloads."""
    metric = _review_metric(initial_review) or _review_metric(final_review) or "val_bpb"
    direction = _review_metric_direction(initial_review) or _review_metric_direction(final_review)
    previous_best = _review_best_value(initial_review)
    current_best = _review_best_value(final_review)
    improved = _metric_improved(
        previous=previous_best,
        current=current_best,
        direction=direction,
    )
    final_policy = _review_loop_policy(final_review)
    if final_policy.get("decision") == "stop":
        decision = "stop"
        reason = str(
            final_policy.get("reason")
            or final_policy.get("stop_reason")
            or "final review loop policy stopped the experiment loop"
        )
        reason_category = str(final_policy.get("reason_category") or "loop_policy_stop")
        recommended_next_action = str(
            final_policy.get("recommended_next_action") or "inspect_final_review"
        )
    elif improved:
        decision = "continue"
        reason = "best metric improved; continue with the next reviewed patch"
        reason_category = "metric_improved"
        recommended_next_action = "continue_with_reviewed_patch"
    else:
        decision = "stop"
        reason = "best metric did not improve; stop and inspect the final review before continuing"
        reason_category = "metric_not_improved"
        recommended_next_action = "inspect_final_review"
    return {
        "decision": decision,
        "reason": reason,
        "reason_category": reason_category,
        "recommended_next_action": recommended_next_action,
        "metric": metric,
        "metric_direction": direction,
        "previous_best": previous_best,
        "current_best": current_best,
        "improved": improved,
    }


def _review_loop_policy(review: dict[str, Any]) -> dict[str, Any]:
    state = review.get("experiment_state") if isinstance(review.get("experiment_state"), dict) else {}
    policy = state.get("loop_policy") if isinstance(state.get("loop_policy"), dict) else {}
    return policy


def _review_metric(review: dict[str, Any]) -> str | None:
    metric = _review_plan_metric(review)
    name = metric.get("name")
    return str(name) if name else None


def _review_metric_direction(review: dict[str, Any]) -> str:
    metric = _review_plan_metric(review)
    direction = metric.get("direction")
    return str(direction) if direction else "minimize"


def _review_plan_metric(review: dict[str, Any]) -> dict[str, Any]:
    state = review.get("experiment_state") if isinstance(review.get("experiment_state"), dict) else {}
    plan = (
        state.get("code_change_plan", {}).get("next_experiment_plan", {})
        if isinstance(state.get("code_change_plan"), dict)
        else {}
    )
    metric = plan.get("metric") if isinstance(plan.get("metric"), dict) else {}
    return metric


def _review_best_value(review: dict[str, Any]) -> float | None:
    state = review.get("experiment_state") if isinstance(review.get("experiment_state"), dict) else {}
    best_result = state.get("best_result") if isinstance(state.get("best_result"), dict) else {}
    value = best_result.get("val")
    try:
        return float(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _metric_improved(
    previous: float | None,
    current: float | None,
    direction: str,
) -> bool:
    if previous is None or current is None:
        return False
    if direction == "maximize":
        return current > previous
    return current < previous


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


def _required_change_proposal(arguments: dict[str, Any]) -> dict[str, Any]:
    proposal = arguments.get("change_proposal")
    if not isinstance(proposal, dict):
        raise MCPToolError({"status": "failed", "error": "change_proposal must be an object"})
    required = ("change_type", "target", "current_value", "proposed_value")
    missing = [key for key in required if key not in proposal]
    if missing:
        raise MCPToolError({
            "status": "failed",
            "error": "change_proposal is missing required fields",
            "missing_fields": missing,
        })
    change_type = str(proposal["change_type"])
    supported = {"hyperparam", "architecture", "training_strategy"}
    if change_type not in supported:
        raise MCPToolError({
            "status": "failed",
            "error_type": "unsupported_patch_type",
            "error": f"Unsupported change_type: {change_type}",
            "supported_change_types": sorted(supported),
        })
    target = str(proposal["target"]).strip().upper()
    if not target:
        raise MCPToolError({"status": "failed", "error": "change_proposal.target is required"})
    try:
        confidence = float(proposal.get("confidence", 0.5))
    except (TypeError, ValueError) as exc:
        raise MCPToolError({
            "status": "failed",
            "error_type": "invalid_patch_confidence",
            "error": "change_proposal.confidence must be numeric",
        }) from exc
    return {
        "change_type": change_type,
        "target": target,
        "current_value": str(proposal["current_value"]).strip(),
        "proposed_value": str(proposal["proposed_value"]).strip(),
        "reason": str(proposal.get("reason") or ""),
        "confidence": confidence,
    }


def _validate_client_patch_proposal(
    workspace: Path,
    proposal: dict[str, Any],
) -> dict[str, Any]:
    train_py = workspace / "train.py"
    if not train_py.exists():
        raise MCPToolError({
            "status": "failed",
            "error_type": "missing_train_py",
            "error": "workspace/train.py is required for client patch validation",
            "workspace": str(workspace),
        })
    search_region = parse_search_region(train_py.read_text(encoding="utf-8"))
    if not search_region:
        raise MCPToolError({
            "status": "failed",
            "error_type": "missing_search_region",
            "error": "train.py does not contain an AUTORESEARCH SEARCH REGION",
            "train_py": str(train_py),
        })
    target = proposal["target"]
    if target not in search_region:
        raise MCPToolError({
            "status": "failed",
            "error_type": "invalid_patch_target",
            "error": "change_proposal.target is not in the current SEARCH REGION",
            "target": target,
            "available_targets": sorted(search_region),
        })
    actual_value = search_region[target]
    if proposal["current_value"] != actual_value:
        raise MCPToolError({
            "status": "failed",
            "error_type": "stale_patch",
            "error": "change_proposal.current_value does not match current train.py",
            "target": target,
            "expected_value": proposal["current_value"],
            "actual_value": actual_value,
        })
    task_patch = _client_proposal_task_patch(proposal)
    return {
        "status": "validated",
        "mode": "task_patch_only",
        "target": target,
        "change_type": proposal["change_type"],
        "confidence": proposal["confidence"],
        "task_patch": task_patch,
        "diff_preview": {
            "before": f"{target} = {actual_value}",
            "after": f"{target} = {proposal['proposed_value']}",
            "note": (
                "MCP validates against train.py but executes through task_patch so "
                "autoresearch can own workspace setup and sampling."
            ),
        },
        "execution_guardrails": [
            "target must exist in the current AUTORESEARCH SEARCH REGION",
            "current_value must match train.py before execution",
            "only one parameter is narrowed to the proposed value",
            "the original train.py is not mutated by this MCP tool",
        ],
    }


def _client_proposal_task_patch(proposal: dict[str, Any]) -> dict[str, Any]:
    target = proposal["target"]
    proposed_value = _parse_patch_literal(proposal["proposed_value"])
    reason = proposal.get("reason") or "client-generated patch"
    return {
        "hyperparameter_space": {
            target.lower(): {"type": "choice", "values": [proposed_value]},
        },
        "program_md_overrides": {
            "hints": [
                (
                    f"Client proposal {target}: {proposal['current_value']} -> "
                    f"{proposal['proposed_value']}. Reason: {reason}"
                ),
            ],
        },
    }


def _parse_patch_literal(value: str) -> Any:
    try:
        return ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return value


def _initial_review_for_client_patch(arguments: dict[str, Any]) -> dict[str, Any] | None:
    if not arguments.get("include_final_review"):
        return None
    task_id = _task_id_from_task_config(arguments)
    try:
        return review_research_results_tool(_review_arguments_for_task(arguments, task_id))
    except MCPToolError:
        return None


def _review_arguments_for_task(arguments: dict[str, Any], task_id: str) -> dict[str, Any]:
    review_arguments = {"task_id": task_id}
    for key in ("runtime_root", "workspace"):
        if key in arguments:
            review_arguments[key] = arguments[key]
    return review_arguments


def _task_id_from_run_payload(run_payload: dict[str, Any]) -> str | None:
    result = run_payload.get("result")
    if isinstance(result, dict) and result.get("task_id"):
        return str(result["task_id"])
    if run_payload.get("task_id"):
        return str(run_payload["task_id"])
    return None


def _task_id_from_task_config(arguments: dict[str, Any]) -> str:
    task_config = Path(_required_string(arguments, "task_config")).expanduser().resolve()
    task_payload = _read_json_file(task_config)
    return str(task_payload.get("task_id") or task_config.stem)


def _review_seed_from_run(
    run_payload: dict[str, Any],
    arguments: dict[str, Any],
) -> dict[str, Any]:
    result = run_payload.get("result") if isinstance(run_payload.get("result"), dict) else {}
    return {
        "experiment_state": {
            "best_result": result.get("best_result", {}),
            "code_change_plan": {
                "next_experiment_plan": {
                    "metric": _task_metric_from_config(arguments),
                },
            },
        },
    }


def _task_metric_from_config(arguments: dict[str, Any]) -> dict[str, str]:
    try:
        task_payload = _read_json_file(
            Path(_required_string(arguments, "task_config")).expanduser().resolve()
        )
    except MCPToolError:
        return {"name": "val_bpb", "direction": "minimize"}
    metric = task_payload.get("metric")
    if not isinstance(metric, dict):
        return {"name": "val_bpb", "direction": "minimize"}
    return {
        "name": str(metric.get("name") or "val_bpb"),
        "direction": str(metric.get("direction") or "minimize"),
    }


def _base_code_patch_execution(patch_text: str = "") -> dict[str, Any]:
    preview_limit = 4000
    diff_preview = patch_text[:preview_limit]
    if len(patch_text) > preview_limit:
        diff_preview += "\n...<truncated>"
    return {
        "mode": "workspace_unified_diff",
        "changed_files": [],
        "preflight": {"status": "pending"},
        "apply": {"status": "pending"},
        "syntax_check": {"status": "pending"},
        "test_check": {"status": "pending"},
        "rollback": {"performed": False},
        "diff_preview": diff_preview,
    }


def _normalized_allowed_patch_files(value: Any) -> set[str] | None:
    if value is None:
        return None
    if not isinstance(value, list):
        _raise_code_patch_error(
            "invalid_allowed_files",
            "allowed_files must be an array of workspace-relative file paths",
        )
    normalized = set()
    for item in value:
        if not isinstance(item, str):
            _raise_code_patch_error(
                "invalid_allowed_files",
                "allowed_files entries must be strings",
            )
        normalized.add(_normalize_patch_path(item, field="allowed_files"))
    return normalized


def _normalized_test_command(value: Any) -> list[str] | None:
    if value is None:
        return None
    if (
        not isinstance(value, list)
        or not value
        or not all(isinstance(item, str) and item for item in value)
    ):
        _raise_code_patch_error(
            "invalid_test_command",
            "test_command must be a non-empty argv array of strings",
        )
    return [str(item) for item in value]


def _normalized_test_timeout(value: Any) -> int:
    try:
        timeout = int(value)
    except (TypeError, ValueError):
        _raise_code_patch_error(
            "invalid_test_timeout",
            "test_timeout_seconds must be an integer",
        )
    return max(1, timeout)


def _parse_client_unified_diff(patch_text: str) -> list[dict[str, Any]]:
    lines = patch_text.splitlines()
    file_patches: list[dict[str, Any]] = []
    index = 0
    while index < len(lines):
        if not lines[index].strip():
            index += 1
            continue
        if not lines[index].startswith("--- "):
            _raise_code_patch_error(
                "invalid_patch",
                "unified diff must start each file patch with a --- header",
                line=index + 1,
            )
        old_path = _normalize_patch_path(lines[index][4:].strip(), field="old_path")
        index += 1
        if index >= len(lines) or not lines[index].startswith("+++ "):
            _raise_code_patch_error(
                "invalid_patch",
                "unified diff file patch is missing a +++ header",
                line=index + 1,
            )
        new_path = _normalize_patch_path(lines[index][4:].strip(), field="new_path")
        if old_path != new_path:
            _raise_code_patch_error(
                "unsupported_patch_operation",
                "renames, new files, and deletes are not supported by apply_client_code_patch",
                old_path=old_path,
                new_path=new_path,
            )
        index += 1
        hunks: list[dict[str, Any]] = []
        while index < len(lines) and not lines[index].startswith("--- "):
            if not lines[index].startswith("@@ "):
                _raise_code_patch_error(
                    "invalid_patch",
                    "unified diff file patch is missing a hunk header",
                    file=old_path,
                    line=index + 1,
                )
            old_start = _parse_unified_hunk_old_start(lines[index])
            index += 1
            hunk_lines: list[str] = []
            while (
                index < len(lines)
                and not lines[index].startswith("@@ ")
                and not lines[index].startswith("--- ")
            ):
                patch_line = lines[index]
                if patch_line.startswith("\\"):
                    index += 1
                    continue
                if not patch_line or patch_line[0] not in {" ", "-", "+"}:
                    _raise_code_patch_error(
                        "invalid_patch",
                        "hunk lines must start with space, -, or +",
                        file=old_path,
                        line=index + 1,
                    )
                hunk_lines.append(patch_line)
                index += 1
            hunks.append({"old_start": old_start, "lines": hunk_lines})
        if not hunks:
            _raise_code_patch_error(
                "invalid_patch",
                "unified diff file patch must include at least one hunk",
                file=old_path,
            )
        file_patches.append({"path": old_path, "hunks": hunks})
    if not file_patches:
        _raise_code_patch_error("invalid_patch", "patch must contain at least one file diff")
    return file_patches


def _normalize_patch_path(raw_path: str, field: str) -> str:
    path_text = raw_path.strip()
    if "\t" in path_text:
        path_text = path_text.split("\t", 1)[0].strip()
    if path_text == "/dev/null":
        _raise_code_patch_error(
            "unsupported_patch_operation",
            "new files and deletes are not supported by apply_client_code_patch",
            field=field,
        )
    if path_text.startswith("a/") or path_text.startswith("b/"):
        path_text = path_text[2:]
    relative = Path(path_text)
    if (
        not path_text
        or str(relative) == "."
        or relative.is_absolute()
        or ".." in relative.parts
    ):
        _raise_code_patch_error(
            "unsafe_patch_path",
            "patch paths must be workspace-relative and may not contain ..",
            field=field,
            path=path_text,
        )
    return relative.as_posix()


def _parse_unified_hunk_old_start(header: str) -> int:
    try:
        hunk_ranges = header.split("@@", 2)[1].strip().split()
        old_range = hunk_ranges[0]
        if not old_range.startswith("-"):
            raise ValueError
        old_start = int(old_range[1:].split(",", 1)[0])
    except (IndexError, TypeError, ValueError):
        _raise_code_patch_error(
            "invalid_patch",
            "hunk header must include an old-file range like @@ -1,2 +1,2 @@",
            header=header,
        )
    return max(1, old_start)


def _preflight_client_code_patch(
    workspace: Path,
    file_patches: list[dict[str, Any]],
    allowed_files: set[str] | None,
) -> dict[str, str]:
    planned_changes: dict[str, str] = {}
    for file_patch in file_patches:
        relative_path = str(file_patch["path"])
        if relative_path in planned_changes:
            _raise_code_patch_error(
                "duplicate_patch_target",
                "patch may contain only one file patch per target path",
                file=relative_path,
            )
        if allowed_files is not None and relative_path not in allowed_files:
            _raise_code_patch_error(
                "patch_target_not_allowed",
                "patch target is not in allowed_files",
                file=relative_path,
            )
        target_file = (workspace / relative_path).resolve()
        if not _is_relative_to(target_file, workspace):
            _raise_code_patch_error(
                "unsafe_patch_path",
                "patch target resolves outside workspace",
                file=relative_path,
                path=str(target_file),
            )
        if not target_file.exists() or not target_file.is_file():
            _raise_code_patch_error(
                "patch_target_missing",
                "patch target file does not exist",
                file=relative_path,
            )
        original_text = target_file.read_text(encoding="utf-8")
        planned_changes[relative_path] = _apply_unified_hunks(
            original_text,
            file_patch["hunks"],
            relative_path,
        )
    return planned_changes


def _apply_unified_hunks(
    original_text: str,
    hunks: list[dict[str, Any]],
    relative_path: str,
) -> str:
    original_lines = original_text.splitlines(keepends=True)
    output_lines: list[str] = []
    cursor = 0
    for hunk in hunks:
        old_index = int(hunk["old_start"]) - 1
        if old_index < cursor or old_index > len(original_lines):
            _raise_code_patch_error(
                "patch_context_mismatch",
                "patch hunk location does not match current file",
                file=relative_path,
                old_start=hunk["old_start"],
            )
        output_lines.extend(original_lines[cursor:old_index])
        cursor = old_index
        for patch_line in hunk["lines"]:
            marker = patch_line[0]
            content = patch_line[1:]
            if marker == " ":
                _assert_patch_context_line(original_lines, cursor, content, relative_path)
                output_lines.append(original_lines[cursor])
                cursor += 1
            elif marker == "-":
                _assert_patch_context_line(original_lines, cursor, content, relative_path)
                cursor += 1
            elif marker == "+":
                output_lines.append(f"{content}\n")
    output_lines.extend(original_lines[cursor:])
    return "".join(output_lines)


def _assert_patch_context_line(
    original_lines: list[str],
    cursor: int,
    expected: str,
    relative_path: str,
) -> None:
    actual = original_lines[cursor].rstrip("\r\n") if cursor < len(original_lines) else None
    if actual == expected:
        return
    _raise_code_patch_error(
        "patch_context_mismatch",
        "patch context does not match current file",
        file=relative_path,
        expected=expected,
        actual=actual,
    )


def _syntax_check_changed_python_files(
    workspace: Path,
    changed_files: list[str],
) -> dict[str, Any]:
    checked_files = [path for path in changed_files if path.endswith(".py")]
    for relative_path in checked_files:
        target_file = workspace / relative_path
        try:
            compile(target_file.read_text(encoding="utf-8"), str(target_file), "exec")
        except SyntaxError as exc:
            return {
                "status": "failed",
                "checked_files": checked_files,
                "file": relative_path,
                "line": exc.lineno,
                "error": f"{relative_path}:{exc.lineno}: {exc.msg}",
            }
    return {
        "status": "passed",
        "checked_files": checked_files,
    }


def _run_client_code_patch_test_command(
    workspace: Path,
    command: list[str] | None,
    timeout_seconds: int,
    env: dict[str, str],
) -> dict[str, Any]:
    if command is None:
        return {
            "status": "skipped",
            "command": None,
        }
    timeout = max(1, int(timeout_seconds))
    try:
        proc = subprocess.run(
            command,
            cwd=workspace,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        return {
            "status": "failed",
            "command": _safe_cmd(command),
            "returncode": None,
            "error": f"test command not found: {exc}",
        }
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "command": _safe_cmd(command),
            "timeout_seconds": timeout,
            "error": f"test command timed out after {timeout}s",
            "stdout_tail": _stdout_tail(exc.stdout or ""),
        }
    status = "passed" if proc.returncode == 0 else "failed"
    return {
        "status": status,
        "command": _safe_cmd(command),
        "returncode": proc.returncode,
        "stdout_tail": _stdout_tail(proc.stdout),
        **({} if status == "passed" else {"error": f"test command exited {proc.returncode}"}),
    }


def _stdout_tail(stdout: str, line_limit: int = 40) -> str:
    return "\n".join(str(stdout or "").splitlines()[-line_limit:])


def _rollback_client_code_patch(workspace: Path, backups: dict[str, str]) -> None:
    for relative_path, original_text in backups.items():
        (workspace / relative_path).write_text(original_text, encoding="utf-8")


def _raise_code_patch_error(error_type: str, error: str, **extra: Any) -> None:
    payload = {
        "status": "failed",
        "error_type": error_type,
        "error": error,
        "patch_execution": _base_code_patch_execution(),
    }
    payload.update(extra)
    raise MCPToolError(payload)


TOOL_HANDLERS: dict[str, ToolHandler] = {
    "get_service_manifest": get_service_manifest_tool,
    "run_fresh_demo": run_fresh_demo_tool,
    "run_autoresearch": run_autoresearch_tool,
    "run_ai_autoresearch": run_ai_autoresearch_tool,
    "get_experiment_status": get_experiment_status_tool,
    "get_experiment_result": get_experiment_result_tool,
    "get_experiment_logs": get_experiment_logs_tool,
    "list_runtime_artifacts": list_runtime_artifacts_tool,
    "archive_runtime_artifacts": archive_runtime_artifacts_tool,
    "clean_runtime_artifacts": clean_runtime_artifacts_tool,
    "read_paper": read_paper_tool,
    "research_task": research_task_tool,
    "propose_hypotheses": propose_hypotheses_tool,
    "run_hypothesis_experiment": run_hypothesis_experiment_tool,
    "review_research_results": review_research_results_tool,
    "run_client_patch_experiment": run_client_patch_experiment_tool,
    "apply_client_code_patch": apply_client_code_patch_tool,
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


def run_mcp_subprocess(
    cmd: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout_seconds: int | None,
) -> subprocess.CompletedProcess[str]:
    """Run a service subprocess with structured startup/timeout errors."""
    try:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            **_process_group_kwargs(),
        )
    except OSError as exc:
        raise MCPToolError({
            "status": "failed",
            "error_type": "startup_failed",
            "error": f"failed to start subprocess: {exc}",
            "cmd": _safe_cmd(cmd),
        }) from exc

    try:
        stdout, _ = proc.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        _kill_process_tree(proc)
        stdout, _ = proc.communicate()
        raise MCPToolError({
            "status": "failed",
            "error_type": "timeout",
            "error": f"subprocess timed out after {timeout_seconds}s",
            "timeout_seconds": timeout_seconds,
            "stdout": (stdout or "").strip(),
            "cmd": _safe_cmd(cmd),
        }) from exc

    return subprocess.CompletedProcess(cmd, proc.returncode, stdout or "")


def _process_group_kwargs() -> dict[str, Any]:
    if os.name == "posix":
        return {"start_new_session": True}
    return {}


def _kill_process_tree(proc: subprocess.Popen[str]) -> None:
    if proc.poll() is not None:
        return
    if os.name == "posix":
        try:
            os.killpg(proc.pid, signal.SIGKILL)
            return
        except ProcessLookupError:
            return
        except OSError:
            pass
    proc.kill()


def _safe_cmd(cmd: list[str]) -> list[str]:
    return [str(part) for part in cmd]


def _training_error_type_from_payload(payload: dict[str, Any]) -> str | None:
    result = payload.get("result")
    if not isinstance(result, dict):
        return None
    if isinstance(result.get("best_result"), dict) and result["best_result"]:
        return None
    experiments = result.get("experiments")
    if not isinstance(experiments, list) or not experiments:
        return None
    for experiment in experiments:
        if not isinstance(experiment, dict):
            continue
        error = str(experiment.get("error") or "")
        for marker, error_type in TRAINING_ERROR_TYPES.items():
            if marker in error:
                return error_type
    return None


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


def _execution_metadata(
    arguments: dict[str, Any],
    *,
    started_at: str,
    start_time: float,
    timeout_seconds: int | None,
    experiment_duration: int | None = None,
    default_experiments: int | None = None,
    test_timeout_seconds: int | None = None,
    command: list[str] | None = None,
    task_id: str | None = None,
    workspace: str | Path | None = None,
) -> dict[str, Any]:
    """Return client-facing metadata for an execution-class MCP payload."""
    return {
        "started_at": started_at,
        "finished_at": _utc_now(),
        "wall_time_seconds": round(time.monotonic() - start_time, 3),
        "python_executable": str(
            arguments.get("python")
            or os.environ.get("ML_RESEARCH_LOOP_PYTHON")
            or sys.executable
        ),
        "server_python": sys.executable,
        "timeout_policy": {
            "timeout_enforced": timeout_seconds is not None or test_timeout_seconds is not None,
            "subprocess_timeout_seconds": timeout_seconds,
            "experiment_duration_seconds": experiment_duration,
            "max_experiments": _int_or_none(arguments.get("max_experiments")),
            "max_duration_minutes": _int_or_none(arguments.get("max_duration")),
            "default_experiments": default_experiments,
            "test_timeout_seconds": test_timeout_seconds,
        },
        "execution_sandbox": execution_sandbox_policy(),
        "sandbox_roots": [str(root) for root in _allowed_execution_roots()],
        "artifact_retention": _artifact_retention_paths(
            arguments=arguments,
            task_id=task_id,
            workspace=workspace,
        ),
        **({"command": _safe_cmd(command)} if command else {}),
    }


def _artifact_retention_paths(
    arguments: dict[str, Any],
    *,
    task_id: str | None,
    workspace: str | Path | None,
) -> dict[str, Any]:
    runtime_root = _runtime_root(arguments)
    payload: dict[str, Any] = {
        "runtime_root": str(runtime_root),
        "tasks_dir": str(runtime_root / "tasks"),
        "results_dir": str(runtime_root / "results"),
        "workdir_dir": str(runtime_root / "workdir"),
        "snapshots_dir": str(runtime_root / "snapshots"),
        "archive_dir": str(runtime_root / "archive"),
    }
    if task_id:
        payload["task_file"] = str(
            Path(str(arguments["task_config"])).expanduser().resolve()
            if arguments.get("task_config")
            else runtime_root / "tasks" / f"{task_id}.json"
        )
        payload["result_file"] = str(runtime_root / "results" / f"{task_id}.json")
        payload["progress_file"] = str(runtime_root / "results" / f"{task_id}-progress.json")
        payload["workspace"] = str(
            Path(workspace).expanduser().resolve()
            if workspace is not None
            else _workspace_root(arguments, task_id)
        )
        payload["snapshots_task_dir"] = str(runtime_root / "snapshots" / task_id)
    elif workspace is not None:
        payload["workspace"] = str(Path(workspace).expanduser().resolve())
    return payload


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _int_or_none(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


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


def _artifact_dir_summary(path: Path) -> dict[str, Any]:
    files = [item for item in path.rglob("*") if item.is_file()] if path.exists() else []
    return {
        "path": str(path),
        "exists": path.exists(),
        "file_count": len(files),
        "size_bytes": sum(item.stat().st_size for item in files),
    }


def _runtime_task_ids(runtime_root: Path) -> list[str]:
    task_ids: set[str] = set()
    tasks_dir = runtime_root / "tasks"
    if tasks_dir.exists():
        for path in tasks_dir.glob("*.json"):
            task_ids.add(path.stem.removesuffix("-hypothesis"))
    results_dir = runtime_root / "results"
    if results_dir.exists():
        for path in results_dir.glob("*.json"):
            stem = path.stem
            if stem.endswith("-progress"):
                stem = stem.removesuffix("-progress")
            task_ids.add(stem)
    workdir = runtime_root / "workdir"
    if workdir.exists():
        task_ids.update(path.name for path in workdir.iterdir() if path.is_dir())
    return sorted(task_ids)


def _task_artifact_groups(runtime_root: Path, task_id: str) -> dict[str, list[Path]]:
    return {
        "tasks": [
            runtime_root / "tasks" / f"{task_id}.json",
            runtime_root / "tasks" / f"{task_id}-hypothesis.json",
        ],
        "results": [
            runtime_root / "results" / f"{task_id}.json",
            runtime_root / "results" / f"{task_id}-progress.json",
        ],
        "workdir": [runtime_root / "workdir" / task_id],
        "snapshots": [runtime_root / "snapshots" / task_id],
    }


def _move_task_artifact_groups(
    groups: dict[str, list[Path]],
    destination_root: Path,
) -> int:
    moved_groups = 0
    for group, paths in groups.items():
        group_moved = False
        for path in paths:
            if not path.exists():
                continue
            relative = Path(group) / path.name
            destination = destination_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(path), str(destination))
            group_moved = True
        if group_moved:
            moved_groups += 1
    return moved_groups


def _delete_task_artifact_groups(groups: dict[str, list[Path]]) -> int:
    deleted_groups = 0
    for paths in groups.values():
        group_deleted = False
        for path in paths:
            if not path.exists():
                continue
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            group_deleted = True
        if group_deleted:
            deleted_groups += 1
    return deleted_groups


def _archive_timestamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


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
