import json
import subprocess
import sys

from lib.reproduction_pilot import (
    PaperCandidate,
    PilotRunConfig,
    build_research_case_from_selection,
    evaluate_paper_candidate,
    probe_pilot_environment,
    reject_candidate,
    write_pilot_evidence_indexes,
    write_pilot_proof_archive,
    run_bounded_pilot_experiment,
    run_guarded_pilot_iteration,
    write_fixture_dataset,
    write_human_review_report,
    write_public_memflow_slice,
    write_research_case,
)


def test_candidate_requires_public_paper_metric_data_and_bounded_claim() -> None:
    candidate = PaperCandidate(
        paper_id="arxiv:2605.03312",
        title="MemFlow: Intent-Driven Memory Orchestration for Small Language Model Agents",
        arxiv_url="https://arxiv.org/abs/2605.03312",
        task="bounded memory-routing ablation",
        metric="accuracy",
        dataset_plan="small public or fixture-backed substitute dataset",
        algorithm_plan="minimal intent-router ablation",
        resource_budget_minutes=15,
        target_claim="intent-driven routing improves evidence selection on the bounded task",
        official_scores_claimed=False,
    )

    report = evaluate_paper_candidate(candidate)

    assert report.decision == "accepted_for_pilot"
    assert report.official_scores_claimed is False
    assert not report.reject_reasons
    assert report.task == "bounded memory-routing ablation"
    assert report.target_metric == "accuracy"


def test_candidate_rejects_missing_required_selection_inputs() -> None:
    candidate = PaperCandidate(
        paper_id="arxiv:2605.03312",
        title="MemFlow: Intent-Driven Memory Orchestration for Small Language Model Agents",
        arxiv_url="",
        task="",
        metric="",
        dataset_plan="",
        algorithm_plan="",
        resource_budget_minutes=15,
        target_claim="",
        official_scores_claimed=True,
    )

    report = evaluate_paper_candidate(candidate)

    assert report.decision == "rejected"
    assert report.official_scores_claimed is True
    assert report.reject_reasons == [
        "missing_arxiv_url",
        "missing_task",
        "missing_metric",
        "missing_dataset_plan",
        "missing_target_claim",
        "missing_algorithm_plan",
        "official_scores_claimed_not_allowed",
    ]


def test_candidate_blocks_budget_above_default_limit() -> None:
    candidate = PaperCandidate(
        paper_id="arxiv:2605.03312",
        title="MemFlow: Intent-Driven Memory Orchestration for Small Language Model Agents",
        arxiv_url="https://arxiv.org/abs/2605.03312",
        task="bounded memory-routing ablation",
        metric="accuracy",
        dataset_plan="small public or fixture-backed substitute dataset",
        algorithm_plan="minimal intent-router ablation",
        resource_budget_minutes=16,
        target_claim="intent-driven routing improves evidence selection on the bounded task",
        official_scores_claimed=False,
    )

    report = evaluate_paper_candidate(candidate)

    assert report.decision == "requires_override"
    assert report.reject_reasons == ["resource_budget_exceeds_default_limit"]


def test_reject_candidate_preserves_candidate_fields() -> None:
    candidate = PaperCandidate(
        paper_id="arxiv:2605.03312",
        title="MemFlow: Intent-Driven Memory Orchestration for Small Language Model Agents",
        arxiv_url="https://arxiv.org/abs/2605.03312",
        task="bounded memory-routing ablation",
        metric="accuracy",
        dataset_plan="small public or fixture-backed substitute dataset",
        algorithm_plan="minimal intent-router ablation",
        resource_budget_minutes=15,
        target_claim="intent-driven routing improves evidence selection on the bounded task",
        official_scores_claimed=False,
    )

    report = reject_candidate(candidate, ["manual_rejection"])

    assert report.decision == "rejected"
    assert report.reject_reasons == ["manual_rejection"]
    assert report.paper_id == candidate.paper_id
    assert report.target_metric == candidate.metric


