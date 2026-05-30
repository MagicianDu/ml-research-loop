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
from dataclasses import replace
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
from lib.full_reproduction_harness import (
    FullReproductionRunConfig,
    run_fasttext_multi_proposal_loop,
    run_fasttext_patch_round,
    write_fasttext_release_proof_bundle,
    write_fasttext_patch_round_proof_bundle,
)
from lib.memory_adapters import search_memory_adapters, sync_cards_to_adapters
from lib.proposal_contract import (
    build_proposal_context,
    build_proposal_reflection,
    validate_client_proposal,
)
from lib.proposal_memory import proposal_reflection_to_memory_card
from lib.proposal_search import build_proposal_search
from lib.research_case import (
    EvidenceRef,
    ResearchCase,
    ResearchClaim,
    VALID_CLAIM_STATUSES,
    VALID_EVIDENCE_STRENGTHS,
    serialize_research_case,
    summarize_research_case,
)
from lib.research_memory import (
    ResearchMemoryCard,
    ResearchMemoryStore,
    extract_fasttext_release_memory_cards,
)
from lib.benchmarks import (
    build_benchmark_readiness,
    build_hf_external_eval_plan,
    build_official_harness_probe,
    build_official_proof_setup_bundle,
    build_proof_archive_bundle,
    build_proof_publication_bundle,
    build_public_proof_plan,
    grade_official_mle_submission,
    load_hf_eval_targets,
    materialize_official_mle_agent_workspace,
    run_cp_bench_candidate_round,
    run_cp_bench_proposal_round,
    run_official_mle_solver_round,
    select_hf_eval_targets,
    write_cp_bench_client_candidate_submission,
    write_cp_bench_local_baseline,
    write_cp_bench_live_verification,
    write_cp_bench_proposal_context,
    write_cp_bench_submission_gate,
    write_official_mle_patch_round_proof_bundle,
    write_official_proof_setup_bundle,
    write_hf_external_eval_plan,
    write_paperbench_codex_review_bundle,
    write_paperbench_codex_review_report,
    write_proof_archive_bundle,
    write_proof_publication_bundle,
    write_smol_worldcup_baseline,
    write_smol_worldcup_live_verification,
    write_smol_worldcup_model_eval,
    write_smol_worldcup_prompt_leakage_audit,
    run_smol_worldcup_proposal_round,
    write_smol_worldcup_rescore,
    write_smol_worldcup_rescore_proof_archive,
    write_smol_worldcup_submission_probe,
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
    "plan_research_case",
    "research_task",
    "read_paper",
    "propose_hypotheses",
    "run_hypothesis_experiment",
    "review_research_results",
    "run_client_patch_experiment",
    "apply_client_code_patch",
    "build_proposal_context",
    "validate_client_proposal_contract",
    "write_proposal_reflection",
    "summarize_proposal_search",
    "run_next_experiment_from_review",
    "get_experiment_status",
    "get_experiment_result",
    "get_experiment_logs",
    "list_runtime_artifacts",
    "archive_runtime_artifacts",
    "clean_runtime_artifacts",
    "run_ai_autoresearch",
    "get_benchmark_harness_probe",
    "plan_benchmark_proof_run",
    "write_benchmark_proof_setup_bundle",
    "write_benchmark_proof_publication_bundle",
    "write_benchmark_proof_archive",
    "get_hf_external_eval_targets",
    "write_hf_external_eval_plan",
    "write_cp_bench_live_verification",
    "run_cp_bench_local_baseline",
    "run_cp_bench_proposal_round",
    "run_cp_bench_candidate_round",
    "build_cp_bench_proposal_context",
    "write_cp_bench_client_candidate_submission",
    "write_cp_bench_submission_gate",
    "write_smol_worldcup_live_verification",
    "write_smol_worldcup_prompt_leakage_audit",
    "run_smol_worldcup_local_baseline",
    "run_smol_worldcup_model_eval",
    "run_smol_worldcup_proposal_round",
    "run_smol_worldcup_rescore",
    "write_smol_worldcup_rescore_proof_archive",
    "write_smol_worldcup_submission_probe",
    "prepare_official_mle_bench_workspace",
    "grade_official_mle_bench_submission",
    "run_official_mle_bench_round",
    "run_official_mle_bench_patch_round",
    "write_official_mle_bench_patch_round_proof_bundle",
    "run_fasttext_patch_round",
    "write_fasttext_patch_round_proof_bundle",
    "run_fasttext_multi_proposal_loop",
    "write_fasttext_release_proof_bundle",
    "prepare_paperbench_codex_review_bundle",
    "write_paperbench_codex_review_report",
    "record_research_memory",
    "retrieve_research_memory",
    "suggest_from_memory",
    "promote_memory_card",
    "audit_memory_trace",
]
TOOL_CONTRACT_DESCRIPTIONS = {
    "get_service_manifest": "Return the versioned MCP product and planner contract.",
    "plan_research_case": "Create a long-running research case plan without running experiments, network, or LLM.",
    "research_task": "Return research context, evidence quality, cache metadata, and diagnostics.",
    "read_paper": "Return normalized paper evidence, findings, and experiment hypotheses.",
    "propose_hypotheses": "Convert research context into bounded experiment hypotheses.",
    "run_hypothesis_experiment": "Run bounded autoresearch validation for selected hypotheses.",
    "review_research_results": "Return experiment state, planner actions, and next-round patches.",
    "run_client_patch_experiment": "Validate a client-generated SEARCH REGION proposal and run it as a bounded experiment.",
    "apply_client_code_patch": "Apply a guarded client-generated unified diff inside a workspace with rollback.",
    "build_proposal_context": "Write a non-executing artifact bundle and prompt contract for client-side proposal generation.",
    "validate_client_proposal_contract": "Validate a client-generated proposal JSON against the proposal prompt contract.",
    "write_proposal_reflection": "Write a non-executing reflection artifact from proposal evaluation feedback.",
    "summarize_proposal_search": "Summarize a small proposal portfolio/tree frontier without executing experiments.",
    "run_next_experiment_from_review": "Execute the proposed next task patch from a review payload.",
    "get_experiment_status": "Return progress metadata for a task from runtime artifacts.",
    "get_experiment_result": "Return the final task result payload from runtime artifacts.",
    "get_experiment_logs": "Return recent training log tails for debugging failed runs.",
    "list_runtime_artifacts": "List runtime tasks, results, workdirs, snapshots, and archives.",
    "archive_runtime_artifacts": "Move one task's runtime artifacts into archive/.",
    "clean_runtime_artifacts": "Delete one task's runtime artifacts after explicit confirmation.",
    "run_ai_autoresearch": "Run explicit opt-in server-side LLM autoresearch.",
    "get_benchmark_harness_probe": "Probe official benchmark harness prerequisites without running evaluations.",
    "plan_benchmark_proof_run": "Plan an official/debug benchmark proof run without launching evaluations.",
    "write_benchmark_proof_setup_bundle": "Write read-only setup files for an external official/debug proof-run environment.",
    "write_benchmark_proof_publication_bundle": "Validate proof-run artifacts and write a guarded publication bundle.",
    "write_benchmark_proof_archive": "Copy complete proof-run artifacts into a hashed archive with a publication guard.",
    "get_hf_external_eval_targets": "Return Hugging Face external evaluation target candidates without submitting or claiming scores.",
    "write_hf_external_eval_plan": "Write a local proof plan for one Hugging Face external evaluation target without submitting results.",
    "write_cp_bench_live_verification": "Write CP-Bench live verification artifacts without submitting or claiming scores.",
    "run_cp_bench_local_baseline": "Write a CP-Bench local baseline artifact bundle without submitting or claiming scores.",
    "run_cp_bench_proposal_round": "Write guarded CP-Bench proposal-round and rollback artifacts without submitting or claiming scores.",
    "run_cp_bench_candidate_round": "Run a guarded CP-Bench candidate submission against a local baseline without submitting or claiming scores.",
    "build_cp_bench_proposal_context": "Write a CP-Bench proposal prompt context from local evaluator failure outcomes without submitting or claiming scores.",
    "write_cp_bench_client_candidate_submission": "Write a non-reference-replay CP-Bench client candidate bundle without submitting or claiming scores.",
    "write_cp_bench_submission_gate": "Write a manual CP-Bench submission gate bundle without submitting or claiming scores.",
    "write_smol_worldcup_live_verification": "Write Smol AI WorldCup live verification artifacts without submitting or claiming scores.",
    "write_smol_worldcup_prompt_leakage_audit": "Write a Smol AI WorldCup prompt leakage audit without submitting or claiming scores.",
    "run_smol_worldcup_local_baseline": "Run a local-compatible Smol AI WorldCup baseline without submitting or claiming scores.",
    "run_smol_worldcup_model_eval": "Run Smol AI WorldCup local model evaluation through an OpenAI-compatible endpoint without submitting or claiming scores.",
    "run_smol_worldcup_proposal_round": "Validate a client proposal contract and run one guarded Smol AI WorldCup local diagnostic round.",
    "run_smol_worldcup_rescore": "Rescore existing Smol AI WorldCup predictions with scorer-v2 without claiming leaderboard scores.",
    "write_smol_worldcup_rescore_proof_archive": "Package formal Smol AI WorldCup scorer-v2 rescore artifacts into a proof archive without claiming official scores.",
    "write_smol_worldcup_submission_probe": "Probe the Smol AI WorldCup HF Space submission API without launching evaluation or claiming scores.",
    "prepare_official_mle_bench_workspace": "Create an agent-editable workspace from official MLE-bench prepared data.",
    "grade_official_mle_bench_submission": "Run official mlebench grade-sample for local scorer feedback without claiming leaderboard scores.",
    "run_official_mle_bench_round": "Run solve.py and official mlebench grade-sample as one artifact-producing solver round.",
    "run_official_mle_bench_patch_round": "Apply a client-generated patch, run solve.py, and grade the result as one MLE-bench loop round.",
    "write_official_mle_bench_patch_round_proof_bundle": "Package a persisted MLE-bench patch-round report into a publication-guarded proof archive.",
    "run_fasttext_patch_round": "Run one bounded client-proposed fastText hyperparameter patch round against an archived baseline.",
    "write_fasttext_patch_round_proof_bundle": "Package a completed fastText patch round into a human-reviewed, hash-indexed proof bundle.",
    "run_fasttext_multi_proposal_loop": "Run several bounded fastText proposals, preserving failed rounds and best-so-far rollback state.",
    "write_fasttext_release_proof_bundle": "Package reviewed fastText proof artifacts into a downloadable tarball with checksum and review checklist.",
    "prepare_paperbench_codex_review_bundle": "Prepare PaperBench run and paper artifacts for Codex-assisted rubric review without claiming official scores.",
    "write_paperbench_codex_review_report": "Persist a client-supplied Codex rubric review as a non-official PaperBench review report.",
    "record_research_memory": "Record public, provenance-backed research memory cards without executing experiments.",
    "retrieve_research_memory": "Retrieve prior research memory cards with scores, reasons, and artifact provenance.",
    "suggest_from_memory": "Return advisory next-step suggestions from memory; never executes the suggested tool.",
    "promote_memory_card": "Append a promoted copy of a memory card after human or client review.",
    "audit_memory_trace": "Return evidence, artifact hashes, and claim boundaries for selected memory cards.",
}
SKILL_CONTRACTS = {
    "ml-research-loop-planner": {
        "path": "skills/ml-research-loop-planner/SKILL.md",
        "client_role": "workflow_planner",
        "description": (
            "Plan research, hypothesis, experiment, review, and patch workflows "
            "against the MCP tool contract."
        ),
        "required_tools": [
            "get_service_manifest",
            "plan_research_case",
            "research_task",
            "read_paper",
            "propose_hypotheses",
            "run_hypothesis_experiment",
            "review_research_results",
            "run_next_experiment_from_review",
            "run_client_patch_experiment",
            "apply_client_code_patch",
            "build_proposal_context",
            "validate_client_proposal_contract",
            "write_proposal_reflection",
            "summarize_proposal_search",
            "get_benchmark_harness_probe",
            "plan_benchmark_proof_run",
            "write_benchmark_proof_setup_bundle",
            "write_benchmark_proof_publication_bundle",
            "write_benchmark_proof_archive",
            "get_hf_external_eval_targets",
            "write_hf_external_eval_plan",
            "write_cp_bench_live_verification",
            "run_cp_bench_local_baseline",
            "run_cp_bench_proposal_round",
            "run_cp_bench_candidate_round",
            "build_cp_bench_proposal_context",
            "write_cp_bench_client_candidate_submission",
            "write_cp_bench_submission_gate",
            "write_smol_worldcup_live_verification",
            "write_smol_worldcup_prompt_leakage_audit",
            "run_smol_worldcup_local_baseline",
            "run_smol_worldcup_model_eval",
            "run_smol_worldcup_proposal_round",
            "run_smol_worldcup_rescore",
            "write_smol_worldcup_rescore_proof_archive",
            "write_smol_worldcup_submission_probe",
            "prepare_official_mle_bench_workspace",
            "grade_official_mle_bench_submission",
            "run_official_mle_bench_round",
            "run_official_mle_bench_patch_round",
            "write_official_mle_bench_patch_round_proof_bundle",
            "run_fasttext_patch_round",
            "write_fasttext_patch_round_proof_bundle",
            "run_fasttext_multi_proposal_loop",
            "write_fasttext_release_proof_bundle",
            "prepare_paperbench_codex_review_bundle",
            "write_paperbench_codex_review_report",
            "record_research_memory",
            "retrieve_research_memory",
            "suggest_from_memory",
            "promote_memory_card",
            "audit_memory_trace",
        ],
        "planning_signals": [
            "research_case",
            "research_evidence_gate",
            "provider_coverage",
            "experiment_tree",
            "loop_policy",
            "planner_actions",
            "benchmark_proof_plan",
            "benchmark_proof_archive",
            "smol_worldcup_prompt_leakage_audit",
            "smol_worldcup_model_eval",
            "smol_worldcup_rescore",
            "smol_worldcup_rescore_proof_archive",
            "smol_worldcup_submission_probe",
            "official_mle_agent_workspace",
            "official_mle_grade_sample",
            "official_mle_solver_round",
            "official_mle_patch_round",
            "official_mle_patch_proof_archive",
            "full_reproduction_fasttext_patch_round",
            "full_reproduction_fasttext_patch_proof_bundle",
            "full_reproduction_fasttext_multi_proposal_loop",
            "full_reproduction_fasttext_release_proof_bundle",
            "paperbench_codex_review_bundle",
            "paperbench_codex_review_report",
            "proposal_context",
            "proposal_contract.validation",
            "proposal_reflection",
            "research_memory",
            "research_memory.suggestions",
            "research_memory.trace",
        ],
        "safety_rules": [
            "human_confirmation",
            "manifest_first",
            "server_side_llm_opt_in",
        ],
    },
    "ml-research-loop-reproduction": {
        "path": "skills/ml-research-loop-reproduction/SKILL.md",
        "client_role": "reproduction_reviewer",
        "description": (
            "Drive paper-grounded reproduction readiness, required files, rubric, "
            "and grade report workflows."
        ),
        "required_tools": [
            "get_service_manifest",
            "read_paper",
            "research_task",
            "run_hypothesis_experiment",
            "review_research_results",
            "prepare_paperbench_codex_review_bundle",
            "write_paperbench_codex_review_report",
            "run_fasttext_multi_proposal_loop",
            "write_fasttext_release_proof_bundle",
            "record_research_memory",
            "retrieve_research_memory",
            "audit_memory_trace",
        ],
        "planning_signals": [
            "reproduction.readiness",
            "experiment_tree",
            "research_evidence_gate",
            "full_reproduction_fasttext_multi_proposal_loop",
            "full_reproduction_fasttext_release_proof_bundle",
            "paperbench_codex_review_bundle",
            "paperbench_codex_review_report",
            "research_memory",
            "research_memory.trace",
        ],
        "safety_rules": [
            "workspace_relative_required_files",
            "invalid_required_files_block",
            "human_confirmation",
        ],
    },
    "ml-research-loop-experiment-optimizer": {
        "path": "skills/ml-research-loop-experiment-optimizer/SKILL.md",
        "client_role": "metric_optimizer",
        "description": (
            "Use review state, experiment trees, guarded patches, and loop "
            "decisions to improve task metrics."
        ),
        "required_tools": [
            "get_service_manifest",
            "review_research_results",
            "run_next_experiment_from_review",
            "run_client_patch_experiment",
            "apply_client_code_patch",
            "build_proposal_context",
            "validate_client_proposal_contract",
            "write_proposal_reflection",
            "summarize_proposal_search",
            "run_fasttext_patch_round",
            "write_fasttext_patch_round_proof_bundle",
            "run_fasttext_multi_proposal_loop",
            "write_fasttext_release_proof_bundle",
            "get_experiment_logs",
            "retrieve_research_memory",
            "suggest_from_memory",
            "record_research_memory",
            "audit_memory_trace",
        ],
        "planning_signals": [
            "experiment_tree",
            "loop_policy",
            "code_change_plan",
            "loop_decision",
            "proposal_context",
            "proposal_contract.validation",
            "proposal_reflection",
            "full_reproduction_fasttext_patch_round",
            "full_reproduction_fasttext_patch_proof_bundle",
            "full_reproduction_fasttext_multi_proposal_loop",
            "full_reproduction_fasttext_release_proof_bundle",
            "research_memory",
            "research_memory.suggestions",
            "research_memory.trace",
        ],
        "safety_rules": [
            "stale_patch_rejection",
            "syntax_test_preflight",
            "rollback_required",
            "human_confirmation",
        ],
    },
    "ml-research-loop-operator": {
        "path": "skills/ml-research-loop-operator/SKILL.md",
        "client_role": "operator",
        "description": (
            "Install, validate, troubleshoot, and manage MCP runtime artifacts."
        ),
        "required_tools": [
            "get_service_manifest",
            "list_runtime_artifacts",
            "archive_runtime_artifacts",
            "clean_runtime_artifacts",
            "get_benchmark_harness_probe",
            "plan_benchmark_proof_run",
            "write_benchmark_proof_setup_bundle",
            "write_benchmark_proof_publication_bundle",
            "write_benchmark_proof_archive",
            "get_hf_external_eval_targets",
            "write_hf_external_eval_plan",
            "write_cp_bench_live_verification",
            "run_cp_bench_local_baseline",
            "run_cp_bench_proposal_round",
            "run_cp_bench_candidate_round",
            "build_cp_bench_proposal_context",
            "write_cp_bench_client_candidate_submission",
            "write_cp_bench_submission_gate",
            "write_smol_worldcup_live_verification",
            "write_smol_worldcup_prompt_leakage_audit",
            "run_smol_worldcup_local_baseline",
            "run_smol_worldcup_model_eval",
            "run_smol_worldcup_proposal_round",
            "run_smol_worldcup_rescore",
            "write_smol_worldcup_rescore_proof_archive",
            "write_smol_worldcup_submission_probe",
            "prepare_official_mle_bench_workspace",
            "grade_official_mle_bench_submission",
            "run_official_mle_bench_round",
            "run_official_mle_bench_patch_round",
            "write_official_mle_bench_patch_round_proof_bundle",
            "prepare_paperbench_codex_review_bundle",
            "write_paperbench_codex_review_report",
            "record_research_memory",
            "retrieve_research_memory",
            "suggest_from_memory",
            "promote_memory_card",
            "audit_memory_trace",
        ],
        "planning_signals": [
            "execution_metadata",
            "execution_sandbox",
            "compatibility_check",
            "hf_external_eval_targets",
            "hf_external_eval_plan",
            "smol_worldcup_prompt_leakage_audit",
            "smol_worldcup_model_eval",
            "smol_worldcup_rescore",
            "smol_worldcup_rescore_proof_archive",
            "smol_worldcup_submission_probe",
            "official_mle_agent_workspace",
            "official_mle_grade_sample",
            "official_mle_solver_round",
            "official_mle_patch_round",
            "official_mle_patch_proof_archive",
            "paperbench_codex_review_bundle",
            "paperbench_codex_review_report",
            "research_memory",
            "research_memory.suggestions",
            "research_memory.trace",
        ],
        "safety_rules": [
            "explicit_cleanup_confirmation",
            "allowed_roots_required",
            "contract_mismatch_stop",
        ],
    },
}
RECOMMENDED_SKILLS = list(SKILL_CONTRACTS)


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
            "name": "plan_research_case",
            "description": (
                "Create a long-running ResearchCase plan without running "
                "experiments, network access, or LLM calls."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "objective": {"type": "string"},
                    "case_id": {"type": "string"},
                    "claims": {
                        "type": "array",
                        "items": {
                            "anyOf": [
                                {"type": "string"},
                                {
                                    "type": "object",
                                    "properties": {
                                        "claim_id": {"type": "string"},
                                        "text": {"type": "string"},
                                        "status": {
                                            "type": "string",
                                            "enum": sorted(VALID_CLAIM_STATUSES),
                                        },
                                        "evidence_refs": {
                                            "type": "array",
                                            "items": {
                                                "type": "object",
                                                "properties": {
                                                    "source_id": {"type": "string"},
                                                    "artifact_path": {"type": "string"},
                                                    "quote": {"type": "string"},
                                                    "strength": {
                                                        "type": "string",
                                                        "enum": sorted(
                                                            VALID_EVIDENCE_STRENGTHS
                                                        ),
                                                    },
                                                },
                                                "required": ["source_id", "artifact_path"],
                                                "additionalProperties": True,
                                            },
                                        },
                                    },
                                    "required": ["text"],
                                    "additionalProperties": True,
                                },
                            ],
                        },
                    },
                    "forbidden_claims": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["objective"],
                "additionalProperties": False,
            },
        },
        {
            "name": "get_benchmark_harness_probe",
            "description": (
                "Probe official benchmark harness prerequisites without running "
                "evaluations, downloads, grading, or setup commands."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "mle_bench_repo": {"type": "string"},
                    "paperbench_repo": {"type": "string"},
                    "paperbench_data_dir": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "plan_benchmark_proof_run",
            "description": (
                "Build a safe official/debug benchmark proof-run plan from a "
                "read-only harness probe."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "mle_bench_repo": {"type": "string"},
                    "paperbench_repo": {"type": "string"},
                    "paperbench_data_dir": {"type": "string"},
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "write_benchmark_proof_setup_bundle",
            "description": (
                "Write read-only setup files for an external official/debug "
                "benchmark proof-run environment."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "mle_bench_repo": {"type": "string"},
                    "paperbench_repo": {"type": "string"},
                    "paperbench_data_dir": {"type": "string"},
                    "output_dir": {"type": "string"},
                },
                "required": ["output_dir"],
                "additionalProperties": False,
            },
        },
        {
            "name": "write_benchmark_proof_publication_bundle",
            "description": (
                "Validate proof-run artifacts and write a guarded publication "
                "bundle that blocks unsupported score claims."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "manifest": {"type": "string"},
                    "artifact_root": {"type": "string"},
                    "output_dir": {"type": "string"},
                },
                "required": ["manifest", "artifact_root", "output_dir"],
                "additionalProperties": False,
            },
        },
        {
            "name": "write_benchmark_proof_archive",
            "description": (
                "Copy complete proof-run artifacts into a hashed archive and "
                "embed the publication guard outputs."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "manifest": {"type": "string"},
                    "artifact_root": {"type": "string"},
                    "output_dir": {"type": "string"},
                },
                "required": ["manifest", "artifact_root", "output_dir"],
                "additionalProperties": False,
            },
        },
        {
            "name": "get_hf_external_eval_targets",
            "description": (
                "Return Hugging Face external evaluation candidates for client-side "
                "planning. This is read-only and never submits results or claims scores."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "shortlist_path": {
                        "type": "string",
                        "description": "Optional path to a target-shortlist.json inside allowed roots.",
                    },
                    "task_family": {"type": "string"},
                    "limit": {"type": "integer", "default": 5},
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "write_hf_external_eval_plan",
            "description": (
                "Write a local proof plan for one Hugging Face external evaluation "
                "target. This does not access tokens, upload artifacts, or claim scores."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "shortlist_path": {
                        "type": "string",
                        "description": "Optional path to a target-shortlist.json inside allowed roots.",
                    },
                    "target_id": {"type": "string"},
                    "output_dir": {
                        "type": "string",
                        "description": "Directory inside allowed roots for hf-external-eval-plan.json/md.",
                    },
                },
                "required": ["output_dir"],
                "additionalProperties": False,
            },
        },
        {
            "name": "write_cp_bench_live_verification",
            "description": (
                "Write CP-Bench live verification and target-contract artifacts. "
                "This checks public Hugging Face URLs, but never uploads results "
                "or claims leaderboard scores."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "output_dir": {
                        "type": "string",
                        "description": (
                            "Directory inside allowed roots for cp-bench live "
                            "verification JSON and Markdown."
                        ),
                    },
                    "timeout_seconds": {"type": "integer", "default": 30},
                    "include_raw": {
                        "type": "boolean",
                        "default": False,
                        "description": "Write raw HTTP excerpts alongside summary artifacts.",
                    },
                },
                "required": ["output_dir"],
                "additionalProperties": False,
            },
        },
        {
            "name": "run_cp_bench_local_baseline",
            "description": (
                "Write a CP-Bench local baseline artifact bundle. In dry-run mode "
                "this validates submission format and parser output without invoking "
                "the external evaluator or claiming scores."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "output_dir": {
                        "type": "string",
                        "description": "Directory inside allowed roots for CP-Bench P1 artifacts.",
                    },
                    "limit": {"type": "integer", "default": 1},
                    "framework": {
                        "type": "string",
                        "enum": ["CPMpy", "MiniZinc", "OR-Tools"],
                        "default": "CPMpy",
                    },
                    "dataset_version": {
                        "type": "string",
                        "enum": ["original", "verified"],
                        "default": "verified",
                    },
                    "dry_run": {
                        "type": "boolean",
                        "default": True,
                        "description": (
                            "Keep true until the local CP-Bench evaluator dependency "
                            "probe and runner are configured."
                        ),
                    },
                    "timeout_seconds": {
                        "type": "integer",
                        "default": 60,
                        "description": "Timeout for the local CP-Bench evaluator when dry_run is false.",
                    },
                },
                "required": ["output_dir"],
                "additionalProperties": False,
            },
        },
        {
            "name": "run_cp_bench_proposal_round",
            "description": (
                "Write a guarded CP-Bench proposal-round artifact bundle with "
                "rollback evidence. This never uploads to Hugging Face or claims "
                "leaderboard scores."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "baseline_report": {
                        "type": "string",
                        "description": "Baseline report JSON inside allowed roots.",
                    },
                    "proposal": {
                        "type": "string",
                        "description": "Client-generated CP-Bench proposal JSON inside allowed roots.",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Directory inside allowed roots for proposal-round artifacts.",
                    },
                },
                "required": ["baseline_report", "proposal", "output_dir"],
                "additionalProperties": False,
            },
        },
        {
            "name": "run_cp_bench_candidate_round",
            "description": (
                "Run a guarded CP-Bench candidate submission against a local "
                "baseline, compare local evaluator metrics, and write a proof "
                "bundle without uploading to Hugging Face or claiming scores."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "baseline_report": {
                        "type": "string",
                        "description": "Baseline local-eval report JSON inside allowed roots.",
                    },
                    "submission": {
                        "type": "string",
                        "description": "Candidate submission JSONL inside allowed roots.",
                    },
                    "proposal": {
                        "type": "string",
                        "description": "Optional proposal JSON inside allowed roots.",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Directory inside allowed roots for candidate-round artifacts.",
                    },
                    "framework": {
                        "type": "string",
                        "enum": ["CPMpy", "MiniZinc", "OR-Tools"],
                        "default": "CPMpy",
                    },
                    "dataset_version": {
                        "type": "string",
                        "enum": ["original", "verified"],
                        "default": "verified",
                    },
                    "timeout_seconds": {"type": "integer", "default": 60},
                },
                "required": ["baseline_report", "submission", "output_dir"],
                "additionalProperties": False,
            },
        },
        {
            "name": "build_cp_bench_proposal_context",
            "description": (
                "Write a CP-Bench proposal prompt context from local evaluator "
                "failure outcomes. This helps Codex/Claude generate bounded local "
                "candidate proposals without uploading to Hugging Face or claiming scores."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "current_report": {
                        "type": "string",
                        "description": "Candidate-round report JSON inside allowed roots.",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Directory inside allowed roots for proposal-context artifacts.",
                    },
                    "max_proposals": {"type": "integer", "default": 3},
                },
                "required": ["current_report", "output_dir"],
                "additionalProperties": False,
            },
        },
        {
            "name": "write_cp_bench_client_candidate_submission",
            "description": (
                "Write a non-reference-replay CP-Bench client candidate submission "
                "bundle. This never uploads to Hugging Face or claims leaderboard scores."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "output_dir": {
                        "type": "string",
                        "description": "Directory inside allowed roots for candidate artifacts.",
                    },
                    "limit": {"type": "integer", "default": 10},
                    "dataset_version": {
                        "type": "string",
                        "enum": ["original", "verified"],
                        "default": "verified",
                    },
                    "strategy": {
                        "type": "string",
                        "enum": ["handcrafted-small-cpmpy-v1"],
                        "default": "handcrafted-small-cpmpy-v1",
                    },
                },
                "required": ["output_dir"],
                "additionalProperties": False,
            },
        },
        {
            "name": "write_cp_bench_submission_gate",
            "description": (
                "Write a manual CP-Bench submission gate bundle with checklist, "
                "manifest, and SHA256SUMS. This never uploads to Hugging Face or "
                "claims leaderboard scores."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "submission": {
                        "type": "string",
                        "description": "Submission JSONL inside allowed roots.",
                    },
                    "source_report": {
                        "type": "string",
                        "description": "Optional local-eval/proposal report JSON inside allowed roots.",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Directory inside allowed roots for submission gate artifacts.",
                    },
                },
                "required": ["submission", "output_dir"],
                "additionalProperties": False,
            },
        },
        {
            "name": "write_smol_worldcup_live_verification",
            "description": (
                "Write Smol AI WorldCup live verification artifacts. This checks public "
                "dataset, Space, and runtime endpoints, but never uploads results or "
                "claims leaderboard scores."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "output_dir": {
                        "type": "string",
                        "description": (
                            "Directory inside allowed roots for hf-live-verification.json/md."
                        ),
                    },
                    "timeout_seconds": {"type": "integer", "default": 30},
                    "include_raw": {
                        "type": "boolean",
                        "default": False,
                        "description": "Write raw HTTP responses alongside summary artifacts.",
                    },
                },
                "required": ["output_dir"],
                "additionalProperties": False,
            },
        },
        {
            "name": "write_smol_worldcup_prompt_leakage_audit",
            "description": (
                "Write a Smol AI WorldCup prompt leakage audit. This verifies local "
                "model prompts do not expose evaluation-only markers such as "
                "answer_key or grading_rule, and never claims leaderboard scores."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "output_dir": {
                        "type": "string",
                        "description": (
                            "Directory inside allowed roots for prompt-leakage-audit.json."
                        ),
                    },
                    "timeout_seconds": {"type": "integer", "default": 30},
                    "page_size": {"type": "integer", "default": 100},
                    "limit": {"type": "integer"},
                    "prompt_profile": {
                        "type": "string",
                        "enum": [
                            "default",
                            "p3-routing-v1",
                            "p3-dev-v2",
                            "p3-semantic-v1",
                            "p3-semantic-v2",
                        ],
                        "default": "default",
                    },
                    "evaluation_split": {
                        "type": "string",
                        "enum": ["all", "dev", "canary"],
                        "default": "all",
                    },
                    "canary_fraction": {"type": "number", "default": 0.2},
                },
                "required": ["output_dir"],
                "additionalProperties": False,
            },
        },
        {
            "name": "run_smol_worldcup_local_baseline",
            "description": (
                "Run a local-compatible Smol AI WorldCup baseline and write P1 artifacts. "
                "This reads public data and scores local responses, but never uploads "
                "results or claims leaderboard scores."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "output_dir": {
                        "type": "string",
                        "description": (
                            "Directory inside allowed roots for baseline report artifacts."
                        ),
                    },
                    "timeout_seconds": {"type": "integer", "default": 30},
                    "page_size": {"type": "integer", "default": 100},
                    "limit": {"type": "integer"},
                    "strategy": {
                        "type": "string",
                        "default": "local-abstain-baseline",
                    },
                    "evaluation_split": {
                        "type": "string",
                        "enum": ["all", "dev", "canary"],
                        "default": "all",
                    },
                    "canary_fraction": {"type": "number", "default": 0.2},
                    "model_size_billion": {"type": "number", "default": 0.001},
                    "estimated_ram_gb": {"type": "number", "default": 0.01},
                },
                "required": ["output_dir"],
                "additionalProperties": False,
            },
        },
        {
            "name": "run_smol_worldcup_model_eval",
            "description": (
                "Run Smol AI WorldCup local model evaluation through an "
                "OpenAI-compatible endpoint, such as LM Studio. This writes P2 "
                "prediction, scoring, failure-case, and proposal artifacts, but never "
                "uploads results or claims leaderboard scores."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "output_dir": {
                        "type": "string",
                        "description": (
                            "Directory inside allowed roots for local model eval artifacts."
                        ),
                    },
                    "base_url": {
                        "type": "string",
                        "default": "http://127.0.0.1:1234/v1",
                        "description": "OpenAI-compatible base URL.",
                    },
                    "model": {
                        "type": "string",
                        "default": "openai/gpt-oss-20b",
                    },
                    "model_provider": {
                        "type": "string",
                        "enum": ["openai-compatible", "deepseek"],
                        "default": "openai-compatible",
                        "description": (
                            "Provider preset. deepseek uses the official DeepSeek "
                            "OpenAI-compatible API and DEEPSEEK_API_KEY by default."
                        ),
                    },
                    "api_key_env": {
                        "type": "string",
                        "description": (
                            "Environment variable name for authenticated providers. "
                            "DeepSeek defaults to DEEPSEEK_API_KEY when omitted. Only "
                            "the env var name is recorded; secret values are never "
                            "written to artifacts."
                        ),
                    },
                    "thinking_mode": {
                        "type": "string",
                        "enum": ["default", "enabled", "disabled"],
                        "default": "default",
                    },
                    "reasoning_effort": {
                        "type": "string",
                        "enum": ["high", "max"],
                    },
                    "timeout_seconds": {"type": "integer", "default": 120},
                    "page_size": {"type": "integer", "default": 100},
                    "limit": {"type": "integer"},
                    "temperature": {"type": "number", "default": 0.0},
                    "max_tokens": {"type": "integer", "default": 512},
                    "round_id": {"type": "string", "default": "round-001"},
                    "prompt_profile": {
                        "type": "string",
                        "enum": [
                            "default",
                            "p3-routing-v1",
                            "p3-dev-v2",
                            "p3-semantic-v1",
                            "p3-semantic-v2",
                        ],
                        "default": "default",
                    },
                    "evaluation_split": {
                        "type": "string",
                        "enum": ["all", "dev", "canary"],
                        "default": "all",
                    },
                    "canary_fraction": {"type": "number", "default": 0.2},
                    "judge_mode": {
                        "type": "string",
                        "enum": ["heuristic", "openai-compatible"],
                        "default": "heuristic",
                    },
                    "judge_model": {
                        "type": "string",
                        "description": (
                            "OpenAI-compatible judge model for llm_judge rows. "
                            "Defaults to model."
                        ),
                    },
                    "judge_base_url": {
                        "type": "string",
                        "description": (
                            "OpenAI-compatible judge endpoint. Defaults to base_url."
                        ),
                    },
                    "model_size_billion": {"type": "number", "default": 20.0},
                    "estimated_ram_gb": {"type": "number", "default": 32.0},
                },
                "required": ["output_dir"],
                "additionalProperties": False,
            },
        },
        {
            "name": "run_smol_worldcup_proposal_round",
            "description": (
                "Validate a client proposal contract and run one guarded Smol AI "
                "WorldCup local diagnostic round. This may call a configured local "
                "OpenAI-compatible endpoint, but never uploads or claims official scores."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "proposal": {"type": "object"},
                    "proposal_file": {"type": "string"},
                    "output_dir": {"type": "string"},
                    "current_report": {"type": "string"},
                    "baseline_report": {"type": "string"},
                    "base_url": {
                        "type": "string",
                        "default": "http://127.0.0.1:1234/v1",
                    },
                    "model": {"type": "string", "default": "openai/gpt-oss-20b"},
                    "model_provider": {
                        "type": "string",
                        "enum": ["openai-compatible", "deepseek"],
                        "default": "openai-compatible",
                    },
                    "api_key_env": {"type": "string"},
                    "thinking_mode": {
                        "type": "string",
                        "enum": ["default", "enabled", "disabled"],
                        "default": "default",
                    },
                    "reasoning_effort": {"type": "string", "enum": ["high", "max"]},
                    "timeout_seconds": {"type": "integer", "default": 120},
                    "page_size": {"type": "integer", "default": 100},
                    "limit": {"type": "integer"},
                    "temperature": {"type": "number", "default": 0.0},
                    "max_tokens": {"type": "integer", "default": 512},
                    "round_id": {"type": "string"},
                    "prompt_profile": {
                        "type": "string",
                        "enum": [
                            "default",
                            "p3-routing-v1",
                            "p3-dev-v2",
                            "p3-semantic-v1",
                            "p3-semantic-v2",
                        ],
                    },
                    "evaluation_split": {
                        "type": "string",
                        "enum": ["all", "dev", "canary"],
                        "default": "dev",
                    },
                    "canary_fraction": {"type": "number", "default": 0.2},
                    "judge_mode": {
                        "type": "string",
                        "enum": ["heuristic", "openai-compatible"],
                        "default": "heuristic",
                    },
                    "judge_model": {"type": "string"},
                    "judge_base_url": {"type": "string"},
                    "model_size_billion": {"type": "number", "default": 20.0},
                    "estimated_ram_gb": {"type": "number", "default": 32.0},
                    "allowed_change_surfaces": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["output_dir"],
                "anyOf": [
                    {"required": ["proposal"]},
                    {"required": ["proposal_file"]},
                ],
                "additionalProperties": False,
            },
        },
        {
            "name": "run_smol_worldcup_rescore",
            "description": (
                "Rescore an existing Smol AI WorldCup prediction.jsonl with scorer-v2. "
                "This writes scoring-adapter audit artifacts and a confidence "
                "calibration dual-track report, but never uploads results or claims "
                "leaderboard scores."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "output_dir": {
                        "type": "string",
                        "description": "Directory inside allowed roots for rescore artifacts.",
                    },
                    "prediction_path": {
                        "type": "string",
                        "description": "Existing Smol WorldCup prediction.jsonl to rescore.",
                    },
                    "source_report": {
                        "type": "string",
                        "description": "Optional source model-eval report for provenance.",
                    },
                    "source_rows": {
                        "type": "string",
                        "description": "Optional local source rows JSON/JSONL; defaults to public dataset fetch.",
                    },
                    "source_run_id": {"type": "string"},
                    "timeout_seconds": {"type": "integer", "default": 30},
                    "page_size": {"type": "integer", "default": 100},
                    "preserve_llm_judge_scores": {
                        "type": "boolean",
                        "default": True,
                        "description": (
                            "Preserve existing llm_judge scores unless a fresh judge "
                            "run is explicitly implemented."
                        ),
                    },
                    "model_size_billion": {"type": "number", "default": 20.0},
                    "estimated_ram_gb": {"type": "number", "default": 32.0},
                },
                "required": ["output_dir", "prediction_path"],
                "additionalProperties": False,
            },
        },
        {
            "name": "write_smol_worldcup_rescore_proof_archive",
            "description": (
                "Package formal Smol AI WorldCup scorer-v2 rescore artifacts into a "
                "hash-indexed proof archive. This is publication evidence only and "
                "never claims Hugging Face leaderboard scores."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "output_dir": {
                        "type": "string",
                        "description": "Directory inside allowed roots for proof archive.",
                    },
                    "rescore_dir": {
                        "type": "string",
                        "description": "Directory containing formal rescore artifacts.",
                    },
                    "source_report": {
                        "type": "string",
                        "description": "Optional source model-eval report for provenance.",
                    },
                    "source_prediction_path": {
                        "type": "string",
                        "description": "Optional original prediction.jsonl for provenance.",
                    },
                    "source_run_id": {"type": "string"},
                    "command_lines": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Command lines to record in the archive.",
                    },
                },
                "required": ["output_dir", "rescore_dir"],
                "additionalProperties": False,
            },
        },
        {
            "name": "write_smol_worldcup_submission_probe",
            "description": (
                "Probe the public Smol AI WorldCup HF Space submission API without "
                "launching evaluation. Use this before any real Hugging Face "
                "submission decision."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "output_dir": {
                        "type": "string",
                        "description": "Directory inside allowed roots for probe artifacts.",
                    },
                    "model": {
                        "type": "string",
                        "default": "openai/gpt-oss-20b",
                    },
                    "timeout_seconds": {"type": "integer", "default": 30},
                    "include_raw": {
                        "type": "boolean",
                        "default": True,
                        "description": "Write raw HTTP responses alongside probe summary.",
                    },
                },
                "required": ["output_dir"],
                "additionalProperties": False,
            },
        },
        {
            "name": "prepare_official_mle_bench_workspace",
            "description": (
                "Create an agent-editable workspace from already prepared official "
                "MLE-bench data. This tool does not download data or claim leaderboard scores."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "competition_id": {"type": "string"},
                    "prepared_competition_dir": {
                        "type": "string",
                        "description": (
                            "Path to one competition directory containing prepared/public."
                        ),
                    },
                    "runtime_root": {"type": "string"},
                    "workspace_name": {"type": "string"},
                },
                "required": [
                    "competition_id",
                    "prepared_competition_dir",
                    "runtime_root",
                ],
                "additionalProperties": False,
            },
        },
        {
            "name": "grade_official_mle_bench_submission",
            "description": (
                "Run official `mlebench grade-sample` on a local submission and return "
                "bounded scorer feedback. The output is not a leaderboard score claim."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "competition_id": {"type": "string"},
                    "submission": {"type": "string"},
                    "data_dir": {
                        "type": "string",
                        "description": "MLE-bench data root containing the prepared competition.",
                    },
                    "mlebench": {
                        "type": "string",
                        "description": "Path to the official mlebench executable.",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Directory for grade-report.json and grade.log.",
                    },
                    "timeout_seconds": {"type": "integer", "default": 300},
                },
                "required": [
                    "competition_id",
                    "submission",
                    "data_dir",
                    "mlebench",
                    "output_dir",
                ],
                "additionalProperties": False,
            },
        },
        {
            "name": "run_official_mle_bench_round",
            "description": (
                "Run an agent workspace `solve.py`, grade the resulting `submission.csv` "
                "with official `mlebench grade-sample`, and return solve/grade artifacts. "
                "The output is local debug feedback, not a leaderboard score claim."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "competition_id": {"type": "string"},
                    "workspace": {
                        "type": "string",
                        "description": "Agent-editable workspace containing solve.py.",
                    },
                    "data_dir": {
                        "type": "string",
                        "description": "MLE-bench data root containing the prepared competition.",
                    },
                    "mlebench": {
                        "type": "string",
                        "description": "Path to the official mlebench executable.",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Directory for round-report.json, solve.log, and grade files.",
                    },
                    "python": {
                        "type": "string",
                        "description": "Python executable used to run solve.py.",
                    },
                    "round_id": {"type": "string", "default": "round-001"},
                    "timeout_seconds": {"type": "integer", "default": 300},
                },
                "required": [
                    "competition_id",
                    "workspace",
                    "data_dir",
                    "mlebench",
                    "output_dir",
                ],
                "additionalProperties": False,
            },
        },
        {
            "name": "run_official_mle_bench_patch_round",
            "description": (
                "Apply a bounded Codex/Claude-generated diff to an official MLE-bench "
                "workspace, run `solve.py`, grade `submission.csv`, and return patch and "
                "round artifacts. The output is local debug feedback, not a leaderboard claim."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "competition_id": {"type": "string"},
                    "workspace": {
                        "type": "string",
                        "description": "Agent-editable workspace containing solve.py.",
                    },
                    "data_dir": {
                        "type": "string",
                        "description": "MLE-bench data root containing the prepared competition.",
                    },
                    "mlebench": {
                        "type": "string",
                        "description": "Path to the official mlebench executable.",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Directory for patch-round artifacts.",
                    },
                    "patch": {
                        "type": "string",
                        "description": "Unified diff targeting solve.py or submission.csv.",
                    },
                    "allowed_files": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Optional narrower allowlist. Defaults to solve.py and submission.csv.",
                    },
                    "python": {
                        "type": "string",
                        "description": "Python executable used to run solve.py.",
                    },
                    "round_id": {"type": "string", "default": "round-001"},
                    "timeout_seconds": {"type": "integer", "default": 300},
                    "test_timeout_seconds": {"type": "integer", "default": 60},
                },
                "required": [
                    "competition_id",
                    "workspace",
                    "data_dir",
                    "mlebench",
                    "output_dir",
                    "patch",
                ],
                "additionalProperties": False,
            },
        },
        {
            "name": "write_official_mle_bench_patch_round_proof_bundle",
            "description": (
                "Package a persisted official MLE-bench patch-round report into proof "
                "artifacts, a publication guard, and a hashed archive. This does not "
                "claim leaderboard scores."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "patch_round_report": {
                        "type": "string",
                        "description": "Path to patch-round-report.json from mle-patch-round.",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Directory where manifest, artifacts, and archive are written.",
                    },
                },
                "required": ["patch_round_report", "output_dir"],
                "additionalProperties": False,
            },
        },
        {
            "name": "run_fasttext_patch_round",
            "description": (
                "Run one bounded Codex/Claude-proposed fastText hyperparameter patch "
                "round against an archived AG News baseline. The output is local proof "
                "feedback, not a leaderboard score claim."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "target_spec": {
                        "type": "string",
                        "description": "Path to full-reproduction-target.json.",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Directory for patch round artifacts.",
                    },
                    "ag_news_train_csv": {"type": "string"},
                    "ag_news_test_csv": {"type": "string"},
                    "fasttext_binary": {"type": "string"},
                    "baseline_report": {
                        "type": "string",
                        "description": "Path to fasttext-baseline-report.json.",
                    },
                    "proposal": {
                        "type": "object",
                        "description": "Client proposal with proposal_id, reason, and train_args.",
                    },
                    "max_train_seconds": {"type": "integer", "default": 300},
                },
                "required": [
                    "target_spec",
                    "output_dir",
                    "ag_news_train_csv",
                    "ag_news_test_csv",
                    "fasttext_binary",
                    "baseline_report",
                    "proposal",
                ],
                "additionalProperties": False,
            },
        },
        {
            "name": "write_fasttext_patch_round_proof_bundle",
            "description": (
                "Package a completed fastText patch round into a human-reviewed, "
                "hash-indexed proof bundle. This preserves official_scores_claimed=false."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "patch_round_report": {
                        "type": "string",
                        "description": "Path to improvement-report.json from run_fasttext_patch_round.",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Directory where the proof bundle is written.",
                    },
                    "reviewer": {
                        "type": "string",
                        "default": "local-review",
                    },
                    "review_status": {
                        "type": "string",
                        "enum": [
                            "approved_with_limitations",
                            "needs_more_evidence",
                            "rejected",
                        ],
                        "default": "approved_with_limitations",
                    },
                },
                "required": ["patch_round_report", "output_dir"],
                "additionalProperties": False,
            },
        },
        {
            "name": "run_fasttext_multi_proposal_loop",
            "description": (
                "Run several bounded Codex/Claude-proposed fastText hyperparameter "
                "proposals, preserve failed rounds, and return best-so-far rollback "
                "state. The output is local proof feedback, not a leaderboard score."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "target_spec": {
                        "type": "string",
                        "description": "Path to full-reproduction-target.json.",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Directory for multi-round artifacts.",
                    },
                    "ag_news_train_csv": {"type": "string"},
                    "ag_news_test_csv": {"type": "string"},
                    "fasttext_binary": {"type": "string"},
                    "baseline_report": {
                        "type": "string",
                        "description": "Path to fasttext-baseline-report.json.",
                    },
                    "proposals": {
                        "type": "array",
                        "items": {"type": "object"},
                        "description": (
                            "Client proposals with proposal_id, reason, and train_args. "
                            "Invalid proposals are recorded as failed rounds."
                        ),
                    },
                    "max_train_seconds": {"type": "integer", "default": 300},
                },
                "required": [
                    "target_spec",
                    "output_dir",
                    "ag_news_train_csv",
                    "ag_news_test_csv",
                    "fasttext_binary",
                    "baseline_report",
                    "proposals",
                ],
                "additionalProperties": False,
            },
        },
        {
            "name": "write_fasttext_release_proof_bundle",
            "description": (
                "Package reviewed fastText proof artifacts into a downloadable tar.gz "
                "with SHA-256 and a human review checklist. This preserves "
                "official_scores_claimed=false."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "proof_manifest": {
                        "type": "string",
                        "description": "Path to proof-manifest.json from the P4 proof bundle.",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Directory where release proof files are written.",
                    },
                    "multi_round_report": {
                        "type": "string",
                        "description": "Optional P5 multi-round-report.json to include.",
                    },
                    "reviewer": {"type": "string", "default": "local-review"},
                },
                "required": ["proof_manifest", "output_dir"],
                "additionalProperties": False,
            },
        },
        {
            "name": "prepare_paperbench_codex_review_bundle",
            "description": (
                "Prepare PaperBench run artifacts, paper text, and rubric for "
                "Codex-assisted rubric review. This does not call any API or claim "
                "official PaperBench scores."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "run_dir": {
                        "type": "string",
                        "description": "PaperBench task run directory containing grade.json.",
                    },
                    "paper_dir": {
                        "type": "string",
                        "description": "Official PaperBench paper directory containing paper.md and rubric.json.",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Directory where the Codex review packet and prompt are written.",
                    },
                },
                "required": ["run_dir", "paper_dir", "output_dir"],
                "additionalProperties": False,
            },
        },
        {
            "name": "write_paperbench_codex_review_report",
            "description": (
                "Persist a Codex-supplied PaperBench rubric review with evidence "
                "references. The report is explicitly not an official PaperBench score."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "bundle": {
                        "type": "string",
                        "description": "Path to codex-review-bundle.json.",
                    },
                    "review": {
                        "type": "object",
                        "description": "Codex review JSON matching the bundle review_schema.",
                    },
                    "output_dir": {
                        "type": "string",
                        "description": "Directory where codex-review-report.json/md are written.",
                    },
                },
                "required": ["bundle", "review", "output_dir"],
                "additionalProperties": False,
            },
        },
        {
            "name": "record_research_memory",
            "description": (
                "Append public, provenance-backed research memory cards. This records "
                "evidence only; it does not run experiments or claim official scores."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "store": {
                        "type": "string",
                        "description": "JSONL memory store path inside allowed roots.",
                    },
                    "card": {
                        "type": "object",
                        "description": "One ResearchMemoryCard payload.",
                    },
                    "release_manifest": {
                        "type": "string",
                        "description": "Optional fastText release-proof-manifest.json.",
                    },
                    "multi_round_report": {
                        "type": "string",
                        "description": "Optional fastText multi-round-report.json.",
                    },
                    "review_checklist": {
                        "type": "string",
                        "description": "Optional fastText release-review-checklist.md.",
                    },
                    "sync_adapters": {
                        "type": "boolean",
                        "default": False,
                        "description": (
                            "Explicitly sync recorded cards to configured optional "
                            "Graphiti/cognee adapters."
                        ),
                    },
                    "adapters": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["graphiti", "cognee"]},
                        "description": "Optional adapter allowlist for sync/search.",
                    },
                },
                "required": ["store"],
                "additionalProperties": False,
            },
        },
        {
            "name": "retrieve_research_memory",
            "description": (
                "Search prior research memory and return card provenance, scores, "
                "and match reasons."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "store": {"type": "string"},
                    "query": {"type": "string"},
                    "paper_id": {"type": "string"},
                    "dataset": {"type": "string"},
                    "metric_name": {"type": "string"},
                    "patch_type": {"type": "string"},
                    "failure_category": {"type": "string"},
                    "limit": {"type": "integer", "default": 10},
                    "include_adapters": {
                        "type": "boolean",
                        "default": False,
                        "description": (
                            "Explicitly include configured optional Graphiti/cognee "
                            "adapter search results."
                        ),
                    },
                    "adapters": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["graphiti", "cognee"]},
                        "description": "Optional adapter allowlist for sync/search.",
                    },
                },
                "required": ["store"],
                "additionalProperties": False,
            },
        },
        {
            "name": "suggest_from_memory",
            "description": (
                "Return advisory next-step suggestions from memory. Suggestions never "
                "execute the recommended MCP tools."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "store": {"type": "string"},
                    "query": {"type": "string"},
                    "paper_id": {"type": "string"},
                    "dataset": {"type": "string"},
                    "limit": {"type": "integer", "default": 5},
                },
                "required": ["store", "query"],
                "additionalProperties": False,
            },
        },
        {
            "name": "promote_memory_card",
            "description": (
                "Append a promoted copy of a memory card after client or human review. "
                "Promotion is auditable and keeps original evidence references."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "store": {"type": "string"},
                    "card_id": {"type": "string"},
                    "promoted_card_id": {"type": "string"},
                },
                "required": ["store", "card_id"],
                "additionalProperties": False,
            },
        },
        {
            "name": "audit_memory_trace",
            "description": (
                "Return evidence cards, artifact hashes, and claim boundaries for "
                "selected memory IDs."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "store": {"type": "string"},
                    "card_ids": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "required": ["store", "card_ids"],
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
            "name": "build_proposal_context",
            "description": (
                "Write a non-executing artifact bundle and prompt contract that "
                "Codex/Claude can use to generate structured proposal JSON."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "objective": {"type": "string"},
                    "output_dir": {"type": "string"},
                    "baseline_report": {"type": "string"},
                    "current_report": {"type": "string"},
                    "dev_report": {"type": "string"},
                    "canary_report": {"type": "string"},
                    "category_deltas": {"type": "string"},
                    "failure_samples": {"type": "string"},
                    "rollback_summary": {"type": "string"},
                    "previous_proposals": {"type": "string"},
                    "memory_cards": {"type": "string"},
                    "memory_store": {"type": "string"},
                    "memory_query": {"type": "object"},
                    "memory_limit": {"type": "integer", "default": 5},
                    "resource_constraints": {"type": "object"},
                    "allowed_change_surfaces": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                    "max_proposals": {"type": "integer", "default": 3},
                    "overwrite": {"type": "boolean", "default": False},
                },
                "required": ["objective", "output_dir"],
                "additionalProperties": False,
            },
        },
        {
            "name": "validate_client_proposal_contract",
            "description": (
                "Validate client-generated proposal JSON before any execution tool "
                "is called."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "proposal": {"type": "object"},
                    "proposal_file": {"type": "string"},
                    "allowed_change_surfaces": {
                        "type": "array",
                        "items": {"type": "string"},
                    },
                },
                "additionalProperties": False,
            },
        },
        {
            "name": "write_proposal_reflection",
            "description": (
                "Write non-executing proposal reflection artifacts from evaluator "
                "feedback, failure labels, and rollback reasons."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "proposal": {"type": "object"},
                    "proposal_file": {"type": "string"},
                    "evaluation": {"type": "object"},
                    "evaluation_file": {"type": "string"},
                    "output_dir": {"type": "string"},
                    "overwrite": {"type": "boolean", "default": False},
                    "memory_store": {"type": "string"},
                    "sync_adapters": {"type": "boolean", "default": False},
                    "adapter_names": {
                        "type": "array",
                        "items": {"type": "string", "enum": ["graphiti", "cognee"]},
                    },
                },
                "required": ["output_dir"],
                "allOf": [
                    {
                        "anyOf": [
                            {"required": ["proposal"]},
                            {"required": ["proposal_file"]},
                        ],
                    },
                    {
                        "anyOf": [
                            {"required": ["evaluation"]},
                            {"required": ["evaluation_file"]},
                        ],
                    },
                ],
                "additionalProperties": False,
            },
        },
        {
            "name": "summarize_proposal_search",
            "description": (
                "Summarize a small proposal portfolio/tree frontier from client-provided "
                "proposal, evaluation, and reflection objects. This never runs experiments."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "items": {
                        "type": "array",
                        "items": {"type": "object"},
                    },
                    "branch_budget": {"type": "integer"},
                    "diversity_constraint": {"type": "object"},
                },
                "required": ["items"],
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
    harness_probe = build_official_harness_probe()
    proof_plan = build_public_proof_plan(harness_probe)
    publication_manifest = _sample_publication_manifest()
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
            "deduplication_report",
            "cache_summary",
            "provider_quality_matrix",
            "provider_coverage",
            "source_rankings",
            "retrieval_diagnostics",
            "research_case",
            "research_evidence_gate",
            "dataset_profile",
            "experiment_tree",
            "loop_policy",
            "failure_diagnostics",
            "metric_stop_policy",
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
            "proposal_context",
            "proposal_contract.validation",
            "proposal_reflection",
            "proposal_search.frontier",
            "benchmark_adapters",
            "benchmark_adapters.adapters",
            "benchmark_adapters.combined_smoke",
            "benchmark_harness_probe",
            "benchmark_proof_plan",
            "benchmark_proof_setup",
            "benchmark_proof_publication",
            "benchmark_proof_archive",
            "hf_external_eval_targets",
            "hf_external_eval_plan",
            "cp_bench_live_verification",
            "cp_bench_local_baseline",
            "cp_bench_proposal_round",
            "cp_bench_candidate_round",
            "cp_bench_proposal_context",
            "cp_bench_client_candidate",
            "cp_bench_submission_gate",
            "smol_worldcup_live_verification",
            "smol_worldcup_prompt_leakage_audit",
            "smol_worldcup_local_baseline",
            "smol_worldcup_model_eval",
            "smol_worldcup_proposal_round",
            "smol_worldcup_rescore",
            "smol_worldcup_rescore_proof_archive",
            "smol_worldcup_submission_probe",
            "official_mle_agent_workspace",
            "official_mle_grade_sample",
            "official_mle_solver_round",
            "official_mle_patch_round",
            "official_mle_patch_proof_archive",
            "full_reproduction_fasttext_patch_round",
            "full_reproduction_fasttext_patch_proof_bundle",
            "full_reproduction_fasttext_multi_proposal_loop",
            "full_reproduction_fasttext_release_proof_bundle",
            "paperbench_codex_review_bundle",
            "paperbench_codex_review_report",
            "research_memory",
            "research_memory.suggestions",
            "research_memory.trace",
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
        "benchmark_adapters": build_benchmark_readiness(),
        "benchmark_harness_probe": harness_probe,
        "benchmark_proof_plan": proof_plan,
        "benchmark_proof_setup": build_official_proof_setup_bundle(proof_plan),
        "benchmark_proof_publication": build_proof_publication_bundle(
            publication_manifest,
            PROJECT_ROOT,
        ),
        "benchmark_proof_archive": build_proof_archive_bundle(
            publication_manifest,
            PROJECT_ROOT,
        ),
        "hf_external_eval_targets": _hf_external_eval_manifest(),
        "hf_external_eval_plan": build_hf_external_eval_plan(),
        "cp_bench_live_verification": {
            "status": "explicit_tool_only",
            "target_id": "cp-bench-constraint-modeling",
            "tool": "write_cp_bench_live_verification",
            "network_access": "required_on_call",
            "manual_submission_required": True,
            "official_scores_claimed": False,
            "claim_boundary": (
                "CP-Bench live verification and target contract only; not a Hugging "
                "Face submission, leaderboard score, or ranking"
            ),
        },
        "cp_bench_local_baseline": {
            "status": "explicit_tool_only",
            "target_id": "cp-bench-constraint-modeling",
            "tool": "run_cp_bench_local_baseline",
            "default_framework": "CPMpy",
            "default_dataset_version": "verified",
            "default_dry_run": True,
            "local_eval_dependency_gate": "available_when_dry_run_false",
            "manual_submission_required": True,
            "official_scores_claimed": False,
            "claim_boundary": (
                "CP-Bench local baseline artifact only; dry-run mode does not invoke "
                "the evaluator, non-dry-run mode writes local evaluator or blocked "
                "dependency artifacts, and neither path claims a leaderboard score"
            ),
        },
        "cp_bench_proposal_round": {
            "status": "explicit_tool_only",
            "target_id": "cp-bench-constraint-modeling",
            "tool": "run_cp_bench_proposal_round",
            "manual_submission_required": True,
            "official_scores_claimed": False,
            "claim_boundary": (
                "CP-Bench proposal rounds record proposal guards and rollback "
                "evidence only; they do not upload to Hugging Face or claim scores"
            ),
        },
        "cp_bench_candidate_round": {
            "status": "explicit_tool_only",
            "target_id": "cp-bench-constraint-modeling",
            "tool": "run_cp_bench_candidate_round",
            "manual_submission_required": True,
            "external_submission_status": "not_submitted",
            "official_scores_claimed": False,
            "claim_boundary": (
                "CP-Bench candidate rounds run local evaluator feedback for "
                "client-generated submissions only; they do not upload to Hugging "
                "Face or claim leaderboard scores"
            ),
        },
        "cp_bench_proposal_context": {
            "status": "explicit_tool_only",
            "target_id": "cp-bench-constraint-modeling",
            "tool": "build_cp_bench_proposal_context",
            "manual_submission_required": True,
            "external_submission_status": "not_submitted",
            "official_scores_claimed": False,
            "claim_boundary": (
                "CP-Bench proposal contexts only guide client-side proposal "
                "generation from local evaluator outcomes; they do not execute "
                "submissions, upload to Hugging Face, or claim leaderboard scores"
            ),
        },
        "cp_bench_client_candidate": {
            "status": "explicit_tool_only",
            "target_id": "cp-bench-constraint-modeling",
            "tool": "write_cp_bench_client_candidate_submission",
            "manual_submission_required": True,
            "external_submission_status": "not_submitted",
            "official_scores_claimed": False,
            "claim_boundary": (
                "CP-Bench client candidates are local non-reference-replay "
                "submission bundles; they must be verified by local evaluator "
                "artifacts before any manual submission gate."
            ),
        },
        "cp_bench_submission_gate": {
            "status": "explicit_tool_only",
            "target_id": "cp-bench-constraint-modeling",
            "tool": "write_cp_bench_submission_gate",
            "manual_submission_required": True,
            "external_submission_status": "not_submitted",
            "official_scores_claimed": False,
            "claim_boundary": (
                "CP-Bench submission gate bundles prepare files for manual review "
                "only; they do not upload to Hugging Face or claim scores"
            ),
        },
        "smol_worldcup_live_verification": {
            "status": "explicit_tool_only",
            "target_id": "smol-ai-worldcup-shift",
            "tool": "write_smol_worldcup_live_verification",
            "network_access": "required_on_call",
            "official_scores_claimed": False,
        },
        "smol_worldcup_prompt_leakage_audit": {
            "status": "explicit_tool_only",
            "target_id": "smol-ai-worldcup-shift",
            "tool": "write_smol_worldcup_prompt_leakage_audit",
            "default_prompt_profile": "default",
            "p3_prompt_profile": "p3-routing-v1",
            "p3_dev_prompt_profile": "p3-dev-v2",
            "blocked_terms": [
                "answer_key",
                "grading_rule",
                "test_case",
                "correct_answer",
            ],
            "official_scores_claimed": False,
            "claim_boundary": "prompt leakage audit only; not a hidden-test proof",
        },
        "smol_worldcup_local_baseline": {
            "status": "explicit_tool_only",
            "target_id": "smol-ai-worldcup-shift",
            "tool": "run_smol_worldcup_local_baseline",
            "default_strategy": "local-abstain-baseline",
            "default_evaluation_split": "all",
            "future_holdout_split": "canary",
            "official_scores_claimed": False,
            "claim_boundary": "local-compatible baseline only; not a Hugging Face score",
        },
        "smol_worldcup_model_eval": {
            "status": "explicit_tool_only",
            "target_id": "smol-ai-worldcup-shift",
            "tool": "run_smol_worldcup_model_eval",
            "default_model": "openai/gpt-oss-20b",
            "default_base_url": "http://127.0.0.1:1234/v1",
            "default_prompt_profile": "default",
            "p3_prompt_profile": "p3-routing-v1",
            "p3_dev_prompt_profile": "p3-dev-v2",
            "default_evaluation_split": "all",
            "future_holdout_split": "canary",
            "judge_independence_boundary": (
                "same model and endpoint is self_judge; use different judge_model "
                "or judge_base_url for independent_judge_configured"
            ),
            "official_scores_claimed": False,
            "claim_boundary": (
                "local LM Studio/OpenAI-compatible model evaluation only; "
                "not a Hugging Face leaderboard score"
            ),
        },
        "smol_worldcup_proposal_round": {
            "status": "explicit_tool_only",
            "target_id": "smol-ai-worldcup-shift",
            "tool": "run_smol_worldcup_proposal_round",
            "default_evaluation_split": "dev",
            "promotion_split": "canary",
            "executes_after_contract_validation": True,
            "official_scores_claimed": False,
            "claim_boundary": (
                "validated proposal to local diagnostic model eval only; "
                "not a Hugging Face submission or official score"
            ),
        },
        "smol_worldcup_rescore": {
            "status": "explicit_tool_only",
            "target_id": "smol-ai-worldcup-shift",
            "tool": "run_smol_worldcup_rescore",
            "scorer_profile": "scorer-v2-response-normalizer",
            "preserve_llm_judge_scores_default": True,
            "writes_confidence_dual_track_report": True,
            "official_scores_claimed": False,
            "claim_boundary": (
                "scoring-adapter audit of existing predictions only; not a new model "
                "run or Hugging Face leaderboard score"
            ),
        },
        "smol_worldcup_rescore_proof_archive": {
            "status": "explicit_tool_only",
            "target_id": "smol-ai-worldcup-shift",
            "tool": "write_smol_worldcup_rescore_proof_archive",
            "archive_type": "proof_archive",
            "official_scores_claimed": False,
            "claim_boundary": (
                "hash-indexed formal rescore artifact archive only; not a Hugging "
                "Face submission or leaderboard score"
            ),
        },
        "smol_worldcup_submission_probe": {
            "status": "explicit_tool_only",
            "target_id": "smol-ai-worldcup-shift",
            "tool": "write_smol_worldcup_submission_probe",
            "submission_action": "not_launched",
            "network_access": "required_on_call",
            "official_scores_claimed": False,
            "claim_boundary": (
                "submission API probe only; it never launches evaluation or claims "
                "official leaderboard scores"
            ),
        },
        "research_memory": {
            "status": "preview",
            "default_store": ".demo_runs/research-memory/memory.jsonl",
            "optional_adapters": ["graphiti", "cognee"],
            "executes_tools": False,
            "claim_boundary": "retrieval and suggestions only; not new proof",
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
        "skill_package": {
            "status": "repo_local",
            "install_command": "ml-loop init-skills",
            "docs": "docs/skills-setup-cn.md",
            "default_codex_target": "~/.codex/skills",
            "default_claude_target": "~/.claude/skills",
        },
        "recommended_skills": list(RECOMMENDED_SKILLS),
        "skill_contracts": build_skill_contracts(),
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
                    "build_proposal_context",
                    "validate_client_proposal_contract",
                    "run_client_patch_experiment",
                    "apply_client_code_patch",
                    "review_research_results",
                    "write_proposal_reflection",
                    "summarize_proposal_search",
                ],
                "handoff": (
                    "Use when the client model wants to propose the next metric move. "
                    "First build a context bundle, validate the generated proposal "
                    "contract, execute only accepted proposals through guarded tools, "
                    "then write a reflection artifact with failure labels and rollback "
                    "state."
                ),
            },
            {
                "name": "benchmark_proof_lifecycle",
                "tools": [
                    "get_benchmark_harness_probe",
                    "plan_benchmark_proof_run",
                    "write_benchmark_proof_setup_bundle",
                    "write_benchmark_proof_publication_bundle",
                    "write_benchmark_proof_archive",
                ],
                "handoff": (
                    "Use for official/debug benchmark proof work. These tools prepare, "
                    "validate, publish, and archive artifacts; they do not launch "
                    "official evaluations or claim leaderboard scores by themselves."
                ),
            },
            {
                "name": "hf_external_validation",
                "tools": [
                    "get_hf_external_eval_targets",
                    "write_hf_external_eval_plan",
                    "write_cp_bench_live_verification",
                    "run_cp_bench_local_baseline",
                    "run_cp_bench_proposal_round",
                    "run_cp_bench_candidate_round",
                    "build_cp_bench_proposal_context",
                    "write_cp_bench_client_candidate_submission",
                    "write_cp_bench_submission_gate",
                    "write_smol_worldcup_live_verification",
                    "write_smol_worldcup_prompt_leakage_audit",
                    "run_smol_worldcup_local_baseline",
                    "run_smol_worldcup_model_eval",
                    "run_smol_worldcup_proposal_round",
                    "run_smol_worldcup_rescore",
                    "write_smol_worldcup_rescore_proof_archive",
                    "write_smol_worldcup_submission_probe",
                    "write_benchmark_proof_publication_bundle",
                    "write_benchmark_proof_archive",
                ],
                "handoff": (
                    "Use before attempting Hugging Face competitions or leaderboards. "
                    "The client model selects a target, writes a local proof plan, runs "
                    "live verification, baseline/iteration work through explicit tools, "
                    "and only submits externally after human confirmation."
                ),
            },
            {
                "name": "official_mle_agent_loop",
                "tools": [
                    "prepare_official_mle_bench_workspace",
                    "apply_client_code_patch",
                    "run_official_mle_bench_patch_round",
                    "run_official_mle_bench_round",
                    "grade_official_mle_bench_submission",
                    "write_official_mle_bench_patch_round_proof_bundle",
                    "write_benchmark_proof_publication_bundle",
                    "write_benchmark_proof_archive",
                ],
                "handoff": (
                    "Use after MLE-bench data has already been prepared. The client model "
                    "reads the latest round report, generates a bounded patch, then calls "
                    "run_official_mle_bench_patch_round to apply it, execute solve.py, grade "
                    "the local submission, return loop feedback, and write an MLE patch proof "
                    "bundle before reviewing publication/archive evidence."
                ),
            },
            {
                "name": "fasttext_reproduction_patch_loop",
                "tools": [
                    "run_fasttext_patch_round",
                    "write_fasttext_patch_round_proof_bundle",
                    "run_fasttext_multi_proposal_loop",
                    "write_fasttext_release_proof_bundle",
                    "write_benchmark_proof_publication_bundle",
                    "write_benchmark_proof_archive",
                ],
                "handoff": (
                    "Use after a trusted fastText AG News baseline exists. Codex/Claude "
                    "proposes allowlisted supervised hyperparameter changes, MCP runs "
                    "the selected binary, records failed proposals and best-so-far "
                    "rollback state, then packages reviewed proof artifacts for "
                    "download with official_scores_claimed=false."
                ),
            },
            {
                "name": "paperbench_codex_assisted_review",
                "tools": [
                    "prepare_paperbench_codex_review_bundle",
                    "write_paperbench_codex_review_report",
                    "write_benchmark_proof_publication_bundle",
                    "write_benchmark_proof_archive",
                ],
                "handoff": (
                    "Use when official PaperBench real-judge credentials are unavailable "
                    "or when the operator wants a client-model audit first. The MCP "
                    "service prepares the evidence packet and prompt, Codex/Claude "
                    "performs the rubric review, and write_paperbench_codex_review_report "
                    "records the result with official_scores_claimed=false."
                ),
            },
            {
                "name": "research_memory_loop",
                "tools": [
                    "retrieve_research_memory",
                    "suggest_from_memory",
                    "audit_memory_trace",
                    "record_research_memory",
                    "promote_memory_card",
                ],
                "handoff": (
                    "Use before patch planning to retrieve prior failures and useful "
                    "configurations, then audit provenance before the client model acts. "
                    "Suggestions are advisory and never execute tools by themselves."
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
            "python3 scripts/proposal_contract_smoke.py --output-dir .demo_runs/proposal-contract --json",
            "python3 scripts/benchmark_adapter_smoke.py --json",
            "python3 scripts/benchmark_harness_probe.py --json",
            "python3 scripts/benchmark_proof_plan.py --json",
            "python3 scripts/benchmark_proof_setup.py --output-dir .demo_runs/proof-setup --json",
            "python3 scripts/benchmark_proof_publication.py --manifest <proof-manifest.json> --artifact-root <proof-artifacts> --output-dir <publication> --json",
            "python3 scripts/benchmark_proof_archive.py --manifest <proof-manifest.json> --artifact-root <proof-artifacts> --output-dir <archive> --json",
            "ml-loop benchmark mle-workspace --competition-id <id> --prepared-competition-dir <prepared-competition-dir> --runtime-root <runtime> --json",
            "ml-loop benchmark mle-grade --competition-id <id> --submission <workspace/submission.csv> --data-dir <mlebench-data> --mlebench <mlebench> --output-dir <reports> --json",
            "ml-loop benchmark mle-round --competition-id <id> --workspace <workspace> --data-dir <mlebench-data> --mlebench <mlebench> --output-dir <rounds> --json",
            "ml-loop benchmark mle-patch-round --competition-id <id> --workspace <workspace> --data-dir <mlebench-data> --mlebench <mlebench> --output-dir <rounds> --patch-file <patch.diff> --json",
            "ml-loop benchmark mle-patch-proof --patch-round-report <rounds/round-id/patch-round-report.json> --output-dir <proof-dir> --json",
            "ml-loop benchmark paperbench-codex-review-bundle --run-dir <paperbench-run-dir> --paper-dir <paperbench-paper-dir> --output-dir <review-bundle> --json",
            "ml-loop benchmark paperbench-codex-review-report --bundle <review-bundle/codex-review-bundle.json> --review-file <codex-review.json> --output-dir <review-report> --json",
            "ml-loop hf-eval shortlist --json",
            "ml-loop hf-eval plan --target-id smol-ai-worldcup-shift --output-dir .demo_runs/hf-eval/smol-ai-worldcup-plan --json",
            "ml-loop hf-eval smol-worldcup-verify --output-dir .demo_runs/hf-eval/smol-worldcup-p0 --json",
            "ml-loop hf-eval smol-worldcup-leakage-audit --output-dir .demo_runs/hf-eval/smol-worldcup-p3-leakage-audit --prompt-profile p3-routing-v1 --json",
            "ml-loop hf-eval smol-worldcup-leakage-audit --output-dir .demo_runs/hf-eval/smol-worldcup-p3-dev-v2-leakage-audit --prompt-profile p3-dev-v2 --json",
            "ml-loop hf-eval smol-worldcup-baseline --output-dir .demo_runs/hf-eval/smol-worldcup-p1 --json",
            "ml-loop hf-eval smol-worldcup-baseline --output-dir .demo_runs/hf-eval/smol-worldcup-canary-baseline --evaluation-split canary --json",
            "ml-loop hf-eval smol-worldcup-model-eval --output-dir .demo_runs/hf-eval/smol-worldcup-p2 --limit 5 --json",
            "ml-loop hf-eval smol-worldcup-rescore --prediction-path <prediction.jsonl> --output-dir <rescore-dir> --json",
            "ml-loop hf-eval smol-worldcup-rescore-proof-archive --rescore-dir <rescore-dir> --output-dir <proof-archive-dir> --json",
            "ml-loop hf-eval smol-worldcup-submission-probe --output-dir .demo_runs/hf-eval/smol-worldcup-submission-probe --json",
            "python3 scripts/memory_smoke.py --output-dir .demo_runs/memory-smoke --json",
            "python3 scripts/mcp_real_data_demo.py --max-experiments 1 --experiment-duration 30",
            "python3 scripts/mcp_reproduction_demo.py --max-experiments 1 --experiment-duration 30 --json",
        ],
    }


