from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib import mcp_service
from lib.benchmarks.hf_external_eval import (
    build_hf_external_eval_plan,
    load_hf_eval_targets,
    select_hf_eval_targets,
    write_hf_external_eval_plan,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_load_hf_eval_targets_preserves_claim_boundary() -> None:
    payload = load_hf_eval_targets()

    assert payload["official_scores_claimed"] is False
    assert len(payload["targets"]) >= 5
    assert payload["selection_policy"]["preferred_first_pilot"] == (
        "cp-bench-constraint-modeling"
    )
    for target in payload["targets"]:
        assert target["claim_boundary"]
        assert target["product_fit_score"] in {1, 2, 3, 4, 5}
        assert all(url.startswith("https://") for url in target["urls"].values())
        assert "leaderboard" in json.dumps(target, ensure_ascii=False).lower() or (
            target["hf_kind"] in {"competition_platform", "competition_space", "eval_results"}
        )


def test_select_hf_eval_targets_prefers_high_product_fit() -> None:
    payload = load_hf_eval_targets()

    targets = select_hf_eval_targets(payload, limit=2)

    assert [target["target_id"] for target in targets] == [
        "cp-bench-constraint-modeling",
        "aitx-challenge-model-space",
    ]


def test_build_hf_external_eval_plan_uses_preferred_target_by_default() -> None:
    plan = build_hf_external_eval_plan()

    assert plan["status"] == "planned"
    assert plan["official_scores_claimed"] is False
    assert plan["target"]["target_id"] == "cp-bench-constraint-modeling"
    assert plan["default_next_step"].startswith("Run live verification")
    assert "official HF leaderboard score" in plan["blocked_public_claims"][0]
    assert [phase["phase"] for phase in plan["phases"]] == ["P0", "P1", "P2", "P3"]


def test_write_hf_external_eval_plan_writes_json_and_markdown(tmp_path: Path) -> None:
    result = write_hf_external_eval_plan(
        tmp_path / "hf-plan",
        target_id="turingbench-2-questions",
    )

    json_path = Path(result["json_path"])
    markdown_path = Path(result["markdown_path"])
    assert result["status"] == "written"
    assert result["official_scores_claimed"] is False
    assert result["target_id"] == "turingbench-2-questions"
    assert json_path.exists()
    assert markdown_path.exists()

    payload = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")
    assert payload["target"]["target_id"] == "turingbench-2-questions"
    assert payload["official_scores_claimed"] is False
    assert "official_scores_claimed: `false`" in markdown
    assert "TuringBench" in markdown
    assert "Blocked Public Claims" in markdown


def test_load_hf_eval_targets_rejects_official_score_claims(tmp_path: Path) -> None:
    shortlist = tmp_path / "shortlist.json"
    source = json.loads(
        (PROJECT_ROOT / "docs/hf-evaluation/target-shortlist.json").read_text(
            encoding="utf-8"
        )
    )
    source["official_scores_claimed"] = True
    shortlist.write_text(json.dumps(source, ensure_ascii=False), encoding="utf-8")

    with pytest.raises(ValueError, match="official_scores_claimed=false"):
        load_hf_eval_targets(shortlist)


def test_hf_external_eval_mcp_tools_are_exposed_and_safe(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ML_RESEARCH_LOOP_ALLOWED_ROOTS", str(tmp_path))

    tool_names = {tool["name"] for tool in mcp_service.tool_definitions()}
    assert "get_hf_external_eval_targets" in tool_names
    assert "write_hf_external_eval_plan" in tool_names
    assert "write_cp_bench_live_verification" in tool_names
    assert "run_cp_bench_local_baseline" in tool_names
    assert "run_cp_bench_proposal_round" in tool_names
    assert "run_cp_bench_candidate_round" in tool_names
    assert "write_cp_bench_submission_gate" in tool_names
    assert "write_smol_worldcup_live_verification" in tool_names
    assert "write_smol_worldcup_prompt_leakage_audit" in tool_names
    assert "run_smol_worldcup_local_baseline" in tool_names
    assert "run_smol_worldcup_model_eval" in tool_names
    assert "run_smol_worldcup_rescore" in tool_names
    assert "get_hf_external_eval_targets" in mcp_service.REQUIRED_TOOLS
    assert "write_hf_external_eval_plan" in mcp_service.REQUIRED_TOOLS
    assert "write_cp_bench_live_verification" in mcp_service.REQUIRED_TOOLS
    assert "run_cp_bench_local_baseline" in mcp_service.REQUIRED_TOOLS
    assert "run_cp_bench_proposal_round" in mcp_service.REQUIRED_TOOLS
    assert "run_cp_bench_candidate_round" in mcp_service.REQUIRED_TOOLS
    assert "write_cp_bench_submission_gate" in mcp_service.REQUIRED_TOOLS
    assert "write_smol_worldcup_live_verification" in mcp_service.REQUIRED_TOOLS
    assert "write_smol_worldcup_prompt_leakage_audit" in mcp_service.REQUIRED_TOOLS
    assert "run_smol_worldcup_local_baseline" in mcp_service.REQUIRED_TOOLS
    assert "run_smol_worldcup_model_eval" in mcp_service.REQUIRED_TOOLS
    assert "run_smol_worldcup_rescore" in mcp_service.REQUIRED_TOOLS
    tools = {tool["name"]: tool for tool in mcp_service.tool_definitions()}
    leakage_profile_enum = (
        tools["write_smol_worldcup_prompt_leakage_audit"]["inputSchema"]["properties"]
        ["prompt_profile"]["enum"]
    )
    model_eval_profile_enum = (
        tools["run_smol_worldcup_model_eval"]["inputSchema"]["properties"]
        ["prompt_profile"]["enum"]
    )
    assert "p3-dev-v2" in leakage_profile_enum
    assert "p3-dev-v2" in model_eval_profile_enum
    model_eval_schema = tools["run_smol_worldcup_model_eval"]["inputSchema"]["properties"]
    assert model_eval_schema["model_provider"]["enum"] == [
        "openai-compatible",
        "deepseek",
    ]
    assert "DeepSeek defaults to DEEPSEEK_API_KEY" in (
        model_eval_schema["api_key_env"]["description"]
    )
    assert model_eval_schema["thinking_mode"]["enum"] == ["default", "enabled", "disabled"]
    assert model_eval_schema["reasoning_effort"]["enum"] == ["high", "max"]
    rescore_schema = tools["run_smol_worldcup_rescore"]["inputSchema"]["properties"]
    assert "prediction_path" in rescore_schema
    assert "source_report" in rescore_schema
    assert "preserve_llm_judge_scores" in rescore_schema

    listed = mcp_service.get_hf_external_eval_targets_tool({"limit": 1})
    assert listed["status"] == "listed"
    assert listed["official_scores_claimed"] is False
    assert listed["targets"][0]["target_id"] == "cp-bench-constraint-modeling"

    written = mcp_service.write_hf_external_eval_plan_tool({
        "target_id": "smol-ai-worldcup-shift",
        "output_dir": str(tmp_path / "hf-plan"),
    })
    assert written["status"] == "written"
    assert written["official_scores_claimed"] is False
    assert Path(written["json_path"]).exists()
    assert Path(written["markdown_path"]).exists()

    def fake_cp_bench_live_verification(output_dir: Path, **kwargs):
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "cp-bench-live-verification.json"
        markdown_path = output_dir / "cp-bench-target-contract.md"
        json_path.write_text("{}", encoding="utf-8")
        markdown_path.write_text("official_scores_claimed: `false`", encoding="utf-8")
        return {
            "status": "written",
            "verification_status": "verified_with_limitations",
            "official_scores_claimed": False,
            "manual_submission_required": True,
            "json_path": str(json_path),
            "contract_path": str(markdown_path),
            "include_raw": kwargs.get("include_raw", False),
        }

    monkeypatch.setattr(
        mcp_service,
        "write_cp_bench_live_verification",
        fake_cp_bench_live_verification,
    )
    cp_bench_live = mcp_service.write_cp_bench_live_verification_tool({
        "output_dir": str(tmp_path / "cp-bench-live"),
        "include_raw": False,
    })
    assert cp_bench_live["status"] == "written"
    assert cp_bench_live["official_scores_claimed"] is False
    assert cp_bench_live["manual_submission_required"] is True
    assert Path(cp_bench_live["json_path"]).exists()

    def fake_cp_bench_baseline(output_dir: Path, **kwargs):
        output_dir.mkdir(parents=True, exist_ok=True)
        submission_path = output_dir / "submission.jsonl"
        manifest_path = output_dir / "artifact-manifest.json"
        submission_path.write_text('{"id":"dry","model":"print(1)"}\n', encoding="utf-8")
        manifest_path.write_text("{}", encoding="utf-8")
        return {
            "status": "written",
            "official_scores_claimed": False,
            "manual_submission_required": True,
            "dry_run": kwargs["dry_run"],
            "framework": kwargs["framework"],
            "dataset_version": kwargs["dataset_version"],
            "timeout_seconds": kwargs["timeout_seconds"],
            "row_count": kwargs["limit"],
            "submission_path": str(submission_path),
            "artifact_manifest_path": str(manifest_path),
        }

    monkeypatch.setattr(
        mcp_service,
        "write_cp_bench_local_baseline",
        fake_cp_bench_baseline,
    )
    cp_bench_baseline = mcp_service.run_cp_bench_local_baseline_tool({
        "output_dir": str(tmp_path / "cp-bench-baseline"),
        "limit": 2,
        "framework": "CPMpy",
        "dataset_version": "verified",
        "timeout_seconds": 7,
        "dry_run": True,
    })
    assert cp_bench_baseline["status"] == "written"
    assert cp_bench_baseline["official_scores_claimed"] is False
    assert cp_bench_baseline["manual_submission_required"] is True
    assert cp_bench_baseline["dry_run"] is True
    assert cp_bench_baseline["framework"] == "CPMpy"
    assert cp_bench_baseline["timeout_seconds"] == 7
    assert cp_bench_baseline["row_count"] == 2

    def fake_cp_bench_proposal_round(
        baseline_report_path: Path,
        proposal_path: Path,
        output_dir: Path,
    ):
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "cp-bench-proposal-round-report.json"
        rollback_path = output_dir / "rollback-evidence.json"
        manifest_path = output_dir / "artifact-manifest.json"
        report_path.write_text("{}", encoding="utf-8")
        rollback_path.write_text("{}", encoding="utf-8")
        manifest_path.write_text("{}", encoding="utf-8")
        return {
            "status": "blocked_pending_local_eval",
            "decision": "defer_execution",
            "official_scores_claimed": False,
            "manual_submission_required": True,
            "baseline_report_path": str(baseline_report_path),
            "proposal_path": str(proposal_path),
            "report_path": str(report_path),
            "rollback_evidence_path": str(rollback_path),
            "artifact_manifest_path": str(manifest_path),
        }

    monkeypatch.setattr(
        mcp_service,
        "run_cp_bench_proposal_round",
        fake_cp_bench_proposal_round,
    )
    baseline_report = tmp_path / "baseline.json"
    proposal = tmp_path / "proposal.json"
    baseline_report.write_text("{}", encoding="utf-8")
    proposal.write_text("{}", encoding="utf-8")
    cp_bench_proposal = mcp_service.run_cp_bench_proposal_round_tool({
        "baseline_report": str(baseline_report),
        "proposal": str(proposal),
        "output_dir": str(tmp_path / "cp-bench-proposal"),
    })
    assert cp_bench_proposal["status"] == "blocked_pending_local_eval"
    assert cp_bench_proposal["official_scores_claimed"] is False
    assert Path(cp_bench_proposal["rollback_evidence_path"]).exists()

    def fake_cp_bench_candidate_round(
        baseline_report_path: Path,
        submission_path: Path,
        output_dir: Path,
        **kwargs,
    ):
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "cp-bench-candidate-round-report.json"
        manifest_path = output_dir / "artifact-manifest.json"
        report_path.write_text("{}", encoding="utf-8")
        manifest_path.write_text("{}", encoding="utf-8")
        return {
            "status": "improved",
            "decision": "candidate_improved",
            "metric_delta": 1.59,
            "official_scores_claimed": False,
            "manual_submission_required": True,
            "baseline_report_path": str(baseline_report_path),
            "submission_path": str(submission_path),
            "proposal_path": str(kwargs["proposal_path"]),
            "framework": kwargs["framework"],
            "timeout_seconds": kwargs["timeout_seconds"],
            "report_path": str(report_path),
            "artifact_manifest_path": str(manifest_path),
        }

    monkeypatch.setattr(
        mcp_service,
        "run_cp_bench_candidate_round",
        fake_cp_bench_candidate_round,
    )
    candidate_submission = tmp_path / "candidate-submission.jsonl"
    candidate_submission.write_text('{"id":"x","model":"print(1)"}\n', encoding="utf-8")
    cp_bench_candidate = mcp_service.run_cp_bench_candidate_round_tool({
        "baseline_report": str(baseline_report),
        "submission": str(candidate_submission),
        "proposal": str(proposal),
        "output_dir": str(tmp_path / "cp-bench-candidate"),
        "framework": "CPMpy",
        "timeout_seconds": 11,
    })
    assert cp_bench_candidate["status"] == "improved"
    assert cp_bench_candidate["metric_delta"] == 1.59
    assert cp_bench_candidate["official_scores_claimed"] is False
    assert cp_bench_candidate["framework"] == "CPMpy"
    assert cp_bench_candidate["timeout_seconds"] == 11

    def fake_cp_bench_submission_gate(
        submission_path: Path,
        output_dir: Path,
        **kwargs,
    ):
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "submission-report.md"
        checklist_path = output_dir / "manual-checklist.md"
        manifest_path = output_dir / "artifact-manifest.json"
        sha_path = output_dir / "SHA256SUMS"
        report_path.write_text("official_scores_claimed: `false`", encoding="utf-8")
        checklist_path.write_text("official_scores_claimed: `false`", encoding="utf-8")
        manifest_path.write_text("{}", encoding="utf-8")
        sha_path.write_text("abc  submission.jsonl\n", encoding="utf-8")
        return {
            "status": "written",
            "official_scores_claimed": False,
            "manual_submission_required": True,
            "external_submission_status": "not_submitted",
            "submission_path": str(submission_path),
            "source_report_path": str(kwargs["source_report_path"]),
            "submission_report_path": str(report_path),
            "manual_checklist_path": str(checklist_path),
            "artifact_manifest_path": str(manifest_path),
            "sha256sums_path": str(sha_path),
        }

    monkeypatch.setattr(
        mcp_service,
        "write_cp_bench_submission_gate",
        fake_cp_bench_submission_gate,
    )
    submission = tmp_path / "submission.jsonl"
    source_report = tmp_path / "source-report.json"
    submission.write_text('{"id":"x","model":"print(1)"}\n', encoding="utf-8")
    source_report.write_text("{}", encoding="utf-8")
    cp_bench_gate = mcp_service.write_cp_bench_submission_gate_tool({
        "submission": str(submission),
        "source_report": str(source_report),
        "output_dir": str(tmp_path / "cp-bench-gate"),
    })
    assert cp_bench_gate["status"] == "written"
    assert cp_bench_gate["official_scores_claimed"] is False
    assert cp_bench_gate["external_submission_status"] == "not_submitted"

    def fake_live_verification(output_dir: Path, **kwargs):
        output_dir.mkdir(parents=True, exist_ok=True)
        json_path = output_dir / "hf-live-verification.json"
        markdown_path = output_dir / "hf-target-contract.md"
        json_path.write_text("{}", encoding="utf-8")
        markdown_path.write_text("official_scores_claimed: `false`", encoding="utf-8")
        return {
            "status": "written",
            "official_scores_claimed": False,
            "json_path": str(json_path),
            "contract_path": str(markdown_path),
            "include_raw": kwargs.get("include_raw", False),
        }

    monkeypatch.setattr(
        mcp_service,
        "write_smol_worldcup_live_verification",
        fake_live_verification,
    )
    live = mcp_service.write_smol_worldcup_live_verification_tool({
        "output_dir": str(tmp_path / "hf-live"),
        "include_raw": False,
    })
    assert live["status"] == "written"
    assert live["official_scores_claimed"] is False
    assert Path(live["json_path"]).exists()

    def fake_prompt_leakage_audit(output_dir: Path, **kwargs):
        output_dir.mkdir(parents=True, exist_ok=True)
        audit_path = output_dir / "prompt-leakage-audit.json"
        audit_path.write_text("{}", encoding="utf-8")
        return {
            "status": "written",
            "audit_status": "passed",
            "official_scores_claimed": False,
            "prompt_profile": kwargs["prompt_profile"],
            "evaluation_split": kwargs["evaluation_split"],
            "leak_count": 0,
            "audit_path": str(audit_path),
        }

    monkeypatch.setattr(
        mcp_service,
        "write_smol_worldcup_prompt_leakage_audit",
        fake_prompt_leakage_audit,
    )
    leakage = mcp_service.write_smol_worldcup_prompt_leakage_audit_tool({
        "output_dir": str(tmp_path / "hf-leakage"),
        "prompt_profile": "p3-dev-v2",
        "evaluation_split": "canary",
    })
    assert leakage["status"] == "written"
    assert leakage["official_scores_claimed"] is False
    assert leakage["prompt_profile"] == "p3-dev-v2"
    assert leakage["evaluation_split"] == "canary"

    def fake_baseline(output_dir: Path, **kwargs):
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "smol-worldcup-baseline-report.json"
        prediction_path = output_dir / "prediction.jsonl"
        report_path.write_text("{}", encoding="utf-8")
        prediction_path.write_text("{}", encoding="utf-8")
        return {
            "status": "written",
            "official_scores_claimed": False,
            "row_count": kwargs.get("limit") or 125,
            "evaluation_split": kwargs["evaluation_split"],
            "baseline_report_path": str(report_path),
            "prediction_path": str(prediction_path),
        }

    monkeypatch.setattr(mcp_service, "write_smol_worldcup_baseline", fake_baseline)
    baseline = mcp_service.run_smol_worldcup_local_baseline_tool({
        "output_dir": str(tmp_path / "hf-baseline"),
        "limit": 4,
        "evaluation_split": "dev",
    })
    assert baseline["status"] == "written"
    assert baseline["official_scores_claimed"] is False
    assert baseline["row_count"] == 4
    assert baseline["evaluation_split"] == "dev"

    def fake_model_eval(output_dir: Path, **kwargs):
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "smol-worldcup-model-eval-report.json"
        prediction_path = output_dir / "prediction.jsonl"
        report_path.write_text("{}", encoding="utf-8")
        prediction_path.write_text("{}", encoding="utf-8")
        return {
            "status": "written",
            "official_scores_claimed": False,
            "model_provider": kwargs["model_provider"],
            "model": kwargs["model"],
            "base_url": kwargs["base_url"],
            "api_key_env": kwargs["api_key_env"],
            "thinking_mode": kwargs["thinking_mode"],
            "reasoning_effort": kwargs["reasoning_effort"],
            "prompt_profile": kwargs["prompt_profile"],
            "evaluation_split": kwargs["evaluation_split"],
            "judge_mode": kwargs["judge_mode"],
            "judge_model": kwargs["judge_model"],
            "row_count": kwargs.get("limit") or 125,
            "model_eval_report_path": str(report_path),
            "prediction_path": str(prediction_path),
        }

    monkeypatch.setattr(mcp_service, "write_smol_worldcup_model_eval", fake_model_eval)
    model_eval = mcp_service.run_smol_worldcup_model_eval_tool({
        "output_dir": str(tmp_path / "hf-model-eval"),
        "model_provider": "deepseek",
        "model": "deepseek-v4-flash",
        "api_key_env": "DEEPSEEK_API_KEY",
        "thinking_mode": "enabled",
        "reasoning_effort": "high",
        "limit": 3,
        "temperature": 0.0,
        "max_tokens": 256,
        "prompt_profile": "p3-dev-v2",
        "evaluation_split": "canary",
        "judge_mode": "openai-compatible",
        "judge_model": "google/gemma-4-31b",
    })
    assert model_eval["status"] == "written"
    assert model_eval["official_scores_claimed"] is False
    assert model_eval["model_provider"] == "deepseek"
    assert model_eval["model"] == "deepseek-v4-flash"
    assert model_eval["base_url"] == "https://api.deepseek.com"
    assert model_eval["api_key_env"] == "DEEPSEEK_API_KEY"
    assert model_eval["thinking_mode"] == "enabled"
    assert model_eval["reasoning_effort"] == "high"
    assert model_eval["prompt_profile"] == "p3-dev-v2"
    assert model_eval["evaluation_split"] == "canary"
    assert model_eval["judge_mode"] == "openai-compatible"
    assert model_eval["judge_model"] == "google/gemma-4-31b"
    assert model_eval["row_count"] == 3

    def fake_rescore(output_dir: Path, **kwargs):
        output_dir.mkdir(parents=True, exist_ok=True)
        report_path = output_dir / "smol-worldcup-rescore-report.json"
        confidence_path = output_dir / "confidence-calibration-audit.json"
        report_path.write_text("{}", encoding="utf-8")
        confidence_path.write_text("{}", encoding="utf-8")
        return {
            "status": "written",
            "official_scores_claimed": False,
            "prediction_path": str(kwargs["prediction_path"]),
            "source_report_path": str(kwargs["source_report"]),
            "source_run_id": kwargs["source_run_id"],
            "preserve_llm_judge_scores": kwargs["preserve_llm_judge_scores"],
            "rescore_report_path": str(report_path),
            "confidence_calibration_audit_path": str(confidence_path),
        }

    source_prediction = tmp_path / "hf-model-eval" / "prediction.jsonl"
    source_report = tmp_path / "hf-model-eval" / "smol-worldcup-model-eval-report.json"
    source_report.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(mcp_service, "write_smol_worldcup_rescore", fake_rescore)
    rescore = mcp_service.run_smol_worldcup_rescore_tool({
        "output_dir": str(tmp_path / "hf-rescore"),
        "prediction_path": str(source_prediction),
        "source_report": str(source_report),
        "source_run_id": "round-004-dev-v2",
    })
    assert rescore["status"] == "written"
    assert rescore["official_scores_claimed"] is False
    assert rescore["source_run_id"] == "round-004-dev-v2"
    assert rescore["preserve_llm_judge_scores"] is True

    def fake_rescore_proof_archive(**kwargs):
        output_dir = kwargs["output_dir"]
        output_dir.mkdir(parents=True, exist_ok=True)
        proof_path = output_dir / "proof-archive.json"
        proof_path.write_text("{}", encoding="utf-8")
        return {
            "status": "written",
            "official_scores_claimed": False,
            "archive_status": "archivable",
            "rescore_dir": str(kwargs["rescore_dir"]),
            "proof_archive_path": str(proof_path),
            "source_run_id": kwargs["source_run_id"],
        }

    monkeypatch.setattr(
        mcp_service,
        "write_smol_worldcup_rescore_proof_archive",
        fake_rescore_proof_archive,
    )
    rescore_archive = mcp_service.write_smol_worldcup_rescore_proof_archive_tool({
        "output_dir": str(tmp_path / "hf-rescore-proof"),
        "rescore_dir": str(tmp_path / "hf-rescore"),
        "source_report": str(source_report),
        "source_prediction_path": str(source_prediction),
        "source_run_id": "round-004-dev-v2",
        "command_lines": ["ml-loop hf-eval smol-worldcup-rescore --json"],
    })
    assert rescore_archive["status"] == "written"
    assert rescore_archive["official_scores_claimed"] is False
    assert rescore_archive["archive_status"] == "archivable"
    assert rescore_archive["source_run_id"] == "round-004-dev-v2"

    def fake_submission_probe(output_dir: Path, **kwargs):
        output_dir.mkdir(parents=True, exist_ok=True)
        probe_path = output_dir / "smol-worldcup-submission-probe.json"
        probe_path.write_text("{}", encoding="utf-8")
        return {
            "status": "written",
            "official_scores_claimed": False,
            "submission_action": "not_launched",
            "submission_path_status": "blocked_for_local_predictions",
            "requested_model_supported_by_space": False,
            "model_id": kwargs["model_id"],
            "probe_path": str(probe_path),
        }

    monkeypatch.setattr(
        mcp_service,
        "write_smol_worldcup_submission_probe",
        fake_submission_probe,
    )
    submission_probe = mcp_service.write_smol_worldcup_submission_probe_tool({
        "output_dir": str(tmp_path / "hf-submission-probe"),
        "model": "openai/gpt-oss-20b",
        "include_raw": False,
    })
    assert submission_probe["status"] == "written"
    assert submission_probe["official_scores_claimed"] is False
    assert submission_probe["submission_action"] == "not_launched"
    assert submission_probe["submission_path_status"] == "blocked_for_local_predictions"
    assert submission_probe["requested_model_supported_by_space"] is False


def test_service_manifest_mentions_hf_external_validation() -> None:
    manifest = mcp_service.get_service_manifest_tool({})

    assert "hf_external_eval_targets" in manifest["planning_signals"]
    assert manifest["hf_external_eval_targets"]["official_scores_claimed"] is False
    assert manifest["hf_external_eval_plan"]["official_scores_claimed"] is False
    assert manifest["cp_bench_live_verification"]["official_scores_claimed"] is False
    assert manifest["cp_bench_live_verification"]["status"] == "explicit_tool_only"
    assert manifest["cp_bench_local_baseline"]["official_scores_claimed"] is False
    assert manifest["cp_bench_local_baseline"]["status"] == "explicit_tool_only"
    assert manifest["cp_bench_candidate_round"]["official_scores_claimed"] is False
    assert manifest["cp_bench_candidate_round"]["status"] == "explicit_tool_only"
    assert manifest["cp_bench_candidate_round"]["tool"] == "run_cp_bench_candidate_round"
    assert manifest["smol_worldcup_live_verification"]["official_scores_claimed"] is False
    assert manifest["smol_worldcup_live_verification"]["status"] == "explicit_tool_only"
    assert manifest["smol_worldcup_prompt_leakage_audit"]["official_scores_claimed"] is False
    assert manifest["smol_worldcup_prompt_leakage_audit"]["status"] == "explicit_tool_only"
    assert manifest["smol_worldcup_local_baseline"]["official_scores_claimed"] is False
    assert manifest["smol_worldcup_local_baseline"]["status"] == "explicit_tool_only"
    assert manifest["smol_worldcup_model_eval"]["official_scores_claimed"] is False
    assert manifest["smol_worldcup_model_eval"]["status"] == "explicit_tool_only"
    assert manifest["smol_worldcup_model_eval"]["tool"] == "run_smol_worldcup_model_eval"
    assert manifest["smol_worldcup_rescore"]["official_scores_claimed"] is False
    assert manifest["smol_worldcup_rescore"]["status"] == "explicit_tool_only"
    assert manifest["smol_worldcup_rescore"]["tool"] == "run_smol_worldcup_rescore"
    assert manifest["smol_worldcup_rescore_proof_archive"]["official_scores_claimed"] is False
    assert manifest["smol_worldcup_rescore_proof_archive"]["status"] == "explicit_tool_only"
    assert manifest["smol_worldcup_rescore_proof_archive"]["tool"] == (
        "write_smol_worldcup_rescore_proof_archive"
    )
    assert manifest["smol_worldcup_submission_probe"]["official_scores_claimed"] is False
    assert manifest["smol_worldcup_submission_probe"]["status"] == "explicit_tool_only"
    assert manifest["smol_worldcup_submission_probe"]["tool"] == (
        "write_smol_worldcup_submission_probe"
    )
    workflows = {workflow["name"]: workflow for workflow in manifest["recommended_workflows"]}
    assert "hf_external_validation" in workflows
    assert "get_hf_external_eval_targets" in workflows["hf_external_validation"]["tools"]
    assert "write_cp_bench_live_verification" in workflows["hf_external_validation"]["tools"]
    assert "run_cp_bench_local_baseline" in workflows["hf_external_validation"]["tools"]
    assert "run_cp_bench_candidate_round" in workflows["hf_external_validation"]["tools"]
    assert "write_smol_worldcup_live_verification" in workflows["hf_external_validation"]["tools"]
    assert (
        "write_smol_worldcup_prompt_leakage_audit"
        in workflows["hf_external_validation"]["tools"]
    )
    assert "run_smol_worldcup_local_baseline" in workflows["hf_external_validation"]["tools"]
    assert "run_smol_worldcup_model_eval" in workflows["hf_external_validation"]["tools"]
    assert "run_smol_worldcup_rescore" in workflows["hf_external_validation"]["tools"]
    assert (
        "write_smol_worldcup_rescore_proof_archive"
        in workflows["hf_external_validation"]["tools"]
    )
    assert (
        "write_smol_worldcup_submission_probe"
        in workflows["hf_external_validation"]["tools"]
    )
