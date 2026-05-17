from __future__ import annotations

import hashlib
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


def test_stable_readiness_reports_beta_ready_with_stable_blockers(tmp_path: Path) -> None:
    _write_minimal_beta_docs(tmp_path)

    payload = fresh_checkout_check.build_stable_readiness_report(tmp_path)

    assert payload["status"] == "beta_ready"
    assert payload["beta_blockers"] == []
    assert payload["release_boundary"] == {
        "preview": {"status": "ready", "blockers": []},
        "beta": {"status": "ready", "blockers": []},
        "stable": {
            "status": "blocked",
            "blockers": [
                "missing_frozen_contract_versions",
                "missing_external_pilot_feedback",
                "missing_real_task_proof_archives",
                "missing_official_debug_benchmark_proof",
                "missing_public_claim_proof_mapping",
                "missing_downloadable_release_artifact",
            ],
        },
    }
    beta_gates = {gate["gate"]: gate for gate in payload["beta_readiness"]}
    assert beta_gates["release_gate"]["status"] == "ready"
    assert beta_gates["client_acceptance"]["status"] == "ready"
    assert beta_gates["skills_dry_run"]["status"] == "ready"
    assert beta_gates["fresh_checkout"]["status"] == "ready"
    assert beta_gates["proof_matrix"]["status"] == "ready"
    assert beta_gates["known_limitations"]["status"] == "ready"
    assert beta_gates["optional_cognee_adapter"]["status"] == "not_required"
    assert payload["release_artifacts"]["status"] == "missing"
    assert payload["release_artifacts"]["missing"] == [
        "dist/*.whl",
        "dist/*.tar.gz",
        "dist/SHA256SUMS or dist/*.sha256",
    ]
    assert "python3 -m build" in payload["release_artifacts"]["next_action"]
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
    _write_official_debug_proof_archive(
        tmp_path / "release" / "evidence" / "official-debug" / "archive"
    )

    payload = fresh_checkout_check.build_stable_readiness_report(tmp_path)

    assert "missing_official_debug_benchmark_proof" not in payload["stable_blockers"]
    assert "missing_public_claim_proof_mapping" not in payload["stable_blockers"]
    assert "missing_real_task_proof_archives" in payload["stable_blockers"]