def test_select_only_cli_writes_memflow_selection_report(tmp_path) -> None:
    output_dir = tmp_path / "memflow"

    result = subprocess.run(
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

    stdout_payload = json.loads(result.stdout)
    report_path = output_dir / "paper-selection-report.json"
    artifact_payload = json.loads(report_path.read_text())

    assert stdout_payload == artifact_payload
    assert artifact_payload["paper_id"] == "arxiv:2605.03312"
    assert (
        artifact_payload["title"]
        == "MemFlow: Intent-Driven Memory Orchestration for Small Language Model Agents"
    )
    assert artifact_payload["arxiv_url"] == "https://arxiv.org/abs/2605.03312"
    assert artifact_payload["task"] == "bounded memory-routing ablation"
    assert artifact_payload["target_metric"] == "accuracy"
    assert artifact_payload["dataset_plan"]
    assert artifact_payload["algorithm_plan"]
    assert artifact_payload["resource_budget_minutes"] == 15
    assert artifact_payload["decision"] == "accepted_for_pilot"
    assert artifact_payload["reject_reasons"] == []
    assert artifact_payload["official_scores_claimed"] is False


def test_build_research_case_from_selection_records_claim_boundaries(tmp_path) -> None:
    candidate = PaperCandidate(
        paper_id="arxiv:2605.03312",
        title="MemFlow: Intent-Driven Memory Orchestration for Small Language Model Agents",
        arxiv_url="https://arxiv.org/abs/2605.03312",
        task="bounded memory-routing ablation",
        metric="accuracy",
        dataset_plan="small public or fixture-backed substitute dataset",
        algorithm_plan="minimal intent-router ablation",
        resource_budget_minutes=15,
        target_claim="intent-driven routing improves evidence selection on the bounded task",
        official_scores_claimed=False,
    )
    report = evaluate_paper_candidate(candidate)

    case = build_research_case_from_selection(
        report,
        selection_artifact_path=tmp_path / "paper-selection-report.json",
    )

    assert case.case_id == "real-paper-pilot-arxiv-2605-03312"
    assert "bounded" in case.objective
    assert case.official_scores_claimed is False
    assert case.claims[0].claim_id == "claim-memflow-bounded"
    assert case.claims[0].status == "needs_evidence"
    assert case.claims[0].evidence_refs[0].source_id == "arxiv:2605.03312"
    assert "official benchmark score" in case.forbidden_claims
    assert "full SOTA reproduction" in case.forbidden_claims


def test_write_research_case_persists_json_summary(tmp_path) -> None:
    candidate = PaperCandidate(
        paper_id="arxiv:2605.03312",
        title="MemFlow: Intent-Driven Memory Orchestration for Small Language Model Agents",
        arxiv_url="https://arxiv.org/abs/2605.03312",
        task="bounded memory-routing ablation",
        metric="accuracy",
        dataset_plan="small public or fixture-backed substitute dataset",
        algorithm_plan="minimal intent-router ablation",
        resource_budget_minutes=15,
        target_claim="intent-driven routing improves evidence selection on the bounded task",
        official_scores_claimed=False,
    )
    case = build_research_case_from_selection(
        evaluate_paper_candidate(candidate),
        selection_artifact_path=tmp_path / "paper-selection-report.json",
    )

    case_path = write_research_case(case, tmp_path)
    payload = json.loads(case_path.read_text(encoding="utf-8"))

    assert case_path.name == "research-case.json"
    assert payload["case_id"] == "real-paper-pilot-arxiv-2605-03312"
    assert payload["official_scores_claimed"] is False
    assert payload["forbidden_claims"]


def test_pilot_probe_reports_repair_plan_when_dataset_missing(tmp_path) -> None:
    config = PilotRunConfig(
        case_id="case-memflow-mini",
        data_path=tmp_path / "missing-dataset.jsonl",
        output_dir=tmp_path / "out",
        max_runtime_seconds=60,
    )

    report = probe_pilot_environment(config)

    assert report.status == "blocked"
    assert "dataset_missing" in report.blockers
    assert "pytest" in report.package_status
    assert report.package_status["pytest"] in {"available", "missing"}
    assert report.repair_plan
    assert report.official_scores_claimed is False


def test_pilot_probe_blocks_malformed_dataset_without_traceback(tmp_path) -> None:
    data_path = tmp_path / "data" / "pilot.jsonl"
    data_path.parent.mkdir(parents=True)
    data_path.write_text("{not-json}\n", encoding="utf-8")

    report = probe_pilot_environment(
        PilotRunConfig(
            case_id="case-memflow-mini",
            data_path=data_path,
            output_dir=tmp_path / "out",
            max_runtime_seconds=60,
        )
    )

    assert report.status == "blocked"
    assert "dataset_malformed_jsonl" in report.blockers
    assert any(entry["kind"] == "fix_dataset_format" for entry in report.repair_plan)
    assert report.official_scores_claimed is False


def test_probe_only_cli_writes_environment_probe_and_research_case(tmp_path) -> None:
    output_dir = tmp_path / "memflow"

    result = subprocess.run(
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

    stdout_payload = json.loads(result.stdout)
    probe_path = output_dir / "environment-probe.json"
    case_path = output_dir / "research-case.json"

    assert stdout_payload["status"] in {"ready", "blocked"}
    assert probe_path.exists()
    assert case_path.exists()
    assert stdout_payload["environment_probe"] == str(probe_path)
    assert stdout_payload["research_case"] == str(case_path)


def test_run_baseline_cli_with_bad_data_returns_structured_blocked_payload(tmp_path) -> None:
    output_dir = tmp_path / "memflow"
    data_path = tmp_path / "bad.jsonl"
    data_path.write_text("{}\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            "scripts/real_paper_reproduction_pilot.py",
            "--paper-id",
            "arxiv:2605.03312",
            "--output-dir",
            str(output_dir),
            "--data-path",
            str(data_path),
            "--run-baseline",
            "--json",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)

    assert result.returncode == 1
    assert result.stderr == ""
    assert payload["status"] == "blocked"
    assert "dataset_missing_required_fields" in payload["blockers"]
    assert payload["official_scores_claimed"] is False


def test_bounded_pilot_experiment_writes_metrics_and_client_handoff(tmp_path) -> None:
    data_path = tmp_path / "data" / "pilot.jsonl"
    output_dir = tmp_path / "out"
    write_fixture_dataset(data_path)
    config = PilotRunConfig(
        case_id="real-paper-pilot-arxiv-2605-03312",
        data_path=data_path,
        output_dir=output_dir,
        max_runtime_seconds=60,
    )

    result = run_bounded_pilot_experiment(
        config,
        target_claim="intent-driven routing improves evidence selection on the bounded task",
        metric_name="selection_accuracy",
        substitute_data=True,
    )

    assert result.status == "completed"
    assert result.metric_name == "selection_accuracy"
    assert result.baseline_metric < result.ablation_metric
    assert result.substitute_data is True
    assert result.official_scores_claimed is False

    for artifact in result.artifacts.values():
        assert artifact.exists()

    baseline = json.loads(result.artifacts["baseline_metrics"].read_text())
    handoff = json.loads(result.artifacts["client_handoff"].read_text())

    assert baseline["substitute_data"] is True
    assert baseline["official_scores_claimed"] is False
    assert handoff["allowed_patch_scope"] == [
        "fixture dataset records",
        "routing heuristic configuration",
    ]
    assert handoff["stop_rules"]


def test_public_memflow_slice_writes_source_provenance(tmp_path) -> None:
    data_path = tmp_path / "data" / "public-memflow.jsonl"

    result = write_public_memflow_slice(data_path)

    assert result == data_path
    records = [
        json.loads(line)
        for line in data_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(records) >= 4
    assert all(record["source"]["kind"] == "public_arxiv_metadata" for record in records)
    assert all(record["source"]["url"] == "https://arxiv.org/abs/2605.03312" for record in records)
    assert all(record["source"]["verbatim_excerpt"] is False for record in records)


def test_bounded_pilot_public_slice_marks_non_substitute_handoff(tmp_path) -> None:
    data_path = tmp_path / "data" / "public-memflow.jsonl"
    output_dir = tmp_path / "out"
    write_public_memflow_slice(data_path)
    config = PilotRunConfig(
        case_id="real-paper-pilot-arxiv-2605-03312",
        data_path=data_path,
        output_dir=output_dir,
        max_runtime_seconds=60,
    )

    result = run_bounded_pilot_experiment(
        config,
        target_claim="intent-driven routing improves evidence selection on the bounded task",
        metric_name="selection_accuracy",
        substitute_data=False,
    )

    summary = json.loads((output_dir / "experiment-summary.json").read_text())
    provenance = json.loads((output_dir / "dataset-provenance.json").read_text())
    handoff = json.loads((output_dir / "client-handoff.json").read_text())

    assert result.substitute_data is False
    assert summary["substitute_data"] is False
    assert provenance["data_kind"] == "local_public_data"
    assert provenance["source_url"] == "https://arxiv.org/abs/2605.03312"
    assert handoff["case_summary"]["data_kind"] == "local_public_data"
    assert "public mini-slice records" in handoff["allowed_patch_scope"]
    assert "substitute-data metric" not in handoff["failure_or_gap"]


def test_run_baseline_cli_with_fixture_writes_metrics_and_handoff(tmp_path) -> None:
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
    assert payload["substitute_data"] is True
    assert payload["official_scores_claimed"] is False
    assert payload["metric_after"] > payload["metric_before"]
    assert (output_dir / "baseline-metrics.json").exists()
    assert (output_dir / "ablation-metrics.json").exists()
    assert (output_dir / "experiment-summary.json").exists()
    assert (output_dir / "client-handoff.json").exists()


def test_guarded_pilot_iteration_writes_patch_and_comparison(tmp_path) -> None:
    data_path = tmp_path / "data" / "pilot.jsonl"
    output_dir = tmp_path / "out"
    write_fixture_dataset(data_path)
    config = PilotRunConfig(
        case_id="real-paper-pilot-arxiv-2605-03312",
        data_path=data_path,
        output_dir=output_dir,
        max_runtime_seconds=60,
    )
    run_bounded_pilot_experiment(
        config,
        target_claim="intent-driven routing improves evidence selection on the bounded task",
        metric_name="selection_accuracy",
        substitute_data=True,
    )

    result = run_guarded_pilot_iteration(
        config,
        target_claim="intent-driven routing improves evidence selection on the bounded task",
        metric_name="selection_accuracy",
        substitute_data=True,
    )

    assert result["status"] == "completed"
    assert result["metric_before"] == 0.5
    assert result["metric_after"] == 1.0
    assert result["delta"] == 0.5
    assert result["decision"] == "continue"
    assert result["official_scores_claimed"] is False

    patch_payload = json.loads((output_dir / "client-routing-patch.json").read_text())
    comparison = json.loads((output_dir / "iteration-comparison.json").read_text())

    assert patch_payload["patch_kind"] == "routing_config"
    assert patch_payload["patch_applied"] is True
    assert patch_payload["allowed_patch_scope"] == ["routing heuristic configuration"]
    assert comparison["why"]
    assert comparison["next_recommended_action"]
    assert comparison["official_scores_claimed"] is False


def test_human_review_report_records_claim_boundaries(tmp_path) -> None:
    output_dir = tmp_path / "out"
    data_path = output_dir / "data" / "pilot.jsonl"
    write_public_memflow_slice(data_path)
    config = PilotRunConfig(
        case_id="real-paper-pilot-arxiv-2605-03312",
        data_path=data_path,
        output_dir=output_dir,
        max_runtime_seconds=60,
    )
    run_bounded_pilot_experiment(
        config,
        target_claim="intent-driven routing improves evidence selection on the bounded task",
        metric_name="selection_accuracy",
        substitute_data=False,
    )
    run_guarded_pilot_iteration(
        config,
        target_claim="intent-driven routing improves evidence selection on the bounded task",
        metric_name="selection_accuracy",
        substitute_data=False,
    )

    report_path = write_human_review_report(
        output_dir=output_dir,
        paper_id="arxiv:2605.03312",
        claim="intent-driven routing improves evidence selection on the bounded task",
        reviewer="local-operator",
        decision="approved_with_limitations",
    )

    report = json.loads(report_path.read_text())

    assert report_path.name == "human-review-report.json"
    assert report["review_status"] == "approved_with_limitations"
    assert report["reviewer"] == "local-operator"
    assert report["claim_strength"] == "local_public_data"
    assert report["official_scores_claimed"] is False
    assert report["human_review_required_for_stronger_claims"] is True
    assert all(item["status"] == "passed" for item in report["checklist"])
    assert "official benchmark" in " ".join(report["blocked_public_claims"])


def test_run_iteration_cli_without_baseline_returns_blocked_payload(tmp_path) -> None:
    output_dir = tmp_path / "memflow"

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
        check=False,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)

    assert result.returncode == 1
    assert result.stderr == ""
    assert payload["status"] == "blocked"
    assert payload["blockers"] == ["missing_baseline_metrics"]
    assert payload["official_scores_claimed"] is False


def test_run_iteration_cli_with_fixture_writes_iteration_comparison(tmp_path) -> None:
    output_dir = tmp_path / "memflow"
    baseline_command = [
        sys.executable,
        "scripts/real_paper_reproduction_pilot.py",
        "--paper-id",
        "arxiv:2605.03312",
        "--output-dir",
        str(output_dir),
        "--run-baseline",
        "--use-fixture-data",
        "--json",
    ]
    subprocess.run(baseline_command, check=True, capture_output=True, text=True)

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
    assert payload["metric_after"] > payload["metric_before"]
    assert payload["official_scores_claimed"] is False
    assert (output_dir / "client-routing-patch.json").exists()
    assert (output_dir / "patched-metrics.json").exists()
    assert (output_dir / "iteration-comparison.json").exists()


def test_write_pilot_proof_archive_hashes_required_artifacts(tmp_path) -> None:
    output_dir = tmp_path / "memflow"
    proof_dir = tmp_path / "proof"
    data_path = output_dir / "data" / "pilot.jsonl"
    write_fixture_dataset(data_path)
    config = PilotRunConfig(
        case_id="real-paper-pilot-arxiv-2605-03312",
        data_path=data_path,
        output_dir=output_dir,
        max_runtime_seconds=60,
    )
    candidate = PaperCandidate(
        paper_id="arxiv:2605.03312",
        title="MemFlow: Intent-Driven Memory Orchestration for Small Language Model Agents",
        arxiv_url="https://arxiv.org/abs/2605.03312",
        task="bounded memory-routing ablation",
        metric="accuracy",
        dataset_plan="small public or fixture-backed substitute dataset",
        algorithm_plan="minimal intent-router ablation",
        resource_budget_minutes=15,
        target_claim="intent-driven routing improves evidence selection on the bounded task",
        official_scores_claimed=False,
    )
    selection = evaluate_paper_candidate(candidate)
    selection_path = output_dir / "paper-selection-report.json"
    output_dir.mkdir(parents=True, exist_ok=True)
    selection_path.write_text(json.dumps(selection.to_dict()), encoding="utf-8")
    case = build_research_case_from_selection(
        selection,
        selection_artifact_path=selection_path,
    )
    write_research_case(case, output_dir)
    probe = probe_pilot_environment(config)
    (output_dir / "environment-probe.json").write_text(
        json.dumps(probe.to_dict()),
        encoding="utf-8",
    )
    run_bounded_pilot_experiment(
        config,
        target_claim=candidate.target_claim,
        metric_name="selection_accuracy",
        substitute_data=True,
    )
    run_guarded_pilot_iteration(
        config,
        target_claim=candidate.target_claim,
        metric_name="selection_accuracy",
        substitute_data=True,
    )
    write_human_review_report(
        output_dir=output_dir,
        paper_id=candidate.paper_id,
        claim=candidate.target_claim,
        reviewer="local-operator",
        decision="approved_with_limitations",
    )

    result = write_pilot_proof_archive(
        output_dir=output_dir,
        proof_dir=proof_dir,
        paper_id=candidate.paper_id,
        claim=candidate.target_claim,
        commands=[
            "python3 scripts/real_paper_reproduction_pilot.py --run-baseline --use-fixture-data",
            "python3 scripts/real_paper_reproduction_pilot.py --run-iteration --use-fixture-data",
        ],
    )

    manifest_path = proof_dir / "proof-manifest.json"
    manifest = json.loads(manifest_path.read_text())

    assert result["status"] == "completed"
    assert result["proof_manifest"] == str(manifest_path)
    assert manifest["case_id"] == "real-paper-pilot-arxiv-2605-03312"
    assert manifest["paper_id"] == "arxiv:2605.03312"
    assert manifest["claim_strength"] == "local_substitute_data"
    assert manifest["official_scores_claimed"] is False
    assert manifest["metric_summary"]["metric_before"] == 0.5
    assert manifest["metric_summary"]["metric_after"] == 1.0
    assert manifest["limitations"]
    assert manifest["review_status"] == "approved_with_limitations"
    assert manifest["artifact_sha256"]["human_review_report"]
    assert len(manifest["artifacts"]) >= 13
    assert all(item["sha256"] for item in manifest["artifacts"])
    assert all(not item["source_path"].startswith("/") for item in manifest["artifacts"])
    assert all((proof_dir / item["archive_path"]).exists() for item in manifest["artifacts"])
    for item in manifest["artifacts"]:
        archived_text = (proof_dir / item["archive_path"]).read_text(encoding="utf-8")
        assert str(tmp_path) not in archived_text


def test_write_pilot_proof_archive_blocks_when_required_artifact_missing(tmp_path) -> None:
    output_dir = tmp_path / "memflow"
    proof_dir = tmp_path / "proof"
    output_dir.mkdir()
    (output_dir / "paper-selection-report.json").write_text("{}", encoding="utf-8")

    result = write_pilot_proof_archive(
        output_dir=output_dir,
        proof_dir=proof_dir,
        paper_id="arxiv:2605.03312",
        claim="bounded claim",
        commands=[],
    )

    assert result["status"] == "blocked"
    assert "missing_required_artifacts" in result["blockers"]
    assert not (proof_dir / "proof-manifest.json").exists()


def test_write_pilot_evidence_indexes_maps_public_claims(tmp_path) -> None:
    proof_dir = tmp_path / "proof"
    proof_dir.mkdir()
    manifest_path = proof_dir / "proof-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "case_id": "real-paper-pilot-arxiv-2605-03312",
                "paper_id": "arxiv:2605.03312",
                "claim": "bounded claim",
                "claim_strength": "local_substitute_data",
                "official_scores_claimed": False,
                "metric_summary": {"metric_before": 0.5, "metric_after": 1.0},
                "limitations": ["fixture-backed substitute data"],
                "review_status": "approved_with_limitations",
            }
        ),
        encoding="utf-8",
    )

    result = write_pilot_evidence_indexes(
        manifest_path=manifest_path,
        evidence_dir=tmp_path / "docs" / "evidence",
    )

    pilot_index = json.loads(result["pilot_index"].read_text())
    claims_map = json.loads(result["public_claims_map"].read_text())

    assert pilot_index["official_scores_claimed"] is False
    assert pilot_index["entries"][0]["claim_strength"] == "local_substitute_data"
    assert not pilot_index["entries"][0]["proof_manifest"].startswith("/")
    assert claims_map["official_scores_claimed"] is False
    assert claims_map["public_claims"][0]["claim_id"] == "real-paper-pilot-local-proof"
    assert claims_map["public_claims"][0]["proof_matrix_entry"] == "Real paper pilot"
    assert not claims_map["public_claims"][0]["evidence"].startswith("/")
    assert claims_map["claims"][0]["public_claim_status"] == "allowed_with_boundary"
    assert claims_map["claims"][1]["public_claim_status"] == "blocked"


def test_write_pilot_evidence_indexes_blocks_unreviewed_public_claim(tmp_path) -> None:
    proof_dir = tmp_path / "proof"
    proof_dir.mkdir()
    manifest_path = proof_dir / "proof-manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "case_id": "real-paper-pilot-arxiv-2605-03312",
                "paper_id": "arxiv:2605.03312",
                "claim": "bounded claim",
                "claim_strength": "local_public_data",
                "official_scores_claimed": False,
                "metric_summary": {"metric_before": 0.25, "metric_after": 1.0},
                "limitations": ["public mini-slice only"],
                "review_status": "local_artifacts_ready_for_review",
            }
        ),
        encoding="utf-8",
    )

    result = write_pilot_evidence_indexes(
        manifest_path=manifest_path,
        evidence_dir=tmp_path / "docs" / "evidence",
    )

    claims_map = json.loads(result["public_claims_map"].read_text())

    assert claims_map["claims"][0]["public_claim_status"] == "blocked_pending_review"
