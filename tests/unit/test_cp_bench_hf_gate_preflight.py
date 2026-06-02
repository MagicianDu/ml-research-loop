from __future__ import annotations

import hashlib
import json
from pathlib import Path

from scripts.cp_bench_hf_gate_preflight import (
    build_preflight,
    normalize_submission_name,
    validate_gate,
)
from scripts.cp_bench_hf_gradio_submission import build_gradio_submission_plan
from scripts.cp_bench_hf_public_result_watcher import (
    build_public_result_watch,
    parse_cp_bench_summary,
)
from scripts.cp_bench_hf_submission_packet import build_submission_packet
from scripts.cp_bench_hf_upload_readiness_audit import build_upload_readiness_audit


PROJECT_ROOT = Path(__file__).resolve().parents[2]
P17_GATE_DIR = PROJECT_ROOT / "docs/hf-evaluation/cp-bench-p17-manual-submission-gate"


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


def test_submission_packet_records_blocker_without_uploading(tmp_path: Path) -> None:
    gate_dir = _write_gate(tmp_path)
    output_dir = tmp_path / "packet"

    payload = build_submission_packet(
        gate_dir=gate_dir,
        output_dir=output_dir,
        api=FakeApi(logged_in=False),
    )
    report_text = (output_dir / "submission-readiness-report.json").read_text(encoding="utf-8")
    form_fields = json.loads((output_dir / "manual-form-fields.json").read_text(encoding="utf-8"))

    assert payload["status"] == "blocked_missing_hf_auth"
    assert payload["manual_upload"]["space_repo_id"] == "kostis-init/CP-Bench-Leaderboard"
    assert payload["manual_upload"]["space_url"] == "https://huggingface.co/spaces/kostis-init/CP-Bench-Leaderboard"
    assert payload["manual_upload"]["submission_name"] == "ml_research_loop_p17"
    assert payload["manual_upload"]["target_result_path"] == "results/v1_verified/ml_research_loop_p17/summary.txt"
    assert payload["manual_upload"]["can_upload_now"] is False
    assert payload["external_upload_performed_by_script"] is False
    assert payload["official_scores_claimed"] is False
    assert form_fields["Submission Name"] == "ml_research_loop_p17"
    assert str(tmp_path) not in report_text
    assert (output_dir / "README.md").exists()
    assert (output_dir / "post-upload-verification.md").exists()
    assert (output_dir / "artifact-manifest.json").exists()
    assert (output_dir / "SHA256SUMS").exists()


def test_committed_p17_manual_gate_is_locally_valid() -> None:
    validation = validate_gate(P17_GATE_DIR)

    assert validation["status"] == "valid", validation["errors"]
    assert validation["submission_name"] == "ml_research_loop_p17"
    assert validation["official_scores_claimed"] is False


def test_gradio_submission_plan_is_dry_run_by_default(tmp_path: Path) -> None:
    gate_dir = _write_gate(tmp_path)
    output_dir = tmp_path / "gradio-plan"
    client = FakeGradioClient()

    payload = build_gradio_submission_plan(
        gate_dir=gate_dir,
        output_dir=output_dir,
        repo_files=[],
        space_config=_space_config(),
        client_factory=lambda _: client,
    )
    report_text = (output_dir / "gradio-submission-plan.json").read_text(encoding="utf-8")

    assert payload["status"] == "dry_run_ready_for_human_approved_space_upload"
    assert payload["space_api_contract"]["api_name"] == "/handle_upload"
    assert payload["would_upload"] is True
    assert payload["external_upload_performed_by_script"] is False
    assert payload["official_scores_claimed"] is False
    assert client.calls == []
    assert str(tmp_path) not in report_text
    assert (output_dir / "README.md").exists()
    assert (output_dir / "artifact-manifest.json").exists()
    assert (output_dir / "SHA256SUMS").exists()


def test_gradio_submission_requires_human_approval_note(tmp_path: Path) -> None:
    gate_dir = _write_gate(tmp_path)
    client = FakeGradioClient()

    payload = build_gradio_submission_plan(
        gate_dir=gate_dir,
        output_dir=tmp_path / "gradio-plan",
        repo_files=[],
        space_config=_space_config(),
        confirm_public_upload=True,
        client_factory=lambda _: client,
    )

    assert payload["status"] == "blocked_missing_human_approval_note"
    assert payload["external_upload_performed_by_script"] is False
    assert client.calls == []


