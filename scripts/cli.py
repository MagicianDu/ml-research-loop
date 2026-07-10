"""Command-line interface for ml-research-loop."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from lib.demo_templates import (
    list_demo_templates,
    materialize_demo_template,
    run_demo_template,
)
from lib.benchmarks import (
    build_benchmark_readiness,
    load_hf_eval_targets,
    build_official_harness_probe,
    build_official_proof_setup_bundle,
    build_proof_archive_bundle,
    build_proof_publication_bundle,
    build_public_proof_plan,
    grade_official_mle_submission,
    materialize_official_mle_agent_workspace,
    run_official_mle_solver_round,
    run_cp_bench_candidate_round,
    run_cp_bench_proposal_round,
    select_hf_eval_targets,
    write_cp_bench_client_candidate_submission,
    write_cp_bench_local_baseline,
    write_cp_bench_live_verification,
    write_cp_bench_proposal_context,
    write_cp_bench_submission_gate,
    write_official_mle_patch_round_proof_bundle,
    write_official_proof_setup_bundle,
    write_arguard_b1_live_verification,
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
from lib.feedback_bundle import build_feedback_bundle, write_feedback_bundle
from lib.memory_adapters import search_memory_adapters, sync_cards_to_adapters
from lib.failure_driven_proposal import (
    build_gate_policy_composition,
    build_gate_policy_graph,
    build_gate_policy_input,
    build_method_proposal_generation_trace,
    build_method_search_study,
    build_multi_optimizer_candidate_race,
    build_optuna_dashboard_export,
    build_optuna_sampler_adapter,
    build_optuna_storage_adapter,
    build_model_runtime_preflight,
    build_optimizer_package_runtime_benefit_audit,
    build_optimizer_gate_scheduler_plan,
    build_optimizer_gate_execution_preflight,
    build_optimizer_gate_execution_plan,
    build_optimizer_gate_system_spec,
    build_registered_profile_canary_result_gate,
    build_registered_profile_outcome_schedule,
    build_registered_profile_canary_preflight,
    build_registered_profile_execution_bundle,
    build_prompt_profile_registration_plan,
    register_prompt_profile_from_plan,
    build_prompt_module_spec,
    build_optimizer_gate_run_plan,
    build_paired_repeat_manifest,
    build_slice_eval_matrix,
    build_slice_optimizer_selection,
    build_slice_repair_context,
    build_proposal_pattern_memory,
    evaluate_gate_policy,
    evaluate_gate_policy_graph,
    evaluate_slice_variance_gate,
    evaluate_slice_gate,
    extract_failure_records,
    generate_slice_patch_candidates,
    materialize_slice_patch_candidate,
    probe_optimizer_runtime,
    retrieve_proposal_patterns,
    record_proposal_outcome,
    record_slice_patch_outcome,
    build_optimizer_gate_canary_runner_bundle,
    build_optimizer_gate_human_promotion_approval,
    build_optimizer_gate_official_claim,
    build_optimizer_gate_official_submission,
    build_optimizer_gate_promotion_review_queue,
    build_optimizer_gate_scheduler_handoff,
    fetch_optimizer_gate_public_result,
    run_optimizer_gate_canary_runner_bundle,
    run_optimizer_gate_executable_loop,
    run_optimizer_gate_external_submission_action,
    run_optimizer_gate_local_promotion_action,
    run_optimizer_gate_local_promotion_rollback,
    run_method_search_trajectory,
    run_optimizer_gate_scheduler_action,
    run_optimizer_gate_scheduler_loop,
    run_multi_optimizer_candidate_race,
    run_real_benchmark_readiness_run,
    run_registered_profile_canary_execution,
    run_registered_profile_execution,
    ask_method_search_trial,
    tell_method_search_trial,
    verify_optimizer_gate_public_result,
)
from lib.proposal_effectiveness import (
    bridge_failure_driven_outcome_to_memory_card,
    build_cp_bench_proposal_effectiveness_bundle,
    build_cross_task_proposal_effectiveness_summary,
    build_failure_driven_client_proposal_templates,
    build_failure_driven_proposal_context,
    build_failure_driven_proposal_handoff,
    build_fasttext_proposal_effectiveness_bundle,
    build_mixed_signal_proposal_effectiveness_audit,
    build_proposal_effectiveness_claim_audit,
    build_real_paper_proposal_effectiveness_bundle,
    build_smol_worldcup_cached_confidence_scoring_gate,
    build_smol_worldcup_canary_control_arm_execution_bundle,
    build_smol_worldcup_canary_control_arm_handoff,
    build_smol_worldcup_canary_failure_slice_audit,
    build_smol_worldcup_confidence_variance_gate,
    build_smol_worldcup_promotion_gate,
    build_smol_worldcup_promotion_gate_refresh,
    build_smol_worldcup_proposal_effectiveness_bundle,
    build_smol_worldcup_result_analysis,
    evaluate_failure_driven_proposal_effectiveness,
    generate_failure_driven_proposals,
    rank_failure_driven_proposals,
)
from lib.proposal_contract import (
    build_proposal_context,
    build_proposal_reflection,
    validate_client_proposal,
)
from lib.proposal_memory import (
    proposal_reflection_to_memory_card,
)
from lib.proposal_search import build_proposal_search
from lib.research_memory import (
    ResearchMemoryCard,
    ResearchMemoryStore,
    extract_fasttext_release_memory_cards,
)
from lib import mcp_service
from lib.runtime import resolve_python_executable
from lib.task_protocol import WORKSPACE_ROOT
from ml_intern.autoresearch_manager import AutoResearchManager


def build_parser() -> argparse.ArgumentParser:
    """Build the ml-loop argument parser."""
    parser = argparse.ArgumentParser(prog="ml-loop")
    subcommands = parser.add_subparsers(dest="command", required=True)

    run = subcommands.add_parser("run", help="Run an autoresearch task config")
    run.add_argument("--task-config", required=True)
    run.add_argument("--workspace")
    run.add_argument("--max-experiments", type=int)
    run.add_argument("--max-duration", type=int)
    run.add_argument("--experiment-duration", type=int, default=300)
    run.add_argument("--ai", action="store_true")
    run.add_argument("--mock", action="store_true")
    run.add_argument("--verbose", action="store_true")

    status = subcommands.add_parser("status", help="Read task progress")
    status.add_argument("task_id")

    result = subcommands.add_parser("result", help="Read task result")
    result.add_argument("task_id")

    check = subcommands.add_parser("check", help="Run MCP/product readiness checks")
    check.add_argument("--python", default=resolve_python_executable(WORKSPACE_ROOT))
    check.add_argument("--skip-demos", action="store_true")
    check.add_argument("--json", action="store_true")

    artifacts = subcommands.add_parser("artifacts", help="Manage runtime artifacts")
    artifact_commands = artifacts.add_subparsers(dest="artifact_command", required=True)
    artifacts_list = artifact_commands.add_parser("list", help="List runtime artifacts")
    artifacts_list.add_argument("--runtime-root", required=True)
    artifacts_archive = artifact_commands.add_parser("archive", help="Archive one task's artifacts")
    artifacts_archive.add_argument("--runtime-root", required=True)
    artifacts_archive.add_argument("--task-id", required=True)
    artifacts_clean = artifact_commands.add_parser("clean", help="Delete one task's artifacts")
    artifacts_clean.add_argument("--runtime-root", required=True)
    artifacts_clean.add_argument("--task-id", required=True)
    artifacts_clean.add_argument("--confirm", action="store_true")

    memory = subcommands.add_parser("memory", help="Record or retrieve local research memory")
    memory_commands = memory.add_subparsers(dest="memory_command", required=True)
    memory_record = memory_commands.add_parser(
        "record-fasttext-release",
        help="Record fastText release proof artifacts into a memory JSONL store",
    )
    memory_record.add_argument("--store", type=Path, required=True)
    memory_record.add_argument("--release-manifest", type=Path, required=True)
    memory_record.add_argument("--multi-round-report", type=Path, required=True)
    memory_record.add_argument("--review-checklist", type=Path, required=True)
    memory_record.add_argument(
        "--sync-adapters",
        action="store_true",
        help="Explicitly sync recorded cards to configured optional memory adapters",
    )
    memory_record.add_argument(
        "--adapter",
        action="append",
        choices=["graphiti", "cognee"],
        help="Optional adapter to sync/search. Can be provided multiple times.",
    )
    memory_retrieve = memory_commands.add_parser(
        "retrieve",
        help="Retrieve matching local research memory cards",
    )
    memory_retrieve.add_argument("--store", type=Path, required=True)
    memory_retrieve.add_argument("--query", required=True)
    memory_retrieve.add_argument("--paper-id")
    memory_retrieve.add_argument("--dataset")
    memory_retrieve.add_argument("--limit", type=int, default=10)
    memory_retrieve.add_argument(
        "--include-adapters",
        action="store_true",
        help="Explicitly include configured optional adapter search results",
    )
    memory_retrieve.add_argument(
        "--adapter",
        action="append",
        choices=["graphiti", "cognee"],
        help="Optional adapter to sync/search. Can be provided multiple times.",
    )
    memory_cleanup = memory_commands.add_parser(
        "cleanup",
        help="Dry-run or execute local research memory retention cleanup",
    )
    memory_cleanup.add_argument("--store", type=Path, required=True)
    memory_cleanup.add_argument("--dry-run", action="store_true")
    memory_cleanup.add_argument("--keep-last", type=int)
    memory_cleanup.add_argument(
        "--memory-type",
        choices=["evidence", "experiment", "patch", "failure", "procedure"],
    )
    memory_cleanup.add_argument("--older-than-days", type=int)
    memory_cleanup.add_argument("--include-private", action="store_true")
    memory_cleanup.add_argument(
        "--confirm",
        action="store_true",
        help="Required to execute cleanup; --dry-run does not require confirmation",
    )
    memory_cleanup.add_argument("--json", action="store_true")
    memory_record_candidate = memory_commands.add_parser(
        "record-card-candidate",
        help="Record a reviewed memory card candidate into the local memory store",
    )
    memory_record_candidate.add_argument("--store", type=Path, required=True)
    memory_record_candidate.add_argument("--candidate-file", type=Path, required=True)
    memory_record_candidate.add_argument("--confirm", action="store_true")
    memory_record_candidate.add_argument(
        "--sync-adapters",
        action="store_true",
        help="Explicitly sync the recorded card to configured optional memory adapters",
    )
    memory_record_candidate.add_argument(
        "--adapter",
        action="append",
        choices=["graphiti", "cognee"],
        help="Optional adapter to sync/search. Can be provided multiple times.",
    )
    memory_record_candidate.add_argument("--json", action="store_true")

    proposal = subcommands.add_parser(
        "proposal",
        help="Build and validate client-side proposal prompt contracts",
    )
    proposal_commands = proposal.add_subparsers(dest="proposal_command", required=True)
    proposal_context = proposal_commands.add_parser(
        "context",
        help="Write a proposal context bundle for Codex/Claude",
    )
    proposal_context.add_argument("--objective", required=True)
    proposal_context.add_argument("--output-dir", type=Path, required=True)
    proposal_context.add_argument("--baseline-report", type=Path)
    proposal_context.add_argument("--current-report", type=Path)
    proposal_context.add_argument("--dev-report", type=Path)
    proposal_context.add_argument("--canary-report", type=Path)
    proposal_context.add_argument("--category-deltas", type=Path)
    proposal_context.add_argument("--failure-samples", type=Path)
    proposal_context.add_argument("--rollback-summary", type=Path)
    proposal_context.add_argument("--previous-proposals", type=Path)
    proposal_context.add_argument("--memory-cards", type=Path)
    proposal_context.add_argument("--memory-store", type=Path)
    proposal_context.add_argument("--memory-query")
    proposal_context.add_argument("--memory-paper-id")
    proposal_context.add_argument("--memory-dataset")
    proposal_context.add_argument("--memory-metric-name")
    proposal_context.add_argument("--memory-patch-type")
    proposal_context.add_argument("--memory-failure-category")
    proposal_context.add_argument("--memory-limit", type=int, default=5)
    proposal_context.add_argument("--resource-constraints", type=Path)
    proposal_context.add_argument("--allowed-change-surface", action="append")
    proposal_context.add_argument("--max-proposals", type=int, default=3)
    proposal_context.add_argument("--force", action="store_true")
    proposal_context.add_argument("--json", action="store_true")
    proposal_validate = proposal_commands.add_parser(
        "validate",
        help="Validate a client-generated proposal JSON file",
    )
    proposal_validate.add_argument("--proposal", type=Path, required=True)
    proposal_validate.add_argument("--allowed-change-surface", action="append")
    proposal_validate.add_argument("--json", action="store_true")
    proposal_reflect = proposal_commands.add_parser(
        "reflect",
        help="Write a proposal reflection artifact from an evaluation payload",
    )
    proposal_reflect.add_argument("--proposal", type=Path, required=True)
    proposal_reflect.add_argument("--evaluation", type=Path, required=True)
    proposal_reflect.add_argument("--output-dir", type=Path, required=True)
    proposal_reflect.add_argument("--force", action="store_true")
    proposal_reflect.add_argument("--memory-store", type=Path)
    proposal_reflect.add_argument("--sync-adapters", action="store_true")
    proposal_reflect.add_argument(
        "--adapter",
        action="append",
        choices=["graphiti", "cognee"],
        help="Optional memory adapter to sync. Can be provided multiple times.",
    )
    proposal_reflect.add_argument("--json", action="store_true")
    proposal_extract_failures = proposal_commands.add_parser(
        "extract-failures",
        help="Extract failure records from a proposal reflection or outcome artifact",
    )
    proposal_extract_failures.add_argument("--source-artifact", type=Path, required=True)
    proposal_extract_failures.add_argument("--output", type=Path, required=True)
    proposal_extract_failures.add_argument("--force", action="store_true")
    proposal_extract_failures.add_argument("--json", action="store_true")
    proposal_record_outcome = proposal_commands.add_parser(
        "record-outcome",
        help="Write a proposal outcome artifact from proposal and evaluation JSON",
    )
    proposal_record_outcome.add_argument("--proposal", type=Path, required=True)
    proposal_record_outcome.add_argument("--evaluation", type=Path, required=True)
    proposal_record_outcome.add_argument("--output", type=Path, required=True)
    proposal_record_outcome.add_argument("--force", action="store_true")
    proposal_record_outcome.add_argument("--json", action="store_true")
    proposal_pattern_memory = proposal_commands.add_parser(
        "build-pattern-memory",
        help="Aggregate proposal outcomes into local proposal pattern memory JSONL",
    )
    proposal_pattern_memory.add_argument("--outcomes", type=Path, required=True)
    proposal_pattern_memory.add_argument("--output", type=Path, required=True)
    proposal_pattern_memory.add_argument("--force", action="store_true")
    proposal_pattern_memory.add_argument("--json", action="store_true")
    proposal_retrieve_patterns = proposal_commands.add_parser(
        "retrieve-patterns",
        help="Retrieve proposal pattern memory entries by failure/proposal/metric filters",
    )
    proposal_retrieve_patterns.add_argument("--pattern-memory", type=Path, required=True)
    proposal_retrieve_patterns.add_argument("--failure-type")
    proposal_retrieve_patterns.add_argument("--proposal-type")
    proposal_retrieve_patterns.add_argument("--task-family")
    proposal_retrieve_patterns.add_argument("--metric-name")
    proposal_retrieve_patterns.add_argument("--limit", type=int, default=10)
    proposal_retrieve_patterns.add_argument("--output", type=Path)
    proposal_retrieve_patterns.add_argument("--force", action="store_true")
    proposal_retrieve_patterns.add_argument("--json", action="store_true")
    proposal_prompt_modules = proposal_commands.add_parser(
        "build-prompt-module-spec",
        help="Build a default prompt module spec for slice-aware repair",
    )
    proposal_prompt_modules.add_argument("--profile-id", required=True)
    proposal_prompt_modules.add_argument("--output", type=Path, required=True)
    proposal_prompt_modules.add_argument("--force", action="store_true")
    proposal_prompt_modules.add_argument("--json", action="store_true")
    proposal_slice_matrix = proposal_commands.add_parser(
        "build-slice-eval-matrix",
        help="Build a non-executing slice regression matrix from score breakdown artifacts",
    )
    proposal_slice_matrix.add_argument("--baseline-report", type=Path, required=True)
    proposal_slice_matrix.add_argument("--candidate-report", type=Path, required=True)
    proposal_slice_matrix.add_argument("--candidate-evaluation", type=Path)
    proposal_slice_matrix.add_argument("--output", type=Path, required=True)
    proposal_slice_matrix.add_argument("--force", action="store_true")
    proposal_slice_matrix.add_argument("--json", action="store_true")
    proposal_slice_context = proposal_commands.add_parser(
        "build-slice-repair-context",
        help="Build a one-module/one-section slice repair context",
    )
    proposal_slice_context.add_argument("--slice-matrix", type=Path, required=True)
    proposal_slice_context.add_argument("--prompt-modules", type=Path, required=True)
    proposal_slice_context.add_argument("--pattern-memory", type=Path)
    proposal_slice_context.add_argument("--output", type=Path, required=True)
    proposal_slice_context.add_argument("--force", action="store_true")
    proposal_slice_context.add_argument("--json", action="store_true")
    proposal_slice_patches = proposal_commands.add_parser(
        "generate-slice-patches",
        help="Generate deterministic section-local slice patch candidates",
    )
    proposal_slice_patches.add_argument("--context", type=Path, required=True)
    proposal_slice_patches.add_argument("--output", type=Path, required=True)
    proposal_slice_patches.add_argument("--optimizer", default="manual-template")
    proposal_slice_patches.add_argument(
        "--plugin-manifest",
        type=Path,
        action="append",
    )
    proposal_slice_patches.add_argument("--max-candidates", type=int, default=1)
    proposal_slice_patches.add_argument("--execute-optimizer", action="store_true")
    proposal_slice_patches.add_argument("--optimizer-model")
    proposal_slice_patches.add_argument("--optimizer-base-url")
    proposal_slice_patches.add_argument("--optimizer-api-key")
    proposal_slice_patches.add_argument("--optimizer-timeout-seconds", type=int, default=30)
    proposal_slice_patches.add_argument("--optimizer-temperature", type=float, default=0.0)
    proposal_slice_patches.add_argument("--optimizer-max-tokens", type=int, default=512)
    proposal_slice_patches.add_argument("--force", action="store_true")
    proposal_slice_patches.add_argument("--json", action="store_true")
    proposal_optimizer_runtime_probe = proposal_commands.add_parser(
        "probe-optimizer-runtime",
        help="Probe optimizer runtime readiness without executing benchmark evaluation",
    )
    proposal_optimizer_runtime_probe.add_argument("--optimizer", default="manual-template")
    proposal_optimizer_runtime_probe.add_argument(
        "--plugin-manifest",
        type=Path,
        action="append",
    )
    proposal_optimizer_runtime_probe.add_argument("--execute-probe", action="store_true")
    proposal_optimizer_runtime_probe.add_argument("--optimizer-model")
    proposal_optimizer_runtime_probe.add_argument("--optimizer-base-url")
    proposal_optimizer_runtime_probe.add_argument(
        "--optimizer-timeout-seconds",
        type=int,
        default=30,
    )
    proposal_optimizer_runtime_probe.add_argument("--output", type=Path, required=True)
    proposal_optimizer_runtime_probe.add_argument("--force", action="store_true")
    proposal_optimizer_runtime_probe.add_argument("--json", action="store_true")
    proposal_optimizer_package_runtime_benefit_audit = proposal_commands.add_parser(
        "build-optimizer-package-runtime-benefit-audit",
        help=(
            "Bind package runtime readiness, candidate generation, and local gate "
            "evidence into a benefit audit"
        ),
    )
    proposal_optimizer_package_runtime_benefit_audit.add_argument(
        "--optimizer-runtime-probe",
        type=Path,
        required=True,
    )
    proposal_optimizer_package_runtime_benefit_audit.add_argument(
        "--slice-patch-candidates",
        type=Path,
    )
    proposal_optimizer_package_runtime_benefit_audit.add_argument(
        "--gate-decision",
        type=Path,
    )
    proposal_optimizer_package_runtime_benefit_audit.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    proposal_optimizer_package_runtime_benefit_audit.add_argument(
        "--force",
        action="store_true",
    )
    proposal_optimizer_package_runtime_benefit_audit.add_argument(
        "--json",
        action="store_true",
    )
    proposal_method_trace = proposal_commands.add_parser(
        "build-method-proposal-generation-trace",
        help=(
            "Record method proposal search context, structured reasoning trace, "
            "ranking, and validation links without executing experiments"
        ),
    )
    proposal_method_trace.add_argument("--generation-context", type=Path, required=True)
    proposal_method_trace.add_argument("--generation-run", type=Path, required=True)
    proposal_method_trace.add_argument("--reasoning-trace", type=Path, required=True)
    proposal_method_trace.add_argument("--proposals", type=Path, required=True)
    proposal_method_trace.add_argument("--ranking-decisions", type=Path, required=True)
    proposal_method_trace.add_argument(
        "--selected-proposal-id",
        action="append",
        default=[],
    )
    proposal_method_trace.add_argument("--execution-links", type=Path)
    proposal_method_trace.add_argument("--gate-results", type=Path)
    proposal_method_trace.add_argument("--output", type=Path, required=True)
    proposal_method_trace.add_argument("--force", action="store_true")
    proposal_method_trace.add_argument("--json", action="store_true")
    proposal_method_search_study = proposal_commands.add_parser(
        "build-method-search-study",
        help="Create an Optuna-style method search Study artifact without importing Optuna",
    )
    proposal_method_search_study.add_argument("--study-name", required=True)
    proposal_method_search_study.add_argument("--objective", required=True)
    proposal_method_search_study.add_argument(
        "--direction",
        default="maximize",
        choices=("maximize", "minimize"),
    )
    proposal_method_search_study.add_argument("--operator", action="append", default=[])
    proposal_method_search_study.add_argument("--output", type=Path, required=True)
    proposal_method_search_study.add_argument("--force", action="store_true")
    proposal_method_search_study.add_argument("--json", action="store_true")
    proposal_method_search_ask = proposal_commands.add_parser(
        "ask-method-search-trial",
        help=(
            "Run MethodSearchStudy.ask through HexagonGuidedLLMSampler and "
            "emit WAITING trials"
        ),
    )
    proposal_method_search_ask.add_argument("--study", type=Path, required=True)
    proposal_method_search_ask.add_argument("--objective")
    proposal_method_search_ask.add_argument("--operator", action="append", default=[])
    proposal_method_search_ask.add_argument("--llm-proposals", type=Path)
    proposal_method_search_ask.add_argument("--gate-feedback-memory", type=Path)
    proposal_method_search_ask.add_argument("--gate-feedback-memory-store", type=Path)
    proposal_method_search_ask.add_argument("--model", default="llm-method-search")
    proposal_method_search_ask.add_argument("--execute-llm", action="store_true")
    proposal_method_search_ask.add_argument(
        "--llm-base-url",
        default="http://127.0.0.1:1234/v1",
    )
    proposal_method_search_ask.add_argument("--llm-provider", default="openai-compatible")
    proposal_method_search_ask.add_argument("--llm-api-key-env")
    proposal_method_search_ask.add_argument("--llm-temperature", type=float, default=0.2)
    proposal_method_search_ask.add_argument("--llm-max-tokens", type=int, default=1600)
    proposal_method_search_ask.add_argument("--llm-timeout-seconds", type=int, default=60)
    proposal_method_search_ask.add_argument("--adapter", default="llm-method-search")
    proposal_method_search_ask.add_argument("--slice-id", default="unspecified")
    proposal_method_search_ask.add_argument("--patch-scope", default="unspecified")
    proposal_method_search_ask.add_argument("--budget-json", default="{}")
    proposal_method_search_ask.add_argument("--max-trials", type=int, default=1)
    proposal_method_search_ask.add_argument("--output-dir", type=Path)
    proposal_method_search_ask.add_argument("--output", type=Path, required=True)
    proposal_method_search_ask.add_argument("--force", action="store_true")
    proposal_method_search_ask.add_argument("--json", action="store_true")
    proposal_method_search_tell = proposal_commands.add_parser(
        "tell-method-search-trial",
        help="Run MethodSearchStudy.tell with a gate result and update sampler feedback",
    )
    proposal_method_search_tell.add_argument("--study", type=Path, required=True)
    trial_group = proposal_method_search_tell.add_mutually_exclusive_group(required=True)
    trial_group.add_argument("--trial", type=Path)
    trial_group.add_argument("--trial-id")
    proposal_method_search_tell.add_argument("--gate-result", type=Path, required=True)
    proposal_method_search_tell.add_argument("--feedback-store", type=Path)
    proposal_method_search_tell.add_argument("--output", type=Path, required=True)
    proposal_method_search_tell.add_argument("--force", action="store_true")
    proposal_method_search_tell.add_argument("--json", action="store_true")
    proposal_optuna_sampler = proposal_commands.add_parser(
        "build-optuna-sampler-adapter",
        help="Export the MethodSearchStudy sampler as an Optuna-compatible contract",
    )
    proposal_optuna_sampler.add_argument("--study", type=Path, required=True)
    proposal_optuna_sampler.add_argument("--output", type=Path, required=True)
    proposal_optuna_sampler.add_argument("--force", action="store_true")
    proposal_optuna_sampler.add_argument("--json", action="store_true")
    proposal_optuna_storage = proposal_commands.add_parser(
        "build-optuna-storage-adapter",
        help="Export MethodSearchStudy storage as an Optuna-compatible contract",
    )
    proposal_optuna_storage.add_argument("--study", type=Path, required=True)
    proposal_optuna_storage.add_argument("--gate-feedback-memory-store", type=Path)
    proposal_optuna_storage.add_argument("--output", type=Path, required=True)
    proposal_optuna_storage.add_argument("--force", action="store_true")
    proposal_optuna_storage.add_argument("--json", action="store_true")
    proposal_optuna_dashboard = proposal_commands.add_parser(
        "build-optuna-dashboard-export",
        help="Export a dashboard-ready Optuna-style MethodSearchStudy artifact",
    )
    proposal_optuna_dashboard.add_argument("--study", type=Path, required=True)
    proposal_optuna_dashboard.add_argument("--gate-feedback-memory-store", type=Path)
    proposal_optuna_dashboard.add_argument("--output", type=Path, required=True)
    proposal_optuna_dashboard.add_argument("--force", action="store_true")
    proposal_optuna_dashboard.add_argument("--json", action="store_true")
    proposal_multi_optimizer_race = proposal_commands.add_parser(
        "build-multi-optimizer-candidate-race",
        help=(
            "Run LLM/Optuna/TextGrad/DSPy/heuristic candidates through one "
            "MethodSearch gate ledger and select a gate-backed winner"
        ),
    )
    proposal_multi_optimizer_race.add_argument("--race-name", required=True)
    proposal_multi_optimizer_race.add_argument("--objective", required=True)
    proposal_multi_optimizer_race.add_argument(
        "--candidate-sources",
        type=Path,
        required=True,
    )
    proposal_multi_optimizer_race.add_argument("--gate-results", type=Path, required=True)
    proposal_multi_optimizer_race.add_argument("--operator", action="append", default=[])
    proposal_multi_optimizer_race.add_argument(
        "--direction",
        default="maximize",
        choices=("maximize", "minimize"),
    )
    proposal_multi_optimizer_race.add_argument(
        "--model",
        default="multi-optimizer-candidate-race",
    )
    proposal_multi_optimizer_race.add_argument(
        "--adapter",
        default="multi-optimizer-candidate-race",
    )
    proposal_multi_optimizer_race.add_argument("--slice-id", default="multi_optimizer_race")
    proposal_multi_optimizer_race.add_argument(
        "--patch-scope",
        default="multi_optimizer_candidate",
    )
    proposal_multi_optimizer_race.add_argument("--budget-json", default="{}")
    proposal_multi_optimizer_race.add_argument("--output-dir", type=Path)
    proposal_multi_optimizer_race.add_argument("--feedback-store", type=Path)
    proposal_multi_optimizer_race.add_argument("--output", type=Path, required=True)
    proposal_multi_optimizer_race.add_argument("--force", action="store_true")
    proposal_multi_optimizer_race.add_argument("--json", action="store_true")
    proposal_multi_optimizer_run = proposal_commands.add_parser(
        "run-multi-optimizer-candidate-race",
        help=(
            "Generate candidates from LLM/Optuna/TextGrad/DSPy/heuristic sources "
            "before running one MethodSearch gate race"
        ),
    )
    proposal_multi_optimizer_run.add_argument("--race-name", required=True)
    proposal_multi_optimizer_run.add_argument("--objective", required=True)
    proposal_multi_optimizer_run.add_argument(
        "--mode",
        default="optimization-run",
        choices=("optimization-run", "review/dry-run"),
    )
    proposal_multi_optimizer_run.add_argument(
        "--dry-run",
        dest="mode",
        action="store_const",
        const="review/dry-run",
        help="Alias for --mode review/dry-run.",
    )
    proposal_multi_optimizer_run.add_argument("--context", type=Path, required=True)
    proposal_multi_optimizer_run.add_argument("--gate-results", type=Path, required=True)
    proposal_multi_optimizer_run.add_argument(
        "--optimizer-source",
        action="append",
        default=[],
        help="Optimizer source to try; defaults to llm,optuna,textgrad,dspy,heuristic.",
    )
    proposal_multi_optimizer_run.add_argument("--operator", action="append", default=[])
    proposal_multi_optimizer_run.add_argument(
        "--direction",
        default="maximize",
        choices=("maximize", "minimize"),
    )
    proposal_multi_optimizer_run.add_argument(
        "--max-candidates-per-source",
        type=int,
        default=1,
    )
    proposal_multi_optimizer_run.add_argument("--llm-proposals", type=Path)
    proposal_multi_optimizer_run.add_argument(
        "--execute-llm",
        action="store_true",
        default=None,
    )
    proposal_multi_optimizer_run.add_argument(
        "--execute-optimizer-runtime",
        dest="execute_optimizer_runtime",
        action="store_true",
        default=None,
    )
    proposal_multi_optimizer_run.add_argument(
        "--no-execute-optimizer-runtime",
        dest="execute_optimizer_runtime",
        action="store_false",
    )
    proposal_multi_optimizer_run.add_argument(
        "--allow-style-fallback",
        dest="allow_style_fallback",
        action="store_true",
        default=None,
    )
    proposal_multi_optimizer_run.add_argument(
        "--no-style-fallback",
        dest="allow_style_fallback",
        action="store_false",
    )
    proposal_multi_optimizer_run.add_argument(
        "--plugin-manifest",
        type=Path,
        action="append",
    )
    proposal_multi_optimizer_run.add_argument("--optimizer-model")
    proposal_multi_optimizer_run.add_argument("--optimizer-base-url")
    proposal_multi_optimizer_run.add_argument("--optimizer-api-key")
    proposal_multi_optimizer_run.add_argument(
        "--optimizer-timeout-seconds",
        type=int,
        default=30,
    )
    proposal_multi_optimizer_run.add_argument(
        "--optimizer-temperature",
        type=float,
        default=0.0,
    )
    proposal_multi_optimizer_run.add_argument(
        "--optimizer-max-tokens",
        type=int,
        default=512,
    )
    proposal_multi_optimizer_run.add_argument("--output-dir", type=Path, required=True)
    proposal_multi_optimizer_run.add_argument("--feedback-store", type=Path)
    proposal_multi_optimizer_run.add_argument("--output", type=Path, required=True)
    proposal_multi_optimizer_run.add_argument("--force", action="store_true")
    proposal_multi_optimizer_run.add_argument("--json", action="store_true")
    proposal_method_search_trajectory = proposal_commands.add_parser(
        "run-method-search-trajectory",
        help=(
            "Run 3-5 multi-optimizer candidate races as one gate-feedbacked "
            "method-search trajectory"
        ),
    )
    proposal_method_search_trajectory.add_argument("--trajectory-name", required=True)
    proposal_method_search_trajectory.add_argument("--objective", required=True)
    proposal_method_search_trajectory.add_argument(
        "--mode",
        default="optimization-run",
        choices=("optimization-run", "review/dry-run"),
    )
    proposal_method_search_trajectory.add_argument("--context", type=Path, required=True)
    proposal_method_search_trajectory.add_argument(
        "--round-gate-results",
        type=Path,
        action="append",
        default=[],
        required=True,
        help="Gate results for one round; provide 3-5 in execution order.",
    )
    proposal_method_search_trajectory.add_argument(
        "--round-llm-proposals",
        type=Path,
        action="append",
        default=[],
    )
    proposal_method_search_trajectory.add_argument(
        "--round-count",
        type=int,
        default=4,
    )
    proposal_method_search_trajectory.add_argument(
        "--optimizer-source",
        action="append",
        default=[],
    )
    proposal_method_search_trajectory.add_argument("--operator", action="append", default=[])
    proposal_method_search_trajectory.add_argument(
        "--direction",
        default="maximize",
        choices=("maximize", "minimize"),
    )
    proposal_method_search_trajectory.add_argument(
        "--max-candidates-per-source",
        type=int,
        default=1,
    )
    proposal_method_search_trajectory.add_argument(
        "--execute-llm",
        action="store_true",
        default=None,
    )
    proposal_method_search_trajectory.add_argument(
        "--execute-optimizer-runtime",
        dest="execute_optimizer_runtime",
        action="store_true",
        default=None,
    )
    proposal_method_search_trajectory.add_argument(
        "--no-execute-optimizer-runtime",
        dest="execute_optimizer_runtime",
        action="store_false",
    )
    proposal_method_search_trajectory.add_argument(
        "--allow-style-fallback",
        dest="allow_style_fallback",
        action="store_true",
        default=None,
    )
    proposal_method_search_trajectory.add_argument(
        "--no-style-fallback",
        dest="allow_style_fallback",
        action="store_false",
    )
    proposal_method_search_trajectory.add_argument(
        "--plugin-manifest",
        type=Path,
        action="append",
    )
    proposal_method_search_trajectory.add_argument("--optimizer-model")
    proposal_method_search_trajectory.add_argument("--optimizer-base-url")
    proposal_method_search_trajectory.add_argument("--optimizer-api-key")
    proposal_method_search_trajectory.add_argument(
        "--optimizer-timeout-seconds",
        type=int,
        default=30,
    )
    proposal_method_search_trajectory.add_argument(
        "--optimizer-temperature",
        type=float,
        default=0.0,
    )
    proposal_method_search_trajectory.add_argument(
        "--optimizer-max-tokens",
        type=int,
        default=512,
    )
    proposal_method_search_trajectory.add_argument("--output-dir", type=Path, required=True)
    proposal_method_search_trajectory.add_argument("--feedback-store", type=Path)
    proposal_method_search_trajectory.add_argument("--output", type=Path, required=True)
    proposal_method_search_trajectory.add_argument("--force", action="store_true")
    proposal_method_search_trajectory.add_argument("--json", action="store_true")
    proposal_real_benchmark_readiness = proposal_commands.add_parser(
        "run-real-benchmark-readiness",
        help=(
            "Run 3-5 optimizer races where gate results are produced by local "
            "Smol WorldCup benchmark eval outcomes"
        ),
    )
    proposal_real_benchmark_readiness.add_argument("--run-name", required=True)
    proposal_real_benchmark_readiness.add_argument("--objective", required=True)
    proposal_real_benchmark_readiness.add_argument(
        "--benchmark-id",
        default="smol_worldcup",
    )
    proposal_real_benchmark_readiness.add_argument("--rows", type=Path, required=True)
    proposal_real_benchmark_readiness.add_argument("--context", type=Path)
    proposal_real_benchmark_readiness.add_argument(
        "--round-count",
        type=int,
        default=3,
    )
    proposal_real_benchmark_readiness.add_argument(
        "--mode",
        default="optimization-run",
        choices=("optimization-run", "review/dry-run"),
    )
    proposal_real_benchmark_readiness.add_argument(
        "--optimizer-source",
        action="append",
        default=[],
    )
    proposal_real_benchmark_readiness.add_argument(
        "--operator",
        action="append",
        default=[],
    )
    proposal_real_benchmark_readiness.add_argument(
        "--direction",
        default="maximize",
        choices=("maximize", "minimize"),
    )
    proposal_real_benchmark_readiness.add_argument(
        "--max-candidates-per-source",
        type=int,
        default=1,
    )
    proposal_real_benchmark_readiness.add_argument(
        "--execute-llm",
        action="store_true",
        default=None,
    )
    proposal_real_benchmark_readiness.add_argument(
        "--execute-optimizer-runtime",
        dest="execute_optimizer_runtime",
        action="store_true",
        default=None,
    )
    proposal_real_benchmark_readiness.add_argument(
        "--no-execute-optimizer-runtime",
        dest="execute_optimizer_runtime",
        action="store_false",
    )
    proposal_real_benchmark_readiness.add_argument(
        "--allow-style-fallback",
        dest="allow_style_fallback",
        action="store_true",
        default=None,
    )
    proposal_real_benchmark_readiness.add_argument(
        "--no-style-fallback",
        dest="allow_style_fallback",
        action="store_false",
    )
    proposal_real_benchmark_readiness.add_argument(
        "--plugin-manifest",
        type=Path,
        action="append",
    )
    proposal_real_benchmark_readiness.add_argument("--optimizer-model")
    proposal_real_benchmark_readiness.add_argument("--optimizer-base-url")
    proposal_real_benchmark_readiness.add_argument("--optimizer-api-key")
    proposal_real_benchmark_readiness.add_argument(
        "--optimizer-timeout-seconds",
        type=int,
        default=30,
    )
    proposal_real_benchmark_readiness.add_argument(
        "--optimizer-temperature",
        type=float,
        default=0.0,
    )
    proposal_real_benchmark_readiness.add_argument(
        "--optimizer-max-tokens",
        type=int,
        default=512,
    )
    proposal_real_benchmark_readiness.add_argument(
        "--model",
        default="openai/gpt-oss-20b",
    )
    proposal_real_benchmark_readiness.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000/v1",
    )
    proposal_real_benchmark_readiness.add_argument(
        "--model-provider",
        default="openai-compatible",
        choices=["openai-compatible", "deepseek"],
    )
    proposal_real_benchmark_readiness.add_argument("--api-key-env")
    proposal_real_benchmark_readiness.add_argument(
        "--timeout-seconds",
        type=int,
        default=120,
    )
    proposal_real_benchmark_readiness.add_argument(
        "--temperature",
        type=float,
        default=0.0,
    )
    proposal_real_benchmark_readiness.add_argument(
        "--max-tokens",
        type=int,
        default=512,
    )
    proposal_real_benchmark_readiness.add_argument(
        "--judge-mode",
        default="heuristic",
        choices=["heuristic", "openai-compatible"],
    )
    proposal_real_benchmark_readiness.add_argument(
        "--canary-fraction",
        type=float,
        default=0.25,
    )
    proposal_real_benchmark_readiness.add_argument("--gate-metric", default="SHIFT")
    proposal_real_benchmark_readiness.add_argument(
        "--min-dev-delta",
        type=float,
        default=0.0,
    )
    proposal_real_benchmark_readiness.add_argument(
        "--min-canary-delta",
        type=float,
        default=0.0,
    )
    proposal_real_benchmark_readiness.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )
    proposal_real_benchmark_readiness.add_argument("--feedback-store", type=Path)
    proposal_real_benchmark_readiness.add_argument("--output", type=Path, required=True)
    proposal_real_benchmark_readiness.add_argument("--force", action="store_true")
    proposal_real_benchmark_readiness.add_argument("--json", action="store_true")
    proposal_slice_materialize = proposal_commands.add_parser(
        "materialize-slice-patch",
        help="Build a review-only materialization bundle for a slice patch candidate",
    )
    proposal_slice_materialize.add_argument("--candidate", type=Path, required=True)
    proposal_slice_materialize.add_argument("--base-profile-id", required=True)
    proposal_slice_materialize.add_argument("--output", type=Path, required=True)
    proposal_slice_materialize.add_argument("--force", action="store_true")
    proposal_slice_materialize.add_argument("--json", action="store_true")
    proposal_optimizer_gate_run = proposal_commands.add_parser(
        "build-optimizer-gate-run",
        help="Build a non-executing optimizer/gate run bundle",
    )
    proposal_optimizer_gate_run.add_argument("--context", type=Path, required=True)
    proposal_optimizer_gate_run.add_argument("--base-profile-id", required=True)
    proposal_optimizer_gate_run.add_argument("--optimizer", default="manual-template")
    proposal_optimizer_gate_run.add_argument(
        "--plugin-manifest",
        type=Path,
        action="append",
    )
    proposal_optimizer_gate_run.add_argument("--max-candidates", type=int, default=1)
    proposal_optimizer_gate_run.add_argument("--execute-runtime-probe", action="store_true")
    proposal_optimizer_gate_run.add_argument("--output-dir", type=Path, required=True)
    proposal_optimizer_gate_run.add_argument("--force", action="store_true")
    proposal_optimizer_gate_run.add_argument("--json", action="store_true")
    proposal_optimizer_gate_execution_plan = proposal_commands.add_parser(
        "build-optimizer-gate-execution-plan",
        help="Build a non-executing benchmark adapter execution plan",
    )
    proposal_optimizer_gate_execution_plan.add_argument(
        "--run",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_execution_plan.add_argument(
        "--benchmark",
        default="smol_worldcup",
    )
    proposal_optimizer_gate_execution_plan.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_execution_plan.add_argument("--force", action="store_true")
    proposal_optimizer_gate_execution_plan.add_argument("--json", action="store_true")
    proposal_prompt_profile_registration_plan = proposal_commands.add_parser(
        "build-prompt-profile-registration-plan",
        help="Build a review-only prompt profile registration plan",
    )
    proposal_prompt_profile_registration_plan.add_argument(
        "--materialization",
        type=Path,
        required=True,
    )
    proposal_prompt_profile_registration_plan.add_argument(
        "--benchmark",
        default="smol_worldcup",
    )
    proposal_prompt_profile_registration_plan.add_argument(
        "--proposed-profile-id",
        required=True,
    )
    proposal_prompt_profile_registration_plan.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    proposal_prompt_profile_registration_plan.add_argument("--force", action="store_true")
    proposal_prompt_profile_registration_plan.add_argument("--json", action="store_true")
    proposal_prompt_profile_registration = proposal_commands.add_parser(
        "register-prompt-profile",
        help="Build a prompt profile registration artifact from an approved plan",
    )
    proposal_prompt_profile_registration.add_argument(
        "--registration-plan",
        type=Path,
        required=True,
    )
    proposal_prompt_profile_registration.add_argument("--approve", action="store_true")
    proposal_prompt_profile_registration.add_argument("--approved-by")
    proposal_prompt_profile_registration.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    proposal_prompt_profile_registration.add_argument("--force", action="store_true")
    proposal_prompt_profile_registration.add_argument("--json", action="store_true")
    proposal_optimizer_gate_execution_preflight = proposal_commands.add_parser(
        "build-optimizer-gate-execution-preflight",
        help="Build a non-executing optimizer/gate execution preflight",
    )
    proposal_optimizer_gate_execution_preflight.add_argument(
        "--registration-plan",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_execution_preflight.add_argument(
        "--registered-profile",
        type=Path,
    )
    proposal_optimizer_gate_execution_preflight.add_argument("--registered-profile-id")
    proposal_optimizer_gate_execution_preflight.add_argument(
        "--prompt-leakage-audit",
        type=Path,
    )
    proposal_optimizer_gate_execution_preflight.add_argument("--target-smoke", type=Path)
    proposal_optimizer_gate_execution_preflight.add_argument("--dev-model-eval", type=Path)
    proposal_optimizer_gate_execution_preflight.add_argument(
        "--gate-decision",
        type=Path,
        action="append",
    )
    proposal_optimizer_gate_execution_preflight.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_execution_preflight.add_argument("--force", action="store_true")
    proposal_optimizer_gate_execution_preflight.add_argument("--json", action="store_true")
    proposal_registered_profile_execution_bundle = proposal_commands.add_parser(
        "build-registered-profile-execution-bundle",
        help="Build a non-executing registered profile execution bundle",
    )
    proposal_registered_profile_execution_bundle.add_argument(
        "--registration-plan",
        type=Path,
        required=True,
    )
    proposal_registered_profile_execution_bundle.add_argument(
        "--registered-profile",
        type=Path,
    )
    proposal_registered_profile_execution_bundle.add_argument("--registered-profile-id")
    proposal_registered_profile_execution_bundle.add_argument(
        "--prompt-leakage-audit",
        type=Path,
    )
    proposal_registered_profile_execution_bundle.add_argument(
        "--target-smoke",
        type=Path,
    )
    proposal_registered_profile_execution_bundle.add_argument(
        "--dev-model-eval",
        type=Path,
    )
    proposal_registered_profile_execution_bundle.add_argument(
        "--gate-decision",
        type=Path,
        action="append",
    )
    proposal_registered_profile_execution_bundle.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )
    proposal_registered_profile_execution_bundle.add_argument("--force", action="store_true")
    proposal_registered_profile_execution_bundle.add_argument("--json", action="store_true")
    proposal_registered_profile_execution_run = proposal_commands.add_parser(
        "run-registered-profile-execution",
        help=(
            "Run safe registered profile execution stages and generate hard-gate "
            "artifacts from supplied eval tables before building the bundle"
        ),
    )
    proposal_registered_profile_execution_run.add_argument(
        "--registration-plan",
        type=Path,
        required=True,
    )
    proposal_registered_profile_execution_run.add_argument(
        "--registered-profile",
        type=Path,
    )
    proposal_registered_profile_execution_run.add_argument("--registered-profile-id")
    proposal_registered_profile_execution_run.add_argument(
        "--prompt-leakage-rows",
        type=Path,
    )
    proposal_registered_profile_execution_run.add_argument(
        "--prompt-leakage-audit",
        type=Path,
    )
    proposal_registered_profile_execution_run.add_argument(
        "--target-smoke",
        type=Path,
    )
    proposal_registered_profile_execution_run.add_argument(
        "--dev-model-eval",
        type=Path,
    )
    proposal_registered_profile_execution_run.add_argument(
        "--dev-baseline-eval",
        type=Path,
    )
    proposal_registered_profile_execution_run.add_argument(
        "--dev-gate-source",
        type=Path,
    )
    proposal_registered_profile_execution_run.add_argument(
        "--model-runtime-preflight",
        type=Path,
    )
    proposal_registered_profile_execution_run.add_argument(
        "--execute-model-eval",
        action="store_true",
        help="Explicitly run local model eval from supplied target/dev rows.",
    )
    proposal_registered_profile_execution_run.add_argument(
        "--target-smoke-rows",
        type=Path,
    )
    proposal_registered_profile_execution_run.add_argument(
        "--dev-model-eval-rows",
        type=Path,
    )
    proposal_registered_profile_execution_run.add_argument(
        "--model-eval-model",
        default="qwen/qwen3-8b",
    )
    proposal_registered_profile_execution_run.add_argument(
        "--model-eval-base-url",
        default="http://127.0.0.1:1234/v1",
    )
    proposal_registered_profile_execution_run.add_argument(
        "--model-eval-model-provider",
        default="openai-compatible",
        choices=["openai-compatible", "deepseek"],
    )
    proposal_registered_profile_execution_run.add_argument("--model-eval-api-key-env")
    proposal_registered_profile_execution_run.add_argument(
        "--model-eval-timeout-seconds",
        type=int,
        default=120,
    )
    proposal_registered_profile_execution_run.add_argument(
        "--model-eval-temperature",
        type=float,
        default=0.0,
    )
    proposal_registered_profile_execution_run.add_argument(
        "--model-eval-max-tokens",
        type=int,
        default=512,
    )
    proposal_registered_profile_execution_run.add_argument(
        "--model-eval-judge-mode",
        default="heuristic",
        choices=["heuristic", "openai-compatible"],
    )
    proposal_registered_profile_execution_run.add_argument(
        "--gate-decision",
        type=Path,
        action="append",
    )
    proposal_registered_profile_execution_run.add_argument(
        "--benchmark",
        default="smol_worldcup",
    )
    proposal_registered_profile_execution_run.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )
    proposal_registered_profile_execution_run.add_argument("--force", action="store_true")
    proposal_registered_profile_execution_run.add_argument("--json", action="store_true")
    proposal_registered_profile_canary_preflight = proposal_commands.add_parser(
        "build-registered-profile-canary-preflight",
        help="Build a non-executing registered profile canary preflight",
    )
    proposal_registered_profile_canary_preflight.add_argument(
        "--registered-profile-execution-run",
        type=Path,
        required=True,
    )
    proposal_registered_profile_canary_preflight.add_argument(
        "--canary-rows",
        type=Path,
    )
    proposal_registered_profile_canary_preflight.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    proposal_registered_profile_canary_preflight.add_argument(
        "--force",
        action="store_true",
    )
    proposal_registered_profile_canary_preflight.add_argument(
        "--json",
        action="store_true",
    )
    proposal_registered_profile_canary_execution = proposal_commands.add_parser(
        "run-registered-profile-canary-execution",
        help="Run explicit registered profile canary execution after dev hard-gate",
    )
    proposal_registered_profile_canary_execution.add_argument(
        "--registered-profile-execution-run",
        type=Path,
        required=True,
    )
    proposal_registered_profile_canary_execution.add_argument(
        "--registered-profile",
        type=Path,
    )
    proposal_registered_profile_canary_execution.add_argument(
        "--execute-canary",
        action="store_true",
    )
    proposal_registered_profile_canary_execution.add_argument(
        "--canary-rows",
        type=Path,
    )
    proposal_registered_profile_canary_execution.add_argument(
        "--model-runtime-preflight",
        type=Path,
    )
    proposal_registered_profile_canary_execution.add_argument(
        "--model-eval-model",
        default="qwen/qwen3-8b",
    )
    proposal_registered_profile_canary_execution.add_argument(
        "--model-eval-base-url",
        default="http://127.0.0.1:1234/v1",
    )
    proposal_registered_profile_canary_execution.add_argument(
        "--model-eval-model-provider",
        default="openai-compatible",
        choices=["openai-compatible", "deepseek"],
    )
    proposal_registered_profile_canary_execution.add_argument(
        "--model-eval-api-key-env"
    )
    proposal_registered_profile_canary_execution.add_argument(
        "--model-eval-timeout-seconds",
        type=int,
        default=120,
    )
    proposal_registered_profile_canary_execution.add_argument(
        "--model-eval-temperature",
        type=float,
        default=0.0,
    )
    proposal_registered_profile_canary_execution.add_argument(
        "--model-eval-max-tokens",
        type=int,
        default=512,
    )
    proposal_registered_profile_canary_execution.add_argument(
        "--model-eval-judge-mode",
        default="heuristic",
        choices=["heuristic", "openai-compatible"],
    )
    proposal_registered_profile_canary_execution.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )
    proposal_registered_profile_canary_execution.add_argument(
        "--force",
        action="store_true",
    )
    proposal_registered_profile_canary_execution.add_argument(
        "--json",
        action="store_true",
    )
    proposal_registered_profile_canary_result_gate = proposal_commands.add_parser(
        "build-registered-profile-canary-result-gate",
        help="Build a non-executing registered profile canary result gate",
    )
    proposal_registered_profile_canary_result_gate.add_argument(
        "--registered-profile-canary-execution",
        type=Path,
        required=True,
    )
    proposal_registered_profile_canary_result_gate.add_argument(
        "--min-canary-row-count",
        type=int,
        default=1,
    )
    proposal_registered_profile_canary_result_gate.add_argument(
        "--max-failure-count",
        type=int,
        default=0,
    )
    proposal_registered_profile_canary_result_gate.add_argument(
        "--max-runtime-error-count",
        type=int,
        default=0,
    )
    proposal_registered_profile_canary_result_gate.add_argument(
        "--max-empty-output-count",
        type=int,
        default=0,
    )
    proposal_registered_profile_canary_result_gate.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    proposal_registered_profile_canary_result_gate.add_argument(
        "--force",
        action="store_true",
    )
    proposal_registered_profile_canary_result_gate.add_argument(
        "--json",
        action="store_true",
    )
    proposal_registered_profile_outcome_schedule = proposal_commands.add_parser(
        "build-registered-profile-outcome-schedule",
        help="Build a non-executing registered profile outcome schedule",
    )
    proposal_registered_profile_outcome_schedule.add_argument(
        "--registered-profile-canary-result-gate",
        type=Path,
        required=True,
    )
    proposal_registered_profile_outcome_schedule.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    proposal_registered_profile_outcome_schedule.add_argument(
        "--force",
        action="store_true",
    )
    proposal_registered_profile_outcome_schedule.add_argument(
        "--json",
        action="store_true",
    )
    proposal_optimizer_gate_scheduler_plan = proposal_commands.add_parser(
        "build-optimizer-gate-scheduler-plan",
        help="Build a non-executing optimizer/gate scheduler plan",
    )
    proposal_optimizer_gate_scheduler_plan.add_argument(
        "--registered-profile-outcome-schedule",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_scheduler_plan.add_argument(
        "--model-runtime-preflight",
        type=Path,
    )
    proposal_optimizer_gate_scheduler_plan.add_argument(
        "--slice-optimizer-selection",
        type=Path,
    )
    proposal_optimizer_gate_scheduler_plan.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_scheduler_plan.add_argument(
        "--force",
        action="store_true",
    )
    proposal_optimizer_gate_scheduler_plan.add_argument(
        "--json",
        action="store_true",
    )
    proposal_optimizer_gate_scheduler_action = proposal_commands.add_parser(
        "run-optimizer-gate-scheduler-action",
        help="Run one explicit safe planning action from an optimizer/gate scheduler plan",
    )
    proposal_optimizer_gate_scheduler_action.add_argument(
        "--optimizer-gate-scheduler-plan",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_scheduler_action.add_argument("--action-name")
    proposal_optimizer_gate_scheduler_action.add_argument("--model")
    proposal_optimizer_gate_scheduler_action.add_argument("--base-url")
    proposal_optimizer_gate_scheduler_action.add_argument(
        "--model-provider",
        default="openai-compatible",
        choices=["openai-compatible", "deepseek"],
    )
    proposal_optimizer_gate_scheduler_action.add_argument("--api-key-env")
    proposal_optimizer_gate_scheduler_action.add_argument(
        "--execute-probe",
        action="store_true",
    )
    proposal_optimizer_gate_scheduler_action.add_argument(
        "--timeout-seconds",
        type=int,
        default=30,
    )
    proposal_optimizer_gate_scheduler_action.add_argument(
        "--max-tokens",
        type=int,
        default=512,
    )
    proposal_optimizer_gate_scheduler_action.add_argument(
        "--no-apply-no-think",
        dest="apply_no_think",
        action="store_false",
    )
    proposal_optimizer_gate_scheduler_action.set_defaults(apply_no_think=True)
    proposal_optimizer_gate_scheduler_action.add_argument("--context", type=Path)
    proposal_optimizer_gate_scheduler_action.add_argument(
        "--plugin-manifest",
        type=Path,
        action="append",
        default=[],
    )
    proposal_optimizer_gate_scheduler_action.add_argument(
        "--max-candidates",
        type=int,
        default=1,
    )
    proposal_optimizer_gate_scheduler_action.add_argument(
        "--experiment-action-allowlist",
        action="append",
        default=[],
    )
    proposal_optimizer_gate_scheduler_action.add_argument(
        "--experiment-max-actions",
        type=int,
    )
    proposal_optimizer_gate_scheduler_action.add_argument(
        "--canary-runner-bundle",
        type=Path,
    )
    proposal_optimizer_gate_scheduler_action.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_scheduler_action.add_argument(
        "--force",
        action="store_true",
    )
    proposal_optimizer_gate_scheduler_action.add_argument(
        "--json",
        action="store_true",
    )
    proposal_optimizer_gate_scheduler_loop = proposal_commands.add_parser(
        "run-optimizer-gate-scheduler-loop",
        help="Run safe scheduler planning actions until refresh or manual review is required",
    )
    proposal_optimizer_gate_scheduler_loop.add_argument(
        "--optimizer-gate-scheduler-plan",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_scheduler_loop.add_argument("--model")
    proposal_optimizer_gate_scheduler_loop.add_argument("--base-url")
    proposal_optimizer_gate_scheduler_loop.add_argument(
        "--model-provider",
        default="openai-compatible",
        choices=["openai-compatible", "deepseek"],
    )
    proposal_optimizer_gate_scheduler_loop.add_argument("--api-key-env")
    proposal_optimizer_gate_scheduler_loop.add_argument(
        "--execute-probe",
        action="store_true",
    )
    proposal_optimizer_gate_scheduler_loop.add_argument(
        "--timeout-seconds",
        type=int,
        default=30,
    )
    proposal_optimizer_gate_scheduler_loop.add_argument(
        "--max-tokens",
        type=int,
        default=512,
    )
    proposal_optimizer_gate_scheduler_loop.add_argument(
        "--no-apply-no-think",
        dest="apply_no_think",
        action="store_false",
    )
    proposal_optimizer_gate_scheduler_loop.set_defaults(apply_no_think=True)
    proposal_optimizer_gate_scheduler_loop.add_argument("--context", type=Path)
    proposal_optimizer_gate_scheduler_loop.add_argument(
        "--plugin-manifest",
        type=Path,
        action="append",
        default=[],
    )
    proposal_optimizer_gate_scheduler_loop.add_argument(
        "--max-candidates",
        type=int,
        default=1,
    )
    proposal_optimizer_gate_scheduler_loop.add_argument(
        "--max-actions",
        type=int,
        default=3,
    )
    proposal_optimizer_gate_scheduler_loop.add_argument(
        "--auto-refresh-scheduler-plan",
        action="store_true",
    )
    proposal_optimizer_gate_scheduler_loop.add_argument(
        "--experiment-action-allowlist",
        action="append",
        default=[],
    )
    proposal_optimizer_gate_scheduler_loop.add_argument(
        "--experiment-max-actions",
        type=int,
    )
    proposal_optimizer_gate_scheduler_loop.add_argument(
        "--canary-runner-bundle",
        type=Path,
    )
    proposal_optimizer_gate_scheduler_loop.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_scheduler_loop.add_argument(
        "--force",
        action="store_true",
    )
    proposal_optimizer_gate_scheduler_loop.add_argument(
        "--json",
        action="store_true",
    )
    proposal_optimizer_gate_scheduler_handoff = proposal_commands.add_parser(
        "build-optimizer-gate-scheduler-handoff",
        help="Build a non-executing handoff from optimizer/gate scheduler loop output",
    )
    proposal_optimizer_gate_scheduler_handoff.add_argument(
        "--optimizer-gate-scheduler-loop",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_scheduler_handoff.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_scheduler_handoff.add_argument(
        "--force",
        action="store_true",
    )
    proposal_optimizer_gate_scheduler_handoff.add_argument(
        "--json",
        action="store_true",
    )
    proposal_optimizer_gate_canary_runner_bundle = proposal_commands.add_parser(
        "build-optimizer-gate-canary-runner-bundle",
        help="Build a non-executing explicit canary runner bundle from scheduler handoff",
    )
    proposal_optimizer_gate_canary_runner_bundle.add_argument(
        "--optimizer-gate-scheduler-handoff",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_canary_runner_bundle.add_argument(
        "--registered-profile-execution-run",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_canary_runner_bundle.add_argument(
        "--registered-profile",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_canary_runner_bundle.add_argument(
        "--canary-rows",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_canary_runner_bundle.add_argument(
        "--model-runtime-preflight",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_canary_runner_bundle.add_argument(
        "--no-execute-canary-flag",
        action="store_true",
        help="Build a blocked bundle without the explicit canary execution flag",
    )
    proposal_optimizer_gate_canary_runner_bundle.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_canary_runner_bundle.add_argument(
        "--force",
        action="store_true",
    )
    proposal_optimizer_gate_canary_runner_bundle.add_argument(
        "--json",
        action="store_true",
    )
    proposal_optimizer_gate_canary_runner_execution = proposal_commands.add_parser(
        "run-optimizer-gate-canary-runner-bundle",
        help="Run an explicit canary runner from a replayable optimizer/gate bundle",
    )
    proposal_optimizer_gate_canary_runner_execution.add_argument(
        "--optimizer-gate-canary-runner-bundle",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_canary_runner_execution.add_argument(
        "--model",
        default="qwen/qwen3-8b",
    )
    proposal_optimizer_gate_canary_runner_execution.add_argument(
        "--base-url",
        default="http://127.0.0.1:1234/v1",
    )
    proposal_optimizer_gate_canary_runner_execution.add_argument(
        "--model-provider",
        default="openai-compatible",
        choices=["openai-compatible", "deepseek"],
    )
    proposal_optimizer_gate_canary_runner_execution.add_argument("--api-key-env")
    proposal_optimizer_gate_canary_runner_execution.add_argument(
        "--timeout-seconds",
        type=int,
        default=120,
    )
    proposal_optimizer_gate_canary_runner_execution.add_argument(
        "--temperature",
        type=float,
        default=0.0,
    )
    proposal_optimizer_gate_canary_runner_execution.add_argument(
        "--max-tokens",
        type=int,
        default=512,
    )
    proposal_optimizer_gate_canary_runner_execution.add_argument(
        "--judge-mode",
        default="heuristic",
        choices=["heuristic", "exact"],
    )
    proposal_optimizer_gate_canary_runner_execution.add_argument(
        "--min-canary-row-count",
        type=int,
        default=1,
    )
    proposal_optimizer_gate_canary_runner_execution.add_argument(
        "--max-failure-count",
        type=int,
        default=0,
    )
    proposal_optimizer_gate_canary_runner_execution.add_argument(
        "--max-runtime-error-count",
        type=int,
        default=0,
    )
    proposal_optimizer_gate_canary_runner_execution.add_argument(
        "--max-empty-output-count",
        type=int,
        default=0,
    )
    proposal_optimizer_gate_canary_runner_execution.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_canary_runner_execution.add_argument(
        "--force",
        action="store_true",
    )
    proposal_optimizer_gate_canary_runner_execution.add_argument(
        "--json",
        action="store_true",
    )
    proposal_optimizer_gate_promotion_review_queue = proposal_commands.add_parser(
        "build-optimizer-gate-promotion-review-queue",
        help="Build a non-executing human promotion review queue from scheduler handoff",
    )
    proposal_optimizer_gate_promotion_review_queue.add_argument(
        "--optimizer-gate-scheduler-handoff",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_promotion_review_queue.add_argument(
        "--canary-result-gate",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_promotion_review_queue.add_argument(
        "--promotion-policy",
        type=Path,
    )
    proposal_optimizer_gate_promotion_review_queue.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_promotion_review_queue.add_argument(
        "--force",
        action="store_true",
    )
    proposal_optimizer_gate_promotion_review_queue.add_argument(
        "--json",
        action="store_true",
    )
    proposal_optimizer_gate_human_promotion_approval = proposal_commands.add_parser(
        "build-optimizer-gate-human-promotion-approval",
        help="Record a human promotion review decision without executing promotion",
    )
    proposal_optimizer_gate_human_promotion_approval.add_argument(
        "--promotion-review-queue",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_human_promotion_approval.add_argument(
        "--decision",
        choices=["approve", "reject"],
        required=True,
    )
    proposal_optimizer_gate_human_promotion_approval.add_argument(
        "--approved-by",
        required=True,
    )
    proposal_optimizer_gate_human_promotion_approval.add_argument("--reviewed-at")
    proposal_optimizer_gate_human_promotion_approval.add_argument("--decision-notes")
    proposal_optimizer_gate_human_promotion_approval.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_human_promotion_approval.add_argument(
        "--force",
        action="store_true",
    )
    proposal_optimizer_gate_human_promotion_approval.add_argument(
        "--json",
        action="store_true",
    )
    proposal_optimizer_gate_local_promotion_action = proposal_commands.add_parser(
        "run-optimizer-gate-local-promotion-action",
        help="Record an explicit local promotion action after human approval",
    )
    proposal_optimizer_gate_local_promotion_action.add_argument(
        "--human-promotion-approval",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_local_promotion_action.add_argument(
        "--execute-promotion",
        action="store_true",
    )
    proposal_optimizer_gate_local_promotion_action.add_argument("--promoted-by")
    proposal_optimizer_gate_local_promotion_action.add_argument("--promoted-at")
    proposal_optimizer_gate_local_promotion_action.add_argument(
        "--profile-registry",
        type=Path,
    )
    proposal_optimizer_gate_local_promotion_action.add_argument(
        "--registry-output",
        type=Path,
    )
    proposal_optimizer_gate_local_promotion_action.add_argument(
        "--rollback-output",
        type=Path,
    )
    proposal_optimizer_gate_local_promotion_action.add_argument(
        "--audit-log",
        type=Path,
    )
    proposal_optimizer_gate_local_promotion_action.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_local_promotion_action.add_argument(
        "--force",
        action="store_true",
    )
    proposal_optimizer_gate_local_promotion_action.add_argument(
        "--json",
        action="store_true",
    )
    proposal_optimizer_gate_local_promotion_rollback = proposal_commands.add_parser(
        "run-optimizer-gate-local-promotion-rollback",
        help="Restore a local optimizer/gate profile registry from a rollback artifact",
    )
    proposal_optimizer_gate_local_promotion_rollback.add_argument(
        "--rollback-record",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_local_promotion_rollback.add_argument("--rolled-back-by")
    proposal_optimizer_gate_local_promotion_rollback.add_argument("--rolled-back-at")
    proposal_optimizer_gate_local_promotion_rollback.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_local_promotion_rollback.add_argument(
        "--force",
        action="store_true",
    )
    proposal_optimizer_gate_local_promotion_rollback.add_argument(
        "--json",
        action="store_true",
    )
    proposal_optimizer_gate_external_submission = proposal_commands.add_parser(
        "run-optimizer-gate-external-submission-action",
        help="Execute an explicit optimizer/gate external benchmark submission action",
    )
    proposal_optimizer_gate_external_submission.add_argument(
        "--local-promotion-action",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_external_submission.add_argument("--benchmark-id", required=True)
    proposal_optimizer_gate_external_submission.add_argument("--submission-url", required=True)
    proposal_optimizer_gate_external_submission.add_argument(
        "--submission-payload",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_external_submission.add_argument("--submitted-by", required=True)
    proposal_optimizer_gate_external_submission.add_argument(
        "--execute-submission",
        action="store_true",
    )
    proposal_optimizer_gate_external_submission.add_argument(
        "--timeout-seconds",
        type=int,
        default=30,
    )
    proposal_optimizer_gate_external_submission.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_external_submission.add_argument(
        "--force",
        action="store_true",
    )
    proposal_optimizer_gate_external_submission.add_argument("--json", action="store_true")
    proposal_optimizer_gate_official_submission = proposal_commands.add_parser(
        "build-optimizer-gate-official-submission",
        help="Record an explicit optimizer/gate official submission boundary artifact",
    )
    proposal_optimizer_gate_official_submission.add_argument(
        "--local-promotion-action",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_official_submission.add_argument("--benchmark-id", required=True)
    proposal_optimizer_gate_official_submission.add_argument("--submission-id", required=True)
    proposal_optimizer_gate_official_submission.add_argument("--public-url", required=True)
    proposal_optimizer_gate_official_submission.add_argument("--submitted-by", required=True)
    proposal_optimizer_gate_official_submission.add_argument("--submitted-at")
    proposal_optimizer_gate_official_submission.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_official_submission.add_argument(
        "--force",
        action="store_true",
    )
    proposal_optimizer_gate_official_submission.add_argument("--json", action="store_true")
    proposal_optimizer_gate_public_result_fetch = proposal_commands.add_parser(
        "fetch-optimizer-gate-public-result",
        help="Fetch and parse an optimizer/gate public result from a URL",
    )
    proposal_optimizer_gate_public_result_fetch.add_argument(
        "--public-result-url",
        required=True,
    )
    proposal_optimizer_gate_public_result_fetch.add_argument(
        "--timeout-seconds",
        type=int,
        default=30,
    )
    proposal_optimizer_gate_public_result_fetch.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_public_result_fetch.add_argument(
        "--force",
        action="store_true",
    )
    proposal_optimizer_gate_public_result_fetch.add_argument("--json", action="store_true")
    proposal_optimizer_gate_public_result_verifier = proposal_commands.add_parser(
        "verify-optimizer-gate-public-result",
        help="Verify a public result before building an official claim artifact",
    )
    proposal_optimizer_gate_public_result_verifier.add_argument(
        "--official-submission",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_public_result_verifier.add_argument(
        "--public-result",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_public_result_verifier.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_public_result_verifier.add_argument(
        "--force",
        action="store_true",
    )
    proposal_optimizer_gate_public_result_verifier.add_argument("--json", action="store_true")
    proposal_optimizer_gate_official_claim = proposal_commands.add_parser(
        "build-optimizer-gate-official-claim",
        help="Build the official claim artifact from a verified public result",
    )
    proposal_optimizer_gate_official_claim.add_argument(
        "--public-result-verifier",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_official_claim.add_argument("--claim-id", required=True)
    proposal_optimizer_gate_official_claim.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_official_claim.add_argument("--force", action="store_true")
    proposal_optimizer_gate_official_claim.add_argument("--json", action="store_true")
    proposal_optimizer_gate_executable_loop = proposal_commands.add_parser(
        "run-optimizer-gate-executable-loop",
        help="Run a bounded executable optimizer/gate loop from a canary result gate",
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--canary-result-gate",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--slice-repair-context",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--candidate-optimizer",
        action="append",
        default=[],
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--plugin-manifest",
        type=Path,
        action="append",
        default=[],
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--base-profile-id",
        default="p3-dev-v2",
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--proposed-profile-prefix",
        default="optimizer-gate-loop-profile",
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--max-iterations",
        type=int,
        default=1,
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--max-candidates",
        type=int,
        default=1,
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--execute-optimizer",
        action="store_true",
    )
    proposal_optimizer_gate_executable_loop.add_argument("--optimizer-model")
    proposal_optimizer_gate_executable_loop.add_argument("--optimizer-base-url")
    proposal_optimizer_gate_executable_loop.add_argument("--optimizer-api-key")
    proposal_optimizer_gate_executable_loop.add_argument(
        "--optimizer-timeout-seconds",
        type=int,
        default=30,
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--optimizer-temperature",
        type=float,
        default=0.0,
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--optimizer-max-tokens",
        type=int,
        default=512,
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--auto-approve-registration",
        action="store_true",
    )
    proposal_optimizer_gate_executable_loop.add_argument("--approved-by")
    proposal_optimizer_gate_executable_loop.add_argument(
        "--prompt-leakage-rows",
        type=Path,
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--prompt-leakage-audit",
        type=Path,
    )
    proposal_optimizer_gate_executable_loop.add_argument("--target-smoke", type=Path)
    proposal_optimizer_gate_executable_loop.add_argument("--dev-model-eval", type=Path)
    proposal_optimizer_gate_executable_loop.add_argument("--dev-baseline-eval", type=Path)
    proposal_optimizer_gate_executable_loop.add_argument("--dev-gate-source", type=Path)
    proposal_optimizer_gate_executable_loop.add_argument(
        "--model-runtime-preflight",
        type=Path,
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--execute-model-eval",
        action="store_true",
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--target-smoke-rows",
        type=Path,
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--dev-model-eval-rows",
        type=Path,
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--execute-canary-runner",
        action="store_true",
    )
    proposal_optimizer_gate_executable_loop.add_argument("--canary-rows", type=Path)
    proposal_optimizer_gate_executable_loop.add_argument(
        "--min-canary-row-count",
        type=int,
        default=1,
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--max-canary-failure-count",
        type=int,
        default=0,
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--max-canary-runtime-error-count",
        type=int,
        default=0,
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--max-canary-empty-output-count",
        type=int,
        default=0,
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--model-eval-model",
        default="qwen/qwen3-8b",
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--model-eval-base-url",
        default="http://127.0.0.1:1234/v1",
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--model-eval-model-provider",
        default="openai-compatible",
        choices=["openai-compatible", "deepseek"],
    )
    proposal_optimizer_gate_executable_loop.add_argument("--model-eval-api-key-env")
    proposal_optimizer_gate_executable_loop.add_argument(
        "--model-eval-timeout-seconds",
        type=int,
        default=120,
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--model-eval-temperature",
        type=float,
        default=0.0,
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--model-eval-max-tokens",
        type=int,
        default=512,
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--model-eval-judge-mode",
        default="heuristic",
        choices=["heuristic", "exact"],
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--force",
        action="store_true",
    )
    proposal_optimizer_gate_executable_loop.add_argument(
        "--json",
        action="store_true",
    )
    proposal_model_runtime_preflight = proposal_commands.add_parser(
        "build-model-runtime-preflight",
        help="Build a guarded model runtime preflight before target/dev/canary eval",
    )
    proposal_model_runtime_preflight.add_argument("--model", required=True)
    proposal_model_runtime_preflight.add_argument("--base-url", required=True)
    proposal_model_runtime_preflight.add_argument(
        "--model-provider",
        default="openai-compatible",
        choices=["openai-compatible", "deepseek"],
    )
    proposal_model_runtime_preflight.add_argument("--api-key-env")
    proposal_model_runtime_preflight.add_argument(
        "--execute-probe",
        action="store_true",
    )
    proposal_model_runtime_preflight.add_argument(
        "--timeout-seconds",
        type=int,
        default=30,
    )
    proposal_model_runtime_preflight.add_argument(
        "--temperature",
        type=float,
        default=0.0,
    )
    proposal_model_runtime_preflight.add_argument(
        "--max-tokens",
        type=int,
        default=512,
    )
    proposal_model_runtime_preflight.add_argument(
        "--min-max-tokens",
        type=int,
        default=32,
    )
    proposal_model_runtime_preflight.add_argument(
        "--no-apply-no-think",
        dest="apply_no_think",
        action="store_false",
    )
    proposal_model_runtime_preflight.set_defaults(apply_no_think=True)
    proposal_model_runtime_preflight.add_argument(
        "--probe-prompt",
        default='Return compact JSON exactly as {"ok": true}.',
    )
    proposal_model_runtime_preflight.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    proposal_model_runtime_preflight.add_argument(
        "--force",
        action="store_true",
    )
    proposal_model_runtime_preflight.add_argument(
        "--json",
        action="store_true",
    )
    proposal_optimizer_gate_spec = proposal_commands.add_parser(
        "build-optimizer-gate-system-spec",
        help="Build a non-executing optimizer/gate system registry",
    )
    proposal_optimizer_gate_spec.add_argument(
        "--plugin-manifest",
        type=Path,
        action="append",
    )
    proposal_optimizer_gate_spec.add_argument("--output", type=Path, required=True)
    proposal_optimizer_gate_spec.add_argument("--force", action="store_true")
    proposal_optimizer_gate_spec.add_argument("--json", action="store_true")
    proposal_gate_policy_input = proposal_commands.add_parser(
        "build-gate-policy-input",
        help="Build a benchmark-agnostic gate policy input from metric and slice tables",
    )
    proposal_gate_policy_input.add_argument("--metric-table", type=Path, required=True)
    proposal_gate_policy_input.add_argument("--slice-table", type=Path, required=True)
    proposal_gate_policy_input.add_argument("--policy-id", default="slice-dev-hard-gate")
    proposal_gate_policy_input.add_argument("--task-family", default="generic_gate_policy")
    proposal_gate_policy_input.add_argument("--split", default="dev")
    proposal_gate_policy_input.add_argument("--quality-constraints", type=Path)
    proposal_gate_policy_input.add_argument("--execution-quality", type=Path)
    proposal_gate_policy_input.add_argument("--output", type=Path, required=True)
    proposal_gate_policy_input.add_argument("--force", action="store_true")
    proposal_gate_policy_input.add_argument("--json", action="store_true")
    proposal_gate_policy_decision = proposal_commands.add_parser(
        "evaluate-gate-policy",
        help="Evaluate a benchmark-agnostic gate policy input",
    )
    proposal_gate_policy_decision.add_argument("--gate-input", type=Path, required=True)
    proposal_gate_policy_decision.add_argument("--output", type=Path, required=True)
    proposal_gate_policy_decision.add_argument("--force", action="store_true")
    proposal_gate_policy_decision.add_argument("--json", action="store_true")
    proposal_gate_policy_composition = proposal_commands.add_parser(
        "build-gate-policy-composition",
        help="Compose gate policy decisions into one hard-gate result",
    )
    proposal_gate_policy_composition.add_argument(
        "--decision",
        type=Path,
        action="append",
        required=True,
    )
    proposal_gate_policy_composition.add_argument(
        "--composition-id",
        default="optimizer-gate-hard-composition",
    )
    proposal_gate_policy_composition.add_argument("--output", type=Path, required=True)
    proposal_gate_policy_composition.add_argument("--force", action="store_true")
    proposal_gate_policy_composition.add_argument("--json", action="store_true")
    proposal_gate_policy_graph = proposal_commands.add_parser(
        "build-gate-policy-graph",
        help="Build a configurable non-executing gate policy graph",
    )
    proposal_gate_policy_graph.add_argument(
        "--graph-id",
        default="optimizer-gate-policy-graph",
    )
    proposal_gate_policy_graph.add_argument(
        "--required-policy",
        action="append",
    )
    proposal_gate_policy_graph.add_argument(
        "--optional-policy",
        action="append",
    )
    proposal_gate_policy_graph.add_argument("--output", type=Path, required=True)
    proposal_gate_policy_graph.add_argument("--force", action="store_true")
    proposal_gate_policy_graph.add_argument("--json", action="store_true")
    proposal_gate_policy_graph_decision = proposal_commands.add_parser(
        "evaluate-gate-policy-graph",
        help="Evaluate gate decisions through a configurable policy graph",
    )
    proposal_gate_policy_graph_decision.add_argument(
        "--policy-graph",
        type=Path,
        required=True,
    )
    proposal_gate_policy_graph_decision.add_argument(
        "--decision",
        type=Path,
        action="append",
        required=True,
    )
    proposal_gate_policy_graph_decision.add_argument("--output", type=Path, required=True)
    proposal_gate_policy_graph_decision.add_argument("--force", action="store_true")
    proposal_gate_policy_graph_decision.add_argument("--json", action="store_true")
    proposal_slice_gate = proposal_commands.add_parser(
        "evaluate-slice-gate",
        help="Evaluate a dev-first slice gate without executing experiments",
    )
    proposal_slice_gate.add_argument("--slice-matrix", type=Path)
    proposal_slice_gate.add_argument("--baseline-report", type=Path)
    proposal_slice_gate.add_argument("--candidate-report", type=Path)
    proposal_slice_gate.add_argument("--candidate-evaluation", type=Path)
    proposal_slice_gate.add_argument("--output", type=Path, required=True)
    proposal_slice_gate.add_argument("--force", action="store_true")
    proposal_slice_gate.add_argument("--json", action="store_true")
    proposal_slice_variance_gate = proposal_commands.add_parser(
        "evaluate-slice-variance-gate",
        help="Evaluate paired-repeat slice variance before choosing optimizer targets",
    )
    proposal_slice_variance_gate.add_argument(
        "--slice-matrix",
        type=Path,
        action="append",
    )
    proposal_slice_variance_gate.add_argument("--paired-repeat-manifest", type=Path)
    proposal_slice_variance_gate.add_argument("--output", type=Path, required=True)
    proposal_slice_variance_gate.add_argument("--min-repeats", type=int, default=2)
    proposal_slice_variance_gate.add_argument(
        "--regression-delta-threshold",
        type=float,
        default=-1.0,
    )
    proposal_slice_variance_gate.add_argument(
        "--stable-support-ratio",
        type=float,
        default=1.0,
    )
    proposal_slice_variance_gate.add_argument("--force", action="store_true")
    proposal_slice_variance_gate.add_argument("--json", action="store_true")
    proposal_paired_repeat_manifest = proposal_commands.add_parser(
        "build-paired-repeat-manifest",
        help="Build an auditable paired-repeat manifest from slice matrices",
    )
    proposal_paired_repeat_manifest.add_argument(
        "--slice-matrix",
        type=Path,
        action="append",
        required=True,
    )
    proposal_paired_repeat_manifest.add_argument(
        "--task-family",
        default="generic_paired_repeat",
    )
    proposal_paired_repeat_manifest.add_argument("--output", type=Path, required=True)
    proposal_paired_repeat_manifest.add_argument("--force", action="store_true")
    proposal_paired_repeat_manifest.add_argument("--json", action="store_true")
    proposal_slice_patch_outcome = proposal_commands.add_parser(
        "record-slice-patch-outcome",
        help="Record a slice patch outcome from candidate, materialization, and gate decision",
    )
    proposal_slice_patch_outcome.add_argument("--candidate", type=Path, required=True)
    proposal_slice_patch_outcome.add_argument("--materialization", type=Path, required=True)
    proposal_slice_patch_outcome.add_argument("--gate-decision", type=Path, required=True)
    proposal_slice_patch_outcome.add_argument("--output", type=Path, required=True)
    proposal_slice_patch_outcome.add_argument("--force", action="store_true")
    proposal_slice_patch_outcome.add_argument("--json", action="store_true")
    proposal_slice_optimizer_selection = proposal_commands.add_parser(
        "build-slice-optimizer-selection",
        help="Select an optimizer adapter from prior slice patch outcomes",
    )
    proposal_slice_optimizer_selection.add_argument("--outcomes", type=Path, required=True)
    proposal_slice_optimizer_selection.add_argument("--target-scope", required=True)
    proposal_slice_optimizer_selection.add_argument(
        "--failure-label",
        action="append",
        default=[],
    )
    proposal_slice_optimizer_selection.add_argument(
        "--candidate-optimizer",
        action="append",
        default=[],
    )
    proposal_slice_optimizer_selection.add_argument("--output", type=Path, required=True)
    proposal_slice_optimizer_selection.add_argument("--force", action="store_true")
    proposal_slice_optimizer_selection.add_argument("--json", action="store_true")
    proposal_cp_bench_bundle = proposal_commands.add_parser(
        "build-cp-bench-effectiveness-bundle",
        help="Build control/treatment/effectiveness artifacts from CP-Bench candidate round reports",
    )
    proposal_cp_bench_bundle.add_argument(
        "--round-report",
        type=Path,
        action="append",
        required=True,
    )
    proposal_cp_bench_bundle.add_argument("--output-dir", type=Path, required=True)
    proposal_cp_bench_bundle.add_argument(
        "--control-label",
        default="without_failure_driven_context",
    )
    proposal_cp_bench_bundle.add_argument(
        "--treatment-label",
        default="with_failure_driven_context",
    )
    proposal_cp_bench_bundle.add_argument("--force", action="store_true")
    proposal_cp_bench_bundle.add_argument("--json", action="store_true")
    proposal_fasttext_bundle = proposal_commands.add_parser(
        "build-fasttext-effectiveness-bundle",
        help="Build control/treatment/effectiveness artifacts from fastText multi-round reports",
    )
    proposal_fasttext_bundle.add_argument(
        "--multi-round-report",
        type=Path,
        action="append",
        required=True,
    )
    proposal_fasttext_bundle.add_argument("--output-dir", type=Path, required=True)
    proposal_fasttext_bundle.add_argument(
        "--control-label",
        default="without_failure_driven_context",
    )
    proposal_fasttext_bundle.add_argument(
        "--treatment-label",
        default="with_failure_driven_context",
    )
    proposal_fasttext_bundle.add_argument(
        "--completed-only",
        action="store_true",
        help="Exclude failed or non-executed rounds from the effectiveness arms",
    )
    proposal_fasttext_bundle.add_argument("--force", action="store_true")
    proposal_fasttext_bundle.add_argument("--json", action="store_true")
    proposal_smol_worldcup_bundle = proposal_commands.add_parser(
        "build-smol-worldcup-effectiveness-bundle",
        help=(
            "Build control/treatment/effectiveness artifacts from paired Smol WorldCup "
            "prompt-profile reports"
        ),
    )
    proposal_smol_worldcup_bundle.add_argument(
        "--control-report",
        type=Path,
        action="append",
        required=True,
    )
    proposal_smol_worldcup_bundle.add_argument(
        "--treatment-report",
        type=Path,
        action="append",
        required=True,
    )
    proposal_smol_worldcup_bundle.add_argument("--output-dir", type=Path, required=True)
    proposal_smol_worldcup_bundle.add_argument(
        "--control-label",
        default="without_failure_driven_context",
    )
    proposal_smol_worldcup_bundle.add_argument(
        "--treatment-label",
        default="with_failure_driven_context",
    )
    proposal_smol_worldcup_bundle.add_argument(
        "--split-filter",
        choices=["dev", "canary"],
        help="Restrict the bundle to one Smol WorldCup evaluation split",
    )
    proposal_smol_worldcup_bundle.add_argument("--force", action="store_true")
    proposal_smol_worldcup_bundle.add_argument("--json", action="store_true")
    proposal_smol_worldcup_result_analysis = proposal_commands.add_parser(
        "build-smol-worldcup-result-analysis",
        help=(
            "Analyze paired Smol WorldCup control/treatment results before changing prompts "
            "or launching another optimizer round"
        ),
    )
    proposal_smol_worldcup_result_analysis.add_argument(
        "--control-report",
        type=Path,
        action="append",
        required=True,
    )
    proposal_smol_worldcup_result_analysis.add_argument(
        "--treatment-report",
        type=Path,
        action="append",
        required=True,
    )
    proposal_smol_worldcup_result_analysis.add_argument("--output-dir", type=Path, required=True)
    proposal_smol_worldcup_result_analysis.add_argument(
        "--split-filter",
        choices=["dev", "canary"],
        help="Restrict result analysis to one Smol WorldCup evaluation split",
    )
    proposal_smol_worldcup_result_analysis.add_argument("--force", action="store_true")
    proposal_smol_worldcup_result_analysis.add_argument("--json", action="store_true")
    proposal_smol_worldcup_confidence_variance_gate = proposal_commands.add_parser(
        "build-smol-worldcup-confidence-variance-gate",
        help=(
            "Gate Smol WorldCup confidence-row regression attribution against A/A "
            "variance evidence"
        ),
    )
    proposal_smol_worldcup_confidence_variance_gate.add_argument(
        "--aa-result-analysis",
        type=Path,
        required=True,
    )
    proposal_smol_worldcup_confidence_variance_gate.add_argument(
        "--candidate-result-analysis",
        type=Path,
        action="append",
        required=True,
    )
    proposal_smol_worldcup_confidence_variance_gate.add_argument("--output", type=Path, required=True)
    proposal_smol_worldcup_confidence_variance_gate.add_argument(
        "--confidence-category",
        default="confidence_calibration",
    )
    proposal_smol_worldcup_confidence_variance_gate.add_argument(
        "--min-abs-score-delta",
        type=float,
        default=1.0,
    )
    proposal_smol_worldcup_confidence_variance_gate.add_argument(
        "--aa-coverage-ratio",
        type=float,
        default=1.0,
    )
    proposal_smol_worldcup_confidence_variance_gate.add_argument("--force", action="store_true")
    proposal_smol_worldcup_confidence_variance_gate.add_argument("--json", action="store_true")
    proposal_smol_worldcup_cached_confidence_scoring_gate = proposal_commands.add_parser(
        "build-smol-worldcup-cached-confidence-scoring-gate",
        help=(
            "Gate Smol WorldCup confidence-row prompt repair on response cache and "
            "deterministic scoring evidence"
        ),
    )
    proposal_smol_worldcup_cached_confidence_scoring_gate.add_argument(
        "--model-eval-report",
        type=Path,
        action="append",
        required=True,
    )
    proposal_smol_worldcup_cached_confidence_scoring_gate.add_argument(
        "--output",
        type=Path,
        required=True,
    )
    proposal_smol_worldcup_cached_confidence_scoring_gate.add_argument(
        "--confidence-category",
        default="confidence_calibration",
    )
    proposal_smol_worldcup_cached_confidence_scoring_gate.add_argument(
        "--min-repeats",
        type=int,
        default=2,
    )
    proposal_smol_worldcup_cached_confidence_scoring_gate.add_argument(
        "--max-score-range",
        type=float,
        default=0.0,
    )
    proposal_smol_worldcup_cached_confidence_scoring_gate.add_argument(
        "--force",
        action="store_true",
    )
    proposal_smol_worldcup_cached_confidence_scoring_gate.add_argument("--json", action="store_true")
    proposal_real_paper_bundle = proposal_commands.add_parser(
        "build-real-paper-effectiveness-bundle",
        help="Build control/treatment/effectiveness artifacts from real-paper public-slice proof archives",
    )
    proposal_real_paper_bundle.add_argument(
        "--proof-archive",
        type=Path,
        action="append",
        required=True,
    )
    proposal_real_paper_bundle.add_argument("--output-dir", type=Path, required=True)
    proposal_real_paper_bundle.add_argument(
        "--control-label",
        default="without_failure_driven_context",
    )
    proposal_real_paper_bundle.add_argument(
        "--treatment-label",
        default="with_failure_driven_context",
    )
    proposal_real_paper_bundle.add_argument("--force", action="store_true")
    proposal_real_paper_bundle.add_argument("--json", action="store_true")
    proposal_cross_task_summary = proposal_commands.add_parser(
        "build-cross-task-effectiveness-summary",
        help="Build a cross-task summary from multiple proposal effectiveness reports",
    )
    proposal_cross_task_summary.add_argument(
        "--effectiveness-report",
        type=Path,
        action="append",
        required=True,
    )
    proposal_cross_task_summary.add_argument("--output-dir", type=Path, required=True)
    proposal_cross_task_summary.add_argument("--force", action="store_true")
    proposal_cross_task_summary.add_argument("--json", action="store_true")
    proposal_claim_audit = proposal_commands.add_parser(
        "build-effectiveness-claim-audit",
        help="Build a bounded claim audit from a cross-task proposal effectiveness summary",
    )
    proposal_claim_audit.add_argument("--cross-task-summary", type=Path, required=True)
    proposal_claim_audit.add_argument("--output-dir", type=Path, required=True)
    proposal_claim_audit.add_argument("--min-task-count", type=int, default=3)
    proposal_claim_audit.add_argument(
        "--min-positive-task-families",
        type=int,
        default=2,
    )
    proposal_claim_audit.add_argument("--force", action="store_true")
    proposal_claim_audit.add_argument("--json", action="store_true")
    proposal_mixed_signal_audit = proposal_commands.add_parser(
        "build-mixed-signal-audit",
        help="Build a task-family audit for mixed-signal proposal effectiveness reports",
    )
    proposal_mixed_signal_audit.add_argument(
        "--effectiveness-report",
        type=Path,
        action="append",
        required=True,
    )
    proposal_mixed_signal_audit.add_argument("--output-dir", type=Path, required=True)
    proposal_mixed_signal_audit.add_argument("--force", action="store_true")
    proposal_mixed_signal_audit.add_argument("--json", action="store_true")
    proposal_smol_promotion_gate = proposal_commands.add_parser(
        "build-smol-promotion-gate",
        help="Build a dev/canary promotion gate from Smol WorldCup effectiveness reports",
    )
    proposal_smol_promotion_gate.add_argument("--dev-effectiveness-report", type=Path, required=True)
    proposal_smol_promotion_gate.add_argument(
        "--canary-effectiveness-report",
        type=Path,
        required=True,
    )
    proposal_smol_promotion_gate.add_argument("--output-dir", type=Path, required=True)
    proposal_smol_promotion_gate.add_argument("--force", action="store_true")
    proposal_smol_promotion_gate.add_argument("--json", action="store_true")
    proposal_smol_canary_failure_slice_audit = proposal_commands.add_parser(
        "build-smol-canary-failure-slice-audit",
        help="Build a Smol WorldCup canary failure-slice audit from canary artifacts",
    )
    proposal_smol_canary_failure_slice_audit.add_argument(
        "--canary-effectiveness-report",
        type=Path,
        required=True,
    )
    proposal_smol_canary_failure_slice_audit.add_argument(
        "--promotion-gate",
        type=Path,
        required=True,
    )
    proposal_smol_canary_failure_slice_audit.add_argument(
        "--control-outcomes",
        type=Path,
        required=True,
    )
    proposal_smol_canary_failure_slice_audit.add_argument(
        "--treatment-outcomes",
        type=Path,
        required=True,
    )
    proposal_smol_canary_failure_slice_audit.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )
    proposal_smol_canary_failure_slice_audit.add_argument("--force", action="store_true")
    proposal_smol_canary_failure_slice_audit.add_argument("--json", action="store_true")
    proposal_smol_canary_control_arm_handoff = proposal_commands.add_parser(
        "build-smol-canary-control-arm-handoff",
        help="Build a Smol WorldCup canary control-arm proposal handoff from the failure-slice audit",
    )
    proposal_smol_canary_control_arm_handoff.add_argument(
        "--failure-slice-audit",
        type=Path,
        required=True,
    )
    proposal_smol_canary_control_arm_handoff.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )
    proposal_smol_canary_control_arm_handoff.add_argument("--force", action="store_true")
    proposal_smol_canary_control_arm_handoff.add_argument("--json", action="store_true")
    proposal_smol_canary_control_arm_execution_bundle = proposal_commands.add_parser(
        "build-smol-canary-control-arm-execution-bundle",
        help="Build a Smol WorldCup canary control-arm execution bundle from the handoff",
    )
    proposal_smol_canary_control_arm_execution_bundle.add_argument(
        "--handoff",
        type=Path,
        required=True,
    )
    proposal_smol_canary_control_arm_execution_bundle.add_argument("--current-report", type=Path)
    proposal_smol_canary_control_arm_execution_bundle.add_argument("--baseline-report", type=Path)
    proposal_smol_canary_control_arm_execution_bundle.add_argument("--evidence-root", type=Path)
    proposal_smol_canary_control_arm_execution_bundle.add_argument(
        "--target-prompt-profile"
    )
    proposal_smol_canary_control_arm_execution_bundle.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )
    proposal_smol_canary_control_arm_execution_bundle.add_argument("--force", action="store_true")
    proposal_smol_canary_control_arm_execution_bundle.add_argument("--json", action="store_true")
    proposal_smol_promotion_gate_refresh = proposal_commands.add_parser(
        "build-smol-promotion-gate-refresh",
        help="Refresh a Smol WorldCup promotion gate from a guarded proposal-round summary",
    )
    proposal_smol_promotion_gate_refresh.add_argument(
        "--previous-gate",
        type=Path,
        required=True,
    )
    proposal_smol_promotion_gate_refresh.add_argument(
        "--proposal-round-summary",
        type=Path,
        required=True,
    )
    proposal_smol_promotion_gate_refresh.add_argument(
        "--output-dir",
        type=Path,
        required=True,
    )
    proposal_smol_promotion_gate_refresh.add_argument("--force", action="store_true")
    proposal_smol_promotion_gate_refresh.add_argument("--json", action="store_true")
    proposal_failure_context = proposal_commands.add_parser(
        "build-failure-context",
        help="Build a failure-driven planner context from failure records and pattern memory",
    )
    proposal_failure_context.add_argument("--objective", required=True)
    proposal_failure_context.add_argument("--failures", type=Path, required=True)
    proposal_failure_context.add_argument("--pattern-memory", type=Path)
    proposal_failure_context.add_argument("--output", type=Path, required=True)
    proposal_failure_context.add_argument("--max-proposals", type=int, default=3)
    proposal_failure_context.add_argument("--force", action="store_true")
    proposal_failure_context.add_argument("--json", action="store_true")
    proposal_generate = proposal_commands.add_parser(
        "generate-proposals",
        help="Generate failure-driven proposal drafts from planner context",
    )
    proposal_generate.add_argument("--context", type=Path, required=True)
    proposal_generate.add_argument("--output", type=Path, required=True)
    proposal_generate.add_argument("--preferred-change-surface", action="append")
    proposal_generate.add_argument("--force", action="store_true")
    proposal_generate.add_argument("--json", action="store_true")
    proposal_rank = proposal_commands.add_parser(
        "rank",
        help="Rank failure-driven proposals with pattern priors and redundancy penalties",
    )
    proposal_rank.add_argument("--proposals", type=Path, required=True)
    proposal_rank.add_argument("--failures", type=Path, required=True)
    proposal_rank.add_argument("--pattern-memory", type=Path)
    proposal_rank.add_argument("--output", type=Path, required=True)
    proposal_rank.add_argument("--force", action="store_true")
    proposal_rank.add_argument("--json", action="store_true")
    proposal_handoff = proposal_commands.add_parser(
        "handoff",
        help="Build a planner handoff from failure-driven context and ranked proposals",
    )
    proposal_handoff.add_argument("--context", type=Path, required=True)
    proposal_handoff.add_argument("--ranking", type=Path, required=True)
    proposal_handoff.add_argument("--output-dir", type=Path, required=True)
    proposal_handoff.add_argument("--max-selected", type=int, default=1)
    proposal_handoff.add_argument("--force", action="store_true")
    proposal_handoff.add_argument("--json", action="store_true")
    proposal_client_templates = proposal_commands.add_parser(
        "build-client-templates",
        help="Build strict client proposal templates from a failure-driven handoff",
    )
    proposal_client_templates.add_argument("--handoff", type=Path, required=True)
    proposal_client_templates.add_argument("--output-dir", type=Path, required=True)
    proposal_client_templates.add_argument("--force", action="store_true")
    proposal_client_templates.add_argument("--json", action="store_true")
    proposal_bridge_memory = proposal_commands.add_parser(
        "bridge-to-memory-card",
        help="Build a review-only memory card candidate from a proposal outcome",
    )
    proposal_bridge_memory.add_argument("--outcome", type=Path, required=True)
    proposal_bridge_memory.add_argument("--handoff", type=Path)
    proposal_bridge_memory.add_argument("--output", type=Path, required=True)
    proposal_bridge_memory.add_argument("--force", action="store_true")
    proposal_bridge_memory.add_argument("--json", action="store_true")
    proposal_effectiveness = proposal_commands.add_parser(
        "evaluate-effectiveness",
        help="Compare control vs treatment proposal outcomes for local A/B effectiveness",
    )
    proposal_effectiveness.add_argument("--control-outcomes", type=Path, required=True)
    proposal_effectiveness.add_argument("--treatment-outcomes", type=Path, required=True)
    proposal_effectiveness.add_argument("--output", type=Path, required=True)
    proposal_effectiveness.add_argument(
        "--control-label",
        default="without_failure_driven_context",
    )
    proposal_effectiveness.add_argument(
        "--treatment-label",
        default="with_failure_driven_context",
    )
    proposal_effectiveness.add_argument("--force", action="store_true")
    proposal_effectiveness.add_argument("--json", action="store_true")
    proposal_search = proposal_commands.add_parser(
        "search",
        help="Summarize a small proposal portfolio/tree frontier",
    )
    proposal_search.add_argument("--items", type=Path, required=True)
    proposal_search.add_argument("--branch-budget", type=int)
    proposal_search.add_argument("--diversity-max-per-family", type=int)
    proposal_search.add_argument("--json", action="store_true")

    init_config = subcommands.add_parser(
        "init-mcp-config",
        help="Render a Codex/Claude MCP config for this checkout",
    )
    init_config.add_argument(
        "--client",
        choices=["codex", "claude-code", "claude-desktop"],
        required=True,
    )
    init_config.add_argument("--project-root", default=str(WORKSPACE_ROOT))
    init_config.add_argument("--python", default=resolve_python_executable(WORKSPACE_ROOT))
    init_config.add_argument(
        "--server-name",
        help="Override MCP server name. Defaults to mlResearchLoop for Codex and ml-research-loop for Claude.",
    )
    init_config.add_argument("--output", help="Optional output file. Defaults to stdout.")
    init_config.add_argument("--force", action="store_true", help="Overwrite --output if it exists.")

    init_skills = subcommands.add_parser(
        "init-skills",
        help="Install the repository ML Research Loop skills for Codex or Claude",
    )
    init_skills.add_argument("--client", choices=["codex", "claude"], required=True)
    init_skills.add_argument("--project-root", default=str(WORKSPACE_ROOT))
    init_skills.add_argument(
        "--target-root",
        help="Skill root. Defaults to ~/.codex/skills for Codex and ~/.claude/skills for Claude.",
    )
    init_skills.add_argument("--force", action="store_true", help="Overwrite existing skills.")
    init_skills.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the install plan without copying files.",
    )

    feedback = subcommands.add_parser(
        "feedback-bundle",
        help="Write a redacted preview feedback diagnostics bundle",
    )
    feedback.add_argument("--runtime-root", type=Path)
    feedback.add_argument("--task-id")
    feedback.add_argument("--output-dir", type=Path, default=Path("feedback-bundle"))
    feedback.add_argument("--log-lines", type=int, default=80)
    feedback.add_argument("--python", default=sys.executable)

    hf_eval = subcommands.add_parser(
        "hf-eval",
        help="Plan Hugging Face external evaluation and leaderboard proof tracks",
    )
    hf_eval_commands = hf_eval.add_subparsers(dest="hf_eval_command", required=True)
    hf_eval_shortlist = hf_eval_commands.add_parser(
        "shortlist",
        help="Print the HF external evaluation target shortlist",
    )
    hf_eval_shortlist.add_argument(
        "--shortlist",
        type=Path,
        default=WORKSPACE_ROOT / "docs" / "hf-evaluation" / "target-shortlist.json",
    )
    hf_eval_shortlist.add_argument("--task-family")
    hf_eval_shortlist.add_argument("--limit", type=int)
    hf_eval_shortlist.add_argument("--json", action="store_true")
    hf_eval_plan = hf_eval_commands.add_parser(
        "plan",
        help="Write a local proof plan for one HF external evaluation target",
    )
    hf_eval_plan.add_argument(
        "--shortlist",
        type=Path,
        default=WORKSPACE_ROOT / "docs" / "hf-evaluation" / "target-shortlist.json",
    )
    hf_eval_plan.add_argument("--target-id")
    hf_eval_plan.add_argument("--output-dir", type=Path, required=True)
    hf_eval_plan.add_argument("--json", action="store_true")
    hf_eval_arguard_b1_verify = hf_eval_commands.add_parser(
        "arguard-b1-verify",
        help="Write live verification artifacts for the ArGuard B1 target",
    )
    hf_eval_arguard_b1_verify.add_argument("--output-dir", type=Path, required=True)
    hf_eval_arguard_b1_verify.add_argument("--timeout-seconds", type=int, default=30)
    hf_eval_arguard_b1_verify.add_argument("--no-raw", action="store_true")
    hf_eval_arguard_b1_verify.add_argument("--json", action="store_true")
    hf_eval_cp_bench_verify = hf_eval_commands.add_parser(
        "cp-bench-verify",
        help="Write live verification artifacts for the CP-Bench target",
    )
    hf_eval_cp_bench_verify.add_argument("--output-dir", type=Path, required=True)
    hf_eval_cp_bench_verify.add_argument("--timeout-seconds", type=int, default=30)
    hf_eval_cp_bench_verify.add_argument("--no-raw", action="store_true")
    hf_eval_cp_bench_verify.add_argument("--json", action="store_true")
    hf_eval_cp_bench_baseline = hf_eval_commands.add_parser(
        "cp-bench-baseline",
        help="Write a CP-Bench local baseline artifact bundle",
    )
    hf_eval_cp_bench_baseline.add_argument("--output-dir", type=Path, required=True)
    hf_eval_cp_bench_baseline.add_argument("--limit", type=int, default=1)
    hf_eval_cp_bench_baseline.add_argument(
        "--framework",
        default="CPMpy",
        choices=["CPMpy", "MiniZinc", "OR-Tools"],
    )
    hf_eval_cp_bench_baseline.add_argument(
        "--dataset-version",
        default="verified",
        choices=["original", "verified"],
    )
    hf_eval_cp_bench_baseline.add_argument("--timeout-seconds", type=int, default=60)
    hf_eval_cp_bench_baseline.add_argument(
        "--dry-run",
        action="store_true",
        help="Write format-check artifacts without invoking the CP-Bench evaluator.",
    )
    hf_eval_cp_bench_baseline.add_argument("--json", action="store_true")
    hf_eval_cp_bench_proposal = hf_eval_commands.add_parser(
        "cp-bench-proposal-round",
        help="Write a guarded CP-Bench proposal-round artifact bundle",
    )
    hf_eval_cp_bench_proposal.add_argument("--baseline-report", type=Path, required=True)
    hf_eval_cp_bench_proposal.add_argument("--proposal", type=Path, required=True)
    hf_eval_cp_bench_proposal.add_argument("--output-dir", type=Path, required=True)
    hf_eval_cp_bench_proposal.add_argument("--json", action="store_true")
    hf_eval_cp_bench_candidate = hf_eval_commands.add_parser(
        "cp-bench-candidate-round",
        help="Run a guarded CP-Bench candidate submission against a local baseline",
    )
    hf_eval_cp_bench_candidate.add_argument("--baseline-report", type=Path, required=True)
    hf_eval_cp_bench_candidate.add_argument("--submission", type=Path, required=True)
    hf_eval_cp_bench_candidate.add_argument("--output-dir", type=Path, required=True)
    hf_eval_cp_bench_candidate.add_argument("--proposal", type=Path)
    hf_eval_cp_bench_candidate.add_argument(
        "--framework",
        default="CPMpy",
        choices=["CPMpy", "MiniZinc", "OR-Tools"],
    )
    hf_eval_cp_bench_candidate.add_argument(
        "--dataset-version",
        default="verified",
        choices=["original", "verified"],
    )
    hf_eval_cp_bench_candidate.add_argument("--timeout-seconds", type=int, default=60)
    hf_eval_cp_bench_candidate.add_argument("--json", action="store_true")
    hf_eval_cp_bench_context = hf_eval_commands.add_parser(
        "cp-bench-proposal-context",
        help="Write a CP-Bench proposal prompt context from a candidate-round report",
    )
    hf_eval_cp_bench_context.add_argument("--current-report", type=Path, required=True)
    hf_eval_cp_bench_context.add_argument("--output-dir", type=Path, required=True)
    hf_eval_cp_bench_context.add_argument("--max-proposals", type=int, default=3)
    hf_eval_cp_bench_context.add_argument("--json", action="store_true")
    hf_eval_cp_bench_client_candidate = hf_eval_commands.add_parser(
        "cp-bench-client-candidate",
        help="Write a non-reference-replay CP-Bench client candidate submission bundle",
    )
    hf_eval_cp_bench_client_candidate.add_argument("--output-dir", type=Path, required=True)
    hf_eval_cp_bench_client_candidate.add_argument("--limit", type=int, default=10)
    hf_eval_cp_bench_client_candidate.add_argument(
        "--dataset-version",
        default="verified",
        choices=["original", "verified"],
    )
    hf_eval_cp_bench_client_candidate.add_argument(
        "--strategy",
        default="handcrafted-small-cpmpy-v1",
        choices=["handcrafted-small-cpmpy-v1"],
    )
    hf_eval_cp_bench_client_candidate.add_argument("--json", action="store_true")
    hf_eval_cp_bench_gate = hf_eval_commands.add_parser(
        "cp-bench-submission-gate",
        help="Write a manual CP-Bench submission gate bundle",
    )
    hf_eval_cp_bench_gate.add_argument("--submission", type=Path, required=True)
    hf_eval_cp_bench_gate.add_argument("--source-report", type=Path)
    hf_eval_cp_bench_gate.add_argument("--output-dir", type=Path, required=True)
    hf_eval_cp_bench_gate.add_argument("--json", action="store_true")
    hf_eval_smol_verify = hf_eval_commands.add_parser(
        "smol-worldcup-verify",
        help="Write live verification artifacts for the Smol AI WorldCup target",
    )
    hf_eval_smol_verify.add_argument("--output-dir", type=Path, required=True)
    hf_eval_smol_verify.add_argument("--timeout-seconds", type=int, default=30)
    hf_eval_smol_verify.add_argument("--no-raw", action="store_true")
    hf_eval_smol_verify.add_argument("--json", action="store_true")
    hf_eval_smol_leakage_audit = hf_eval_commands.add_parser(
        "smol-worldcup-leakage-audit",
        help="Audit generated Smol AI WorldCup model prompts for evaluation-only leakage",
    )
    hf_eval_smol_leakage_audit.add_argument("--output-dir", type=Path, required=True)
    hf_eval_smol_leakage_audit.add_argument("--timeout-seconds", type=int, default=30)
    hf_eval_smol_leakage_audit.add_argument("--page-size", type=int, default=100)
    hf_eval_smol_leakage_audit.add_argument("--limit", type=int)
    hf_eval_smol_leakage_audit.add_argument(
        "--prompt-profile",
        default="default",
        choices=[
            "default",
            "p3-routing-v1",
            "p3-dev-v2",
            "p3-semantic-v1",
            "p3-semantic-v2",
            "p3-canary-repair-v1",
            "p3-canary-repair-v2",
            "p3-canary-repair-v3",
            "p3-canary-repair-v4",
            "p3-canary-repair-v5",
            "p3-canary-repair-v6",
            "p3-canary-repair-v7",
            "p3-slice-metacognition-textgrad-v1",
            "p3-v7-metacognition-textgrad-v2",
            "p3-v7-metacognition-textgrad-pw-ar-v3",
        ],
    )
    hf_eval_smol_leakage_audit.add_argument(
        "--prompt-profile-registration",
        type=Path,
        help="PromptProfileRegistration artifact used as a dynamic profile overlay.",
    )
    hf_eval_smol_leakage_audit.add_argument(
        "--evaluation-split",
        default="all",
        choices=["all", "dev", "canary"],
    )
    hf_eval_smol_leakage_audit.add_argument("--canary-fraction", type=float, default=0.2)
    hf_eval_smol_leakage_audit.add_argument("--json", action="store_true")
    hf_eval_smol_baseline = hf_eval_commands.add_parser(
        "smol-worldcup-baseline",
        help="Run a local-compatible Smol AI WorldCup baseline and write P1 artifacts",
    )
    hf_eval_smol_baseline.add_argument("--output-dir", type=Path, required=True)
    hf_eval_smol_baseline.add_argument("--timeout-seconds", type=int, default=30)
    hf_eval_smol_baseline.add_argument("--page-size", type=int, default=100)
    hf_eval_smol_baseline.add_argument("--limit", type=int)
    hf_eval_smol_baseline.add_argument("--strategy", default="local-abstain-baseline")
    hf_eval_smol_baseline.add_argument(
        "--evaluation-split",
        default="all",
        choices=["all", "dev", "canary"],
    )
    hf_eval_smol_baseline.add_argument("--canary-fraction", type=float, default=0.2)
    hf_eval_smol_baseline.add_argument("--model-size-billion", type=float, default=0.001)
    hf_eval_smol_baseline.add_argument("--estimated-ram-gb", type=float, default=0.01)
    hf_eval_smol_baseline.add_argument("--json", action="store_true")
    hf_eval_smol_model_eval = hf_eval_commands.add_parser(
        "smol-worldcup-model-eval",
        help="Run Smol AI WorldCup local model eval through an OpenAI-compatible endpoint",
    )
    hf_eval_smol_model_eval.add_argument("--output-dir", type=Path, required=True)
    hf_eval_smol_model_eval.add_argument(
        "--base-url",
        default="http://127.0.0.1:1234/v1",
        help="OpenAI-compatible base URL, such as LM Studio's local server.",
    )
    hf_eval_smol_model_eval.add_argument("--model", default="openai/gpt-oss-20b")
    hf_eval_smol_model_eval.add_argument(
        "--model-provider",
        default="openai-compatible",
        choices=["openai-compatible", "deepseek"],
        help="Model provider preset. deepseek defaults to https://api.deepseek.com.",
    )
    hf_eval_smol_model_eval.add_argument(
        "--api-key-env",
        help="Environment variable name for authenticated providers, for example DEEPSEEK_API_KEY.",
    )
    hf_eval_smol_model_eval.add_argument(
        "--thinking-mode",
        default="default",
        choices=["default", "enabled", "disabled"],
        help="DeepSeek thinking mode. Use default to omit the provider-specific field.",
    )
    hf_eval_smol_model_eval.add_argument(
        "--reasoning-effort",
        choices=["high", "max"],
        help="DeepSeek reasoning_effort. Omit for provider default.",
    )
    hf_eval_smol_model_eval.add_argument("--timeout-seconds", type=int, default=120)
    hf_eval_smol_model_eval.add_argument("--page-size", type=int, default=100)
    hf_eval_smol_model_eval.add_argument("--limit", type=int)
    hf_eval_smol_model_eval.add_argument("--dataset-offset", type=int, default=0)
    hf_eval_smol_model_eval.add_argument(
        "--row-id",
        action="append",
        default=[],
        help="Restrict model eval to specific Smol WorldCup row ids; repeatable.",
    )
    hf_eval_smol_model_eval.add_argument(
        "--cached-response-prediction-path",
        type=Path,
        help="Replay model responses from a previous prediction.jsonl response cache.",
    )
    hf_eval_smol_model_eval.add_argument(
        "--require-cached-responses",
        action="store_true",
        help="Fail if any selected row is missing from the cached response predictions.",
    )
    hf_eval_smol_model_eval.add_argument("--temperature", type=float, default=0.0)
    hf_eval_smol_model_eval.add_argument("--max-tokens", type=int, default=512)
    hf_eval_smol_model_eval.add_argument("--round-id", default="round-001")
    hf_eval_smol_model_eval.add_argument(
        "--prompt-profile",
        default="default",
        choices=[
            "default",
            "p3-routing-v1",
            "p3-dev-v2",
            "p3-semantic-v1",
            "p3-semantic-v2",
            "p3-canary-repair-v1",
            "p3-canary-repair-v2",
            "p3-canary-repair-v3",
            "p3-canary-repair-v4",
            "p3-canary-repair-v5",
            "p3-canary-repair-v6",
            "p3-canary-repair-v7",
            "p3-slice-metacognition-textgrad-v1",
            "p3-v7-metacognition-textgrad-v2",
            "p3-v7-metacognition-textgrad-pw-ar-v3",
        ],
        help="Prompt/routing profile for local model evaluation.",
    )
    hf_eval_smol_model_eval.add_argument(
        "--prompt-profile-registration",
        type=Path,
        help="PromptProfileRegistration artifact used as a dynamic profile overlay.",
    )
    hf_eval_smol_model_eval.add_argument(
        "--evaluation-split",
        default="all",
        choices=["all", "dev", "canary"],
        help="Deterministic row split for future dev/canary holdout discipline.",
    )
    hf_eval_smol_model_eval.add_argument("--canary-fraction", type=float, default=0.2)
    hf_eval_smol_model_eval.add_argument(
        "--judge-mode",
        default="heuristic",
        choices=["heuristic", "openai-compatible"],
        help="Rubric judge mode for llm_judge rows.",
    )
    hf_eval_smol_model_eval.add_argument(
        "--judge-model",
        help="OpenAI-compatible model used when --judge-mode=openai-compatible.",
    )
    hf_eval_smol_model_eval.add_argument(
        "--judge-base-url",
        help="OpenAI-compatible judge base URL. Defaults to --base-url.",
    )
    hf_eval_smol_model_eval.add_argument("--model-size-billion", type=float, default=20.0)
    hf_eval_smol_model_eval.add_argument("--estimated-ram-gb", type=float, default=32.0)
    hf_eval_smol_model_eval.add_argument("--json", action="store_true")
    hf_eval_smol_proposal_round = hf_eval_commands.add_parser(
        "smol-worldcup-proposal-round",
        help="Validate a proposal contract and run one guarded Smol WorldCup local round",
    )
    hf_eval_smol_proposal_round.add_argument("--proposal", type=Path, required=True)
    hf_eval_smol_proposal_round.add_argument("--output-dir", type=Path, required=True)
    hf_eval_smol_proposal_round.add_argument("--baseline-report", type=Path)
    hf_eval_smol_proposal_round.add_argument("--current-report", type=Path)
    hf_eval_smol_proposal_round.add_argument(
        "--base-url",
        default="http://127.0.0.1:1234/v1",
        help="OpenAI-compatible base URL, such as LM Studio's local server.",
    )
    hf_eval_smol_proposal_round.add_argument("--model", default="openai/gpt-oss-20b")
    hf_eval_smol_proposal_round.add_argument(
        "--model-provider",
        default="openai-compatible",
        choices=["openai-compatible", "deepseek"],
    )
    hf_eval_smol_proposal_round.add_argument("--api-key-env")
    hf_eval_smol_proposal_round.add_argument(
        "--thinking-mode",
        default="default",
        choices=["default", "enabled", "disabled"],
    )
    hf_eval_smol_proposal_round.add_argument(
        "--reasoning-effort",
        choices=["high", "max"],
    )
    hf_eval_smol_proposal_round.add_argument("--timeout-seconds", type=int, default=120)
    hf_eval_smol_proposal_round.add_argument("--page-size", type=int, default=100)
    hf_eval_smol_proposal_round.add_argument("--limit", type=int)
    hf_eval_smol_proposal_round.add_argument("--dataset-offset", type=int, default=0)
    hf_eval_smol_proposal_round.add_argument("--temperature", type=float, default=0.0)
    hf_eval_smol_proposal_round.add_argument("--max-tokens", type=int, default=512)
    hf_eval_smol_proposal_round.add_argument("--round-id")
    hf_eval_smol_proposal_round.add_argument(
        "--prompt-profile",
        choices=[
            "default",
            "p3-routing-v1",
            "p3-dev-v2",
            "p3-semantic-v1",
            "p3-semantic-v2",
            "p3-canary-repair-v1",
            "p3-canary-repair-v2",
            "p3-canary-repair-v3",
            "p3-canary-repair-v4",
            "p3-canary-repair-v5",
            "p3-canary-repair-v6",
            "p3-canary-repair-v7",
            "p3-slice-metacognition-textgrad-v1",
            "p3-v7-metacognition-textgrad-v2",
            "p3-v7-metacognition-textgrad-pw-ar-v3",
        ],
        help="Override the prompt profile selected from proposal.change_spec.",
    )
    hf_eval_smol_proposal_round.add_argument(
        "--evaluation-split",
        default="dev",
        choices=["all", "dev", "canary"],
    )
    hf_eval_smol_proposal_round.add_argument("--canary-fraction", type=float, default=0.2)
    hf_eval_smol_proposal_round.add_argument(
        "--judge-mode",
        default="heuristic",
        choices=["heuristic", "openai-compatible"],
    )
    hf_eval_smol_proposal_round.add_argument("--judge-model")
    hf_eval_smol_proposal_round.add_argument("--judge-base-url")
    hf_eval_smol_proposal_round.add_argument("--model-size-billion", type=float, default=20.0)
    hf_eval_smol_proposal_round.add_argument("--estimated-ram-gb", type=float, default=32.0)
    hf_eval_smol_proposal_round.add_argument("--allowed-change-surface", action="append")
    hf_eval_smol_proposal_round.add_argument("--json", action="store_true")
    hf_eval_smol_rescore = hf_eval_commands.add_parser(
        "smol-worldcup-rescore",
        help="Rescore existing Smol AI WorldCup predictions with scorer-v2",
    )
    hf_eval_smol_rescore.add_argument("--prediction-path", type=Path, required=True)
    hf_eval_smol_rescore.add_argument("--output-dir", type=Path, required=True)
    hf_eval_smol_rescore.add_argument("--source-report", type=Path)
    hf_eval_smol_rescore.add_argument("--source-rows", type=Path)
    hf_eval_smol_rescore.add_argument("--source-run-id")
    hf_eval_smol_rescore.add_argument("--timeout-seconds", type=int, default=30)
    hf_eval_smol_rescore.add_argument("--page-size", type=int, default=100)
    hf_eval_smol_rescore.add_argument(
        "--rerun-llm-judge-heuristic",
        action="store_true",
        help=(
            "Do not preserve existing llm_judge scores; use local heuristic fallback "
            "unless a future judge is wired explicitly."
        ),
    )
    hf_eval_smol_rescore.add_argument("--model-size-billion", type=float, default=20.0)
    hf_eval_smol_rescore.add_argument("--estimated-ram-gb", type=float, default=32.0)
    hf_eval_smol_rescore.add_argument("--json", action="store_true")
    hf_eval_smol_rescore_archive = hf_eval_commands.add_parser(
        "smol-worldcup-rescore-proof-archive",
        help="Package formal Smol AI WorldCup rescore artifacts into a proof archive",
    )
    hf_eval_smol_rescore_archive.add_argument("--rescore-dir", type=Path, required=True)
    hf_eval_smol_rescore_archive.add_argument("--output-dir", type=Path, required=True)
    hf_eval_smol_rescore_archive.add_argument("--source-report", type=Path)
    hf_eval_smol_rescore_archive.add_argument("--source-prediction-path", type=Path)
    hf_eval_smol_rescore_archive.add_argument("--source-run-id")
    hf_eval_smol_rescore_archive.add_argument(
        "--command-line",
        action="append",
        help="Command line to include in proof archive. Can be provided multiple times.",
    )
    hf_eval_smol_rescore_archive.add_argument("--json", action="store_true")
    hf_eval_smol_submission_probe = hf_eval_commands.add_parser(
        "smol-worldcup-submission-probe",
        help="Probe the Smol AI WorldCup HF Space submission path without submitting",
    )
    hf_eval_smol_submission_probe.add_argument("--output-dir", type=Path, required=True)
    hf_eval_smol_submission_probe.add_argument("--model", default="openai/gpt-oss-20b")
    hf_eval_smol_submission_probe.add_argument("--timeout-seconds", type=int, default=30)
    hf_eval_smol_submission_probe.add_argument("--no-raw", action="store_true")
    hf_eval_smol_submission_probe.add_argument("--json", action="store_true")

    benchmark = subcommands.add_parser(
        "benchmark",
        help="Inspect or run benchmark adapter compatibility flows",
    )
    benchmark_commands = benchmark.add_subparsers(dest="benchmark_command", required=True)
    benchmark_readiness = benchmark_commands.add_parser(
        "readiness",
        help="Print benchmark adapter readiness metadata",
    )
    benchmark_readiness.add_argument("--json", action="store_true")
    benchmark_smoke = benchmark_commands.add_parser(
        "smoke",
        help="Run all benchmark adapter compatibility demos",
    )
    benchmark_smoke.add_argument("--runtime-root", type=Path, required=True)
    benchmark_smoke.add_argument("--python", default=sys.executable)
    benchmark_smoke.add_argument("--json", action="store_true")
    benchmark_probe = benchmark_commands.add_parser(
        "probe",
        help="Probe official benchmark harness prerequisites without running evaluations",
    )
    benchmark_probe.add_argument("--mle-bench-repo", type=Path)
    benchmark_probe.add_argument("--paperbench-repo", type=Path)
    benchmark_probe.add_argument("--paperbench-data-dir", type=Path)
    benchmark_probe.add_argument("--json", action="store_true")
    benchmark_proof_plan = benchmark_commands.add_parser(
        "proof-plan",
        help="Plan a public official-debug proof run without launching evaluations",
    )
    benchmark_proof_plan.add_argument("--mle-bench-repo", type=Path)
    benchmark_proof_plan.add_argument("--paperbench-repo", type=Path)
    benchmark_proof_plan.add_argument("--paperbench-data-dir", type=Path)
    benchmark_proof_plan.add_argument("--json", action="store_true")
    benchmark_setup_bundle = benchmark_commands.add_parser(
        "setup-bundle",
        help="Write read-only setup files for an official debug proof-run environment",
    )
    benchmark_setup_bundle.add_argument("--mle-bench-repo", type=Path)
    benchmark_setup_bundle.add_argument("--paperbench-repo", type=Path)
    benchmark_setup_bundle.add_argument("--paperbench-data-dir", type=Path)
    benchmark_setup_bundle.add_argument("--output-dir", type=Path, required=True)
    benchmark_setup_bundle.add_argument("--json", action="store_true")
    benchmark_publication_bundle = benchmark_commands.add_parser(
        "publication-bundle",
        help="Write a guarded publication bundle from proof-run artifacts",
    )
    benchmark_publication_bundle.add_argument("--manifest", type=Path, required=True)
    benchmark_publication_bundle.add_argument("--artifact-root", type=Path, required=True)
    benchmark_publication_bundle.add_argument("--output-dir", type=Path, required=True)
    benchmark_publication_bundle.add_argument("--json", action="store_true")
    benchmark_archive_proof = benchmark_commands.add_parser(
        "archive-proof",
        help="Copy proof-run artifacts into a hashed archive bundle",
    )
    benchmark_archive_proof.add_argument("--manifest", type=Path, required=True)
    benchmark_archive_proof.add_argument("--artifact-root", type=Path, required=True)
    benchmark_archive_proof.add_argument("--output-dir", type=Path, required=True)
    benchmark_archive_proof.add_argument("--json", action="store_true")
    benchmark_mle_workspace = benchmark_commands.add_parser(
        "mle-workspace",
        help="Create an agent workspace from official MLE-bench prepared data",
    )
    benchmark_mle_workspace.add_argument("--competition-id", required=True)
    benchmark_mle_workspace.add_argument("--prepared-competition-dir", type=Path, required=True)
    benchmark_mle_workspace.add_argument("--runtime-root", type=Path, required=True)
    benchmark_mle_workspace.add_argument("--workspace-name")
    benchmark_mle_workspace.add_argument("--json", action="store_true")
    benchmark_mle_grade = benchmark_commands.add_parser(
        "mle-grade",
        help="Grade a submission with official mlebench grade-sample",
    )
    benchmark_mle_grade.add_argument("--competition-id", required=True)
    benchmark_mle_grade.add_argument("--submission", type=Path, required=True)
    benchmark_mle_grade.add_argument("--data-dir", type=Path, required=True)
    benchmark_mle_grade.add_argument("--mlebench", type=Path, required=True)
    benchmark_mle_grade.add_argument("--output-dir", type=Path, required=True)
    benchmark_mle_grade.add_argument("--timeout-seconds", type=int, default=300)
    benchmark_mle_grade.add_argument("--json", action="store_true")
    benchmark_mle_round = benchmark_commands.add_parser(
        "mle-round",
        help="Run workspace solve.py and grade submission.csv with official mlebench grade-sample",
    )
    benchmark_mle_round.add_argument("--competition-id", required=True)
    benchmark_mle_round.add_argument("--workspace", type=Path, required=True)
    benchmark_mle_round.add_argument("--data-dir", type=Path, required=True)
    benchmark_mle_round.add_argument("--mlebench", type=Path, required=True)
    benchmark_mle_round.add_argument("--output-dir", type=Path, required=True)
    benchmark_mle_round.add_argument("--python", default=sys.executable)
    benchmark_mle_round.add_argument("--round-id", default="round-001")
    benchmark_mle_round.add_argument("--timeout-seconds", type=int, default=300)
    benchmark_mle_round.add_argument("--json", action="store_true")
    benchmark_mle_patch_round = benchmark_commands.add_parser(
        "mle-patch-round",
        help="Apply a workspace patch, run solve.py, and grade submission.csv",
    )
    benchmark_mle_patch_round.add_argument("--competition-id", required=True)
    benchmark_mle_patch_round.add_argument("--workspace", type=Path, required=True)
    benchmark_mle_patch_round.add_argument("--data-dir", type=Path, required=True)
    benchmark_mle_patch_round.add_argument("--mlebench", type=Path, required=True)
    benchmark_mle_patch_round.add_argument("--output-dir", type=Path, required=True)
    benchmark_mle_patch_round.add_argument("--patch-file", type=Path, required=True)
    benchmark_mle_patch_round.add_argument("--python", default=sys.executable)
    benchmark_mle_patch_round.add_argument("--round-id", default="round-001")
    benchmark_mle_patch_round.add_argument("--timeout-seconds", type=int, default=300)
    benchmark_mle_patch_round.add_argument("--json", action="store_true")
    benchmark_mle_patch_proof = benchmark_commands.add_parser(
        "mle-patch-proof",
        help="Write a proof archive from an official MLE-bench patch-round report",
    )
    benchmark_mle_patch_proof.add_argument("--patch-round-report", type=Path, required=True)
    benchmark_mle_patch_proof.add_argument("--output-dir", type=Path, required=True)
    benchmark_mle_patch_proof.add_argument("--json", action="store_true")
    benchmark_paperbench_codex_bundle = benchmark_commands.add_parser(
        "paperbench-codex-review-bundle",
        help="Prepare PaperBench artifacts for Codex-assisted rubric review",
    )
    benchmark_paperbench_codex_bundle.add_argument("--run-dir", type=Path, required=True)
    benchmark_paperbench_codex_bundle.add_argument("--paper-dir", type=Path, required=True)
    benchmark_paperbench_codex_bundle.add_argument("--output-dir", type=Path, required=True)
    benchmark_paperbench_codex_bundle.add_argument("--json", action="store_true")
    benchmark_paperbench_codex_report = benchmark_commands.add_parser(
        "paperbench-codex-review-report",
        help="Write a Codex-assisted PaperBench rubric review report",
    )
    benchmark_paperbench_codex_report.add_argument("--bundle", type=Path, required=True)
    benchmark_paperbench_codex_report.add_argument("--review-file", type=Path, required=True)
    benchmark_paperbench_codex_report.add_argument("--output-dir", type=Path, required=True)
    benchmark_paperbench_codex_report.add_argument("--json", action="store_true")

    demo = subcommands.add_parser("demo", help="List, initialize, or run stable demos")
    demo_commands = demo.add_subparsers(dest="demo_command", required=True)
    demo_commands.add_parser("list", help="List available demo templates")
    demo_init = demo_commands.add_parser("init", help="Write a demo task and dataset")
    _add_demo_template_args(demo_init)
    demo_run = demo_commands.add_parser("run", help="Write and run a demo template")
    _add_demo_template_args(demo_run)
    demo_run.add_argument("--python", default=sys.executable)
    demo_run.add_argument("--json", action="store_true")

    return parser


def _run_task(args: argparse.Namespace) -> int:
    script = "ai_autoresearch_run.py" if args.ai else "autoresearch_run.py"
    cmd = [
        resolve_python_executable(WORKSPACE_ROOT),
        str(WORKSPACE_ROOT / "scripts" / script),
        "--task-config",
        args.task_config,
        "--experiment-duration",
        str(args.experiment_duration),
    ]
    if args.workspace:
        cmd.extend(["--workspace", args.workspace])
    if args.max_experiments is not None:
        cmd.extend(["--max-experiments", str(args.max_experiments)])
    if args.max_duration is not None:
        cmd.extend(["--max-duration", str(args.max_duration)])
    if args.ai and args.mock:
        cmd.append("--mock")
    if args.verbose:
        cmd.append("--verbose")

    return subprocess.call(cmd, cwd=str(WORKSPACE_ROOT))


def _run_check(args: argparse.Namespace) -> int:
    cmd = [
        resolve_python_executable(WORKSPACE_ROOT),
        str(WORKSPACE_ROOT / "scripts" / "release_check.py"),
        "--python",
        args.python,
    ]
    if args.skip_demos:
        cmd.append("--skip-golden-path")
    if args.json:
        cmd.append("--json")
    return subprocess.call(cmd, cwd=str(WORKSPACE_ROOT))


def _run_artifacts(args: argparse.Namespace) -> int:
    arguments = {"runtime_root": args.runtime_root}
    if args.artifact_command == "list":
        payload = mcp_service.list_runtime_artifacts_tool(arguments)
    elif args.artifact_command == "archive":
        payload = mcp_service.archive_runtime_artifacts_tool({
            **arguments,
            "task_id": args.task_id,
        })
    elif args.artifact_command == "clean":
        payload = mcp_service.clean_runtime_artifacts_tool({
            **arguments,
            "task_id": args.task_id,
            "confirm": args.confirm,
        })
    else:
        return 2
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _run_memory(args: argparse.Namespace) -> int:
    store = ResearchMemoryStore(args.store)
    if args.memory_command == "record-fasttext-release":
        cards = extract_fasttext_release_memory_cards(
            release_manifest=args.release_manifest,
            multi_round_report=args.multi_round_report,
            review_checklist=args.review_checklist,
        )
        for card in cards:
            store.append(card)
        adapter_results = None
        if args.sync_adapters:
            adapter_results = sync_cards_to_adapters(
                cards,
                adapter_names=args.adapter,
            )
        payload = {
            "status": "recorded",
            "store": str(args.store),
            "card_count": len(cards),
            "card_ids": [card.card_id for card in cards],
            "official_scores_claimed": False,
        }
        if adapter_results is not None:
            payload["adapter_results"] = adapter_results
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if args.memory_command == "retrieve":
        matches = store.search(
            query=args.query,
            paper_id=args.paper_id,
            dataset=args.dataset,
            limit=args.limit,
        )
        payload = {
            "status": "retrieved",
            "store": str(args.store),
            "match_count": len(matches),
            "matches": [match.to_dict() for match in matches],
        }
        if args.include_adapters:
            payload["adapter_results"] = search_memory_adapters(
                query=args.query,
                limit=args.limit,
                adapter_names=args.adapter,
            )
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if args.memory_command == "cleanup":
        if not args.dry_run and not args.confirm:
            print(
                "memory cleanup execution requires --confirm; run with --dry-run first",
                file=sys.stderr,
            )
            return 1
        payload = store.cleanup(
            keep_last=args.keep_last,
            memory_type=args.memory_type,
            older_than_days=args.older_than_days,
            dry_run=args.dry_run,
            include_private=args.include_private,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if args.memory_command == "record-card-candidate":
        if not args.confirm:
            print(
                "memory card candidate recording requires --confirm",
                file=sys.stderr,
            )
            return 1
        candidate_payload = json.loads(args.candidate_file.read_text(encoding="utf-8"))
        if not isinstance(candidate_payload, dict):
            print("candidate JSON must be an object", file=sys.stderr)
            return 1
        card_payload = candidate_payload.get("memory_card_candidate")
        if not isinstance(card_payload, dict):
            print("candidate JSON must contain memory_card_candidate", file=sys.stderr)
            return 1
        card = ResearchMemoryCard.from_dict(card_payload)
        store.append(card)
        adapter_results = None
        if args.sync_adapters:
            adapter_results = sync_cards_to_adapters(
                [card],
                adapter_names=args.adapter,
            )
        payload = {
            "status": "recorded",
            "store": str(args.store),
            "card_ids": [card.card_id],
            "official_scores_claimed": False,
        }
        if adapter_results is not None:
            payload["adapter_results"] = adapter_results
        _print_json_payload(payload, compact=args.json)
        return 0
    return 2


def _run_proposal(args: argparse.Namespace) -> int:
    if args.proposal_command == "context":
        payload = build_proposal_context(
            objective=args.objective,
            output_dir=args.output_dir,
            baseline_report=args.baseline_report,
            current_report=args.current_report,
            dev_report=args.dev_report,
            canary_report=args.canary_report,
            category_deltas=args.category_deltas,
            failure_samples=args.failure_samples,
            rollback_summary=args.rollback_summary,
            previous_proposals=args.previous_proposals,
            memory_cards=args.memory_cards,
            memory_store=args.memory_store,
            memory_query=_proposal_memory_query_from_args(args),
            memory_limit=args.memory_limit,
            resource_constraints=_load_optional_json_object(args.resource_constraints),
            allowed_change_surfaces=args.allowed_change_surface,
            max_proposals=args.max_proposals,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "validate":
        proposal = json.loads(args.proposal.read_text(encoding="utf-8"))
        if not isinstance(proposal, dict):
            print("proposal JSON must be an object", file=sys.stderr)
            return 1
        payload = validate_client_proposal(
            proposal,
            allowed_change_surfaces=args.allowed_change_surface,
        )
        _print_json_payload(payload, compact=args.json)
        return 0 if payload["status"] == "accepted" else 1
    if args.proposal_command == "reflect":
        proposal = json.loads(args.proposal.read_text(encoding="utf-8"))
        evaluation = json.loads(args.evaluation.read_text(encoding="utf-8"))
        if not isinstance(proposal, dict) or not isinstance(evaluation, dict):
            print("proposal and evaluation JSON must be objects", file=sys.stderr)
            return 1
        payload = build_proposal_reflection(
            proposal=proposal,
            evaluation=evaluation,
            output_dir=args.output_dir,
            overwrite=args.force,
        )
        if args.memory_store is not None:
            store = ResearchMemoryStore(args.memory_store)
            card = proposal_reflection_to_memory_card(payload)
            store.append(card)
            memory_sync = {
                "status": "synced",
                "store": str(args.memory_store),
                "card_id": card.card_id,
                "executes_tool": False,
                "official_scores_claimed": False,
            }
            if args.sync_adapters:
                memory_sync["adapter_results"] = sync_cards_to_adapters(
                    [card],
                    adapter_names=args.adapter,
                )
            payload["memory_sync"] = memory_sync
        elif args.sync_adapters:
            print("--sync-adapters requires --memory-store", file=sys.stderr)
            return 1
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "search":
        raw_items = json.loads(args.items.read_text(encoding="utf-8"))
        if isinstance(raw_items, dict):
            items = raw_items.get("items") or raw_items.get("proposals")
        else:
            items = raw_items
        if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
            print("proposal search items JSON must be a list of objects", file=sys.stderr)
            return 1
        payload = build_proposal_search(
            items,
            branch_budget=args.branch_budget,
            diversity_constraint=_proposal_diversity_constraint_from_args(args),
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "extract-failures":
        payload = extract_failure_records(
            args.source_artifact,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "record-outcome":
        proposal = json.loads(args.proposal.read_text(encoding="utf-8"))
        evaluation = json.loads(args.evaluation.read_text(encoding="utf-8"))
        if not isinstance(proposal, dict) or not isinstance(evaluation, dict):
            print("proposal and evaluation JSON must be objects", file=sys.stderr)
            return 1
        payload = record_proposal_outcome(
            proposal=proposal,
            evaluation=evaluation,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-pattern-memory":
        payload = build_proposal_pattern_memory(
            args.outcomes,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "retrieve-patterns":
        payload = retrieve_proposal_patterns(
            pattern_memory=args.pattern_memory,
            failure_type=args.failure_type,
            proposal_type=args.proposal_type,
            task_family=args.task_family,
            metric_name=args.metric_name,
            limit=args.limit,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-prompt-module-spec":
        payload = build_prompt_module_spec(
            profile_id=args.profile_id,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-slice-eval-matrix":
        payload = build_slice_eval_matrix(
            baseline_report=args.baseline_report,
            candidate_report=args.candidate_report,
            candidate_evaluation=args.candidate_evaluation,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-slice-repair-context":
        payload = build_slice_repair_context(
            slice_matrix=args.slice_matrix,
            prompt_modules=args.prompt_modules,
            pattern_memory=args.pattern_memory,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "generate-slice-patches":
        payload = generate_slice_patch_candidates(
            context=args.context,
            optimizer=args.optimizer,
            optimizer_gate_plugin_manifests=args.plugin_manifest,
            max_candidates=args.max_candidates,
            execute_optimizer=args.execute_optimizer,
            optimizer_model=args.optimizer_model,
            optimizer_base_url=args.optimizer_base_url,
            optimizer_api_key=args.optimizer_api_key,
            optimizer_timeout_seconds=args.optimizer_timeout_seconds,
            optimizer_temperature=args.optimizer_temperature,
            optimizer_max_tokens=args.optimizer_max_tokens,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "probe-optimizer-runtime":
        payload = probe_optimizer_runtime(
            optimizer=args.optimizer,
            optimizer_gate_plugin_manifests=args.plugin_manifest,
            execute_probe=args.execute_probe,
            optimizer_model=args.optimizer_model,
            optimizer_base_url=args.optimizer_base_url,
            optimizer_timeout_seconds=args.optimizer_timeout_seconds,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-optimizer-package-runtime-benefit-audit":
        payload = build_optimizer_package_runtime_benefit_audit(
            optimizer_runtime_probe=args.optimizer_runtime_probe,
            slice_patch_candidates=args.slice_patch_candidates,
            gate_decision=args.gate_decision,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-method-proposal-generation-trace":
        payload = build_method_proposal_generation_trace(
            generation_context=args.generation_context,
            generation_run=args.generation_run,
            reasoning_trace=args.reasoning_trace,
            proposals=args.proposals,
            ranking_decisions=args.ranking_decisions,
            selected_proposal_ids=args.selected_proposal_id,
            execution_links=args.execution_links,
            gate_results=args.gate_results,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-method-search-study":
        payload = build_method_search_study(
            study_name=args.study_name,
            objective=args.objective,
            direction=args.direction,
            operators=args.operator,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "ask-method-search-trial":
        if args.llm_proposals is None and not args.execute_llm:
            raise SystemExit("--llm-proposals is required unless --execute-llm is set")
        payload = ask_method_search_trial(
            study=_load_method_search_study_argument(args.study),
            objective=args.objective,
            operators=args.operator or None,
            llm_proposals=args.llm_proposals,
            gate_feedback_memory=args.gate_feedback_memory,
            gate_feedback_memory_store=args.gate_feedback_memory_store,
            model=args.model,
            execute_llm=args.execute_llm,
            llm_base_url=args.llm_base_url,
            llm_provider=args.llm_provider,
            llm_api_key_env=args.llm_api_key_env,
            llm_temperature=args.llm_temperature,
            llm_max_tokens=args.llm_max_tokens,
            llm_timeout_seconds=args.llm_timeout_seconds,
            adapter=args.adapter,
            slice_id=args.slice_id,
            patch_scope=args.patch_scope,
            budget=_load_json_object_argument(args.budget_json),
            max_trials=args.max_trials,
            output_dir=args.output_dir,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "tell-method-search-trial":
        study_payload = _load_method_search_study_argument(args.study)
        trial_payload = (
            args.trial
            if args.trial is not None
            else _method_search_trial_from_study(study_payload, args.trial_id)
        )
        payload = tell_method_search_trial(
            study=study_payload,
            trial=trial_payload,
            gate_result=args.gate_result,
            feedback_store_path=args.feedback_store,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-optuna-sampler-adapter":
        payload = build_optuna_sampler_adapter(
            study=_load_method_search_study_argument(args.study),
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-optuna-storage-adapter":
        payload = build_optuna_storage_adapter(
            study=_load_method_search_study_argument(args.study),
            gate_feedback_memory_store=args.gate_feedback_memory_store,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-optuna-dashboard-export":
        payload = build_optuna_dashboard_export(
            study=_load_method_search_study_argument(args.study),
            gate_feedback_memory_store=args.gate_feedback_memory_store,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-multi-optimizer-candidate-race":
        payload = build_multi_optimizer_candidate_race(
            race_name=args.race_name,
            objective=args.objective,
            candidate_sources=args.candidate_sources,
            gate_results=args.gate_results,
            operators=args.operator or None,
            direction=args.direction,
            model=args.model,
            adapter=args.adapter,
            slice_id=args.slice_id,
            patch_scope=args.patch_scope,
            budget=_load_json_object_argument(args.budget_json),
            output_dir=args.output_dir,
            feedback_store_path=args.feedback_store,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "run-multi-optimizer-candidate-race":
        payload = run_multi_optimizer_candidate_race(
            race_name=args.race_name,
            objective=args.objective,
            context=args.context,
            gate_results=args.gate_results,
            mode=args.mode,
            optimizer_sources=args.optimizer_source or None,
            operators=args.operator or None,
            direction=args.direction,
            max_candidates_per_source=args.max_candidates_per_source,
            execute_llm=args.execute_llm,
            llm_proposals=args.llm_proposals,
            execute_optimizer_runtimes=args.execute_optimizer_runtime,
            allow_style_fallback=args.allow_style_fallback,
            optimizer_gate_plugin_manifests=args.plugin_manifest,
            optimizer_model=args.optimizer_model,
            optimizer_base_url=args.optimizer_base_url,
            optimizer_api_key=args.optimizer_api_key,
            optimizer_timeout_seconds=args.optimizer_timeout_seconds,
            optimizer_temperature=args.optimizer_temperature,
            optimizer_max_tokens=args.optimizer_max_tokens,
            output_dir=args.output_dir,
            feedback_store_path=args.feedback_store,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "run-method-search-trajectory":
        payload = run_method_search_trajectory(
            trajectory_name=args.trajectory_name,
            objective=args.objective,
            context=args.context,
            gate_results_by_round=args.round_gate_results,
            round_count=args.round_count,
            mode=args.mode,
            optimizer_sources=args.optimizer_source or None,
            operators=args.operator or None,
            direction=args.direction,
            max_candidates_per_source=args.max_candidates_per_source,
            llm_proposals_by_round=args.round_llm_proposals or None,
            execute_llm=args.execute_llm,
            execute_optimizer_runtimes=args.execute_optimizer_runtime,
            allow_style_fallback=args.allow_style_fallback,
            optimizer_gate_plugin_manifests=args.plugin_manifest,
            optimizer_model=args.optimizer_model,
            optimizer_base_url=args.optimizer_base_url,
            optimizer_api_key=args.optimizer_api_key,
            optimizer_timeout_seconds=args.optimizer_timeout_seconds,
            optimizer_temperature=args.optimizer_temperature,
            optimizer_max_tokens=args.optimizer_max_tokens,
            output_dir=args.output_dir,
            feedback_store_path=args.feedback_store,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "run-real-benchmark-readiness":
        payload = run_real_benchmark_readiness_run(
            run_name=args.run_name,
            objective=args.objective,
            benchmark_id=args.benchmark_id,
            rows=args.rows,
            context=args.context,
            round_count=args.round_count,
            mode=args.mode,
            optimizer_sources=args.optimizer_source or None,
            operators=args.operator or None,
            direction=args.direction,
            max_candidates_per_source=args.max_candidates_per_source,
            execute_llm=args.execute_llm,
            execute_optimizer_runtimes=args.execute_optimizer_runtime,
            allow_style_fallback=args.allow_style_fallback,
            optimizer_gate_plugin_manifests=args.plugin_manifest,
            optimizer_model=args.optimizer_model,
            optimizer_base_url=args.optimizer_base_url,
            optimizer_api_key=args.optimizer_api_key,
            optimizer_timeout_seconds=args.optimizer_timeout_seconds,
            optimizer_temperature=args.optimizer_temperature,
            optimizer_max_tokens=args.optimizer_max_tokens,
            model=args.model,
            base_url=args.base_url,
            model_provider=args.model_provider,
            api_key_env=args.api_key_env,
            timeout_seconds=args.timeout_seconds,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            judge_mode=args.judge_mode,
            canary_fraction=args.canary_fraction,
            gate_metric=args.gate_metric,
            min_dev_delta=args.min_dev_delta,
            min_canary_delta=args.min_canary_delta,
            output_dir=args.output_dir,
            feedback_store_path=args.feedback_store,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "materialize-slice-patch":
        payload = materialize_slice_patch_candidate(
            candidate=args.candidate,
            base_profile_id=args.base_profile_id,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-optimizer-gate-run":
        payload = build_optimizer_gate_run_plan(
            context=args.context,
            base_profile_id=args.base_profile_id,
            optimizer=args.optimizer,
            optimizer_gate_plugin_manifests=args.plugin_manifest,
            max_candidates=args.max_candidates,
            execute_runtime_probe=args.execute_runtime_probe,
            output_dir=args.output_dir,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-optimizer-gate-execution-plan":
        payload = build_optimizer_gate_execution_plan(
            optimizer_gate_run=args.run,
            benchmark_id=args.benchmark,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-prompt-profile-registration-plan":
        payload = build_prompt_profile_registration_plan(
            materialization=args.materialization,
            benchmark_id=args.benchmark,
            proposed_profile_id=args.proposed_profile_id,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "register-prompt-profile":
        payload = register_prompt_profile_from_plan(
            registration_plan=args.registration_plan,
            approved=args.approve,
            approved_by=args.approved_by,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-optimizer-gate-execution-preflight":
        payload = build_optimizer_gate_execution_preflight(
            registration_plan=args.registration_plan,
            registered_profile=args.registered_profile,
            registered_profile_id=args.registered_profile_id,
            prompt_leakage_audit=args.prompt_leakage_audit,
            target_smoke=args.target_smoke,
            dev_model_eval=args.dev_model_eval,
            gate_decisions=args.gate_decision,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-registered-profile-execution-bundle":
        payload = build_registered_profile_execution_bundle(
            registration_plan=args.registration_plan,
            registered_profile=args.registered_profile,
            registered_profile_id=args.registered_profile_id,
            prompt_leakage_audit=args.prompt_leakage_audit,
            target_smoke=args.target_smoke,
            dev_model_eval=args.dev_model_eval,
            gate_decisions=args.gate_decision,
            output_dir=args.output_dir,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "run-registered-profile-execution":
        payload = run_registered_profile_execution(
            registration_plan=args.registration_plan,
            registered_profile=args.registered_profile,
            registered_profile_id=args.registered_profile_id,
            prompt_leakage_rows=args.prompt_leakage_rows,
            prompt_leakage_audit=args.prompt_leakage_audit,
            target_smoke=args.target_smoke,
            dev_model_eval=args.dev_model_eval,
            dev_baseline_eval=args.dev_baseline_eval,
            dev_gate_source=args.dev_gate_source,
            model_runtime_preflight=args.model_runtime_preflight,
            execute_model_eval=args.execute_model_eval,
            target_smoke_rows=args.target_smoke_rows,
            dev_model_eval_rows=args.dev_model_eval_rows,
            model_eval_model=args.model_eval_model,
            model_eval_base_url=args.model_eval_base_url,
            model_eval_model_provider=args.model_eval_model_provider,
            model_eval_api_key_env=args.model_eval_api_key_env,
            model_eval_timeout_seconds=args.model_eval_timeout_seconds,
            model_eval_temperature=args.model_eval_temperature,
            model_eval_max_tokens=args.model_eval_max_tokens,
            model_eval_judge_mode=args.model_eval_judge_mode,
            gate_decisions=args.gate_decision,
            benchmark_id=args.benchmark,
            output_dir=args.output_dir,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-registered-profile-canary-preflight":
        payload = build_registered_profile_canary_preflight(
            registered_profile_execution_run=args.registered_profile_execution_run,
            canary_rows=args.canary_rows,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "run-registered-profile-canary-execution":
        payload = run_registered_profile_canary_execution(
            registered_profile_execution_run=args.registered_profile_execution_run,
            registered_profile=args.registered_profile,
            model_runtime_preflight=args.model_runtime_preflight,
            execute_canary=args.execute_canary,
            canary_rows=args.canary_rows,
            model_eval_model=args.model_eval_model,
            model_eval_base_url=args.model_eval_base_url,
            model_eval_model_provider=args.model_eval_model_provider,
            model_eval_api_key_env=args.model_eval_api_key_env,
            model_eval_timeout_seconds=args.model_eval_timeout_seconds,
            model_eval_temperature=args.model_eval_temperature,
            model_eval_max_tokens=args.model_eval_max_tokens,
            model_eval_judge_mode=args.model_eval_judge_mode,
            min_canary_row_count=args.min_canary_row_count,
            max_canary_failure_count=args.max_canary_failure_count,
            max_canary_runtime_error_count=args.max_canary_runtime_error_count,
            max_canary_empty_output_count=args.max_canary_empty_output_count,
            output_dir=args.output_dir,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-registered-profile-canary-result-gate":
        payload = build_registered_profile_canary_result_gate(
            registered_profile_canary_execution=(
                args.registered_profile_canary_execution
            ),
            output_path=args.output,
            min_canary_row_count=args.min_canary_row_count,
            max_failure_count=args.max_failure_count,
            max_runtime_error_count=args.max_runtime_error_count,
            max_empty_output_count=args.max_empty_output_count,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-registered-profile-outcome-schedule":
        payload = build_registered_profile_outcome_schedule(
            registered_profile_canary_result_gate=(
                args.registered_profile_canary_result_gate
            ),
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-optimizer-gate-scheduler-plan":
        payload = build_optimizer_gate_scheduler_plan(
            registered_profile_outcome_schedule=(
                args.registered_profile_outcome_schedule
            ),
            model_runtime_preflight=args.model_runtime_preflight,
            slice_optimizer_selection=args.slice_optimizer_selection,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "run-optimizer-gate-scheduler-action":
        payload = run_optimizer_gate_scheduler_action(
            optimizer_gate_scheduler_plan=args.optimizer_gate_scheduler_plan,
            action_name=args.action_name,
            model=args.model,
            base_url=args.base_url,
            model_provider=args.model_provider,
            api_key_env=args.api_key_env,
            execute_probe=args.execute_probe,
            timeout_seconds=args.timeout_seconds,
            max_tokens=args.max_tokens,
            apply_no_think=args.apply_no_think,
            context=args.context,
            optimizer_gate_plugin_manifests=args.plugin_manifest,
            max_candidates=args.max_candidates,
            experiment_action_allowlist=args.experiment_action_allowlist,
            experiment_budget=(
                {"max_experiment_actions": args.experiment_max_actions}
                if args.experiment_max_actions is not None
                else None
            ),
            canary_runner_bundle=args.canary_runner_bundle,
            output_dir=args.output_dir,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "run-optimizer-gate-scheduler-loop":
        payload = run_optimizer_gate_scheduler_loop(
            optimizer_gate_scheduler_plan=args.optimizer_gate_scheduler_plan,
            model=args.model,
            base_url=args.base_url,
            model_provider=args.model_provider,
            api_key_env=args.api_key_env,
            execute_probe=args.execute_probe,
            timeout_seconds=args.timeout_seconds,
            max_tokens=args.max_tokens,
            apply_no_think=args.apply_no_think,
            context=args.context,
            optimizer_gate_plugin_manifests=args.plugin_manifest,
            max_candidates=args.max_candidates,
            max_actions=args.max_actions,
            auto_refresh_scheduler_plan=args.auto_refresh_scheduler_plan,
            experiment_action_allowlist=args.experiment_action_allowlist,
            experiment_budget=(
                {"max_experiment_actions": args.experiment_max_actions}
                if args.experiment_max_actions is not None
                else None
            ),
            canary_runner_bundle=args.canary_runner_bundle,
            output_dir=args.output_dir,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-optimizer-gate-scheduler-handoff":
        payload = build_optimizer_gate_scheduler_handoff(
            optimizer_gate_scheduler_loop=args.optimizer_gate_scheduler_loop,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-optimizer-gate-canary-runner-bundle":
        payload = build_optimizer_gate_canary_runner_bundle(
            optimizer_gate_scheduler_handoff=args.optimizer_gate_scheduler_handoff,
            registered_profile_execution_run=args.registered_profile_execution_run,
            registered_profile=args.registered_profile,
            canary_rows=args.canary_rows,
            model_runtime_preflight=args.model_runtime_preflight,
            execute_canary=not args.no_execute_canary_flag,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "run-optimizer-gate-canary-runner-bundle":
        payload = run_optimizer_gate_canary_runner_bundle(
            optimizer_gate_canary_runner_bundle=args.optimizer_gate_canary_runner_bundle,
            model_eval_model=args.model,
            model_eval_base_url=args.base_url,
            model_eval_model_provider=args.model_provider,
            model_eval_api_key_env=args.api_key_env,
            model_eval_timeout_seconds=args.timeout_seconds,
            model_eval_temperature=args.temperature,
            model_eval_max_tokens=args.max_tokens,
            model_eval_judge_mode=args.judge_mode,
            min_canary_row_count=args.min_canary_row_count,
            max_failure_count=args.max_failure_count,
            max_runtime_error_count=args.max_runtime_error_count,
            max_empty_output_count=args.max_empty_output_count,
            output_dir=args.output_dir,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-optimizer-gate-promotion-review-queue":
        payload = build_optimizer_gate_promotion_review_queue(
            optimizer_gate_scheduler_handoff=args.optimizer_gate_scheduler_handoff,
            canary_result_gate=args.canary_result_gate,
            promotion_policy=args.promotion_policy,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-optimizer-gate-human-promotion-approval":
        payload = build_optimizer_gate_human_promotion_approval(
            promotion_review_queue=args.promotion_review_queue,
            approved=args.decision == "approve",
            approved_by=args.approved_by,
            decision_notes=args.decision_notes,
            reviewed_at=args.reviewed_at,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "run-optimizer-gate-local-promotion-action":
        payload = run_optimizer_gate_local_promotion_action(
            human_promotion_approval=args.human_promotion_approval,
            execute_promotion=args.execute_promotion,
            promoted_by=args.promoted_by,
            promoted_at=args.promoted_at,
            profile_registry=args.profile_registry,
            registry_output_path=args.registry_output,
            rollback_output_path=args.rollback_output,
            audit_log_path=args.audit_log,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "run-optimizer-gate-local-promotion-rollback":
        payload = run_optimizer_gate_local_promotion_rollback(
            rollback_record=args.rollback_record,
            rolled_back_by=args.rolled_back_by,
            rolled_back_at=args.rolled_back_at,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "run-optimizer-gate-external-submission-action":
        payload = run_optimizer_gate_external_submission_action(
            local_promotion_action=args.local_promotion_action,
            benchmark_id=args.benchmark_id,
            submission_url=args.submission_url,
            submission_payload=_load_optional_json_object(args.submission_payload),
            submitted_by=args.submitted_by,
            execute_submission=args.execute_submission,
            timeout_seconds=args.timeout_seconds,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-optimizer-gate-official-submission":
        payload = build_optimizer_gate_official_submission(
            local_promotion_action=args.local_promotion_action,
            benchmark_id=args.benchmark_id,
            submission_id=args.submission_id,
            public_url=args.public_url,
            submitted_by=args.submitted_by,
            submitted_at=args.submitted_at,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "fetch-optimizer-gate-public-result":
        payload = fetch_optimizer_gate_public_result(
            public_result_url=args.public_result_url,
            timeout_seconds=args.timeout_seconds,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "verify-optimizer-gate-public-result":
        payload = verify_optimizer_gate_public_result(
            official_submission=args.official_submission,
            public_result=args.public_result,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-optimizer-gate-official-claim":
        payload = build_optimizer_gate_official_claim(
            public_result_verifier=args.public_result_verifier,
            claim_id=args.claim_id,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "run-optimizer-gate-executable-loop":
        payload = run_optimizer_gate_executable_loop(
            canary_result_gate=args.canary_result_gate,
            slice_repair_context=args.slice_repair_context,
            candidate_optimizers=args.candidate_optimizer,
            optimizer_gate_plugin_manifests=args.plugin_manifest,
            base_profile_id=args.base_profile_id,
            proposed_profile_prefix=args.proposed_profile_prefix,
            max_iterations=args.max_iterations,
            max_candidates=args.max_candidates,
            execute_optimizer=args.execute_optimizer,
            optimizer_model=args.optimizer_model,
            optimizer_base_url=args.optimizer_base_url,
            optimizer_api_key=args.optimizer_api_key,
            optimizer_timeout_seconds=args.optimizer_timeout_seconds,
            optimizer_temperature=args.optimizer_temperature,
            optimizer_max_tokens=args.optimizer_max_tokens,
            auto_approve_registration=args.auto_approve_registration,
            approved_by=args.approved_by,
            prompt_leakage_rows=args.prompt_leakage_rows,
            prompt_leakage_audit=args.prompt_leakage_audit,
            target_smoke=args.target_smoke,
            dev_model_eval=args.dev_model_eval,
            dev_baseline_eval=args.dev_baseline_eval,
            dev_gate_source=args.dev_gate_source,
            model_runtime_preflight=args.model_runtime_preflight,
            execute_model_eval=args.execute_model_eval,
            target_smoke_rows=args.target_smoke_rows,
            dev_model_eval_rows=args.dev_model_eval_rows,
            execute_canary_runner=args.execute_canary_runner,
            canary_rows=args.canary_rows,
            model_eval_model=args.model_eval_model,
            model_eval_base_url=args.model_eval_base_url,
            model_eval_model_provider=args.model_eval_model_provider,
            model_eval_api_key_env=args.model_eval_api_key_env,
            model_eval_timeout_seconds=args.model_eval_timeout_seconds,
            model_eval_temperature=args.model_eval_temperature,
            model_eval_max_tokens=args.model_eval_max_tokens,
            model_eval_judge_mode=args.model_eval_judge_mode,
            min_canary_row_count=args.min_canary_row_count,
            max_canary_failure_count=args.max_canary_failure_count,
            max_canary_runtime_error_count=args.max_canary_runtime_error_count,
            max_canary_empty_output_count=args.max_canary_empty_output_count,
            output_dir=args.output_dir,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-model-runtime-preflight":
        payload = build_model_runtime_preflight(
            model=args.model,
            base_url=args.base_url,
            model_provider=args.model_provider,
            api_key_env=args.api_key_env,
            execute_probe=args.execute_probe,
            timeout_seconds=args.timeout_seconds,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            min_max_tokens=args.min_max_tokens,
            apply_no_think=args.apply_no_think,
            probe_prompt=args.probe_prompt,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-optimizer-gate-system-spec":
        payload = build_optimizer_gate_system_spec(
            plugin_manifests=args.plugin_manifest,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-gate-policy-input":
        payload = build_gate_policy_input(
            metric_table=args.metric_table,
            slice_table=args.slice_table,
            policy_id=args.policy_id,
            task_family=args.task_family,
            split=args.split,
            quality_constraints=_load_optional_json_object(args.quality_constraints),
            execution_quality=_load_optional_json_object(args.execution_quality),
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "evaluate-gate-policy":
        payload = evaluate_gate_policy(
            gate_input=args.gate_input,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-gate-policy-composition":
        payload = build_gate_policy_composition(
            decisions=list(args.decision),
            composition_id=args.composition_id,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-gate-policy-graph":
        payload = build_gate_policy_graph(
            graph_id=args.graph_id,
            required_policies=args.required_policy,
            optional_policies=args.optional_policy,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "evaluate-gate-policy-graph":
        payload = evaluate_gate_policy_graph(
            policy_graph=args.policy_graph,
            decisions=list(args.decision),
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "evaluate-slice-gate":
        if args.slice_matrix is None and (
            args.baseline_report is None or args.candidate_report is None
        ):
            print(
                "--slice-matrix or --baseline-report and --candidate-report are required",
                file=sys.stderr,
            )
            return 1
        payload = evaluate_slice_gate(
            slice_matrix=args.slice_matrix,
            baseline_report=args.baseline_report,
            candidate_report=args.candidate_report,
            candidate_evaluation=args.candidate_evaluation,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "evaluate-slice-variance-gate":
        payload = evaluate_slice_variance_gate(
            slice_matrices=list(args.slice_matrix or []),
            paired_repeat_manifest=args.paired_repeat_manifest,
            min_repeats=args.min_repeats,
            regression_delta_threshold=args.regression_delta_threshold,
            stable_support_ratio=args.stable_support_ratio,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-paired-repeat-manifest":
        payload = build_paired_repeat_manifest(
            slice_matrices=list(args.slice_matrix),
            task_family=args.task_family,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "record-slice-patch-outcome":
        payload = record_slice_patch_outcome(
            candidate=args.candidate,
            materialization=args.materialization,
            gate_decision=args.gate_decision,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-slice-optimizer-selection":
        payload = build_slice_optimizer_selection(
            outcomes=args.outcomes,
            target_scope=args.target_scope,
            failure_labels=list(args.failure_label),
            candidate_optimizers=list(args.candidate_optimizer),
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-cp-bench-effectiveness-bundle":
        payload = build_cp_bench_proposal_effectiveness_bundle(
            round_reports=list(args.round_report),
            output_dir=args.output_dir,
            control_label=args.control_label,
            treatment_label=args.treatment_label,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-fasttext-effectiveness-bundle":
        payload = build_fasttext_proposal_effectiveness_bundle(
            multi_round_reports=list(args.multi_round_report),
            output_dir=args.output_dir,
            control_label=args.control_label,
            treatment_label=args.treatment_label,
            include_failed_rounds=not args.completed_only,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-smol-worldcup-effectiveness-bundle":
        payload = build_smol_worldcup_proposal_effectiveness_bundle(
            control_reports=list(args.control_report),
            treatment_reports=list(args.treatment_report),
            output_dir=args.output_dir,
            control_label=args.control_label,
            treatment_label=args.treatment_label,
            split_filter=args.split_filter,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-smol-worldcup-result-analysis":
        payload = build_smol_worldcup_result_analysis(
            control_reports=list(args.control_report),
            treatment_reports=list(args.treatment_report),
            output_dir=args.output_dir,
            split_filter=args.split_filter,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-smol-worldcup-confidence-variance-gate":
        payload = build_smol_worldcup_confidence_variance_gate(
            aa_result_analysis=args.aa_result_analysis,
            candidate_result_analyses=list(args.candidate_result_analysis),
            output_path=args.output,
            confidence_category=args.confidence_category,
            min_abs_score_delta=args.min_abs_score_delta,
            aa_coverage_ratio=args.aa_coverage_ratio,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-smol-worldcup-cached-confidence-scoring-gate":
        payload = build_smol_worldcup_cached_confidence_scoring_gate(
            model_eval_reports=list(args.model_eval_report),
            output_path=args.output,
            confidence_category=args.confidence_category,
            min_repeats=args.min_repeats,
            max_score_range=args.max_score_range,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-real-paper-effectiveness-bundle":
        payload = build_real_paper_proposal_effectiveness_bundle(
            proof_archives=list(args.proof_archive),
            output_dir=args.output_dir,
            control_label=args.control_label,
            treatment_label=args.treatment_label,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-cross-task-effectiveness-summary":
        payload = build_cross_task_proposal_effectiveness_summary(
            effectiveness_reports=list(args.effectiveness_report),
            output_dir=args.output_dir,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-effectiveness-claim-audit":
        payload = build_proposal_effectiveness_claim_audit(
            cross_task_summary=args.cross_task_summary,
            output_dir=args.output_dir,
            minimum_task_count=args.min_task_count,
            minimum_positive_task_families=args.min_positive_task_families,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-mixed-signal-audit":
        payload = build_mixed_signal_proposal_effectiveness_audit(
            effectiveness_reports=list(args.effectiveness_report),
            output_dir=args.output_dir,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-smol-promotion-gate":
        payload = build_smol_worldcup_promotion_gate(
            dev_effectiveness_report=args.dev_effectiveness_report,
            canary_effectiveness_report=args.canary_effectiveness_report,
            output_dir=args.output_dir,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-smol-canary-failure-slice-audit":
        payload = build_smol_worldcup_canary_failure_slice_audit(
            canary_effectiveness_report=args.canary_effectiveness_report,
            promotion_gate=args.promotion_gate,
            control_outcomes=args.control_outcomes,
            treatment_outcomes=args.treatment_outcomes,
            output_dir=args.output_dir,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-smol-canary-control-arm-handoff":
        payload = build_smol_worldcup_canary_control_arm_handoff(
            failure_slice_audit=args.failure_slice_audit,
            output_dir=args.output_dir,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-smol-canary-control-arm-execution-bundle":
        payload = build_smol_worldcup_canary_control_arm_execution_bundle(
            handoff=args.handoff,
            output_dir=args.output_dir,
            current_report=args.current_report,
            baseline_report=args.baseline_report,
            target_prompt_profile=args.target_prompt_profile,
            evidence_root=args.evidence_root,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-smol-promotion-gate-refresh":
        payload = build_smol_worldcup_promotion_gate_refresh(
            previous_gate=args.previous_gate,
            proposal_round_summary=args.proposal_round_summary,
            output_dir=args.output_dir,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-failure-context":
        payload = build_failure_driven_proposal_context(
            objective=args.objective,
            failure_records=args.failures,
            pattern_memory=args.pattern_memory,
            output_path=args.output,
            max_proposals=args.max_proposals,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "generate-proposals":
        payload = generate_failure_driven_proposals(
            context=args.context,
            output_path=args.output,
            preferred_change_surfaces=args.preferred_change_surface,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "rank":
        payload = rank_failure_driven_proposals(
            proposals=_proposal_rank_input(args.proposals),
            failure_records=args.failures,
            pattern_memory=args.pattern_memory,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "handoff":
        payload = build_failure_driven_proposal_handoff(
            context=args.context,
            ranking=args.ranking,
            output_dir=args.output_dir,
            max_selected=args.max_selected,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "build-client-templates":
        payload = build_failure_driven_client_proposal_templates(
            handoff=args.handoff,
            output_dir=args.output_dir,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "bridge-to-memory-card":
        payload = bridge_failure_driven_outcome_to_memory_card(
            outcome=args.outcome,
            handoff=args.handoff,
            output_path=args.output,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    if args.proposal_command == "evaluate-effectiveness":
        payload = evaluate_failure_driven_proposal_effectiveness(
            control_outcomes=args.control_outcomes,
            treatment_outcomes=args.treatment_outcomes,
            output_path=args.output,
            control_label=args.control_label,
            treatment_label=args.treatment_label,
            overwrite=args.force,
        )
        _print_json_payload(payload, compact=args.json)
        return 0
    return 2


def _proposal_memory_query_from_args(args: argparse.Namespace) -> dict[str, str] | None:
    query = {
        "query": args.memory_query,
        "paper_id": args.memory_paper_id,
        "dataset": args.memory_dataset,
        "metric_name": args.memory_metric_name,
        "patch_type": args.memory_patch_type,
        "failure_category": args.memory_failure_category,
    }
    compact = {key: value for key, value in query.items() if value}
    return compact or None


def _proposal_rank_input(path: Path) -> Path | list[dict[str, object]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict) and isinstance(payload.get("proposals"), list):
        proposals = [item for item in payload["proposals"] if isinstance(item, dict)]
        if proposals:
            return proposals
    return path


def _proposal_diversity_constraint_from_args(
    args: argparse.Namespace,
) -> dict[str, int] | None:
    if args.diversity_max_per_family is None:
        return None
    return {"max_per_family": args.diversity_max_per_family}


def _load_optional_json_object(path: Path | None) -> dict[str, object] | None:
    if path is None:
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("JSON file must contain an object")
    return payload


def _load_json_object_argument(raw: str) -> dict[str, object]:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise SystemExit("JSON argument must contain an object")
    return payload


def _load_method_search_study_argument(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise SystemExit("study JSON must contain an object")
    nested = payload.get("study")
    if isinstance(nested, dict):
        return nested
    return payload


def _method_search_trial_from_study(
    study: dict[str, object],
    trial_id: str | None,
) -> dict[str, object]:
    trials = study.get("trials")
    if not isinstance(trials, list):
        raise SystemExit("study JSON does not contain trials")
    for trial in trials:
        if isinstance(trial, dict) and trial.get("trial_id") == trial_id:
            return trial
    raise SystemExit(f"trial_id not found: {trial_id}")


def _print_json_payload(payload: dict[str, object], *, compact: bool) -> None:
    if compact:
        print(json.dumps(payload, ensure_ascii=False))
    else:
        print(json.dumps(payload, indent=2, ensure_ascii=False))


def _run_init_mcp_config(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    python_executable = str(args.python)
    server_name = args.server_name or _default_mcp_server_name(args.client)
    payload = render_mcp_config(
        client=args.client,
        project_root=project_root,
        python_executable=python_executable,
        server_name=server_name,
    )
    if args.output:
        output = Path(args.output).expanduser().resolve()
        if output.exists() and not args.force:
            print(f"Refusing to overwrite existing file: {output}", file=sys.stderr)
            return 1
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
        return 0
    print(payload)
    return 0


def _run_init_skills(args: argparse.Namespace) -> int:
    project_root = Path(args.project_root).expanduser().resolve()
    target_root = (
        Path(args.target_root).expanduser().resolve()
        if args.target_root
        else _default_skill_root(args.client)
    )
    try:
        payload = install_skill_package(
            client=args.client,
            project_root=project_root,
            target_root=target_root,
            force=args.force,
            dry_run=args.dry_run,
        )
    except FileExistsError as exc:
        print(
            f"Refusing to overwrite existing skill: {exc.filename or exc}",
            file=sys.stderr,
        )
        return 1
    except FileNotFoundError as exc:
        print(f"Missing repository skill package: {exc.filename or exc}", file=sys.stderr)
        return 1
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _run_feedback_bundle(args: argparse.Namespace) -> int:
    bundle = build_feedback_bundle(
        project_root=WORKSPACE_ROOT,
        runtime_root=args.runtime_root,
        task_id=args.task_id,
        log_lines=args.log_lines,
        python_executable=args.python,
    )
    payload = write_feedback_bundle(bundle, args.output_dir)
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 0


def _run_hf_eval(args: argparse.Namespace) -> int:
    if args.hf_eval_command == "shortlist":
        payload = load_hf_eval_targets(args.shortlist)
        targets = select_hf_eval_targets(
            payload,
            task_family=args.task_family,
            limit=args.limit,
        )
        output = {
            "status": "listed",
            "official_scores_claimed": False,
            "target_count": len(targets),
            "selection_policy": payload.get("selection_policy", {}),
            "targets": targets,
        }
        if args.json:
            print(json.dumps(output, ensure_ascii=False))
        else:
            print(json.dumps(output, indent=2, ensure_ascii=False))
        return 0
    if args.hf_eval_command == "plan":
        payload = write_hf_external_eval_plan(
            args.output_dir,
            shortlist_path=args.shortlist,
            target_id=args.target_id,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") == "written" else 1
    if args.hf_eval_command == "arguard-b1-verify":
        payload = write_arguard_b1_live_verification(
            args.output_dir,
            timeout_seconds=args.timeout_seconds,
            include_raw=not args.no_raw,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") == "written" else 1
    if args.hf_eval_command == "cp-bench-verify":
        payload = write_cp_bench_live_verification(
            args.output_dir,
            timeout_seconds=args.timeout_seconds,
            include_raw=not args.no_raw,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") == "written" else 1
    if args.hf_eval_command == "cp-bench-baseline":
        payload = write_cp_bench_local_baseline(
            args.output_dir,
            limit=args.limit,
            framework=args.framework,
            dataset_version=args.dataset_version,
            dry_run=args.dry_run,
            timeout_seconds=args.timeout_seconds,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") in {
            "written",
            "blocked_missing_dependencies",
            "blocked_evaluator_unavailable",
            "blocked_dataset_unavailable",
            "invalid_submission",
            "failed_timeout",
            "failed_missing_summary",
            "failed_nonzero_exit",
        } else 1
    if args.hf_eval_command == "cp-bench-proposal-round":
        payload = run_cp_bench_proposal_round(
            args.baseline_report,
            args.proposal,
            args.output_dir,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") in {
            "rejected_by_guard",
            "blocked_pending_local_eval",
            "ready_for_guarded_execution",
        } else 1
    if args.hf_eval_command == "cp-bench-candidate-round":
        payload = run_cp_bench_candidate_round(
            args.baseline_report,
            args.submission,
            args.output_dir,
            proposal_path=args.proposal,
            framework=args.framework,
            dataset_version=args.dataset_version,
            timeout_seconds=args.timeout_seconds,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") in {
            "improved",
            "no_gain",
            "regressed",
            "candidate_eval_inconclusive",
            "candidate_eval_failed",
            "blocked_pending_baseline",
            "rejected_by_guard",
        } else 1
    if args.hf_eval_command == "cp-bench-proposal-context":
        payload = write_cp_bench_proposal_context(
            args.current_report,
            args.output_dir,
            max_proposals=args.max_proposals,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") in {
            "ready_for_client_proposal",
            "ready_for_scale_up_proposal",
        } else 1
    if args.hf_eval_command == "cp-bench-client-candidate":
        payload = write_cp_bench_client_candidate_submission(
            args.output_dir,
            limit=args.limit,
            dataset_version=args.dataset_version,
            strategy=args.strategy,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") in {
            "generated",
            "partial_generated",
            "fallback_only",
        } else 1
    if args.hf_eval_command == "cp-bench-submission-gate":
        payload = write_cp_bench_submission_gate(
            args.submission,
            args.output_dir,
            source_report_path=args.source_report,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") in {"written", "invalid_submission"} else 1
    if args.hf_eval_command == "smol-worldcup-verify":
        payload = write_smol_worldcup_live_verification(
            args.output_dir,
            timeout_seconds=args.timeout_seconds,
            include_raw=not args.no_raw,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") == "written" else 1
    if args.hf_eval_command == "smol-worldcup-leakage-audit":
        payload = write_smol_worldcup_prompt_leakage_audit(
            args.output_dir,
            timeout_seconds=args.timeout_seconds,
            page_size=args.page_size,
            limit=args.limit,
            prompt_profile=args.prompt_profile,
            prompt_profile_registration=args.prompt_profile_registration,
            evaluation_split=args.evaluation_split,
            canary_fraction=args.canary_fraction,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") == "written" else 1
    if args.hf_eval_command == "smol-worldcup-baseline":
        payload = write_smol_worldcup_baseline(
            args.output_dir,
            timeout_seconds=args.timeout_seconds,
            page_size=args.page_size,
            strategy=args.strategy,
            limit=args.limit,
            evaluation_split=args.evaluation_split,
            canary_fraction=args.canary_fraction,
            model_size_billion=args.model_size_billion,
            estimated_ram_gb=args.estimated_ram_gb,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") == "written" else 1
    if args.hf_eval_command == "smol-worldcup-model-eval":
        model_eval_base_url = args.base_url
        if (
            args.model_provider == "deepseek"
            and model_eval_base_url == "http://127.0.0.1:1234/v1"
        ):
            model_eval_base_url = "https://api.deepseek.com"
        payload = write_smol_worldcup_model_eval(
            args.output_dir,
            timeout_seconds=args.timeout_seconds,
            page_size=args.page_size,
            limit=args.limit,
            dataset_offset=args.dataset_offset,
            row_ids=args.row_id,
            model=args.model,
            base_url=model_eval_base_url,
            model_provider=args.model_provider,
            api_key_env=args.api_key_env,
            thinking_mode=args.thinking_mode,
            reasoning_effort=args.reasoning_effort,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            round_id=args.round_id,
            prompt_profile=args.prompt_profile,
            prompt_profile_registration=args.prompt_profile_registration,
            evaluation_split=args.evaluation_split,
            canary_fraction=args.canary_fraction,
            cached_response_prediction_path=args.cached_response_prediction_path,
            require_cached_responses=args.require_cached_responses,
            judge_mode=args.judge_mode,
            judge_model=args.judge_model,
            judge_base_url=args.judge_base_url,
            model_size_billion=args.model_size_billion,
            estimated_ram_gb=args.estimated_ram_gb,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") == "written" else 1
    if args.hf_eval_command == "smol-worldcup-proposal-round":
        model_eval_base_url = args.base_url
        if (
            args.model_provider == "deepseek"
            and model_eval_base_url == "http://127.0.0.1:1234/v1"
        ):
            model_eval_base_url = "https://api.deepseek.com"
        proposal = json.loads(args.proposal.read_text(encoding="utf-8"))
        if not isinstance(proposal, dict):
            print("proposal JSON must be an object", file=sys.stderr)
            return 1
        payload = run_smol_worldcup_proposal_round(
            proposal=proposal,
            output_dir=args.output_dir,
            current_report=args.current_report,
            baseline_report=args.baseline_report,
            timeout_seconds=args.timeout_seconds,
            page_size=args.page_size,
            limit=args.limit,
            dataset_offset=args.dataset_offset,
            model=args.model,
            base_url=model_eval_base_url,
            model_provider=args.model_provider,
            api_key_env=args.api_key_env,
            thinking_mode=args.thinking_mode,
            reasoning_effort=args.reasoning_effort,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
            round_id=args.round_id,
            prompt_profile=args.prompt_profile,
            evaluation_split=args.evaluation_split,
            canary_fraction=args.canary_fraction,
            judge_mode=args.judge_mode,
            judge_model=args.judge_model,
            judge_base_url=args.judge_base_url,
            model_size_billion=args.model_size_billion,
            estimated_ram_gb=args.estimated_ram_gb,
            allowed_change_surfaces=args.allowed_change_surface,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") == "completed" else 1
    if args.hf_eval_command == "smol-worldcup-rescore":
        payload = write_smol_worldcup_rescore(
            args.output_dir,
            prediction_path=args.prediction_path,
            source_rows_path=args.source_rows,
            source_report=args.source_report,
            source_run_id=args.source_run_id,
            timeout_seconds=args.timeout_seconds,
            page_size=args.page_size,
            preserve_llm_judge_scores=not args.rerun_llm_judge_heuristic,
            model_size_billion=args.model_size_billion,
            estimated_ram_gb=args.estimated_ram_gb,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") == "written" else 1
    if args.hf_eval_command == "smol-worldcup-rescore-proof-archive":
        payload = write_smol_worldcup_rescore_proof_archive(
            rescore_dir=args.rescore_dir,
            output_dir=args.output_dir,
            source_report=args.source_report,
            source_prediction_path=args.source_prediction_path,
            source_run_id=args.source_run_id,
            command_lines=args.command_line,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") == "written" else 1
    if args.hf_eval_command == "smol-worldcup-submission-probe":
        payload = write_smol_worldcup_submission_probe(
            args.output_dir,
            timeout_seconds=args.timeout_seconds,
            model_id=args.model,
            include_raw=not args.no_raw,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") == "written" else 1
    return 2


def _run_benchmark(args: argparse.Namespace) -> int:
    if args.benchmark_command == "readiness":
        payload = build_benchmark_readiness()
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if args.benchmark_command == "smoke":
        cmd = [
            args.python,
            str(WORKSPACE_ROOT / "scripts" / "benchmark_adapter_smoke.py"),
            "--runtime-root",
            str(args.runtime_root),
        ]
        if args.json:
            cmd.append("--json")
        return subprocess.call(cmd, cwd=str(WORKSPACE_ROOT))
    if args.benchmark_command == "probe":
        payload = build_official_harness_probe(
            mle_bench_repo=args.mle_bench_repo,
            paperbench_repo=args.paperbench_repo,
            paperbench_data_dir=args.paperbench_data_dir,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if args.benchmark_command == "proof-plan":
        probe = build_official_harness_probe(
            mle_bench_repo=args.mle_bench_repo,
            paperbench_repo=args.paperbench_repo,
            paperbench_data_dir=args.paperbench_data_dir,
        )
        payload = build_public_proof_plan(probe)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if args.benchmark_command == "setup-bundle":
        probe = build_official_harness_probe(
            mle_bench_repo=args.mle_bench_repo,
            paperbench_repo=args.paperbench_repo,
            paperbench_data_dir=args.paperbench_data_dir,
        )
        proof_plan = build_public_proof_plan(probe)
        bundle = build_official_proof_setup_bundle(proof_plan)
        payload = write_official_proof_setup_bundle(bundle, args.output_dir)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if args.benchmark_command == "publication-bundle":
        artifact_manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        bundle = build_proof_publication_bundle(artifact_manifest, args.artifact_root)
        payload = write_proof_publication_bundle(bundle, args.output_dir)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if args.benchmark_command == "archive-proof":
        artifact_manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        bundle = build_proof_archive_bundle(artifact_manifest, args.artifact_root)
        payload = write_proof_archive_bundle(bundle, args.artifact_root, args.output_dir)
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if args.benchmark_command == "mle-workspace":
        payload = materialize_official_mle_agent_workspace(
            competition_id=args.competition_id,
            prepared_competition_dir=args.prepared_competition_dir,
            runtime_root=args.runtime_root,
            workspace_name=args.workspace_name,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if args.benchmark_command == "mle-grade":
        payload = grade_official_mle_submission(
            competition_id=args.competition_id,
            submission_path=args.submission,
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            mlebench_executable=args.mlebench,
            timeout_seconds=args.timeout_seconds,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") == "graded" else 1
    if args.benchmark_command == "mle-round":
        payload = run_official_mle_solver_round(
            competition_id=args.competition_id,
            workspace=args.workspace,
            data_dir=args.data_dir,
            output_dir=args.output_dir,
            mlebench_executable=args.mlebench,
            python_executable=args.python,
            round_id=args.round_id,
            timeout_seconds=args.timeout_seconds,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") == "graded" else 1
    if args.benchmark_command == "mle-patch-round":
        payload = mcp_service.run_official_mle_bench_patch_round_tool({
            "competition_id": args.competition_id,
            "workspace": str(args.workspace),
            "data_dir": str(args.data_dir),
            "mlebench": str(args.mlebench),
            "output_dir": str(args.output_dir),
            "patch": args.patch_file.read_text(encoding="utf-8"),
            "python": args.python,
            "round_id": args.round_id,
            "timeout_seconds": args.timeout_seconds,
        })
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") == "graded" else 1
    if args.benchmark_command == "mle-patch-proof":
        payload = write_official_mle_patch_round_proof_bundle(
            patch_round_report=args.patch_round_report,
            output_dir=args.output_dir,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") == "written" else 1
    if args.benchmark_command == "paperbench-codex-review-bundle":
        payload = write_paperbench_codex_review_bundle(
            run_dir=args.run_dir,
            paper_dir=args.paper_dir,
            output_dir=args.output_dir,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") == "written" else 1
    if args.benchmark_command == "paperbench-codex-review-report":
        payload = write_paperbench_codex_review_report(
            bundle_path=args.bundle,
            review_payload=json.loads(args.review_file.read_text(encoding="utf-8")),
            output_dir=args.output_dir,
        )
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") == "written" else 1
    return 2


def _run_demo(args: argparse.Namespace) -> int:
    if args.demo_command == "list":
        print(json.dumps({"templates": list_demo_templates()}, indent=2, ensure_ascii=False))
        return 0
    if args.demo_command == "init":
        try:
            payload = materialize_demo_template(
                template_name=args.template,
                runtime_root=args.runtime_root,
                project_root=WORKSPACE_ROOT,
                max_experiments=args.max_experiments,
                experiment_duration=args.experiment_duration,
                force=args.force,
            )
        except (FileExistsError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0
    if args.demo_command == "run":
        try:
            payload = run_demo_template(
                template_name=args.template,
                runtime_root=args.runtime_root,
                project_root=WORKSPACE_ROOT,
                max_experiments=args.max_experiments,
                experiment_duration=args.experiment_duration,
                force=args.force,
                python_executable=args.python,
            )
        except (FileExistsError, ValueError) as exc:
            print(str(exc), file=sys.stderr)
            return 1
        if args.json:
            print(json.dumps(payload, ensure_ascii=False))
        else:
            print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if payload.get("status") == "completed" else 1
    return 2


def _add_demo_template_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--template", required=True)
    parser.add_argument("--runtime-root", type=Path, required=True)
    parser.add_argument("--max-experiments", type=int)
    parser.add_argument("--experiment-duration", type=int)
    parser.add_argument("--force", action="store_true")


def install_skill_package(
    client: str,
    project_root: Path,
    target_root: Path,
    force: bool = False,
    dry_run: bool = False,
) -> dict[str, object]:
    """Copy repository-local skills into the selected client skill root."""
    source_root = project_root / "skills"
    skill_items = []
    for name in mcp_service.RECOMMENDED_SKILLS:
        source = source_root / name
        if not (source / "SKILL.md").exists():
            raise FileNotFoundError(str(source / "SKILL.md"))
        target = target_root / name
        if target.exists() and not force and not dry_run:
            raise FileExistsError(str(target))
        skill_items.append({
            "name": name,
            "source_path": str(source),
            "target_path": str(target),
        })

    if not dry_run:
        target_root.mkdir(parents=True, exist_ok=True)
        for item in skill_items:
            source = Path(str(item["source_path"]))
            target = Path(str(item["target_path"]))
            if target.exists():
                shutil.rmtree(target)
            shutil.copytree(source, target)

    return {
        "status": "dry_run" if dry_run else "installed",
        "client": client,
        "source_root": str(source_root),
        "target_root": str(target_root),
        "skills": skill_items,
    }


def render_mcp_config(
    client: str,
    project_root: Path,
    python_executable: str,
    server_name: str,
) -> str:
    """Render a concrete MCP client config for the local checkout."""
    project_root = project_root.expanduser().resolve()
    server_script = project_root / "scripts" / "mcp_server.py"
    env = {
        "PYTHONPATH": _pythonpath_for_project(project_root),
        "ML_RESEARCH_LOOP_PYTHON": python_executable,
    }
    if client == "codex":
        return _render_codex_config(
            server_name=server_name,
            python_executable=python_executable,
            server_script=server_script,
            project_root=project_root,
            env=env,
        )
    if client in {"claude-code", "claude-desktop"}:
        return json.dumps(
            {
                "mcpServers": {
                    server_name: {
                        "type": "stdio",
                        "command": python_executable,
                        "args": [str(server_script)],
                        "env": env,
                    }
                }
            },
            indent=2,
            ensure_ascii=False,
        ) + "\n"
    raise ValueError(f"unsupported MCP client: {client}")


def _render_codex_config(
    server_name: str,
    python_executable: str,
    server_script: Path,
    project_root: Path,
    env: dict[str, str],
) -> str:
    return "\n".join([
        f"[mcp_servers.{server_name}]",
        f"command = {json.dumps(python_executable)}",
        f"args = [{json.dumps(str(server_script))}]",
        f"cwd = {json.dumps(str(project_root))}",
        "startup_timeout_sec = 20",
        "tool_timeout_sec = 3600",
        "",
        f"[mcp_servers.{server_name}.env]",
        f"PYTHONPATH = {json.dumps(env['PYTHONPATH'])}",
        f"ML_RESEARCH_LOOP_PYTHON = {json.dumps(env['ML_RESEARCH_LOOP_PYTHON'])}",
        "",
    ])


def _default_mcp_server_name(client: str) -> str:
    if client == "codex":
        return "mlResearchLoop"
    return "ml-research-loop"


def _default_skill_root(client: str) -> Path:
    if client == "codex":
        return Path.home() / ".codex" / "skills"
    return Path.home() / ".claude" / "skills"


def _pythonpath_for_project(project_root: Path) -> str:
    parts = [str(project_root)]
    parts.extend(str(path) for path in _site_packages_paths(project_root))
    return os.pathsep.join(parts)


def _site_packages_paths(project_root: Path) -> list[Path]:
    site_packages_root = project_root / ".venv" / "lib"
    if not site_packages_root.exists():
        return []
    return sorted(site_packages_root.glob("python*/site-packages"))


def main(argv: list[str] | None = None) -> int:
    """Run the CLI."""
    args = build_parser().parse_args(argv)
    manager = AutoResearchManager()

    if args.command == "run":
        return _run_task(args)
    if args.command == "check":
        return _run_check(args)
    if args.command == "artifacts":
        return _run_artifacts(args)
    if args.command == "memory":
        return _run_memory(args)
    if args.command == "proposal":
        return _run_proposal(args)
    if args.command == "init-mcp-config":
        return _run_init_mcp_config(args)
    if args.command == "init-skills":
        return _run_init_skills(args)
    if args.command == "feedback-bundle":
        return _run_feedback_bundle(args)
    if args.command == "hf-eval":
        return _run_hf_eval(args)
    if args.command == "benchmark":
        return _run_benchmark(args)
    if args.command == "demo":
        return _run_demo(args)
    if args.command == "status":
        print(json.dumps(manager.get_status(args.task_id), indent=2, ensure_ascii=False))
        return 0
    if args.command == "result":
        result = manager.get_result(args.task_id)
        payload = result.to_dict() if result is not None else {
            "task_id": args.task_id,
            "status": "not_ready",
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    return 2


if __name__ == "__main__":
    raise SystemExit(main())
