import json
from pathlib import Path

from lib.research_memory import ResearchMemoryCard, ResearchMemoryStore
from scripts.cli import build_parser, main


SKILL_NAMES = [
    "ml-research-loop-planner",
    "ml-research-loop-reproduction",
    "ml-research-loop-experiment-optimizer",
    "ml-research-loop-operator",
]


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
        "--prompt-profile",
        "p3-semantic-v2",
        "--evaluation-split",
        "canary",
        "--judge-mode",
        "openai-compatible",
        "--judge-model",
        "google/gemma-4-31b",
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
    assert hf_eval_smol_leakage_audit_args.evaluation_split == "canary"
    assert hf_eval_smol_model_eval_args.hf_eval_command == "smol-worldcup-model-eval"
    assert str(hf_eval_smol_model_eval_args.output_dir) == "/tmp/hf-smol-p2"
    assert hf_eval_smol_model_eval_args.model == "deepseek-v4-flash"
    assert hf_eval_smol_model_eval_args.model_provider == "deepseek"
    assert hf_eval_smol_model_eval_args.api_key_env == "DEEPSEEK_API_KEY"
    assert hf_eval_smol_model_eval_args.thinking_mode == "enabled"
    assert hf_eval_smol_model_eval_args.reasoning_effort == "high"
    assert hf_eval_smol_model_eval_args.limit == 4
    assert hf_eval_smol_model_eval_args.prompt_profile == "p3-semantic-v2"
    assert hf_eval_smol_model_eval_args.evaluation_split == "canary"
    assert hf_eval_smol_model_eval_args.judge_mode == "openai-compatible"
    assert hf_eval_smol_model_eval_args.judge_model == "google/gemma-4-31b"
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
