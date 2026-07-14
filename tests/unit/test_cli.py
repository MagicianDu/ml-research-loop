import json
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sys
import threading

import pytest

from lib.research_memory import ResearchMemoryCard, ResearchMemoryStore
from scripts.cli import build_parser, main


SKILL_NAMES = [
    "ml-research-loop-planner",
    "ml-research-loop-reproduction",
    "ml-research-loop-experiment-optimizer",
    "ml-research-loop-operator",
]


class _QuietSimpleHTTPRequestHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002
        return


def _procedure_memory_card(
    card_id,
    *,
    created_at,
    privacy_scope="public",
):
    return ResearchMemoryCard(
        card_id=card_id,
        memory_type="procedure",
        task_family="cleanup-policy",
        summary=f"{card_id} cleanup policy memory.",
        privacy_scope=privacy_scope,
        allow_private_ingestion=privacy_scope != "public",
        created_at=created_at,
    )


def _serve_directory(directory: Path) -> tuple[ThreadingHTTPServer, threading.Thread]:
    def handler(*args, **kwargs):
        return _QuietSimpleHTTPRequestHandler(
            *args,
            directory=str(directory),
            **kwargs,
        )

    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _serve_submission_endpoint(
    response_payload: dict,
) -> tuple[ThreadingHTTPServer, threading.Thread, list[dict]]:
    requests: list[dict] = []

    class _SubmissionHandler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):  # noqa: A002
            return

        def do_POST(self):  # noqa: N802
            body = self.rfile.read(int(self.headers.get("Content-Length", "0") or 0))
            requests.append({
                "path": self.path,
                "payload": json.loads(body.decode("utf-8")),
            })
            encoded = json.dumps(response_payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

    server = ThreadingHTTPServer(("127.0.0.1", 0), _SubmissionHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, requests


def test_parser_has_run_status_result_subcommands():
    parser = build_parser()

    run_args = parser.parse_args(["run", "--task-config", "tasks/demo.json"])
    status_args = parser.parse_args(["status", "demo"])
    result_args = parser.parse_args(["result", "demo"])
    check_args = parser.parse_args(["check", "--json"])
    artifacts_args = parser.parse_args(["artifacts", "list", "--runtime-root", "/tmp/runtime"])
    init_args = parser.parse_args(["init-mcp-config", "--client", "codex"])
    skills_args = parser.parse_args(["init-skills", "--client", "codex"])
    feedback_args = parser.parse_args([
        "feedback-bundle",
        "--runtime-root",
        "/tmp/runtime",
        "--task-id",
        "demo",
    ])
    hf_eval_smol_verify_args = parser.parse_args([
        "hf-eval",
        "smol-worldcup-verify",
        "--output-dir",
        "/tmp/hf-smol-p0",
        "--timeout-seconds",
        "10",
        "--json",
    ])
    hf_eval_cp_bench_verify_args = parser.parse_args([
        "hf-eval",
        "cp-bench-verify",
        "--output-dir",
        "/tmp/hf-cp-bench-p0",
        "--timeout-seconds",
        "10",
        "--no-raw",
        "--json",
    ])
    hf_eval_arguard_b1_verify_args = parser.parse_args([
        "hf-eval",
        "arguard-b1-verify",
        "--output-dir",
        "/tmp/arguard-b1-p0",
        "--timeout-seconds",
        "11",
        "--no-raw",
        "--json",
    ])
    hf_eval_cp_bench_baseline_args = parser.parse_args([
        "hf-eval",
        "cp-bench-baseline",
        "--output-dir",
        "/tmp/hf-cp-bench-p1",
        "--limit",
        "1",
        "--framework",
        "CPMpy",
        "--timeout-seconds",
        "7",
        "--dry-run",
        "--json",
    ])
    hf_eval_cp_bench_proposal_args = parser.parse_args([
        "hf-eval",
        "cp-bench-proposal-round",
        "--baseline-report",
        "/tmp/cp-baseline.json",
        "--proposal",
        "/tmp/cp-proposal.json",
        "--output-dir",
        "/tmp/hf-cp-bench-proposal",
        "--json",
    ])
    hf_eval_cp_bench_candidate_args = parser.parse_args([
        "hf-eval",
        "cp-bench-candidate-round",
        "--baseline-report",
        "/tmp/cp-baseline.json",
        "--submission",
        "/tmp/cp-submission.jsonl",
        "--proposal",
        "/tmp/cp-proposal.json",
        "--output-dir",
        "/tmp/hf-cp-bench-candidate",
        "--framework",
        "CPMpy",
        "--timeout-seconds",
        "9",
        "--json",
    ])
    hf_eval_cp_bench_context_args = parser.parse_args([
        "hf-eval",
        "cp-bench-proposal-context",
        "--current-report",
        "/tmp/cp-candidate-report.json",
        "--output-dir",
        "/tmp/hf-cp-bench-proposal-context",
        "--max-proposals",
        "2",
        "--json",
    ])
    hf_eval_cp_bench_client_candidate_args = parser.parse_args([
        "hf-eval",
        "cp-bench-client-candidate",
        "--output-dir",
        "/tmp/hf-cp-bench-p13-client-candidate",
        "--limit",
        "10",
        "--strategy",
        "handcrafted-small-cpmpy-v1",
        "--dataset-version",
        "verified",
        "--json",
    ])
    hf_eval_cp_bench_gate_args = parser.parse_args([
        "hf-eval",
        "cp-bench-submission-gate",
        "--submission",
        "/tmp/submission.jsonl",
        "--source-report",
        "/tmp/cp-report.json",
        "--output-dir",
        "/tmp/hf-cp-bench-gate",
        "--json",
    ])
    hf_eval_smol_baseline_args = parser.parse_args([
        "hf-eval",
        "smol-worldcup-baseline",
        "--output-dir",
        "/tmp/hf-smol-p1",
        "--limit",
        "25",
        "--evaluation-split",
        "dev",
        "--canary-fraction",
        "0.2",
        "--json",
    ])
    hf_eval_smol_leakage_audit_args = parser.parse_args([
        "hf-eval",
        "smol-worldcup-leakage-audit",
        "--output-dir",
        "/tmp/hf-smol-audit",
        "--prompt-profile",
        "p3-dev-v2",
        "--prompt-profile-registration",
        "/tmp/prompt-profile-registration.json",
        "--evaluation-split",
        "canary",
        "--json",
    ])
    hf_eval_smol_model_eval_args = parser.parse_args([
        "hf-eval",
        "smol-worldcup-model-eval",
        "--output-dir",
        "/tmp/hf-smol-p2",
        "--model",
        "deepseek-v4-flash",
        "--model-provider",
        "deepseek",
        "--api-key-env",
        "DEEPSEEK_API_KEY",
        "--thinking-mode",
        "enabled",
        "--reasoning-effort",
        "high",
        "--limit",
        "4",
        "--dataset-offset",
        "12",
        "--row-id",
        "S1-H3-024",
        "--row-id",
        "S1-H2-012",
        "--prompt-profile",
        "p3-v7-metacognition-textgrad-pw-ar-v3",
        "--prompt-profile-registration",
        "/tmp/prompt-profile-registration.json",
        "--evaluation-split",
        "canary",
        "--judge-mode",
        "openai-compatible",
        "--judge-model",
        "google/gemma-4-31b",
        "--cached-response-prediction-path",
        "/tmp/hf-smol-p2/prediction.jsonl",
        "--require-cached-responses",
        "--json",
    ])
    hf_eval_smol_rescore_args = parser.parse_args([
        "hf-eval",
        "smol-worldcup-rescore",
        "--prediction-path",
        "/tmp/hf-smol-p2/prediction.jsonl",
        "--output-dir",
        "/tmp/hf-smol-rescore",
        "--source-report",
        "/tmp/hf-smol-p2/smol-worldcup-model-eval-report.json",
        "--source-run-id",
        "round-004-dev-v2",
        "--json",
    ])
    hf_eval_smol_rescore_archive_args = parser.parse_args([
        "hf-eval",
        "smol-worldcup-rescore-proof-archive",
        "--rescore-dir",
        "/tmp/hf-smol-rescore",
        "--output-dir",
        "/tmp/hf-smol-rescore-proof",
        "--source-report",
        "/tmp/hf-smol-p2/smol-worldcup-model-eval-report.json",
        "--source-prediction-path",
        "/tmp/hf-smol-p2/prediction.jsonl",
        "--command-line",
        "ml-loop hf-eval smol-worldcup-rescore --json",
        "--json",
    ])
    hf_eval_smol_submission_probe_args = parser.parse_args([
        "hf-eval",
        "smol-worldcup-submission-probe",
        "--output-dir",
        "/tmp/hf-smol-submission-probe",
        "--model",
        "openai/gpt-oss-20b",
        "--timeout-seconds",
        "10",
        "--no-raw",
        "--json",
    ])
    hf_eval_smol_proposal_round_args = parser.parse_args([
        "hf-eval",
        "smol-worldcup-proposal-round",
        "--proposal",
        "/tmp/proposal.json",
        "--output-dir",
        "/tmp/hf-smol-proposal-round",
        "--current-report",
        "/tmp/current-report.json",
        "--model",
        "qwen/qwen3-8b",
        "--prompt-profile",
        "p3-dev-v2",
        "--evaluation-split",
        "dev",
        "--limit",
        "4",
        "--dataset-offset",
        "12",
        "--json",
    ])
    benchmark_readiness_args = parser.parse_args(["benchmark", "readiness", "--json"])
    benchmark_smoke_args = parser.parse_args([
        "benchmark",
        "smoke",
        "--runtime-root",
        "/tmp/runtime",
        "--json",
    ])
    benchmark_probe_args = parser.parse_args(["benchmark", "probe", "--json"])
    benchmark_proof_plan_args = parser.parse_args(["benchmark", "proof-plan", "--json"])
    benchmark_setup_bundle_args = parser.parse_args([
        "benchmark",
        "setup-bundle",
        "--output-dir",
        "/tmp/proof-setup",
        "--json",
    ])
    benchmark_publication_args = parser.parse_args([
        "benchmark",
        "publication-bundle",
        "--manifest",
        "/tmp/proof/manifest.json",
        "--artifact-root",
        "/tmp/proof/artifacts",
        "--output-dir",
        "/tmp/proof/publication",
        "--json",
    ])
    benchmark_archive_args = parser.parse_args([
        "benchmark",
        "archive-proof",
        "--manifest",
        "/tmp/proof/manifest.json",
        "--artifact-root",
        "/tmp/proof/artifacts",
        "--output-dir",
        "/tmp/proof/archive",
        "--json",
    ])
    benchmark_mle_workspace_args = parser.parse_args([
        "benchmark",
        "mle-workspace",
        "--competition-id",
        "spooky-author-identification",
        "--prepared-competition-dir",
        "/tmp/mlebench-data/spooky-author-identification",
        "--runtime-root",
        "/tmp/runtime",
        "--json",
    ])
    benchmark_mle_grade_args = parser.parse_args([
        "benchmark",
        "mle-grade",
        "--competition-id",
        "spooky-author-identification",
        "--submission",
        "/tmp/workspace/submission.csv",
        "--data-dir",
        "/tmp/mlebench-data",
        "--mlebench",
        "/tmp/venv/bin/mlebench",
        "--output-dir",
        "/tmp/reports",
        "--json",
    ])
    benchmark_mle_round_args = parser.parse_args([
        "benchmark",
        "mle-round",
        "--competition-id",
        "spooky-author-identification",
        "--workspace",
        "/tmp/workspace",
        "--data-dir",
        "/tmp/mlebench-data",
        "--mlebench",
        "/tmp/venv/bin/mlebench",
        "--output-dir",
        "/tmp/reports",
        "--python",
        "python3",
        "--round-id",
        "round-001",
        "--json",
    ])
    benchmark_mle_patch_round_args = parser.parse_args([
        "benchmark",
        "mle-patch-round",
        "--competition-id",
        "spooky-author-identification",
        "--workspace",
        "/tmp/workspace",
        "--data-dir",
        "/tmp/mlebench-data",
        "--mlebench",
        "/tmp/venv/bin/mlebench",
        "--output-dir",
        "/tmp/reports",
        "--patch-file",
        "/tmp/patch.diff",
        "--python",
        "python3",
        "--round-id",
        "round-002",
        "--json",
    ])
    benchmark_mle_patch_proof_args = parser.parse_args([
        "benchmark",
        "mle-patch-proof",
        "--patch-round-report",
        "/tmp/reports/round-002/patch-round-report.json",
        "--output-dir",
        "/tmp/proof",
        "--json",
    ])
    benchmark_paperbench_codex_bundle_args = parser.parse_args([
        "benchmark",
        "paperbench-codex-review-bundle",
        "--run-dir",
        "/tmp/paperbench/runs/group/rice_123",
        "--paper-dir",
        "/tmp/frontier-evals/project/paperbench/data/papers/rice",
        "--output-dir",
        "/tmp/review-bundle",
        "--json",
    ])
    benchmark_paperbench_codex_report_args = parser.parse_args([
        "benchmark",
        "paperbench-codex-review-report",
        "--bundle",
        "/tmp/review-bundle/codex-review-bundle.json",
        "--review-file",
        "/tmp/codex-review.json",
        "--output-dir",
        "/tmp/review-report",
        "--json",
    ])
    demo_list_args = parser.parse_args(["demo", "list"])
    demo_init_args = parser.parse_args([
        "demo",
        "init",
        "--template",
        "byte-lm-smoke",
        "--runtime-root",
        "/tmp/runtime",
    ])
    proposal_context_args = parser.parse_args([
        "proposal",
        "context",
        "--objective",
        "Improve local metric",
        "--output-dir",
        "/tmp/proposal-context",
        "--baseline-report",
        "/tmp/baseline.json",
        "--current-report",
        "/tmp/current.json",
        "--failure-samples",
        "/tmp/failure-samples.json",
        "--memory-store",
        "/tmp/research-memory.jsonl",
        "--memory-query",
        "fastText proposal",
        "--memory-limit",
        "2",
        "--resource-constraints",
        "/tmp/resource-constraints.json",
        "--allowed-change-surface",
        "prompt_profile",
        "--max-proposals",
        "4",
        "--json",
    ])
    proposal_reflect_memory_args = parser.parse_args([
        "proposal",
        "reflect",
        "--proposal",
        "/tmp/proposal.json",
        "--evaluation",
        "/tmp/evaluation.json",
        "--output-dir",
        "/tmp/reflection",
        "--memory-store",
        "/tmp/memory.jsonl",
        "--sync-adapters",
        "--adapter",
        "graphiti",
        "--json",
    ])
    proposal_search_args = parser.parse_args([
        "proposal",
        "search",
        "--items",
        "/tmp/proposal-items.json",
        "--branch-budget",
        "2",
        "--diversity-max-per-family",
        "1",
        "--json",
    ])

    assert run_args.command == "run"
    assert status_args.command == "status"
    assert result_args.command == "result"
    assert check_args.command == "check"
    assert artifacts_args.command == "artifacts"
    assert artifacts_args.artifact_command == "list"
    assert init_args.command == "init-mcp-config"
    assert init_args.client == "codex"
    assert skills_args.command == "init-skills"
    assert skills_args.client == "codex"
    assert feedback_args.command == "feedback-bundle"
    assert feedback_args.task_id == "demo"
    assert hf_eval_smol_verify_args.command == "hf-eval"
    assert hf_eval_smol_verify_args.hf_eval_command == "smol-worldcup-verify"
    assert str(hf_eval_smol_verify_args.output_dir) == "/tmp/hf-smol-p0"
    assert hf_eval_smol_verify_args.timeout_seconds == 10
    assert hf_eval_cp_bench_verify_args.hf_eval_command == "cp-bench-verify"
    assert str(hf_eval_cp_bench_verify_args.output_dir) == "/tmp/hf-cp-bench-p0"
    assert hf_eval_cp_bench_verify_args.timeout_seconds == 10
    assert hf_eval_cp_bench_verify_args.no_raw is True
    assert hf_eval_cp_bench_verify_args.json is True
    assert hf_eval_arguard_b1_verify_args.hf_eval_command == "arguard-b1-verify"
    assert str(hf_eval_arguard_b1_verify_args.output_dir) == "/tmp/arguard-b1-p0"
    assert hf_eval_arguard_b1_verify_args.timeout_seconds == 11
    assert hf_eval_arguard_b1_verify_args.no_raw is True
    assert hf_eval_arguard_b1_verify_args.json is True
    assert hf_eval_cp_bench_baseline_args.hf_eval_command == "cp-bench-baseline"
    assert str(hf_eval_cp_bench_baseline_args.output_dir) == "/tmp/hf-cp-bench-p1"
    assert hf_eval_cp_bench_baseline_args.limit == 1
    assert hf_eval_cp_bench_baseline_args.framework == "CPMpy"
    assert hf_eval_cp_bench_baseline_args.timeout_seconds == 7
    assert hf_eval_cp_bench_baseline_args.dry_run is True
    assert hf_eval_cp_bench_baseline_args.json is True
    assert hf_eval_cp_bench_proposal_args.hf_eval_command == "cp-bench-proposal-round"
    assert str(hf_eval_cp_bench_proposal_args.baseline_report).endswith(
        "cp-baseline.json"
    )
    assert str(hf_eval_cp_bench_proposal_args.proposal).endswith("cp-proposal.json")
    assert str(hf_eval_cp_bench_proposal_args.output_dir) == (
        "/tmp/hf-cp-bench-proposal"
    )
    assert hf_eval_cp_bench_candidate_args.hf_eval_command == "cp-bench-candidate-round"
    assert str(hf_eval_cp_bench_candidate_args.baseline_report).endswith(
        "cp-baseline.json"
    )
    assert str(hf_eval_cp_bench_candidate_args.submission).endswith(
        "cp-submission.jsonl"
    )
    assert str(hf_eval_cp_bench_candidate_args.proposal).endswith("cp-proposal.json")
    assert str(hf_eval_cp_bench_candidate_args.output_dir) == (
        "/tmp/hf-cp-bench-candidate"
    )
    assert hf_eval_cp_bench_candidate_args.framework == "CPMpy"
    assert hf_eval_cp_bench_candidate_args.timeout_seconds == 9
    assert hf_eval_cp_bench_context_args.hf_eval_command == "cp-bench-proposal-context"
    assert str(hf_eval_cp_bench_context_args.current_report).endswith(
        "cp-candidate-report.json"
    )
    assert str(hf_eval_cp_bench_context_args.output_dir) == (
        "/tmp/hf-cp-bench-proposal-context"
    )
    assert hf_eval_cp_bench_context_args.max_proposals == 2
    assert (
        hf_eval_cp_bench_client_candidate_args.hf_eval_command
        == "cp-bench-client-candidate"
    )
    assert str(hf_eval_cp_bench_client_candidate_args.output_dir) == (
        "/tmp/hf-cp-bench-p13-client-candidate"
    )
    assert hf_eval_cp_bench_client_candidate_args.limit == 10
    assert hf_eval_cp_bench_client_candidate_args.strategy == (
        "handcrafted-small-cpmpy-v1"
    )
    assert hf_eval_cp_bench_client_candidate_args.dataset_version == "verified"
    assert hf_eval_cp_bench_gate_args.hf_eval_command == "cp-bench-submission-gate"
    assert str(hf_eval_cp_bench_gate_args.submission).endswith("submission.jsonl")
    assert str(hf_eval_cp_bench_gate_args.source_report).endswith("cp-report.json")
    assert str(hf_eval_cp_bench_gate_args.output_dir) == "/tmp/hf-cp-bench-gate"
    assert hf_eval_smol_baseline_args.hf_eval_command == "smol-worldcup-baseline"
    assert str(hf_eval_smol_baseline_args.output_dir) == "/tmp/hf-smol-p1"
    assert hf_eval_smol_baseline_args.limit == 25
    assert hf_eval_smol_baseline_args.evaluation_split == "dev"
    assert hf_eval_smol_leakage_audit_args.hf_eval_command == "smol-worldcup-leakage-audit"
    assert str(hf_eval_smol_leakage_audit_args.output_dir) == "/tmp/hf-smol-audit"
    assert hf_eval_smol_leakage_audit_args.prompt_profile == "p3-dev-v2"
    assert str(hf_eval_smol_leakage_audit_args.prompt_profile_registration) == (
        "/tmp/prompt-profile-registration.json"
    )
    assert hf_eval_smol_leakage_audit_args.evaluation_split == "canary"
    assert hf_eval_smol_model_eval_args.hf_eval_command == "smol-worldcup-model-eval"
    assert str(hf_eval_smol_model_eval_args.output_dir) == "/tmp/hf-smol-p2"
    assert hf_eval_smol_model_eval_args.model == "deepseek-v4-flash"
    assert hf_eval_smol_model_eval_args.model_provider == "deepseek"
    assert hf_eval_smol_model_eval_args.api_key_env == "DEEPSEEK_API_KEY"
    assert hf_eval_smol_model_eval_args.thinking_mode == "enabled"
    assert hf_eval_smol_model_eval_args.reasoning_effort == "high"
    assert hf_eval_smol_model_eval_args.limit == 4
    assert hf_eval_smol_model_eval_args.dataset_offset == 12
    assert hf_eval_smol_model_eval_args.row_id == ["S1-H3-024", "S1-H2-012"]
    assert hf_eval_smol_model_eval_args.prompt_profile == (
        "p3-v7-metacognition-textgrad-pw-ar-v3"
    )
    assert str(hf_eval_smol_model_eval_args.prompt_profile_registration) == (
        "/tmp/prompt-profile-registration.json"
    )
    assert hf_eval_smol_model_eval_args.evaluation_split == "canary"
    assert hf_eval_smol_model_eval_args.judge_mode == "openai-compatible"
    assert hf_eval_smol_model_eval_args.judge_model == "google/gemma-4-31b"
    assert str(hf_eval_smol_model_eval_args.cached_response_prediction_path) == (
        "/tmp/hf-smol-p2/prediction.jsonl"
    )
    assert hf_eval_smol_model_eval_args.require_cached_responses is True
    assert hf_eval_smol_rescore_args.hf_eval_command == "smol-worldcup-rescore"
    assert str(hf_eval_smol_rescore_args.prediction_path).endswith("prediction.jsonl")
    assert str(hf_eval_smol_rescore_args.output_dir) == "/tmp/hf-smol-rescore"
    assert str(hf_eval_smol_rescore_args.source_report).endswith(
        "smol-worldcup-model-eval-report.json"
    )
    assert hf_eval_smol_rescore_args.source_run_id == "round-004-dev-v2"
    assert (
        hf_eval_smol_rescore_archive_args.hf_eval_command
        == "smol-worldcup-rescore-proof-archive"
    )
    assert str(hf_eval_smol_rescore_archive_args.rescore_dir) == "/tmp/hf-smol-rescore"
    assert str(hf_eval_smol_rescore_archive_args.output_dir) == (
        "/tmp/hf-smol-rescore-proof"
    )
    assert str(hf_eval_smol_rescore_archive_args.source_prediction_path).endswith(
        "prediction.jsonl"
    )
    assert hf_eval_smol_rescore_archive_args.command_line == [
        "ml-loop hf-eval smol-worldcup-rescore --json"
    ]
    assert hf_eval_smol_submission_probe_args.hf_eval_command == (
        "smol-worldcup-submission-probe"
    )
    assert str(hf_eval_smol_submission_probe_args.output_dir) == (
        "/tmp/hf-smol-submission-probe"
    )
    assert hf_eval_smol_submission_probe_args.model == "openai/gpt-oss-20b"
    assert hf_eval_smol_submission_probe_args.timeout_seconds == 10
    assert hf_eval_smol_submission_probe_args.no_raw is True
    assert hf_eval_smol_proposal_round_args.hf_eval_command == (
        "smol-worldcup-proposal-round"
    )
    assert str(hf_eval_smol_proposal_round_args.proposal) == "/tmp/proposal.json"
    assert str(hf_eval_smol_proposal_round_args.current_report).endswith(
        "current-report.json"
    )
    assert hf_eval_smol_proposal_round_args.prompt_profile == "p3-dev-v2"
    assert hf_eval_smol_proposal_round_args.evaluation_split == "dev"
    assert hf_eval_smol_proposal_round_args.limit == 4
    assert hf_eval_smol_proposal_round_args.dataset_offset == 12
    assert benchmark_readiness_args.command == "benchmark"
    assert benchmark_readiness_args.benchmark_command == "readiness"
    assert benchmark_smoke_args.benchmark_command == "smoke"
    assert str(benchmark_smoke_args.runtime_root) == "/tmp/runtime"
    assert benchmark_probe_args.benchmark_command == "probe"
    assert benchmark_proof_plan_args.benchmark_command == "proof-plan"
    assert benchmark_setup_bundle_args.benchmark_command == "setup-bundle"
    assert str(benchmark_setup_bundle_args.output_dir) == "/tmp/proof-setup"
    assert benchmark_publication_args.benchmark_command == "publication-bundle"
    assert str(benchmark_publication_args.manifest) == "/tmp/proof/manifest.json"
    assert benchmark_archive_args.benchmark_command == "archive-proof"
    assert str(benchmark_archive_args.output_dir) == "/tmp/proof/archive"
    assert benchmark_mle_workspace_args.benchmark_command == "mle-workspace"
    assert benchmark_mle_workspace_args.competition_id == "spooky-author-identification"
    assert str(benchmark_mle_workspace_args.runtime_root) == "/tmp/runtime"
    assert benchmark_mle_grade_args.benchmark_command == "mle-grade"
    assert str(benchmark_mle_grade_args.submission) == "/tmp/workspace/submission.csv"
    assert benchmark_mle_round_args.benchmark_command == "mle-round"
    assert str(benchmark_mle_round_args.workspace) == "/tmp/workspace"
    assert benchmark_mle_round_args.round_id == "round-001"
    assert benchmark_mle_patch_round_args.benchmark_command == "mle-patch-round"
    assert str(benchmark_mle_patch_round_args.patch_file) == "/tmp/patch.diff"
    assert benchmark_mle_patch_round_args.round_id == "round-002"
    assert benchmark_mle_patch_proof_args.benchmark_command == "mle-patch-proof"
    assert str(benchmark_mle_patch_proof_args.patch_round_report) == (
        "/tmp/reports/round-002/patch-round-report.json"
    )
    assert str(benchmark_mle_patch_proof_args.output_dir) == "/tmp/proof"
    assert (
        benchmark_paperbench_codex_bundle_args.benchmark_command
        == "paperbench-codex-review-bundle"
    )
    assert str(benchmark_paperbench_codex_bundle_args.run_dir).endswith("rice_123")
    assert (
        benchmark_paperbench_codex_report_args.benchmark_command
        == "paperbench-codex-review-report"
    )
    assert str(benchmark_paperbench_codex_report_args.review_file) == "/tmp/codex-review.json"
    assert demo_list_args.command == "demo"
    assert demo_list_args.demo_command == "list"
    assert demo_init_args.demo_command == "init"
    assert demo_init_args.template == "byte-lm-smoke"
    assert proposal_context_args.command == "proposal"
    assert proposal_context_args.proposal_command == "context"
    assert proposal_context_args.allowed_change_surface == ["prompt_profile"]
    assert str(proposal_context_args.failure_samples) == "/tmp/failure-samples.json"
    assert str(proposal_context_args.memory_store) == "/tmp/research-memory.jsonl"
    assert proposal_context_args.memory_query == "fastText proposal"
    assert proposal_context_args.memory_limit == 2
    assert str(proposal_context_args.resource_constraints) == "/tmp/resource-constraints.json"
    assert proposal_context_args.max_proposals == 4
    assert proposal_reflect_memory_args.proposal_command == "reflect"
    assert str(proposal_reflect_memory_args.memory_store) == "/tmp/memory.jsonl"
    assert proposal_reflect_memory_args.sync_adapters is True
    assert proposal_reflect_memory_args.adapter == ["graphiti"]
    assert proposal_search_args.proposal_command == "search"
    assert str(proposal_search_args.items) == "/tmp/proposal-items.json"
    assert proposal_search_args.branch_budget == 2
    assert proposal_search_args.diversity_max_per_family == 1


def test_parser_has_slice_aware_proposal_subcommands():
    parser = build_parser()

    module_spec_args = parser.parse_args([
        "proposal",
        "build-prompt-module-spec",
        "--profile-id",
        "p3-dev-v2",
        "--output",
        "/tmp/prompt-modules.json",
        "--json",
    ])
    matrix_args = parser.parse_args([
        "proposal",
        "build-slice-eval-matrix",
        "--baseline-report",
        "/tmp/baseline.json",
        "--candidate-report",
        "/tmp/candidate.json",
        "--candidate-evaluation",
        "/tmp/evaluation.json",
        "--output",
        "/tmp/slice-matrix.json",
        "--json",
    ])
    gate_args = parser.parse_args([
        "proposal",
        "evaluate-slice-gate",
        "--slice-matrix",
        "/tmp/slice-matrix.json",
        "--output",
        "/tmp/slice-gate.json",
        "--json",
    ])
    variance_gate_args = parser.parse_args([
        "proposal",
        "evaluate-slice-variance-gate",
        "--slice-matrix",
        "/tmp/slice-matrix-a.json",
        "--slice-matrix",
        "/tmp/slice-matrix-b.json",
        "--output",
        "/tmp/slice-variance-gate.json",
        "--min-repeats",
        "2",
        "--json",
    ])
    paired_repeat_manifest_args = parser.parse_args([
        "proposal",
        "build-paired-repeat-manifest",
        "--slice-matrix",
        "/tmp/slice-matrix-a.json",
        "--slice-matrix",
        "/tmp/slice-matrix-b.json",
        "--task-family",
        "generic-fixture",
        "--output",
        "/tmp/paired-repeat-manifest.json",
        "--json",
    ])
    variance_gate_manifest_args = parser.parse_args([
        "proposal",
        "evaluate-slice-variance-gate",
        "--paired-repeat-manifest",
        "/tmp/paired-repeat-manifest.json",
        "--output",
        "/tmp/slice-variance-gate.json",
        "--json",
    ])
    slice_patch_args = parser.parse_args([
        "proposal",
        "generate-slice-patches",
        "--context",
        "/tmp/slice-repair-context.json",
        "--optimizer",
        "runtime-textgrad-plugin",
        "--plugin-manifest",
        "/tmp/optimizer-gate-runtime-plugin-manifest.json",
        "--output",
        "/tmp/slice-patches.json",
        "--json",
    ])
    optimizer_runtime_probe_args = parser.parse_args([
        "proposal",
        "probe-optimizer-runtime",
        "--optimizer",
        "subprocess-textgrad-plugin",
        "--plugin-manifest",
        "/tmp/optimizer-gate-subprocess-plugin-manifest.json",
        "--execute-probe",
        "--output",
        "/tmp/optimizer-runtime-probe.json",
        "--json",
    ])
    optimizer_gate_run_args = parser.parse_args([
        "proposal",
        "build-optimizer-gate-run",
        "--context",
        "/tmp/slice-repair-context.json",
        "--base-profile-id",
        "p3-system-fixture",
        "--optimizer",
        "manual-template",
        "--plugin-manifest",
        "/tmp/optimizer-gate-plugin-manifest.json",
        "--execute-runtime-probe",
        "--output-dir",
        "/tmp/optimizer-gate-run",
        "--json",
    ])
    optimizer_gate_execution_plan_args = parser.parse_args([
        "proposal",
        "build-optimizer-gate-execution-plan",
        "--run",
        "/tmp/optimizer-gate-run.json",
        "--benchmark",
        "smol_worldcup",
        "--output",
        "/tmp/optimizer-gate-execution-plan.json",
        "--json",
    ])
    prompt_profile_registration_plan_args = parser.parse_args([
        "proposal",
        "build-prompt-profile-registration-plan",
        "--materialization",
        "/tmp/slice-patch-materialization.json",
        "--benchmark",
        "smol_worldcup",
        "--proposed-profile-id",
        "p3-system-fixture-slice-patch-001",
        "--output",
        "/tmp/prompt-profile-registration-plan.json",
        "--json",
    ])
    prompt_profile_registration_args = parser.parse_args([
        "proposal",
        "register-prompt-profile",
        "--registration-plan",
        "/tmp/prompt-profile-registration-plan.json",
        "--approve",
        "--output",
        "/tmp/prompt-profile-registration.json",
        "--json",
    ])
    optimizer_gate_execution_preflight_args = parser.parse_args([
        "proposal",
        "build-optimizer-gate-execution-preflight",
        "--registration-plan",
        "/tmp/prompt-profile-registration-plan.json",
        "--registered-profile",
        "/tmp/prompt-profile-registration.json",
        "--registered-profile-id",
        "p3-system-fixture-slice-patch-001",
        "--prompt-leakage-audit",
        "/tmp/prompt-leakage-audit.json",
        "--target-smoke",
        "/tmp/target-smoke.json",
        "--dev-model-eval",
        "/tmp/dev-model-eval.json",
        "--gate-decision",
        "/tmp/gate-policy-composition.json",
        "--output",
        "/tmp/optimizer-gate-execution-preflight.json",
        "--json",
    ])
    registered_profile_execution_bundle_args = parser.parse_args([
        "proposal",
        "build-registered-profile-execution-bundle",
        "--registration-plan",
        "/tmp/prompt-profile-registration-plan.json",
        "--registered-profile",
        "/tmp/prompt-profile-registration.json",
        "--prompt-leakage-audit",
        "/tmp/prompt-leakage-audit.json",
        "--target-smoke",
        "/tmp/target-smoke.json",
        "--dev-model-eval",
        "/tmp/dev-model-eval.json",
        "--gate-decision",
        "/tmp/gate-policy-composition.json",
        "--output-dir",
        "/tmp/registered-profile-execution",
        "--json",
    ])
    registered_profile_execution_run_args = parser.parse_args([
        "proposal",
        "run-registered-profile-execution",
        "--registration-plan",
        "/tmp/prompt-profile-registration-plan.json",
        "--registered-profile",
        "/tmp/prompt-profile-registration.json",
        "--prompt-leakage-rows",
        "/tmp/prompt-leakage-rows.json",
        "--execute-model-eval",
        "--target-smoke-rows",
        "/tmp/target-smoke-rows.json",
        "--dev-model-eval-rows",
        "/tmp/dev-model-eval-rows.json",
        "--dev-baseline-eval",
        "/tmp/dev-baseline-eval.json",
        "--dev-gate-source",
        "/tmp/dev-slice-eval-matrix.json",
        "--model-runtime-preflight",
        "/tmp/model-runtime-preflight.json",
        "--model-eval-model",
        "qwen/qwen3-8b",
        "--model-eval-base-url",
        "http://127.0.0.1:1234/v1",
        "--output-dir",
        "/tmp/registered-profile-execution-run",
        "--json",
    ])
    canary_preflight_args = parser.parse_args([
        "proposal",
        "build-registered-profile-canary-preflight",
        "--registered-profile-execution-run",
        "/tmp/registered-profile-execution-run.json",
        "--canary-rows",
        "/tmp/canary-rows.json",
        "--output",
        "/tmp/registered-profile-canary-preflight.json",
        "--json",
    ])
    canary_execution_args = parser.parse_args([
        "proposal",
        "run-registered-profile-canary-execution",
        "--registered-profile-execution-run",
        "/tmp/registered-profile-execution-run.json",
        "--registered-profile",
        "/tmp/prompt-profile-registration.json",
        "--execute-canary",
        "--canary-rows",
        "/tmp/canary-rows.json",
        "--model-runtime-preflight",
        "/tmp/model-runtime-preflight.json",
        "--model-eval-model",
        "qwen/qwen3-8b",
        "--model-eval-base-url",
        "http://127.0.0.1:1234/v1",
        "--output-dir",
        "/tmp/registered-profile-canary-execution",
        "--json",
    ])
    canary_result_gate_args = parser.parse_args([
        "proposal",
        "build-registered-profile-canary-result-gate",
        "--registered-profile-canary-execution",
        "/tmp/registered-profile-canary-execution.json",
        "--output",
        "/tmp/registered-profile-canary-result-gate.json",
        "--json",
    ])
    outcome_schedule_args = parser.parse_args([
        "proposal",
        "build-registered-profile-outcome-schedule",
        "--registered-profile-canary-result-gate",
        "/tmp/registered-profile-canary-result-gate.json",
        "--output",
        "/tmp/registered-profile-outcome-schedule.json",
        "--json",
    ])
    scheduler_plan_args = parser.parse_args([
        "proposal",
        "build-optimizer-gate-scheduler-plan",
        "--registered-profile-outcome-schedule",
        "/tmp/registered-profile-outcome-schedule.json",
        "--model-runtime-preflight",
        "/tmp/model-runtime-preflight.json",
        "--slice-optimizer-selection",
        "/tmp/slice-optimizer-selection.json",
        "--output",
        "/tmp/optimizer-gate-scheduler-plan.json",
        "--json",
    ])
    scheduler_action_args = parser.parse_args([
        "proposal",
        "run-optimizer-gate-scheduler-action",
        "--optimizer-gate-scheduler-plan",
        "/tmp/optimizer-gate-scheduler-plan.json",
        "--action-name",
        "build_model_runtime_preflight",
        "--model",
        "qwen/qwen3-8b",
        "--base-url",
        "http://127.0.0.1:1234/v1",
        "--experiment-action-allowlist",
        "run_registered_profile_canary_execution",
        "--experiment-max-actions",
        "1",
        "--canary-runner-bundle",
        "/tmp/optimizer-gate-canary-runner-bundle.json",
        "--output-dir",
        "/tmp/optimizer-gate-scheduler-action",
        "--json",
    ])
    scheduler_loop_args = parser.parse_args([
        "proposal",
        "run-optimizer-gate-scheduler-loop",
        "--optimizer-gate-scheduler-plan",
        "/tmp/optimizer-gate-scheduler-plan.json",
        "--model",
        "qwen/qwen3-8b",
        "--base-url",
        "http://127.0.0.1:1234/v1",
        "--max-actions",
        "2",
        "--auto-refresh-scheduler-plan",
        "--experiment-action-allowlist",
        "run_registered_profile_canary_execution",
        "--experiment-max-actions",
        "1",
        "--canary-runner-bundle",
        "/tmp/optimizer-gate-canary-runner-bundle.json",
        "--output-dir",
        "/tmp/optimizer-gate-scheduler-loop",
        "--json",
    ])
    scheduler_handoff_args = parser.parse_args([
        "proposal",
        "build-optimizer-gate-scheduler-handoff",
        "--optimizer-gate-scheduler-loop",
        "/tmp/optimizer-gate-scheduler-loop.json",
        "--output",
        "/tmp/optimizer-gate-scheduler-handoff.json",
        "--json",
    ])
    model_runtime_preflight_args = parser.parse_args([
        "proposal",
        "build-model-runtime-preflight",
        "--model",
        "qwen/qwen3-8b",
        "--base-url",
        "http://127.0.0.1:1234/v1",
        "--execute-probe",
        "--max-tokens",
        "128",
        "--output",
        "/tmp/model-runtime-preflight.json",
        "--json",
    ])
    optimizer_gate_spec_args = parser.parse_args([
        "proposal",
        "build-optimizer-gate-system-spec",
        "--plugin-manifest",
        "/tmp/optimizer-gate-plugin-manifest.json",
        "--output",
        "/tmp/optimizer-gate-system-spec.json",
        "--json",
    ])
    gate_policy_input_args = parser.parse_args([
        "proposal",
        "build-gate-policy-input",
        "--metric-table",
        "/tmp/metric-table.json",
        "--slice-table",
        "/tmp/slice-table.json",
        "--policy-id",
        "slice-dev-hard-gate",
        "--task-family",
        "generic-fixture",
        "--split",
        "dev",
        "--quality-constraints",
        "/tmp/quality-constraints.json",
        "--execution-quality",
        "/tmp/execution-quality.json",
        "--output",
        "/tmp/gate-policy-input.json",
        "--json",
    ])
    gate_policy_decision_args = parser.parse_args([
        "proposal",
        "evaluate-gate-policy",
        "--gate-input",
        "/tmp/gate-policy-input.json",
        "--output",
        "/tmp/gate-policy-decision.json",
        "--json",
    ])
    gate_policy_composition_args = parser.parse_args([
        "proposal",
        "build-gate-policy-composition",
        "--decision",
        "/tmp/gate-policy-decision.json",
        "--decision",
        "/tmp/slice-variance-gate-decision.json",
        "--composition-id",
        "dev-hard-gate-composition",
        "--output",
        "/tmp/gate-policy-composition.json",
        "--json",
    ])
    gate_policy_graph_args = parser.parse_args([
        "proposal",
        "build-gate-policy-graph",
        "--graph-id",
        "dev-policy-graph",
        "--required-policy",
        "slice-dev-hard-gate",
        "--required-policy",
        "paired-repeat-variance-gate",
        "--optional-policy",
        "cost-ceiling-gate",
        "--output",
        "/tmp/gate-policy-graph.json",
        "--json",
    ])
    gate_policy_graph_decision_args = parser.parse_args([
        "proposal",
        "evaluate-gate-policy-graph",
        "--policy-graph",
        "/tmp/gate-policy-graph.json",
        "--decision",
        "/tmp/gate-policy-decision.json",
        "--decision",
        "/tmp/slice-variance-gate-decision.json",
        "--output",
        "/tmp/gate-policy-graph-decision.json",
        "--json",
    ])
    slice_patch_outcome_args = parser.parse_args([
        "proposal",
        "record-slice-patch-outcome",
        "--candidate",
        "/tmp/slice-patch-candidate.json",
        "--materialization",
        "/tmp/slice-patch-materialization.json",
        "--gate-decision",
        "/tmp/gate-policy-decision.json",
        "--output",
        "/tmp/slice-patch-outcome.json",
        "--json",
    ])
    slice_optimizer_selection_args = parser.parse_args([
        "proposal",
        "build-slice-optimizer-selection",
        "--outcomes",
        "/tmp/slice-patch-outcomes.jsonl",
        "--target-scope",
        "multilingual_variant_explanation/output_format",
        "--failure-label",
        "slice_regression",
        "--candidate-optimizer",
        "promptwizard-constrained",
        "--candidate-optimizer",
        "textgrad-local",
        "--output",
        "/tmp/slice-optimizer-selection.json",
        "--json",
    ])
    optimizer_gate_executable_loop_args = parser.parse_args([
        "proposal",
        "run-optimizer-gate-executable-loop",
        "--canary-result-gate",
        "/tmp/canary-result-gate.json",
        "--slice-repair-context",
        "/tmp/slice-repair-context.json",
        "--candidate-optimizer",
        "manual-template",
        "--base-profile-id",
        "p3-dev-v2",
        "--proposed-profile-prefix",
        "p3-loop-next",
        "--max-iterations",
        "1",
        "--max-candidates",
        "1",
        "--auto-approve-registration",
        "--approved-by",
        "cli-loop-test",
        "--prompt-leakage-rows",
        "/tmp/prompt-leakage-rows.json",
        "--prompt-leakage-audit",
        "/tmp/prompt-leakage-audit.json",
        "--target-smoke",
        "/tmp/target-smoke.json",
        "--dev-model-eval",
        "/tmp/dev-model-eval.json",
        "--dev-baseline-eval",
        "/tmp/dev-baseline-eval.json",
        "--dev-gate-source",
        "/tmp/dev-slice-eval-matrix.json",
        "--model-runtime-preflight",
        "/tmp/model-runtime-preflight.json",
        "--execute-model-eval",
        "--target-smoke-rows",
        "/tmp/target-smoke-rows.json",
        "--dev-model-eval-rows",
        "/tmp/dev-model-eval-rows.json",
        "--execute-canary-runner",
        "--canary-rows",
        "/tmp/canary-rows.json",
        "--min-canary-row-count",
        "2",
        "--max-canary-failure-count",
        "0",
        "--max-canary-runtime-error-count",
        "0",
        "--max-canary-empty-output-count",
        "0",
        "--model-eval-model",
        "qwen/qwen3-8b",
        "--model-eval-base-url",
        "http://127.0.0.1:1234/v1",
        "--model-eval-timeout-seconds",
        "3",
        "--model-eval-max-tokens",
        "64",
        "--output-dir",
        "/tmp/optimizer-gate-executable-loop",
        "--json",
    ])

    assert module_spec_args.proposal_command == "build-prompt-module-spec"
    assert module_spec_args.profile_id == "p3-dev-v2"
    assert str(module_spec_args.output) == "/tmp/prompt-modules.json"
    assert matrix_args.proposal_command == "build-slice-eval-matrix"
    assert str(matrix_args.baseline_report) == "/tmp/baseline.json"
    assert str(matrix_args.candidate_report) == "/tmp/candidate.json"
    assert str(matrix_args.candidate_evaluation) == "/tmp/evaluation.json"
    assert gate_args.proposal_command == "evaluate-slice-gate"
    assert str(gate_args.slice_matrix) == "/tmp/slice-matrix.json"
    assert variance_gate_args.proposal_command == "evaluate-slice-variance-gate"
    assert [str(item) for item in variance_gate_args.slice_matrix] == [
        "/tmp/slice-matrix-a.json",
        "/tmp/slice-matrix-b.json",
    ]
    assert str(variance_gate_args.output) == "/tmp/slice-variance-gate.json"
    assert variance_gate_args.min_repeats == 2
    assert paired_repeat_manifest_args.proposal_command == "build-paired-repeat-manifest"
    assert [str(item) for item in paired_repeat_manifest_args.slice_matrix] == [
        "/tmp/slice-matrix-a.json",
        "/tmp/slice-matrix-b.json",
    ]
    assert paired_repeat_manifest_args.task_family == "generic-fixture"
    assert str(paired_repeat_manifest_args.output) == "/tmp/paired-repeat-manifest.json"
    assert variance_gate_manifest_args.proposal_command == "evaluate-slice-variance-gate"
    assert str(variance_gate_manifest_args.paired_repeat_manifest) == (
        "/tmp/paired-repeat-manifest.json"
    )
    assert slice_patch_args.proposal_command == "generate-slice-patches"
    assert slice_patch_args.optimizer == "runtime-textgrad-plugin"
    assert [str(item) for item in slice_patch_args.plugin_manifest] == [
        "/tmp/optimizer-gate-runtime-plugin-manifest.json"
    ]
    assert optimizer_runtime_probe_args.proposal_command == "probe-optimizer-runtime"
    assert optimizer_runtime_probe_args.optimizer == "subprocess-textgrad-plugin"
    assert [str(item) for item in optimizer_runtime_probe_args.plugin_manifest] == [
        "/tmp/optimizer-gate-subprocess-plugin-manifest.json"
    ]
    assert optimizer_runtime_probe_args.execute_probe is True
    assert optimizer_gate_run_args.proposal_command == "build-optimizer-gate-run"
    assert str(optimizer_gate_run_args.context) == "/tmp/slice-repair-context.json"
    assert optimizer_gate_run_args.base_profile_id == "p3-system-fixture"
    assert optimizer_gate_run_args.optimizer == "manual-template"
    assert [str(item) for item in optimizer_gate_run_args.plugin_manifest] == [
        "/tmp/optimizer-gate-plugin-manifest.json"
    ]
    assert optimizer_gate_run_args.execute_runtime_probe is True
    assert str(optimizer_gate_run_args.output_dir) == "/tmp/optimizer-gate-run"
    assert optimizer_gate_execution_plan_args.proposal_command == (
        "build-optimizer-gate-execution-plan"
    )
    assert str(optimizer_gate_execution_plan_args.run) == (
        "/tmp/optimizer-gate-run.json"
    )
    assert optimizer_gate_execution_plan_args.benchmark == "smol_worldcup"
    assert prompt_profile_registration_plan_args.proposal_command == (
        "build-prompt-profile-registration-plan"
    )
    assert str(prompt_profile_registration_plan_args.materialization) == (
        "/tmp/slice-patch-materialization.json"
    )
    assert prompt_profile_registration_plan_args.benchmark == "smol_worldcup"
    assert prompt_profile_registration_plan_args.proposed_profile_id == (
        "p3-system-fixture-slice-patch-001"
    )
    assert str(prompt_profile_registration_plan_args.output) == (
        "/tmp/prompt-profile-registration-plan.json"
    )
    assert prompt_profile_registration_args.proposal_command == "register-prompt-profile"
    assert str(prompt_profile_registration_args.registration_plan) == (
        "/tmp/prompt-profile-registration-plan.json"
    )
    assert prompt_profile_registration_args.approve is True
    assert str(prompt_profile_registration_args.output) == (
        "/tmp/prompt-profile-registration.json"
    )
    assert optimizer_gate_execution_preflight_args.proposal_command == (
        "build-optimizer-gate-execution-preflight"
    )
    assert str(optimizer_gate_execution_preflight_args.registration_plan) == (
        "/tmp/prompt-profile-registration-plan.json"
    )
    assert str(optimizer_gate_execution_preflight_args.registered_profile) == (
        "/tmp/prompt-profile-registration.json"
    )
    assert optimizer_gate_execution_preflight_args.registered_profile_id == (
        "p3-system-fixture-slice-patch-001"
    )
    assert str(optimizer_gate_execution_preflight_args.prompt_leakage_audit) == (
        "/tmp/prompt-leakage-audit.json"
    )
    assert registered_profile_execution_bundle_args.proposal_command == (
        "build-registered-profile-execution-bundle"
    )
    assert str(registered_profile_execution_bundle_args.registration_plan) == (
        "/tmp/prompt-profile-registration-plan.json"
    )
    assert str(registered_profile_execution_bundle_args.output_dir) == (
        "/tmp/registered-profile-execution"
    )
    assert registered_profile_execution_run_args.proposal_command == (
        "run-registered-profile-execution"
    )
    assert str(registered_profile_execution_run_args.prompt_leakage_rows) == (
        "/tmp/prompt-leakage-rows.json"
    )
    assert registered_profile_execution_run_args.execute_model_eval is True
    assert str(registered_profile_execution_run_args.target_smoke_rows) == (
        "/tmp/target-smoke-rows.json"
    )
    assert str(registered_profile_execution_run_args.dev_model_eval_rows) == (
        "/tmp/dev-model-eval-rows.json"
    )
    assert str(registered_profile_execution_run_args.dev_baseline_eval) == (
        "/tmp/dev-baseline-eval.json"
    )
    assert str(registered_profile_execution_run_args.dev_gate_source) == (
        "/tmp/dev-slice-eval-matrix.json"
    )
    assert str(registered_profile_execution_run_args.model_runtime_preflight) == (
        "/tmp/model-runtime-preflight.json"
    )
    assert registered_profile_execution_run_args.model_eval_model == "qwen/qwen3-8b"
    assert str(registered_profile_execution_run_args.output_dir) == (
        "/tmp/registered-profile-execution-run"
    )
    assert canary_preflight_args.proposal_command == (
        "build-registered-profile-canary-preflight"
    )
    assert str(canary_preflight_args.registered_profile_execution_run) == (
        "/tmp/registered-profile-execution-run.json"
    )
    assert str(canary_preflight_args.canary_rows) == "/tmp/canary-rows.json"
    assert str(canary_preflight_args.output) == (
        "/tmp/registered-profile-canary-preflight.json"
    )
    assert canary_execution_args.proposal_command == (
        "run-registered-profile-canary-execution"
    )
    assert str(canary_execution_args.registered_profile_execution_run) == (
        "/tmp/registered-profile-execution-run.json"
    )
    assert str(canary_execution_args.registered_profile) == (
        "/tmp/prompt-profile-registration.json"
    )
    assert canary_execution_args.execute_canary is True
    assert str(canary_execution_args.canary_rows) == "/tmp/canary-rows.json"
    assert str(canary_execution_args.model_runtime_preflight) == (
        "/tmp/model-runtime-preflight.json"
    )
    assert str(canary_execution_args.output_dir) == (
        "/tmp/registered-profile-canary-execution"
    )
    assert canary_result_gate_args.proposal_command == (
        "build-registered-profile-canary-result-gate"
    )
    assert str(canary_result_gate_args.registered_profile_canary_execution) == (
        "/tmp/registered-profile-canary-execution.json"
    )
    assert str(canary_result_gate_args.output) == (
        "/tmp/registered-profile-canary-result-gate.json"
    )
    assert outcome_schedule_args.proposal_command == (
        "build-registered-profile-outcome-schedule"
    )
    assert str(outcome_schedule_args.registered_profile_canary_result_gate) == (
        "/tmp/registered-profile-canary-result-gate.json"
    )
    assert str(outcome_schedule_args.output) == (
        "/tmp/registered-profile-outcome-schedule.json"
    )
    assert scheduler_plan_args.proposal_command == (
        "build-optimizer-gate-scheduler-plan"
    )
    assert str(scheduler_plan_args.registered_profile_outcome_schedule) == (
        "/tmp/registered-profile-outcome-schedule.json"
    )
    assert str(scheduler_plan_args.model_runtime_preflight) == (
        "/tmp/model-runtime-preflight.json"
    )
    assert str(scheduler_plan_args.slice_optimizer_selection) == (
        "/tmp/slice-optimizer-selection.json"
    )
    assert str(scheduler_plan_args.output) == (
        "/tmp/optimizer-gate-scheduler-plan.json"
    )
    assert scheduler_action_args.proposal_command == (
        "run-optimizer-gate-scheduler-action"
    )
    assert str(scheduler_action_args.optimizer_gate_scheduler_plan) == (
        "/tmp/optimizer-gate-scheduler-plan.json"
    )
    assert scheduler_action_args.action_name == "build_model_runtime_preflight"
    assert scheduler_action_args.model == "qwen/qwen3-8b"
    assert scheduler_action_args.experiment_action_allowlist == [
        "run_registered_profile_canary_execution"
    ]
    assert scheduler_action_args.experiment_max_actions == 1
    assert str(scheduler_action_args.canary_runner_bundle) == (
        "/tmp/optimizer-gate-canary-runner-bundle.json"
    )
    assert str(scheduler_action_args.output_dir) == (
        "/tmp/optimizer-gate-scheduler-action"
    )
    assert scheduler_loop_args.proposal_command == (
        "run-optimizer-gate-scheduler-loop"
    )
    assert str(scheduler_loop_args.optimizer_gate_scheduler_plan) == (
        "/tmp/optimizer-gate-scheduler-plan.json"
    )
    assert scheduler_loop_args.max_actions == 2
    assert scheduler_loop_args.auto_refresh_scheduler_plan is True
    assert scheduler_loop_args.experiment_action_allowlist == [
        "run_registered_profile_canary_execution"
    ]
    assert scheduler_loop_args.experiment_max_actions == 1
    assert str(scheduler_loop_args.canary_runner_bundle) == (
        "/tmp/optimizer-gate-canary-runner-bundle.json"
    )
    assert str(scheduler_loop_args.output_dir) == "/tmp/optimizer-gate-scheduler-loop"
    assert scheduler_handoff_args.proposal_command == (
        "build-optimizer-gate-scheduler-handoff"
    )
    assert str(scheduler_handoff_args.optimizer_gate_scheduler_loop) == (
        "/tmp/optimizer-gate-scheduler-loop.json"
    )
    assert str(scheduler_handoff_args.output) == (
        "/tmp/optimizer-gate-scheduler-handoff.json"
    )
    assert model_runtime_preflight_args.proposal_command == (
        "build-model-runtime-preflight"
    )
    assert model_runtime_preflight_args.model == "qwen/qwen3-8b"
    assert model_runtime_preflight_args.execute_probe is True
    assert model_runtime_preflight_args.max_tokens == 128
    assert str(model_runtime_preflight_args.output) == (
        "/tmp/model-runtime-preflight.json"
    )
    assert str(optimizer_gate_execution_preflight_args.target_smoke) == (
        "/tmp/target-smoke.json"
    )
    assert str(optimizer_gate_execution_preflight_args.dev_model_eval) == (
        "/tmp/dev-model-eval.json"
    )
    assert [str(item) for item in optimizer_gate_execution_preflight_args.gate_decision] == [
        "/tmp/gate-policy-composition.json"
    ]
    assert optimizer_gate_spec_args.proposal_command == "build-optimizer-gate-system-spec"
    assert [str(item) for item in optimizer_gate_spec_args.plugin_manifest] == [
        "/tmp/optimizer-gate-plugin-manifest.json"
    ]
    assert str(optimizer_gate_spec_args.output) == "/tmp/optimizer-gate-system-spec.json"
    assert gate_policy_input_args.proposal_command == "build-gate-policy-input"
    assert str(gate_policy_input_args.metric_table) == "/tmp/metric-table.json"
    assert str(gate_policy_input_args.slice_table) == "/tmp/slice-table.json"
    assert gate_policy_input_args.policy_id == "slice-dev-hard-gate"
    assert gate_policy_input_args.task_family == "generic-fixture"
    assert gate_policy_input_args.split == "dev"
    assert str(gate_policy_input_args.quality_constraints) == (
        "/tmp/quality-constraints.json"
    )
    assert str(gate_policy_input_args.execution_quality) == "/tmp/execution-quality.json"
    assert gate_policy_decision_args.proposal_command == "evaluate-gate-policy"
    assert str(gate_policy_decision_args.gate_input) == "/tmp/gate-policy-input.json"
    assert gate_policy_composition_args.proposal_command == (
        "build-gate-policy-composition"
    )
    assert [str(item) for item in gate_policy_composition_args.decision] == [
        "/tmp/gate-policy-decision.json",
        "/tmp/slice-variance-gate-decision.json",
    ]
    assert gate_policy_composition_args.composition_id == "dev-hard-gate-composition"
    assert gate_policy_graph_args.proposal_command == "build-gate-policy-graph"
    assert gate_policy_graph_args.graph_id == "dev-policy-graph"
    assert gate_policy_graph_args.required_policy == [
        "slice-dev-hard-gate",
        "paired-repeat-variance-gate",
    ]
    assert gate_policy_graph_args.optional_policy == ["cost-ceiling-gate"]
    assert gate_policy_graph_decision_args.proposal_command == (
        "evaluate-gate-policy-graph"
    )
    assert str(gate_policy_graph_decision_args.policy_graph) == (
        "/tmp/gate-policy-graph.json"
    )
    assert slice_patch_outcome_args.proposal_command == "record-slice-patch-outcome"
    assert str(slice_patch_outcome_args.candidate) == "/tmp/slice-patch-candidate.json"
    assert str(slice_patch_outcome_args.materialization) == (
        "/tmp/slice-patch-materialization.json"
    )
    assert str(slice_patch_outcome_args.gate_decision) == "/tmp/gate-policy-decision.json"
    assert slice_optimizer_selection_args.proposal_command == (
        "build-slice-optimizer-selection"
    )
    assert str(slice_optimizer_selection_args.outcomes) == "/tmp/slice-patch-outcomes.jsonl"
    assert slice_optimizer_selection_args.target_scope == (
        "multilingual_variant_explanation/output_format"
    )
    assert slice_optimizer_selection_args.failure_label == ["slice_regression"]
    assert slice_optimizer_selection_args.candidate_optimizer == [
        "promptwizard-constrained",
        "textgrad-local",
    ]
    assert optimizer_gate_executable_loop_args.proposal_command == (
        "run-optimizer-gate-executable-loop"
    )
    assert str(optimizer_gate_executable_loop_args.canary_result_gate) == (
        "/tmp/canary-result-gate.json"
    )
    assert str(optimizer_gate_executable_loop_args.slice_repair_context) == (
        "/tmp/slice-repair-context.json"
    )
    assert optimizer_gate_executable_loop_args.auto_approve_registration is True
    assert optimizer_gate_executable_loop_args.approved_by == "cli-loop-test"
    assert str(optimizer_gate_executable_loop_args.prompt_leakage_rows) == (
        "/tmp/prompt-leakage-rows.json"
    )
    assert str(optimizer_gate_executable_loop_args.prompt_leakage_audit) == (
        "/tmp/prompt-leakage-audit.json"
    )
    assert str(optimizer_gate_executable_loop_args.target_smoke) == (
        "/tmp/target-smoke.json"
    )
    assert str(optimizer_gate_executable_loop_args.dev_model_eval) == (
        "/tmp/dev-model-eval.json"
    )
    assert str(optimizer_gate_executable_loop_args.dev_baseline_eval) == (
        "/tmp/dev-baseline-eval.json"
    )
    assert str(optimizer_gate_executable_loop_args.dev_gate_source) == (
        "/tmp/dev-slice-eval-matrix.json"
    )
    assert str(optimizer_gate_executable_loop_args.model_runtime_preflight) == (
        "/tmp/model-runtime-preflight.json"
    )
    assert optimizer_gate_executable_loop_args.execute_model_eval is True
    assert str(optimizer_gate_executable_loop_args.target_smoke_rows) == (
        "/tmp/target-smoke-rows.json"
    )
    assert str(optimizer_gate_executable_loop_args.dev_model_eval_rows) == (
        "/tmp/dev-model-eval-rows.json"
    )
    assert optimizer_gate_executable_loop_args.execute_canary_runner is True
    assert str(optimizer_gate_executable_loop_args.canary_rows) == (
        "/tmp/canary-rows.json"
    )
    assert optimizer_gate_executable_loop_args.min_canary_row_count == 2
    assert optimizer_gate_executable_loop_args.max_canary_failure_count == 0
    assert optimizer_gate_executable_loop_args.max_canary_runtime_error_count == 0
    assert optimizer_gate_executable_loop_args.max_canary_empty_output_count == 0
    assert optimizer_gate_executable_loop_args.model_eval_model == "qwen/qwen3-8b"
    assert optimizer_gate_executable_loop_args.model_eval_timeout_seconds == 3
    assert optimizer_gate_executable_loop_args.model_eval_max_tokens == 64
    assert str(optimizer_gate_executable_loop_args.output_dir) == (
        "/tmp/optimizer-gate-executable-loop"
    )


def test_slice_eval_matrix_cli_writes_output(tmp_path, capsys):
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    output = tmp_path / "slice-matrix.json"
    baseline.write_text(
        json.dumps(
            {
                "metrics": {"SHIFT": 80.0},
                "dataset": {"evaluation_split": "dev"},
                "score_breakdown": {
                    "by_category": {
                        "multilingual_pt": {"row_count": 3, "score_percent": 53.0}
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    candidate.write_text(
        json.dumps(
            {
                "metrics": {"SHIFT": 70.0},
                "dataset": {"evaluation_split": "dev"},
                "score_breakdown": {
                    "by_category": {
                        "multilingual_pt": {"row_count": 3, "score_percent": 23.0}
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-slice-eval-matrix",
        "--baseline-report",
        str(baseline),
        "--candidate-report",
        str(candidate),
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "completed"
    assert output.exists()
    assert payload["official_scores_claimed"] is False


def test_prompt_module_spec_cli_writes_output(tmp_path, capsys):
    output = tmp_path / "prompt-modules.json"

    exit_code = main([
        "proposal",
        "build-prompt-module-spec",
        "--profile-id",
        "p3-dev-v2",
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == "2026-06-04.prompt-module-spec.v1"
    assert payload["profile_id"] == "p3-dev-v2"
    assert output.exists()
    assert payload["official_scores_claimed"] is False


def test_textgrad_openai_compatible_cli_writes_executed_candidate(
    monkeypatch,
    tmp_path,
    capsys,
):
    context = tmp_path / "slice-repair-context.json"
    output = tmp_path / "slice-patches.json"
    context.write_text(
        json.dumps(
            {
                "recommended_patch_contract": {
                    "module_id": "multilingual_variant_explanation",
                    "section_id": "output_format",
                    "based_on_slices": ["dev/category/multilingual_pt"],
                    "target_slice": "multilingual_pt",
                    "before_text": "return concise JSON",
                    "protected_slices": ["multilingual_th"],
                    "protected_sections": ["role"],
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    def fake_chat(**kwargs):
        return {
            "content": json.dumps(
                {
                    "critic_feedback": "Use a locale-specific JSON cue.",
                    "after_text": "return concise JSON with pt idiom evidence",
                }
            ),
            "raw_response": {"id": "chatcmpl-cli"},
        }

    monkeypatch.setattr(
        "lib.failure_driven_proposal._call_openai_compatible_chat",
        fake_chat,
    )

    exit_code = main([
        "proposal",
        "generate-slice-patches",
        "--context",
        str(context),
        "--optimizer",
        "textgrad-openai-compatible",
        "--execute-optimizer",
        "--optimizer-model",
        "qwen/qwen3-8b",
        "--optimizer-base-url",
        "http://127.0.0.1:1234/v1",
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["optimizer_runtime"]["status"] == "executed"
    assert payload["executes_tool"] is True
    assert payload["candidates"][0]["optimizer_model"] == "qwen/qwen3-8b"
    assert output.exists()
    assert payload["official_scores_claimed"] is False


def test_runtime_optimizer_plugin_cli_writes_executed_candidate(
    monkeypatch,
    tmp_path,
    capsys,
):
    context = tmp_path / "slice-repair-context.json"
    plugin_manifest = tmp_path / "optimizer-gate-runtime-plugin-manifest.json"
    output = tmp_path / "slice-patches.json"
    context.write_text(
        json.dumps(
            {
                "recommended_patch_contract": {
                    "module_id": "multilingual_variant_explanation",
                    "section_id": "output_format",
                    "based_on_slices": ["dev/category/multilingual_pt"],
                    "target_slice": "multilingual_pt",
                    "before_text": "return concise JSON",
                    "protected_slices": ["multilingual_th"],
                    "protected_sections": ["role"],
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    plugin_manifest.write_text(
        json.dumps(_runtime_optimizer_plugin_manifest_fixture()),
        encoding="utf-8",
    )

    def fake_chat(**kwargs):
        return {
            "content": json.dumps(
                {
                    "critic_feedback": "Use a locale-specific JSON cue.",
                    "after_text": "return concise JSON with pt idiom evidence",
                }
            ),
            "raw_response": {"id": "chatcmpl-cli-runtime-plugin"},
        }

    monkeypatch.setattr(
        "lib.failure_driven_proposal._call_openai_compatible_chat",
        fake_chat,
    )

    exit_code = main([
        "proposal",
        "generate-slice-patches",
        "--context",
        str(context),
        "--optimizer",
        "runtime-textgrad-plugin",
        "--plugin-manifest",
        str(plugin_manifest),
        "--execute-optimizer",
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["optimizer"] == "runtime-textgrad-plugin"
    assert payload["optimizer_runtime"]["status"] == "executed"
    assert payload["candidates"][0]["candidate_strategy"] == (
        "plugin_openai_compatible"
    )
    assert payload["executes_tool"] is True
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_subprocess_optimizer_plugin_cli_writes_executed_candidate(
    tmp_path,
    capsys,
):
    context = tmp_path / "slice-repair-context.json"
    plugin_manifest = tmp_path / "optimizer-gate-subprocess-plugin-manifest.json"
    runtime_script = tmp_path / "subprocess_optimizer.py"
    output = tmp_path / "slice-patches.json"
    context.write_text(
        json.dumps(
            {
                "recommended_patch_contract": {
                    "module_id": "multilingual_variant_explanation",
                    "section_id": "output_format",
                    "based_on_slices": ["dev/category/multilingual_pt"],
                    "target_slice": "multilingual_pt",
                    "before_text": "return concise JSON",
                    "protected_slices": ["multilingual_th"],
                    "protected_sections": ["role"],
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    runtime_script.write_text(
        "import json, sys\n"
        "payload = json.load(sys.stdin)\n"
        "contract = payload['contract']\n"
        "json.dump({\n"
        "  'critic_feedback': 'subprocess optimizer saw ' + payload['optimizer'],\n"
        "  'after_text': contract.get('before_text', '') + '\\nsubprocess runtime patch',\n"
        "  'response_id': 'subprocess-cli-001'\n"
        "}, sys.stdout)\n",
        encoding="utf-8",
    )
    plugin_manifest.write_text(
        json.dumps(
            _subprocess_optimizer_plugin_manifest_fixture(
                command=[sys.executable, str(runtime_script)]
            )
        ),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "generate-slice-patches",
        "--context",
        str(context),
        "--optimizer",
        "subprocess-textgrad-plugin",
        "--plugin-manifest",
        str(plugin_manifest),
        "--execute-optimizer",
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["optimizer"] == "subprocess-textgrad-plugin"
    assert payload["optimizer_runtime"]["status"] == "executed"
    assert payload["optimizer_runtime"]["provider"] == "local-subprocess-json"
    assert payload["candidates"][0]["candidate_strategy"] == "plugin_subprocess_json"
    assert "subprocess runtime patch" in payload["candidates"][0]["after_text"]
    assert payload["executes_tool"] is True
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_python_package_optimizer_plugin_cli_writes_executed_candidate(
    tmp_path,
    monkeypatch,
    capsys,
):
    package_dir = tmp_path / "cli_optimizer_runtime"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text(
        "\n".join(
            [
                "__version__ = '1.0.0'",
                "class FixtureOptimizerAdapter:",
                "    def generate_slice_patch_candidate(self, payload):",
                "        return {",
                "            'after_text': payload['contract']['before_text'] + '\\ncli package patch',",
                "            'critic_feedback': 'cli package adapter called',",
                "            'candidate_strategy': 'cli_python_package_runtime',",
                "        }",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    context = tmp_path / "slice-repair-context.json"
    plugin_manifest = tmp_path / "optimizer-gate-python-package-plugin-manifest.json"
    output = tmp_path / "slice-patches.json"
    context.write_text(
        json.dumps(
            {
                "recommended_patch_contract": {
                    "module_id": "multilingual_variant_explanation",
                    "section_id": "output_format",
                    "based_on_slices": ["dev/category/multilingual_pt"],
                    "target_slice": "multilingual_pt",
                    "before_text": "return concise JSON",
                    "protected_slices": ["multilingual_th"],
                    "protected_sections": ["role"],
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    plugin_manifest.write_text(
        json.dumps(
            _python_package_optimizer_plugin_manifest_fixture(
                package_import="cli_optimizer_runtime",
                candidate_method="generate_slice_patch_candidate",
            )
        ),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "generate-slice-patches",
        "--context",
        str(context),
        "--optimizer",
        "python-package-optimizer-plugin",
        "--plugin-manifest",
        str(plugin_manifest),
        "--execute-optimizer",
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "completed"
    assert payload["optimizer_runtime"]["status"] == "executed"
    assert payload["optimizer_runtime"]["provider"] == "python-package"
    assert payload["optimizer_runtime"]["package_version"] == "1.0.0"
    assert payload["optimizer_runtime"]["fallback_used"] is False
    assert payload["executes_tool"] is True
    assert payload["executes_optimizer_runtime"] is True
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert payload["candidates"][0]["candidate_strategy"] == (
        "cli_python_package_runtime"
    )
    assert "cli package patch" in payload["candidates"][0]["after_text"]
    assert output.exists()


def test_dspy_mipro_package_optimizer_cli_writes_executed_candidate(
    tmp_path,
    monkeypatch,
    capsys,
):
    dspy_runtime_path = (
        Path(__file__).resolve().parents[2]
        / ".research_cache"
        / "optimizer-runtime-packages"
        / "dspy"
    )
    if not (dspy_runtime_path / "dspy").exists():
        pytest.skip("dspy package runtime cache is not installed")
    monkeypatch.syspath_prepend(str(dspy_runtime_path))
    context = tmp_path / "slice-repair-context.json"
    output = tmp_path / "slice-patches.json"
    context.write_text(
        json.dumps(
            {
                "recommended_patch_contract": {
                    "module_id": "multilingual_variant_explanation",
                    "section_id": "output_format",
                    "based_on_slices": ["dev/category/multilingual_pt"],
                    "target_slice": "multilingual_pt",
                    "before_text": "return concise JSON",
                    "protected_slices": ["multilingual_th"],
                    "protected_sections": ["role"],
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "generate-slice-patches",
        "--context",
        str(context),
        "--optimizer",
        "dspy-mipro-package",
        "--execute-optimizer",
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "completed"
    assert payload["optimizer"] == "dspy-mipro-package"
    assert payload["optimizer_runtime"]["status"] == "executed"
    assert payload["optimizer_runtime"]["provider"] == "python-package"
    assert payload["optimizer_runtime"]["package_import"] == "dspy"
    assert payload["optimizer_runtime"]["package_version"] == "3.2.1"
    assert payload["optimizer_runtime"]["dspy_api"]["mipro_class"] == "MIPROv2"
    assert payload["optimizer_runtime"]["fallback_used"] is False
    assert payload["executes_optimizer_runtime"] is True
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert payload["candidates"][0]["candidate_strategy"] == (
        "dspy_mipro_package_runtime"
    )
    assert "multilingual_pt" in payload["candidates"][0]["after_text"]
    assert output.exists()


def test_subprocess_optimizer_plugin_cli_probes_runtime(
    tmp_path,
    capsys,
):
    plugin_manifest = tmp_path / "optimizer-gate-subprocess-plugin-manifest.json"
    runtime_script = tmp_path / "subprocess_optimizer.py"
    output = tmp_path / "optimizer-runtime-probe.json"
    runtime_script.write_text(
        "import json, sys\n"
        "payload = json.load(sys.stdin)\n"
        "if payload.get('task') == 'probe_optimizer_runtime':\n"
        "    json.dump({\n"
        "      'status': 'ready',\n"
        "      'runtime_ready': True,\n"
        "      'probe_detail': 'subprocess probe ok',\n"
        "      'response_id': 'probe-cli-001'\n"
        "    }, sys.stdout)\n"
        "    raise SystemExit(0)\n"
        "json.dump({'status': 'unexpected'}, sys.stdout)\n",
        encoding="utf-8",
    )
    plugin_manifest.write_text(
        json.dumps(
            _subprocess_optimizer_plugin_manifest_fixture(
                command=[sys.executable, str(runtime_script)]
            )
        ),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "probe-optimizer-runtime",
        "--optimizer",
        "subprocess-textgrad-plugin",
        "--plugin-manifest",
        str(plugin_manifest),
        "--execute-probe",
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == "2026-06-05.optimizer-runtime-probe.v1"
    assert payload["status"] == "ready"
    assert payload["runtime_ready"] is True
    assert payload["runtime"]["provider"] == "local-subprocess-json"
    assert payload["executes_tool"] is True
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_python_package_optimizer_plugin_cli_probes_runtime(
    tmp_path,
    capsys,
):
    plugin_manifest = tmp_path / "optimizer-gate-python-package-plugin-manifest.json"
    output = tmp_path / "optimizer-runtime-probe.json"
    plugin_manifest.write_text(
        json.dumps(
            _python_package_optimizer_plugin_manifest_fixture(package_import="json")
        ),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "probe-optimizer-runtime",
        "--optimizer",
        "python-package-optimizer-plugin",
        "--plugin-manifest",
        str(plugin_manifest),
        "--execute-probe",
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == "2026-06-05.optimizer-runtime-probe.v1"
    assert payload["status"] == "ready"
    assert payload["runtime_ready"] is True
    assert payload["runtime"]["provider"] == "python-package"
    assert payload["probe_result"]["package_import"] == "json"
    assert payload["probe_result"]["import_available"] is True
    assert payload["executes_tool"] is True
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_optimizer_package_runtime_benefit_audit_cli_builds_artifact(
    tmp_path,
    capsys,
):
    runtime_probe = tmp_path / "optimizer-runtime-probe.json"
    candidates = tmp_path / "slice-patch-candidates.json"
    gate_decision = tmp_path / "gate-decision.json"
    output = tmp_path / "optimizer-package-runtime-benefit-audit.json"
    runtime_probe.write_text(
        json.dumps({
            "schema_version": "2026-06-05.optimizer-runtime-probe.v1",
            "status": "ready",
            "runtime_ready": True,
            "optimizer": {"name": "textgrad-python-package"},
            "probe_result": {
                "package_import": "textgrad",
                "package_version": "0.1.8",
                "textgrad_api": {"variable_class": "Variable"},
            },
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    candidates.write_text(
        json.dumps({
            "schema_version": "2026-06-04.slice-patch-candidates.v1",
            "status": "completed",
            "optimizer": "textgrad-python-package",
            "candidate_count": 1,
            "candidates": [{"patch_id": "patch-cli-001"}],
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    gate_decision.write_text(
        json.dumps({
            "schema_version": "2026-06-05.gate-policy-decision.v1",
            "status": "passed_for_canary",
            "metric_delta": {"SHIFT": 0.5},
            "gate": {"canary_allowed": True},
            "hard_blockers": [],
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-optimizer-package-runtime-benefit-audit",
        "--optimizer-runtime-probe",
        str(runtime_probe),
        "--slice-patch-candidates",
        str(candidates),
        "--gate-decision",
        str(gate_decision),
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == (
        "2026-06-16.optimizer-package-runtime-benefit-audit.v1"
    )
    assert payload["status"] == "benefit_verified"
    assert payload["gate"]["benefit_verified"] is True
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_method_proposal_generation_trace_cli_builds_artifact(
    tmp_path,
    capsys,
):
    generation_context = tmp_path / "generation-context.json"
    generation_run = tmp_path / "generation-run.json"
    reasoning_trace = tmp_path / "reasoning-trace.json"
    proposals = tmp_path / "method-proposals.json"
    ranking_decisions = tmp_path / "ranking-decisions.json"
    gate_results = tmp_path / "gate-results.json"
    output = tmp_path / "method-proposal-generation-trace.json"

    generation_context.write_text(
        json.dumps({
            "task_family": "smol_worldcup",
            "failure_slice": "multilingual_bn",
            "objective": "search for robust prompt repair methods",
        }),
        encoding="utf-8",
    )
    generation_run.write_text(
        json.dumps({
            "generator": "llm-method-search",
            "model": "qwen/qwen3-8b",
            "prompt_template_id": "method-search-v1",
        }),
        encoding="utf-8",
    )
    reasoning_trace.write_text(
        json.dumps({
            "trace_kind": "structured_rationale",
            "steps": [
                {
                    "step_id": "reason-cli-001",
                    "summary": "Target the locale-specific output format first.",
                    "proposal_ids": ["proposal-cli-001"],
                }
            ],
        }),
        encoding="utf-8",
    )
    proposals.write_text(
        json.dumps({
            "proposals": [
                {
                    "proposal_id": "proposal-cli-001",
                    "method": "section_patch",
                    "target_scope": "multilingual_variant_explanation/output_format",
                    "rationale": "Constrain output format for BN cases.",
                },
                {
                    "proposal_id": "proposal-cli-002",
                    "method": "global_prompt_rewrite",
                    "target_scope": "global",
                    "rationale": "Rewrite all answer instructions.",
                },
            ]
        }),
        encoding="utf-8",
    )
    ranking_decisions.write_text(
        json.dumps({
            "decisions": [
                {
                    "proposal_id": "proposal-cli-001",
                    "rank": 1,
                    "decision": "selected_for_validation",
                    "score": 0.8,
                    "rationale": "Narrower patch.",
                },
                {
                    "proposal_id": "proposal-cli-002",
                    "rank": 2,
                    "decision": "rejected",
                    "score": 0.2,
                    "rationale": "Too broad for current gate.",
                },
            ]
        }),
        encoding="utf-8",
    )
    gate_results.write_text(
        json.dumps({
            "results": [
                {
                    "proposal_id": "proposal-cli-001",
                    "gate_status": "passed_for_canary",
                    "metric_delta": {"SHIFT": 0.4},
                    "hard_blockers": [],
                }
            ]
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-method-proposal-generation-trace",
        "--generation-context",
        str(generation_context),
        "--generation-run",
        str(generation_run),
        "--reasoning-trace",
        str(reasoning_trace),
        "--proposals",
        str(proposals),
        "--ranking-decisions",
        str(ranking_decisions),
        "--selected-proposal-id",
        "proposal-cli-001",
        "--gate-results",
        str(gate_results),
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == (
        "2026-06-16.method-proposal-generation-trace.v1"
    )
    assert payload["proposal_count"] == 2
    assert payload["selected_proposal_count"] == 1
    assert payload["pruned_proposal_count"] == 1
    assert payload["reasoning_trace"]["records_private_chain_of_thought"] is False
    assert payload["validation_links"][0]["gate_status"] == "passed_for_canary"
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_method_search_study_cli_runs_ask_tell_chain(tmp_path, capsys):
    study_output = tmp_path / "method-search-study.json"
    ask_output = tmp_path / "method-search-ask.json"
    ask_dir = tmp_path / "ask"
    gate_result = tmp_path / "gate-result.json"
    tell_output = tmp_path / "method-search-tell.json"
    feedback_store = tmp_path / "gate-feedback-memory-store.json"
    llm_proposals = tmp_path / "llm-proposals.json"
    second_llm_proposals = tmp_path / "llm-proposals-round-2.json"
    second_ask_output = tmp_path / "method-search-ask-round-2.json"
    sampler_adapter_output = tmp_path / "optuna-sampler-adapter.json"
    storage_adapter_output = tmp_path / "optuna-storage-adapter.json"
    dashboard_export_output = tmp_path / "optuna-dashboard-export.json"

    llm_proposals.write_text(
        json.dumps({
            "proposals": [
                {
                    "proposal_id": "proposal-cli-combine",
                    "operator_id": "combine",
                    "why_this_operator_applies": "Combine locale evidence with strict JSON output.",
                    "hypothesis": "A section-local combined instruction may reduce BN errors.",
                    "change_surface": "prompt_section",
                    "expected_effect": "local gate may improve the target slice",
                    "risk": "protected slices may regress",
                    "cheapest_validation": "run local slice gate on dev rows",
                    "rollback_or_stop_condition": "stop on hard blocker",
                }
            ]
        }),
        encoding="utf-8",
    )
    second_llm_proposals.write_text(
        json.dumps({
            "proposals": [
                {
                    "proposal_id": "proposal-cli-combine-round-2",
                    "operator_id": "combine",
                    "why_this_operator_applies": "Combine remains a candidate but has prior hard blockers.",
                    "hypothesis": "A broader combined instruction might help, pending gate.",
                    "change_surface": "prompt_section",
                    "expected_effect": "local gate decides the outcome",
                    "risk": "same protected-slice regression pattern may recur",
                    "cheapest_validation": "run local slice gate on dev rows",
                    "rollback_or_stop_condition": "stop on hard blocker",
                },
                {
                    "proposal_id": "proposal-cli-adapt-round-2",
                    "operator_id": "adapt",
                    "why_this_operator_applies": "Adapt avoids the blocked combine pattern.",
                    "hypothesis": "A narrower adapted contract may reduce risk.",
                    "change_surface": "prompt_section",
                    "expected_effect": "local gate decides the outcome",
                    "risk": "could underfit the failing slice",
                    "cheapest_validation": "run local slice gate on dev rows",
                    "rollback_or_stop_condition": "stop on hard blocker",
                },
            ]
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-method-search-study",
        "--study-name",
        "smol-method-search",
        "--objective",
        "search local prompt repair methods",
        "--operator",
        "combine",
        "--operator",
        "adapt",
        "--output",
        str(study_output),
        "--json",
    ])
    study_payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert study_payload["schema_version"] == "2026-06-19.method-search-study.v1"
    assert study_payload["optuna_compatibility"]["supports_ask_tell"] is True
    assert study_payload["official_scores_claimed"] is False

    exit_code = main([
        "proposal",
        "ask-method-search-trial",
        "--study",
        str(study_output),
        "--objective",
        "reduce BN failures with local evidence only",
        "--operator",
        "combine",
        "--operator",
        "adapt",
        "--llm-proposals",
        str(llm_proposals),
        "--model",
        "qwen/qwen3-8b",
        "--adapter",
        "llm-method-search-fixture",
        "--slice-id",
        "dev/category/multilingual_bn",
        "--patch-scope",
        "single_module_single_section",
        "--budget-json",
        '{"max_candidates": 1}',
        "--output-dir",
        str(ask_dir),
        "--output",
        str(ask_output),
        "--json",
    ])
    ask_payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert ask_payload["schema_version"] == "2026-06-19.method-search-ask.v1"
    assert ask_payload["trials"][0]["state"] == "WAITING"
    assert ask_payload["method_proposal_generation_trace"]["proposal_count"] == 1
    assert ask_payload["official_scores_claimed"] is False

    gate_result.write_text(
        json.dumps({
            "proposal_id": ask_payload["trials"][0]["proposal_id"],
            "operator_id": ask_payload["trials"][0]["params"]["operator"],
            "status": "blocked",
            "score": 0.0,
            "hard_blockers": ["slice_regression"],
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "tell-method-search-trial",
        "--study",
        str(ask_output),
        "--trial-id",
        ask_payload["trials"][0]["trial_id"],
        "--gate-result",
        str(gate_result),
        "--feedback-store",
        str(feedback_store),
        "--output",
        str(tell_output),
        "--json",
    ])
    tell_payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert tell_payload["schema_version"] == "2026-06-19.method-search-tell.v1"
    assert tell_payload["trial"]["state"] == "PRUNED"
    assert tell_payload["gate_feedback_memory"]["operator_weights"]["combine"] < 1.0
    assert tell_payload["feedback_store"]["path"] == str(feedback_store)
    assert tell_payload["acceptance_answers"]["claim_boundary"][
        "official_scores_claimed"
    ] is False
    assert tell_output.exists()
    assert feedback_store.exists()

    exit_code = main([
        "proposal",
        "ask-method-search-trial",
        "--study",
        str(tell_output),
        "--operator",
        "combine",
        "--operator",
        "adapt",
        "--gate-feedback-memory-store",
        str(feedback_store),
        "--llm-proposals",
        str(second_llm_proposals),
        "--output",
        str(second_ask_output),
        "--json",
    ])
    second_ask_payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert second_ask_payload["sampler"]["selected_operator_ids"] == ["adapt"]
    assert second_ask_payload["trials"][0]["params"]["operator"] == "adapt"
    assert second_ask_payload["study"]["sampler_state"]["feedback_store_ref"] == str(
        feedback_store
    )

    exit_code = main([
        "proposal",
        "build-optuna-sampler-adapter",
        "--study",
        str(tell_output),
        "--output",
        str(sampler_adapter_output),
        "--json",
    ])
    sampler_adapter = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert sampler_adapter["adapter_name"] == "OptunaSamplerAdapter"

    exit_code = main([
        "proposal",
        "build-optuna-storage-adapter",
        "--study",
        str(tell_output),
        "--gate-feedback-memory-store",
        str(feedback_store),
        "--output",
        str(storage_adapter_output),
        "--json",
    ])
    storage_adapter = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert storage_adapter["adapter_name"] == "OptunaStorageAdapter"
    assert storage_adapter["feedback_store"]["record_count"] == 1

    exit_code = main([
        "proposal",
        "build-optuna-dashboard-export",
        "--study",
        str(tell_output),
        "--gate-feedback-memory-store",
        str(feedback_store),
        "--output",
        str(dashboard_export_output),
        "--json",
    ])
    dashboard_export = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert dashboard_export["export_name"] == "OptunaDashboardExport"
    assert dashboard_export["official_scores_claimed"] is False


def test_multi_optimizer_candidate_race_cli_writes_winner_bundle(tmp_path, capsys):
    candidate_sources = tmp_path / "candidate-sources.json"
    gate_results = tmp_path / "gate-results.json"
    output = tmp_path / "multi-optimizer-candidate-race.json"
    output_dir = tmp_path / "race-artifacts"
    feedback_store = tmp_path / "gate-feedback-memory-store.json"
    candidate_sources.write_text(
        json.dumps({
            "sources": [
                {
                    "source_id": "llm-hexagon",
                    "optimizer": "llm",
                    "proposals": [
                        {
                            "proposal_id": "llm-001",
                            "operator_id": "adapt",
                            "why_this_operator_applies": "Adapt targets the failing slice.",
                            "hypothesis": "The LLM proposal may reduce slice errors.",
                            "change_surface": "prompt_section",
                            "expected_effect": "gate decides the effect",
                            "risk": "canary regression",
                            "cheapest_validation": "run shared gate",
                            "rollback_or_stop_condition": "stop on hard blocker",
                        }
                    ],
                },
                {
                    "source_id": "optuna-tpe",
                    "optimizer": "optuna",
                    "proposals": [
                        {
                            "proposal_id": "optuna-049",
                            "operator_id": "combine",
                            "why_this_operator_applies": "Combine feature families.",
                            "hypothesis": "Optuna-selected parameters may improve validation.",
                            "change_surface": "classifier_features",
                            "expected_effect": "gate decides the effect",
                            "risk": "overfits local split",
                            "cheapest_validation": "run shared gate",
                            "rollback_or_stop_condition": "stop on non-positive delta",
                        }
                    ],
                },
            ]
        }),
        encoding="utf-8",
    )
    gate_results.write_text(
        json.dumps({
            "gate_results": [
                {
                    "proposal_id": "llm-001",
                    "operator_id": "adapt",
                    "status": "blocked",
                    "score": 0.66,
                    "hard_blockers": ["canary_regression"],
                },
                {
                    "proposal_id": "optuna-049",
                    "operator_id": "combine",
                    "status": "passed",
                    "score": 0.7,
                    "metric_delta": {"accuracy": 0.01},
                    "hard_blockers": [],
                },
            ]
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-multi-optimizer-candidate-race",
        "--race-name",
        "sst2-race",
        "--objective",
        "pick the best optimizer candidate under one gate",
        "--candidate-sources",
        str(candidate_sources),
        "--gate-results",
        str(gate_results),
        "--operator",
        "combine",
        "--operator",
        "adapt",
        "--output-dir",
        str(output_dir),
        "--feedback-store",
        str(feedback_store),
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == "2026-06-25.multi-optimizer-candidate-race.v1"
    assert payload["winner"]["proposal_id"] == "optuna-049"
    assert payload["study"]["trial_count"] == 2
    assert payload["acceptance_answers"]["winner_selected_by_gate"] is True
    assert payload["official_scores_claimed"] is False
    assert output.exists()
    assert feedback_store.exists()


def test_run_multi_optimizer_candidate_race_cli_generates_and_races(
    tmp_path,
    capsys,
):
    context = tmp_path / "slice-repair-context.json"
    llm_proposals = tmp_path / "llm-proposals.json"
    gate_results = tmp_path / "gate-results.json"
    output = tmp_path / "multi-optimizer-candidate-race-run.json"
    output_dir = tmp_path / "run"
    feedback_store = tmp_path / "gate-feedback-memory-store.json"
    context.write_text(
        json.dumps({
            "recommended_patch_contract": {
                "module_id": "router",
                "section_id": "country_aliases",
                "target_slice": "alias_confusion",
                "based_on_slices": ["alias_confusion"],
                "before_text": "Resolve aliases conservatively.",
                "protected_slices": ["exact_match"],
            },
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    llm_proposals.write_text(
        json.dumps({
            "proposals": [
                {
                    "proposal_id": "llm-001",
                    "operator_id": "adapt",
                    "why_this_operator_applies": "Adapt targets the failing slice.",
                    "hypothesis": "The LLM proposal may reduce slice errors.",
                    "change_surface": "prompt_section",
                    "expected_effect": "gate decides the effect",
                    "risk": "canary regression",
                    "cheapest_validation": "run shared gate",
                    "rollback_or_stop_condition": "stop on hard blocker",
                }
            ]
        }),
        encoding="utf-8",
    )
    gate_results.write_text(
        json.dumps({
            "gate_results": [
                {
                    "proposal_id": "llm-001",
                    "operator_id": "adapt",
                    "status": "blocked",
                    "score": 0.61,
                    "hard_blockers": ["canary_regression"],
                },
                {
                    "proposal_id": "optuna-001",
                    "operator_id": "combine",
                    "status": "passed",
                    "score": 0.72,
                    "hard_blockers": [],
                },
                {
                    "proposal_id": "textgrad-001",
                    "operator_id": "adapt",
                    "status": "passed",
                    "score": 0.69,
                    "hard_blockers": [],
                },
                {
                    "proposal_id": "dspy-001",
                    "operator_id": "combine",
                    "status": "blocked",
                    "score": 0.63,
                    "hard_blockers": ["fallback_not_real_runtime"],
                },
                {
                    "proposal_id": "heuristic-001",
                    "operator_id": "separate",
                    "status": "blocked",
                    "score": 0.60,
                    "hard_blockers": ["no_local_improvement"],
                },
            ]
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "run-multi-optimizer-candidate-race",
        "--race-name",
        "execution-capable-race",
        "--objective",
        "generate and compare multiple optimizer candidates",
        "--mode",
        "review/dry-run",
        "--context",
        str(context),
        "--gate-results",
        str(gate_results),
        "--llm-proposals",
        str(llm_proposals),
        "--operator",
        "combine",
        "--operator",
        "adapt",
        "--operator",
        "separate",
        "--output-dir",
        str(output_dir),
        "--feedback-store",
        str(feedback_store),
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == (
        "2026-06-25.multi-optimizer-candidate-race-run.v1"
    )
    assert payload["winner"]["proposal_id"] == "optuna-001"
    assert payload["source_generation"]["generated_candidate_count"] == 5
    assert payload["acceptance_answers"]["parallel_generation_used"] is True
    assert output.exists()
    assert (output_dir / "generated-candidate-sources.json").exists()
    assert feedback_store.exists()


def test_run_method_search_trajectory_cli_runs_three_rounds(tmp_path, capsys):
    runtime_dir = tmp_path / "cli_trajectory_optimizer"
    runtime_dir.mkdir()
    (runtime_dir / "__init__.py").write_text(
        """
__version__ = "1.0.0"


class FixtureOptimizerAdapter:
    def generate_slice_patch_candidate(self, payload):
        contract = payload["contract"]
        return {
            "after_text": contract.get("before_text", "") + "\\ntrajectory patch",
            "critic_feedback": "trajectory optimizer produced a candidate",
            "candidate_strategy": "trajectory_python_package_runtime",
        }
""".lstrip(),
        encoding="utf-8",
    )
    sys.path.insert(0, str(tmp_path))
    context = tmp_path / "slice-repair-context.json"
    plugin_manifest = tmp_path / "plugin-manifest.json"
    gate_round_1 = tmp_path / "gate-round-1.json"
    gate_round_2 = tmp_path / "gate-round-2.json"
    gate_round_3 = tmp_path / "gate-round-3.json"
    output_dir = tmp_path / "trajectory"
    output = tmp_path / "method-search-trajectory.json"
    feedback_store = tmp_path / "gate-feedback-memory-store.json"
    context.write_text(
        json.dumps({
            "recommended_patch_contract": {
                "module_id": "router",
                "section_id": "country_aliases",
                "target_slice": "alias_confusion",
                "based_on_slices": ["alias_confusion"],
                "before_text": "Resolve aliases conservatively.",
                "protected_slices": ["exact_match"],
            },
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    plugin_manifest.write_text(
        json.dumps(
            _python_package_optimizer_plugin_manifest_fixture(
                package_import="cli_trajectory_optimizer",
                candidate_method="generate_slice_patch_candidate",
            )
        ),
        encoding="utf-8",
    )
    for path, score in (
        (gate_round_1, 0.62),
        (gate_round_2, 0.71),
        (gate_round_3, 0.76),
    ):
        path.write_text(
            json.dumps({
                "gate_results": [
                    {
                        "proposal_id": "python-package-optimizer-plugin-001",
                        "operator_id": "adapt",
                        "status": "passed",
                        "score": score,
                        "hard_blockers": [],
                    }
                ]
            }),
            encoding="utf-8",
        )

    exit_code = main([
        "proposal",
        "run-method-search-trajectory",
        "--trajectory-name",
        "cli-three-round-trajectory",
        "--objective",
        "find a best local optimizer path",
        "--context",
        str(context),
        "--round-gate-results",
        str(gate_round_1),
        "--round-gate-results",
        str(gate_round_2),
        "--round-gate-results",
        str(gate_round_3),
        "--round-count",
        "3",
        "--optimizer-source",
        "python-package-optimizer-plugin",
        "--operator",
        "adapt",
        "--plugin-manifest",
        str(plugin_manifest),
        "--output-dir",
        str(output_dir),
        "--feedback-store",
        str(feedback_store),
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == "2026-06-27.method-search-trajectory.v1"
    assert payload["round_count"] == 3
    assert payload["best_path"]["winner"]["score"] == 0.76
    assert payload["real_optimizer_candidate_count"] == 3
    assert payload["acceptance_answers"]["rounds_executed"] == 3
    assert payload["official_scores_claimed"] is False
    assert output.exists()
    assert (output_dir / "round-003" / "multi-optimizer-candidate-race-run.json").exists()
    assert feedback_store.exists()


def test_run_real_benchmark_readiness_cli_dispatches_runner(
    tmp_path,
    capsys,
    monkeypatch,
):
    rows = tmp_path / "rows.json"
    context = tmp_path / "slice-repair-context.json"
    plugin_manifest = tmp_path / "plugin-manifest.json"
    output_dir = tmp_path / "readiness"
    output = tmp_path / "real-benchmark-readiness-run.json"
    feedback_store = tmp_path / "gate-feedback-memory-store.json"
    rows.write_text(
        json.dumps({
            "rows": [
                _smol_cli_eval_row(
                    row_id="S1-H1-001",
                    category="reasoning",
                    auto_grade="answer_match",
                    answer_key={"answer": "Brazil"},
                )
            ]
        }),
        encoding="utf-8",
    )
    context.write_text(
        json.dumps({
            "recommended_patch_contract": {
                "module_id": "router",
                "section_id": "country_aliases",
                "target_slice": "alias_confusion",
                "based_on_slices": ["alias_confusion"],
                "before_text": "Resolve aliases conservatively.",
                "protected_slices": ["exact_match"],
            },
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    plugin_manifest.write_text(
        json.dumps(
            _python_package_optimizer_plugin_manifest_fixture(
                package_import="cli_readiness_optimizer",
                candidate_method="generate_slice_patch_candidate",
            )
        ),
        encoding="utf-8",
    )
    called = {}

    def fake_run_real_benchmark_readiness_run(**kwargs):
        called.update(kwargs)
        return {
            "schema_version": "2026-06-27.real-benchmark-readiness-run.v1",
            "status": "completed",
            "benchmark_id": kwargs["benchmark_id"],
            "round_count": kwargs["round_count"],
            "official_scores_claimed": False,
        }

    monkeypatch.setattr(
        "scripts.cli.run_real_benchmark_readiness_run",
        fake_run_real_benchmark_readiness_run,
    )

    exit_code = main([
        "proposal",
        "run-real-benchmark-readiness",
        "--run-name",
        "cli-real-readiness",
        "--objective",
        "verify real eval driven optimizer gate",
        "--benchmark-id",
        "smol_worldcup",
        "--rows",
        str(rows),
        "--context",
        str(context),
        "--round-count",
        "3",
        "--optimizer-source",
        "python-package-optimizer-plugin",
        "--operator",
        "adapt",
        "--plugin-manifest",
        str(plugin_manifest),
        "--model",
        "fixture-model",
        "--base-url",
        "http://127.0.0.1:8000/v1",
        "--output-dir",
        str(output_dir),
        "--feedback-store",
        str(feedback_store),
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == "2026-06-27.real-benchmark-readiness-run.v1"
    assert called["run_name"] == "cli-real-readiness"
    assert called["rows"] == rows
    assert called["context"] == context
    assert called["optimizer_sources"] == ["python-package-optimizer-plugin"]
    assert called["operators"] == ["adapt"]
    assert called["optimizer_gate_plugin_manifests"] == [plugin_manifest]
    assert called["model"] == "fixture-model"
    assert called["output_dir"] == output_dir
    assert called["output_path"] == output
    assert payload["official_scores_claimed"] is False


def test_materialize_slice_patch_cli_writes_review_bundle(tmp_path, capsys):
    candidate = tmp_path / "slice-patches.json"
    output = tmp_path / "slice-patch-materialization.json"
    candidate.write_text(
        json.dumps(
            {
                "candidates": [
                    {
                        "patch_id": "slice-patch-001",
                        "module_id": "multilingual_variant_explanation",
                        "section_id": "output_format",
                        "before_text": "return concise JSON",
                        "after_text": "return concise JSON with locale evidence",
                        "protected_slices": ["multilingual_th"],
                        "protected_sections": ["role"],
                        "official_scores_claimed": False,
                    }
                ],
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "materialize-slice-patch",
        "--candidate",
        str(candidate),
        "--base-profile-id",
        "p3-dev-v2",
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "needs_prompt_profile_registration"
    assert payload["execution_ready"] is False
    assert output.exists()
    assert payload["official_scores_claimed"] is False


def test_optimizer_gate_run_cli_writes_non_executing_bundle(tmp_path, capsys):
    context = tmp_path / "slice-repair-context.json"
    output_dir = tmp_path / "optimizer-gate-run"
    context.write_text(
        json.dumps(
            {
                "recommended_patch_contract": {
                    "module_id": "multilingual_variant_explanation",
                    "section_id": "output_format",
                    "based_on_slices": ["dev/category/multilingual_pt"],
                    "target_slice": "multilingual_pt",
                    "before_text": "return concise JSON",
                    "protected_slices": ["multilingual_th"],
                    "protected_sections": ["role"],
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-optimizer-gate-run",
        "--context",
        str(context),
        "--base-profile-id",
        "p3-system-fixture",
        "--optimizer",
        "promptwizard-constrained",
        "--output-dir",
        str(output_dir),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == "2026-06-05.optimizer-gate-run.v1"
    assert payload["status"] == "needs_prompt_profile_registration"
    assert payload["optimizer"]["registry_ref"] == (
        "optimizer_adapter:promptwizard-constrained"
    )
    assert payload["optimizer"]["adapter_type"] == "deterministic_local"
    assert payload["runtime_probe"]["status"] == "not_required"
    assert payload["stages"][0]["name"] == "probe_optimizer_runtime"
    assert "evaluate_gate_policy" in payload["gate_plan"]["required_gates"]
    assert "gate_policy:slice-dev-hard-gate" in payload["gate_plan"]["policy_refs"]
    assert payload["gate_plan"]["canary_allowed"] is False
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert (output_dir / "optimizer-runtime-probe.json").exists()
    assert (output_dir / "optimizer-gate-run.json").exists()


def test_optimizer_gate_system_spec_cli_writes_registry(tmp_path, capsys):
    plugin_manifest = tmp_path / "optimizer-gate-plugin-manifest.json"
    output = tmp_path / "optimizer-gate-system-spec.json"
    plugin_manifest.write_text(
        json.dumps(_optimizer_gate_plugin_manifest_fixture()),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-optimizer-gate-system-spec",
        "--plugin-manifest",
        str(plugin_manifest),
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == "2026-06-05.optimizer-gate-system-spec.v1"
    assert any(
        item["name"] == "textgrad-openai-compatible"
        for item in payload["optimizer_adapters"]
    )
    assert any(
        item["name"] == "promptwizard-constrained"
        and item["candidate_schema"] == "2026-06-04.slice-patch-candidate.v1"
        for item in payload["optimizer_adapters"]
    )
    assert any(
        item["policy_id"] == "paired-repeat-variance-gate"
        for item in payload["gate_policies"]
    )
    assert any(
        item["policy_id"] == "slice-dev-hard-gate"
        and item["function"] == "evaluate_gate_policy"
        and item["decision_schema"] == "2026-06-05.gate-policy-decision.v1"
        for item in payload["gate_policies"]
    )
    assert any(
        item["name"] == "dspy-mipro-local" and item["source"] == "plugin"
        for item in payload["optimizer_adapters"]
    )
    assert any(
        item["benchmark_id"] == "smol_worldcup"
        for item in payload["benchmark_adapters"]
    )
    assert payload["plugin_manifests"][0]["plugin_id"] == "local-dspy-fixture"
    assert payload["executes_tool"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_optimizer_gate_execution_plan_cli_writes_non_executing_plan(
    tmp_path,
    capsys,
):
    run_path = tmp_path / "optimizer-gate-run.json"
    output = tmp_path / "optimizer-gate-execution-plan.json"
    run_path.write_text(
        json.dumps({
            "schema_version": "2026-06-05.optimizer-gate-run.v1",
            "status": "needs_prompt_profile_registration",
            "base_profile_id": "p3-system-fixture",
            "optimizer": {
                "name": "promptwizard-constrained",
                "candidate_count": 1,
            },
            "runtime_probe": {
                "status": "not_required",
                "runtime_ready": True,
            },
            "materialization": {
                "status": "needs_prompt_profile_registration",
                "execution_ready": False,
            },
            "gate_plan": {
                "required_gates": [
                    "evaluate_gate_policy",
                    "evaluate_slice_variance_gate",
                    "build_gate_policy_composition",
                ],
                "canary_allowed": False,
                "promotion_ready": False,
            },
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-optimizer-gate-execution-plan",
        "--run",
        str(run_path),
        "--benchmark",
        "smol_worldcup",
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == "2026-06-05.optimizer-gate-execution-plan.v1"
    assert payload["status"] == "needs_prompt_profile_registration"
    assert payload["benchmark_adapter"]["benchmark_id"] == "smol_worldcup"
    assert payload["preflight"]["candidate_count"] == 1
    assert payload["preflight"]["hard_blockers"] == []
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_prompt_profile_registration_plan_cli_writes_review_plan(tmp_path, capsys):
    materialization = tmp_path / "slice-patch-materialization.json"
    output = tmp_path / "prompt-profile-registration-plan.json"
    materialization.write_text(
        json.dumps({
            "schema_version": "2026-06-04.slice-patch-materialization.v1",
            "status": "needs_prompt_profile_registration",
            "base_profile_id": "p3-system-fixture",
            "patch_id": "slice-patch-001",
            "optimizer": "promptwizard-constrained",
            "materialized_change": {
                "module_id": "multilingual_variant_explanation",
                "section_id": "output_format",
                "change_surface": "prompt_section",
                "edit_scope": "single_section",
                "before_text": "return concise JSON",
                "after_text": "return concise JSON with locale evidence",
                "protected_slices": ["multilingual_tr"],
                "protected_sections": ["role"],
            },
            "execution_ready": False,
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-prompt-profile-registration-plan",
        "--materialization",
        str(materialization),
        "--benchmark",
        "smol_worldcup",
        "--proposed-profile-id",
        "p3-system-fixture-slice-patch-001",
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == (
        "2026-06-05.prompt-profile-registration-plan.v1"
    )
    assert payload["status"] == "ready_for_profile_registration_review"
    assert payload["registry_patch"]["operation"] == "add_prompt_profile"
    assert payload["execution_ready"] is False
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_optimizer_gate_execution_preflight_cli_blocks_unregistered_profile(
    tmp_path,
    capsys,
):
    registration_plan = tmp_path / "prompt-profile-registration-plan.json"
    output = tmp_path / "optimizer-gate-execution-preflight.json"
    registration_plan.write_text(
        json.dumps({
            "schema_version": "2026-06-05.prompt-profile-registration-plan.v1",
            "status": "ready_for_profile_registration_review",
            "benchmark_adapter": {"benchmark_id": "smol_worldcup"},
            "materialization_ref": "inline",
            "base_profile_id": "p3-system-fixture",
            "proposed_profile_id": "p3-system-fixture-slice-patch-001",
            "registry_patch": {"operation": "add_prompt_profile"},
            "required_pre_execution_checks": [],
            "gate_constraints": {"canary_allowed_before_dev_gate": False},
            "claim_boundary": "review-only",
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-optimizer-gate-execution-preflight",
        "--registration-plan",
        str(registration_plan),
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == (
        "2026-06-05.optimizer-gate-execution-preflight.v1"
    )
    assert payload["status"] == "blocked_prompt_profile_not_registered"
    assert payload["gate"]["canary_allowed"] is False
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_register_prompt_profile_cli_writes_registration_artifact(tmp_path, capsys):
    registration_plan = tmp_path / "prompt-profile-registration-plan.json"
    output = tmp_path / "prompt-profile-registration.json"
    registration_plan.write_text(
        json.dumps({
            "schema_version": "2026-06-05.prompt-profile-registration-plan.v1",
            "status": "ready_for_profile_registration_review",
            "benchmark_adapter": {"benchmark_id": "smol_worldcup"},
            "materialization_ref": "inline",
            "base_profile_id": "p3-system-fixture",
            "proposed_profile_id": "p3-system-fixture-slice-patch-001",
            "patch_id": "slice-patch-001",
            "materialized_change": {
                "module_id": "multilingual_variant_explanation",
                "section_id": "output_format",
                "change_surface": "prompt_section",
                "edit_scope": "single_section",
                "before_text": "return concise JSON",
                "after_text": "return concise JSON with locale evidence",
                "protected_slices": ["multilingual_tr"],
                "protected_sections": ["role"],
            },
            "registry_patch": {
                "operation": "add_prompt_profile",
                "target_profile_id": "p3-system-fixture-slice-patch-001",
                "base_profile_id": "p3-system-fixture",
            },
            "required_pre_execution_checks": [],
            "gate_constraints": {"canary_allowed_before_dev_gate": False},
            "claim_boundary": "review-only",
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "register-prompt-profile",
        "--registration-plan",
        str(registration_plan),
        "--approve",
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == "2026-06-05.prompt-profile-registration.v1"
    assert payload["status"] == "registered"
    assert payload["registered_profile"]["registered"] is True
    assert payload["registered_profile"]["registered_profile_id"] == (
        "p3-system-fixture-slice-patch-001"
    )
    assert payload["registry_entry"]["patch_id"] == "slice-patch-001"
    assert payload["gate"]["canary_allowed"] is False
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_registered_profile_execution_bundle_cli_writes_non_executing_bundle(
    tmp_path,
    capsys,
):
    registration_plan = tmp_path / "prompt-profile-registration-plan.json"
    registered_profile = tmp_path / "prompt-profile-registration.json"
    output_dir = tmp_path / "registered-profile-execution"
    registration_plan.write_text(
        json.dumps({
            "schema_version": "2026-06-05.prompt-profile-registration-plan.v1",
            "status": "ready_for_profile_registration_review",
            "benchmark_adapter": {"benchmark_id": "smol_worldcup"},
            "materialization_ref": "inline",
            "base_profile_id": "p3-system-fixture",
            "proposed_profile_id": "p3-system-fixture-slice-patch-001",
            "patch_id": "slice-patch-001",
            "materialized_change": {
                "module_id": "multilingual_variant_explanation",
                "section_id": "output_format",
                "change_surface": "prompt_section",
                "edit_scope": "single_section",
                "before_text": "return concise JSON",
                "after_text": "return concise JSON with locale evidence",
            },
            "registry_patch": {
                "operation": "add_prompt_profile",
                "target_profile_id": "p3-system-fixture-slice-patch-001",
                "base_profile_id": "p3-system-fixture",
            },
            "required_pre_execution_checks": [],
            "gate_constraints": {"canary_allowed_before_dev_gate": False},
            "claim_boundary": "review-only",
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    main([
        "proposal",
        "register-prompt-profile",
        "--registration-plan",
        str(registration_plan),
        "--approve",
        "--output",
        str(registered_profile),
        "--json",
    ])
    capsys.readouterr()
    exit_code = main([
        "proposal",
        "build-registered-profile-execution-bundle",
        "--registration-plan",
        str(registration_plan),
        "--registered-profile",
        str(registered_profile),
        "--output-dir",
        str(output_dir),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == (
        "2026-06-05.registered-profile-execution-bundle.v1"
    )
    assert payload["status"] == "blocked_missing_pre_execution_artifacts"
    assert payload["registered_profile"]["registered"] is True
    assert payload["gate"]["canary_allowed"] is False
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert (output_dir / "registered-profile-execution-bundle.json").exists()
    assert (output_dir / "optimizer-gate-execution-preflight.json").exists()


def test_registered_profile_execution_run_cli_generates_leakage_audit(
    tmp_path,
    capsys,
):
    registration_plan = tmp_path / "prompt-profile-registration-plan.json"
    registered_profile = tmp_path / "prompt-profile-registration.json"
    rows_path = tmp_path / "prompt-leakage-rows.json"
    output_dir = tmp_path / "registered-profile-execution-run"
    registration_plan.write_text(
        json.dumps({
            "schema_version": "2026-06-05.prompt-profile-registration-plan.v1",
            "status": "ready_for_profile_registration_review",
            "benchmark_adapter": {"benchmark_id": "smol_worldcup"},
            "materialization_ref": "inline",
            "base_profile_id": "p3-dev-v2",
            "proposed_profile_id": "p3-dev-v2-slice-patch-cli",
            "patch_id": "slice-patch-cli",
            "materialized_change": {
                "module_id": "multilingual_variant_explanation",
                "section_id": "output_format",
                "change_surface": "prompt_section",
                "edit_scope": "single_section",
                "before_text": "return concise JSON",
                "after_text": "return concise JSON with locale evidence",
            },
            "registry_patch": {
                "operation": "add_prompt_profile",
                "target_profile_id": "p3-dev-v2-slice-patch-cli",
                "base_profile_id": "p3-dev-v2",
            },
            "required_pre_execution_checks": [],
            "gate_constraints": {"canary_allowed_before_dev_gate": False},
            "claim_boundary": "review-only",
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    rows_path.write_text(
        json.dumps([
            {
                "id": "S1-I1-001",
                "shift_axis": "instruction_following",
                "category": "multilingual_pt",
                "auto_grade": "json",
                "prompt": "Return a compact JSON answer about a football result.",
            }
        ]),
        encoding="utf-8",
    )

    main([
        "proposal",
        "register-prompt-profile",
        "--registration-plan",
        str(registration_plan),
        "--approve",
        "--output",
        str(registered_profile),
        "--json",
    ])
    capsys.readouterr()
    exit_code = main([
        "proposal",
        "run-registered-profile-execution",
        "--registration-plan",
        str(registration_plan),
        "--registered-profile",
        str(registered_profile),
        "--prompt-leakage-rows",
        str(rows_path),
        "--output-dir",
        str(output_dir),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == "2026-06-05.registered-profile-execution-run.v1"
    assert payload["status"] == "blocked_missing_pre_execution_artifacts"
    assert payload["execution"]["prompt_leakage_audit"]["status"] == "generated"
    assert payload["gate"]["canary_allowed"] is False
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert (output_dir / "prompt-leakage-audit.json").exists()
    assert (output_dir / "registered-profile-execution-run.json").exists()


def test_registered_profile_execution_run_cli_generates_gate_decision(
    tmp_path,
    capsys,
):
    registration_plan = tmp_path / "prompt-profile-registration-plan.json"
    registered_profile = tmp_path / "prompt-profile-registration.json"
    prompt_leakage_audit = tmp_path / "prompt-leakage-audit.json"
    target_smoke = tmp_path / "target-smoke.json"
    dev_model_eval = tmp_path / "dev-model-eval.json"
    output_dir = tmp_path / "registered-profile-execution-run"
    profile_id = "p3-dev-v2-slice-patch-cli-gate"
    registration_plan.write_text(
        json.dumps({
            "schema_version": "2026-06-05.prompt-profile-registration-plan.v1",
            "status": "ready_for_profile_registration_review",
            "benchmark_adapter": {"benchmark_id": "smol_worldcup"},
            "materialization_ref": "inline",
            "base_profile_id": "p3-dev-v2",
            "proposed_profile_id": profile_id,
            "patch_id": "slice-patch-cli-gate",
            "materialized_change": {
                "module_id": "multilingual_variant_explanation",
                "section_id": "output_format",
                "change_surface": "prompt_section",
                "edit_scope": "single_section",
                "before_text": "return concise JSON",
                "after_text": "return concise JSON with locale evidence",
            },
            "registry_patch": {
                "operation": "add_prompt_profile",
                "target_profile_id": profile_id,
                "base_profile_id": "p3-dev-v2",
            },
            "required_pre_execution_checks": [],
            "gate_constraints": {"canary_allowed_before_dev_gate": False},
            "claim_boundary": "review-only",
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    prompt_leakage_audit.write_text(
        json.dumps({
            "schema_version": "2026-05-19.smol-worldcup-prompt-leakage-audit.v1",
            "status": "passed",
            "prompt_profile": profile_id,
            "row_count": 1,
            "leak_count": 0,
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    target_smoke.write_text(
        json.dumps({
            "schema_version": "2026-05-20.smol-worldcup-model-eval.v1",
            "status": "completed",
            "model": {"prompt_profile": profile_id},
            "dataset": {"evaluation_split": "dev", "row_count": 1},
            "metrics": {"SHIFT": 80.0},
            "failure_summary": {"runtime_error_count": 0},
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    dev_model_eval.write_text(
        json.dumps({
            "schema_version": "2026-05-20.smol-worldcup-model-eval.v1",
            "status": "completed",
            "model": {"prompt_profile": profile_id},
            "dataset": {"evaluation_split": "dev", "row_count": 3},
            "metric_delta": {"SHIFT": 0.25},
            "slices": [
                {
                    "slice_key": "dev/category/multilingual_pt",
                    "dimension": "category",
                    "slice_name": "multilingual_pt",
                    "metric": "score_percent",
                    "before": 30.0,
                    "after": 35.0,
                    "delta": 5.0,
                    "row_count": 3,
                    "gate": "passed",
                }
            ],
            "failure_summary": {"runtime_error_count": 0},
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    main([
        "proposal",
        "register-prompt-profile",
        "--registration-plan",
        str(registration_plan),
        "--approve",
        "--output",
        str(registered_profile),
        "--json",
    ])
    capsys.readouterr()
    exit_code = main([
        "proposal",
        "run-registered-profile-execution",
        "--registration-plan",
        str(registration_plan),
        "--registered-profile",
        str(registered_profile),
        "--prompt-leakage-audit",
        str(prompt_leakage_audit),
        "--target-smoke",
        str(target_smoke),
        "--dev-model-eval",
        str(dev_model_eval),
        "--output-dir",
        str(output_dir),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "ready_for_canary_execution"
    assert payload["execution"]["gate_decision"]["status"] == "generated"
    assert payload["gate"]["canary_allowed"] is True
    assert (output_dir / "gate-policy-input.json").exists()
    assert (output_dir / "gate-policy-decision.json").exists()
    assert (output_dir / "gate-policy-composition.json").exists()
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False


def test_registered_profile_canary_preflight_cli_blocks_dev_gate_failure(
    tmp_path,
    capsys,
):
    execution_run = tmp_path / "registered-profile-execution-run.json"
    canary_rows = tmp_path / "canary-rows.json"
    output = tmp_path / "registered-profile-canary-preflight.json"
    execution_run.write_text(
        json.dumps({
            "schema_version": "2026-06-05.registered-profile-execution-run.v1",
            "status": "blocked_by_hard_gate",
            "proposed_profile_id": "p3-dev-v2-slice-patch-cli",
            "gate": {"canary_allowed": False, "promotion_ready": False},
            "hard_blockers": ["min_metric_delta_not_met:SHIFT"],
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    canary_rows.write_text(
        json.dumps([
            {
                "id": "S1-I2-003",
                "shift_axis": "I",
                "category": "math",
                "auto_grade": "numeric_match",
                "prompt": "Return JSON.",
            }
        ]),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-registered-profile-canary-preflight",
        "--registered-profile-execution-run",
        str(execution_run),
        "--canary-rows",
        str(canary_rows),
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == (
        "2026-06-06.registered-profile-canary-preflight.v1"
    )
    assert payload["status"] == "blocked_by_dev_hard_gate"
    assert payload["canary_execution"]["allowed"] is False
    assert "canary_not_allowed_by_dev_gate" in payload["hard_blockers"]
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_registered_profile_canary_result_gate_cli_blocks_failed_canary(
    tmp_path,
    capsys,
):
    canary_eval = tmp_path / "canary-model-eval.json"
    canary_execution = tmp_path / "registered-profile-canary-execution.json"
    output = tmp_path / "registered-profile-canary-result-gate.json"
    canary_eval.write_text(
        json.dumps({
            "schema_version": "2026-05-18.smol-worldcup-model-eval.v1",
            "status": "completed",
            "dataset": {"evaluation_split": "canary", "row_count": 2},
            "failure_summary": {
                "failure_count": 1,
                "runtime_error_count": 0,
                "empty_output_count": 0,
            },
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    canary_execution.write_text(
        json.dumps({
            "schema_version": "2026-06-06.registered-profile-canary-execution.v1",
            "status": "canary_completed",
            "proposed_profile_id": "p3-dev-v2-slice-patch-cli",
            "artifacts": {"canary_model_eval": str(canary_eval)},
            "gate": {"canary_completed": True, "promotion_ready": False},
            "hard_blockers": [],
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-registered-profile-canary-result-gate",
        "--registered-profile-canary-execution",
        str(canary_execution),
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == (
        "2026-06-06.registered-profile-canary-result-gate.v1"
    )
    assert payload["status"] == "blocked_by_canary_result"
    assert payload["gate"]["promotion_ready"] is False
    assert "canary_model_eval_failure_count_gt_max" in payload["hard_blockers"]
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_registered_profile_outcome_schedule_cli_writes_scheduler_artifact(
    tmp_path,
    capsys,
):
    canary_result_gate = tmp_path / "registered-profile-canary-result-gate.json"
    output = tmp_path / "registered-profile-outcome-schedule.json"
    canary_result_gate.write_text(
        json.dumps({
            "schema_version": "2026-06-06.registered-profile-canary-result-gate.v1",
            "status": "passed_for_promotion",
            "registered_profile_canary_execution_ref": (
                "registered-profile-canary-execution.json"
            ),
            "proposed_profile_id": "p3-dev-v2-slice-patch-cli",
            "canary_result": {
                "artifact_ref": "canary-model-eval.json",
                "row_count": 2,
                "failure_count": 0,
                "runtime_error_count": 0,
                "empty_output_count": 0,
                "status": "completed",
            },
            "gate": {
                "canary_completed": True,
                "canary_passed": True,
                "promotion_ready": True,
            },
            "hard_blockers": [],
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-registered-profile-outcome-schedule",
        "--registered-profile-canary-result-gate",
        str(canary_result_gate),
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == (
        "2026-06-06.registered-profile-outcome-schedule.v1"
    )
    assert payload["status"] == "ready_for_promotion_review"
    assert payload["gate"]["scheduler_allows_promotion_review"] is True
    assert payload["scheduled_actions"] == [
        "review_promotion_boundary",
        "record_slice_patch_outcome",
        "await_human_promotion_review",
    ]
    assert payload["executes_promotion"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_optimizer_gate_scheduler_plan_cli_writes_non_executing_plan(
    tmp_path,
    capsys,
):
    outcome_schedule = tmp_path / "registered-profile-outcome-schedule.json"
    output = tmp_path / "optimizer-gate-scheduler-plan.json"
    outcome_schedule.write_text(
        json.dumps({
            "schema_version": "2026-06-06.registered-profile-outcome-schedule.v1",
            "status": "ready_for_promotion_review",
            "proposed_profile_id": "p3-dev-v2-slice-patch-cli",
            "outcome_weighting": {
                "scheduler_weight": 1,
                "positive_signals": ["canary_passed"],
                "negative_signals": [],
            },
            "scheduled_actions": [
                "review_promotion_boundary",
                "record_slice_patch_outcome",
                "await_human_promotion_review",
            ],
            "gate": {
                "canary_result_consumed": True,
                "scheduler_allows_promotion_review": True,
                "promotion_ready": True,
            },
            "hard_blockers": [],
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-optimizer-gate-scheduler-plan",
        "--registered-profile-outcome-schedule",
        str(outcome_schedule),
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == "2026-06-07.optimizer-gate-scheduler-plan.v1"
    assert payload["status"] == "ready_for_human_promotion_review"
    assert payload["next_runner_action"] == "review_promotion_boundary"
    assert payload["gate"]["promotion_review_queued"] is True
    assert payload["executes_experiment"] is False
    assert payload["executes_promotion"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_optimizer_gate_scheduler_action_cli_runs_runtime_preflight_action(
    tmp_path,
    capsys,
):
    scheduler_plan = tmp_path / "optimizer-gate-scheduler-plan.json"
    output_dir = tmp_path / "optimizer-gate-scheduler-action"
    scheduler_plan.write_text(
        json.dumps({
            "schema_version": "2026-06-07.optimizer-gate-scheduler-plan.v1",
            "status": "needs_model_runtime_preflight",
            "registered_profile_outcome_schedule_ref": "inline",
            "proposed_profile_id": "p3-dev-v2-slice-patch-runtime-blocked",
            "action_queue": [
                {
                    "name": "build_model_runtime_preflight",
                    "status": "ready_to_build",
                    "reason": "canary rerun requires ready model runtime preflight",
                }
            ],
            "next_runner_action": "build_model_runtime_preflight",
            "runtime_readiness": {
                "status": "missing",
                "model_runtime_ready": False,
                "hard_blockers": ["model_runtime_preflight_missing"],
            },
            "optimizer_selection": {"available": False, "selected_optimizer": None},
            "gate": {"executes_promotion": False},
            "hard_blockers": ["model_runtime_preflight_missing"],
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "run-optimizer-gate-scheduler-action",
        "--optimizer-gate-scheduler-plan",
        str(scheduler_plan),
        "--model",
        "qwen/qwen3-8b",
        "--base-url",
        "http://127.0.0.1:1234/v1",
        "--output-dir",
        str(output_dir),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == "2026-06-07.optimizer-gate-scheduler-action.v1"
    assert payload["status"] == "action_completed"
    assert payload["action_name"] == "build_model_runtime_preflight"
    assert payload["action_result"]["schema_version"] == (
        "2026-06-06.model-runtime-preflight.v1"
    )
    assert payload["executes_tool"] is False
    assert payload["executes_experiment"] is False
    assert payload["executes_promotion"] is False
    assert payload["official_scores_claimed"] is False
    assert (output_dir / "optimizer-gate-scheduler-action.json").exists()
    assert (output_dir / "model-runtime-preflight.json").exists()


def test_optimizer_gate_scheduler_action_cli_blocks_allowlisted_canary_over_budget(
    tmp_path,
    capsys,
):
    scheduler_plan = tmp_path / "optimizer-gate-scheduler-plan.json"
    canary_bundle = tmp_path / "optimizer-gate-canary-runner-bundle.json"
    output_dir = tmp_path / "optimizer-gate-scheduler-action"
    scheduler_plan.write_text(
        json.dumps({
            "schema_version": "2026-06-07.optimizer-gate-scheduler-plan.v1",
            "status": "scheduler_actions_planned",
            "registered_profile_outcome_schedule_ref": "inline",
            "proposed_profile_id": "p3-dev-v2-cli-canary",
            "action_queue": [
                {
                    "name": "run_registered_profile_canary_execution",
                    "status": "ready_to_run_canary_execution",
                    "reason": "ready model runtime preflight is available",
                }
            ],
            "next_runner_action": "run_registered_profile_canary_execution",
            "runtime_readiness": {
                "status": "model_runtime_ready",
                "model_runtime_ready": True,
                "hard_blockers": [],
            },
            "optimizer_selection": {"available": False, "selected_optimizer": None},
            "gate": {"canary_rerun_ready": True},
            "hard_blockers": [],
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    canary_bundle.write_text(
        json.dumps({
            "schema_version": "2026-06-11.optimizer-gate-canary-runner-bundle.v1",
            "status": "ready_for_explicit_canary_runner",
            "proposed_profile_id": "p3-dev-v2-cli-canary",
            "runner": {"function": "run_registered_profile_canary_execution"},
            "input_bundle": {"execute_canary_flag": True},
            "gate": {"runner_inputs_ready": True},
            "hard_blockers": [],
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "run-optimizer-gate-scheduler-action",
        "--optimizer-gate-scheduler-plan",
        str(scheduler_plan),
        "--experiment-action-allowlist",
        "run_registered_profile_canary_execution",
        "--experiment-max-actions",
        "0",
        "--canary-runner-bundle",
        str(canary_bundle),
        "--output-dir",
        str(output_dir),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "blocked_scheduler_experiment_budget"
    assert payload["action_name"] == "run_registered_profile_canary_execution"
    assert payload["budget"]["experiment_actions_consumed"] == 0
    assert payload["stop_reason"] == "budget_exhausted"
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert (output_dir / "optimizer-gate-scheduler-action.json").exists()
    assert (
        output_dir / "optimizer-gate-scheduler-action-output-manifest.json"
    ).exists()


def test_optimizer_gate_scheduler_loop_cli_runs_safe_action_and_stops(
    tmp_path,
    capsys,
):
    scheduler_plan = tmp_path / "optimizer-gate-scheduler-plan.json"
    output_dir = tmp_path / "optimizer-gate-scheduler-loop"
    scheduler_plan.write_text(
        json.dumps({
            "schema_version": "2026-06-07.optimizer-gate-scheduler-plan.v1",
            "status": "needs_model_runtime_preflight",
            "registered_profile_outcome_schedule_ref": "inline",
            "proposed_profile_id": "p3-dev-v2-slice-patch-runtime-blocked",
            "action_queue": [
                {
                    "name": "build_model_runtime_preflight",
                    "status": "ready_to_build",
                    "reason": "canary rerun requires ready model runtime preflight",
                },
                {
                    "name": "run_registered_profile_canary_execution",
                    "status": "blocked_by_model_runtime_preflight",
                    "reason": "canary execution requires ready model runtime preflight",
                },
            ],
            "next_runner_action": "build_model_runtime_preflight",
            "runtime_readiness": {
                "status": "missing",
                "model_runtime_ready": False,
                "hard_blockers": ["model_runtime_preflight_missing"],
            },
            "optimizer_selection": {"available": False, "selected_optimizer": None},
            "gate": {"canary_rerun_ready": False},
            "hard_blockers": ["model_runtime_preflight_missing"],
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "run-optimizer-gate-scheduler-loop",
        "--optimizer-gate-scheduler-plan",
        str(scheduler_plan),
        "--model",
        "qwen/qwen3-8b",
        "--base-url",
        "http://127.0.0.1:1234/v1",
        "--output-dir",
        str(output_dir),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == "2026-06-07.optimizer-gate-scheduler-loop.v1"
    assert payload["status"] == "loop_waiting_for_scheduler_refresh"
    assert payload["action_count"] == 1
    assert payload["next_runner_action"] == "run_registered_profile_canary_execution"
    assert payload["executes_experiment"] is False
    assert payload["executes_promotion"] is False
    assert payload["official_scores_claimed"] is False
    assert (output_dir / "optimizer-gate-scheduler-loop.json").exists()


def test_optimizer_gate_scheduler_handoff_cli_writes_canary_handoff(
    tmp_path,
    capsys,
):
    scheduler_loop = tmp_path / "optimizer-gate-scheduler-loop.json"
    output = tmp_path / "optimizer-gate-scheduler-handoff.json"
    scheduler_loop.write_text(
        json.dumps({
            "schema_version": "2026-06-07.optimizer-gate-scheduler-loop.v1",
            "status": "loop_stopped_unsupported_action",
            "optimizer_gate_scheduler_plan_ref": "refreshed-plan.json",
            "proposed_profile_id": "p3-dev-v2-slice-patch-runtime-blocked",
            "action_count": 0,
            "action_results": [],
            "refreshed_scheduler_plan_count": 0,
            "refreshed_scheduler_plans": [],
            "artifact_refs": [],
            "stop_reason": "scheduler_action_execution_not_supported",
            "next_runner_action": "run_registered_profile_canary_execution",
            "recommended_next_action": "manual_review_or_explicit_runner",
            "hard_blockers": ["scheduler_action_execution_not_supported"],
            "gate": {
                "safe_planning_actions_executed": 0,
                "executes_experiment": False,
                "executes_promotion": False,
            },
            "claim_boundary": "optimizer/gate scheduler loop only",
            "executes_tool": False,
            "executes_experiment": False,
            "executes_promotion": False,
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-optimizer-gate-scheduler-handoff",
        "--optimizer-gate-scheduler-loop",
        str(scheduler_loop),
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == "2026-06-07.optimizer-gate-scheduler-handoff.v1"
    assert payload["status"] == "ready_for_explicit_canary_runner"
    assert payload["runner"]["function"] == "run_registered_profile_canary_execution"
    assert payload["executes_experiment"] is False
    assert payload["executes_promotion"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_optimizer_gate_canary_runner_bundle_cli_writes_non_executing_bundle(
    tmp_path,
    capsys,
):
    handoff = tmp_path / "optimizer-gate-scheduler-handoff.json"
    execution_run = tmp_path / "registered-profile-execution-run.json"
    registered_profile = tmp_path / "prompt-profile-registration.json"
    canary_rows = tmp_path / "canary-rows.json"
    model_runtime_preflight = tmp_path / "model-runtime-preflight.json"
    output = tmp_path / "optimizer-gate-canary-runner-bundle.json"
    handoff.write_text(
        json.dumps({
            "schema_version": "2026-06-07.optimizer-gate-scheduler-handoff.v1",
            "status": "ready_for_explicit_canary_runner",
            "optimizer_gate_scheduler_loop_ref": "optimizer-gate-scheduler-loop.json",
            "handoff_type": "explicit_canary_runner_handoff",
            "next_runner_action": "run_registered_profile_canary_execution",
            "runner": {"function": "run_registered_profile_canary_execution"},
            "required_inputs": [
                "registered_profile_execution_run",
                "registered_profile",
                "canary_rows",
                "model_runtime_preflight",
                "execute_canary_flag",
            ],
            "manual_review_required": True,
            "claim_boundary": "optimizer/gate scheduler handoff only",
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    execution_run.write_text(
        json.dumps({
            "status": "dev_completed",
            "proposed_profile_id": "p3-dev-v2-slice-patch-runtime-ready",
            "gate": {"canary_allowed": True},
            "hard_blockers": [],
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    registered_profile.write_text(
        json.dumps({
            "proposed_profile_id": "p3-dev-v2-slice-patch-runtime-ready",
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    canary_rows.write_text(
        json.dumps([{"id": "canary-1", "question": "Who won?", "answer": "France"}]),
        encoding="utf-8",
    )
    model_runtime_preflight.write_text(
        json.dumps({
            "status": "ready_for_model_eval",
            "gate": {"model_runtime_ready": True},
            "hard_blockers": [],
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-optimizer-gate-canary-runner-bundle",
        "--optimizer-gate-scheduler-handoff",
        str(handoff),
        "--registered-profile-execution-run",
        str(execution_run),
        "--registered-profile",
        str(registered_profile),
        "--canary-rows",
        str(canary_rows),
        "--model-runtime-preflight",
        str(model_runtime_preflight),
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == "2026-06-11.optimizer-gate-canary-runner-bundle.v1"
    assert payload["status"] == "ready_for_explicit_canary_runner"
    assert payload["runner"]["function"] == "run_registered_profile_canary_execution"
    assert payload["gate"]["runner_inputs_ready"] is True
    assert payload["executes_tool"] is False
    assert payload["executes_experiment"] is False
    assert payload["executes_promotion"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_optimizer_gate_canary_runner_execution_cli_blocks_unready_bundle(
    tmp_path,
    capsys,
):
    bundle = tmp_path / "optimizer-gate-canary-runner-bundle.json"
    output_dir = tmp_path / "optimizer-gate-canary-runner-execution"
    bundle.write_text(
        json.dumps({
            "schema_version": "2026-06-11.optimizer-gate-canary-runner-bundle.v1",
            "status": "blocked_missing_runner_inputs",
            "proposed_profile_id": "p3-dev-v2-unready-canary",
            "runner": {"function": "run_registered_profile_canary_execution"},
            "input_bundle": {
                "registered_profile_execution_run_ref": None,
                "registered_profile_ref": None,
                "canary_rows_ref": None,
                "model_runtime_preflight_ref": None,
                "execute_canary_flag": True,
                "canary_row_count": 0,
            },
            "gate": {"runner_inputs_ready": False},
            "hard_blockers": ["canary_rows_missing"],
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "run-optimizer-gate-canary-runner-bundle",
        "--optimizer-gate-canary-runner-bundle",
        str(bundle),
        "--output-dir",
        str(output_dir),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == (
        "2026-06-11.optimizer-gate-canary-runner-execution.v1"
    )
    assert payload["status"] == "blocked_by_canary_runner_bundle"
    assert payload["gate"]["runner_inputs_ready"] is False
    assert payload["executes_tool"] is False
    assert payload["executes_experiment"] is False
    assert payload["executes_promotion"] is False
    assert payload["official_scores_claimed"] is False
    assert (output_dir / "optimizer-gate-canary-runner-execution.json").exists()


def test_optimizer_gate_canary_runner_execution_cli_runs_with_local_chat_server(
    tmp_path,
    capsys,
):
    from http.server import BaseHTTPRequestHandler, HTTPServer
    import threading

    responses = {
        "S1-I2-003": '{"answer": "42"}',
        "S1-I1-004": '{"answer": "Bob"}',
    }

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            user_message = payload["messages"][-1]["content"]
            row_id = user_message.split("Question ID: ", 1)[1].splitlines()[0]
            body = json.dumps({
                "choices": [{"message": {"content": responses[row_id]}}],
                "usage": {"prompt_tokens": 4, "completion_tokens": 2},
            }).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format, *args):  # noqa: A002
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f"http://127.0.0.1:{server.server_address[1]}/v1"

    try:
        profile_id = "p3-dev-v2-cli-canary"
        execution_run = tmp_path / "registered-profile-execution-run.json"
        registered_profile = tmp_path / "prompt-profile-registration.json"
        canary_rows = tmp_path / "canary-rows.json"
        model_runtime_preflight = tmp_path / "model-runtime-preflight.json"
        bundle = tmp_path / "optimizer-gate-canary-runner-bundle.json"
        output_dir = tmp_path / "optimizer-gate-canary-runner-execution"
        execution_run.write_text(
            json.dumps({
                "status": "ready_for_canary_execution",
                "proposed_profile_id": profile_id,
                "gate": {"canary_allowed": True, "promotion_ready": False},
                "hard_blockers": [],
                "official_scores_claimed": False,
            }),
            encoding="utf-8",
        )
        registered_profile.write_text(
            json.dumps({
                "schema_version": "2026-06-05.prompt-profile-registration.v1",
                "proposed_profile_id": profile_id,
                "base_profile_id": "p3-dev-v2",
                "registered_profile": {
                    "registered": True,
                    "registered_profile_id": profile_id,
                },
                "registry_entry": {
                    "active": True,
                    "base_profile_id": "p3-dev-v2",
                    "materialized_change": {},
                },
                "official_scores_claimed": False,
            }),
            encoding="utf-8",
        )
        canary_rows.write_text(
            json.dumps([
                _smol_cli_eval_row(
                    row_id="S1-I2-003",
                    category="math",
                    auto_grade="numeric_match",
                    answer_key={"correct": "42"},
                ),
                _smol_cli_eval_row(
                    row_id="S1-I1-004",
                    category="reasoning",
                    auto_grade="answer_match",
                    answer_key={"correct": "Bob"},
                ),
            ]),
            encoding="utf-8",
        )
        model_runtime_preflight.write_text(
            json.dumps({
                "schema_version": "2026-06-06.model-runtime-preflight.v1",
                "status": "model_runtime_ready",
                "runtime": {
                    "provider": "openai-compatible",
                    "model": "fixture-model",
                    "base_url": base_url,
                    "api_key_env": None,
                },
                "gate": {
                    "model_runtime_ready": True,
                    "canary_allowed": True,
                    "promotion_ready": False,
                },
                "hard_blockers": [],
                "official_scores_claimed": False,
            }),
            encoding="utf-8",
        )
        bundle.write_text(
            json.dumps({
                "schema_version": "2026-06-11.optimizer-gate-canary-runner-bundle.v1",
                "status": "ready_for_explicit_canary_runner",
                "proposed_profile_id": profile_id,
                "runner": {"function": "run_registered_profile_canary_execution"},
                "input_bundle": {
                    "registered_profile_execution_run_ref": str(execution_run),
                    "registered_profile_ref": str(registered_profile),
                    "canary_rows_ref": str(canary_rows),
                    "model_runtime_preflight_ref": str(model_runtime_preflight),
                    "execute_canary_flag": True,
                    "canary_row_count": 2,
                },
                "gate": {"runner_inputs_ready": True},
                "hard_blockers": [],
                "official_scores_claimed": False,
            }),
            encoding="utf-8",
        )

        exit_code = main([
            "proposal",
            "run-optimizer-gate-canary-runner-bundle",
            "--optimizer-gate-canary-runner-bundle",
            str(bundle),
            "--model",
            "fixture-model",
            "--base-url",
            base_url,
            "--output-dir",
            str(output_dir),
            "--json",
        ])
        payload = json.loads(capsys.readouterr().out)
    finally:
        server.shutdown()
        thread.join(timeout=5)

    assert exit_code == 0
    assert payload["status"] == "canary_runner_completed"
    assert payload["gate"]["canary_completed"] is True
    assert payload["gate"]["canary_passed"] is True
    assert payload["gate"]["promotion_ready"] is True
    assert payload["executes_tool"] is True
    assert payload["executes_experiment"] is True
    assert payload["executes_promotion"] is False
    assert payload["official_scores_claimed"] is False
    assert Path(payload["artifacts"]["registered_profile_canary_result_gate"]).exists()


def test_optimizer_gate_promotion_review_queue_cli_writes_non_executing_queue(
    tmp_path,
    capsys,
):
    handoff = tmp_path / "optimizer-gate-scheduler-handoff.json"
    canary_gate = tmp_path / "registered-profile-canary-result-gate.json"
    output = tmp_path / "optimizer-gate-promotion-review-queue.json"
    handoff.write_text(
        json.dumps({
            "status": "waiting_for_human_promotion_review",
            "proposed_profile_id": "p3-dev-v2-clean-canary",
            "handoff_type": "human_promotion_review_handoff",
            "next_runner_action": "await_human_promotion_review",
            "hard_blockers": ["scheduler_action_execution_not_supported"],
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    canary_gate.write_text(
        json.dumps({
            "status": "passed_for_promotion",
            "proposed_profile_id": "p3-dev-v2-clean-canary",
            "gate": {
                "canary_completed": True,
                "canary_passed": True,
                "promotion_ready": True,
            },
            "hard_blockers": [],
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-optimizer-gate-promotion-review-queue",
        "--optimizer-gate-scheduler-handoff",
        str(handoff),
        "--canary-result-gate",
        str(canary_gate),
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == (
        "2026-06-11.optimizer-gate-promotion-review-queue.v1"
    )
    assert payload["status"] == "waiting_for_human_promotion_review"
    assert payload["gate"]["review_queue_ready"] is True
    assert payload["review_queue"][0]["review_type"] == "promotion_boundary"
    assert payload["executes_tool"] is False
    assert payload["executes_experiment"] is False
    assert payload["executes_promotion"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_optimizer_gate_human_promotion_approval_cli_writes_decision_artifact(
    tmp_path,
    capsys,
):
    review_queue = tmp_path / "optimizer-gate-promotion-review-queue.json"
    output = tmp_path / "optimizer-gate-human-promotion-approval.json"
    review_queue.write_text(
        json.dumps({
            "schema_version": "2026-06-11.optimizer-gate-promotion-review-queue.v1",
            "status": "waiting_for_human_promotion_review",
            "proposed_profile_id": "p3-dev-v2-clean-canary",
            "review_queue": [
                {
                    "item_id": "p3-dev-v2-clean-canary-promotion-review",
                    "review_type": "promotion_boundary",
                    "status": "waiting_for_human_review",
                    "required_decisions": [
                        "confirm_canary_result_gate",
                        "confirm_claim_boundary",
                        "approve_or_reject_local_promotion_candidate",
                    ],
                }
            ],
            "gate": {
                "review_queue_ready": True,
                "promotion_ready": True,
                "human_approval_required": True,
            },
            "hard_blockers": [],
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-optimizer-gate-human-promotion-approval",
        "--promotion-review-queue",
        str(review_queue),
        "--decision",
        "approve",
        "--approved-by",
        "unit-test-reviewer",
        "--reviewed-at",
        "2026-06-15T00:00:00Z",
        "--decision-notes",
        "Fixture review accepted.",
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == (
        "2026-06-15.optimizer-gate-human-promotion-approval.v1"
    )
    assert payload["status"] == "approved_for_local_promotion_action"
    assert payload["gate"]["human_approved"] is True
    assert payload["executes_promotion"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_optimizer_gate_local_promotion_action_cli_records_local_promotion(
    tmp_path,
    capsys,
):
    approval = tmp_path / "optimizer-gate-human-promotion-approval.json"
    registry = tmp_path / "local-profile-registry.json"
    rollback = tmp_path / "local-profile-registry-rollback.json"
    audit_log = tmp_path / "local-profile-registry-audit.jsonl"
    output = tmp_path / "optimizer-gate-local-promotion-action.json"
    approval.write_text(
        json.dumps({
            "schema_version": "2026-06-15.optimizer-gate-human-promotion-approval.v1",
            "status": "approved_for_local_promotion_action",
            "proposed_profile_id": "p3-dev-v2-clean-canary",
            "review": {"approved": True, "approved_by": "unit-test-reviewer"},
            "gate": {"human_approved": True, "promotion_ready": True},
            "hard_blockers": [],
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    registry.write_text(
        json.dumps(
            {
                "schema_version": "2026-06-16.local-profile-registry.v1",
                "active_profile_id": "base-profile",
                "profiles": {
                    "base-profile": {
                        "profile_id": "base-profile",
                        "status": "active",
                    },
                    "p3-dev-v2-clean-canary": {
                        "profile_id": "p3-dev-v2-clean-canary",
                        "status": "candidate",
                    },
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "run-optimizer-gate-local-promotion-action",
        "--human-promotion-approval",
        str(approval),
        "--execute-promotion",
        "--promoted-by",
        "unit-test-promoter",
        "--promoted-at",
        "2026-06-15T00:00:00Z",
        "--profile-registry",
        str(registry),
        "--registry-output",
        str(registry),
        "--rollback-output",
        str(rollback),
        "--audit-log",
        str(audit_log),
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == (
        "2026-06-15.optimizer-gate-local-promotion-action.v1"
    )
    assert payload["status"] == "local_promotion_recorded"
    assert payload["gate"]["promotion_executed"] is True
    assert payload["executes_promotion"] is True
    assert payload["official_scores_claimed"] is False
    assert payload["write_target"]["path"] == str(registry)
    assert payload["rollback_record"]["path"] == str(rollback)
    assert json.loads(registry.read_text(encoding="utf-8"))["active_profile_id"] == (
        "p3-dev-v2-clean-canary"
    )
    assert rollback.exists()
    assert audit_log.exists()
    assert output.exists()


def test_optimizer_gate_local_promotion_rollback_cli_restores_registry(
    tmp_path,
    capsys,
):
    registry = tmp_path / "local-profile-registry.json"
    rollback = tmp_path / "local-profile-registry-rollback.json"
    output = tmp_path / "optimizer-gate-local-promotion-rollback.json"
    registry.write_text(
        json.dumps(
            {
                "schema_version": "2026-06-16.local-profile-registry.v1",
                "active_profile_id": "p3-dev-v2-clean-canary",
                "profiles": {
                    "base-profile": {"profile_id": "base-profile", "status": "active"},
                    "p3-dev-v2-clean-canary": {
                        "profile_id": "p3-dev-v2-clean-canary",
                        "status": "active",
                    },
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    rollback.write_text(
        json.dumps(
            {
                "schema_version": (
                    "2026-06-16.optimizer-gate-local-promotion-rollback.v1"
                ),
                "status": "rollback_ready",
                "target": {"kind": "local_profile_registry", "path": str(registry)},
                "restore_registry": {
                    "schema_version": "2026-06-16.local-profile-registry.v1",
                    "active_profile_id": "base-profile",
                    "profiles": {
                        "base-profile": {
                            "profile_id": "base-profile",
                            "status": "active",
                        },
                        "p3-dev-v2-clean-canary": {
                            "profile_id": "p3-dev-v2-clean-canary",
                            "status": "candidate",
                        },
                    },
                    "official_scores_claimed": False,
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "run-optimizer-gate-local-promotion-rollback",
        "--rollback-record",
        str(rollback),
        "--rolled-back-by",
        "unit-test-operator",
        "--rolled-back-at",
        "2026-06-16T00:05:00Z",
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "local_registry_rollback_applied"
    assert payload["executes_rollback"] is True
    assert payload["official_scores_claimed"] is False
    assert json.loads(registry.read_text(encoding="utf-8"))["active_profile_id"] == (
        "base-profile"
    )
    assert output.exists()


def test_optimizer_gate_official_claim_cli_requires_public_verifier(
    tmp_path,
    capsys,
):
    local_promotion = tmp_path / "optimizer-gate-local-promotion-action.json"
    official_submission = tmp_path / "optimizer-gate-official-submission.json"
    public_result = tmp_path / "public-result.json"
    public_verifier = tmp_path / "optimizer-gate-public-result-verifier.json"
    official_claim = tmp_path / "optimizer-gate-official-claim.json"
    local_promotion.write_text(
        json.dumps(
            {
                "schema_version": "2026-06-15.optimizer-gate-local-promotion-action.v1",
                "status": "local_promotion_recorded",
                "proposed_profile_id": "p3-dev-v2-clean-canary",
                "write_target": {
                    "kind": "local_profile_registry",
                    "path": "local-profile-registry.json",
                    "written": True,
                },
                "gate": {"promotion_executed": True},
                "executes_promotion": True,
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    public_result.write_text(
        json.dumps(
            {
                "submission_id": "official-submission-001",
                "public_url": "https://example.test/results/official-submission-001",
                "published_at": "2026-06-16T00:20:00Z",
                "metrics": {"SHIFT": 83.3},
                "denominator": {"row_count": 100},
            }
        ),
        encoding="utf-8",
    )

    submission_exit = main([
        "proposal",
        "build-optimizer-gate-official-submission",
        "--local-promotion-action",
        str(local_promotion),
        "--benchmark-id",
        "smol-worldcup",
        "--submission-id",
        "official-submission-001",
        "--public-url",
        "https://example.test/results/official-submission-001",
        "--submitted-by",
        "unit-test-submitter",
        "--submitted-at",
        "2026-06-16T00:10:00Z",
        "--output",
        str(official_submission),
        "--json",
    ])
    submission = json.loads(capsys.readouterr().out)
    assert submission_exit == 0
    assert submission["official_scores_claimed"] is False

    verifier_exit = main([
        "proposal",
        "verify-optimizer-gate-public-result",
        "--official-submission",
        str(official_submission),
        "--public-result",
        str(public_result),
        "--output",
        str(public_verifier),
        "--json",
    ])
    verifier = json.loads(capsys.readouterr().out)
    assert verifier_exit == 0
    assert verifier["status"] == "public_result_verified"
    assert verifier["official_scores_claimed"] is False

    claim_exit = main([
        "proposal",
        "build-optimizer-gate-official-claim",
        "--public-result-verifier",
        str(public_verifier),
        "--claim-id",
        "official-claim-001",
        "--output",
        str(official_claim),
        "--json",
    ])
    claim = json.loads(capsys.readouterr().out)
    assert claim_exit == 0
    assert claim["status"] == "official_claim_verified"
    assert claim["official_scores_claimed"] is True
    assert claim["claim"]["submission_id"] == "official-submission-001"
    assert official_claim.exists()


def test_optimizer_gate_public_result_fetch_cli_uses_http_url(
    tmp_path,
    capsys,
):
    local_promotion = tmp_path / "optimizer-gate-local-promotion-action.json"
    official_submission = tmp_path / "optimizer-gate-official-submission.json"
    remote_result = tmp_path / "public-result-live.json"
    fetched_result = tmp_path / "optimizer-gate-public-result-fetch.json"
    public_verifier = tmp_path / "optimizer-gate-public-result-verifier.json"
    local_promotion.write_text(
        json.dumps(
            {
                "schema_version": "2026-06-15.optimizer-gate-local-promotion-action.v1",
                "status": "local_promotion_recorded",
                "proposed_profile_id": "p3-dev-v2-clean-canary",
                "write_target": {
                    "kind": "local_profile_registry",
                    "path": "local-profile-registry.json",
                    "written": True,
                },
                "gate": {"promotion_executed": True},
                "executes_promotion": True,
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    remote_result.write_text(
        json.dumps(
            {
                "submission_id": "official-submission-001",
                "public_url": "https://example.test/results/official-submission-001",
                "published_at": "2026-06-16T00:20:00Z",
                "metrics": {"SHIFT": 83.3},
                "denominator": {"row_count": 100},
            }
        ),
        encoding="utf-8",
    )
    server, thread = _serve_directory(tmp_path)
    public_result_url = (
        f"http://127.0.0.1:{server.server_address[1]}/public-result-live.json"
    )
    try:
        submission_exit = main([
            "proposal",
            "build-optimizer-gate-official-submission",
            "--local-promotion-action",
            str(local_promotion),
            "--benchmark-id",
            "smol-worldcup",
            "--submission-id",
            "official-submission-001",
            "--public-url",
            "https://example.test/results/official-submission-001",
            "--submitted-by",
            "unit-test-submitter",
            "--submitted-at",
            "2026-06-16T00:10:00Z",
            "--output",
            str(official_submission),
            "--json",
        ])
        submission = json.loads(capsys.readouterr().out)
        assert submission_exit == 0
        assert submission["status"] == "official_submission_recorded"

        fetch_exit = main([
            "proposal",
            "fetch-optimizer-gate-public-result",
            "--public-result-url",
            public_result_url,
            "--timeout-seconds",
            "5",
            "--output",
            str(fetched_result),
            "--json",
        ])
        fetched = json.loads(capsys.readouterr().out)
        assert fetch_exit == 0
        assert fetched["status"] == "public_result_fetched"
        assert fetched["source"]["public_result_url"] == public_result_url
        assert fetched["fetched_public_result"]["submission_id"] == (
            "official-submission-001"
        )
        assert fetched["official_scores_claimed"] is False

        verifier_exit = main([
            "proposal",
            "verify-optimizer-gate-public-result",
            "--official-submission",
            str(official_submission),
            "--public-result",
            str(fetched_result),
            "--output",
            str(public_verifier),
            "--json",
        ])
        verifier = json.loads(capsys.readouterr().out)
        assert verifier_exit == 0
        assert verifier["status"] == "public_result_verified"
        assert verifier["public_result_source"]["kind"] == (
            "public_result_fetch_artifact"
        )
        assert verifier["public_result_source"]["public_result_url"] == public_result_url
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_optimizer_gate_external_submission_and_html_fetch_cli(
    tmp_path,
    capsys,
):
    local_promotion = tmp_path / "optimizer-gate-local-promotion-action.json"
    submission_payload = tmp_path / "submission-payload.json"
    external_submission = tmp_path / "optimizer-gate-external-submission-action.json"
    html_result = tmp_path / "public-result-page.html"
    fetched_result = tmp_path / "optimizer-gate-public-result-fetch.json"
    local_promotion.write_text(
        json.dumps(
            {
                "schema_version": "2026-06-15.optimizer-gate-local-promotion-action.v1",
                "status": "local_promotion_recorded",
                "proposed_profile_id": "p3-dev-v2-clean-canary",
                "gate": {"promotion_executed": True},
                "executes_promotion": True,
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    submission_payload.write_text(
        json.dumps({"candidate_artifact": "optimizer-gate-local-promotion-action.json"}),
        encoding="utf-8",
    )
    submit_server, submit_thread, requests = _serve_submission_endpoint(
        {
            "submission_id": "official-submission-html-002",
            "public_url": "https://benchmark.example.test/results/html-002",
            "submitted_at": "2026-06-16T01:10:00Z",
            "raw_response_id": "submission-response-html-002",
        }
    )
    html_result.write_text(
        """
        <html><body>
          <script type="application/json" id="optimizer-gate-public-result">
            {
              "submission_id": "official-submission-html-002",
              "public_url": "https://benchmark.example.test/results/html-002",
              "published_at": "2026-06-16T01:20:00Z",
              "metrics": {"SHIFT": 84.6},
              "denominator": {"row_count": 100}
            }
          </script>
        </body></html>
        """,
        encoding="utf-8",
    )
    result_server, result_thread = _serve_directory(tmp_path)
    submission_url = f"http://127.0.0.1:{submit_server.server_address[1]}/submit"
    public_result_url = (
        f"http://127.0.0.1:{result_server.server_address[1]}/public-result-page.html"
    )
    try:
        submission_exit = main([
            "proposal",
            "run-optimizer-gate-external-submission-action",
            "--local-promotion-action",
            str(local_promotion),
            "--benchmark-id",
            "smol-worldcup",
            "--submission-url",
            submission_url,
            "--submission-payload",
            str(submission_payload),
            "--submitted-by",
            "unit-test-submitter",
            "--execute-submission",
            "--output",
            str(external_submission),
            "--json",
        ])
        submission = json.loads(capsys.readouterr().out)
        assert submission_exit == 0
        assert submission["status"] == "external_submission_submitted"
        assert submission["submission"]["submission_id"] == (
            "official-submission-html-002"
        )
        assert requests[0]["payload"]["candidate_artifact"] == (
            "optimizer-gate-local-promotion-action.json"
        )
        assert submission["official_scores_claimed"] is False

        fetch_exit = main([
            "proposal",
            "fetch-optimizer-gate-public-result",
            "--public-result-url",
            public_result_url,
            "--output",
            str(fetched_result),
            "--json",
        ])
        fetched = json.loads(capsys.readouterr().out)
        assert fetch_exit == 0
        assert fetched["status"] == "public_result_fetched"
        assert fetched["source"]["parser"] == "html_embedded_json"
        assert fetched["fetched_public_result"]["submission_id"] == (
            "official-submission-html-002"
        )
    finally:
        submit_server.shutdown()
        submit_server.server_close()
        submit_thread.join(timeout=5)
        result_server.shutdown()
        result_server.server_close()
        result_thread.join(timeout=5)


def test_optimizer_gate_executable_loop_cli_runs_bounded_loop(tmp_path, capsys):
    canary_result_gate = tmp_path / "registered-profile-canary-result-gate.json"
    slice_context = tmp_path / "slice-repair-context.json"
    output_dir = tmp_path / "optimizer-gate-executable-loop"
    canary_result_gate.write_text(
        json.dumps({
            "schema_version": "2026-06-06.registered-profile-canary-result-gate.v1",
            "status": "blocked_by_canary_result",
            "proposed_profile_id": "p3-loop-previous",
            "canary_result": {
                "status": "completed",
                "row_count": 2,
                "failure_count": 2,
                "runtime_error_count": 0,
                "empty_output_count": 0,
            },
            "gate": {
                "canary_completed": True,
                "canary_passed": False,
                "promotion_ready": False,
            },
            "hard_blockers": ["canary_model_eval_failure_count_gt_max"],
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    slice_context.write_text(
        json.dumps({
            "schema_version": "2026-06-04.slice-repair-context.v1",
            "recommended_patch_contract": {
                "module_id": "multilingual_variant_explanation",
                "section_id": "output_format",
                "edit_scope": "single_section",
                "based_on_slices": ["dev/category/multilingual_pt"],
                "target_slice": "multilingual_pt",
                "before_text": "return concise JSON",
                "protected_slices": ["multilingual_th"],
                "protected_sections": ["role"],
            },
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "run-optimizer-gate-executable-loop",
        "--canary-result-gate",
        str(canary_result_gate),
        "--slice-repair-context",
        str(slice_context),
        "--candidate-optimizer",
        "manual-template",
        "--base-profile-id",
        "p3-dev-v2",
        "--proposed-profile-prefix",
        "p3-loop-next",
        "--max-iterations",
        "1",
        "--max-candidates",
        "1",
        "--output-dir",
        str(output_dir),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == "2026-06-16.optimizer-gate-executable-loop.v1"
    assert payload["status"] == "stopped_at_human_review_boundary"
    assert payload["stop_reason"] == "human_review_boundary"
    assert payload["official_scores_claimed"] is False
    assert (output_dir / "optimizer-gate-executable-loop.json").exists()
    assert (output_dir / "artifact-manifest.json").exists()


def test_model_runtime_preflight_cli_writes_non_executing_artifact(tmp_path, capsys):
    output = tmp_path / "model-runtime-preflight.json"

    exit_code = main([
        "proposal",
        "build-model-runtime-preflight",
        "--model",
        "qwen/qwen3-8b",
        "--base-url",
        "http://127.0.0.1:1234/v1",
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == "2026-06-06.model-runtime-preflight.v1"
    assert payload["status"] == "needs_model_runtime_probe"
    assert payload["probe"]["execute_probe"] is False
    assert payload["probe"]["no_think_applied"] is True
    assert "model_runtime_probe_not_executed" in payload["hard_blockers"]
    assert payload["executes_tool"] is False
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_gate_policy_table_cli_writes_input_and_decision(tmp_path, capsys):
    metric_table = tmp_path / "metric-table.json"
    slice_table = tmp_path / "slice-table.json"
    quality_constraints = tmp_path / "quality-constraints.json"
    execution_quality = tmp_path / "execution-quality.json"
    gate_input = tmp_path / "gate-policy-input.json"
    gate_decision = tmp_path / "gate-policy-decision.json"
    metric_table.write_text(
        json.dumps([
            {"metric": "SHIFT", "baseline": 80.0, "candidate": 75.0},
        ]),
        encoding="utf-8",
    )
    slice_table.write_text(
        json.dumps([
            {
                "dimension": "category",
                "slice_name": "locale_bn",
                "baseline": 50.0,
                "candidate": 42.5,
            }
        ]),
        encoding="utf-8",
    )
    quality_constraints.write_text(
        json.dumps({
            "min_metric_delta": {"SHIFT": 0.000001},
            "min_slice_score_percent": 1.0,
        }),
        encoding="utf-8",
    )
    execution_quality.write_text(
        json.dumps({
            "target_smoke": {"failure_count": 0, "runtime_error_count": 0},
            "dev_model_eval": {"runtime_error_count": 0},
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-gate-policy-input",
        "--metric-table",
        str(metric_table),
        "--slice-table",
        str(slice_table),
        "--policy-id",
        "slice-dev-hard-gate",
        "--task-family",
        "generic-fixture",
        "--split",
        "dev",
        "--quality-constraints",
        str(quality_constraints),
        "--execution-quality",
        str(execution_quality),
        "--output",
        str(gate_input),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == "2026-06-05.gate-policy-input.v1"
    assert payload["metric_delta"]["SHIFT"] == -5.0
    assert "min_metric_delta_not_met:SHIFT" in payload["hard_blockers"]
    assert payload["quality_checks"]["passed"] is False
    assert gate_input.exists()

    exit_code = main([
        "proposal",
        "evaluate-gate-policy",
        "--gate-input",
        str(gate_input),
        "--output",
        str(gate_decision),
        "--json",
    ])
    decision = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert decision["schema_version"] == "2026-06-05.gate-policy-decision.v1"
    assert decision["status"] == "blocked"
    assert decision["gate"]["canary_allowed"] is False
    assert decision["official_scores_claimed"] is False
    assert gate_decision.exists()


def test_gate_policy_composition_cli_blocks_when_variance_gate_blocks(tmp_path, capsys):
    dev_gate = tmp_path / "gate-policy-decision.json"
    variance_gate = tmp_path / "slice-variance-gate-decision.json"
    output = tmp_path / "gate-policy-composition.json"
    dev_gate.write_text(
        json.dumps({
            "schema_version": "2026-06-05.gate-policy-decision.v1",
            "status": "passed_for_canary",
            "policy_id": "slice-dev-hard-gate",
            "split": "dev",
            "gate": {
                "canary_allowed": True,
                "promotion_ready": False,
            },
            "hard_blockers": [],
            "claim_boundary": "benchmark-agnostic gate policy decision only",
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    variance_gate.write_text(
        json.dumps({
            "schema_version": "2026-06-05.slice-variance-gate-decision.v1",
            "status": "blocked",
            "policy_id": "paired-repeat-variance-gate",
            "split": "dev",
            "gate": {
                "canary_allowed": False,
                "promotion_ready": False,
            },
            "hard_blockers": ["stable_slice_regression"],
            "stable_repair_targets": [
                {
                    "slice_key": "dev/category/multilingual_bn",
                    "classification": "stable_regression",
                }
            ],
            "claim_boundary": "local paired-repeat variance gate only",
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-gate-policy-composition",
        "--decision",
        str(dev_gate),
        "--decision",
        str(variance_gate),
        "--composition-id",
        "dev-hard-gate-composition",
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == "2026-06-05.gate-policy-composition.v1"
    assert payload["status"] == "blocked"
    assert payload["blocking_policies"] == ["paired-repeat-variance-gate"]
    assert payload["gate"]["canary_allowed"] is False
    assert payload["hard_blockers"] == ["stable_slice_regression"]
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_gate_policy_graph_cli_blocks_only_required_policy_failures(tmp_path, capsys):
    graph = tmp_path / "gate-policy-graph.json"
    decision_output = tmp_path / "gate-policy-graph-decision.json"
    dev_gate = tmp_path / "gate-policy-decision.json"
    variance_gate = tmp_path / "slice-variance-gate-decision.json"
    cost_gate = tmp_path / "cost-gate-decision.json"
    dev_gate.write_text(
        json.dumps({
            "schema_version": "2026-06-05.gate-policy-decision.v1",
            "status": "passed_for_canary",
            "policy_id": "slice-dev-hard-gate",
            "split": "dev",
            "gate": {"canary_allowed": True, "promotion_ready": False},
            "hard_blockers": [],
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    variance_gate.write_text(
        json.dumps({
            "schema_version": "2026-06-05.slice-variance-gate-decision.v1",
            "status": "blocked",
            "policy_id": "paired-repeat-variance-gate",
            "split": "dev",
            "gate": {"canary_allowed": False, "promotion_ready": False},
            "hard_blockers": ["stable_slice_regression"],
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    cost_gate.write_text(
        json.dumps({
            "schema_version": "2026-06-05.gate-policy-decision.v1",
            "status": "blocked",
            "policy_id": "cost-ceiling-gate",
            "split": "dev",
            "gate": {"canary_allowed": False, "promotion_ready": False},
            "hard_blockers": ["cost_too_high"],
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    graph_exit = main([
        "proposal",
        "build-gate-policy-graph",
        "--graph-id",
        "dev-policy-graph",
        "--required-policy",
        "slice-dev-hard-gate",
        "--required-policy",
        "paired-repeat-variance-gate",
        "--optional-policy",
        "cost-ceiling-gate",
        "--output",
        str(graph),
        "--json",
    ])
    graph_payload = json.loads(capsys.readouterr().out)

    decision_exit = main([
        "proposal",
        "evaluate-gate-policy-graph",
        "--policy-graph",
        str(graph),
        "--decision",
        str(dev_gate),
        "--decision",
        str(variance_gate),
        "--decision",
        str(cost_gate),
        "--output",
        str(decision_output),
        "--json",
    ])
    decision = json.loads(capsys.readouterr().out)

    assert graph_exit == 0
    assert graph_payload["schema_version"] == "2026-06-05.gate-policy-graph.v1"
    assert decision_exit == 0
    assert decision["schema_version"] == "2026-06-05.gate-policy-graph-decision.v1"
    assert decision["blocking_policies"] == ["paired-repeat-variance-gate"]
    assert decision["advisory_blocking_policies"] == ["cost-ceiling-gate"]
    assert decision["gate"]["canary_allowed"] is False
    assert decision["official_scores_claimed"] is False
    assert decision_output.exists()


def test_paired_repeat_manifest_cli_feeds_variance_gate(tmp_path, capsys):
    first = tmp_path / "slice-matrix-a.json"
    second = tmp_path / "slice-matrix-b.json"
    manifest = tmp_path / "paired-repeat-manifest.json"
    decision = tmp_path / "slice-variance-gate.json"
    base_matrix = {
        "schema_version": "2026-06-04.slice-eval-matrix.v1",
        "task_family": "generic_fixture",
        "baseline_ref": "baseline-profile-a",
        "candidate_ref": "candidate-profile-b",
        "split": "dev",
        "metric_delta": {"SHIFT": 0.1},
        "slices": [
            {
                "slice_key": "dev/category/multilingual_bn",
                "slice_name": "multilingual_bn",
                "delta": -10.0,
                "gate": "blocked",
            }
        ],
        "official_scores_claimed": False,
    }
    first.write_text(json.dumps(base_matrix), encoding="utf-8")
    second_matrix = dict(base_matrix)
    second_matrix["metric_delta"] = {"SHIFT": 0.2}
    second_matrix["slices"] = [
        {
            "slice_key": "dev/category/multilingual_bn",
            "slice_name": "multilingual_bn",
            "delta": -8.0,
            "gate": "blocked",
        }
    ]
    second.write_text(json.dumps(second_matrix), encoding="utf-8")

    manifest_exit = main([
        "proposal",
        "build-paired-repeat-manifest",
        "--slice-matrix",
        str(first),
        "--slice-matrix",
        str(second),
        "--task-family",
        "generic_fixture",
        "--output",
        str(manifest),
        "--json",
    ])
    manifest_payload = json.loads(capsys.readouterr().out)

    assert manifest_exit == 0
    assert manifest_payload["schema_version"] == "2026-06-05.paired-repeat-manifest.v1"
    assert manifest_payload["repeat_count"] == 2
    assert manifest_payload["hard_blockers"] == []
    assert manifest.exists()

    decision_exit = main([
        "proposal",
        "evaluate-slice-variance-gate",
        "--paired-repeat-manifest",
        str(manifest),
        "--output",
        str(decision),
        "--json",
    ])
    decision_payload = json.loads(capsys.readouterr().out)

    assert decision_exit == 0
    assert decision_payload["status"] == "blocked"
    assert decision_payload["paired_repeat_manifest_ref"] == str(manifest)
    assert "stable_slice_regression" in decision_payload["hard_blockers"]
    assert decision_payload["official_scores_claimed"] is False
    assert decision.exists()


def test_slice_patch_outcome_cli_records_gate_result(tmp_path, capsys):
    candidate = tmp_path / "slice-patch-candidate.json"
    materialization = tmp_path / "slice-patch-materialization.json"
    gate_decision = tmp_path / "gate-policy-decision.json"
    output = tmp_path / "slice-patch-outcome.json"
    candidate.write_text(
        json.dumps({
            "schema_version": "2026-06-04.slice-patch-candidate.v1",
            "patch_id": "slice-patch-001",
            "module_id": "multilingual_variant_explanation",
            "section_id": "output_format",
            "optimizer": "promptwizard-constrained",
            "candidate_strategy": "constraint_guard_variant",
            "based_on_slices": ["dev/category/multilingual_bn"],
            "protected_slices": ["multilingual_tr"],
            "before_text": "return concise JSON",
            "after_text": "return concise JSON with locale rationale",
            "edit_scope": "single_section",
            "claim_boundary": "local section patch candidate only",
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    materialization.write_text(
        json.dumps({
            "schema_version": "2026-06-04.slice-patch-materialization.v1",
            "status": "needs_prompt_profile_registration",
            "base_profile_id": "p3-system-fixture",
            "patch_id": "slice-patch-001",
            "execution_ready": False,
            "claim_boundary": "review-only materialization",
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    gate_decision.write_text(
        json.dumps({
            "schema_version": "2026-06-05.gate-policy-decision.v1",
            "status": "blocked",
            "policy_id": "slice-dev-hard-gate",
            "split": "dev",
            "metric_delta": {"SHIFT": 0.2},
            "gate": {
                "canary_allowed": False,
                "promotion_ready": False,
            },
            "hard_blockers": ["slice_regression"],
            "slice_regressions": [
                {
                    "slice_key": "dev/category/multilingual_bn",
                    "slice_name": "multilingual_bn",
                    "delta": -8.0,
                    "gate": "blocked",
                }
            ],
            "claim_boundary": "benchmark-agnostic gate policy decision only",
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "record-slice-patch-outcome",
        "--candidate",
        str(candidate),
        "--materialization",
        str(materialization),
        "--gate-decision",
        str(gate_decision),
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == "2026-06-05.slice-patch-outcome.v1"
    assert payload["patch_id"] == "slice-patch-001"
    assert payload["accepted_for_next_stage"] is False
    assert payload["failure_labels"] == ["slice_regression"]
    assert payload["gate"]["canary_allowed"] is False
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_slice_optimizer_selection_cli_uses_outcome_memory(tmp_path, capsys):
    outcomes = tmp_path / "slice-patch-outcomes.jsonl"
    output = tmp_path / "slice-optimizer-selection.json"
    rows = [
        {
            "schema_version": "2026-06-05.slice-patch-outcome.v1",
            "status": "completed",
            "patch_id": "blocked-pw",
            "optimizer": "promptwizard-constrained",
            "module_id": "multilingual_variant_explanation",
            "section_id": "output_format",
            "gate_status": "blocked",
            "accepted_for_next_stage": False,
            "failure_labels": ["slice_regression"],
            "learning_signal": {
                "outcome": "blocked",
                "target_scope": "multilingual_variant_explanation/output_format",
                "failure_labels": ["slice_regression"],
            },
            "official_scores_claimed": False,
        },
        {
            "schema_version": "2026-06-05.slice-patch-outcome.v1",
            "status": "completed",
            "patch_id": "passed-textgrad",
            "optimizer": "textgrad-local",
            "module_id": "multilingual_variant_explanation",
            "section_id": "output_format",
            "gate_status": "passed_for_canary",
            "accepted_for_next_stage": True,
            "failure_labels": [],
            "learning_signal": {
                "outcome": "passed_for_canary",
                "target_scope": "multilingual_variant_explanation/output_format",
                "failure_labels": [],
            },
            "official_scores_claimed": False,
        },
    ]
    outcomes.write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-slice-optimizer-selection",
        "--outcomes",
        str(outcomes),
        "--target-scope",
        "multilingual_variant_explanation/output_format",
        "--failure-label",
        "slice_regression",
        "--candidate-optimizer",
        "promptwizard-constrained",
        "--candidate-optimizer",
        "textgrad-local",
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["schema_version"] == "2026-06-05.slice-optimizer-selection.v1"
    assert payload["selected_optimizer"] == "textgrad-local"
    assert payload["optimizer_scores"][0]["optimizer"] == "textgrad-local"
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_cli_cp_bench_baseline_treats_dataset_block_as_written_artifact(
    monkeypatch,
    tmp_path,
    capsys,
):
    monkeypatch.setattr(
        "scripts.cli.write_cp_bench_local_baseline",
        lambda *args, **kwargs: {
            "status": "blocked_dataset_unavailable",
            "artifact_manifest_path": str(kwargs["output_dir"] / "artifact-manifest.json")
            if "output_dir" in kwargs
            else str(args[0] / "artifact-manifest.json"),
            "official_scores_claimed": False,
        },
    )

    exit_code = main([
        "hf-eval",
        "cp-bench-baseline",
        "--output-dir",
        str(tmp_path / "cp-bench-baseline"),
        "--limit",
        "1",
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "blocked_dataset_unavailable"
    assert payload["official_scores_claimed"] is False


def test_cli_arguard_b1_verify_writes_json_payload(monkeypatch, tmp_path, capsys):
    captured = {}

    def fake_arguard_b1_live_verification(output_dir, **kwargs):
        captured["output_dir"] = output_dir
        captured.update(kwargs)
        return {
            "status": "written",
            "verification_status": "verified_with_asset_blockers",
            "official_scores_claimed": False,
            "manual_submission_required": True,
            "json_path": str(output_dir / "arguard-b1-live-verification.json"),
            "contract_path": str(output_dir / "arguard-b1-target-contract.md"),
        }

    monkeypatch.setattr(
        "scripts.cli.write_arguard_b1_live_verification",
        fake_arguard_b1_live_verification,
    )

    exit_code = main([
        "hf-eval",
        "arguard-b1-verify",
        "--output-dir",
        str(tmp_path / "arguard-b1-p0"),
        "--timeout-seconds",
        "11",
        "--no-raw",
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "written"
    assert payload["verification_status"] == "verified_with_asset_blockers"
    assert payload["official_scores_claimed"] is False
    assert captured["output_dir"] == tmp_path / "arguard-b1-p0"
    assert captured["timeout_seconds"] == 11
    assert captured["include_raw"] is False


def test_cli_cp_bench_client_candidate_writes_json_payload(
    monkeypatch,
    tmp_path,
    capsys,
):
    monkeypatch.setattr(
        "scripts.cli.write_cp_bench_client_candidate_submission",
        lambda *args, **kwargs: {
            "status": "partial_generated",
            "submission_path": str(args[0] / "candidate-submission.jsonl"),
            "source_audit_path": str(args[0] / "source-audit.json"),
            "artifact_manifest_path": str(args[0] / "artifact-manifest.json"),
            "generated_count": 3,
            "fallback_count": 7,
            "reference_model_field_accessed": False,
            "official_scores_claimed": False,
        },
    )

    exit_code = main([
        "hf-eval",
        "cp-bench-client-candidate",
        "--output-dir",
        str(tmp_path / "cp-bench-client-candidate"),
        "--limit",
        "10",
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "partial_generated"
    assert payload["generated_count"] == 3
    assert payload["fallback_count"] == 7
    assert payload["reference_model_field_accessed"] is False
    assert payload["official_scores_claimed"] is False


def test_memory_cleanup_cli_dry_run_json_reports_candidates(tmp_path, capsys):
    store_path = tmp_path / "memory.jsonl"
    store = ResearchMemoryStore(store_path)
    for card in [
        _procedure_memory_card("proc-old", created_at=10.0),
        _procedure_memory_card("proc-middle", created_at=20.0),
        _procedure_memory_card("proc-new", created_at=30.0),
    ]:
        store.append(card)

    exit_code = main([
        "memory",
        "cleanup",
        "--store",
        str(store_path),
        "--dry-run",
        "--keep-last",
        "1",
        "--memory-type",
        "procedure",
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["dry_run"] is True
    assert payload["candidate_count"] == 2
    assert payload["deleted_count"] == 0
    assert payload["kept_count"] == 1
    assert [item["card_id"] for item in payload["candidates"]] == [
        "proc-old",
        "proc-middle",
    ]
    assert [card.card_id for card in store.list_cards()] == [
        "proc-old",
        "proc-middle",
        "proc-new",
    ]


def test_memory_cleanup_cli_execute_include_private(tmp_path, capsys):
    store_path = tmp_path / "memory.jsonl"
    store = ResearchMemoryStore(store_path)
    for card in [
        _procedure_memory_card("proc-public-old", created_at=1.0),
        _procedure_memory_card(
            "proc-private-old",
            created_at=1.0,
            privacy_scope="private",
        ),
    ]:
        store.append(card)

    exit_code = main([
        "memory",
        "cleanup",
        "--store",
        str(store_path),
        "--memory-type",
        "procedure",
        "--older-than-days",
        "1",
        "--include-private",
        "--confirm",
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["dry_run"] is False
    assert payload["candidate_count"] == 2
    assert payload["deleted_count"] == 2
    assert payload["kept_count"] == 0
    assert [item["card_id"] for item in payload["candidates"]] == [
        "proc-public-old",
        "proc-private-old",
    ]
    assert store.list_cards() == []


def test_memory_cleanup_cli_execute_requires_confirm(tmp_path, capsys):
    store_path = tmp_path / "memory.jsonl"
    store = ResearchMemoryStore(store_path)
    store.append(_procedure_memory_card("proc-old", created_at=1.0))

    exit_code = main([
        "memory",
        "cleanup",
        "--store",
        str(store_path),
        "--memory-type",
        "procedure",
        "--json",
    ])

    output = capsys.readouterr()
    assert exit_code == 1
    assert "requires --confirm" in output.err
    assert [card.card_id for card in store.list_cards()] == ["proc-old"]


def test_status_command_prints_json(monkeypatch, capsys):
    monkeypatch.setattr(
        "scripts.cli.AutoResearchManager.get_status",
        lambda self, task_id: {"task_id": task_id, "status": "running"},
    )

    exit_code = main(["status", "demo"])

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["status"] == "running"


def test_check_command_invokes_release_check(monkeypatch):
    captured = {}

    def fake_call(cmd, cwd=None):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        return 0

    monkeypatch.setattr("scripts.cli.subprocess.call", fake_call)

    exit_code = main(["check", "--json", "--skip-demos", "--python", "python3"])

    assert exit_code == 0
    assert captured["cmd"][-4:] == [
        "--python",
        "python3",
        "--skip-golden-path",
        "--json",
    ]
    assert "release_check.py" in captured["cmd"][1]


def test_artifacts_list_command_prints_json(monkeypatch, capsys):
    monkeypatch.setattr(
        "scripts.cli.mcp_service.list_runtime_artifacts_tool",
        lambda arguments: {"runtime_root": arguments["runtime_root"], "task_ids": ["demo"]},
    )

    exit_code = main(["artifacts", "list", "--runtime-root", "/tmp/runtime"])

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {"runtime_root": "/tmp/runtime", "task_ids": ["demo"]}


def test_cli_proposal_context_writes_artifacts(tmp_path: Path, capsys) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    baseline.write_text('{"metric": 1}', encoding="utf-8")
    current.write_text('{"metric": 2}', encoding="utf-8")
    output_dir = tmp_path / "context"

    exit_code = main([
        "proposal",
        "context",
        "--objective",
        "Improve metric",
        "--output-dir",
        str(output_dir),
        "--baseline-report",
        str(baseline),
        "--current-report",
        str(current),
        "--json",
    ])

    printed = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert printed["status"] == "ready_for_client_proposal"
    assert (output_dir / "proposal-context.json").exists()


def test_cli_proposal_validate_rejects_invalid_surface(
    tmp_path: Path,
    capsys,
) -> None:
    proposal = tmp_path / "proposal.json"
    proposal.write_text(
        json.dumps({
            "proposal_id": "bad",
            "hypothesis": "Change too much",
            "change_surface": "training_recipe",
            "change_spec": {"single_primary_variable": False},
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "validate",
        "--proposal",
        str(proposal),
        "--allowed-change-surface",
        "prompt_profile",
        "--json",
    ])

    printed = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert printed["status"] == "rejected"
    assert "change_surface_not_allowed" in printed["failure_labels"]


def test_cli_proposal_reflect_writes_reflection(tmp_path: Path, capsys) -> None:
    proposal = tmp_path / "proposal.json"
    evaluation = tmp_path / "evaluation.json"
    output_dir = tmp_path / "reflection"
    proposal.write_text(
        json.dumps({
            "proposal_id": "round-001",
            "hypothesis": "A bounded routing change can improve SHIFT.",
            "evidence_used": [{"artifact": "dev_report", "observation": "delta"}],
            "change_surface": "routing",
            "change_spec": {"single_primary_variable": True, "target": "router"},
            "expected_effect": {"primary_metric": "SHIFT", "expected_direction": "increase"},
            "validation_plan": {
                "first_split": "dev",
                "promotion_split": "canary",
                "rollback_if": ["SHIFT_delta_lt_0"],
            },
            "risk_assessment": {"overfit_risk": "low"},
            "next_if_success": "promote_candidate_profile",
            "next_if_failure": "rollback_candidate",
            "claim_boundary": "local diagnostic proposal only",
        }),
        encoding="utf-8",
    )
    evaluation.write_text(
        json.dumps({"rollback_reasons": ["canary_not_confirmed"]}),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "reflect",
        "--proposal",
        str(proposal),
        "--evaluation",
        str(evaluation),
        "--output-dir",
        str(output_dir),
        "--json",
    ])

    printed = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert printed["status"] == "needs_rollback_or_more_evidence"
    assert (output_dir / "proposal-reflection.json").exists()


def test_cli_proposal_reflect_can_sync_memory_store(
    tmp_path: Path,
    capsys,
) -> None:
    proposal = tmp_path / "proposal.json"
    evaluation = tmp_path / "evaluation.json"
    output_dir = tmp_path / "reflection"
    memory_store = tmp_path / "proposal-memory.jsonl"
    proposal.write_text(
        json.dumps({
            "proposal_id": "round-memory",
            "hypothesis": "A bounded prompt change can improve SHIFT.",
            "evidence_used": [{"artifact": "dev_report", "observation": "delta"}],
            "change_surface": "prompt_profile",
            "change_spec": {"single_primary_variable": True, "target": "p3-dev-v2"},
            "expected_effect": {"primary_metric": "SHIFT", "expected_direction": "increase"},
            "validation_plan": {
                "first_split": "dev",
                "promotion_split": "canary",
                "rollback_if": ["SHIFT_delta_lt_0"],
            },
            "risk_assessment": {"overfit_risk": "low"},
            "next_if_success": "run_canary_confirmation",
            "next_if_failure": "rollback_candidate",
            "claim_boundary": "local diagnostic proposal only",
        }),
        encoding="utf-8",
    )
    evaluation.write_text(
        json.dumps({"dev_delta": {"SHIFT": 1.0, "H": 0.0}}),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "reflect",
        "--proposal",
        str(proposal),
        "--evaluation",
        str(evaluation),
        "--output-dir",
        str(output_dir),
        "--memory-store",
        str(memory_store),
        "--json",
    ])

    printed = json.loads(capsys.readouterr().out)
    cards = ResearchMemoryStore(memory_store).list_cards()
    assert exit_code == 0
    assert printed["memory_sync"]["status"] == "synced"
    assert printed["memory_sync"]["card_id"] == "proposal-reflection-round-memory"
    assert len(cards) == 1
    assert cards[0].config["status"] == "needs_promotion_evidence"


def test_cli_proposal_context_can_inject_memory_and_resource_constraints(
    tmp_path: Path,
    capsys,
) -> None:
    memory_store = tmp_path / "proposal-memory.jsonl"
    resource_constraints = tmp_path / "resource-constraints.json"
    resource_constraints.write_text(
        json.dumps({"max_rounds": 3, "local_model": "qwen3-8b"}),
        encoding="utf-8",
    )
    ResearchMemoryStore(memory_store).append(
        _procedure_memory_card("fasttext-proposal-procedure", created_at=10.0)
    )

    exit_code = main([
        "proposal",
        "context",
        "--objective",
        "Plan fasttext proposal",
        "--output-dir",
        str(tmp_path / "proposal-context"),
        "--memory-store",
        str(memory_store),
        "--memory-query",
        "fasttext proposal",
        "--resource-constraints",
        str(resource_constraints),
        "--json",
    ])

    printed = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert printed["inputs"]["memory_cards"]["provided"] is True
    assert printed["inputs"]["memory_cards"]["metrics"]["retrieved_count"] == 1
    assert printed["inputs"]["resource_constraints"]["raw"]["max_rounds"] == 3
    assert printed["artifact_manifest"]["artifacts"]["memory_cards"]["path"] == str(
        memory_store
    )


def test_cli_proposal_search_summarizes_frontier(tmp_path: Path, capsys) -> None:
    items = tmp_path / "proposal-items.json"
    items.write_text(
        json.dumps([
            {"proposal_id": "p1", "score_delta": {"dev": 0.5}},
            {
                "proposal_id": "p2",
                "score_delta": {"dev": 0.6, "canary": 0.2},
                "promote_to_default": True,
            },
        ]),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "search",
        "--items",
        str(items),
        "--branch-budget",
        "1",
        "--diversity-max-per-family",
        "1",
        "--json",
    ])

    printed = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert printed["status"] == "supported_candidate_found"
    assert printed["best_proposal_id"] == "p2"
    assert [node["proposal_id"] for node in printed["selected_next_nodes"]] == ["p2"]
    assert printed["stop_reason"] == "frontier_open"
    assert printed["official_scores_claimed"] is False


def test_memory_record_and_retrieve_cli(tmp_path, capsys):
    proof_dir = tmp_path / "release-proof"
    proof_dir.mkdir()
    release_manifest = proof_dir / "release-proof-manifest.json"
    multi_round_report = proof_dir / "multi-round-report.json"
    review_checklist = proof_dir / "release-review-checklist.md"
    store = tmp_path / "memory.jsonl"
    release_manifest.write_text(
        json.dumps(
            {
                "official_scores_claimed": False,
                "bundle_sha256": "abc123",
                "stage": "p5_fasttext_release_proof_bundle",
                "status": "completed",
                "p4_summary": {"review_status": "approved_with_limitations"},
            }
        ),
        encoding="utf-8",
    )
    multi_round_report.write_text(
        json.dumps(
            {
                "stage": "p5_fasttext_multi_proposal_loop",
                "official_scores_claimed": False,
                "paper_reference": {"paper_id": "arxiv:1607.01759"},
                "baseline": {"p_at_1": 0.914},
                "summary": {
                    "best_metric": 0.916,
                    "best_source": "round-001-wordngrams-2",
                    "failure_count": 1,
                },
                "rollback_summary": {"rollback_events": 1},
            }
        ),
        encoding="utf-8",
    )
    review_checklist.write_text(
        "Review status: `approved_with_limitations`",
        encoding="utf-8",
    )

    record_exit = main([
        "memory",
        "record-fasttext-release",
        "--store",
        str(store),
        "--release-manifest",
        str(release_manifest),
        "--multi-round-report",
        str(multi_round_report),
        "--review-checklist",
        str(review_checklist),
    ])
    record_payload = json.loads(capsys.readouterr().out)

    assert record_exit == 0
    assert record_payload["status"] == "recorded"
    assert record_payload["card_count"] == 2

    retrieve_exit = main([
        "memory",
        "retrieve",
        "--store",
        str(store),
        "--query",
        "AG News fastText",
        "--paper-id",
        "arxiv:1607.01759",
        "--dataset",
        "AG News",
        "--limit",
        "5",
    ])
    retrieve_payload = json.loads(capsys.readouterr().out)

    assert retrieve_exit == 0
    assert any(
        "arxiv:1607.01759" in match["card"]["paper_ids"]
        for match in retrieve_payload["matches"]
    )


def test_memory_cli_can_sync_and_search_optional_adapters(
    monkeypatch,
    tmp_path,
    capsys,
):
    proof_dir = tmp_path / "release-proof"
    proof_dir.mkdir()
    release_manifest = proof_dir / "release-proof-manifest.json"
    multi_round_report = proof_dir / "multi-round-report.json"
    review_checklist = proof_dir / "release-review-checklist.md"
    store = tmp_path / "memory.jsonl"
    release_manifest.write_text(
        json.dumps(
            {
                "official_scores_claimed": False,
                "stage": "p5_fasttext_release_proof_bundle",
                "status": "completed",
                "p4_summary": {"review_status": "approved_with_limitations"},
            }
        ),
        encoding="utf-8",
    )
    multi_round_report.write_text(
        json.dumps(
            {
                "stage": "p5_fasttext_multi_proposal_loop",
                "official_scores_claimed": False,
                "paper_reference": {"paper_id": "arxiv:1607.01759"},
                "baseline": {"p_at_1": 0.75},
                "summary": {"best_metric": 0.875, "failure_count": 1},
            }
        ),
        encoding="utf-8",
    )
    review_checklist.write_text(
        "Review status: `approved_with_limitations`",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "scripts.cli.sync_cards_to_adapters",
        lambda cards, adapter_names=None: {
            "status": "completed",
            "card_count": len(cards),
            "adapter_names": adapter_names,
            "results": [{"adapter": "graphiti", "status": "indexed"}],
        },
    )
    monkeypatch.setattr(
        "scripts.cli.search_memory_adapters",
        lambda *, query, limit=10, adapter_names=None: {
            "status": "completed",
            "adapter_names": adapter_names,
            "results": [{"adapter": "cognee", "text": query, "score": 0.8}],
        },
    )

    record_exit = main([
        "memory",
        "record-fasttext-release",
        "--store",
        str(store),
        "--release-manifest",
        str(release_manifest),
        "--multi-round-report",
        str(multi_round_report),
        "--review-checklist",
        str(review_checklist),
        "--sync-adapters",
        "--adapter",
        "graphiti",
    ])
    record_payload = json.loads(capsys.readouterr().out)

    assert record_exit == 0
    assert record_payload["adapter_results"]["adapter_names"] == ["graphiti"]
    assert record_payload["adapter_results"]["results"][0]["status"] == "indexed"

    retrieve_exit = main([
        "memory",
        "retrieve",
        "--store",
        str(store),
        "--query",
        "AG News",
        "--include-adapters",
        "--adapter",
        "cognee",
    ])
    retrieve_payload = json.loads(capsys.readouterr().out)

    assert retrieve_exit == 0
    assert retrieve_payload["adapter_results"]["adapter_names"] == ["cognee"]
    assert retrieve_payload["adapter_results"]["results"][0]["adapter"] == "cognee"


def test_proposal_failure_driven_cli_round_trip(tmp_path, capsys):
    reflection = tmp_path / "proposal-reflection.json"
    proposal = tmp_path / "proposal-card.json"
    evaluation = tmp_path / "evaluation.json"
    outcomes = tmp_path / "proposal-outcomes.jsonl"

    reflection.write_text(
        json.dumps(
            {
                "proposal_id": "round-001",
                "status": "needs_rollback_or_more_evidence",
                "proposal": {
                    "proposal_id": "round-001",
                    "change_surface": "routing",
                    "hypothesis": "Bounded routing change should survive canary.",
                },
                "failure_labels": ["canary_not_confirmed"],
                "recommended_next_action": "rollback_or_keep_as_candidate",
                "evaluation": {
                    "dev_delta": {"SHIFT": 0.5},
                    "canary_delta": {"SHIFT": -0.2},
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    proposal.write_text(
        json.dumps(
            {
                "proposal_id": "round-002",
                "proposal_type": "failure_fix",
                "based_on_failures": ["round-001:canary_not_confirmed:1"],
                "intent": "Preserve dev gain on canary.",
                "change_surface": "routing",
                "target_scope": "single routing block",
                "verification_plan": {"first_split": "dev", "promotion_split": "canary"},
                "rollback_rule": {"if": ["canary_delta_lt_0"]},
                "claim_boundary": "local proposal only",
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    evaluation.write_text(
        json.dumps(
            {
                "dev_delta": {"SHIFT": 0.7},
                "canary_delta": {"SHIFT": 0.1},
                "rollback_reasons": [],
            }
        ),
        encoding="utf-8",
    )

    extract_exit = main([
        "proposal",
        "extract-failures",
        "--source-artifact",
        str(reflection),
        "--output",
        str(tmp_path / "failure-records.jsonl"),
        "--json",
    ])
    extract_payload = json.loads(capsys.readouterr().out)

    assert extract_exit == 0
    assert extract_payload["record_count"] == 1

    record_exit = main([
        "proposal",
        "record-outcome",
        "--proposal",
        str(proposal),
        "--evaluation",
        str(evaluation),
        "--output",
        str(tmp_path / "proposal-outcome.json"),
        "--json",
    ])
    record_payload = json.loads(capsys.readouterr().out)

    assert record_exit == 0
    assert record_payload["accepted"] is True
    outcomes.write_text(json.dumps(record_payload) + "\n", encoding="utf-8")

    pattern_exit = main([
        "proposal",
        "build-pattern-memory",
        "--outcomes",
        str(outcomes),
        "--output",
        str(tmp_path / "proposal-pattern-memory.jsonl"),
        "--json",
    ])
    pattern_payload = json.loads(capsys.readouterr().out)

    assert pattern_exit == 0
    assert pattern_payload["pattern_count"] == 1
    assert pattern_payload["patterns"][0]["proposal_type"] == "failure_fix"


def test_proposal_failure_driven_context_and_rank_cli(tmp_path, capsys):
    failure_records = tmp_path / "failure-records.jsonl"
    failure_records.write_text(
        json.dumps(
            {
                "schema_version": "2026-06-02.failure-record.v1",
                "failure_id": "f1",
                "task_id": "round-001",
                "failure_type": "canary_not_confirmed",
                "symptom": "canary regressed",
                "severity": "medium",
                "claim_boundary": "local only",
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    patterns = tmp_path / "proposal-pattern-memory.jsonl"
    patterns.write_text(
        json.dumps(
            {
                "schema_version": "2026-06-02.proposal-pattern-memory.v1",
                "pattern_id": "failure_fix::canary_not_confirmed",
                "pattern_summary": "failure_fix against canary_not_confirmed",
                "proposal_type": "failure_fix",
                "applicable_when": ["canary_not_confirmed"],
                "historical_success_rate": 0.8,
                "historical_failure_rate": 0.2,
                "claim_boundary": "local only",
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    proposals = tmp_path / "proposal-cards.json"
    proposals.write_text(
        json.dumps(
            [
                {
                    "proposal_id": "p1",
                    "proposal_type": "failure_fix",
                    "based_on_failures": ["f1"],
                    "intent": "Preserve canary behavior.",
                    "change_surface": "routing",
                    "target_scope": "single routing block",
                    "expected_gain": {"score": 0.9},
                    "risk_level": "low",
                    "verification_plan": {"first_split": "dev"},
                    "rollback_rule": {"if": ["canary_delta_lt_0"]},
                    "claim_boundary": "local only",
                    "official_scores_claimed": False,
                }
            ]
        ),
        encoding="utf-8",
    )

    context_exit = main([
        "proposal",
        "build-failure-context",
        "--objective",
        "Preserve canary gain",
        "--failures",
        str(failure_records),
        "--pattern-memory",
        str(patterns),
        "--output",
        str(tmp_path / "failure-context.json"),
        "--json",
    ])
    context_payload = json.loads(capsys.readouterr().out)

    assert context_exit == 0
    assert context_payload["status"] == "ready_for_failure_driven_proposals"

    rank_exit = main([
        "proposal",
        "rank",
        "--proposals",
        str(proposals),
        "--failures",
        str(failure_records),
        "--pattern-memory",
        str(patterns),
        "--output",
        str(tmp_path / "ranked-proposals.json"),
        "--json",
    ])
    rank_payload = json.loads(capsys.readouterr().out)

    assert rank_exit == 0
    assert rank_payload["ranked_proposals"][0]["proposal_id"] == "p1"


def test_proposal_failure_driven_handoff_cli(tmp_path, capsys):
    context = tmp_path / "failure-context.json"
    ranking = tmp_path / "ranked-proposals.json"
    context.write_text(
        json.dumps(
            {
                "status": "ready_for_failure_driven_proposals",
                "objective": "Preserve canary gain",
                "failure_summary": {
                    "record_count": 1,
                    "records": [
                        {
                            "failure_id": "f1",
                            "failure_type": "canary_not_confirmed",
                            "symptom": "canary regressed",
                        }
                    ],
                },
                "pattern_summary": {"matched_patterns": []},
                "claim_boundary": "local only",
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    ranking.write_text(
        json.dumps(
            {
                "status": "completed",
                "ranked_proposals": [
                    {
                        "proposal_id": "p1",
                        "proposal_type": "failure_fix",
                        "based_on_failures": ["f1"],
                        "change_surface": "prompt_profile",
                        "target_scope": "prompt_profile",
                        "verification_plan": {"first_split": "dev", "promotion_split": "canary"},
                        "rollback_rule": {"if": ["canary_delta_lt_0"]},
                        "score": 1.2,
                        "rank": 1,
                        "gate_labels": [],
                        "score_breakdown": {"pattern_prior": 0.8},
                        "claim_boundary": "local only",
                        "official_scores_claimed": False,
                    }
                ],
                "claim_boundary": "local only",
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "handoff",
        "--context",
        str(context),
        "--ranking",
        str(ranking),
        "--output-dir",
        str(tmp_path / "handoff"),
        "--max-selected",
        "1",
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["selected_next_proposals"][0]["proposal_id"] == "p1"
    assert payload["selected_next_proposals"][0]["change_surface"] == "prompt_profile"
    assert payload["proposal_file"].endswith("failure-driven-proposal-handoff.json")


def test_proposal_failure_driven_template_and_bridge_cli(tmp_path, capsys):
    handoff = tmp_path / "failure-handoff.json"
    outcome = tmp_path / "proposal-outcome.json"
    handoff.write_text(
        json.dumps(
            {
                "status": "completed",
                "objective": "Preserve canary gain",
                "selected_next_proposals": [
                    {
                        "proposal_id": "p1",
                        "proposal_type": "failure_fix",
                        "based_on_failures": ["f1"],
                        "change_surface": "prompt_profile",
                        "target_scope": "single prompt-profile scope",
                        "verification_plan": {
                            "first_split": "canary",
                            "promotion_split": "canary",
                            "max_rounds": 1,
                        },
                        "rollback_rule": {"if": ["canary_delta_lt_0"]},
                        "score": 1.2,
                        "rank": 1,
                        "requires_client_review": True,
                    }
                ],
                "failure_summary": {
                    "records": [
                        {
                            "failure_id": "f1",
                            "failure_type": "canary_not_confirmed",
                            "symptom": "canary regressed",
                        }
                    ]
                },
                "claim_boundary": "local only",
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    outcome.write_text(
        json.dumps(
            {
                "status": "completed",
                "schema_version": "2026-06-02.proposal-outcome.v1",
                "outcome_id": "p1-outcome",
                "proposal_id": "p1",
                "proposal_type": "failure_fix",
                "based_on_failures": ["f1"],
                "change_surface": "routing",
                "target_scope": "single routing block",
                "executed": True,
                "accepted": True,
                "metric_delta": {"dev": 0.5, "canary": 0.1},
                "rollback_triggered": False,
                "failure_labels": [],
                "claim_boundary": "local only",
                "official_scores_claimed": False,
                "output_path": str(outcome),
            }
        ),
        encoding="utf-8",
    )

    template_exit = main([
        "proposal",
        "build-client-templates",
        "--handoff",
        str(handoff),
        "--output-dir",
        str(tmp_path / "templates"),
        "--json",
    ])
    template_payload = json.loads(capsys.readouterr().out)

    assert template_exit == 0
    assert template_payload["proposal_templates"][0]["proposal_id"].startswith("p1")
    assert template_payload["proposal_templates"][0]["change_surface"] == "prompt_profile"
    assert template_payload["proposal_templates"][0]["validation_plan"]["first_split"] == "canary"
    assert template_payload["proposal_templates"][0]["expected_effect"]["primary_metric"] == "SHIFT"

    bridge_exit = main([
        "proposal",
        "bridge-to-memory-card",
        "--outcome",
        str(outcome),
        "--handoff",
        str(handoff),
        "--output",
        str(tmp_path / "memory-card-candidate.json"),
        "--json",
    ])
    bridge_payload = json.loads(capsys.readouterr().out)

    assert bridge_exit == 0
    assert bridge_payload["memory_card_candidate"]["card_id"] == "failure-driven-p1"


def test_memory_record_card_candidate_cli_requires_confirm_and_records(
    tmp_path,
    capsys,
):
    artifact = tmp_path / "proposal-outcome.json"
    artifact.write_text("{}", encoding="utf-8")
    candidate = tmp_path / "memory-card-candidate.json"
    store = tmp_path / "memory.jsonl"
    candidate.write_text(
        json.dumps(
            {
                "status": "completed",
                "memory_card_candidate": {
                    "card_id": "failure-driven-p1",
                    "memory_type": "patch",
                    "task_family": "failure-driven-proposal",
                    "summary": "Failure-driven proposal p1 outcome=accepted.",
                    "patch_type": "routing",
                    "failure_category": "canary_not_confirmed",
                    "artifact_refs": [
                        {
                            "name": "failure_driven_outcome",
                            "path": str(artifact),
                            "sha256": "abc123",
                            "artifact_type": "proposal_outcome",
                        }
                    ],
                    "claim_boundary": "local candidate only",
                    "official_scores_claimed": False,
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    exit_without_confirm = main([
        "memory",
        "record-card-candidate",
        "--store",
        str(store),
        "--candidate-file",
        str(candidate),
    ])
    err = capsys.readouterr().err

    assert exit_without_confirm == 1
    assert "--confirm" in err

    exit_with_confirm = main([
        "memory",
        "record-card-candidate",
        "--store",
        str(store),
        "--candidate-file",
        str(candidate),
        "--confirm",
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_with_confirm == 0
    assert payload["status"] == "recorded"
    assert payload["card_ids"] == ["failure-driven-p1"]


def test_proposal_evaluate_effectiveness_cli_writes_report(tmp_path, capsys):
    control = tmp_path / "control-outcomes.jsonl"
    treatment = tmp_path / "treatment-outcomes.jsonl"
    control.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "outcome_id": "c1",
                        "accepted": False,
                        "metric_delta": {"dev": 0.2, "canary": -0.2},
                        "rollback_triggered": True,
                        "failure_labels": ["canary_not_confirmed"],
                        "official_scores_claimed": False,
                    }
                ),
                json.dumps(
                    {
                        "outcome_id": "c2",
                        "accepted": True,
                        "metric_delta": {"dev": 0.3, "canary": 0.0},
                        "rollback_triggered": False,
                        "failure_labels": ["canary_not_confirmed"],
                        "official_scores_claimed": False,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    treatment.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "outcome_id": "t1",
                        "accepted": True,
                        "metric_delta": {"dev": 0.4, "canary": 0.2},
                        "rollback_triggered": False,
                        "failure_labels": [],
                        "official_scores_claimed": False,
                    }
                ),
                json.dumps(
                    {
                        "outcome_id": "t2",
                        "accepted": True,
                        "metric_delta": {"dev": 0.1, "canary": 0.1},
                        "rollback_triggered": False,
                        "failure_labels": [],
                        "official_scores_claimed": False,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "evaluate-effectiveness",
        "--control-outcomes",
        str(control),
        "--treatment-outcomes",
        str(treatment),
        "--output",
        str(tmp_path / "proposal-effectiveness.json"),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["comparison"]["proposal_accept_rate_lift"] == 0.5
    assert payload["comparison"]["verdict"] == "treatment_improved_on_measured_metrics"


def test_proposal_build_smol_worldcup_effectiveness_bundle_cli_writes_report(
    tmp_path,
    capsys,
):
    control_dev = tmp_path / "control-dev.json"
    treatment_dev = tmp_path / "treatment-dev.json"
    control_canary = tmp_path / "control-canary.json"
    treatment_canary = tmp_path / "treatment-canary.json"
    control_dev.write_text(
        json.dumps(
            {
                "round_id": "qwen3-8b-dev-round-002-dev-v2-20260521",
                "dataset": {"evaluation_split": "dev", "row_count": 100},
                "model": {"prompt_profile": "p3-dev-v2"},
                "proposal": {
                    "proposal_id": "qwen3-8b-dev-round-002-dev-v2-20260521-failure-driven-routing",
                    "top_failure_categories": [{"category": "confidence_calibration", "count": 7}],
                },
                "metrics": {
                    "H": 92.424242,
                    "I": 73.880597,
                    "SHIFT": 81.298055,
                    "WCS_local_diagnostic": 90.165434,
                },
                "failure_summary": {"failure_count": 35},
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    treatment_dev.write_text(
        json.dumps(
            {
                "round_id": "qwen3-8b-dev-round-004-semantic-v2-20260521",
                "dataset": {"evaluation_split": "dev", "row_count": 100},
                "model": {"prompt_profile": "p3-semantic-v2"},
                "proposal": {
                    "proposal_id": "qwen3-8b-dev-round-004-semantic-v2-20260521-failure-driven-routing",
                    "top_failure_categories": [{"category": "knowledge_synthesis", "count": 4}],
                },
                "metrics": {
                    "H": 92.424242,
                    "I": 75.447761,
                    "SHIFT": 82.238353,
                    "WCS_local_diagnostic": 90.685365,
                },
                "failure_summary": {"failure_count": 36},
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    control_canary.write_text(
        json.dumps(
            {
                "round_id": "qwen3-8b-canary-round-002-dev-v2-20260521",
                "dataset": {"evaluation_split": "canary", "row_count": 25},
                "model": {"prompt_profile": "p3-dev-v2"},
                "proposal": {
                    "proposal_id": "qwen3-8b-canary-round-002-dev-v2-20260521-failure-driven-routing",
                    "top_failure_categories": [{"category": "reasoning", "count": 3}],
                },
                "metrics": {
                    "H": 77.857143,
                    "I": 77.777778,
                    "SHIFT": 77.809524,
                    "WCS_local_diagnostic": 88.209707,
                },
                "failure_summary": {"failure_count": 12},
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    treatment_canary.write_text(
        json.dumps(
            {
                "round_id": "qwen3-8b-canary-round-004-semantic-v2-20260521",
                "dataset": {"evaluation_split": "canary", "row_count": 25},
                "model": {"prompt_profile": "p3-semantic-v2"},
                "proposal": {
                    "proposal_id": "qwen3-8b-canary-round-004-semantic-v2-20260521-failure-driven-routing",
                    "top_failure_categories": [{"category": "reasoning", "count": 2}],
                },
                "metrics": {
                    "H": 77.857143,
                    "I": 77.222222,
                    "SHIFT": 77.47619,
                    "WCS_local_diagnostic": 88.02056,
                },
                "failure_summary": {"failure_count": 11},
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-smol-worldcup-effectiveness-bundle",
        "--control-report",
        str(control_dev),
        "--control-report",
        str(control_canary),
        "--treatment-report",
        str(treatment_dev),
        "--treatment-report",
        str(treatment_canary),
        "--output-dir",
        str(tmp_path / "bundle"),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["comparison"]["proposal_accept_rate_lift"] == 0.5
    assert payload["comparison"]["verdict"] == "mixed_signal"
    assert Path(payload["effectiveness_report_path"]).exists()


def test_proposal_build_effectiveness_claim_audit_cli_writes_report(tmp_path, capsys):
    cross_task_summary = tmp_path / "cross-task-summary.json"
    cross_task_summary.write_text(
        json.dumps(
            {
                "status": "completed",
                "schema_version": "2026-06-02.cross-task-proposal-effectiveness-summary.v1",
                "task_count": 3,
                "task_summaries": [
                    {
                        "task_family": "cp_bench_constraint_model_generation",
                        "verdict": "treatment_improved_on_measured_metrics",
                    },
                    {
                        "task_family": "fasttext_text_classification",
                        "verdict": "mixed_signal",
                    },
                    {
                        "task_family": "smol_worldcup_prompt_routing",
                        "verdict": "mixed_signal",
                    },
                ],
                "aggregate": {
                    "verdict_counts": {
                        "mixed_signal": 2,
                        "treatment_improved_on_measured_metrics": 1,
                    },
                    "consistent_improvements": ["SHIFT"],
                    "tradeoff_metrics": [],
                },
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-effectiveness-claim-audit",
        "--cross-task-summary",
        str(cross_task_summary),
        "--output-dir",
        str(tmp_path / "claim-audit"),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["claim_readiness"] == "insufficient_evidence_for_cross_task_effectiveness_claim"
    assert "run_mixed_signal_task_family_audit" in payload["recommended_next_actions"]
    assert Path(payload["audit_path"]).exists()


def test_proposal_build_smol_worldcup_effectiveness_bundle_cli_split_filter_dev(
    tmp_path,
    capsys,
):
    control_dev = tmp_path / "control-dev.json"
    treatment_dev = tmp_path / "treatment-dev.json"
    control_canary = tmp_path / "control-canary.json"
    treatment_canary = tmp_path / "treatment-canary.json"
    control_dev.write_text(
        json.dumps(
            {
                "round_id": "qwen3-8b-dev-round-002-dev-v2-20260521",
                "dataset": {"evaluation_split": "dev", "row_count": 100},
                "model": {"prompt_profile": "p3-dev-v2"},
                "proposal": {"proposal_id": "dev-control"},
                "metrics": {
                    "H": 92.424242,
                    "I": 73.880597,
                    "SHIFT": 81.298055,
                    "WCS_local_diagnostic": 90.165434,
                },
                "failure_summary": {"failure_count": 35},
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    treatment_dev.write_text(
        json.dumps(
            {
                "round_id": "qwen3-8b-dev-round-004-semantic-v2-20260521",
                "dataset": {"evaluation_split": "dev", "row_count": 100},
                "model": {"prompt_profile": "p3-semantic-v2"},
                "proposal": {"proposal_id": "dev-treatment"},
                "metrics": {
                    "H": 92.424242,
                    "I": 75.447761,
                    "SHIFT": 82.238353,
                    "WCS_local_diagnostic": 90.685365,
                },
                "failure_summary": {"failure_count": 36},
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    control_canary.write_text(
        json.dumps(
            {
                "round_id": "qwen3-8b-canary-round-002-dev-v2-20260521",
                "dataset": {"evaluation_split": "canary", "row_count": 25},
                "model": {"prompt_profile": "p3-dev-v2"},
                "proposal": {"proposal_id": "canary-control"},
                "metrics": {
                    "H": 77.857143,
                    "I": 77.777778,
                    "SHIFT": 77.809524,
                    "WCS_local_diagnostic": 88.209707,
                },
                "failure_summary": {"failure_count": 12},
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    treatment_canary.write_text(
        json.dumps(
            {
                "round_id": "qwen3-8b-canary-round-004-semantic-v2-20260521",
                "dataset": {"evaluation_split": "canary", "row_count": 25},
                "model": {"prompt_profile": "p3-semantic-v2"},
                "proposal": {"proposal_id": "canary-treatment"},
                "metrics": {
                    "H": 77.857143,
                    "I": 77.222222,
                    "SHIFT": 77.47619,
                    "WCS_local_diagnostic": 88.02056,
                },
                "failure_summary": {"failure_count": 11},
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-smol-worldcup-effectiveness-bundle",
        "--control-report",
        str(control_dev),
        "--control-report",
        str(control_canary),
        "--treatment-report",
        str(treatment_dev),
        "--treatment-report",
        str(treatment_canary),
        "--split-filter",
        "dev",
        "--output-dir",
        str(tmp_path / "bundle"),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["split_filter"] == "dev"
    assert payload["comparison_pair_count"] == 1
    assert payload["comparison"]["proposal_accept_rate_lift"] == 1.0
    assert payload["comparison"]["verdict"] == "treatment_improved_on_measured_metrics"


def test_proposal_build_smol_worldcup_result_analysis_cli_writes_report(tmp_path, capsys):
    control = tmp_path / "control.json"
    treatment = tmp_path / "treatment.json"
    control.write_text(
        json.dumps(
            {
                "round_id": "control-dev",
                "dataset": {"evaluation_split": "dev", "row_count": 1},
                "model": {"prompt_profile": "p3-dev-v2"},
                "metrics": {
                    "H": 90.0,
                    "I": 70.0,
                    "SHIFT": 78.0,
                    "WCS_local_diagnostic": 88.0,
                },
                "predictions": [
                    {
                        "row_id": "S1-H2-012",
                        "shift_axis": "H",
                        "category": "confidence_calibration",
                        "subcategory": "hard_math",
                        "auto_grade": "calibration_check",
                        "max_score": 10,
                        "score": 10,
                        "prompt": "What is the integral of e^(x²) from 0 to 1?",
                        "response": "{\"answer\":\"1.46265\",\"confidence\":50}",
                        "grading_method": "calibration_check",
                    }
                ],
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    treatment.write_text(
        json.dumps(
            {
                "round_id": "treatment-dev",
                "dataset": {"evaluation_split": "dev", "row_count": 1},
                "model": {"prompt_profile": "p3-v7-metacognition-textgrad-v2"},
                "metrics": {
                    "H": 88.0,
                    "I": 80.0,
                    "SHIFT": 83.2,
                    "WCS_local_diagnostic": 91.2,
                },
                "predictions": [
                    {
                        "row_id": "S1-H2-012",
                        "shift_axis": "H",
                        "category": "confidence_calibration",
                        "subcategory": "hard_math",
                        "auto_grade": "calibration_check",
                        "max_score": 10,
                        "score": 8.5,
                        "prompt": "What is the integral of e^(x²) from 0 to 1?",
                        "response": "{\"answer\":\"1.46265\",\"confidence\":35}",
                        "grading_method": "calibration_check",
                    }
                ],
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-smol-worldcup-result-analysis",
        "--control-report",
        str(control),
        "--treatment-report",
        str(treatment),
        "--output-dir",
        str(tmp_path / "analysis"),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "analysis_required_before_next_change"
    assert payload["next_action"] == "run_paired_repeat_before_changing_prompt"
    assert payload["row_deltas"][0]["prompt_profile_messages_changed"] is False
    assert Path(payload["analysis_path"]).exists()


def test_proposal_build_smol_worldcup_confidence_variance_gate_cli_writes_report(
    tmp_path,
    capsys,
):
    aa_analysis = tmp_path / "aa-result-analysis.json"
    candidate_analysis = tmp_path / "candidate-result-analysis.json"
    output = tmp_path / "confidence-variance-gate.json"
    aa_analysis.write_text(
        json.dumps({
            "schema_version": "2026-06-27.smol-worldcup-result-analysis.v1",
            "status": "analysis_required_before_next_change",
            "metric_regressions": [{"metric": "H", "delta": -30.0, "split": "dev"}],
            "row_deltas": [
                {
                    "row_id": "S1-H2-012",
                    "category": "confidence_calibration",
                    "score_delta": -7.5,
                    "prompt_profile_messages_changed": False,
                    "root_cause_hypothesis": "stochastic_or_format_variation",
                }
            ],
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    candidate_analysis.write_text(
        json.dumps({
            "schema_version": "2026-06-27.smol-worldcup-result-analysis.v1",
            "status": "analysis_required_before_next_change",
            "metric_regressions": [{"metric": "H", "delta": -42.5, "split": "dev"}],
            "row_deltas": [
                {
                    "row_id": "S1-H2-012",
                    "category": "confidence_calibration",
                    "score_delta": -10.0,
                    "prompt_profile_messages_changed": False,
                    "root_cause_hypothesis": "stochastic_or_format_variation",
                }
            ],
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-smol-worldcup-confidence-variance-gate",
        "--aa-result-analysis",
        str(aa_analysis),
        "--candidate-result-analysis",
        str(candidate_analysis),
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "blocked_by_aa_confidence_variance"
    assert payload["gate"]["optimizer_regression_attribution_allowed"] is False
    assert payload["recommended_next_action"] == (
        "build_cached_confidence_scoring_gate_before_prompt_repair"
    )
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_proposal_build_smol_worldcup_cached_confidence_scoring_gate_cli_writes_report(
    tmp_path,
    capsys,
):
    report_a = tmp_path / "aa-confidence-rerun-1.json"
    report_b = tmp_path / "aa-confidence-rerun-2.json"
    output = tmp_path / "cached-confidence-scoring-gate.json"
    base_payload = {
        "schema_version": "2026-06-27.smol-worldcup-model-eval.v1",
        "dataset": {"evaluation_split": "dev", "row_id_filter": ["S1-H2-012"]},
        "model": {
            "id": "deepseek-v4-pro",
            "provider": "deepseek",
            "prompt_profile": "p3-dev-v2",
            "temperature": 0.0,
        },
        "official_scores_claimed": False,
    }
    report_a.write_text(
        json.dumps({
            **base_payload,
            "round_id": "aa-confidence-rerun-1",
            "predictions": [
                {
                    "row_id": "S1-H2-012",
                    "category": "confidence_calibration",
                    "auto_grade": "calibration_check",
                    "prompt": "confidence prompt",
                    "response": "{\"answer\":\"1.46265\",\"confidence\":50}",
                    "score": 10.0,
                    "max_score": 10.0,
                    "grading_method": "calibration_check",
                }
            ],
        }),
        encoding="utf-8",
    )
    report_b.write_text(
        json.dumps({
            **base_payload,
            "round_id": "aa-confidence-rerun-2",
            "predictions": [
                {
                    "row_id": "S1-H2-012",
                    "category": "confidence_calibration",
                    "auto_grade": "calibration_check",
                    "prompt": "confidence prompt",
                    "response": "{\"answer\":\"1.46265\",\"confidence\":95}",
                    "score": 2.5,
                    "max_score": 10.0,
                    "grading_method": "calibration_check",
                }
            ],
        }),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-smol-worldcup-cached-confidence-scoring-gate",
        "--model-eval-report",
        str(report_a),
        "--model-eval-report",
        str(report_b),
        "--output",
        str(output),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "blocked_cached_confidence_scoring_not_ready"
    assert payload["gate"]["prompt_repair_allowed"] is False
    assert "missing_response_cache_key" in payload["hard_blockers"]
    assert "confidence_score_variance_detected" in payload["hard_blockers"]
    assert payload["row_diagnostics"][0]["score_range"] == 7.5
    assert payload["recommended_next_action"] == (
        "add_response_cache_and_scorer_version_then_repeat_confidence_rows"
    )
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_proposal_build_smol_promotion_gate_cli_writes_report(tmp_path, capsys):
    dev_report = tmp_path / "dev-effectiveness.json"
    canary_report = tmp_path / "canary-effectiveness.json"
    dev_report.write_text(
        json.dumps(
            {
                "comparison": {
                    "proposal_accept_rate_lift": 1.0,
                    "rollback_rate_reduction": 0.0,
                    "avg_metric_delta_lift": {"SHIFT": 0.9403},
                    "verdict": "treatment_improved_on_measured_metrics",
                },
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    canary_report.write_text(
        json.dumps(
            {
                "comparison": {
                    "proposal_accept_rate_lift": 0.0,
                    "rollback_rate_reduction": -1.0,
                    "avg_metric_delta_lift": {"SHIFT": -0.3333},
                    "verdict": "treatment_regressed_on_measured_metrics",
                },
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-smol-promotion-gate",
        "--dev-effectiveness-report",
        str(dev_report),
        "--canary-effectiveness-report",
        str(canary_report),
        "--output-dir",
        str(tmp_path / "promotion-gate"),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "blocked_on_canary_confirmation"
    assert payload["canary_gate"]["passed"] is False
    assert Path(payload["gate_path"]).exists()


def test_proposal_build_smol_canary_failure_slice_audit_cli_writes_report(
    tmp_path,
    capsys,
):
    canary_report = tmp_path / "canary-effectiveness.json"
    promotion_gate = tmp_path / "promotion-gate.json"
    control_outcomes = tmp_path / "control-outcomes.jsonl"
    treatment_outcomes = tmp_path / "treatment-outcomes.jsonl"
    canary_report.write_text(
        json.dumps(
            {
                "comparison": {
                    "proposal_accept_rate_lift": 0.0,
                    "rollback_rate_reduction": -1.0,
                    "avg_metric_delta_lift": {
                        "I": -0.5556,
                        "SHIFT": -0.3333,
                    },
                    "verdict": "treatment_regressed_on_measured_metrics",
                },
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    promotion_gate.write_text(
        json.dumps(
            {
                "status": "blocked_on_canary_confirmation",
                "canary_gate": {
                    "blockers": [
                        "proposal_accept_rate_not_positive",
                        "rollback_rate_worsened",
                    ]
                },
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    control_outcomes.write_text(
        json.dumps(
            {
                "outcome_id": "control-1",
                "failure_labels": ["no_improvement"],
                "rollback_reasons": [],
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    treatment_outcomes.write_text(
        json.dumps(
            {
                "outcome_id": "treatment-1",
                "failure_labels": ["canary_not_confirmed", "no_improvement"],
                "rollback_reasons": ["canary_not_confirmed"],
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-smol-canary-failure-slice-audit",
        "--canary-effectiveness-report",
        str(canary_report),
        "--promotion-gate",
        str(promotion_gate),
        "--control-outcomes",
        str(control_outcomes),
        "--treatment-outcomes",
        str(treatment_outcomes),
        "--output-dir",
        str(tmp_path / "canary-failure-slice-audit"),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "failure_slice_control_arm_required"
    assert payload["failure_slice_label"] == "canary_not_confirmed"
    assert Path(payload["audit_path"]).exists()


def test_proposal_build_smol_canary_control_arm_handoff_cli_writes_report(
    tmp_path,
    capsys,
):
    failure_slice_audit = tmp_path / "failure-slice-audit.json"
    failure_slice_audit.write_text(
        json.dumps(
            {
                "status": "failure_slice_control_arm_required",
                "gate_status": "blocked_on_canary_confirmation",
                "failure_slice_label": "canary_not_confirmed",
                "canary_gate_blockers": [
                    "proposal_accept_rate_not_positive",
                    "rollback_rate_worsened",
                ],
                "control_arm_spec": {
                    "task_family": "smol_worldcup_prompt_routing",
                    "evaluation_split": "canary",
                    "failure_slice_label": "canary_not_confirmed",
                    "baseline_requirement": "matched_canary_negative_control",
                    "comparison_requirement": "same_metric_family_and_split",
                    "success_criteria": [
                        "proposal_accept_rate_lift_gt_0",
                        "rollback_rate_reduction_gte_0",
                    ],
                    "promotion_rule": "do_not_promote_until_failure_slice_control_arm_passes",
                },
                "recommended_next_action": "add_failure_slice_specific_control_arm",
                "audit_path": "docs/evidence/smol-worldcup-qwen3-canary-failure-slice-audit/smol-worldcup-canary-failure-slice-audit.json",
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-smol-canary-control-arm-handoff",
        "--failure-slice-audit",
        str(failure_slice_audit),
        "--output-dir",
        str(tmp_path / "control-arm-handoff"),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "ready_for_client_review"
    assert payload["proposal_template"]["based_on_failures"] == ["canary_not_confirmed"]
    assert payload["proposal_template"]["change_surface"] == "prompt_profile"
    assert Path(payload["handoff_path"]).exists()


def test_proposal_build_smol_canary_control_arm_execution_bundle_cli_writes_report(
    tmp_path,
    capsys,
):
    handoff = tmp_path / "control-arm-handoff.json"
    handoff.write_text(
        json.dumps(
            {
                "status": "ready_for_client_review",
                "failure_slice_label": "canary_not_confirmed",
                "control_outcome_ids": [
                    "qwen3-8b-canary-round-002-dev-v2-20260521-failure-driven-routing-control"
                ],
                "proposal_template": {
                    "proposal_id": "smol-worldcup-canary-control-arm-canary-not-confirmed",
                    "hypothesis": "Run matched canary control arm.",
                    "evidence_used": [
                        {"artifact": "slice-audit", "observation": "canary blocked"}
                    ],
                    "change_surface": "prompt_profile",
                    "change_spec": {"single_primary_variable": True},
                    "expected_effect": {
                        "primary_metric": "SHIFT",
                        "expected_direction": "maximize",
                    },
                    "validation_plan": {
                        "first_split": "canary",
                        "promotion_split": "canary",
                        "rollback_if": ["canary_delta_lt_0"],
                    },
                    "risk_assessment": {"primary": "confounded if not matched"},
                    "next_if_success": "rebuild_gate",
                    "next_if_failure": "keep_blocked",
                    "claim_boundary": "local only",
                    "official_scores_claimed": False,
                },
                "validation_result": {"status": "accepted", "failure_labels": []},
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    current_report = tmp_path / "current-report.json"
    current_report.write_text(
        json.dumps({"metrics": {"SHIFT": 70.0, "H": 70.0, "I": 70.0}}) + "\n",
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-smol-canary-control-arm-execution-bundle",
        "--handoff",
        str(handoff),
        "--current-report",
        str(current_report),
        "--output-dir",
        str(tmp_path / "execution-bundle"),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "ready_for_guarded_execution"
    assert payload["target_prompt_profile"] == "p3-dev-v2"
    assert payload["runtime_config"]["model"] == "qwen/qwen3-8b"
    assert Path(payload["proposal_path"]).exists()


def test_proposal_build_smol_canary_control_arm_execution_bundle_cli_resolves_current_report(
    tmp_path,
    capsys,
):
    handoff = tmp_path / "control-arm-handoff.json"
    handoff.write_text(
        json.dumps(
            {
                "status": "ready_for_client_review",
                "failure_slice_label": "canary_not_confirmed",
                "control_outcome_ids": [
                    "qwen3-8b-canary-round-002-dev-v2-20260521-failure-driven-routing-control"
                ],
                "proposal_template": {
                    "proposal_id": "smol-worldcup-canary-control-arm-canary-not-confirmed",
                    "hypothesis": "Run matched canary control arm.",
                    "evidence_used": [
                        {"artifact": "slice-audit", "observation": "canary blocked"}
                    ],
                    "change_surface": "prompt_profile",
                    "change_spec": {"single_primary_variable": True},
                    "expected_effect": {
                        "primary_metric": "SHIFT",
                        "expected_direction": "maximize",
                    },
                    "validation_plan": {
                        "first_split": "canary",
                        "promotion_split": "canary",
                        "rollback_if": ["canary_delta_lt_0"],
                    },
                    "risk_assessment": {"primary": "confounded if not matched"},
                    "next_if_success": "rebuild_gate",
                    "next_if_failure": "keep_blocked",
                    "claim_boundary": "local only",
                    "official_scores_claimed": False,
                },
                "validation_result": {"status": "accepted", "failure_labels": []},
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    evidence_root = tmp_path / "evidence-root"
    source_report = (
        evidence_root
        / "proof-archives"
        / "smol-worldcup-round-004-canary-formal-rescore-20260520"
        / "artifacts"
        / "source-artifacts"
        / "source-model-eval-report.json"
    )
    source_report.parent.mkdir(parents=True, exist_ok=True)
    source_report.write_text(
        json.dumps(
            {
                "model": {
                    "id": "qwen/qwen3-8b",
                    "prompt_profile": "p3-dev-v2",
                    "provider": "openai-compatible",
                    "base_url": "http://127.0.0.1:1234/v1",
                    "judge_mode": "openai-compatible",
                    "judge_model": "openai/gpt-oss-20b",
                    "judge_base_url": "http://127.0.0.1:1234/v1",
                    "estimated_size_billion": 8.0,
                    "estimated_ram_gb": 16.0,
                },
                "dataset": {"evaluation_split": "canary"},
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-smol-canary-control-arm-execution-bundle",
        "--handoff",
        str(handoff),
        "--evidence-root",
        str(evidence_root),
        "--output-dir",
        str(tmp_path / "execution-bundle"),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["current_report_resolution"]["status"] == "resolved_from_evidence"
    assert payload["current_report_resolution"]["path"] == str(source_report.resolve())
    assert payload["runtime_config"]["model"] == "qwen/qwen3-8b"


def test_proposal_build_smol_promotion_gate_refresh_cli_writes_report(
    tmp_path,
    capsys,
):
    previous_gate = tmp_path / "previous-gate.json"
    previous_gate.write_text(
        json.dumps(
            {
                "status": "blocked_on_canary_confirmation",
                "dev_gate": {"passed": True, "official_scores_claimed": False},
                "canary_gate": {"passed": False, "official_scores_claimed": False},
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    proposal_round_summary = tmp_path / "proposal-round-summary.json"
    proposal_round_summary.write_text(
        json.dumps(
            {
                "status": "completed",
                "validation_status": "accepted",
                "selected_prompt_profile": "p3-dev-v2",
                "evaluation_split": "canary",
                "evaluation": {
                    "canary_delta": {"SHIFT": 0.5, "I": 0.2},
                    "rollback_reasons": [],
                    "promotion_gate_passed": True,
                },
                "reflection_status": "needs_promotion_evidence",
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-smol-promotion-gate-refresh",
        "--previous-gate",
        str(previous_gate),
        "--proposal-round-summary",
        str(proposal_round_summary),
        "--output-dir",
        str(tmp_path / "promotion-gate-refresh"),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "ready_for_prompt_profile_promotion"
    assert payload["promotion_ready"] is True
    assert Path(payload["refresh_path"]).exists()


def test_proposal_build_real_paper_effectiveness_bundle_cli_writes_report(
    tmp_path,
    capsys,
):
    memflow_archive = tmp_path / "memflow-proof-archive.json"
    adam_archive = tmp_path / "adam-proof-archive.json"
    memflow_archive.write_text(
        json.dumps(
            {
                "status": "archivable",
                "benchmark_name": "real_paper_pilot",
                "description": "MemFlow bounded public-slice proof",
                "metric_summary": {
                    "metric_name": "selection_accuracy",
                    "metric_before": 0.25,
                    "metric_after": 1.0,
                    "delta": 0.75,
                    "method_family": "routing",
                },
                "review_status": "approved_with_limitations",
                "claim_boundary": "local public-slice proof only",
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    adam_archive.write_text(
        json.dumps(
            {
                "status": "archivable",
                "benchmark_name": "real_paper_pilot",
                "description": "Adam bounded public-slice proof",
                "metric_summary": {
                    "metric_name": "optimizer_progress_score",
                    "metric_before": 0.422823,
                    "metric_after": 0.881488,
                    "delta": 0.458665,
                    "method_family": "optimizer",
                },
                "review_status": "approved_with_limitations",
                "claim_boundary": "local public-slice proof only",
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-real-paper-effectiveness-bundle",
        "--proof-archive",
        str(memflow_archive),
        "--proof-archive",
        str(adam_archive),
        "--output-dir",
        str(tmp_path / "bundle"),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["comparison"]["proposal_accept_rate_lift"] == 1.0
    assert payload["comparison"]["verdict"] == "treatment_improved_on_measured_metrics"
    assert Path(payload["effectiveness_report_path"]).exists()


def test_proposal_build_mixed_signal_audit_cli_writes_report(tmp_path, capsys):
    fasttext_report = tmp_path / "fasttext-effectiveness.json"
    smol_worldcup_report = tmp_path / "smol-worldcup-effectiveness.json"
    fasttext_report.write_text(
        json.dumps(
            {
                "comparison": {
                    "proposal_accept_rate_lift": 0.5,
                    "rollback_rate_reduction": -0.5,
                    "failure_repeat_rate_reduction": 0.5,
                    "avg_metric_delta_lift": {"p_at_1": 0.001},
                    "verdict": "mixed_signal",
                },
                "treatment_summary": {
                    "outcome_count": 2,
                    "best_outcome_id": "p5-wordngrams-2-treatment",
                },
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    smol_worldcup_report.write_text(
        json.dumps(
            {
                "comparison": {
                    "proposal_accept_rate_lift": 0.5,
                    "rollback_rate_reduction": -0.5,
                    "failure_repeat_rate_reduction": 0.0,
                    "avg_metric_delta_lift": {
                        "SHIFT": 0.3035,
                        "I": 0.5059,
                        "WCS_local_diagnostic": 0.1654,
                    },
                    "verdict": "mixed_signal",
                },
                "treatment_summary": {
                    "outcome_count": 2,
                    "best_outcome_id": "qwen3-8b-dev-round-004-semantic-v2-20260521-treatment",
                },
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-mixed-signal-audit",
        "--effectiveness-report",
        str(fasttext_report),
        "--effectiveness-report",
        str(smol_worldcup_report),
        "--output-dir",
        str(tmp_path / "mixed-signal-audit"),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["mixed_signal_task_count"] == 2
    assert payload["aggregate"]["blocking_signal_counts"]["rollback_rate_worsened"] == 2
    assert Path(payload["audit_path"]).exists()


def test_proposal_generate_drafts_cli_writes_report(tmp_path, capsys):
    context = tmp_path / "failure-context.json"
    context.write_text(
        json.dumps(
            {
                "status": "ready_for_failure_driven_proposals",
                "schema_version": "2026-06-02.failure-driven-context.v1",
                "objective": "Preserve local gain on canary.",
                "max_proposals": 1,
                "failure_summary": {
                    "record_count": 1,
                    "records": [
                        {
                            "failure_id": "f1",
                            "failure_type": "canary_not_confirmed",
                            "severity": "medium",
                            "scope": "single routing block",
                            "official_scores_claimed": False,
                        }
                    ],
                },
                "pattern_summary": {
                    "pattern_count": 1,
                    "matched_patterns": [
                        {
                            "pattern_id": "failure_fix::canary_not_confirmed",
                            "proposal_type": "failure_fix",
                            "applicable_when": ["canary_not_confirmed"],
                            "historical_success_rate": 0.8,
                            "official_scores_claimed": False,
                        }
                    ],
                },
                "prompt_markdown": "failure-driven prompt",
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "generate-proposals",
        "--context",
        str(context),
        "--output",
        str(tmp_path / "generated-proposals.json"),
        "--preferred-change-surface",
        "routing",
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["proposal_count"] == 1
    assert payload["proposals"][0]["change_surface"] == "routing"


def test_proposal_retrieve_patterns_cli_filters_matches(tmp_path, capsys):
    pattern_memory = tmp_path / "proposal-pattern-memory.jsonl"
    pattern_memory.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema_version": "2026-06-02.proposal-pattern-memory.v1",
                        "pattern_id": "failure_fix::canary_not_confirmed",
                        "pattern_summary": "canary fix",
                        "proposal_type": "failure_fix",
                        "applicable_when": ["canary_not_confirmed"],
                        "task_family": "smol_worldcup",
                        "metric_names": ["canary", "dev"],
                        "historical_success_rate": 0.8,
                        "historical_failure_rate": 0.2,
                        "claim_boundary": "local only",
                        "official_scores_claimed": False,
                    }
                ),
                json.dumps(
                    {
                        "schema_version": "2026-06-02.proposal-pattern-memory.v1",
                        "pattern_id": "strategy_shift::no_improvement",
                        "pattern_summary": "strategy shift",
                        "proposal_type": "strategy_shift",
                        "applicable_when": ["no_improvement"],
                        "task_family": "smol_worldcup",
                        "metric_names": ["dev"],
                        "historical_success_rate": 0.4,
                        "historical_failure_rate": 0.6,
                        "claim_boundary": "local only",
                        "official_scores_claimed": False,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "retrieve-patterns",
        "--pattern-memory",
        str(pattern_memory),
        "--failure-type",
        "canary_not_confirmed",
        "--metric-name",
        "canary",
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["match_count"] == 1
    assert payload["matches"][0]["pattern"]["pattern_id"] == "failure_fix::canary_not_confirmed"


def test_proposal_build_cp_bench_effectiveness_bundle_cli_writes_report(tmp_path, capsys):
    round_report = tmp_path / "cp-bench-candidate-round-report.json"
    round_report.write_text(
        json.dumps(
            {
                "status": "improved",
                "target_id": "cp-bench-constraint-modeling",
                "proposal": {
                    "proposal_id": "cp-bench-p15-client-solver-expansion",
                    "change_type": "code_patch",
                },
                "before_summary": {
                    "submitted_models": 21,
                    "coverage_percent": 33.33,
                    "consistency_percent": 0.0,
                    "final_solution_accuracy_percent": 0.0,
                },
                "after_summary": {
                    "submitted_models": 21,
                    "coverage_percent": 33.33,
                    "consistency_percent": 31.75,
                    "final_solution_accuracy_percent": 31.75,
                },
                "failure_summary": {
                    "by_failure_type": {
                        "consistency_or_objective_failed": 1,
                    }
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-cp-bench-effectiveness-bundle",
        "--round-report",
        str(round_report),
        "--output-dir",
        str(tmp_path / "bundle"),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["treatment_outcome_count"] == 1
    assert payload["comparison"]["proposal_accept_rate_lift"] == 1.0


def test_proposal_build_fasttext_effectiveness_bundle_cli_writes_report(tmp_path, capsys):
    multi_round_report = tmp_path / "multi-round-report.json"
    multi_round_report.write_text(
        json.dumps(
            {
                "status": "completed_with_failures",
                "stage": "p5_fasttext_multi_proposal_loop",
                "rounds": [
                    {
                        "round_index": 1,
                        "proposal_id": "p5-wordngrams-2",
                        "status": "completed",
                        "delta_vs_baseline": 0.002,
                        "improved_best": True,
                        "rollback_action": "promote_to_best",
                        "official_scores_claimed": False,
                    },
                    {
                        "round_index": 2,
                        "proposal_id": "p5-invalid-bucket",
                        "status": "failed",
                        "error": "unsupported fastText patch arg '-bucket'",
                        "rollback_action": "keep_best_so_far",
                        "official_scores_claimed": False,
                    },
                ],
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-fasttext-effectiveness-bundle",
        "--multi-round-report",
        str(multi_round_report),
        "--output-dir",
        str(tmp_path / "bundle"),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["treatment_outcome_count"] == 2
    assert payload["comparison"]["proposal_accept_rate_lift"] == 0.5


def test_proposal_build_fasttext_effectiveness_bundle_cli_completed_only(
    tmp_path,
    capsys,
):
    multi_round_report = tmp_path / "multi-round-report.json"
    multi_round_report.write_text(
        json.dumps(
            {
                "status": "completed_with_failures",
                "rounds": [
                    {
                        "proposal_id": "p5-wordngrams-2",
                        "status": "completed",
                        "delta_vs_baseline": 0.002,
                        "improved_best": True,
                        "rollback_action": "promote_to_best",
                        "official_scores_claimed": False,
                    },
                    {
                        "proposal_id": "p5-invalid-bucket",
                        "status": "failed",
                        "error": "unsupported fastText patch arg '-bucket'",
                        "rollback_action": "keep_best_so_far",
                        "official_scores_claimed": False,
                    },
                ],
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-fasttext-effectiveness-bundle",
        "--multi-round-report",
        str(multi_round_report),
        "--completed-only",
        "--output-dir",
        str(tmp_path / "bundle"),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["include_failed_rounds"] is False
    assert payload["treatment_outcome_count"] == 1
    assert payload["comparison"]["proposal_accept_rate_lift"] == 1.0


def test_proposal_build_cross_task_effectiveness_summary_cli_writes_report(
    tmp_path,
    capsys,
):
    cp_bench_report = tmp_path / "cp-bench-effectiveness.json"
    fasttext_report = tmp_path / "fasttext-effectiveness.json"
    cp_bench_report.write_text(
        json.dumps(
            {
                "comparison": {
                    "proposal_accept_rate_lift": 1.0,
                    "rollback_rate_reduction": 0.0,
                    "failure_repeat_rate_reduction": 0.8,
                    "avg_metric_delta_lift": {
                        "final_solution_accuracy_percent": 30.794,
                    },
                    "verdict": "treatment_improved_on_measured_metrics",
                },
                "control_summary": {"outcome_count": 5},
                "treatment_summary": {
                    "outcome_count": 5,
                    "best_outcome_id": "cp-bench-p17-treatment",
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    fasttext_report.write_text(
        json.dumps(
            {
                "comparison": {
                    "proposal_accept_rate_lift": 0.5,
                    "rollback_rate_reduction": -0.5,
                    "failure_repeat_rate_reduction": 0.5,
                    "avg_metric_delta_lift": {
                        "p_at_1": 0.001,
                    },
                    "verdict": "mixed_signal",
                },
                "control_summary": {"outcome_count": 2},
                "treatment_summary": {
                    "outcome_count": 2,
                    "best_outcome_id": "p5-wordngrams-2-treatment",
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    exit_code = main([
        "proposal",
        "build-cross-task-effectiveness-summary",
        "--effectiveness-report",
        str(cp_bench_report),
        "--effectiveness-report",
        str(fasttext_report),
        "--output-dir",
        str(tmp_path / "cross-task-summary"),
        "--json",
    ])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["task_count"] == 2
    assert payload["aggregate"]["verdict_counts"]["mixed_signal"] == 1


def test_init_mcp_config_prints_codex_config(tmp_path, capsys):
    project_root = tmp_path / "ml-research-loop"
    site_packages = project_root / ".venv" / "lib" / "python3.11" / "site-packages"
    site_packages.mkdir(parents=True)

    exit_code = main([
        "init-mcp-config",
        "--client",
        "codex",
        "--project-root",
        str(project_root),
        "--python",
        "/opt/python/bin/python3",
    ])

    text = capsys.readouterr().out
    assert exit_code == 0
    assert "[mcp_servers.mlResearchLoop]" in text
    assert 'command = "/opt/python/bin/python3"' in text
    assert f'args = ["{project_root / "scripts" / "mcp_server.py"}"]' in text
    assert f'cwd = "{project_root}"' in text
    assert f"PYTHONPATH = \"{project_root}:{site_packages}\"" in text
    assert 'ML_RESEARCH_LOOP_PYTHON = "/opt/python/bin/python3"' in text


def test_init_mcp_config_writes_claude_code_json(tmp_path):
    project_root = tmp_path / "ml-research-loop"
    project_root.mkdir()
    output = tmp_path / "claude-code.json"

    exit_code = main([
        "init-mcp-config",
        "--client",
        "claude-code",
        "--project-root",
        str(project_root),
        "--python",
        "/opt/python/bin/python3",
        "--output",
        str(output),
    ])

    assert exit_code == 0
    payload = json.loads(output.read_text(encoding="utf-8"))
    server = payload["mcpServers"]["ml-research-loop"]
    assert server["type"] == "stdio"
    assert server["command"] == "/opt/python/bin/python3"
    assert server["args"] == [str(project_root / "scripts" / "mcp_server.py")]
    assert server["env"]["PYTHONPATH"] == str(project_root)
    assert server["env"]["ML_RESEARCH_LOOP_PYTHON"] == "/opt/python/bin/python3"


def test_init_mcp_config_refuses_to_overwrite_without_force(tmp_path):
    project_root = tmp_path / "ml-research-loop"
    project_root.mkdir()
    output = tmp_path / "codex.toml"
    output.write_text("existing", encoding="utf-8")

    exit_code = main([
        "init-mcp-config",
        "--client",
        "codex",
        "--project-root",
        str(project_root),
        "--output",
        str(output),
    ])

    assert exit_code == 1
    assert output.read_text(encoding="utf-8") == "existing"


def test_init_skills_copies_repo_skills_to_target_root(tmp_path, capsys):
    target_root = tmp_path / "codex-skills"

    exit_code = main([
        "init-skills",
        "--client",
        "codex",
        "--target-root",
        str(target_root),
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "installed"
    assert payload["client"] == "codex"
    assert payload["target_root"] == str(target_root.resolve())
    assert [item["name"] for item in payload["skills"]] == SKILL_NAMES
    for name in SKILL_NAMES:
        assert (target_root / name / "SKILL.md").exists()


def test_init_skills_refuses_to_overwrite_without_force(tmp_path, capsys):
    target_root = tmp_path / "claude-skills"
    existing_skill = target_root / "ml-research-loop-planner"
    existing_skill.mkdir(parents=True)
    existing_file = existing_skill / "SKILL.md"
    existing_file.write_text("custom", encoding="utf-8")

    exit_code = main([
        "init-skills",
        "--client",
        "claude",
        "--target-root",
        str(target_root),
    ])

    captured = capsys.readouterr()
    assert exit_code == 1
    assert "Refusing to overwrite existing skill" in captured.err
    assert existing_file.read_text(encoding="utf-8") == "custom"


def test_init_skills_force_overwrites_existing_skill(tmp_path, capsys):
    target_root = tmp_path / "codex-skills"
    existing_skill = target_root / "ml-research-loop-planner"
    existing_skill.mkdir(parents=True)
    (existing_skill / "SKILL.md").write_text("custom", encoding="utf-8")

    exit_code = main([
        "init-skills",
        "--client",
        "codex",
        "--target-root",
        str(target_root),
        "--force",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "installed"
    assert (
        target_root / "ml-research-loop-planner" / "SKILL.md"
    ).read_text(encoding="utf-8").startswith("---\n")


def test_init_skills_dry_run_reports_default_target_root(monkeypatch, capsys):
    monkeypatch.setattr(Path, "home", lambda: Path("/Users/tester"))

    codex_exit = main(["init-skills", "--client", "codex", "--dry-run"])
    codex_payload = json.loads(capsys.readouterr().out)
    claude_exit = main(["init-skills", "--client", "claude", "--dry-run"])
    claude_payload = json.loads(capsys.readouterr().out)

    assert codex_exit == 0
    assert claude_exit == 0
    assert codex_payload["target_root"] == "/Users/tester/.codex/skills"
    assert claude_payload["target_root"] == "/Users/tester/.claude/skills"


def test_feedback_bundle_command_prints_output_paths(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        "scripts.cli.build_feedback_bundle",
        lambda **kwargs: {
            "bundle_version": "test",
            "runtime": {"runtime_root": str(kwargs["runtime_root"])},
        },
    )
    monkeypatch.setattr(
        "scripts.cli.write_feedback_bundle",
        lambda bundle, output_dir: {
            "status": "written",
            "json_path": str(output_dir / "feedback-bundle.json"),
            "markdown_path": str(output_dir / "feedback-bundle.md"),
            "bundle": bundle,
        },
    )

    exit_code = main([
        "feedback-bundle",
        "--runtime-root",
        str(tmp_path / "runtime"),
        "--output-dir",
        str(tmp_path / "bundle"),
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "written"
    assert payload["bundle"]["runtime"]["runtime_root"] == str(tmp_path / "runtime")


def test_benchmark_readiness_command_prints_manifest_payload(monkeypatch, capsys):
    monkeypatch.setattr(
        "scripts.cli.build_benchmark_readiness",
        lambda: {"status": "compatibility_ready", "adapters": []},
    )

    exit_code = main(["benchmark", "readiness", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload == {"status": "compatibility_ready", "adapters": []}


def test_benchmark_smoke_command_invokes_smoke_script(monkeypatch, tmp_path):
    captured = {}

    def fake_call(cmd, cwd=None):
        captured["cmd"] = cmd
        captured["cwd"] = cwd
        return 0

    monkeypatch.setattr("scripts.cli.subprocess.call", fake_call)

    exit_code = main([
        "benchmark",
        "smoke",
        "--runtime-root",
        str(tmp_path / "runtime"),
        "--python",
        "/opt/python/bin/python3",
        "--json",
    ])

    assert exit_code == 0
    assert captured["cmd"][0] == "/opt/python/bin/python3"
    assert captured["cmd"][1].endswith("scripts/benchmark_adapter_smoke.py")
    assert captured["cmd"][2:] == [
        "--runtime-root",
        str(tmp_path / "runtime"),
        "--json",
    ]


def test_benchmark_probe_command_prints_harness_probe(monkeypatch, capsys):
    monkeypatch.setattr(
        "scripts.cli.build_official_harness_probe",
        lambda **kwargs: {"status": "needs_setup", "read_only": True},
    )

    exit_code = main(["benchmark", "probe", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload == {"status": "needs_setup", "read_only": True}


def test_benchmark_proof_plan_command_prints_plan(monkeypatch, capsys):
    monkeypatch.setattr(
        "scripts.cli.build_official_harness_probe",
        lambda **kwargs: {"status": "needs_setup", "read_only": True},
    )
    monkeypatch.setattr(
        "scripts.cli.build_public_proof_plan",
        lambda probe: {"status": "blocked", "harness_probe": probe},
    )

    exit_code = main(["benchmark", "proof-plan", "--json"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload == {
        "status": "blocked",
        "harness_probe": {"status": "needs_setup", "read_only": True},
    }


def test_benchmark_setup_bundle_command_writes_bundle(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        "scripts.cli.build_official_harness_probe",
        lambda **kwargs: {"status": "needs_setup", "read_only": True},
    )
    monkeypatch.setattr(
        "scripts.cli.build_public_proof_plan",
        lambda probe: {"status": "blocked", "harness_probe": probe},
    )
    monkeypatch.setattr(
        "scripts.cli.build_official_proof_setup_bundle",
        lambda proof_plan: {"read_only": True, "proof_plan": proof_plan},
    )
    monkeypatch.setattr(
        "scripts.cli.write_official_proof_setup_bundle",
        lambda bundle, output_dir: {
            "status": "written",
            "json_path": str(output_dir / "official-proof-setup.json"),
        },
    )

    exit_code = main([
        "benchmark",
        "setup-bundle",
        "--output-dir",
        str(tmp_path / "proof-setup"),
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "written"
    assert payload["json_path"].endswith("official-proof-setup.json")


def test_benchmark_publication_bundle_command_writes_bundle(monkeypatch, tmp_path, capsys):
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"benchmark_name": "mle_bench"}', encoding="utf-8")
    monkeypatch.setattr(
        "scripts.cli.build_proof_publication_bundle",
        lambda artifact_manifest, artifact_root: {
            "read_only": True,
            "artifact_root": str(artifact_root),
            "artifact_manifest": artifact_manifest,
        },
    )
    monkeypatch.setattr(
        "scripts.cli.write_proof_publication_bundle",
        lambda bundle, output_dir: {
            "status": "written",
            "json_path": str(output_dir / "proof-publication.json"),
        },
    )

    exit_code = main([
        "benchmark",
        "publication-bundle",
        "--manifest",
        str(manifest),
        "--artifact-root",
        str(tmp_path / "artifacts"),
        "--output-dir",
        str(tmp_path / "publication"),
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "written"
    assert payload["json_path"].endswith("proof-publication.json")


def test_benchmark_archive_proof_command_writes_archive(monkeypatch, tmp_path, capsys):
    manifest = tmp_path / "manifest.json"
    manifest.write_text('{"benchmark_name": "mle_bench"}', encoding="utf-8")
    monkeypatch.setattr(
        "scripts.cli.build_proof_archive_bundle",
        lambda artifact_manifest, artifact_root: {
            "status": "archivable",
            "artifact_root": str(artifact_root),
            "artifact_manifest": artifact_manifest,
        },
    )
    monkeypatch.setattr(
        "scripts.cli.write_proof_archive_bundle",
        lambda bundle, artifact_root, output_dir: {
            "status": "written",
            "json_path": str(output_dir / "proof-archive.json"),
        },
    )

    exit_code = main([
        "benchmark",
        "archive-proof",
        "--manifest",
        str(manifest),
        "--artifact-root",
        str(tmp_path / "artifacts"),
        "--output-dir",
        str(tmp_path / "archive"),
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "written"
    assert payload["json_path"].endswith("proof-archive.json")


def test_benchmark_mle_workspace_command_writes_agent_workspace(
    monkeypatch,
    tmp_path,
    capsys,
):
    monkeypatch.setattr(
        "scripts.cli.materialize_official_mle_agent_workspace",
        lambda **kwargs: {
            "status": "ready_for_agent",
            "competition_id": kwargs["competition_id"],
            "workspace": str(kwargs["runtime_root"] / "benchmark-workspaces"),
        },
    )

    exit_code = main([
        "benchmark",
        "mle-workspace",
        "--competition-id",
        "spooky-author-identification",
        "--prepared-competition-dir",
        str(tmp_path / "mlebench-data" / "spooky-author-identification"),
        "--runtime-root",
        str(tmp_path / "runtime"),
        "--workspace-name",
        "spooky-debug",
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "ready_for_agent"
    assert payload["competition_id"] == "spooky-author-identification"


def test_benchmark_mle_grade_command_runs_official_grade_sample(
    monkeypatch,
    tmp_path,
    capsys,
):
    monkeypatch.setattr(
        "scripts.cli.grade_official_mle_submission",
        lambda **kwargs: {
            "status": "graded",
            "competition_id": kwargs["competition_id"],
            "report": {"score": 1.23},
            "official_scores_claimed": False,
        },
    )

    exit_code = main([
        "benchmark",
        "mle-grade",
        "--competition-id",
        "spooky-author-identification",
        "--submission",
        str(tmp_path / "workspace" / "submission.csv"),
        "--data-dir",
        str(tmp_path / "mlebench-data"),
        "--mlebench",
        str(tmp_path / "venv" / "bin" / "mlebench"),
        "--output-dir",
        str(tmp_path / "reports"),
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "graded"
    assert payload["official_scores_claimed"] is False


def test_benchmark_mle_round_command_runs_solver_and_grade(
    monkeypatch,
    tmp_path,
    capsys,
):
    monkeypatch.setattr(
        "scripts.cli.run_official_mle_solver_round",
        lambda **kwargs: {
            "status": "graded",
            "competition_id": kwargs["competition_id"],
            "workspace": str(kwargs["workspace"]),
            "round_id": kwargs["round_id"],
            "grade": {"report": {"score": 1.23}},
            "official_scores_claimed": False,
        },
        raising=False,
    )

    exit_code = main([
        "benchmark",
        "mle-round",
        "--competition-id",
        "spooky-author-identification",
        "--workspace",
        str(tmp_path / "workspace"),
        "--data-dir",
        str(tmp_path / "mlebench-data"),
        "--mlebench",
        str(tmp_path / "venv" / "bin" / "mlebench"),
        "--output-dir",
        str(tmp_path / "rounds"),
        "--python",
        "python3",
        "--round-id",
        "round-001",
        "--timeout-seconds",
        "10",
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "graded"
    assert payload["round_id"] == "round-001"
    assert payload["official_scores_claimed"] is False


def test_benchmark_mle_patch_round_command_applies_patch_then_runs_round(
    monkeypatch,
    tmp_path,
    capsys,
):
    patch_file = tmp_path / "patch.diff"
    patch_file.write_text("--- a/solve.py\n+++ b/solve.py\n@@ -1,1 +1,1 @@\n-old\n+new\n")
    monkeypatch.setattr(
        "scripts.cli.mcp_service.run_official_mle_bench_patch_round_tool",
        lambda arguments: {
            "status": "graded",
            "competition_id": arguments["competition_id"],
            "round_id": arguments["round_id"],
            "patch_execution": {"status": "applied"},
            "round": {"status": "graded"},
            "loop_decision": {"recommended_next_action": "continue"},
            "official_scores_claimed": False,
        },
    )

    exit_code = main([
        "benchmark",
        "mle-patch-round",
        "--competition-id",
        "spooky-author-identification",
        "--workspace",
        str(tmp_path / "workspace"),
        "--data-dir",
        str(tmp_path / "mlebench-data"),
        "--mlebench",
        str(tmp_path / "venv" / "bin" / "mlebench"),
        "--output-dir",
        str(tmp_path / "rounds"),
        "--patch-file",
        str(patch_file),
        "--python",
        "python3",
        "--round-id",
        "round-002",
        "--timeout-seconds",
        "10",
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "graded"
    assert payload["patch_execution"]["status"] == "applied"
    assert payload["round"]["status"] == "graded"
    assert payload["official_scores_claimed"] is False


def test_benchmark_mle_patch_proof_command_writes_bundle(
    monkeypatch,
    tmp_path,
    capsys,
):
    patch_round_report = tmp_path / "patch-round-report.json"
    patch_round_report.write_text('{"status": "graded"}', encoding="utf-8")
    monkeypatch.setattr(
        "scripts.cli.write_official_mle_patch_round_proof_bundle",
        lambda *, patch_round_report, output_dir: {
            "status": "written",
            "patch_round_report": str(patch_round_report),
            "manifest_path": str(output_dir / "manifest.json"),
            "archive": {"bundle": {"status": "archivable"}},
            "official_scores_claimed": False,
        },
    )

    exit_code = main([
        "benchmark",
        "mle-patch-proof",
        "--patch-round-report",
        str(patch_round_report),
        "--output-dir",
        str(tmp_path / "proof"),
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "written"
    assert payload["official_scores_claimed"] is False
    assert payload["archive"]["bundle"]["status"] == "archivable"


def test_benchmark_paperbench_codex_review_bundle_command_writes_bundle(
    monkeypatch,
    tmp_path,
    capsys,
):
    monkeypatch.setattr(
        "scripts.cli.write_paperbench_codex_review_bundle",
        lambda *, run_dir, paper_dir, output_dir: {
            "status": "written",
            "bundle_path": str(output_dir / "codex-review-bundle.json"),
            "prompt_path": str(output_dir / "codex-review-prompt.md"),
            "bundle": {
                "paper_id": paper_dir.name,
                "judge_type": "codex_assisted",
                "official_scores_claimed": False,
                "paperbench_score": None,
                "source_run": str(run_dir),
            },
        },
    )

    exit_code = main([
        "benchmark",
        "paperbench-codex-review-bundle",
        "--run-dir",
        str(tmp_path / "runs" / "rice_123"),
        "--paper-dir",
        str(tmp_path / "papers" / "rice"),
        "--output-dir",
        str(tmp_path / "codex-review"),
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "written"
    assert payload["bundle"]["judge_type"] == "codex_assisted"
    assert payload["bundle"]["official_scores_claimed"] is False
    assert payload["bundle"]["paperbench_score"] is None


def test_benchmark_paperbench_codex_review_report_command_writes_report(
    monkeypatch,
    tmp_path,
    capsys,
):
    review_file = tmp_path / "codex-review.json"
    review_file.write_text(
        json.dumps({"summary": "reviewed", "codex_review_score": 0.5}),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "scripts.cli.write_paperbench_codex_review_report",
        lambda *, bundle_path, review_payload, output_dir: {
            "status": "written",
            "json_path": str(output_dir / "codex-review-report.json"),
            "markdown_path": str(output_dir / "codex-review-report.md"),
            "source_bundle": str(bundle_path),
            "report": {
                "judge_type": "codex_assisted",
                "official_scores_claimed": False,
                "paperbench_score": None,
                "codex_review_score": review_payload["codex_review_score"],
            },
        },
    )

    exit_code = main([
        "benchmark",
        "paperbench-codex-review-report",
        "--bundle",
        str(tmp_path / "codex-review-bundle.json"),
        "--review-file",
        str(review_file),
        "--output-dir",
        str(tmp_path / "codex-review-report"),
        "--json",
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "written"
    assert payload["report"]["codex_review_score"] == 0.5
    assert payload["report"]["official_scores_claimed"] is False
    assert payload["report"]["paperbench_score"] is None


def test_demo_list_command_prints_templates(monkeypatch, capsys):
    monkeypatch.setattr(
        "scripts.cli.list_demo_templates",
        lambda: [{"name": "byte-lm-smoke", "description": "demo"}],
    )

    exit_code = main(["demo", "list"])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["templates"][0]["name"] == "byte-lm-smoke"


def test_demo_init_command_materializes_template(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(
        "scripts.cli.materialize_demo_template",
        lambda **kwargs: {
            "status": "initialized",
            "template": {"name": kwargs["template_name"]},
            "runtime_root": str(kwargs["runtime_root"]),
        },
    )

    exit_code = main([
        "demo",
        "init",
        "--template",
        "byte-lm-smoke",
        "--runtime-root",
        str(tmp_path / "runtime"),
    ])

    payload = json.loads(capsys.readouterr().out)
    assert exit_code == 0
    assert payload["status"] == "initialized"
    assert payload["template"]["name"] == "byte-lm-smoke"


def _optimizer_gate_plugin_manifest_fixture() -> dict:
    return {
        "schema_version": "2026-06-05.optimizer-gate-plugin-manifest.v1",
        "plugin_id": "local-dspy-fixture",
        "optimizer_adapters": [
            {
                "name": "dspy-mipro-local",
                "adapter_type": "deterministic_local",
                "runtime_status": "plugin_manifest_only",
                "provider": "plugin",
                "candidate_surface": "prompt_section",
                "candidate_schema": "2026-06-04.slice-patch-candidate.v1",
                "supports_execute_optimizer": False,
                "executes_tool_default": False,
                "executes_experiment": False,
                "module_scope": "single_module_single_section",
                "capabilities": ["module_section_instruction_search"],
            }
        ],
        "gate_policies": [
            {
                "policy_id": "cost-ceiling-gate",
                "function": "external_cost_ceiling_gate",
                "decision_schema": "2026-06-05.gate-policy-decision.v1",
                "required_inputs": ["gate_input"],
                "blocks_on": ["cost_too_high"],
                "decision_outputs": ["hard_blockers", "canary_allowed"],
                "canary_allowed_when": "hard_blockers is empty",
                "executes_experiment": False,
            }
        ],
        "claim_boundary": "non-executing plugin registry fixture only",
        "official_scores_claimed": False,
    }


def _runtime_optimizer_plugin_manifest_fixture() -> dict:
    return {
        "schema_version": "2026-06-05.optimizer-gate-plugin-manifest.v1",
        "plugin_id": "runtime-textgrad-fixture",
        "optimizer_adapters": [
            {
                "name": "runtime-textgrad-plugin",
                "adapter_type": "openai_compatible_critic",
                "runtime_status": "runtime_plugin_available",
                "provider": "plugin-openai-compatible",
                "candidate_surface": "prompt_section",
                "candidate_schema": "2026-06-04.slice-patch-candidate.v1",
                "supports_execute_optimizer": True,
                "executes_tool_default": False,
                "executes_experiment": False,
                "module_scope": "single_module_single_section",
                "capabilities": [
                    "section_local_patch",
                    "critic_feedback",
                    "structured_json_candidate",
                ],
                "runtime_entrypoint": {
                    "kind": "openai-compatible-chat-completions",
                    "default_model": "qwen/qwen3-8b",
                    "default_base_url": "http://127.0.0.1:1234/v1",
                    "api_key_env": "ML_RESEARCH_LOOP_TEXTGRAD_API_KEY",
                },
            }
        ],
        "gate_policies": [],
        "claim_boundary": "runtime-capable optimizer plugin fixture only",
        "official_scores_claimed": False,
    }


def _subprocess_optimizer_plugin_manifest_fixture(command: list[str]) -> dict:
    return {
        "schema_version": "2026-06-05.optimizer-gate-plugin-manifest.v1",
        "plugin_id": "subprocess-textgrad-fixture",
        "optimizer_adapters": [
            {
                "name": "subprocess-textgrad-plugin",
                "adapter_type": "subprocess_json_optimizer",
                "runtime_status": "runtime_plugin_available",
                "provider": "plugin-subprocess",
                "candidate_surface": "prompt_section",
                "candidate_schema": "2026-06-04.slice-patch-candidate.v1",
                "supports_execute_optimizer": True,
                "executes_tool_default": False,
                "executes_experiment": False,
                "module_scope": "single_module_single_section",
                "capabilities": [
                    "section_local_patch",
                    "subprocess_json_candidate",
                ],
                "runtime_entrypoint": {
                    "kind": "local-subprocess-json",
                    "command": command,
                },
            }
        ],
        "gate_policies": [],
        "claim_boundary": "subprocess optimizer plugin fixture only",
        "official_scores_claimed": False,
    }


def _python_package_optimizer_plugin_manifest_fixture(
    package_import: str,
    candidate_method: str | None = None,
) -> dict:
    runtime_entrypoint = {
        "kind": "python-package",
        "package_import": package_import,
        "adapter_class": "FixtureOptimizerAdapter",
    }
    if candidate_method:
        runtime_entrypoint["candidate_method"] = candidate_method
    return {
        "schema_version": "2026-06-05.optimizer-gate-plugin-manifest.v1",
        "plugin_id": "python-package-optimizer-fixture",
        "optimizer_adapters": [
            {
                "name": "python-package-optimizer-plugin",
                "adapter_type": "python_package_optimizer",
                "runtime_status": "runtime_plugin_available",
                "provider": "plugin-python-package",
                "candidate_surface": "prompt_section",
                "candidate_schema": "2026-06-04.slice-patch-candidate.v1",
                "supports_execute_optimizer": True,
                "executes_tool_default": False,
                "executes_experiment": False,
                "module_scope": "single_module_single_section",
                "capabilities": [
                    "section_local_patch",
                    "package_runtime_probe",
                ],
                "runtime_entrypoint": runtime_entrypoint,
            }
        ],
        "gate_policies": [],
        "claim_boundary": "python package optimizer probe fixture only",
        "official_scores_claimed": False,
    }


def _smol_cli_eval_row(
    *,
    row_id: str,
    category: str,
    auto_grade: str,
    answer_key: dict,
) -> dict:
    return {
        "id": row_id,
        "shift_axis": "I",
        "category": category,
        "subcategory": "unit",
        "difficulty": "standard",
        "prompt": "Respond in JSON format.",
        "answer_key": json.dumps(answer_key),
        "explanation": "unit test",
        "grading_rule": "unit test",
        "auto_grade": auto_grade,
        "max_score": 10,
        "anchor": False,
        "season": 1,
        "version": "1.0",
        "language": "en",
        "language_name": "English",
    }


def test_tournament_cli_lifecycle(tmp_path, capsys):
    baseline_artifact = tmp_path / "baseline-report.json"
    baseline_artifact.write_text('{"metric": {"p_at_1": 0.9}}', encoding="utf-8")
    config_file = tmp_path / "config.json"
    config_file.write_text(json.dumps({
        "k": 2, "initial_rounds_per_arm": 1, "halving": 2, "epsilon": 0.001,
        "metric": "P@1", "direction": "maximize",
        "budgets": {"max_total_rounds": 6, "max_wall_seconds": 3600,
                    "target_value": None},
    }), encoding="utf-8")
    baseline_file = tmp_path / "baseline.json"
    baseline_file.write_text(json.dumps(
        {"value": 0.9, "artifact": str(baseline_artifact)}), encoding="utf-8")
    target_file = tmp_path / "target.json"
    target_file.write_text(json.dumps(
        {"kind": "synthetic", "baseline_value": 0.9,
         "weights": {"a": 0.01, "b": 0.001}}), encoding="utf-8")
    directions_file = tmp_path / "directions.json"
    directions_file.write_text(json.dumps([
        {"arm_id": "a1", "hypothesis": "push a",
         "first_proposal": {"params": {"a": 1}}},
        {"arm_id": "a2", "hypothesis": "push b",
         "first_proposal": {"params": {"b": 1}}},
    ]), encoding="utf-8")
    base = ["tournament"]
    common = ["--runtime-root", str(tmp_path), "--run-id", "cli-run"]

    assert main(base + ["start", *common,
                            "--target-id", "demo",
                            "--config-file", str(config_file),
                            "--baseline-file", str(baseline_file),
                            "--target-file", str(target_file), "--json"]) == 0
    assert main(base + ["submit-directions", *common,
                            "--directions-file", str(directions_file),
                            "--json"]) == 0
    assert main(base + ["step", *common, "--json"]) == 0
    assert main(base + ["status", *common, "--json"]) == 0
    payload = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert payload["ledger"]["total_rounds_used"] == 1
    assert payload["pending_action"]["type"] == "run_round"