def plan_research_case_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Create a local ResearchCase planning object without side effects."""
    objective = arguments.get("objective")
    if not isinstance(objective, str) or not objective.strip():
        raise MCPToolError({"status": "failed", "error": "objective is required"})

    case_id = arguments.get("case_id")
    if case_id is None:
        case_id = _default_research_case_id(objective)
    if not isinstance(case_id, str) or not case_id.strip():
        raise MCPToolError({"status": "failed", "error": "case_id must be a string"})

    case = ResearchCase(
        case_id=case_id.strip(),
        objective=objective.strip(),
        claims=_research_claims_argument(arguments.get("claims")),
        forbidden_claims=_string_list_argument(arguments, "forbidden_claims"),
        official_scores_claimed=False,
    )
    return {
        "status": "planned",
        "case": serialize_research_case(case),
        "summary": summarize_research_case(case),
        "official_scores_claimed": False,
    }


def _default_research_case_id(objective: str) -> str:
    slug_chars = [char.lower() if char.isalnum() else "-" for char in objective.strip()]
    slug = "".join(slug_chars).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    if not slug:
        slug = "research"
    return f"case-{slug[:48].strip('-')}"


def _research_claims_argument(raw_claims: Any) -> list[ResearchClaim]:
    if raw_claims is None:
        return []
    if not isinstance(raw_claims, list):
        raise MCPToolError({"status": "failed", "error": "claims must be a list"})

    claims: list[ResearchClaim] = []
    for index, raw_claim in enumerate(raw_claims, start=1):
        if isinstance(raw_claim, str):
            claim_text = raw_claim.strip()
            if not claim_text:
                raise MCPToolError({"status": "failed", "error": "claim text cannot be empty"})
            claims.append(
                ResearchClaim(
                    claim_id=f"claim-{index:03d}",
                    text=claim_text,
                    status="needs_evidence",
                )
            )
            continue
        if not isinstance(raw_claim, dict):
            raise MCPToolError({
                "status": "failed",
                "error": "claims entries must be objects or strings",
            })
        claim_text = raw_claim.get("text")
        if not isinstance(claim_text, str) or not claim_text.strip():
            raise MCPToolError({"status": "failed", "error": "claims[].text is required"})
        claim_id = raw_claim.get("claim_id", f"claim-{index:03d}")
        if not isinstance(claim_id, str) or not claim_id.strip():
            raise MCPToolError({"status": "failed", "error": "claims[].claim_id must be a string"})
        status = _claim_status_argument(raw_claim.get("status", "needs_evidence"))
        claims.append(
            ResearchClaim(
                claim_id=claim_id.strip(),
                text=claim_text.strip(),
                status=status,
                evidence_refs=_evidence_refs_argument(raw_claim.get("evidence_refs")),
            )
        )
    return claims


def _evidence_refs_argument(raw_refs: Any) -> list[EvidenceRef]:
    if raw_refs is None:
        return []
    if not isinstance(raw_refs, list):
        raise MCPToolError({"status": "failed", "error": "claims[].evidence_refs must be a list"})

    refs: list[EvidenceRef] = []
    for raw_ref in raw_refs:
        if not isinstance(raw_ref, dict):
            raise MCPToolError({
                "status": "failed",
                "error": "claims[].evidence_refs entries must be objects",
            })
        source_id = raw_ref.get("source_id")
        artifact_path = raw_ref.get("artifact_path")
        if not isinstance(source_id, str) or not source_id.strip():
            raise MCPToolError({
                "status": "failed",
                "error": "claims[].evidence_refs[].source_id is required",
            })
        if not isinstance(artifact_path, str) or not artifact_path.strip():
            raise MCPToolError({
                "status": "failed",
                "error": "claims[].evidence_refs[].artifact_path is required",
            })
        quote = raw_ref.get("quote", "")
        strength = _evidence_strength_argument(raw_ref.get("strength", "weak"))
        refs.append(
            EvidenceRef(
                source_id=source_id.strip(),
                artifact_path=artifact_path.strip(),
                quote=quote if isinstance(quote, str) else "",
                strength=strength,
            )
        )
    return refs


def _claim_status_argument(raw_status: Any) -> str:
    if not isinstance(raw_status, str) or not raw_status.strip():
        raise MCPToolError({"status": "failed", "error": "claims[].status must be a string"})
    status = raw_status.strip()
    if status not in VALID_CLAIM_STATUSES:
        raise MCPToolError({
            "status": "failed",
            "error": "claims[].status must be one of: "
            + ", ".join(sorted(VALID_CLAIM_STATUSES)),
        })
    return status


def _evidence_strength_argument(raw_strength: Any) -> str:
    if not isinstance(raw_strength, str) or not raw_strength.strip():
        raise MCPToolError({
            "status": "failed",
            "error": "claims[].evidence_refs[].strength must be a string",
        })
    strength = raw_strength.strip()
    if strength not in VALID_EVIDENCE_STRENGTHS:
        raise MCPToolError({
            "status": "failed",
            "error": "claims[].evidence_refs[].strength must be one of: "
            + ", ".join(sorted(VALID_EVIDENCE_STRENGTHS)),
        })
    return strength


def _string_list_argument(arguments: dict[str, Any], key: str) -> list[str]:
    raw_value = arguments.get(key, [])
    if raw_value is None:
        return []
    if not isinstance(raw_value, list) or not all(
        isinstance(item, str) for item in raw_value
    ):
        raise MCPToolError({"status": "failed", "error": f"{key} must be a list of strings"})
    return list(raw_value)


def _optional_dict_argument(arguments: dict[str, Any], key: str) -> dict[str, Any] | None:
    raw_value = arguments.get(key)
    if raw_value is None:
        return None
    if not isinstance(raw_value, dict):
        raise MCPToolError({"status": "failed", "error": f"{key} must be an object"})
    return dict(raw_value)


def _sample_publication_manifest() -> dict[str, Any]:
    return {
        "benchmark_name": "mle_bench",
        "run_mode": "official_debug",
        "official_scores_claimed": False,
        "limitations": ["sample manifest only; no official proof-run artifacts attached"],
        "artifacts": {
            "command_lines": "missing-command-lines.txt",
            "resolved_config": "missing-config.json",
            "environment_manifest": "missing-environment.json",
            "raw_logs": "missing-run.log",
            "raw_reports": "missing-report.json",
            "limitations_note": "missing-limitations.md",
        },
    }


def _hf_external_eval_manifest() -> dict[str, Any]:
    payload = load_hf_eval_targets()
    targets = select_hf_eval_targets(payload, limit=5)
    return {
        "status": "listed",
        "official_scores_claimed": False,
        "target_count": len(targets),
        "selection_policy": payload.get("selection_policy", {}),
        "targets": targets,
        "claim_boundary": "candidate list only; no Hugging Face submission or score claim",
    }


def get_benchmark_harness_probe_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return read-only official benchmark harness readiness."""
    return build_official_harness_probe(
        mle_bench_repo=_optional_path_argument(arguments, "mle_bench_repo"),
        paperbench_repo=_optional_path_argument(arguments, "paperbench_repo"),
        paperbench_data_dir=_optional_path_argument(arguments, "paperbench_data_dir"),
    )