def test_confirmed_gradio_submission_calls_handle_upload(tmp_path: Path) -> None:
    gate_dir = _write_gate(tmp_path)
    client = FakeGradioClient(response="Submission uploaded. Evaluation started.")

    payload = build_gradio_submission_plan(
        gate_dir=gate_dir,
        output_dir=tmp_path / "gradio-plan",
        repo_files=[],
        space_config=_space_config(),
        confirm_public_upload=True,
        human_approval_note="user approved public CP-Bench Space upload",
        client_factory=lambda _: client,
        file_adapter=lambda path: {"path": path.name},
    )

    assert payload["status"] == "submitted_via_gradio_pending_public_result"
    assert payload["external_upload_performed_by_script"] is True
    assert payload["external_submission_status"] == "submitted"
    assert payload["official_scores_claimed"] is False
    assert client.calls == [
        {
            "args": (
                "ml_research_loop_p17",
                {"path": "submission.jsonl"},
                {"path": "approach-report.pdf"},
                "CPMpy",
                "Codex-assisted deterministic CPMPy solver expansion",
                "verified",
            ),
            "api_name": "/handle_upload",
        }
    ]


def test_parse_cp_bench_summary_extracts_official_metrics() -> None:
    metrics = parse_cp_bench_summary(_summary_text(52.38, submitted=34, successful=34))

    assert metrics == {
        "total_submitted_models_in_dataset": 34,
        "runtime_success": "34/34",
        "runtime_success_count": 34,
        "runtime_denominator": 34,
        "coverage_percent": 53.97,
        "error_percent": 0.0,
        "consistency_percent": 52.38,
        "final_solution_accuracy_percent": 52.38,
    }


def test_public_result_watch_waits_without_claiming_when_target_missing(tmp_path: Path) -> None:
    gate_dir = _write_gate(tmp_path)
    output_dir = tmp_path / "public-watch"

    payload = build_public_result_watch(
        gate_dir=gate_dir,
        output_dir=output_dir,
        repo_files=[
            "results/v1_verified/cpagent/summary.txt",
            "results/v1_verified/documentation_prompt_mnz/summary.txt",
        ],
        summary_texts={
            "results/v1_verified/cpagent/summary.txt": _summary_text(100.0),
            "results/v1_verified/documentation_prompt_mnz/summary.txt": _summary_text(46.03),
        },
    )
    report_text = (output_dir / "public-result-watch.json").read_text(encoding="utf-8")

    assert payload["status"] == "waiting_for_public_result"
    assert payload["claimable_public_result"] is False
    assert payload["target_result_exists"] is False
    assert payload["official_scores_claimed"] is False
    assert payload["external_submission_status"] == "not_submitted"
    assert payload["public_verified_leaderboard_snapshot"]["entry_count"] == 2
    assert payload["public_verified_leaderboard_snapshot"]["lowest_public_accuracy_percent"] == 46.03
    assert str(tmp_path) not in report_text
    assert (output_dir / "README.md").exists()
    assert (output_dir / "artifact-manifest.json").exists()
    assert (output_dir / "SHA256SUMS").exists()


def test_public_result_watch_parses_target_and_computes_rank(tmp_path: Path) -> None:
    gate_dir = _write_gate(tmp_path)
    target = "results/v1_verified/ml_research_loop_p17/summary.txt"

    payload = build_public_result_watch(
        gate_dir=gate_dir,
        output_dir=tmp_path / "public-watch",
        repo_files=[
            "results/v1_verified/cpagent/summary.txt",
            target,
            "results/v1_verified/documentation_prompt_mnz/summary.txt",
        ],
        summary_texts={
            "results/v1_verified/cpagent/summary.txt": _summary_text(100.0),
            target: _summary_text(52.38, submitted=34, successful=34),
            "results/v1_verified/documentation_prompt_mnz/summary.txt": _summary_text(46.03),
        },
    )

    assert payload["status"] == "public_result_available"
    assert payload["claimable_public_result"] is True
    assert payload["target_public_result"]["summary_path"] == target
    assert payload["target_public_result"]["final_solution_accuracy_percent"] == 52.38
    assert payload["target_public_result"]["public_rank"] == 2
    assert payload["target_public_result"]["public_entry_count"] == 3
    assert payload["target_public_result"]["would_beat_public_entries"] == 1
    assert payload["external_submission_status"] == "submitted"
    assert payload["official_scores_claimed"] is False


