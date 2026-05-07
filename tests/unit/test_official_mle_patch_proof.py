from __future__ import annotations

import json
import sys
from pathlib import Path

from lib.benchmarks import write_official_mle_patch_round_proof_bundle


def test_write_official_mle_patch_round_proof_bundle_writes_archive(
    tmp_path: Path,
) -> None:
    patch_round_report = _write_patch_round_fixture(tmp_path)

    payload = write_official_mle_patch_round_proof_bundle(
        patch_round_report=patch_round_report,
        output_dir=tmp_path / "proof",
    )

    assert payload["status"] == "written"
    assert payload["official_scores_claimed"] is False
    assert Path(payload["manifest_path"]).is_file()
    assert Path(payload["artifact_root"]).is_dir()
    assert payload["archive"]["bundle"]["status"] == "archivable"
    artifact_root = Path(payload["artifact_root"])
    assert (artifact_root / "commands.txt").is_file()
    assert (artifact_root / "config.json").is_file()
    assert (artifact_root / "environment.json").is_file()
    assert (artifact_root / "logs" / "combined.log").is_file()
    assert (artifact_root / "reports" / "patch-round-report.json").is_file()
    assert (artifact_root / "patches" / "patch.diff").is_file()
    assert (artifact_root / "LIMITATIONS.md").is_file()
    assert Path(payload["archive"]["json_path"]).is_file()
    assert Path(payload["archive"]["index_path"]).is_file()
    assert Path(payload["archive"]["publication_json_path"]).is_file()
    archive_index = json.loads(Path(payload["archive"]["index_path"]).read_text(encoding="utf-8"))
    roles = {entry["role"] for entry in archive_index["artifacts"]}
    assert "patch_diff" in roles
    assert "round_report" in roles
    assert "solver_snapshot" in roles
    manifest = json.loads(Path(payload["manifest_path"]).read_text(encoding="utf-8"))
    assert manifest["benchmark_name"] == "mle_bench"
    assert manifest["run_mode"] == "official_debug_patch_round"
    assert manifest["official_scores_claimed"] is False
    assert manifest["artifacts"]["raw_reports"] == "reports/patch-round-report.json"


def test_write_official_mle_patch_round_proof_bundle_skips_paths_outside_runtime_root(
    tmp_path: Path,
) -> None:
    patch_round_report = _write_patch_round_fixture(tmp_path)
    outside_root = tmp_path.parent / f"{tmp_path.name}-outside"
    outside_root.mkdir()
    outside_patch = outside_root / "patch.diff"
    outside_patch.write_text("--- a/secret\n", encoding="utf-8")
    outside_workspace = outside_root / "workspace"
    outside_workspace.mkdir()
    (outside_workspace / "solve.py").write_text("print('outside')\n", encoding="utf-8")
    report = json.loads(patch_round_report.read_text(encoding="utf-8"))
    report["patch_diff_path"] = str(outside_patch)
    report["workspace"] = str(outside_workspace)
    report["round"]["workspace"] = str(outside_workspace)
    report["round"]["submission_path"] = str(outside_workspace / "submission.csv")
    patch_round_report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    payload = write_official_mle_patch_round_proof_bundle(
        patch_round_report=patch_round_report,
        output_dir=tmp_path / "proof",
    )

    manifest = json.loads(Path(payload["manifest_path"]).read_text(encoding="utf-8"))
    archive_index = json.loads(Path(payload["archive"]["index_path"]).read_text(encoding="utf-8"))
    roles = {entry["role"] for entry in archive_index["artifacts"]}
    assert "patch_diff" not in manifest["artifacts"]
    assert "solver_snapshot" not in manifest["artifacts"]
    assert "submission_snapshot" not in manifest["artifacts"]
    assert "patch_diff" not in roles
    assert "solver_snapshot" not in roles


def test_write_official_mle_patch_round_proof_bundle_keeps_patch_round_snapshots(
    tmp_path: Path,
) -> None:
    patch_round_report = _write_patch_round_fixture(
        tmp_path,
        round_output_dir_name="patch-round",
    )

    payload = write_official_mle_patch_round_proof_bundle(
        patch_round_report=patch_round_report,
        output_dir=tmp_path / "proof",
    )

    manifest = json.loads(Path(payload["manifest_path"]).read_text(encoding="utf-8"))
    artifacts = manifest["artifacts"]
    assert artifacts["solver_snapshot"] == "snapshots/solve.py"
    assert artifacts["submission_snapshot"] == "snapshots/submission.csv"
    assert (Path(payload["artifact_root"]) / artifacts["solver_snapshot"]).is_file()
    assert (Path(payload["artifact_root"]) / artifacts["submission_snapshot"]).is_file()


def _write_patch_round_fixture(
    tmp_path: Path,
    *,
    round_output_dir_name: str = "rounds",
) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "solve.py").write_text("print('patched solver')\n", encoding="utf-8")
    (workspace / "submission.csv").write_text(
        "id,EAP,HPL,MWS\n2,0.4,0.3,0.3\n",
        encoding="utf-8",
    )
    round_dir = tmp_path / round_output_dir_name / "round-002"
    round_dir.mkdir(parents=True)
    (round_dir / "patch.diff").write_text(
        "--- a/solve.py\n+++ b/solve.py\n@@ -1,1 +1,1 @@\n-old\n+new\n",
        encoding="utf-8",
    )
    (round_dir / "solve.log").write_text("solver log\n", encoding="utf-8")
    (round_dir / "grade.log").write_text("grade log\n", encoding="utf-8")
    (round_dir / "grade-report.json").write_text(
        '{"score": 1.11, "valid_submission": true}\n',
        encoding="utf-8",
    )
    round_payload = {
        "status": "graded",
        "round_id": "round-002",
        "competition_id": "spooky-author-identification",
        "workspace": str(workspace),
        "submission_path": str(workspace / "submission.csv"),
        "official_mle_bench": True,
        "official_scores_claimed": False,
        "round_report_path": str(round_dir / "round-report.json"),
        "solve": {"returncode": 0, "log_path": str(round_dir / "solve.log")},
        "grade": {
            "status": "graded",
            "log_path": str(round_dir / "grade.log"),
            "report_path": str(round_dir / "grade-report.json"),
            "report": {"score": 1.11, "valid_submission": True},
        },
    }
    (round_dir / "round-report.json").write_text(
        json.dumps(round_payload, indent=2) + "\n",
        encoding="utf-8",
    )
    patch_round_payload = {
        "status": "graded",
        "official_mle_bench": True,
        "official_scores_claimed": False,
        "round_id": "round-002",
        "competition_id": "spooky-author-identification",
        "workspace": str(workspace),
        "patch_diff_path": str(round_dir / "patch.diff"),
        "patch_execution": {"status": "applied", "changed_files": ["solve.py"]},
        "round": round_payload,
        "loop_decision": {
            "recommended_next_action": "continue",
            "reason_category": "valid_local_score",
        },
        "execution_metadata": {
            "python_executable": "python3",
            "server_python": sys.executable,
            "timeout_policy": {"subprocess_timeout_seconds": 10},
            "execution_sandbox": {"status": "enforced"},
        },
    }
    patch_round_report = round_dir / "patch-round-report.json"
    patch_round_report.write_text(
        json.dumps(patch_round_payload, indent=2) + "\n",
        encoding="utf-8",
    )
    return patch_round_report