def plan_benchmark_proof_run_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return a safe proof-run plan from a read-only harness probe."""
    return build_public_proof_plan(get_benchmark_harness_probe_tool(arguments))


def write_benchmark_proof_setup_bundle_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Write read-only official/debug proof-run setup files."""
    proof_plan = plan_benchmark_proof_run_tool(arguments)
    bundle = build_official_proof_setup_bundle(proof_plan)
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    _assert_path_allowed(output_dir, "output_dir")
    return write_official_proof_setup_bundle(
        bundle,
        output_dir,
    )


def write_benchmark_proof_publication_bundle_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Write guarded publication files from proof-run artifacts."""
    manifest_path, artifact_root, output_dir = _benchmark_proof_writer_paths(arguments)
    artifact_manifest = _read_json_file(manifest_path)
    bundle = build_proof_publication_bundle(artifact_manifest, artifact_root)
    return write_proof_publication_bundle(bundle, output_dir)


def write_benchmark_proof_archive_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Write hashed archive files from complete proof-run artifacts."""
    manifest_path, artifact_root, output_dir = _benchmark_proof_writer_paths(arguments)
    artifact_manifest = _read_json_file(manifest_path)
    bundle = build_proof_archive_bundle(artifact_manifest, artifact_root)
    return write_proof_archive_bundle(bundle, artifact_root, output_dir)