def test_upload_readiness_audit_records_blockers_without_claiming(tmp_path: Path) -> None:
    output_dir = tmp_path / "upload-readiness"

    payload = build_upload_readiness_audit(
        output_dir=output_dir,
        gradio_plan={
            "status": "blocked_space_config_unreadable",
            "would_upload": False,
            "external_upload_performed_by_script": False,
            "official_scores_claimed": False,
            "external_submission_status": "not_submitted",
            "preflight": {
                "status": "blocked_missing_hf_auth",
                "target_submission_exists": False,
                "target_result_exists": False,
                "target_submission_path": "submissions/v1_verified/ml_research_loop_p17",
                "target_result_path": "results/v1_verified/ml_research_loop_p17/summary.txt",
                "gate_validation": {"status": "valid", "errors": []},
            },
            "space_api_contract": {
                "status": "unreadable",
                "api_name": "/handle_upload",
            },
        },
        public_watch={
            "status": "waiting_for_public_result",
            "target_result_exists": False,
            "claimable_public_result": False,
            "official_scores_claimed": False,
            "external_submission_status": "not_submitted",
        },
        environment_probe={
            "gradio_client_installed": False,
            "hf_cli_installed": False,
            "huggingface_hub_installed": True,
        },
    )

    assert payload["status"] == "blocked_before_public_upload"
    assert payload["ready_for_public_upload_attempt"] is False
    assert payload["claimable_public_result"] is False
    assert payload["official_scores_claimed"] is False
    assert payload["external_submission_status"] == "not_submitted"
    assert payload["blockers"] == [
        {
            "id": "space_config_unreadable",
            "severity": "hard",
            "scope": "gradio_upload",
        },
        {
            "id": "missing_gradio_client",
            "severity": "hard",
            "scope": "scripted_gradio_upload",
        },
    ]
    report_text = (output_dir / "upload-readiness-audit.json").read_text(encoding="utf-8")
    assert str(tmp_path) not in report_text
    assert (output_dir / "README.md").exists()
    assert (output_dir / "artifact-manifest.json").exists()
    assert (output_dir / "SHA256SUMS").exists()


def test_upload_readiness_audit_identifies_approval_ready_state(tmp_path: Path) -> None:
    payload = build_upload_readiness_audit(
        output_dir=tmp_path / "upload-readiness",
        gradio_plan={
            "status": "dry_run_ready_for_human_approved_space_upload",
            "would_upload": True,
            "external_upload_performed_by_script": False,
            "official_scores_claimed": False,
            "external_submission_status": "not_submitted",
            "preflight": {
                "status": "blocked_missing_hf_auth",
                "target_submission_exists": False,
                "target_result_exists": False,
                "target_submission_path": "submissions/v1_verified/ml_research_loop_p17",
                "target_result_path": "results/v1_verified/ml_research_loop_p17/summary.txt",
                "gate_validation": {"status": "valid", "errors": []},
            },
            "space_api_contract": {
                "status": "matched",
                "api_name": "/handle_upload",
            },
        },
        public_watch={
            "status": "waiting_for_public_result",
            "target_result_exists": False,
            "claimable_public_result": False,
            "official_scores_claimed": False,
            "external_submission_status": "not_submitted",
        },
        environment_probe={
            "gradio_client_installed": True,
            "hf_cli_installed": False,
            "huggingface_hub_installed": True,
        },
    )

    assert payload["status"] == "ready_for_explicit_public_upload_approval"
    assert payload["ready_for_public_upload_attempt"] is True
    assert payload["blockers"] == []
    assert payload["non_blocking_notes"] == [
        {
            "id": "hf_auth_missing_for_direct_storage",
            "scope": "direct_storage_upload",
        },
        {
            "id": "hf_cli_missing",
            "scope": "manual_diagnostics",
        }
    ]
    assert payload["next_action"] == "request_explicit_human_approval_for_cp_bench_space_upload"


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


class FakeGradioClient:
    def __init__(self, *, response: str = "not called") -> None:
        self.response = response
        self.calls: list[dict[str, object]] = []

    def predict(self, *args: object, api_name: str) -> str:
        self.calls.append({"args": args, "api_name": api_name})
        return self.response


def _space_config() -> dict[str, object]:
    return {
        "dependencies": [
            {
                "id": 2,
                "api_name": "handle_upload",
                "inputs": [7, 13, 12, 8, 9, 10],
                "outputs": [15],
                "show_api": True,
            }
        ],
        "components": [
            {"id": 7, "type": "textbox", "props": {"label": "Submission Name (required)"}},
            {
                "id": 13,
                "type": "file",
                "props": {"label": "Upload Submission File (required, .jsonl)"},
            },
            {
                "id": 12,
                "type": "file",
                "props": {"label": "Upload PDF Report (optional, but recommended)"},
            },
            {"id": 8, "type": "dropdown", "props": {"label": "Modelling Framework (required)"}},
            {"id": 9, "type": "textbox", "props": {"label": "Base LLM (required)"}},
            {"id": 10, "type": "dropdown", "props": {"label": "Dataset Version (required)"}},
            {"id": 15, "type": "textbox", "props": {"label": "Status"}},
        ],
    }


def _summary_text(
    final_accuracy: float,
    *,
    submitted: int = 63,
    successful: int = 63,
) -> str:
    return f"""Ground-Truth Dataset: kostis-init/CP-Bench, Version: verified
------------------------------

==============================
Overall Evaluation Statistics:
  Total Submitted Models that also exist in the dataset: {submitted}
  Models That Ran Successfully (out of submitted models): {successful}/{submitted}
  Submission coverage perc: 53.97%
  Error perc: 0.00%
  Consistency perc: {final_accuracy:.2f}%
  Final Solution Accuracy perc: {final_accuracy:.2f}%
------------------------------
"""
