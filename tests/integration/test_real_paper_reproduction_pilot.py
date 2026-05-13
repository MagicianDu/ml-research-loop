from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_real_paper_pilot_select_and_probe_cli_outputs_expected_artifacts(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "memflow"

    select_result = subprocess.run(
        [
            sys.executable,
            "scripts/real_paper_reproduction_pilot.py",
            "--paper-id",
            "arxiv:2605.03312",
            "--output-dir",
            str(output_dir),
            "--select-only",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    selection = json.loads(select_result.stdout)

    assert selection["decision"] == "accepted_for_pilot"
    assert selection["official_scores_claimed"] is False
    assert (output_dir / "paper-selection-report.json").exists()

    probe_result = subprocess.run(
        [
            sys.executable,
            "scripts/real_paper_reproduction_pilot.py",
            "--paper-id",
            "arxiv:2605.03312",
            "--output-dir",
            str(output_dir),
            "--probe-only",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    probe = json.loads(probe_result.stdout)

    assert probe["status"] == "blocked"
    assert "dataset_missing" in probe["blockers"]
    assert probe["official_scores_claimed"] is False
    assert (output_dir / "research-case.json").exists()
    assert (output_dir / "environment-probe.json").exists()

    case_payload = json.loads((output_dir / "research-case.json").read_text())
    env_payload = json.loads((output_dir / "environment-probe.json").read_text())

    assert case_payload["case_id"] == "real-paper-pilot-arxiv-2605-03312"
    assert case_payload["official_scores_claimed"] is False
    assert "official benchmark score" in case_payload["forbidden_claims"]
    assert env_payload["status"] == "blocked"
    assert "dataset_missing" in env_payload["blockers"]


def test_real_paper_pilot_probe_with_public_mini_slice_is_ready(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "memflow-public"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/real_paper_reproduction_pilot.py",
            "--paper-id",
            "arxiv:2605.03312",
            "--output-dir",
            str(output_dir),
            "--probe-only",
            "--use-public-mini-slice",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)
    env_payload = json.loads((output_dir / "environment-probe.json").read_text())

    assert payload["status"] == "ready"
    assert payload["blockers"] == []
    assert env_payload["data_valid"] is True
    assert (output_dir / "data" / "pilot.jsonl").exists()


def test_real_paper_pilot_run_baseline_with_fixture_outputs_metrics(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "memflow"

    result = subprocess.run(
        [
            sys.executable,
            "scripts/real_paper_reproduction_pilot.py",
            "--paper-id",
            "arxiv:2605.03312",
            "--output-dir",
            str(output_dir),
            "--run-baseline",
            "--use-fixture-data",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "completed"
    assert payload["metric_name"] == "selection_accuracy"
    assert payload["metric_after"] > payload["metric_before"]
    assert payload["substitute_data"] is True
    assert payload["official_scores_claimed"] is False

    for path in [
        output_dir / "baseline-metrics.json",
        output_dir / "ablation-metrics.json",
        output_dir / "experiment-summary.json",
        output_dir / "run-log.txt",
        output_dir / "client-handoff.json",
    ]:
        assert path.exists()

    summary = json.loads((output_dir / "experiment-summary.json").read_text())
    handoff = json.loads((output_dir / "client-handoff.json").read_text())

    assert summary["decision"] == "continue"
    assert summary["official_scores_claimed"] is False
    assert handoff["metric_after"] == payload["metric_after"]
    assert "stop before claiming official benchmark" in " ".join(handoff["stop_rules"])


def test_real_paper_pilot_public_mini_slice_archive_keeps_claim_boundary(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "memflow-public"
    proof_dir = tmp_path / "proof_runs" / "real-paper-pilot" / "memflow"
    evidence_dir = tmp_path / "docs" / "evidence"

    for mode in ["--run-baseline", "--run-iteration"]:
        result = subprocess.run(
            [
                sys.executable,
                "scripts/real_paper_reproduction_pilot.py",
                "--paper-id",
                "arxiv:2605.03312",
                "--output-dir",
                str(output_dir),
                mode,
                "--use-public-mini-slice",
                "--json",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        payload = json.loads(result.stdout)
        assert payload["official_scores_claimed"] is False
        assert payload["substitute_data"] is False

    review_result = subprocess.run(
        [
            sys.executable,
            "scripts/real_paper_reproduction_pilot.py",
            "--paper-id",
            "arxiv:2605.03312",
            "--output-dir",
            str(output_dir),
            "--write-review-report",
            "--reviewer",
            "local-operator",
            "--review-decision",
            "approved_with_limitations",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    review_payload = json.loads(review_result.stdout)
    assert review_payload["status"] == "completed"
    assert review_payload["review_status"] == "approved_with_limitations"
    assert (output_dir / "human-review-report.json").exists()

    archive_result = subprocess.run(
        [
            sys.executable,
            "scripts/real_paper_reproduction_pilot.py",
            "--paper-id",
            "arxiv:2605.03312",
            "--output-dir",
            str(output_dir),
            "--archive-proof",
            "--proof-dir",
            str(proof_dir),
            "--evidence-dir",
            str(evidence_dir),
            "--update-evidence-index",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    archive_payload = json.loads(archive_result.stdout)
    manifest = json.loads((proof_dir / "proof-manifest.json").read_text())
    pilot_index = json.loads((evidence_dir / "real-paper-pilot-index.json").read_text())
    claims_map = json.loads((evidence_dir / "public-claims-map.json").read_text())

    assert archive_payload["artifact_count"] >= 13
    assert manifest["claim_strength"] == "local_public_data"
    assert manifest["official_scores_claimed"] is False
    assert manifest["artifact_sha256"]["dataset_provenance"]
    assert manifest["artifact_sha256"]["human_review_report"]
    assert manifest["review_status"] == "approved_with_limitations"
    assert manifest["metric_summary"]["substitute_data"] is False
    assert any("public mini-slice" in limitation for limitation in manifest["limitations"])
    assert pilot_index["entries"][0]["claim_strength"] == "local_public_data"
    assert claims_map["public_claims"][0]["claim_id"] == "real-paper-pilot-public-slice-proof"
    assert "not an official score" in claims_map["public_claims"][0]["claim_boundary"]


def test_real_paper_pilot_run_iteration_after_baseline_outputs_comparison(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "memflow"
    subprocess.run(
        [
            sys.executable,
            "scripts/real_paper_reproduction_pilot.py",
            "--paper-id",
            "arxiv:2605.03312",
            "--output-dir",
            str(output_dir),
            "--run-baseline",
            "--use-fixture-data",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/real_paper_reproduction_pilot.py",
            "--paper-id",
            "arxiv:2605.03312",
            "--output-dir",
            str(output_dir),
            "--run-iteration",
            "--use-fixture-data",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "completed"
    assert payload["decision"] == "continue"
    assert payload["metric_before"] == 0.5
    assert payload["metric_after"] == 1.0
    assert payload["official_scores_claimed"] is False
    assert (output_dir / "client-routing-patch.json").exists()
    assert (output_dir / "patched-metrics.json").exists()
    assert (output_dir / "iteration-comparison.json").exists()


def test_real_paper_pilot_archive_proof_writes_manifest_and_indexes(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "memflow"
    proof_dir = tmp_path / "proof_runs" / "real-paper-pilot" / "memflow"
    evidence_dir = tmp_path / "docs" / "evidence"
    for mode in ["--run-baseline", "--run-iteration"]:
        subprocess.run(
            [
                sys.executable,
                "scripts/real_paper_reproduction_pilot.py",
                "--paper-id",
                "arxiv:2605.03312",
                "--output-dir",
                str(output_dir),
                mode,
                "--use-fixture-data",
                "--json",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    subprocess.run(
        [
            sys.executable,
            "scripts/real_paper_reproduction_pilot.py",
            "--paper-id",
            "arxiv:2605.03312",
            "--output-dir",
            str(output_dir),
            "--write-review-report",
            "--reviewer",
            "local-operator",
            "--review-decision",
            "approved_with_limitations",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    result = subprocess.run(
        [
            sys.executable,
            "scripts/real_paper_reproduction_pilot.py",
            "--paper-id",
            "arxiv:2605.03312",
            "--output-dir",
            str(output_dir),
            "--archive-proof",
            "--proof-dir",
            str(proof_dir),
            "--evidence-dir",
            str(evidence_dir),
            "--update-evidence-index",
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    payload = json.loads(result.stdout)

    assert payload["status"] == "completed"
    assert payload["official_scores_claimed"] is False
    assert (proof_dir / "proof-manifest.json").exists()
    assert (evidence_dir / "real-paper-pilot-index.json").exists()
    assert (evidence_dir / "public-claims-map.json").exists()

    manifest = json.loads((proof_dir / "proof-manifest.json").read_text())
    assert manifest["claim_strength"] == "local_substitute_data"
    assert manifest["artifact_sha256"]["human_review_report"]
    assert manifest["artifact_sha256"]["iteration_comparison"]