def get_hf_external_eval_targets_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return HF external evaluation targets for client planning."""
    try:
        payload = load_hf_eval_targets(_optional_allowed_path(arguments, "shortlist_path"))
        limit = _positive_int(arguments.get("limit"), default=5) if "limit" in arguments else None
        targets = select_hf_eval_targets(
            payload,
            task_family=_optional_string(arguments, "task_family"),
            limit=limit,
        )
    except (OSError, ValueError) as exc:
        raise MCPToolError({
            "status": "failed",
            "error_type": "hf_external_eval_targets_failed",
            "error": str(exc),
            "official_scores_claimed": False,
        }) from exc
    return {
        "status": "listed",
        "official_scores_claimed": False,
        "target_count": len(targets),
        "selection_policy": payload.get("selection_policy", {}),
        "targets": targets,
        "executes_tool": False,
        "claim_boundary": "candidate list only; no Hugging Face submission or score claim",
    }


def write_hf_external_eval_plan_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Write a local HF external evaluation proof plan."""
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    _assert_path_allowed(output_dir, "output_dir")
    try:
        return write_hf_external_eval_plan(
            output_dir,
            shortlist_path=_optional_allowed_path(arguments, "shortlist_path"),
            target_id=_optional_string(arguments, "target_id"),
        )
    except (OSError, ValueError) as exc:
        raise MCPToolError({
            "status": "failed",
            "error_type": "hf_external_eval_plan_failed",
            "error": str(exc),
            "official_scores_claimed": False,
        }) from exc


