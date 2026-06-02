from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.cp_bench_hf_gate_preflight import (
    build_preflight,
    normalize_submission_name,
    validate_gate,
)


class FakeApi:
    def __init__(
        self,
        *,
        logged_in: bool = False,
        files: list[str] | None = None,
    ) -> None:
        self.logged_in = logged_in
        self.files = files or []

    def whoami(self) -> dict[str, str]:
        if not self.logged_in:
            raise RuntimeError("Token is required")
        return {"name": "hf-test-user"}

    def list_repo_files(self, *, repo_id: str, repo_type: str) -> list[str]:
        assert repo_id == "kostis-init/my-storage"
        assert repo_type == "dataset"
        return self.files


def test_normalize_submission_name_matches_space_rules() -> None:
    assert normalize_submission_name(" ML Research Loop P17! ") == "ml_research_loop_p17"
    assert normalize_submission_name("x" * 40) == "x" * 30


def test_preflight_reports_missing_auth_without_uploading(tmp_path: Path) -> None:
    gate_dir = _write_gate(tmp_path)

    payload = build_preflight(gate_dir, api=FakeApi(logged_in=False))

    assert payload["status"] == "blocked_missing_hf_auth"
    assert payload["target_submission_exists"] is False
    assert payload["target_result_exists"] is False
    assert payload["external_upload_performed_by_script"] is False
    assert payload["manual_approval_required"] is True
    assert payload["official_scores_claimed"] is False
    assert payload["gate_validation"]["status"] == "valid"


def test_preflight_detects_existing_public_result(tmp_path: Path) -> None:
    gate_dir = _write_gate(tmp_path)
    files = [
        "submissions/v1_verified/ml_research_loop_p17/submission.jsonl",
        "submissions/v1_verified/ml_research_loop_p17/metadata.json",
        "results/v1_verified/ml_research_loop_p17/summary.txt",
    ]

    payload = build_preflight(gate_dir, api=FakeApi(logged_in=True, files=files))

    assert payload["status"] == "public_result_available"
    assert payload["target_submission_exists"] is True
    assert payload["target_result_exists"] is True
    assert payload["observed_external_submission_status"] == "submitted"
    assert payload["official_scores_claimed"] is False


def test_validate_gate_rejects_official_score_claims(tmp_path: Path) -> None:
    gate_dir = _write_gate(tmp_path)
    manifest_path = gate_dir / "artifact-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["official_scores_claimed"] = True
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    validation = validate_gate(gate_dir)

    assert validation["status"] == "invalid"
    assert any("official_scores_claimed=false" in error for error in validation["errors"])


def test_validate_gate_requires_space_normalized_submission_name(tmp_path: Path) -> None:
    gate_dir = _write_gate(tmp_path, submission_name="ML Research Loop P17!")

    validation = validate_gate(gate_dir)

    assert validation["status"] == "invalid"
    assert any("CP-Bench Space normalization" in error for error in validation["errors"])


def _write_gate(tmp_path: Path, *, submission_name: str = "ml_research_loop_p17") -> Path:
    gate_dir = tmp_path / "gate"
    gate_dir.mkdir()
    files = {
        "submission.jsonl": '{"id":"demo_problem","model":"print(1)"}\n',
        "submission-report.md": "official_scores_claimed: `false`\n",
        "manual-checklist.md": "official_scores_claimed: `false`\n",
        "manual-upload-instructions.md": "当前状态：`not_submitted`\n",
        "approach-report.pdf": "%PDF-1.4\n",
        "submission-metadata.json": json.dumps(
            {
                "submission_name": submission_name,
                "dataset_version": "verified",
                "modelling_framework": "CPMpy",
                "base_llm": "Codex-assisted deterministic CPMPy solver expansion",
                "external_submission_status": "not_submitted",
                "official_scores_claimed": False,
            },
            indent=2,
        )
        + "\n",
        "README.md": "official_scores_claimed: `false`\n",
        "source-report.json": "{}\n",
    }
    for relative_path, contents in files.items():
        (gate_dir / relative_path).write_text(contents, encoding="utf-8")

    manifest = {
        "schema_version": "2026-05-23.cp-bench-artifact-manifest.v1",
        "status": "written",
        "target_id": "cp-bench-constraint-modeling",
        "official_scores_claimed": False,
        "manual_submission_required": True,
        "external_submission_status": "not_submitted",
        "artifacts": [
            {
                "role": Path(relative_path).stem.replace("-", "_"),
                "path": relative_path,
                "sha256": _sha256(gate_dir / relative_path),
                "byte_count": (gate_dir / relative_path).stat().st_size,
            }
            for relative_path in files
        ],
    }
    manifest_path = gate_dir / "artifact-manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    checksum_lines = [
        f"{_sha256(gate_dir / relative_path)}  {relative_path}" for relative_path in files
    ]
    checksum_lines.append(f"{_sha256(manifest_path)}  artifact-manifest.json")
    (gate_dir / "SHA256SUMS").write_text("\n".join(checksum_lines) + "\n", encoding="utf-8")
    return gate_dir


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
