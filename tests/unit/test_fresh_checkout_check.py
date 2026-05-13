from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from scripts import fresh_checkout_check


def test_fresh_checkout_check_builds_public_checkout_commands(tmp_path: Path) -> None:
    checkout, commands = fresh_checkout_check.build_commands(
        repo_url="https://github.com/MagicianDu/ml-research-loop.git",
        ref="v0.1.0-preview",
        python="/usr/bin/python3",
        workdir=tmp_path,
        skip_golden_path=False,
    )

    labels = [command.label for command in commands]

    assert checkout == tmp_path / "ml-research-loop"
    assert labels == [
        "git-clone",
        "create-venv",
        "install",
        "mcp-client-acceptance",
        "render-codex-config",
        "skills-dry-run",
        "mcp-golden-path",
    ]
    assert commands[0].argv == [
        "git",
        "clone",
        "--depth",
        "1",
        "--branch",
        "v0.1.0-preview",
        "https://github.com/MagicianDu/ml-research-loop.git",
        str(checkout),
    ]
    assert commands[2].argv[:4] == [
        str(checkout / ".venv" / "bin" / "python"),
        "-m",
        "pip",
        "install",
    ]
    assert commands[2].timeout_seconds == 900
    assert commands[3].argv[-2:] == ["--project-root", str(checkout)]
    assert commands[4].argv[0] == str(checkout / ".venv" / "bin" / "ml-loop")
    assert commands[6].argv[1].endswith("scripts/mcp_golden_path.py")


def test_fresh_checkout_check_summary_marks_failed_command(tmp_path: Path) -> None:
    payload = json.loads(
        fresh_checkout_check.render_summary(
            repo_url="repo",
            ref="main",
            checkout=tmp_path / "ml-research-loop",
            results=[
                fresh_checkout_check.FreshResult(
                    label="git-clone",
                    returncode=0,
                    duration_seconds=1.0,
                    stdout="ok\n",
                ),
                fresh_checkout_check.FreshResult(
                    label="install",
                    returncode=1,
                    duration_seconds=2.0,
                    stdout="\n".join(str(index) for index in range(30)),
                ),
            ],
        )
    )

    assert payload["status"] == "failed"
    assert payload["checks"][1]["label"] == "install"
    assert payload["checks"][1]["returncode"] == 1
    assert payload["checks"][1]["stdout_tail"].splitlines()[0] == "10"