def write_cp_bench_live_verification_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Write CP-Bench live verification artifacts."""
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    _assert_path_allowed(output_dir, "output_dir")
    include_raw = arguments.get("include_raw", False)
    if not isinstance(include_raw, bool):
        raise MCPToolError({
            "status": "failed",
            "error_type": "cp_bench_live_verification_failed",
            "error": "include_raw must be a boolean",
            "official_scores_claimed": False,
        })
    try:
        return write_cp_bench_live_verification(
            output_dir,
            timeout_seconds=_positive_int(arguments.get("timeout_seconds"), default=30),
            include_raw=include_raw,
        )
    except (OSError, ValueError) as exc:
        raise MCPToolError({
            "status": "failed",
            "error_type": "cp_bench_live_verification_failed",
            "error": str(exc),
            "official_scores_claimed": False,
        }) from exc


def run_cp_bench_local_baseline_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Write CP-Bench local baseline artifacts."""
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    _assert_path_allowed(output_dir, "output_dir")
    dry_run = arguments.get("dry_run", True)
    if not isinstance(dry_run, bool):
        raise MCPToolError({
            "status": "failed",
            "error_type": "cp_bench_local_baseline_failed",
            "error": "dry_run must be a boolean",
            "official_scores_claimed": False,
        })
    try:
        return write_cp_bench_local_baseline(
            output_dir,
            limit=_positive_int(arguments.get("limit"), default=1),
            framework=_optional_string(arguments, "framework") or "CPMpy",
            dataset_version=_optional_string(arguments, "dataset_version") or "verified",
            dry_run=dry_run,
            timeout_seconds=_positive_int(arguments.get("timeout_seconds"), default=60),
        )
    except (OSError, ValueError) as exc:
        raise MCPToolError({
            "status": "failed",
            "error_type": "cp_bench_local_baseline_failed",
            "error": str(exc),
            "official_scores_claimed": False,
        }) from exc


def run_cp_bench_proposal_round_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Write CP-Bench proposal-round and rollback artifacts."""
    baseline_report = Path(_required_string(arguments, "baseline_report")).expanduser().resolve()
    proposal = Path(_required_string(arguments, "proposal")).expanduser().resolve()
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    _assert_path_allowed(baseline_report, "baseline_report")
    _assert_path_allowed(proposal, "proposal")
    _assert_path_allowed(output_dir, "output_dir")
    try:
        return run_cp_bench_proposal_round(
            baseline_report,
            proposal,
            output_dir,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise MCPToolError({
            "status": "failed",
            "error_type": "cp_bench_proposal_round_failed",
            "error": str(exc),
            "official_scores_claimed": False,
        }) from exc


def run_cp_bench_candidate_round_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Run a guarded CP-Bench candidate submission round."""
    baseline_report = Path(_required_string(arguments, "baseline_report")).expanduser().resolve()
    submission = Path(_required_string(arguments, "submission")).expanduser().resolve()
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    proposal = _optional_string(arguments, "proposal")
    proposal_path = Path(proposal).expanduser().resolve() if proposal else None
    _assert_path_allowed(baseline_report, "baseline_report")
    _assert_path_allowed(submission, "submission")
    _assert_path_allowed(output_dir, "output_dir")
    if proposal_path is not None:
        _assert_path_allowed(proposal_path, "proposal")
    try:
        return run_cp_bench_candidate_round(
            baseline_report,
            submission,
            output_dir,
            proposal_path=proposal_path,
            framework=_optional_string(arguments, "framework") or "CPMpy",
            dataset_version=_optional_string(arguments, "dataset_version") or "verified",
            timeout_seconds=_positive_int(arguments.get("timeout_seconds"), default=60),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise MCPToolError({
            "status": "failed",
            "error_type": "cp_bench_candidate_round_failed",
            "error": str(exc),
            "official_scores_claimed": False,
        }) from exc


def build_cp_bench_proposal_context_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Write a CP-Bench proposal prompt context from local evaluator outcomes."""
    current_report = Path(_required_string(arguments, "current_report")).expanduser().resolve()
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    _assert_path_allowed(current_report, "current_report")
    _assert_path_allowed(output_dir, "output_dir")
    try:
        return write_cp_bench_proposal_context(
            current_report,
            output_dir,
            max_proposals=_positive_int(arguments.get("max_proposals"), default=3),
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise MCPToolError({
            "status": "failed",
            "error_type": "cp_bench_proposal_context_failed",
            "error": str(exc),
            "official_scores_claimed": False,
        }) from exc


def write_cp_bench_client_candidate_submission_tool(
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Write a non-reference-replay CP-Bench client candidate bundle."""
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    _assert_path_allowed(output_dir, "output_dir")
    try:
        return write_cp_bench_client_candidate_submission(
            output_dir,
            limit=_positive_int(arguments.get("limit"), default=10),
            dataset_version=_optional_string(arguments, "dataset_version") or "verified",
            strategy=_optional_string(arguments, "strategy") or "handcrafted-small-cpmpy-v1",
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise MCPToolError({
            "status": "failed",
            "error_type": "cp_bench_client_candidate_failed",
            "error": str(exc),
            "official_scores_claimed": False,
        }) from exc


def write_cp_bench_submission_gate_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Write CP-Bench manual submission gate artifacts."""
    submission = Path(_required_string(arguments, "submission")).expanduser().resolve()
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    source_report = _optional_string(arguments, "source_report")
    source_report_path = Path(source_report).expanduser().resolve() if source_report else None
    _assert_path_allowed(submission, "submission")
    _assert_path_allowed(output_dir, "output_dir")
    if source_report_path is not None:
        _assert_path_allowed(source_report_path, "source_report")
    try:
        return write_cp_bench_submission_gate(
            submission,
            output_dir,
            source_report_path=source_report_path,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise MCPToolError({
            "status": "failed",
            "error_type": "cp_bench_submission_gate_failed",
            "error": str(exc),
            "official_scores_claimed": False,
        }) from exc


def write_smol_worldcup_live_verification_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Write Smol AI WorldCup live verification artifacts."""
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    _assert_path_allowed(output_dir, "output_dir")
    include_raw = arguments.get("include_raw", False)
    if not isinstance(include_raw, bool):
        raise MCPToolError({
            "status": "failed",
            "error_type": "smol_worldcup_live_verification_failed",
            "error": "include_raw must be a boolean",
            "official_scores_claimed": False,
        })
    try:
        return write_smol_worldcup_live_verification(
            output_dir,
            timeout_seconds=_positive_int(arguments.get("timeout_seconds"), default=30),
            include_raw=include_raw,
        )
    except (OSError, ValueError) as exc:
        raise MCPToolError({
            "status": "failed",
            "error_type": "smol_worldcup_live_verification_failed",
            "error": str(exc),
            "official_scores_claimed": False,
        }) from exc


def write_smol_worldcup_prompt_leakage_audit_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Write a prompt leakage audit for Smol AI WorldCup eval prompts."""
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    _assert_path_allowed(output_dir, "output_dir")
    try:
        return write_smol_worldcup_prompt_leakage_audit(
            output_dir,
            timeout_seconds=_positive_int(arguments.get("timeout_seconds"), default=30),
            page_size=_positive_int(arguments.get("page_size"), default=100),
            limit=(
                _positive_int(arguments.get("limit"), default=125)
                if arguments.get("limit") is not None
                else None
            ),
            prompt_profile=_optional_string(arguments, "prompt_profile") or "default",
            evaluation_split=_optional_string(arguments, "evaluation_split") or "all",
            canary_fraction=_optional_float(arguments, "canary_fraction", default=0.2),
        )
    except (OSError, ValueError) as exc:
        raise MCPToolError({
            "status": "failed",
            "error_type": "smol_worldcup_prompt_leakage_audit_failed",
            "error": str(exc),
            "official_scores_claimed": False,
        }) from exc


def run_smol_worldcup_local_baseline_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Run the local-compatible Smol AI WorldCup baseline."""
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    _assert_path_allowed(output_dir, "output_dir")
    try:
        return write_smol_worldcup_baseline(
            output_dir,
            timeout_seconds=_positive_int(arguments.get("timeout_seconds"), default=30),
            page_size=_positive_int(arguments.get("page_size"), default=100),
            strategy=_optional_string(arguments, "strategy") or "local-abstain-baseline",
            limit=(
                _positive_int(arguments.get("limit"), default=125)
                if arguments.get("limit") is not None
                else None
            ),
            evaluation_split=_optional_string(arguments, "evaluation_split") or "all",
            canary_fraction=_optional_float(arguments, "canary_fraction", default=0.2),
            model_size_billion=_optional_float(
                arguments,
                "model_size_billion",
                default=0.001,
            ),
            estimated_ram_gb=_optional_float(arguments, "estimated_ram_gb", default=0.01),
        )
    except (OSError, ValueError) as exc:
        raise MCPToolError({
            "status": "failed",
            "error_type": "smol_worldcup_local_baseline_failed",
            "error": str(exc),
            "official_scores_claimed": False,
        }) from exc


def run_smol_worldcup_model_eval_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Run Smol AI WorldCup local model eval through an OpenAI-compatible endpoint."""
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    _assert_path_allowed(output_dir, "output_dir")
    model_provider = _optional_string(arguments, "model_provider") or "openai-compatible"
    base_url = _optional_string(arguments, "base_url") or "http://127.0.0.1:1234/v1"
    if model_provider == "deepseek" and base_url == "http://127.0.0.1:1234/v1":
        base_url = "https://api.deepseek.com"
    try:
        return write_smol_worldcup_model_eval(
            output_dir,
            timeout_seconds=_positive_int(arguments.get("timeout_seconds"), default=120),
            page_size=_positive_int(arguments.get("page_size"), default=100),
            limit=(
                _positive_int(arguments.get("limit"), default=125)
                if arguments.get("limit") is not None
                else None
            ),
            model=_optional_string(arguments, "model") or "openai/gpt-oss-20b",
            base_url=base_url,
            model_provider=model_provider,
            api_key_env=_optional_string(arguments, "api_key_env"),
            thinking_mode=_optional_string(arguments, "thinking_mode") or "default",
            reasoning_effort=_optional_string(arguments, "reasoning_effort"),
            temperature=_nonnegative_float(arguments, "temperature", default=0.0),
            max_tokens=_positive_int(arguments.get("max_tokens"), default=512),
            round_id=_optional_string(arguments, "round_id") or "round-001",
            prompt_profile=_optional_string(arguments, "prompt_profile") or "default",
            evaluation_split=_optional_string(arguments, "evaluation_split") or "all",
            canary_fraction=_optional_float(arguments, "canary_fraction", default=0.2),
            judge_mode=_optional_string(arguments, "judge_mode") or "heuristic",
            judge_model=_optional_string(arguments, "judge_model"),
            judge_base_url=_optional_string(arguments, "judge_base_url"),
            model_size_billion=_optional_float(
                arguments,
                "model_size_billion",
                default=20.0,
            ),
            estimated_ram_gb=_optional_float(arguments, "estimated_ram_gb", default=32.0),
        )
    except (OSError, ValueError) as exc:
        raise MCPToolError({
            "status": "failed",
            "error_type": "smol_worldcup_model_eval_failed",
            "error": str(exc),
            "official_scores_claimed": False,
        }) from exc


def run_smol_worldcup_proposal_round_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Validate and execute one guarded Smol WorldCup proposal round."""
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    _assert_path_allowed(output_dir, "output_dir")
    proposal = _proposal_payload(arguments, "proposal", "proposal_file")
    model_provider = _optional_string(arguments, "model_provider") or "openai-compatible"
    base_url = _optional_string(arguments, "base_url") or "http://127.0.0.1:1234/v1"
    if model_provider == "deepseek" and base_url == "http://127.0.0.1:1234/v1":
        base_url = "https://api.deepseek.com"
    try:
        return run_smol_worldcup_proposal_round(
            proposal=proposal,
            output_dir=output_dir,
            current_report=_optional_allowed_path(arguments, "current_report"),
            baseline_report=_optional_allowed_path(arguments, "baseline_report"),
            timeout_seconds=_positive_int(arguments.get("timeout_seconds"), default=120),
            page_size=_positive_int(arguments.get("page_size"), default=100),
            limit=(
                _positive_int(arguments.get("limit"), default=125)
                if arguments.get("limit") is not None
                else None
            ),
            model=_optional_string(arguments, "model") or "openai/gpt-oss-20b",
            base_url=base_url,
            model_provider=model_provider,
            api_key_env=_optional_string(arguments, "api_key_env"),
            thinking_mode=_optional_string(arguments, "thinking_mode") or "default",
            reasoning_effort=_optional_string(arguments, "reasoning_effort"),
            temperature=_nonnegative_float(arguments, "temperature", default=0.0),
            max_tokens=_positive_int(arguments.get("max_tokens"), default=512),
            round_id=_optional_string(arguments, "round_id"),
            prompt_profile=_optional_string(arguments, "prompt_profile"),
            evaluation_split=_optional_string(arguments, "evaluation_split") or "dev",
            canary_fraction=_optional_float(arguments, "canary_fraction", default=0.2),
            judge_mode=_optional_string(arguments, "judge_mode") or "heuristic",
            judge_model=_optional_string(arguments, "judge_model"),
            judge_base_url=_optional_string(arguments, "judge_base_url"),
            model_size_billion=_optional_float(
                arguments,
                "model_size_billion",
                default=20.0,
            ),
            estimated_ram_gb=_optional_float(arguments, "estimated_ram_gb", default=32.0),
            allowed_change_surfaces=_string_list_argument(
                arguments,
                "allowed_change_surfaces",
            ) or None,
        )
    except (OSError, ValueError) as exc:
        raise MCPToolError({
            "status": "failed",
            "error_type": "smol_worldcup_proposal_round_failed",
            "error": str(exc),
            "official_scores_claimed": False,
        }) from exc


def run_smol_worldcup_rescore_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Rescore existing Smol AI WorldCup predictions with scorer-v2."""
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    prediction_path = (
        Path(_required_string(arguments, "prediction_path")).expanduser().resolve()
    )
    source_report = _optional_path(arguments, "source_report")
    source_rows = _optional_path(arguments, "source_rows")
    _assert_path_allowed(output_dir, "output_dir")
    _assert_path_allowed(prediction_path, "prediction_path")
    if source_report is not None:
        _assert_path_allowed(source_report, "source_report")
    if source_rows is not None:
        _assert_path_allowed(source_rows, "source_rows")
    try:
        return write_smol_worldcup_rescore(
            output_dir,
            prediction_path=prediction_path,
            source_rows_path=source_rows,
            source_report=source_report,
            source_run_id=_optional_string(arguments, "source_run_id"),
            timeout_seconds=_positive_int(arguments.get("timeout_seconds"), default=30),
            page_size=_positive_int(arguments.get("page_size"), default=100),
            preserve_llm_judge_scores=_optional_bool(
                arguments,
                "preserve_llm_judge_scores",
                default=True,
            ),
            model_size_billion=_optional_float(
                arguments,
                "model_size_billion",
                default=20.0,
            ),
            estimated_ram_gb=_optional_float(arguments, "estimated_ram_gb", default=32.0),
        )
    except (OSError, ValueError) as exc:
        raise MCPToolError({
            "status": "failed",
            "error_type": "smol_worldcup_rescore_failed",
            "error": str(exc),
            "official_scores_claimed": False,
        }) from exc


def write_smol_worldcup_rescore_proof_archive_tool(
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Package formal scorer-v2 rescore artifacts into a proof archive."""
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    rescore_dir = Path(_required_string(arguments, "rescore_dir")).expanduser().resolve()
    source_report = _optional_path(arguments, "source_report")
    source_prediction_path = _optional_path(arguments, "source_prediction_path")
    _assert_path_allowed(output_dir, "output_dir")
    _assert_path_allowed(rescore_dir, "rescore_dir")
    if source_report is not None:
        _assert_path_allowed(source_report, "source_report")
    if source_prediction_path is not None:
        _assert_path_allowed(source_prediction_path, "source_prediction_path")
    command_lines_raw = arguments.get("command_lines")
    command_lines = None
    if command_lines_raw is not None:
        if (
            not isinstance(command_lines_raw, list)
            or not all(isinstance(item, str) for item in command_lines_raw)
        ):
            raise MCPToolError({
                "status": "failed",
                "error_type": "smol_worldcup_rescore_proof_archive_failed",
                "error": "command_lines must be an array of strings",
                "official_scores_claimed": False,
            })
        command_lines = list(command_lines_raw)
    try:
        return write_smol_worldcup_rescore_proof_archive(
            rescore_dir=rescore_dir,
            output_dir=output_dir,
            source_report=source_report,
            source_prediction_path=source_prediction_path,
            source_run_id=_optional_string(arguments, "source_run_id"),
            command_lines=command_lines,
        )
    except (OSError, ValueError) as exc:
        raise MCPToolError({
            "status": "failed",
            "error_type": "smol_worldcup_rescore_proof_archive_failed",
            "error": str(exc),
            "official_scores_claimed": False,
        }) from exc


def write_smol_worldcup_submission_probe_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Probe the public HF Space submission path without submitting."""
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    _assert_path_allowed(output_dir, "output_dir")
    include_raw = _optional_bool(arguments, "include_raw", default=True)
    try:
        return write_smol_worldcup_submission_probe(
            output_dir,
            timeout_seconds=_positive_int(arguments.get("timeout_seconds"), default=30),
            model_id=_optional_string(arguments, "model") or "openai/gpt-oss-20b",
            include_raw=include_raw,
        )
    except (OSError, ValueError) as exc:
        raise MCPToolError({
            "status": "failed",
            "error_type": "smol_worldcup_submission_probe_failed",
            "error": str(exc),
            "official_scores_claimed": False,
        }) from exc


def write_official_mle_bench_patch_round_proof_bundle_tool(
    arguments: dict[str, Any],
) -> dict[str, Any]:
    """Write proof artifacts and archive for one official MLE-bench patch round."""
    patch_round_report = Path(
        _required_string(arguments, "patch_round_report")
    ).expanduser().resolve()
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    _assert_path_allowed(patch_round_report, "patch_round_report")
    _assert_path_allowed(output_dir, "output_dir")
    return write_official_mle_patch_round_proof_bundle(
        patch_round_report=patch_round_report,
        output_dir=output_dir,
    )


def run_fasttext_patch_round_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Run one guarded fastText reproduction patch round."""
    target_spec = Path(_required_string(arguments, "target_spec")).expanduser().resolve()
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    train_csv = Path(_required_string(arguments, "ag_news_train_csv")).expanduser().resolve()
    test_csv = Path(_required_string(arguments, "ag_news_test_csv")).expanduser().resolve()
    fasttext_binary = Path(_required_string(arguments, "fasttext_binary")).expanduser().resolve()
    baseline_report = Path(_required_string(arguments, "baseline_report")).expanduser().resolve()
    for field, path in (
        ("target_spec", target_spec),
        ("output_dir", output_dir),
        ("ag_news_train_csv", train_csv),
        ("ag_news_test_csv", test_csv),
        ("fasttext_binary", fasttext_binary),
        ("baseline_report", baseline_report),
    ):
        _assert_path_allowed(path, field)
    proposal = arguments.get("proposal")
    if not isinstance(proposal, dict):
        raise MCPToolError({
            "status": "failed",
            "error_type": "invalid_fasttext_patch_proposal",
            "error": "proposal must be an object",
        })
    try:
        return run_fasttext_patch_round(
            FullReproductionRunConfig(
                target_spec_path=target_spec,
                output_dir=output_dir,
                max_train_seconds=int(arguments.get("max_train_seconds", 300)),
            ),
            train_csv=train_csv,
            test_csv=test_csv,
            fasttext_binary=fasttext_binary,
            baseline_report=baseline_report,
            proposal=proposal,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise MCPToolError({
            "status": "failed",
            "error_type": "fasttext_patch_round_failed",
            "error": str(exc),
            "official_scores_claimed": False,
        }) from exc


def write_fasttext_patch_round_proof_bundle_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Package a completed fastText patch round into a reviewed proof bundle."""
    patch_round_report = (
        Path(_required_string(arguments, "patch_round_report")).expanduser().resolve()
    )
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    _assert_path_allowed(patch_round_report, "patch_round_report")
    _assert_path_allowed(output_dir, "output_dir")
    reviewer = str(arguments.get("reviewer", "local-review"))
    review_status = str(arguments.get("review_status", "approved_with_limitations"))
    try:
        return write_fasttext_patch_round_proof_bundle(
            patch_round_report=patch_round_report,
            output_dir=output_dir,
            reviewer=reviewer,
            review_status=review_status,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise MCPToolError({
            "status": "failed",
            "error_type": "fasttext_patch_proof_bundle_failed",
            "error": str(exc),
            "official_scores_claimed": False,
        }) from exc


def run_fasttext_multi_proposal_loop_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Run guarded fastText proposal rounds with rollback evidence."""
    target_spec = Path(_required_string(arguments, "target_spec")).expanduser().resolve()
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    train_csv = Path(_required_string(arguments, "ag_news_train_csv")).expanduser().resolve()
    test_csv = Path(_required_string(arguments, "ag_news_test_csv")).expanduser().resolve()
    fasttext_binary = Path(_required_string(arguments, "fasttext_binary")).expanduser().resolve()
    baseline_report = Path(_required_string(arguments, "baseline_report")).expanduser().resolve()
    for field, path in (
        ("target_spec", target_spec),
        ("output_dir", output_dir),
        ("ag_news_train_csv", train_csv),
        ("ag_news_test_csv", test_csv),
        ("fasttext_binary", fasttext_binary),
        ("baseline_report", baseline_report),
    ):
        _assert_path_allowed(path, field)
    proposals = arguments.get("proposals")
    if not isinstance(proposals, list) or not proposals:
        raise MCPToolError({
            "status": "failed",
            "error_type": "invalid_fasttext_proposals",
            "error": "proposals must be a non-empty list",
            "official_scores_claimed": False,
        })
    if not all(isinstance(proposal, dict) for proposal in proposals):
        raise MCPToolError({
            "status": "failed",
            "error_type": "invalid_fasttext_proposals",
            "error": "proposals entries must be objects",
            "official_scores_claimed": False,
        })
    try:
        return run_fasttext_multi_proposal_loop(
            FullReproductionRunConfig(
                target_spec_path=target_spec,
                output_dir=output_dir,
                max_train_seconds=int(arguments.get("max_train_seconds", 300)),
            ),
            train_csv=train_csv,
            test_csv=test_csv,
            fasttext_binary=fasttext_binary,
            baseline_report=baseline_report,
            proposals=proposals,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise MCPToolError({
            "status": "failed",
            "error_type": "fasttext_multi_proposal_loop_failed",
            "error": str(exc),
            "official_scores_claimed": False,
        }) from exc


def write_fasttext_release_proof_bundle_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Package reviewed fastText proof artifacts into a downloadable bundle."""
    proof_manifest = (
        Path(_required_string(arguments, "proof_manifest")).expanduser().resolve()
    )
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    _assert_path_allowed(proof_manifest, "proof_manifest")
    _assert_path_allowed(output_dir, "output_dir")
    multi_round_report_arg = arguments.get("multi_round_report")
    multi_round_report = None
    if isinstance(multi_round_report_arg, str) and multi_round_report_arg:
        multi_round_report = Path(multi_round_report_arg).expanduser().resolve()
        _assert_path_allowed(multi_round_report, "multi_round_report")
    reviewer = str(arguments.get("reviewer", "local-review"))
    try:
        return write_fasttext_release_proof_bundle(
            proof_manifest=proof_manifest,
            output_dir=output_dir,
            multi_round_report=multi_round_report,
            reviewer=reviewer,
        )
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        raise MCPToolError({
            "status": "failed",
            "error_type": "fasttext_release_proof_bundle_failed",
            "error": str(exc),
            "official_scores_claimed": False,
        }) from exc


def prepare_paperbench_codex_review_bundle_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Prepare a keyless PaperBench artifact packet for Codex review."""
    run_dir = Path(_required_string(arguments, "run_dir")).expanduser().resolve()
    paper_dir = Path(_required_string(arguments, "paper_dir")).expanduser().resolve()
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    for field, path in (
        ("run_dir", run_dir),
        ("paper_dir", paper_dir),
        ("output_dir", output_dir),
    ):
        _assert_path_allowed(path, field)
    return write_paperbench_codex_review_bundle(
        run_dir=run_dir,
        paper_dir=paper_dir,
        output_dir=output_dir,
    )


def write_paperbench_codex_review_report_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Write a non-official Codex-assisted PaperBench review report."""
    bundle_path = Path(_required_string(arguments, "bundle")).expanduser().resolve()
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    _assert_path_allowed(bundle_path, "bundle")
    _assert_path_allowed(output_dir, "output_dir")
    review_payload = arguments.get("review")
    if not isinstance(review_payload, dict):
        raise MCPToolError({
            "status": "failed",
            "error": "review must be an object",
            "field": "review",
        })
    return write_paperbench_codex_review_report(
        bundle_path=bundle_path,
        review_payload=review_payload,
        output_dir=output_dir,
    )


def record_research_memory_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Record provenance-backed research memory without running experiments."""
    store = ResearchMemoryStore(_memory_store_path(arguments))
    try:
        cards = _memory_cards_from_record_arguments(arguments)
    except (FileNotFoundError, ValueError, TypeError) as exc:
        raise MCPToolError({
            "status": "failed",
            "error_type": "invalid_research_memory_record",
            "error": str(exc),
            "official_scores_claimed": False,
            "executes_tool": False,
        }) from exc

    for card in cards:
        _assert_memory_card_artifacts_allowed(card)
        store.append(card)

    adapter_results = None
    if arguments.get("sync_adapters") is True:
        try:
            adapter_results = sync_cards_to_adapters(
                cards,
                adapter_names=_memory_adapter_names(arguments),
            )
        except ValueError as exc:
            raise MCPToolError({
                "status": "failed",
                "error_type": "invalid_memory_adapter",
                "error": str(exc),
            }) from exc

    payload = {
        "status": "recorded",
        "store": str(store.path),
        "card_count": len(cards),
        "card_ids": [card.card_id for card in cards],
        "executes_tool": False,
        "official_scores_claimed": False,
        "claim_boundary": "memory recording only; not new proof",
    }
    if adapter_results is not None:
        payload["adapter_results"] = adapter_results
    return payload


def retrieve_research_memory_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Retrieve matching research memory with scores and provenance."""
    store = ResearchMemoryStore(_memory_store_path(arguments))
    results = store.search(
        query=_optional_string(arguments, "query"),
        paper_id=_optional_string(arguments, "paper_id"),
        dataset=_optional_string(arguments, "dataset"),
        metric_name=_optional_string(arguments, "metric_name"),
        patch_type=_optional_string(arguments, "patch_type"),
        failure_category=_optional_string(arguments, "failure_category"),
        limit=_positive_int(arguments.get("limit"), default=10),
    )
    payload = {
        "status": "completed",
        "store": str(store.path),
        "match_count": len(results),
        "matches": [result.to_dict() for result in results],
        "executes_tool": False,
        "official_scores_claimed": False,
        "claim_boundary": "retrieved memory only; client must audit before reuse",
    }
    if arguments.get("include_adapters") is True:
        try:
            payload["adapter_results"] = search_memory_adapters(
                query=_optional_string(arguments, "query") or "",
                limit=_positive_int(arguments.get("limit"), default=10),
                adapter_names=_memory_adapter_names(arguments),
            )
        except ValueError as exc:
            raise MCPToolError({
                "status": "failed",
                "error_type": "invalid_memory_adapter",
                "error": str(exc),
            }) from exc
    return payload


def suggest_from_memory_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return advisory suggestions from memory without executing them."""
    store = ResearchMemoryStore(_memory_store_path(arguments))
    suggestions = store.suggest(
        query=_required_string(arguments, "query"),
        paper_id=_optional_string(arguments, "paper_id"),
        dataset=_optional_string(arguments, "dataset"),
        limit=_positive_int(arguments.get("limit"), default=5),
    )
    return {
        "status": "completed",
        "store": str(store.path),
        "suggestion_count": len(suggestions),
        "suggestions": [suggestion.to_dict() for suggestion in suggestions],
        "executes_tool": False,
        "official_scores_claimed": False,
        "claim_boundary": "suggestions are advisory; no MCP tool was executed",
    }


def promote_memory_card_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Append a promoted copy of a memory card while preserving provenance."""
    store = ResearchMemoryStore(_memory_store_path(arguments))
    card_id = _required_string(arguments, "card_id")
    promoted_card_id = str(arguments.get("promoted_card_id") or f"{card_id}-promoted")
    source_card = _find_memory_card(store, card_id)
    promoted = replace(
        source_card,
        card_id=promoted_card_id,
        promoted=True,
        tags=sorted(set(source_card.tags + ["promoted"])),
        created_at=time.time(),
    )
    store.append(promoted)
    return {
        "status": "promoted",
        "store": str(store.path),
        "source_card_id": card_id,
        "promoted_card_id": promoted.card_id,
        "card": promoted.to_dict(),
        "executes_tool": False,
        "official_scores_claimed": False,
    }


def audit_memory_trace_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Return auditable provenance for selected memory cards."""
    store = ResearchMemoryStore(_memory_store_path(arguments))
    card_ids = arguments.get("card_ids")
    if not isinstance(card_ids, list) or not all(
        isinstance(item, str) and item for item in card_ids
    ):
        raise MCPToolError({
            "status": "failed",
            "error": "card_ids must be a non-empty list of strings",
        })
    trace = store.audit_trace(card_ids)
    found_ids = {card.card_id for card in trace.cards}
    return {
        "status": "completed",
        "store": str(store.path),
        "trace": trace.to_dict(),
        "missing_card_ids": [card_id for card_id in card_ids if card_id not in found_ids],
        "executes_tool": False,
        "official_scores_claimed": False,
        "claim_boundary": "trace audit only; not proof of reproduction quality",
    }


def build_proposal_context_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Write a non-executing context bundle for client proposal generation."""
    objective = _required_string(arguments, "objective").strip()
    if not objective:
        raise MCPToolError({"status": "failed", "error": "objective is required"})
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    _assert_path_allowed(output_dir, "output_dir")
    return build_proposal_context(
        objective=objective,
        output_dir=output_dir,
        baseline_report=_optional_allowed_path(arguments, "baseline_report"),
        current_report=_optional_allowed_path(arguments, "current_report"),
        dev_report=_optional_allowed_path(arguments, "dev_report"),
        canary_report=_optional_allowed_path(arguments, "canary_report"),
        category_deltas=_optional_allowed_path(arguments, "category_deltas"),
        failure_samples=_optional_allowed_path(arguments, "failure_samples"),
        rollback_summary=_optional_allowed_path(arguments, "rollback_summary"),
        previous_proposals=_optional_allowed_path(arguments, "previous_proposals"),
        memory_cards=_optional_allowed_path(arguments, "memory_cards"),
        memory_store=_optional_allowed_path(arguments, "memory_store"),
        memory_query=_optional_dict_argument(arguments, "memory_query"),
        memory_limit=_positive_int(arguments.get("memory_limit"), default=5),
        resource_constraints=_optional_dict_argument(arguments, "resource_constraints"),
        allowed_change_surfaces=_string_list_argument(
            arguments,
            "allowed_change_surfaces",
        ) or None,
        max_proposals=_positive_int(arguments.get("max_proposals"), default=3),
        overwrite=bool(arguments.get("overwrite", False)),
    )


def validate_client_proposal_contract_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Validate a client-generated proposal before execution."""
    proposal = _proposal_payload(arguments, "proposal", "proposal_file")
    return validate_client_proposal(
        proposal,
        allowed_change_surfaces=_string_list_argument(
            arguments,
            "allowed_change_surfaces",
        ) or None,
    )


def write_proposal_reflection_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Write reflection artifacts for a completed proposal evaluation."""
    proposal = _proposal_payload(arguments, "proposal", "proposal_file")
    evaluation = _proposal_payload(arguments, "evaluation", "evaluation_file")
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    _assert_path_allowed(output_dir, "output_dir")
    payload = build_proposal_reflection(
        proposal=proposal,
        evaluation=evaluation,
        output_dir=output_dir,
        overwrite=bool(arguments.get("overwrite", False)),
    )
    memory_store = _optional_allowed_path(arguments, "memory_store")
    if memory_store is not None:
        card = proposal_reflection_to_memory_card(payload)
        _assert_memory_card_artifacts_allowed(card)
        store = ResearchMemoryStore(memory_store)
        store.append(card)
        memory_sync: dict[str, Any] = {
            "status": "synced",
            "store": str(store.path),
            "card_id": card.card_id,
            "executes_tool": False,
            "official_scores_claimed": False,
        }
        if arguments.get("sync_adapters") is True:
            memory_sync["adapter_results"] = sync_cards_to_adapters(
                [card],
                adapter_names=_string_list_argument(arguments, "adapter_names") or None,
            )
        payload["memory_sync"] = memory_sync
    elif arguments.get("sync_adapters") is True:
        raise MCPToolError({
            "status": "failed",
            "error": "sync_adapters requires memory_store",
            "official_scores_claimed": False,
        })
    return payload


def summarize_proposal_search_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Summarize proposal portfolio state without executing anything."""
    items = arguments.get("items")
    if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
        raise MCPToolError({
            "status": "failed",
            "error": "items must be a list of objects",
            "official_scores_claimed": False,
        })
    return build_proposal_search(
        items,
        branch_budget=_optional_positive_int(arguments.get("branch_budget")),
        diversity_constraint=_optional_dict_argument(arguments, "diversity_constraint"),
    )


def _proposal_payload(
    arguments: dict[str, Any],
    object_key: str,
    file_key: str,
) -> dict[str, Any]:
    inline = arguments.get(object_key)
    if inline is not None:
        if not isinstance(inline, dict):
            raise MCPToolError({"status": "failed", "error": f"{object_key} must be an object"})
        return inline
    path = _optional_allowed_path(arguments, file_key)
    if path is None:
        raise MCPToolError({
            "status": "failed",
            "error": f"{object_key} or {file_key} is required",
        })
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise MCPToolError({"status": "failed", "error": f"{file_key} must contain an object"})
    return payload


def _memory_cards_from_record_arguments(arguments: dict[str, Any]) -> list[ResearchMemoryCard]:
    card_payload = arguments.get("card")
    if card_payload is not None:
        if not isinstance(card_payload, dict):
            raise ValueError("card must be an object")
        return [ResearchMemoryCard.from_dict(card_payload)]

    required_paths = ("release_manifest", "multi_round_report", "review_checklist")
    if not all(arguments.get(key) for key in required_paths):
        raise ValueError(
            "record_research_memory requires either card or fastText release artifact paths"
        )
    return extract_fasttext_release_memory_cards(
        release_manifest=_memory_required_path(arguments, "release_manifest"),
        multi_round_report=_memory_required_path(arguments, "multi_round_report"),
        review_checklist=_memory_required_path(arguments, "review_checklist"),
    )


def _memory_adapter_names(arguments: dict[str, Any]) -> list[str] | None:
    names = _string_list_argument(arguments, "adapters")
    return names or None


def _memory_store_path(arguments: dict[str, Any]) -> Path:
    path = Path(_required_string(arguments, "store")).expanduser().resolve()
    _assert_path_allowed(path, "store")
    return path


def _memory_required_path(arguments: dict[str, Any], key: str) -> Path:
    path = Path(_required_string(arguments, key)).expanduser().resolve()
    _assert_path_allowed(path, key)
    return path


def _assert_memory_card_artifacts_allowed(card: ResearchMemoryCard) -> None:
    for artifact in card.artifact_refs:
        _assert_path_allowed(Path(artifact.path).expanduser().resolve(), "artifact_refs")


def _find_memory_card(store: ResearchMemoryStore, card_id: str) -> ResearchMemoryCard:
    for card in reversed(store.list_cards()):
        if card.card_id == card_id:
            return card
    raise MCPToolError({
        "status": "failed",
        "error": f"memory card not found: {card_id}",
        "card_id": card_id,
    })


def _optional_string(arguments: dict[str, Any], key: str) -> str | None:
    value = arguments.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise MCPToolError({"status": "failed", "error": f"{key} must be a string"})
    return value


def _optional_path(arguments: dict[str, Any], key: str) -> Path | None:
    value = _optional_string(arguments, key)
    return Path(value).expanduser().resolve() if value else None


def _optional_bool(arguments: dict[str, Any], key: str, *, default: bool) -> bool:
    value = arguments.get(key)
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    raise MCPToolError({"status": "failed", "error": f"{key} must be a boolean"})


def _positive_int(value: Any, *, default: int) -> int:
    if value is None:
        return default
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise MCPToolError({"status": "failed", "error": "limit must be an integer"}) from exc
    if parsed < 1:
        raise MCPToolError({"status": "failed", "error": "limit must be positive"})
    return parsed


def _optional_positive_int(value: Any) -> int | None:
    if value is None:
        return None
    return _positive_int(value, default=1)


def _optional_float(arguments: dict[str, Any], key: str, *, default: float) -> float:
    value = arguments.get(key)
    if value is None:
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise MCPToolError({"status": "failed", "error": f"{key} must be a number"}) from exc
    if parsed <= 0:
        raise MCPToolError({"status": "failed", "error": f"{key} must be positive"})
    return parsed


def _nonnegative_float(arguments: dict[str, Any], key: str, *, default: float) -> float:
    value = arguments.get(key)
    if value is None:
        return default
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise MCPToolError({"status": "failed", "error": f"{key} must be a number"}) from exc
    if parsed < 0:
        raise MCPToolError({"status": "failed", "error": f"{key} must be non-negative"})
    return parsed


def prepare_official_mle_bench_workspace_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Create a bounded MLE-bench workspace for client-planned solving."""
    started_at = _utc_now()
    start_time = time.monotonic()
    runtime_root = _safe_runtime_root(arguments)
    prepared_competition_dir = Path(
        _required_string(arguments, "prepared_competition_dir")
    ).expanduser().resolve()
    _assert_path_allowed(prepared_competition_dir, "prepared_competition_dir")
    payload = materialize_official_mle_agent_workspace(
        competition_id=_required_string(arguments, "competition_id"),
        prepared_competition_dir=prepared_competition_dir,
        runtime_root=runtime_root,
        workspace_name=arguments.get("workspace_name"),
    )
    payload["execution_metadata"] = _execution_metadata(
        arguments,
        started_at=started_at,
        start_time=start_time,
        timeout_seconds=None,
        task_id=f"mle-bench-{payload['competition_id']}",
        workspace=payload["workspace"],
    )
    return payload


def grade_official_mle_bench_submission_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Grade a local MLE-bench submission with official grade-sample."""
    started_at = _utc_now()
    start_time = time.monotonic()
    submission = Path(_required_string(arguments, "submission")).expanduser().resolve()
    data_dir = Path(_required_string(arguments, "data_dir")).expanduser().resolve()
    mlebench = Path(_required_string(arguments, "mlebench")).expanduser().resolve()
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    for field, path in (
        ("submission", submission),
        ("data_dir", data_dir),
        ("mlebench", mlebench),
        ("output_dir", output_dir),
    ):
        _assert_path_allowed(path, field)
    timeout_seconds = int(arguments.get("timeout_seconds", 300))
    payload = grade_official_mle_submission(
        competition_id=_required_string(arguments, "competition_id"),
        submission_path=submission,
        data_dir=data_dir,
        output_dir=output_dir,
        mlebench_executable=mlebench,
        timeout_seconds=timeout_seconds,
    )
    payload["execution_metadata"] = _execution_metadata(
        arguments,
        started_at=started_at,
        start_time=start_time,
        timeout_seconds=timeout_seconds,
        command=[
            str(mlebench),
            "grade-sample",
            str(submission),
            _required_string(arguments, "competition_id"),
            "--data-dir",
            str(data_dir),
        ],
    )
    return payload


def run_official_mle_bench_round_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Run solve.py and grade the resulting local MLE-bench submission."""
    started_at = _utc_now()
    start_time = time.monotonic()
    workspace = Path(_required_string(arguments, "workspace")).expanduser().resolve()
    data_dir = Path(_required_string(arguments, "data_dir")).expanduser().resolve()
    mlebench = Path(_required_string(arguments, "mlebench")).expanduser().resolve()
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    for field, path in (
        ("workspace", workspace),
        ("data_dir", data_dir),
        ("mlebench", mlebench),
        ("output_dir", output_dir),
    ):
        _assert_path_allowed(path, field)
    timeout_seconds = int(arguments.get("timeout_seconds", 300))
    python_executable = str(arguments.get("python") or sys.executable)
    round_id = str(arguments.get("round_id") or "round-001")
    payload = run_official_mle_solver_round(
        competition_id=_required_string(arguments, "competition_id"),
        workspace=workspace,
        data_dir=data_dir,
        output_dir=output_dir,
        mlebench_executable=mlebench,
        python_executable=python_executable,
        round_id=round_id,
        timeout_seconds=timeout_seconds,
    )
    payload["execution_metadata"] = _execution_metadata(
        arguments,
        started_at=started_at,
        start_time=start_time,
        timeout_seconds=timeout_seconds,
        command=[python_executable, "solve.py"],
        task_id=f"mle-bench-{payload['competition_id']}-{round_id}",
        workspace=workspace,
    )
    return payload


def run_official_mle_bench_patch_round_tool(arguments: dict[str, Any]) -> dict[str, Any]:
    """Apply a client patch, run solve.py, and grade the resulting submission."""
    started_at = _utc_now()
    start_time = time.monotonic()
    workspace = Path(_required_string(arguments, "workspace")).expanduser().resolve()
    data_dir = Path(_required_string(arguments, "data_dir")).expanduser().resolve()
    mlebench = Path(_required_string(arguments, "mlebench")).expanduser().resolve()
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    for field, path in (
        ("workspace", workspace),
        ("data_dir", data_dir),
        ("mlebench", mlebench),
        ("output_dir", output_dir),
    ):
        _assert_path_allowed(path, field)
    round_id = str(arguments.get("round_id") or "round-001")
    timeout_seconds = int(arguments.get("timeout_seconds", 300))
    python_executable = str(arguments.get("python") or sys.executable)
    runtime_root = Path(str(arguments.get("runtime_root") or workspace)).expanduser().resolve()
    _assert_path_allowed(runtime_root, "runtime_root")
    allowed_files = _official_mle_patch_allowed_files(arguments.get("allowed_files"))
    patch_payload = apply_client_code_patch_tool({
        "workspace": str(workspace),
        "runtime_root": str(runtime_root),
        "patch": _required_string(arguments, "patch"),
        "description": arguments.get("description")
        or f"official MLE-bench patch round {round_id}",
        "allowed_files": allowed_files,
        "run_syntax_check": bool(arguments.get("run_syntax_check", True)),
        "test_timeout_seconds": int(arguments.get("test_timeout_seconds", 60)),
    })
    round_arguments = {
        "competition_id": _required_string(arguments, "competition_id"),
        "workspace": str(workspace),
        "data_dir": str(data_dir),
        "mlebench": str(mlebench),
        "output_dir": str(output_dir),
        "python": python_executable,
        "round_id": round_id,
        "timeout_seconds": timeout_seconds,
    }
    if arguments.get("runtime_root"):
        round_arguments["runtime_root"] = str(runtime_root)
    round_payload = run_official_mle_bench_round_tool(round_arguments)
    patch_execution = dict(patch_payload["patch_execution"])
    patch_execution.setdefault("status", patch_payload.get("status", "applied"))
    payload = {
        "status": round_payload.get("status"),
        "official_mle_bench": True,
        "official_scores_claimed": False,
        "round_id": round_id,
        "competition_id": _required_string(arguments, "competition_id"),
        "workspace": str(workspace),
        "patch_execution": patch_execution,
        "round": round_payload,
        "loop_decision": _official_mle_patch_loop_decision(round_payload),
        "execution_metadata": _execution_metadata(
            arguments,
            started_at=started_at,
            start_time=start_time,
            timeout_seconds=timeout_seconds,
            test_timeout_seconds=int(arguments.get("test_timeout_seconds", 60)),
            command=[python_executable, "solve.py"],
            task_id=f"mle-bench-{_required_string(arguments, 'competition_id')}-{round_id}",
            workspace=workspace,
        ),
    }
    _write_official_mle_patch_round_artifacts(
        payload=payload,
        patch_text=_required_string(arguments, "patch"),
        round_payload=round_payload,
    )
    return payload


def _write_official_mle_patch_round_artifacts(
    *,
    payload: dict[str, Any],
    patch_text: str,
    round_payload: dict[str, Any],
) -> None:
    round_report_path = round_payload.get("round_report_path")
    if not isinstance(round_report_path, str) or not round_report_path:
        return
    round_dir = Path(round_report_path).expanduser().resolve().parent
    round_dir.mkdir(parents=True, exist_ok=True)
    patch_diff_path = round_dir / "patch.diff"
    patch_round_report_path = round_dir / "patch-round-report.json"
    patch_diff_path.write_text(patch_text.rstrip("\n") + "\n", encoding="utf-8")
    payload["patch_diff_path"] = str(patch_diff_path)
    payload["patch_round_report_path"] = str(patch_round_report_path)
    patch_round_report_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _official_mle_patch_allowed_files(value: Any) -> list[str]:
    default_allowed = {"solve.py", "submission.csv"}
    allowed_files = _normalized_allowed_patch_files(value)
    if allowed_files is None:
        return sorted(default_allowed)
    unsupported = sorted(allowed_files - default_allowed)
    if unsupported:
        raise MCPToolError({
            "status": "failed",
            "error_type": "unsupported_mle_patch_files",
            "error": "run_official_mle_bench_patch_round only allows solve.py and submission.csv",
            "unsupported_files": unsupported,
            "allowed_files": sorted(default_allowed),
        })
    return sorted(allowed_files)


def _official_mle_patch_loop_decision(round_payload: dict[str, Any]) -> dict[str, Any]:
    grade = round_payload.get("grade") if isinstance(round_payload.get("grade"), dict) else {}
    report = grade.get("report") if isinstance(grade.get("report"), dict) else {}
    if round_payload.get("status") != "graded":
        return {
            "recommended_next_action": "stop",
            "reason_category": "round_failed",
            "reason": "Patch round did not reach a graded local submission.",
            "official_scores_claimed": False,
        }
    if report.get("valid_submission") is not True:
        return {
            "recommended_next_action": "stop",
            "reason_category": "invalid_submission",
            "reason": "Local grade-sample did not accept the generated submission.",
            "score": report.get("score"),
            "official_scores_claimed": False,
        }
    return {
        "recommended_next_action": "continue",
        "reason_category": "valid_local_score",
        "reason": "Local grade-sample produced a valid debug score; client may inspect artifacts and decide the next patch.",
        "score": report.get("score"),
        "is_lower_better": report.get("is_lower_better"),
        "official_scores_claimed": False,
    }


def _benchmark_proof_writer_paths(arguments: dict[str, Any]) -> tuple[Path, Path, Path]:
    manifest_path = Path(_required_string(arguments, "manifest")).expanduser().resolve()
    artifact_root = Path(_required_string(arguments, "artifact_root")).expanduser().resolve()
    output_dir = Path(_required_string(arguments, "output_dir")).expanduser().resolve()
    _assert_path_allowed(manifest_path, "manifest")
    _assert_path_allowed(artifact_root, "artifact_root")
    _assert_path_allowed(output_dir, "output_dir")
    return manifest_path, artifact_root, output_dir


def _optional_path_argument(arguments: dict[str, Any], key: str) -> Path | None:
    value = arguments.get(key)
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise MCPToolError({"status": "failed", "error": f"{key} must be a string"})
    return Path(value)


def _optional_allowed_path(arguments: dict[str, Any], key: str) -> Path | None:
    path = _optional_path_argument(arguments, key)
    if path is None:
        return None
    resolved = path.expanduser().resolve()
    _assert_path_allowed(resolved, key)
    return resolved


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


def build_skill_contracts() -> dict[str, dict[str, Any]]:
    """Return skill metadata clients can use to bind skills to this contract."""
    return {
        name: {
            **contract,
            "contract_version": MCP_CONTRACT_VERSION,
            "stability": "preview",
        }
        for name, contract in SKILL_CONTRACTS.items()
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
    "plan_research_case": plan_research_case_tool,
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
    "build_proposal_context": build_proposal_context_tool,
    "validate_client_proposal_contract": validate_client_proposal_contract_tool,
    "write_proposal_reflection": write_proposal_reflection_tool,
    "summarize_proposal_search": summarize_proposal_search_tool,
    "run_next_experiment_from_review": run_next_experiment_from_review_tool,
    "get_benchmark_harness_probe": get_benchmark_harness_probe_tool,
    "plan_benchmark_proof_run": plan_benchmark_proof_run_tool,
    "write_benchmark_proof_setup_bundle": write_benchmark_proof_setup_bundle_tool,
    "write_benchmark_proof_publication_bundle": write_benchmark_proof_publication_bundle_tool,
    "write_benchmark_proof_archive": write_benchmark_proof_archive_tool,
    "get_hf_external_eval_targets": get_hf_external_eval_targets_tool,
    "write_hf_external_eval_plan": write_hf_external_eval_plan_tool,
    "write_cp_bench_live_verification": write_cp_bench_live_verification_tool,
    "run_cp_bench_local_baseline": run_cp_bench_local_baseline_tool,
    "run_cp_bench_proposal_round": run_cp_bench_proposal_round_tool,
    "run_cp_bench_candidate_round": run_cp_bench_candidate_round_tool,
    "build_cp_bench_proposal_context": build_cp_bench_proposal_context_tool,
    "write_cp_bench_client_candidate_submission": (
        write_cp_bench_client_candidate_submission_tool
    ),
    "write_cp_bench_submission_gate": write_cp_bench_submission_gate_tool,
    "write_smol_worldcup_live_verification": write_smol_worldcup_live_verification_tool,
    "write_smol_worldcup_prompt_leakage_audit": (
        write_smol_worldcup_prompt_leakage_audit_tool
    ),
    "run_smol_worldcup_local_baseline": run_smol_worldcup_local_baseline_tool,
    "run_smol_worldcup_model_eval": run_smol_worldcup_model_eval_tool,
    "run_smol_worldcup_proposal_round": run_smol_worldcup_proposal_round_tool,
    "run_smol_worldcup_rescore": run_smol_worldcup_rescore_tool,
    "write_smol_worldcup_rescore_proof_archive": (
        write_smol_worldcup_rescore_proof_archive_tool
    ),
    "write_smol_worldcup_submission_probe": write_smol_worldcup_submission_probe_tool,
    "write_official_mle_bench_patch_round_proof_bundle": (
        write_official_mle_bench_patch_round_proof_bundle_tool
    ),
    "run_fasttext_patch_round": run_fasttext_patch_round_tool,
    "write_fasttext_patch_round_proof_bundle": write_fasttext_patch_round_proof_bundle_tool,
    "run_fasttext_multi_proposal_loop": run_fasttext_multi_proposal_loop_tool,
    "write_fasttext_release_proof_bundle": write_fasttext_release_proof_bundle_tool,
    "prepare_paperbench_codex_review_bundle": prepare_paperbench_codex_review_bundle_tool,
    "write_paperbench_codex_review_report": write_paperbench_codex_review_report_tool,
    "record_research_memory": record_research_memory_tool,
    "retrieve_research_memory": retrieve_research_memory_tool,
    "suggest_from_memory": suggest_from_memory_tool,
    "promote_memory_card": promote_memory_card_tool,
    "audit_memory_trace": audit_memory_trace_tool,
    "prepare_official_mle_bench_workspace": prepare_official_mle_bench_workspace_tool,
    "grade_official_mle_bench_submission": grade_official_mle_bench_submission_tool,
    "run_official_mle_bench_round": run_official_mle_bench_round_tool,
    "run_official_mle_bench_patch_round": run_official_mle_bench_patch_round_tool,
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
