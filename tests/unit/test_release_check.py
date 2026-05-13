from __future__ import annotations

import json
from pathlib import Path

from scripts import release_check


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_release_check_builds_make_independent_commands() -> None:
    commands = release_check.build_release_commands(
        python="python3",
        project_root=PROJECT_ROOT,
        skip_golden_path=False,
    )
    labels = [command.label for command in commands]

    assert labels == [
        "ruff",
        "pytest",
        "mcp-stdio-smoke",
        "mcp-client-acceptance",
        "mcp-golden-path",
        "mcp-multi-round",
        "mcp-auto-next",
        "mcp-client-patch",
        "mcp-provider-quality",
        "mcp-real-task-code",
        "benchmark-adapter-smoke",
        "mle-bench-official-bridge",
        "benchmark-harness-probe",
        "research-env-probe",
        "benchmark-proof-plan",
        "benchmark-proof-setup",
        "benchmark-proof-publication",
        "benchmark-proof-archive",
        "mcp-real-data",
        "mcp-reproduction",
        "autonomous-research-demo",
        "real-paper-pilot-baseline",
        "real-paper-pilot-iteration",
        "real-paper-pilot-review",
        "real-paper-pilot-archive",
        "real-paper-pilot-adam-baseline",
        "real-paper-pilot-adam-iteration",
        "real-paper-pilot-adam-review",
        "real-paper-pilot-adam-archive",
        "full-reproduction-target",
        "full-reproduction-harness-baseline",
        "full-reproduction-baseline-alignment",
        "full-reproduction-full-data-alignment",
        "full-reproduction-fasttext-binary-baseline",
        "full-reproduction-fasttext-patch-round",
        "full-reproduction-fasttext-patch-proof-bundle",
    ]
    assert all(command.argv[0] == "python3" or command.argv[0].endswith("ruff") for command in commands)
    assert not any("make" in part for command in commands for part in command.argv)


def test_release_check_json_summary_marks_failed_command() -> None:
    result = release_check.CheckResult(
        label="pytest",
        returncode=1,
        duration_seconds=0.12,
        stdout="failed",
    )

    payload = json.loads(release_check.render_summary([result]))

    assert payload["status"] == "failed"
    assert payload["checks"][0]["label"] == "pytest"
    assert payload["checks"][0]["returncode"] == 1


def test_release_env_discovers_python_versioned_site_packages(tmp_path: Path) -> None:
    site_packages = tmp_path / ".venv" / "lib" / "python3.12" / "site-packages"
    site_packages.mkdir(parents=True)

    env = release_check.release_env(tmp_path, "python3")

    assert str(site_packages) in env["PYTHONPATH"].split(":")


def test_release_env_absolutizes_relative_python_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.delenv("ML_RESEARCH_LOOP_PYTHON", raising=False)

    env = release_check.release_env(tmp_path, ".venv/bin/python")

    assert env["ML_RESEARCH_LOOP_PYTHON"] == str((tmp_path / ".venv/bin/python").resolve())


def test_release_check_doc_lists_required_commands() -> None:
    doc = (PROJECT_ROOT / "docs" / "release-checklist.md").read_text(encoding="utf-8")

    assert "python3 scripts/release_check.py" in doc
    assert "scripts/mcp_client_acceptance.py" in doc
    assert "scripts/mcp_golden_path.py" in doc
    assert "scripts/mcp_multi_round_demo.py" in doc
    assert "scripts/mcp_auto_next_demo.py" in doc
    assert "scripts/mcp_client_patch_demo.py" in doc
    assert "scripts/mcp_provider_quality_benchmark.py" in doc
    assert "scripts/mcp_real_task_code_benchmark.py" in doc
    assert "scripts/benchmark_adapter_smoke.py" in doc
    assert "scripts/mle_bench_official_bridge_demo.py" in doc
    assert "scripts/benchmark_harness_probe.py" in doc
    assert "scripts/research_env_probe.py" in doc
    assert "scripts/benchmark_proof_plan.py" in doc
    assert "scripts/benchmark_proof_setup.py" in doc
    assert "scripts/benchmark_proof_publication.py" in doc
    assert "scripts/benchmark_proof_archive.py" in doc
    assert "ml-loop benchmark proof-plan --json" in doc
    assert "ml-loop benchmark setup-bundle" in doc
    assert "ml-loop benchmark publication-bundle" in doc
    assert "ml-loop benchmark archive-proof" in doc
    assert "ml-loop benchmark mle-workspace" in doc
    assert "ml-loop benchmark mle-grade" in doc
    assert "ml-loop benchmark mle-round" in doc
    assert "ml-loop benchmark mle-patch-round" in doc
    assert "ml-loop benchmark mle-patch-proof" in doc
    assert "write_official_mle_bench_patch_round_proof_bundle" in doc
    assert "scripts/mcp_real_data_demo.py" in doc
    assert "scripts/mcp_reproduction_demo.py" in doc
    assert "scripts/autonomous_research_demo.py" in doc
    assert "scripts/real_paper_reproduction_pilot.py" in doc
    assert "scripts/full_reproduction_run.py" in doc
    assert "--align-baseline" in doc
    assert "--align-full-data" in doc
    assert "--run-fasttext-baseline" in doc
    assert "--run-fasttext-patch-round" in doc
    assert "--fasttext-proposal" in doc
    assert "--write-fasttext-patch-proof-bundle" in doc
    assert "--run-baseline --use-public-mini-slice" in doc
    assert "--run-iteration --use-public-mini-slice" in doc
    assert "--write-review-report" in doc
    assert "approved_with_limitations" in doc
    assert "--run-baseline --use-fixture-data" in doc
    assert "--run-iteration --use-fixture-data" in doc
    assert "--archive-proof" in doc
    assert "local_public_data" in doc
    assert "local_substitute_data" in doc
    assert "preview release: real-paper-pilot proof is optional" in doc
    assert "beta release: at least one real-paper-pilot proof archive" in doc
    assert "stable release: substitute-data proof is not enough" in doc
    assert "upstream_patterns.aide.direct_dependency == false" in doc
    assert "upstream_patterns.paperbench.direct_dependency == false" in doc
    assert "invalid_required_files" in doc
    assert "pytest tests/ -q" in doc
    assert "ruff check" in doc
    assert "contract_version" in doc
    assert "tool_contracts" in doc
    assert "compatibility_check.status == compatible" in doc
    assert "execution_metadata.wall_time_seconds" in doc
    assert "execution_sandbox.status == enforced" in doc
    assert "ML_RESEARCH_LOOP_ALLOWED_ROOTS" in doc
    assert "rate_limited" in doc
    assert "proposed_task_patch" in doc
    assert "dry_run_validation" in doc
    assert "run_next_experiment_from_review" in doc
    assert "docs/release-notes.md" in doc
    assert "docs/client-compatibility-matrix.md" in doc
    assert "examples/mcp/README.md" in doc
    assert "beta release gate" in doc
    assert "stable release gate" in doc


def test_github_actions_ci_runs_fast_mcp_gate() -> None:
    workflow = PROJECT_ROOT / ".github" / "workflows" / "ci.yml"

    text = workflow.read_text(encoding="utf-8")

    assert "ruff check" in text
    assert "python -m pytest tests/ -q" in text
    assert "scripts/mcp_client_acceptance.py" in text
