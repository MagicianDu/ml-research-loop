#!/usr/bin/env python3
"""Run release verification without relying on make."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from dataclasses import dataclass
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class ReleaseCommand:
    label: str
    argv: list[str]
    timeout_seconds: int


@dataclass(frozen=True)
class CheckResult:
    label: str
    returncode: int
    duration_seconds: float
    stdout: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run ml-research-loop release checks")
    parser.add_argument("--python", default=sys.executable, help="Python executable to use")
    parser.add_argument("--project-root", type=Path, default=PROJECT_ROOT)
    parser.add_argument("--skip-golden-path", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print only final JSON summary")
    return parser.parse_args()


def build_release_commands(
    python: str,
    project_root: Path,
    skip_golden_path: bool = False,
) -> list[ReleaseCommand]:
    ruff = project_root / ".venv" / "bin" / "ruff"
    ruff_executable = str(ruff) if ruff.exists() else "ruff"
    commands = [
        ReleaseCommand(
            label="ruff",
            argv=[
                ruff_executable,
                "check",
                "lib/",
                "scripts/",
                "ml_intern/",
                "codex_plugin/",
                "tests/",
            ],
            timeout_seconds=120,
        ),
        ReleaseCommand(
            label="pytest",
            argv=[python, "-m", "pytest", "tests/", "-q"],
            timeout_seconds=240,
        ),
        ReleaseCommand(
            label="mcp-stdio-smoke",
            argv=[python, str(project_root / "scripts" / "mcp_server.py")],
            timeout_seconds=15,
        ),
        ReleaseCommand(
            label="mcp-client-acceptance",
            argv=[
                python,
                str(project_root / "scripts" / "mcp_client_acceptance.py"),
                "--python",
                python,
                "--project-root",
                str(project_root),
            ],
            timeout_seconds=30,
        ),
    ]
    if not skip_golden_path:
        runtime_root = project_root / ".demo_runs" / f"release-check-{uuid.uuid4().hex[:8]}"
        multi_round_runtime_root = (
            project_root / ".demo_runs" / f"release-check-multi-{uuid.uuid4().hex[:8]}"
        )
        auto_next_runtime_root = (
            project_root / ".demo_runs" / f"release-check-auto-next-{uuid.uuid4().hex[:8]}"
        )
        client_patch_runtime_root = (
            project_root / ".demo_runs" / f"release-check-client-patch-{uuid.uuid4().hex[:8]}"
        )
        provider_quality_runtime_root = (
            project_root / ".demo_runs" / f"release-check-provider-{uuid.uuid4().hex[:8]}"
        )
        real_task_code_runtime_root = (
            project_root / ".demo_runs" / f"release-check-real-code-{uuid.uuid4().hex[:8]}"
        )
        benchmark_adapter_runtime_root = (
            project_root / ".demo_runs" / f"release-check-benchmark-{uuid.uuid4().hex[:8]}"
        )
        mle_bridge_runtime_root = (
            project_root / ".demo_runs" / f"release-check-mle-bridge-{uuid.uuid4().hex[:8]}"
        )
        benchmark_setup_output_dir = (
            project_root / ".demo_runs" / f"release-check-proof-setup-{uuid.uuid4().hex[:8]}"
        )
        benchmark_publication_root = (
            project_root / ".demo_runs" / f"release-check-proof-publication-{uuid.uuid4().hex[:8]}"
        )
        benchmark_publication_manifest = _write_sample_publication_artifacts(
            benchmark_publication_root
        )
        benchmark_archive_output_dir = benchmark_publication_root / "archive"
        reproduction_runtime_root = (
            project_root / ".demo_runs" / f"release-check-reproduction-{uuid.uuid4().hex[:8]}"
        )
        autonomous_runtime_root = (
            project_root / ".demo_runs" / f"release-check-autonomous-{uuid.uuid4().hex[:8]}"
        )
        real_data_runtime_root = (
            project_root / ".demo_runs" / f"release-check-real-{uuid.uuid4().hex[:8]}"
        )
        real_paper_runtime_root = (
            project_root / ".demo_runs" / f"release-check-real-paper-{uuid.uuid4().hex[:8]}"
        )
        real_paper_proof_dir = real_paper_runtime_root / "proof"
        real_paper_evidence_dir = real_paper_runtime_root / "evidence"
        adam_paper_runtime_root = (
            project_root / ".demo_runs" / f"release-check-adam-paper-{uuid.uuid4().hex[:8]}"
        )
        adam_paper_proof_dir = adam_paper_runtime_root / "proof"
        adam_paper_evidence_dir = adam_paper_runtime_root / "evidence"
        full_reproduction_target_dir = (
            project_root / ".demo_runs" / f"release-check-full-repro-{uuid.uuid4().hex[:8]}"
        )
        full_reproduction_harness_dir = (
            project_root
            / ".demo_runs"
            / f"release-check-full-repro-harness-{uuid.uuid4().hex[:8]}"
        )
        full_reproduction_alignment_dir = (
            project_root
            / ".demo_runs"
            / f"release-check-full-repro-alignment-{uuid.uuid4().hex[:8]}"
        )
        full_reproduction_full_data_dir = (
            project_root
            / ".demo_runs"
            / f"release-check-full-repro-full-data-{uuid.uuid4().hex[:8]}"
        )
        ag_news_train_csv, ag_news_test_csv = _write_sample_ag_news_csvs(
            full_reproduction_full_data_dir / "fixtures"
        )
        fake_fasttext_binary = _write_sample_fasttext_binary(
            full_reproduction_full_data_dir / "fixtures"
        )
        fasttext_patch_proposal = _write_sample_fasttext_patch_proposal(
            full_reproduction_full_data_dir / "fixtures"
        )
        commands.append(
            ReleaseCommand(
                label="mcp-golden-path",
                argv=[
                    python,
                    str(project_root / "scripts" / "mcp_golden_path.py"),
                    "--runtime-root",
                    str(runtime_root),
                    "--max-experiments",
                    "1",
                    "--experiment-duration",
                    "30",
                ],
                timeout_seconds=120,
            )
        )
        commands.append(
            ReleaseCommand(
                label="mcp-multi-round",
                argv=[
                    python,
                    str(project_root / "scripts" / "mcp_multi_round_demo.py"),
                    "--runtime-root",
                    str(multi_round_runtime_root),
                    "--rounds",
                    "2",
                    "--max-experiments",
                    "1",
                    "--experiment-duration",
                    "30",
                ],
                timeout_seconds=180,
            )
        )
        commands.append(
            ReleaseCommand(
                label="mcp-auto-next",
                argv=[
                    python,
                    str(project_root / "scripts" / "mcp_auto_next_demo.py"),
                    "--runtime-root",
                    str(auto_next_runtime_root),
                    "--max-experiments",
                    "1",
                    "--experiment-duration",
                    "30",
                ],
                timeout_seconds=180,
            )
        )
        commands.append(
            ReleaseCommand(
                label="mcp-client-patch",
                argv=[
                    python,
                    str(project_root / "scripts" / "mcp_client_patch_demo.py"),
                    "--runtime-root",
                    str(client_patch_runtime_root),
                    "--max-experiments",
                    "1",
                    "--experiment-duration",
                    "30",
                ],
                timeout_seconds=180,
            )
        )
        commands.append(
            ReleaseCommand(
                label="mcp-provider-quality",
                argv=[
                    python,
                    str(project_root / "scripts" / "mcp_provider_quality_benchmark.py"),
                    "--runtime-root",
                    str(provider_quality_runtime_root),
                ],
                timeout_seconds=60,
            )
        )
        commands.append(
            ReleaseCommand(
                label="mcp-real-task-code",
                argv=[
                    python,
                    str(project_root / "scripts" / "mcp_real_task_code_benchmark.py"),
                    "--runtime-root",
                    str(real_task_code_runtime_root),
                    "--max-experiments",
                    "1",
                    "--experiment-duration",
                    "30",
                ],
                timeout_seconds=180,
            )
        )
        commands.append(
            ReleaseCommand(
                label="benchmark-adapter-smoke",
                argv=[
                    python,
                    str(project_root / "scripts" / "benchmark_adapter_smoke.py"),
                    "--runtime-root",
                    str(benchmark_adapter_runtime_root),
                    "--json",
                ],
                timeout_seconds=180,
            )
        )
        commands.append(
            ReleaseCommand(
                label="mle-bench-official-bridge",
                argv=[
                    python,
                    str(project_root / "scripts" / "mle_bench_official_bridge_demo.py"),
                    "--runtime-root",
                    str(mle_bridge_runtime_root),
                    "--python",
                    python,
                    "--json",
                ],
                timeout_seconds=60,
            )
        )
        commands.append(
            ReleaseCommand(
                label="benchmark-harness-probe",
                argv=[
                    python,
                    str(project_root / "scripts" / "benchmark_harness_probe.py"),
                    "--json",
                ],
                timeout_seconds=30,
            )
        )
        commands.append(
            ReleaseCommand(
                label="research-env-probe",
                argv=[
                    python,
                    str(project_root / "scripts" / "research_env_probe.py"),
                    "--workspace",
                    str(project_root),
                    "--required-command",
                    python,
                    "--json",
                ],
                timeout_seconds=30,
            )
        )
        commands.append(
            ReleaseCommand(
                label="benchmark-proof-plan",
                argv=[
                    python,
                    str(project_root / "scripts" / "benchmark_proof_plan.py"),
                    "--json",
                ],
                timeout_seconds=30,
            )
        )
        commands.append(
            ReleaseCommand(
                label="benchmark-proof-setup",
                argv=[
                    python,
                    str(project_root / "scripts" / "benchmark_proof_setup.py"),
                    "--output-dir",
                    str(benchmark_setup_output_dir),
                    "--json",
                ],
                timeout_seconds=30,
            )
        )
        commands.append(
            ReleaseCommand(
                label="benchmark-proof-publication",
                argv=[
                    python,
                    str(project_root / "scripts" / "benchmark_proof_publication.py"),
                    "--manifest",
                    str(benchmark_publication_manifest),
                    "--artifact-root",
                    str(benchmark_publication_root / "artifacts"),
                    "--output-dir",
                    str(benchmark_publication_root / "publication"),
                    "--json",
                ],
                timeout_seconds=30,
            )
        )
        commands.append(
            ReleaseCommand(
                label="benchmark-proof-archive",
                argv=[
                    python,
                    str(project_root / "scripts" / "benchmark_proof_archive.py"),
                    "--manifest",
                    str(benchmark_publication_manifest),
                    "--artifact-root",
                    str(benchmark_publication_root / "artifacts"),
                    "--output-dir",
                    str(benchmark_archive_output_dir),
                    "--json",
                ],
                timeout_seconds=30,
            )
        )
        commands.append(
            ReleaseCommand(
                label="mcp-real-data",
                argv=[
                    python,
                    str(project_root / "scripts" / "mcp_real_data_demo.py"),
                    "--runtime-root",
                    str(real_data_runtime_root),
                    "--max-experiments",
                    "1",
                    "--experiment-duration",
                    "30",
                ],
                timeout_seconds=120,
            )
        )
        commands.append(
            ReleaseCommand(
                label="mcp-reproduction",
                argv=[
                    python,
                    str(project_root / "scripts" / "mcp_reproduction_demo.py"),
                    "--runtime-root",
                    str(reproduction_runtime_root),
                    "--max-experiments",
                    "1",
                    "--experiment-duration",
                    "30",
                    "--json",
                ],
                timeout_seconds=120,
            )
        )
        commands.append(
            ReleaseCommand(
                label="autonomous-research-demo",
                argv=[
                    python,
                    str(project_root / "scripts" / "autonomous_research_demo.py"),
                    "--runtime-root",
                    str(autonomous_runtime_root),
                    "--json",
                ],
                timeout_seconds=30,
            )
        )
        commands.append(
            ReleaseCommand(
                label="real-paper-pilot-baseline",
                argv=[
                    python,
                    str(project_root / "scripts" / "real_paper_reproduction_pilot.py"),
                    "--paper-id",
                    "arxiv:2605.03312",
                    "--output-dir",
                    str(real_paper_runtime_root),
                    "--run-baseline",
                    "--use-public-mini-slice",
                    "--json",
                ],
                timeout_seconds=30,
            )
        )
        commands.append(
            ReleaseCommand(
                label="real-paper-pilot-iteration",
                argv=[
                    python,
                    str(project_root / "scripts" / "real_paper_reproduction_pilot.py"),
                    "--paper-id",
                    "arxiv:2605.03312",
                    "--output-dir",
                    str(real_paper_runtime_root),
                    "--run-iteration",
                    "--use-public-mini-slice",
                    "--json",
                ],
                timeout_seconds=30,
            )
        )
        commands.append(
            ReleaseCommand(
                label="real-paper-pilot-review",
                argv=[
                    python,
                    str(project_root / "scripts" / "real_paper_reproduction_pilot.py"),
                    "--paper-id",
                    "arxiv:2605.03312",
                    "--output-dir",
                    str(real_paper_runtime_root),
                    "--write-review-report",
                    "--reviewer",
                    "local-release-gate",
                    "--review-decision",
                    "approved_with_limitations",
                    "--json",
                ],
                timeout_seconds=30,
            )
        )
        commands.append(
            ReleaseCommand(
                label="real-paper-pilot-archive",
                argv=[
                    python,
                    str(project_root / "scripts" / "real_paper_reproduction_pilot.py"),
                    "--paper-id",
                    "arxiv:2605.03312",
                    "--output-dir",
                    str(real_paper_runtime_root),
                    "--archive-proof",
                    "--proof-dir",
                    str(real_paper_proof_dir),
                    "--evidence-dir",
                    str(real_paper_evidence_dir),
                    "--update-evidence-index",
                    "--json",
                ],
                timeout_seconds=30,
            )
        )
        commands.append(
            ReleaseCommand(
                label="real-paper-pilot-adam-baseline",
                argv=[
                    python,
                    str(project_root / "scripts" / "real_paper_reproduction_pilot.py"),
                    "--paper-id",
                    "arxiv:1412.6980",
                    "--output-dir",
                    str(adam_paper_runtime_root),
                    "--run-baseline",
                    "--use-public-mini-slice",
                    "--json",
                ],
                timeout_seconds=30,
            )
        )
        commands.append(
            ReleaseCommand(
                label="real-paper-pilot-adam-iteration",
                argv=[
                    python,
                    str(project_root / "scripts" / "real_paper_reproduction_pilot.py"),
                    "--paper-id",
                    "arxiv:1412.6980",
                    "--output-dir",
                    str(adam_paper_runtime_root),
                    "--run-iteration",
                    "--use-public-mini-slice",
                    "--json",
                ],
                timeout_seconds=30,
            )
        )
        commands.append(
            ReleaseCommand(
                label="real-paper-pilot-adam-review",
                argv=[
                    python,
                    str(project_root / "scripts" / "real_paper_reproduction_pilot.py"),
                    "--paper-id",
                    "arxiv:1412.6980",
                    "--output-dir",
                    str(adam_paper_runtime_root),
                    "--write-review-report",
                    "--reviewer",
                    "local-release-gate",
                    "--review-decision",
                    "approved_with_limitations",
                    "--json",
                ],
                timeout_seconds=30,
            )
        )
        commands.append(
            ReleaseCommand(
                label="real-paper-pilot-adam-archive",
                argv=[
                    python,
                    str(project_root / "scripts" / "real_paper_reproduction_pilot.py"),
                    "--paper-id",
                    "arxiv:1412.6980",
                    "--output-dir",
                    str(adam_paper_runtime_root),
                    "--archive-proof",
                    "--proof-dir",
                    str(adam_paper_proof_dir),
                    "--evidence-dir",
                    str(adam_paper_evidence_dir),
                    "--update-evidence-index",
                    "--json",
                ],
                timeout_seconds=30,
            )
        )
        commands.append(
            ReleaseCommand(
                label="full-reproduction-target",
                argv=[
                    python,
                    str(project_root / "scripts" / "full_reproduction_target.py"),
                    "--paper-id",
                    "arxiv:1607.01759",
                    "--output-dir",
                    str(full_reproduction_target_dir),
                    "--json",
                ],
                timeout_seconds=30,
            )
        )
        commands.append(
            ReleaseCommand(
                label="full-reproduction-harness-baseline",
                argv=[
                    python,
                    str(project_root / "scripts" / "full_reproduction_run.py"),
                    "--target-spec",
                    str(project_root / "docs" / "reproduction-pilot" / "full-reproduction-target.json"),
                    "--output-dir",
                    str(full_reproduction_harness_dir),
                    "--run-baseline",
                    "--json",
                ],
                timeout_seconds=30,
            )
        )
        commands.append(
            ReleaseCommand(
                label="full-reproduction-baseline-alignment",
                argv=[
                    python,
                    str(project_root / "scripts" / "full_reproduction_run.py"),
                    "--target-spec",
                    str(project_root / "docs" / "reproduction-pilot" / "full-reproduction-target.json"),
                    "--output-dir",
                    str(full_reproduction_alignment_dir),
                    "--align-baseline",
                    "--repeat-count",
                    "3",
                    "--json",
                ],
                timeout_seconds=30,
            )
        )
        commands.append(
            ReleaseCommand(
                label="full-reproduction-full-data-alignment",
                argv=[
                    python,
                    str(project_root / "scripts" / "full_reproduction_run.py"),
                    "--target-spec",
                    str(project_root / "docs" / "reproduction-pilot" / "full-reproduction-target.json"),
                    "--output-dir",
                    str(full_reproduction_full_data_dir),
                    "--align-full-data",
                    "--ag-news-train-csv",
                    str(ag_news_train_csv),
                    "--ag-news-test-csv",
                    str(ag_news_test_csv),
                    "--fasttext-binary",
                    str(full_reproduction_full_data_dir / "missing-fasttext"),
                    "--repeat-count",
                    "3",
                    "--json",
                ],
                timeout_seconds=30,
            )
        )
        commands.append(
            ReleaseCommand(
                label="full-reproduction-fasttext-binary-baseline",
                argv=[
                    python,
                    str(project_root / "scripts" / "full_reproduction_run.py"),
                    "--target-spec",
                    str(project_root / "docs" / "reproduction-pilot" / "full-reproduction-target.json"),
                    "--output-dir",
                    str(full_reproduction_full_data_dir / "binary-baseline"),
                    "--run-fasttext-baseline",
                    "--ag-news-train-csv",
                    str(ag_news_train_csv),
                    "--ag-news-test-csv",
                    str(ag_news_test_csv),
                    "--fasttext-binary",
                    str(fake_fasttext_binary),
                    "--json",
                ],
                timeout_seconds=30,
            )
        )
        commands.append(
            ReleaseCommand(
                label="full-reproduction-fasttext-patch-round",
                argv=[
                    python,
                    str(project_root / "scripts" / "full_reproduction_run.py"),
                    "--target-spec",
                    str(project_root / "docs" / "reproduction-pilot" / "full-reproduction-target.json"),
                    "--output-dir",
                    str(full_reproduction_full_data_dir / "patch-round"),
                    "--run-fasttext-patch-round",
                    "--ag-news-train-csv",
                    str(ag_news_train_csv),
                    "--ag-news-test-csv",
                    str(ag_news_test_csv),
                    "--fasttext-binary",
                    str(fake_fasttext_binary),
                    "--baseline-report",
                    str(
                        full_reproduction_full_data_dir
                        / "binary-baseline"
                        / "fasttext-baseline-report.json"
                    ),
                    "--fasttext-proposal",
                    str(fasttext_patch_proposal),
                    "--json",
                ],
                timeout_seconds=30,
            )
        )
    return commands


def _write_sample_fasttext_binary(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    binary = root / "fasttext"
    binary.write_text(
        "\n".join(
            [
                "#!/usr/bin/env python3",
                "from pathlib import Path",
                "import sys",
                "cmd = sys.argv[1]",
                "if cmd == 'supervised':",
                "    out = Path(sys.argv[sys.argv.index('-output') + 1])",
                "    metric = '0.875' if '-wordNgrams' in sys.argv and sys.argv[sys.argv.index('-wordNgrams') + 1] == '2' else '0.750'",
                "    out.with_suffix('.bin').write_text(metric + '\\n', encoding='utf-8')",
                "    print('Read 8M words')",
                "    print('Number of words: 42')",
                "    raise SystemExit(0)",
                "if cmd == 'test':",
                "    metric = Path(sys.argv[2]).read_text(encoding='utf-8').strip() or '0.750'",
                "    print('N\\t4')",
                "    print(f'P@1\\t{metric}')",
                "    print(f'R@1\\t{metric}')",
                "    raise SystemExit(0)",
                "raise SystemExit(2)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    binary.chmod(0o755)
    return binary


def _write_sample_fasttext_patch_proposal(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    proposal = root / "fasttext-patch-proposal.json"
    proposal.write_text(
        json.dumps(
            {
                "proposal_id": "release-check-word-ngrams-2",
                "reason": "release gate exercises the P3 client hyperparameter proposal loop",
                "train_args": {"wordNgrams": 2},
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return proposal


def _write_sample_ag_news_csvs(root: Path) -> tuple[Path, Path]:
    root.mkdir(parents=True, exist_ok=True)
    train_csv = root / "train.csv"
    test_csv = root / "test.csv"
    train_csv.write_text(
        "\n".join(
            [
                '"1","Leaders discuss treaty","Foreign ministers opened regional peace talks"',
                '"2","Team wins final","Players celebrated the championship game victory"',
                '"3","Stocks rise","Investors watched revenue growth and bank profits"',
                '"4","New processor released","Software teams tested neural chips and cloud tools"',
                '"1","Election talks continue","Diplomats reviewed the neighboring government vote"',
                '"2","Coach praises players","The league club reached the tournament playoffs"',
                '"3","Company reports profit","Shares moved higher after quarterly earnings"',
                '"4","Browser update ships","Developers patched security flaws in mobile software"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    test_csv.write_text(
        "\n".join(
            [
                '"1","Regional vote monitored","Diplomats and observers discussed election talks"',
                '"2","Club wins match","The league team won the final championship game"',
                '"3","Market watches earnings","Banks and investors reviewed company revenue"',
                '"4","Cloud platform update","Software developers improved processor tools"',
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return train_csv, test_csv


def _write_sample_publication_artifacts(root: Path) -> Path:
    artifact_root = root / "artifacts"
    artifact_paths = {
        "command_lines": "commands.txt",
        "resolved_config": "config.json",
        "environment_manifest": "environment.json",
        "raw_logs": "logs/run.log",
        "raw_reports": "reports/report.json",
        "limitations_note": "LIMITATIONS.md",
    }
    for relative in artifact_paths.values():
        path = artifact_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"release-check sample artifact: {relative}\n", encoding="utf-8")
    manifest_path = root / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        json.dumps(
            {
                "benchmark_name": "mle_bench",
                "run_mode": "official_debug",
                "official_scores_claimed": False,
                "limitations": ["release-check sample; no official score claimed"],
                "artifacts": artifact_paths,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest_path


def run_command(command: ReleaseCommand, project_root: Path, env: dict[str, str]) -> CheckResult:
    start = time.monotonic()
    if command.label == "mcp-stdio-smoke":
        proc = subprocess.run(
            command.argv,
            input=_mcp_smoke_input(),
            cwd=project_root,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=command.timeout_seconds,
        )
    else:
        proc = subprocess.run(
            command.argv,
            cwd=project_root,
            env=env,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=command.timeout_seconds,
        )
    return CheckResult(
        label=command.label,
        returncode=proc.returncode,
        duration_seconds=round(time.monotonic() - start, 3),
        stdout=proc.stdout,
    )


def render_summary(results: list[CheckResult]) -> str:
    payload = {
        "status": "passed" if all(result.returncode == 0 for result in results) else "failed",
        "checks": [
            {
                "label": result.label,
                "returncode": result.returncode,
                "duration_seconds": result.duration_seconds,
                "stdout_tail": "\n".join(result.stdout.splitlines()[-20:]),
            }
            for result in results
        ],
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def release_env(project_root: Path, python: str) -> dict[str, str]:
    env = dict(os.environ)
    pythonpath_parts = [str(project_root)]
    pythonpath_parts.extend(str(path) for path in _site_packages_paths(project_root))
    if env.get("PYTHONPATH"):
        pythonpath_parts.append(env["PYTHONPATH"])
    env["PYTHONPATH"] = os.pathsep.join(pythonpath_parts)
    env["ML_RESEARCH_LOOP_PYTHON"] = resolve_release_python(
        env.get("ML_RESEARCH_LOOP_PYTHON", python),
        project_root,
    )
    return env


def resolve_release_python(python: str, project_root: Path) -> str:
    python_path = Path(python).expanduser()
    if python_path.is_absolute():
        return str(python_path)
    if os.sep in python or (os.altsep and os.altsep in python):
        return str((project_root / python_path).resolve())
    discovered = shutil.which(python)
    return discovered or python


def _site_packages_paths(project_root: Path) -> list[Path]:
    site_packages_root = project_root / ".venv" / "lib"
    if not site_packages_root.exists():
        return []
    return sorted(site_packages_root.glob("python*/site-packages"))


def _mcp_smoke_input() -> str:
    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {"protocolVersion": "2024-11-05"},
        },
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
    ]
    return "\n".join(json.dumps(request) for request in requests) + "\n"


def main() -> int:
    args = parse_args()
    project_root = args.project_root.expanduser().resolve()
    python = resolve_release_python(args.python, project_root)
    env = release_env(project_root, python)
    results: list[CheckResult] = []

    for command in build_release_commands(python, project_root, args.skip_golden_path):
        if not args.json:
            print(f"[release-check] {command.label}: {' '.join(command.argv)}", flush=True)
        result = run_command(command, project_root, env)
        results.append(result)
        if not args.json:
            print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
        if result.returncode != 0:
            break

    print(render_summary(results))
    return 0 if all(result.returncode == 0 for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