def test_stable_readiness_ignores_pilot_feedback_templates(tmp_path: Path) -> None:
    _write_minimal_beta_docs(tmp_path)
    feedback_dir = tmp_path / "docs" / "pilot-feedback"
    feedback_dir.mkdir()
    (feedback_dir / "README.md").write_text(
        "# External pilot feedback\nThis pilot feedback directory is a template.\n",
        encoding="utf-8",
    )
    (feedback_dir / "pilot-feedback.schema.json").write_text(
        json.dumps({"title": "external pilot feedback schema"}) + "\n",
        encoding="utf-8",
    )
    (feedback_dir / "external-feedback.example.json").write_text(
        json.dumps(
            {
                "feedback_type": "external_pilot",
                "status": "received",
                "redacted": True,
                "template": True,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    payload = fresh_checkout_check.build_stable_readiness_report(tmp_path)

    assert "missing_external_pilot_feedback" in payload["stable_blockers"]


def test_stable_readiness_counts_three_real_redacted_external_feedback_items(
    tmp_path: Path,
) -> None:
    _write_minimal_beta_docs(tmp_path)
    feedback_dir = tmp_path / "docs" / "pilot-feedback"
    feedback_dir.mkdir()
    for index, client in enumerate(["codex", "claude-code", "claude-desktop"], start=1):
        (feedback_dir / f"feedback-{index}.json").write_text(
            json.dumps(
                {
                    "feedback_type": "external_pilot",
                    "status": "received",
                    "redacted": True,
                    "source": "external",
                    "client": client,
                    "user_role": "graduate_student",
                    "submitted_at": f"2026-05-17T0{index}:00:00Z",
                    "install_status": "passed",
                    "mcp_status": "passed",
                    "demo_status": "passed",
                }
            )
            + "\n",
            encoding="utf-8",
        )

    payload = fresh_checkout_check.build_stable_readiness_report(tmp_path)

    assert "missing_external_pilot_feedback" not in payload["stable_blockers"]


def test_stable_readiness_ignores_runtime_demo_proof_archives(tmp_path: Path) -> None:
    _write_minimal_beta_docs(tmp_path)
    _write_public_claim_map(tmp_path)
    _write_official_debug_proof_archive(tmp_path / ".demo_runs" / "official-debug" / "archive")

    payload = fresh_checkout_check.build_stable_readiness_report(tmp_path)

    assert "missing_official_debug_benchmark_proof" in payload["stable_blockers"]
    assert "missing_real_task_proof_archives" in payload["stable_blockers"]
    assert "missing_public_claim_proof_mapping" not in payload["stable_blockers"]


def test_stable_readiness_rejects_metadata_only_proof_archives(tmp_path: Path) -> None:
    _write_minimal_beta_docs(tmp_path)
    _write_public_claim_map(tmp_path)
    _write_official_debug_proof_archive(
        tmp_path / "release" / "evidence" / "official-debug" / "archive",
        write_artifact_files=False,
    )

    payload = fresh_checkout_check.build_stable_readiness_report(tmp_path)

    assert "missing_official_debug_benchmark_proof" in payload["stable_blockers"]
    assert "missing_real_task_proof_archives" in payload["stable_blockers"]
    assert "missing_public_claim_proof_mapping" not in payload["stable_blockers"]


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
    assert payload["status"] == "beta_ready"
    assert payload["stable_blockers"][0] == "missing_frozen_contract_versions"
    assert payload["release_boundary"]["beta"]["status"] == "ready"


def test_stable_readiness_reports_preview_when_beta_gate_is_incomplete(
    tmp_path: Path,
) -> None:
    _write_minimal_beta_docs(tmp_path)
    (tmp_path / "docs" / "release-notes.md").write_text(
        "# Release Notes\n## Known Limitations\nknown limitations explicit\n",
        encoding="utf-8",
    )

    payload = fresh_checkout_check.build_stable_readiness_report(tmp_path)

    assert payload["status"] == "preview_ready"
    assert payload["release_boundary"]["preview"]["status"] == "ready"
    assert payload["release_boundary"]["beta"]["status"] == "blocked"
    assert "missing_release_gate" in payload["beta_blockers"]


def test_release_artifact_report_verifies_dist_wheel_and_sdist_hashes(
    tmp_path: Path,
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    wheel = dist / "ml_research_loop-0.1.0-py3-none-any.whl"
    sdist = dist / "ml_research_loop-0.1.0.tar.gz"
    wheel.write_bytes(b"wheel-bytes")
    sdist.write_bytes(b"sdist-bytes")
    sums = dist / "SHA256SUMS"
    sums.write_text(
        "\n".join([
            f"{hashlib.sha256(wheel.read_bytes()).hexdigest()}  {wheel.name}",
            f"{hashlib.sha256(sdist.read_bytes()).hexdigest()}  {sdist.name}",
        ])
        + "\n",
        encoding="utf-8",
    )

    payload = fresh_checkout_check.build_release_artifact_report(tmp_path)

    assert payload["status"] == "verified"
    assert payload["missing"] == []
    assert payload["hash_mismatches"] == []
    assert payload["artifacts"] == [
        "dist/ml_research_loop-0.1.0-py3-none-any.whl",
        "dist/ml_research_loop-0.1.0.tar.gz",
    ]


def test_release_artifact_report_requires_hash_for_existing_artifacts(
    tmp_path: Path,
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "ml_research_loop-0.1.0-py3-none-any.whl").write_bytes(b"wheel-bytes")

    payload = fresh_checkout_check.build_release_artifact_report(tmp_path)

    assert payload["status"] == "hash_missing"
    assert payload["missing"] == ["dist/*.tar.gz", "dist/SHA256SUMS or dist/*.sha256"]
    assert "sha256" in payload["next_action"].lower()


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
            "beta release gate",
            "scripts/release_check.py --json",
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
            "| Reproduction | evidence | gap | proof |",
            "official debug proof archive",
            "official_scores_claimed=false",
            "claim boundary",
        ]),
        encoding="utf-8",
    )


def _write_public_claim_map(root: Path) -> None:
    evidence_file = root / "docs" / "evidence" / "example-proof.md"
    evidence_file.write_text("local proof evidence\n", encoding="utf-8")
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


def _write_official_debug_proof_archive(root: Path, *, write_artifact_files: bool = True) -> None:
    root.mkdir(parents=True)
    roles = [
        "command_lines",
        "resolved_config",
        "environment_manifest",
        "raw_logs",
        "raw_reports",
        "limitations_note",
    ]
    artifacts = []
    for role in roles:
        relative_path = f"artifacts/{role}.txt"
        content = f"{role}: official debug proof\n".encode()
        if write_artifact_files:
            artifact_path = root / relative_path
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_bytes(content)
        artifacts.append(
            {
                "role": role,
                "archive_relative_path": relative_path,
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
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