def test_fresh_checkout_check_reports_timeout_as_json_result(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_run(*args, **kwargs):
        del args, kwargs
        raise subprocess.TimeoutExpired(cmd=["python", "-m", "pip"], timeout=3)

    monkeypatch.setattr(fresh_checkout_check.subprocess, "run", fake_run)

    result = fresh_checkout_check.run_command(
        fresh_checkout_check.FreshCommand(
            label="install",
            argv=["python", "-m", "pip"],
            cwd=tmp_path,
            timeout_seconds=3,
        )
    )

    assert result.label == "install"
    assert result.returncode == 124
    assert "timed out after 3 seconds" in result.stdout


def test_stable_readiness_reports_preview_with_stable_blockers(tmp_path: Path) -> None:
    _write_minimal_beta_docs(tmp_path)

    payload = fresh_checkout_check.build_stable_readiness_report(tmp_path)

    assert payload["status"] == "preview_ready"
    assert payload["beta_blockers"] == []
    assert payload["stable_blockers"] == [
        "missing_frozen_contract_versions",
        "missing_external_pilot_feedback",
        "missing_real_task_proof_archives",
        "missing_official_debug_benchmark_proof",
        "missing_public_claim_proof_mapping",
        "missing_downloadable_release_artifact",
    ]


def test_stable_readiness_requires_structured_claim_map_and_proof_archive(
    tmp_path: Path,
) -> None:
    _write_minimal_beta_docs(tmp_path)
    _write_public_claim_map(tmp_path)
    _write_official_debug_proof_archive(tmp_path / ".demo_runs" / "official-debug" / "archive")

    payload = fresh_checkout_check.build_stable_readiness_report(tmp_path)

    assert "missing_official_debug_benchmark_proof" not in payload["stable_blockers"]
    assert "missing_public_claim_proof_mapping" not in payload["stable_blockers"]
    assert "missing_real_task_proof_archives" in payload["stable_blockers"]


def test_stable_readiness_cli_does_not_run_fresh_checkout_commands(
    monkeypatch,
    capsys,
    tmp_path: Path,
) -> None:
    _write_minimal_beta_docs(tmp_path)

    def fail_run_command(command):
        raise AssertionError(f"unexpected command: {command.label}")

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(sys, "argv", ["fresh_checkout_check.py", "--stable-readiness"])
    monkeypatch.setattr(fresh_checkout_check, "run_command", fail_run_command)

    assert fresh_checkout_check.main() == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "preview_ready"
    assert payload["stable_blockers"][0] == "missing_frozen_contract_versions"


def _write_minimal_beta_docs(root: Path) -> None:
    docs = root / "docs"
    evidence = docs / "evidence"
    evidence.mkdir(parents=True)
    (docs / "release-notes.md").write_text(
        "\n".join([
            "# Release Notes",
            "## Beta Release Gate",
            "clean checkout install",
            "MCP client acceptance",
            "skills install dry-run",
            "bounded demo",
            "autonomous research demo",
            "known limitations explicit",
            "public claims mapped to proof matrix entries",
            "contract_version: 2026-04-30.preview.v1",
            "## Known Limitations",
            "Product status remains preview.",
        ]),
        encoding="utf-8",
    )
    (docs / "release-checklist.md").write_text(
        "\n".join([
            "# Release Checklist",
            "pip install -e \".[dev]\"",
            "scripts/mcp_client_acceptance.py",
            "ml-loop init-skills --dry-run",
            "scripts/mcp_golden_path.py",
            "scripts/autonomous_research_demo.py",
            "pilot guide complete",
        ]),
        encoding="utf-8",
    )
    (docs / "client-compatibility-matrix.md").write_text(
        "\n".join([
            "# Client Compatibility Matrix",
            "| Client | Status |",
            "|---|---|",
            "| Codex | Supported preview |",
            "| Claude Code | Supported preview |",
            "| Claude Desktop | Supported preview |",
        ]),
        encoding="utf-8",
    )
    (docs / "institution-pilot-guide-cn.md").write_text(
        "pilot guide complete\nfeedback loop\nprivacy\nresource budget\n",
        encoding="utf-8",
    )
    (evidence / "autonomous-product-proof-matrix-cn.md").write_text(
        "\n".join([
            "# Proof Matrix",
            "| Capability | Current evidence | Gap | Next proof |",
            "| --- | --- | --- | --- |",
            "| Research evidence | evidence | gap | proof |",
            "| Experiment loop | evidence | gap | proof |",
            "| Patch loop | evidence | gap | proof |",
            "official debug proof archive",
            "official_scores_claimed=false",
            "claim boundary",
        ]),
        encoding="utf-8",
    )


def _write_public_claim_map(root: Path) -> None:
    claim_map = root / "docs" / "evidence" / "public-claims-map.json"
    claim_map.write_text(
        json.dumps(
            {
                "schema_version": "2026-05-13.public-claims-map.v1",
                "public_claims": [
                    {
                        "claim_id": "claim-001",
                        "public_claim": "local proof archive is available for review",
                        "proof_matrix_entry": "Reproduction",
                        "evidence": "docs/evidence/example-proof.md",
                        "claim_boundary": "local proof only; not an official score",
                    }
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def _write_official_debug_proof_archive(root: Path) -> None:
    root.mkdir(parents=True)
    roles = [
        "command_lines",
        "resolved_config",
        "environment_manifest",
        "raw_logs",
        "raw_reports",
        "limitations_note",
    ]
    artifacts = [
        {
            "role": role,
            "archive_relative_path": f"artifacts/{role}.txt",
            "sha256": "a" * 64,
        }
        for role in roles
    ]
    (root / "proof-archive.json").write_text(
        json.dumps(
            {
                "status": "archivable",
                "official_scores_claimed": False,
                "benchmark_name": "mle_bench",
                "run_mode": "official_debug",
                "artifact_count": len(artifacts),
                "artifact_manifest": {
                    "judge_type": "official_scorer",
                    "metric": "debug_score",
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    (root / "artifact-index.json").write_text(
        json.dumps({"artifact_count": len(artifacts), "artifacts": artifacts}) + "\n",
        encoding="utf-8",
    )
    publication = root / "publication"
    publication.mkdir()
    (publication / "proof-publication.json").write_text(
        json.dumps(
            {
                "status": "publishable_with_limitations",
                "official_scores_claimed": False,
                "claim_policy": {
                    "score_claim": "not_allowed",
                    "requires_limitations": True,
                },
                "blocked_public_claims": [
                    "official leaderboard score",
                    "deterministic local fixture score as official benchmark performance",
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )
