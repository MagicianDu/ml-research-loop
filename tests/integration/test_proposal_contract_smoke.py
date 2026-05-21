from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_proposal_contract_smoke_runs_closed_loop_and_protects_artifacts(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[2]
    fixture_dir = root / "examples" / "proposal-contract"
    output_dir = tmp_path / "proposal-contract-smoke"
    env = {
        **os.environ,
        "PYTHONPATH": f"{root}:{root / '.venv' / 'lib' / 'python3.13' / 'site-packages'}",
    }
    command = [
        sys.executable,
        str(root / "scripts" / "proposal_contract_smoke.py"),
        "--fixture-dir",
        str(fixture_dir),
        "--output-dir",
        str(output_dir),
        "--json",
    ]

    proc = subprocess.run(
        command,
        cwd=str(root),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
    )

    assert proc.returncode == 0, proc.stdout
    summary = json.loads(proc.stdout.splitlines()[-1])
    assert summary["accepted_validation_status"] == "accepted"
    assert summary["rejected_validation_status"] == "rejected"
    assert summary["reflection_status"] in {
        "candidate_supported",
        "needs_promotion_evidence",
        "needs_rollback_or_more_evidence",
    }
    assert summary["recommended_next_action"]
    assert "not an official score claim" in summary["claim_boundary"]
    assert summary["official_scores_claimed"] is False
    assert Path(summary["accepted_proposal_output_file"]).exists()
    assert Path(summary["rejected_proposal_output_file"]).exists()
    assert Path(summary["accepted_validation_file"]).exists()
    assert Path(summary["rejected_validation_file"]).exists()
    rejected_validation = json.loads(
        Path(summary["rejected_validation_file"]).read_text(encoding="utf-8")
    )
    assert rejected_validation["status"] == "rejected"
    assert "official_score_claim_forbidden" in rejected_validation["failure_labels"]

    for key in ("context_file", "prompt_file", "reflection_file", "summary_file"):
        assert Path(summary[key]).exists(), key

    reflection = json.loads(Path(summary["reflection_file"]).read_text(encoding="utf-8"))
    assert reflection["status"] == summary["reflection_status"]
    if reflection["status"] == "candidate_supported":
        assert reflection["evaluation"]["promotion_gate_passed"] is True
        assert reflection["evaluation"]["canary_delta"]
    else:
        assert reflection["failure_labels"]

    second_proc = subprocess.run(
        command,
        cwd=str(root),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
    )

    assert second_proc.returncode != 0
    assert "already exists" in second_proc.stdout or "FileExistsError" in second_proc.stdout


def test_proposal_contract_smoke_manifest_command_runs_without_pythonpath(
    tmp_path: Path,
) -> None:
    root = Path(__file__).resolve().parents[2]
    output_dir = tmp_path / "manifest-command"
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)

    proc = subprocess.run(
        [
            sys.executable,
            str(root / "scripts" / "proposal_contract_smoke.py"),
            "--output-dir",
            str(output_dir),
            "--json",
        ],
        cwd=str(root),
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
    )

    assert proc.returncode == 0, proc.stdout
    summary = json.loads(proc.stdout.splitlines()[-1])
    assert summary["status"] == "completed"
    assert summary["accepted_validation_status"] == "accepted"
