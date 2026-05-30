from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from lib import mcp_service
from lib.research_memory import MemoryArtifactRef, ResearchMemoryCard, ResearchMemoryStore


def _request(request_id: int, method: str, params: dict | None = None) -> dict:
    request = {"jsonrpc": "2.0", "id": request_id, "method": method}
    if params is not None:
        request["params"] = params
    return request


def _valid_client_proposal(proposal_id: str) -> dict:
    return {
        "proposal_id": proposal_id,
        "hypothesis": "A bounded prompt profile change can improve local SHIFT.",
        "evidence_used": [{"artifact": "dev_report", "observation": "SHIFT headroom"}],
        "change_surface": "prompt_profile",
        "change_spec": {"single_primary_variable": True, "target": "p3-dev-v2"},
        "expected_effect": {"primary_metric": "SHIFT", "expected_direction": "increase"},
        "validation_plan": {
            "first_split": "dev",
            "promotion_split": "canary",
            "rollback_if": ["SHIFT_delta_lt_0"],
        },
        "risk_assessment": {"overfit_risk": "medium"},
        "next_if_success": "run_canary_confirmation",
        "next_if_failure": "rollback_candidate",
        "claim_boundary": "local diagnostic proposal only",
    }


@pytest.fixture(autouse=True)
def allow_tmp_execution_roots(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    monkeypatch.setenv("ML_RESEARCH_LOOP_ALLOWED_ROOTS", str(tmp_path))


def test_initialize_returns_server_capabilities() -> None:
    response = mcp_service.handle_request(
        _request(1, "initialize", {"protocolVersion": "2024-11-05"})
    )

    assert response["jsonrpc"] == "2.0"
    assert response["id"] == 1
    assert response["result"]["serverInfo"] == {
        "name": "ml-research-loop",
        "version": "0.1.0",
    }
    assert response["result"]["capabilities"] == {"tools": {}}


def test_tools_list_exposes_research_loop_tools() -> None:
    response = mcp_service.handle_request(_request(2, "tools/list"))

    tool_names = {tool["name"] for tool in response["result"]["tools"]}
    assert {
        "run_fresh_demo",
        "run_autoresearch",
        "run_ai_autoresearch",
        "get_service_manifest",
        "plan_research_case",
        "get_experiment_status",
        "get_experiment_result",
        "get_experiment_logs",
        "run_client_patch_experiment",
        "apply_client_code_patch",
        "build_proposal_context",
        "validate_client_proposal_contract",
        "write_proposal_reflection",
        "run_next_experiment_from_review",
        "get_benchmark_harness_probe",
        "plan_benchmark_proof_run",
        "write_benchmark_proof_setup_bundle",
        "write_benchmark_proof_publication_bundle",
        "write_benchmark_proof_archive",
        "prepare_official_mle_bench_workspace",
        "grade_official_mle_bench_submission",
        "run_official_mle_bench_round",
        "run_official_mle_bench_patch_round",
        "write_official_mle_bench_patch_round_proof_bundle",
        "run_fasttext_patch_round",
        "write_fasttext_patch_round_proof_bundle",
        "run_fasttext_multi_proposal_loop",
        "write_fasttext_release_proof_bundle",
        "prepare_paperbench_codex_review_bundle",
        "write_paperbench_codex_review_report",
        "build_cp_bench_proposal_context",
        "write_cp_bench_client_candidate_submission",
    }.issubset(tool_names)
    research_case_tool = next(
        tool for tool in response["result"]["tools"]
        if tool["name"] == "plan_research_case"
    )
    smol_model_eval_tool = next(
        tool for tool in response["result"]["tools"]
        if tool["name"] == "run_smol_worldcup_model_eval"
    )
    smol_proposal_round_tool = next(
        tool for tool in response["result"]["tools"]
        if tool["name"] == "run_smol_worldcup_proposal_round"
    )
    proposal_reflection_tool = next(
        tool for tool in response["result"]["tools"]
        if tool["name"] == "write_proposal_reflection"
    )
    proposal_search_tool = next(
        tool for tool in response["result"]["tools"]
        if tool["name"] == "summarize_proposal_search"
    )
    proposal_context_tool = next(
        tool for tool in response["result"]["tools"]
        if tool["name"] == "build_proposal_context"
    )
    assert set(research_case_tool["inputSchema"]["required"]) == {"objective"}
    assert "p3-semantic-v1" in (
        smol_model_eval_tool["inputSchema"]["properties"]["prompt_profile"]["enum"]
    )
    assert "p3-semantic-v2" in (
        smol_model_eval_tool["inputSchema"]["properties"]["prompt_profile"]["enum"]
    )
    assert set(smol_proposal_round_tool["inputSchema"]["required"]) == {"output_dir"}
    assert "proposal_file" in smol_proposal_round_tool["inputSchema"]["properties"]
    assert {"required": ["proposal"]} in smol_proposal_round_tool["inputSchema"]["anyOf"]
    assert {"required": ["proposal_file"]} in smol_proposal_round_tool["inputSchema"]["anyOf"]
    assert "p3-dev-v2" in (
        smol_proposal_round_tool["inputSchema"]["properties"]["prompt_profile"]["enum"]
    )
    reflection_requirements = proposal_reflection_tool["inputSchema"]["allOf"]
    assert {"required": ["proposal"]} in reflection_requirements[0]["anyOf"]
    assert {"required": ["proposal_file"]} in reflection_requirements[0]["anyOf"]
    assert {"required": ["evaluation"]} in reflection_requirements[1]["anyOf"]
    assert {"required": ["evaluation_file"]} in reflection_requirements[1]["anyOf"]
    assert "memory_store" in proposal_reflection_tool["inputSchema"]["properties"]
    assert "memory_store" in proposal_context_tool["inputSchema"]["properties"]
    assert "memory_query" in proposal_context_tool["inputSchema"]["properties"]
    assert "branch_budget" in proposal_search_tool["inputSchema"]["properties"]
    assert "diversity_constraint" in proposal_search_tool["inputSchema"]["properties"]
    assert set(proposal_search_tool["inputSchema"]["required"]) == {"items"}
    claims_items = research_case_tool["inputSchema"]["properties"]["claims"]["items"]
    assert {"type": "string"} in claims_items["anyOf"]
    claim_object_schema = next(
        item for item in claims_items["anyOf"] if item.get("type") == "object"
    )
    assert set(claim_object_schema["properties"]["status"]["enum"]) == {
        "blocked",
        "needs_evidence",
        "supported_local",
        "unsupported",
    }
    evidence_strength_schema = claim_object_schema["properties"]["evidence_refs"]["items"][
        "properties"
    ]["strength"]
    assert set(evidence_strength_schema["enum"]) == {
        "code_reference",
        "dataset_card",
        "paper_claim",
        "runtime_artifact",
        "weak",
    }
    research_tool = next(
        tool for tool in response["result"]["tools"]
        if tool["name"] == "research_task"
    )
    assert research_tool["inputSchema"]["properties"]["query_fanout"] == {
        "type": "boolean",
        "default": True,
        "description": "Use query_plan variants when a backend returns too few sources.",
    }
    archive_tool = next(
        tool for tool in response["result"]["tools"]
        if tool["name"] == "write_benchmark_proof_archive"
    )
    assert set(archive_tool["inputSchema"]["required"]) == {
        "manifest",
        "artifact_root",
        "output_dir",
    }
    mle_workspace_tool = next(
        tool for tool in response["result"]["tools"]
        if tool["name"] == "prepare_official_mle_bench_workspace"
    )
    assert set(mle_workspace_tool["inputSchema"]["required"]) == {
        "competition_id",
        "prepared_competition_dir",
        "runtime_root",
    }
    mle_round_tool = next(
        tool for tool in response["result"]["tools"]
        if tool["name"] == "run_official_mle_bench_round"
    )
    assert set(mle_round_tool["inputSchema"]["required"]) == {
        "competition_id",
        "workspace",
        "data_dir",
        "mlebench",
        "output_dir",
    }
    mle_patch_round_tool = next(
        tool for tool in response["result"]["tools"]
        if tool["name"] == "run_official_mle_bench_patch_round"
    )
    assert set(mle_patch_round_tool["inputSchema"]["required"]) == {
        "competition_id",
        "workspace",
        "data_dir",
        "mlebench",
        "output_dir",
        "patch",
    }
    mle_patch_proof_tool = next(
        tool for tool in response["result"]["tools"]
        if tool["name"] == "write_official_mle_bench_patch_round_proof_bundle"
    )
    assert set(mle_patch_proof_tool["inputSchema"]["required"]) == {
        "patch_round_report",
        "output_dir",
    }
    fasttext_patch_tool = next(
        tool for tool in response["result"]["tools"]
        if tool["name"] == "run_fasttext_patch_round"
    )
    assert set(fasttext_patch_tool["inputSchema"]["required"]) == {
        "target_spec",
        "output_dir",
        "ag_news_train_csv",
        "ag_news_test_csv",
        "fasttext_binary",
        "baseline_report",
        "proposal",
    }
    fasttext_proof_tool = next(
        tool for tool in response["result"]["tools"]
        if tool["name"] == "write_fasttext_patch_round_proof_bundle"
    )
    assert set(fasttext_proof_tool["inputSchema"]["required"]) == {
        "patch_round_report",
        "output_dir",
    }
    fasttext_multi_tool = next(
        tool for tool in response["result"]["tools"]
        if tool["name"] == "run_fasttext_multi_proposal_loop"
    )
    assert set(fasttext_multi_tool["inputSchema"]["required"]) == {
        "target_spec",
        "output_dir",
        "ag_news_train_csv",
        "ag_news_test_csv",
        "fasttext_binary",
        "baseline_report",
        "proposals",
    }
    fasttext_release_tool = next(
        tool for tool in response["result"]["tools"]
        if tool["name"] == "write_fasttext_release_proof_bundle"
    )
    assert set(fasttext_release_tool["inputSchema"]["required"]) == {
        "proof_manifest",
        "output_dir",
    }
    codex_bundle_tool = next(
        tool for tool in response["result"]["tools"]
        if tool["name"] == "prepare_paperbench_codex_review_bundle"
    )
    assert set(codex_bundle_tool["inputSchema"]["required"]) == {
        "run_dir",
        "paper_dir",
        "output_dir",
    }
    codex_report_tool = next(
        tool for tool in response["result"]["tools"]
        if tool["name"] == "write_paperbench_codex_review_report"
    )
    assert set(codex_report_tool["inputSchema"]["required"]) == {
        "bundle",
        "review",
        "output_dir",
    }


def test_ping_returns_empty_result() -> None:
    response = mcp_service.handle_request(_request(5, "ping"))

    assert response == {"jsonrpc": "2.0", "id": 5, "result": {}}


def test_write_proposal_reflection_tool_can_sync_memory(tmp_path: Path) -> None:
    proposal = _valid_client_proposal("round-mcp-memory")
    memory_store = tmp_path / "memory.jsonl"
    response = mcp_service.handle_request(
        _request(
            31,
            "tools/call",
            {
                "name": "write_proposal_reflection",
                "arguments": {
                    "proposal": proposal,
                    "evaluation": {"dev_delta": {"SHIFT": 1.0, "H": 0.0}},
                    "output_dir": str(tmp_path / "reflection"),
                    "memory_store": str(memory_store),
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])
    cards = ResearchMemoryStore(memory_store).list_cards()
    assert payload["status"] == "needs_promotion_evidence"
    assert payload["memory_sync"]["status"] == "synced"
    assert payload["memory_sync"]["card_id"] == "proposal-reflection-round-mcp-memory"
    assert len(cards) == 1
    assert cards[0].config["proposal_id"] == "round-mcp-memory"


def test_summarize_proposal_search_tool_reports_supported_candidate() -> None:
    response = mcp_service.handle_request(
        _request(
            32,
            "tools/call",
            {
                "name": "summarize_proposal_search",
                "arguments": {
                    "items": [
                        {"proposal_id": "p-dev", "score_delta": {"dev": 1.0}},
                        {
                            "proposal_id": "p-canary",
                            "proposal_family": "prompt",
                            "score_delta": {"dev": 0.3, "canary": 0.2},
                        },
                    ],
                    "branch_budget": 1,
                    "diversity_constraint": {"max_per_family": 1},
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["status"] == "supported_candidate_found"
    assert payload["best_proposal_id"] == "p-canary"
    assert [node["proposal_id"] for node in payload["selected_next_nodes"]] == [
        "p-canary"
    ]


def test_cp_bench_proposal_context_tool_writes_prompt_from_failed_outcome(
    tmp_path: Path,
) -> None:
    report = tmp_path / "candidate-round-report.json"
    report.write_text(
        json.dumps({
            "status": "improved",
            "decision": "candidate_improved",
            "after_summary": {"final_solution_accuracy_percent": 3.17},
            "model_outcomes": [
                {
                    "problem_id": "csplib__csplib_005_autocorrelation",
                    "final_passed": False,
                    "failure_type": "consistency_or_objective_failed",
                }
            ],
            "official_scores_claimed": False,
            "external_submission_status": "not_submitted",
        }),
        encoding="utf-8",
    )

    payload = mcp_service.build_cp_bench_proposal_context_tool({
        "current_report": str(report),
        "output_dir": str(tmp_path / "proposal-context"),
        "max_proposals": 2,
    })

    assert payload["status"] == "ready_for_client_proposal"
    assert payload["official_scores_claimed"] is False
    prompt = Path(payload["prompt_path"]).read_text(encoding="utf-8")
    assert "consistency_or_objective_failed" in prompt
    assert "不要上传 Hugging Face" in prompt
    assert payload["official_scores_claimed"] is False


def test_cp_bench_client_candidate_tool_writes_non_reference_artifacts(
    monkeypatch,
    tmp_path: Path,
) -> None:
    def fake_writer(*args, **kwargs):
        output_dir = args[0]
        return {
            "status": "partial_generated",
            "submission_path": str(output_dir / "candidate-submission.jsonl"),
            "source_audit_path": str(output_dir / "source-audit.json"),
            "artifact_manifest_path": str(output_dir / "artifact-manifest.json"),
            "generated_count": kwargs["limit"] - 1,
            "fallback_count": 1,
            "reference_model_field_accessed": False,
            "official_scores_claimed": False,
        }

    monkeypatch.setattr(
        mcp_service,
        "write_cp_bench_client_candidate_submission",
        fake_writer,
    )

    payload = mcp_service.write_cp_bench_client_candidate_submission_tool({
        "output_dir": str(tmp_path / "client-candidate"),
        "limit": 4,
        "dataset_version": "verified",
        "strategy": "handcrafted-small-cpmpy-v1",
    })

    assert payload["status"] == "partial_generated"
    assert payload["generated_count"] == 3
    assert payload["fallback_count"] == 1
    assert payload["reference_model_field_accessed"] is False
    assert payload["official_scores_claimed"] is False


def test_smol_worldcup_proposal_round_accepts_proposal_file_for_validation(
    tmp_path: Path,
) -> None:
    proposal_file = tmp_path / "bad-proposal.json"
    proposal_file.write_text(
        json.dumps({
            "proposal_id": "bad-smol-proposal",
            "hypothesis": "Change too much.",
            "change_surface": "training_recipe",
            "change_spec": {"single_primary_variable": False},
        }),
        encoding="utf-8",
    )
    response = mcp_service.handle_request(
        _request(
            33,
            "tools/call",
            {
                "name": "run_smol_worldcup_proposal_round",
                "arguments": {
                    "proposal_file": str(proposal_file),
                    "output_dir": str(tmp_path / "smol-round"),
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["status"] == "rejected"
    assert payload["executes_experiment"] is False
    assert payload["validation_status"] == "rejected"


def test_tools_call_wraps_json_payload_as_text_content(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setitem(
        mcp_service.TOOL_HANDLERS,
        "run_fresh_demo",
        lambda arguments: {"status": "completed", "runtime_root": arguments["runtime_root"]},
    )

    response = mcp_service.handle_request(
        _request(
            3,
            "tools/call",
            {
                "name": "run_fresh_demo",
                "arguments": {"runtime_root": "/tmp/ml-loop-demo"},
            },
        )
    )

    assert response["id"] == 3
    assert response["result"]["content"][0]["type"] == "text"
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload == {"status": "completed", "runtime_root": "/tmp/ml-loop-demo"}


def test_plan_research_case_tool_returns_case_and_summary() -> None:
    response = mcp_service.handle_request(
        _request(
            7,
            "tools/call",
            {
                "name": "plan_research_case",
                "arguments": {
                    "case_id": "case-routing",
                    "objective": "Plan a bounded routing replication",
                    "claims": [
                        {
                            "claim_id": "claim-routing",
                            "text": "Routing improves evidence selection",
                            "status": "supported_local",
                            "evidence_refs": [
                                {
                                    "source_id": "paper-1",
                                    "artifact_path": "docs/evidence/routing.md",
                                }
                            ],
                        }
                    ],
                    "forbidden_claims": ["official benchmark score"],
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])

    assert payload["status"] == "planned"
    assert payload["official_scores_claimed"] is False
    assert payload["case"]["case_id"] == "case-routing"
    assert payload["case"]["objective"] == "Plan a bounded routing replication"
    assert payload["case"]["official_scores_claimed"] is False
    assert payload["case"]["claims"][0]["evidence_refs"][0]["source_id"] == "paper-1"
    assert payload["summary"]["case_id"] == "case-routing"
    assert payload["summary"]["supported_claim_count"] == 1
    assert payload["summary"]["official_scores_claimed"] is False
    assert payload["summary"]["forbidden_claims"] == ["official benchmark score"]


def test_plan_research_case_defaults_case_id_and_accepts_string_claims() -> None:
    response = mcp_service.handle_request(
        _request(
            8,
            "tools/call",
            {
                "name": "plan_research_case",
                "arguments": {
                    "objective": "Tune a small byte language model!",
                    "claims": ["Byte-level smoothing improves validation loss"],
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])

    assert payload["status"] == "planned"
    assert payload["case"]["case_id"] == "case-tune-a-small-byte-language-model"
    assert payload["case"]["claims"][0]["claim_id"] == "claim-001"
    assert payload["case"]["claims"][0]["status"] == "needs_evidence"
    assert payload["summary"]["supported_claim_count"] == 0


@pytest.mark.parametrize(
    ("arguments", "expected_error"),
    [
        ({}, "objective is required"),
        ({"objective": " "}, "objective is required"),
        ({"objective": "x", "claims": "not-a-list"}, "claims must be a list"),
        (
            {"objective": "x", "claims": [{"claim_id": "c1"}]},
            "claims[].text is required",
        ),
        (
            {"objective": "x", "claims": [{"text": "claim", "status": "typo"}]},
            "claims[].status must be one of",
        ),
        (
            {
                "objective": "x",
                "claims": [
                    {
                        "text": "claim",
                        "evidence_refs": [
                            {
                                "source_id": "paper-1",
                                "artifact_path": "docs/evidence.md",
                                "strength": "too_strong",
                            }
                        ],
                    }
                ],
            },
            "claims[].evidence_refs[].strength must be one of",
        ),
        (
            {"objective": "x", "forbidden_claims": [1]},
            "forbidden_claims must be a list of strings",
        ),
    ],
)
def test_plan_research_case_rejects_invalid_arguments(
    arguments: dict,
    expected_error: str,
) -> None:
    response = mcp_service.handle_request(
        _request(
            9,
            "tools/call",
            {"name": "plan_research_case", "arguments": arguments},
        )
    )

    assert response["result"]["isError"] is True
    payload = json.loads(response["result"]["content"][0]["text"])
    assert expected_error in payload["error"]


def test_benchmark_proof_mcp_tools_probe_and_plan() -> None:
    probe_response = mcp_service.handle_request(
        _request(20, "tools/call", {"name": "get_benchmark_harness_probe", "arguments": {}})
    )
    probe_payload = json.loads(probe_response["result"]["content"][0]["text"])

    plan_response = mcp_service.handle_request(
        _request(21, "tools/call", {"name": "plan_benchmark_proof_run", "arguments": {}})
    )
    plan_payload = json.loads(plan_response["result"]["content"][0]["text"])

    assert probe_payload["read_only"] is True
    assert probe_payload["official_scores_claimed"] is False
    assert plan_payload["read_only"] is True
    assert plan_payload["official_scores_claimed"] is False
    assert "artifact_requirements" in plan_payload


def test_benchmark_proof_mcp_tools_write_publication_and_archive(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(mcp_service.ALLOWED_ROOTS_ENV, str(tmp_path))
    artifact_root = tmp_path / "proof-artifacts"
    artifact_paths = {
        "command_lines": "commands.txt",
        "resolved_config": "config.json",
        "environment_manifest": "environment.json",
        "raw_logs": "logs/run.log",
        "raw_reports": "reports/report.json",
        "limitations_note": "LIMITATIONS.md",
    }
    for role, relative in artifact_paths.items():
        path = artifact_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{role}: {relative}\n", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({
            "benchmark_name": "mle_bench",
            "run_mode": "official_debug",
            "official_scores_claimed": False,
            "limitations": ["debug proof only"],
            "artifacts": artifact_paths,
        }),
        encoding="utf-8",
    )

    publication_response = mcp_service.handle_request(
        _request(
            22,
            "tools/call",
            {
                "name": "write_benchmark_proof_publication_bundle",
                "arguments": {
                    "manifest": str(manifest_path),
                    "artifact_root": str(artifact_root),
                    "output_dir": str(tmp_path / "publication"),
                },
            },
        )
    )
    publication_payload = json.loads(publication_response["result"]["content"][0]["text"])
    archive_response = mcp_service.handle_request(
        _request(
            23,
            "tools/call",
            {
                "name": "write_benchmark_proof_archive",
                "arguments": {
                    "manifest": str(manifest_path),
                    "artifact_root": str(artifact_root),
                    "output_dir": str(tmp_path / "archive"),
                },
            },
        )
    )
    archive_payload = json.loads(archive_response["result"]["content"][0]["text"])

    assert publication_payload["status"] == "written"
    assert Path(publication_payload["json_path"]).exists()
    assert archive_payload["status"] == "written"
    assert Path(archive_payload["json_path"]).exists()
    assert (tmp_path / "archive" / "artifacts" / "logs" / "run.log").exists()


def test_benchmark_mcp_writes_mle_patch_proof_bundle(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(mcp_service.ALLOWED_ROOTS_ENV, str(tmp_path))
    patch_round_report = _write_mcp_patch_round_report_fixture(tmp_path)

    response = mcp_service.handle_request(
        _request(
            24,
            "tools/call",
            {
                "name": "write_official_mle_bench_patch_round_proof_bundle",
                "arguments": {
                    "patch_round_report": str(patch_round_report),
                    "output_dir": str(tmp_path / "proof"),
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["status"] == "written"
    assert payload["official_scores_claimed"] is False
    assert Path(payload["manifest_path"]).exists()
    assert payload["archive"]["bundle"]["status"] == "archivable"


def test_benchmark_mcp_writes_paperbench_codex_review_bundle_and_report(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(mcp_service.ALLOWED_ROOTS_ENV, str(tmp_path))
    paper_dir = _write_paperbench_paper_fixture(tmp_path)
    run_dir = _write_paperbench_run_fixture(tmp_path)

    bundle_response = mcp_service.handle_request(
        _request(
            25,
            "tools/call",
            {
                "name": "prepare_paperbench_codex_review_bundle",
                "arguments": {
                    "run_dir": str(run_dir),
                    "paper_dir": str(paper_dir),
                    "output_dir": str(tmp_path / "codex-review"),
                },
            },
        )
    )
    bundle_payload = json.loads(bundle_response["result"]["content"][0]["text"])

    report_response = mcp_service.handle_request(
        _request(
            26,
            "tools/call",
            {
                "name": "write_paperbench_codex_review_report",
                "arguments": {
                    "bundle": bundle_payload["bundle_path"],
                    "review": {
                        "summary": "Codex reviewed a minimal debug reproduction.",
                        "codex_review_score": 0.2,
                        "leaf_scores": [],
                        "evidence_refs": ["run/grade.json"],
                        "missing_evidence": ["real experiment outputs"],
                        "confidence": 0.6,
                    },
                    "output_dir": str(tmp_path / "codex-review-report"),
                },
            },
        )
    )
    report_payload = json.loads(report_response["result"]["content"][0]["text"])

    assert bundle_payload["bundle"]["judge_type"] == "codex_assisted"
    assert bundle_payload["bundle"]["official_scores_claimed"] is False
    assert report_payload["report"]["official_scores_claimed"] is False
    assert report_payload["report"]["paperbench_score"] is None
    assert Path(report_payload["json_path"]).is_file()


def test_fasttext_multi_proposal_loop_tool_passes_bounded_inputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(mcp_service.ALLOWED_ROOTS_ENV, str(tmp_path))
    paths = {
        "target_spec": tmp_path / "target.json",
        "ag_news_train_csv": tmp_path / "train.csv",
        "ag_news_test_csv": tmp_path / "test.csv",
        "fasttext_binary": tmp_path / "fasttext",
        "baseline_report": tmp_path / "baseline.json",
    }
    for path in paths.values():
        path.write_text("fixture\n", encoding="utf-8")

    def fake_runner(config, **kwargs):
        return {
            "status": "completed_with_failures",
            "stage": "p5_fasttext_multi_proposal_loop",
            "output_dir": str(config.output_dir),
            "proposal_count": len(kwargs["proposals"]),
            "official_scores_claimed": False,
        }

    monkeypatch.setattr(mcp_service, "run_fasttext_multi_proposal_loop", fake_runner)

    response = mcp_service.handle_request(
        _request(
            27,
            "tools/call",
            {
                "name": "run_fasttext_multi_proposal_loop",
                "arguments": {
                    "target_spec": str(paths["target_spec"]),
                    "output_dir": str(tmp_path / "multi-round"),
                    "ag_news_train_csv": str(paths["ag_news_train_csv"]),
                    "ag_news_test_csv": str(paths["ag_news_test_csv"]),
                    "fasttext_binary": str(paths["fasttext_binary"]),
                    "baseline_report": str(paths["baseline_report"]),
                    "proposals": [
                        {"proposal_id": "good", "train_args": {"wordNgrams": 2}},
                        {"proposal_id": "bad", "train_args": {"bucket": 100}},
                    ],
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["status"] == "completed_with_failures"
    assert payload["proposal_count"] == 2
    assert payload["official_scores_claimed"] is False


def test_fasttext_release_proof_bundle_tool_passes_review_inputs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv(mcp_service.ALLOWED_ROOTS_ENV, str(tmp_path))
    proof_manifest = tmp_path / "proof-manifest.json"
    multi_round_report = tmp_path / "multi-round-report.json"
    proof_manifest.write_text("{}", encoding="utf-8")
    multi_round_report.write_text("{}", encoding="utf-8")

    def fake_writer(**kwargs):
        return {
            "status": "completed",
            "stage": "p5_fasttext_release_proof_bundle",
            "proof_manifest": str(kwargs["proof_manifest"]),
            "multi_round_report": str(kwargs["multi_round_report"]),
            "official_scores_claimed": False,
        }

    monkeypatch.setattr(mcp_service, "write_fasttext_release_proof_bundle", fake_writer)

    response = mcp_service.handle_request(
        _request(
            28,
            "tools/call",
            {
                "name": "write_fasttext_release_proof_bundle",
                "arguments": {
                    "proof_manifest": str(proof_manifest),
                    "output_dir": str(tmp_path / "release-proof"),
                    "multi_round_report": str(multi_round_report),
                    "reviewer": "mcp-test-reviewer",
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["status"] == "completed"
    assert payload["stage"] == "p5_fasttext_release_proof_bundle"
    assert payload["official_scores_claimed"] is False


def test_benchmark_proof_mcp_write_blocks_paths_outside_allowed_roots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    allowed_root = tmp_path / "allowed"
    blocked_root = tmp_path / "blocked"
    allowed_root.mkdir()
    blocked_root.mkdir()
    monkeypatch.setenv(mcp_service.ALLOWED_ROOTS_ENV, str(allowed_root))
    manifest_path = blocked_root / "manifest.json"
    manifest_path.write_text("{}", encoding="utf-8")

    response = mcp_service.handle_request(
        _request(
            24,
            "tools/call",
            {
                "name": "write_benchmark_proof_publication_bundle",
                "arguments": {
                    "manifest": str(manifest_path),
                    "artifact_root": str(blocked_root),
                    "output_dir": str(blocked_root / "publication"),
                },
            },
        )
    )
    payload = json.loads(response["result"]["content"][0]["text"])

    assert response["result"]["isError"] is True
    assert payload["field"] == "manifest"


def _write_paperbench_paper_fixture(tmp_path: Path) -> Path:
    paper_dir = tmp_path / "paperbench-data" / "papers" / "rice"
    paper_dir.mkdir(parents=True)
    (paper_dir / "paper.md").write_text("# RICE\n\nPaper body.\n", encoding="utf-8")
    (paper_dir / "rubric.json").write_text(
        json.dumps({"id": "root", "sub_tasks": [{"id": "env"}]}),
        encoding="utf-8",
    )
    return paper_dir


def _write_paperbench_run_fixture(tmp_path: Path) -> Path:
    run_dir = tmp_path / "paperbench-runs" / "group" / "rice_123"
    submission_dir = run_dir / "submissions" / "2026-05-07T10-08-10-UTC"
    submission_dir.mkdir(parents=True)
    (run_dir / "grade.json").write_text(
        json.dumps({
            "score": 1.0,
            "paperbench_result": {"paper_id": "rice", "submission_exists": True},
        }),
        encoding="utf-8",
    )
    (run_dir / "metadata.json").write_text("{}", encoding="utf-8")
    (run_dir / "agent.log").write_text("agent log\n", encoding="utf-8")
    (run_dir / "run.log").write_text("run log\n", encoding="utf-8")
    (submission_dir / "submission_executed_metadata.json").write_text(
        json.dumps({"repro_script_exists": True}),
        encoding="utf-8",
    )
    return run_dir


def _write_mcp_patch_round_report_fixture(tmp_path: Path) -> Path:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "solve.py").write_text("print('patched')\n", encoding="utf-8")
    (workspace / "submission.csv").write_text(
        "id,EAP,HPL,MWS\n2,0.4,0.3,0.3\n",
        encoding="utf-8",
    )
    round_dir = tmp_path / "rounds" / "round-002"
    round_dir.mkdir(parents=True)
    (round_dir / "patch.diff").write_text(
        "--- a/solve.py\n+++ b/solve.py\n@@ -1,1 +1,1 @@\n-old\n+new\n",
        encoding="utf-8",
    )
    (round_dir / "solve.log").write_text("solve log\n", encoding="utf-8")
    (round_dir / "grade.log").write_text("grade log\n", encoding="utf-8")
    round_payload = {
        "status": "graded",
        "round_id": "round-002",
        "competition_id": "spooky-author-identification",
        "workspace": str(workspace),
        "submission_path": str(workspace / "submission.csv"),
        "round_report_path": str(round_dir / "round-report.json"),
        "official_scores_claimed": False,
        "solve": {"returncode": 0, "log_path": str(round_dir / "solve.log")},
        "grade": {
            "status": "graded",
            "log_path": str(round_dir / "grade.log"),
            "report": {"score": 1.11, "valid_submission": True},
        },
    }
    (round_dir / "round-report.json").write_text(
        json.dumps(round_payload, indent=2) + "\n",
        encoding="utf-8",
    )
    report = {
        "status": "graded",
        "official_mle_bench": True,
        "official_scores_claimed": False,
        "round_id": "round-002",
        "competition_id": "spooky-author-identification",
        "workspace": str(workspace),
        "patch_diff_path": str(round_dir / "patch.diff"),
        "patch_execution": {"status": "applied"},
        "round": round_payload,
        "execution_metadata": {"command": [sys.executable, "solve.py"]},
    }
    patch_round_report = round_dir / "patch-round-report.json"
    patch_round_report.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    return patch_round_report


def _write_mcp_ag_news_fixture_csvs(tmp_path: Path) -> tuple[Path, Path]:
    train_csv = tmp_path / "train.csv"
    test_csv = tmp_path / "test.csv"
    train_csv.write_text(
        "\n".join([
            '"1","Leaders discuss treaty","Foreign ministers opened regional peace talks"',
            '"2","Team wins final","Players celebrated the championship game victory"',
            '"3","Stocks rise","Investors watched revenue growth and bank profits"',
            '"4","New processor released","Software teams tested neural chips and cloud tools"',
        ])
        + "\n",
        encoding="utf-8",
    )
    test_csv.write_text(
        "\n".join([
            '"1","Regional vote monitored","Diplomats discussed election talks"',
            '"2","Club wins match","The league team won the final game"',
            '"3","Market watches earnings","Banks reviewed company revenue"',
            '"4","Cloud platform update","Developers improved processor tools"',
        ])
        + "\n",
        encoding="utf-8",
    )
    return train_csv, test_csv


def _write_mcp_fasttext_binary(tmp_path: Path) -> Path:
    binary = tmp_path / "fasttext"
    binary.write_text(
        "\n".join([
            "#!/usr/bin/env python3",
            "from pathlib import Path",
            "import sys",
            "cmd = sys.argv[1]",
            "if cmd == 'supervised':",
            "    out = Path(sys.argv[sys.argv.index('-output') + 1])",
            "    metric = '0.875' if '-wordNgrams' in sys.argv else '0.750'",
            "    out.with_suffix('.bin').write_text(metric + '\\n', encoding='utf-8')",
            "    print('Read 8M words')",
            "    raise SystemExit(0)",
            "if cmd == 'test':",
            "    metric = Path(sys.argv[2]).read_text(encoding='utf-8').strip() or '0.750'",
            "    print('N\\t4')",
            "    print(f'P@1\\t{metric}')",
            "    print(f'R@1\\t{metric}')",
            "    raise SystemExit(0)",
            "raise SystemExit(2)",
        ])
        + "\n",
        encoding="utf-8",
    )
    binary.chmod(0o755)
    return binary


def test_initialized_notification_returns_no_response() -> None:
    assert mcp_service.handle_request(
        {"jsonrpc": "2.0", "method": "notifications/initialized"}
    ) is None


def test_unknown_tool_returns_tool_error_content() -> None:
    response = mcp_service.handle_request(
        _request(4, "tools/call", {"name": "missing_tool", "arguments": {}})
    )

    assert response["id"] == 4
    assert response["result"]["isError"] is True
    payload = json.loads(response["result"]["content"][0]["text"])
    assert payload["error"] == "Unknown MCP tool: missing_tool"


def test_autoresearch_timeout_is_unbounded_without_explicit_mcp_budget() -> None:
    assert mcp_service.subprocess_timeout(
        arguments={},
        experiment_duration=300,
        default_experiments=None,
    ) is None


def test_timeout_scales_with_explicit_experiment_count() -> None:
    assert mcp_service.subprocess_timeout(
        arguments={"max_experiments": 3},
        experiment_duration=300,
        default_experiments=None,
    ) == 990


def test_run_ai_autoresearch_tool_uses_mock_provider(monkeypatch, tmp_path) -> None:
    task_config = tmp_path / "task.json"
    task_config.write_text("{}", encoding="utf-8")
    result_file = tmp_path / "result.json"
    result_file.write_text('{"task_id": "ai-task", "status": "completed"}', encoding="utf-8")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=(
                f"RESULT_FILE={result_file}\n"
                "STATUS=completed\n"
                "BEST_VAL=0.42\n"
                "EXPERIMENTS=1\n"
            ),
        )

    monkeypatch.setattr(mcp_service, "run_mcp_subprocess", fake_run)

    payload = mcp_service.run_ai_autoresearch_tool({
        "task_config": str(task_config),
        "workspace": str(tmp_path / "workdir"),
        "runtime_root": str(tmp_path),
        "llm_provider": "mock",
        "mock_response": {
            "change_type": "hyperparam",
            "target": "DEPTH",
            "current_value": "1",
            "proposed_value": "2",
            "reason": "test",
            "confidence": 0.9,
        },
        "max_experiments": 1,
        "experiment_duration": 5,
    })

    assert payload["status"] == "completed"
    assert payload["result"]["task_id"] == "ai-task"
    assert str(mcp_service.PROJECT_ROOT / "scripts" / "ai_autoresearch_run.py") in captured["cmd"]
    assert "--mock" in captured["cmd"]
    assert "--mock-response" in captured["cmd"]
    assert "--workspace" in captured["cmd"]


def test_run_ai_autoresearch_tool_passes_real_provider_selection(monkeypatch, tmp_path) -> None:
    task_config = tmp_path / "task.json"
    task_config.write_text("{}", encoding="utf-8")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout="STATUS=completed\nEXPERIMENTS=0\n",
        )

    monkeypatch.setattr(mcp_service, "run_mcp_subprocess", fake_run)

    payload = mcp_service.run_ai_autoresearch_tool({
        "task_config": str(task_config),
        "runtime_root": str(tmp_path),
        "llm_provider": "openai",
        "llm_model": "gpt-5.5",
        "max_experiments": 1,
        "experiment_duration": 5,
    })

    assert payload["status"] == "completed"
    assert "--mock" not in captured["cmd"]
    assert "--llm-provider" in captured["cmd"]
    assert "--llm-model" in captured["cmd"]
    assert "openai" in captured["cmd"]
    assert "gpt-5.5" in captured["cmd"]


def test_run_autoresearch_rejects_task_config_outside_allowed_roots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    monkeypatch.setenv("ML_RESEARCH_LOOP_ALLOWED_ROOTS", str(runtime_root))
    outside_root = tmp_path / "outside"
    outside_root.mkdir()
    task_config = outside_root / "task.json"
    task_config.write_text("{}", encoding="utf-8")

    response = mcp_service.handle_request(
        _request(
            6,
            "tools/call",
            {
                "name": "run_autoresearch",
                "arguments": {
                    "task_config": str(task_config),
                    "runtime_root": str(runtime_root),
                    "experiment_duration": 5,
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])
    assert response["result"]["isError"] is True
    assert payload["status"] == "failed"
    assert payload["field"] == "task_config"
    assert payload["security_policy"]["allowed_roots_env"] == "ML_RESEARCH_LOOP_ALLOWED_ROOTS"


def test_run_autoresearch_rejects_workspace_outside_runtime_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("ML_RESEARCH_LOOP_ALLOWED_ROOTS", str(runtime_root))
    task_dir = runtime_root / "tasks"
    task_dir.mkdir(parents=True)
    task_config = task_dir / "task.json"
    task_config.write_text("{}", encoding="utf-8")
    outside_workspace = tmp_path / "outside-workspace"

    response = mcp_service.handle_request(
        _request(
            7,
            "tools/call",
            {
                "name": "run_autoresearch",
                "arguments": {
                    "task_config": str(task_config),
                    "runtime_root": str(runtime_root),
                    "workspace": str(outside_workspace),
                    "experiment_duration": 5,
                },
            },
        )
    )

    payload = json.loads(response["result"]["content"][0]["text"])
    assert response["result"]["isError"] is True
    assert payload["status"] == "failed"
    assert payload["field"] == "workspace"
    assert "runtime_root" in payload["error"]


def test_run_autoresearch_allows_execution_paths_inside_allowed_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("ML_RESEARCH_LOOP_ALLOWED_ROOTS", str(runtime_root))
    task_dir = runtime_root / "tasks"
    result_dir = runtime_root / "results"
    workspace = runtime_root / "workdir" / "safe-task"
    task_dir.mkdir(parents=True)
    result_dir.mkdir()
    task_config = task_dir / "safe-task.json"
    result_file = result_dir / "safe-task.json"
    task_config.write_text("{}", encoding="utf-8")
    result_file.write_text('{"task_id": "safe-task", "status": "completed"}', encoding="utf-8")
    captured = {}

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=f"RESULT_FILE={result_file}\nSTATUS=completed\nEXPERIMENTS=0\n",
        )

    monkeypatch.setattr(mcp_service, "run_mcp_subprocess", fake_run)

    payload = mcp_service.run_autoresearch_tool({
        "task_config": str(task_config),
        "runtime_root": str(runtime_root),
        "workspace": str(workspace),
        "experiment_duration": 5,
    })

    assert payload["status"] == "completed"
    assert captured["kwargs"]["env"]["ML_RESEARCH_LOOP_ROOT"] == str(runtime_root)
    assert str(task_config) in captured["cmd"]
    assert str(workspace) in captured["cmd"]


def test_run_autoresearch_reports_execution_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("ML_RESEARCH_LOOP_ALLOWED_ROOTS", str(runtime_root))
    task_dir = runtime_root / "tasks"
    result_dir = runtime_root / "results"
    workspace = runtime_root / "workdir" / "metadata-task"
    task_dir.mkdir(parents=True)
    result_dir.mkdir()
    task_config = task_dir / "metadata-task.json"
    result_file = result_dir / "metadata-task.json"
    task_config.write_text('{"task_id": "metadata-task"}', encoding="utf-8")
    result_file.write_text(
        '{"task_id": "metadata-task", "status": "completed"}',
        encoding="utf-8",
    )

    def fake_run(cmd, **kwargs):
        return subprocess.CompletedProcess(
            cmd,
            0,
            stdout=f"RESULT_FILE={result_file}\nSTATUS=completed\nEXPERIMENTS=0\n",
        )

    monkeypatch.setattr(mcp_service, "run_mcp_subprocess", fake_run)

    payload = mcp_service.run_autoresearch_tool({
        "task_config": str(task_config),
        "runtime_root": str(runtime_root),
        "workspace": str(workspace),
        "python": sys.executable,
        "max_experiments": 1,
        "experiment_duration": 5,
    })

    metadata = payload["execution_metadata"]
    assert metadata["wall_time_seconds"] >= 0
    assert metadata["python_executable"] == sys.executable
    assert metadata["timeout_policy"]["subprocess_timeout_seconds"] == 120
    assert metadata["timeout_policy"]["experiment_duration_seconds"] == 5
    assert metadata["timeout_policy"]["max_experiments"] == 1
    assert metadata["execution_sandbox"]["status"] == "enforced"
    assert str(runtime_root) in metadata["sandbox_roots"]
    assert metadata["artifact_retention"]["runtime_root"] == str(runtime_root)
    assert metadata["artifact_retention"]["task_file"] == str(task_config)
    assert metadata["artifact_retention"]["result_file"] == str(result_file)
    assert metadata["artifact_retention"]["workspace"] == str(workspace)


def test_run_mcp_subprocess_reports_startup_failure(tmp_path) -> None:
    missing_binary = tmp_path / "missing-python"

    with pytest.raises(mcp_service.MCPToolError) as exc_info:
        mcp_service.run_mcp_subprocess(
            [str(missing_binary), "-c", "print('never')"],
            cwd=tmp_path,
            env=dict(os.environ),
            timeout_seconds=5,
        )

    assert exc_info.value.payload["status"] == "failed"
    assert exc_info.value.payload["error_type"] == "startup_failed"
    assert str(missing_binary) in exc_info.value.payload["error"]


def test_run_mcp_subprocess_reports_timeout_and_kills_process(tmp_path) -> None:
    sentinel = tmp_path / "child-survived.txt"
    command = [
        sys.executable,
        "-c",
        (
            "import pathlib,subprocess,sys,time;"
            f"sentinel={str(sentinel)!r};"
            "subprocess.Popen([sys.executable,'-c',"
            "'import pathlib,time; time.sleep(2); pathlib.Path(%r).write_text(\"alive\")' % sentinel]);"
            "time.sleep(20)"
        ),
    ]

    with pytest.raises(mcp_service.MCPToolError) as exc_info:
        mcp_service.run_mcp_subprocess(
            command,
            cwd=tmp_path,
            env=dict(os.environ),
            timeout_seconds=1,
        )

    assert exc_info.value.payload["status"] == "failed"
    assert exc_info.value.payload["error_type"] == "timeout"
    assert exc_info.value.payload["timeout_seconds"] == 1
    time.sleep(2.5)
    assert not sentinel.exists()


def test_get_service_manifest_returns_client_contract() -> None:
    payload = mcp_service.get_service_manifest_tool({})

    assert payload["contract_version"] == "2026-04-30.preview.v1"
    assert payload["schema_versions"] == {
        "service_manifest": "2026-04-30.preview.v1",
        "tool_inputs": "2026-04-30.preview.v1",
        "tool_outputs": "2026-04-30.preview.v1",
        "runtime_artifacts": "2026-04-30.preview.v1",
    }
    assert payload["compatibility"] == {
        "status": "preview",
        "breaking_changes": "allowed only with a contract_version change",
        "client_requirement": "check contract_version before planning automated loops",
    }
    assert payload["architecture"] == "hybrid_client_planner_server_executor"
    assert payload["product_status"] == "preview"
    assert payload["execution_sandbox"] == {
        "status": "enforced",
        "allowed_roots_env": "ML_RESEARCH_LOOP_ALLOWED_ROOTS",
        "default_allowed_roots": ["project_root", "ML_RESEARCH_LOOP_ROOT"],
        "rules": [
            "execution task_config/runtime_root/workspace paths must be inside allowed roots",
            "workspace must stay inside runtime_root when both are provided",
        ],
    }
    assert "Codex/Claude" in payload["client_model_role"]
    assert payload["server_side_llm"]["tool"] == "run_ai_autoresearch"
    assert payload["benchmark_adapters"]["status"] == "compatibility_ready"
    assert payload["benchmark_adapters"]["official_scores_claimed"] is False
    assert [adapter["name"] for adapter in payload["benchmark_adapters"]["adapters"]] == [
        "mle_bench",
        "paperbench",
    ]
    assert payload["benchmark_harness_probe"]["read_only"] is True
    assert payload["benchmark_harness_probe"]["official_scores_claimed"] is False
    assert [harness["name"] for harness in payload["benchmark_harness_probe"]["harnesses"]] == [
        "mle_bench",
        "paperbench",
    ]
    assert payload["benchmark_proof_plan"]["read_only"] is True
    assert payload["benchmark_proof_plan"]["official_scores_claimed"] is False
    assert payload["benchmark_proof_plan"]["status"] in {"blocked", "ready_for_debug_run"}
    assert "harness_probe" in payload["benchmark_proof_plan"]
    assert payload["benchmark_proof_setup"]["read_only"] is True
    assert payload["benchmark_proof_setup"]["official_scores_claimed"] is False
    assert "environment_template" in payload["benchmark_proof_setup"]
    assert payload["benchmark_proof_publication"]["read_only"] is True
    assert payload["benchmark_proof_publication"]["official_scores_claimed"] is False
    assert "claim_policy" in payload["benchmark_proof_publication"]
    assert payload["benchmark_proof_archive"]["evaluation_runs_launched"] is False
    assert payload["benchmark_proof_archive"]["official_scores_claimed"] is False
    assert "artifact_index" in payload["benchmark_proof_archive"]
    assert payload["hf_external_eval_targets"]["official_scores_claimed"] is False
    assert payload["hf_external_eval_targets"]["target_count"] >= 5
    assert payload["hf_external_eval_plan"]["official_scores_claimed"] is False
    assert (
        payload["hf_external_eval_plan"]["target"]["target_id"]
        == "cp-bench-constraint-modeling"
    )
    assert payload["cp_bench_live_verification"]["official_scores_claimed"] is False
    assert payload["cp_bench_live_verification"]["tool"] == (
        "write_cp_bench_live_verification"
    )
    assert payload["cp_bench_local_baseline"]["official_scores_claimed"] is False
    assert payload["cp_bench_local_baseline"]["tool"] == "run_cp_bench_local_baseline"
    assert payload["cp_bench_proposal_round"]["official_scores_claimed"] is False
    assert payload["cp_bench_proposal_round"]["tool"] == "run_cp_bench_proposal_round"
    assert payload["cp_bench_candidate_round"]["official_scores_claimed"] is False
    assert payload["cp_bench_candidate_round"]["tool"] == "run_cp_bench_candidate_round"
    assert payload["cp_bench_proposal_context"]["official_scores_claimed"] is False
    assert payload["cp_bench_proposal_context"]["tool"] == "build_cp_bench_proposal_context"
    assert payload["cp_bench_client_candidate"]["official_scores_claimed"] is False
    assert payload["cp_bench_client_candidate"]["tool"] == (
        "write_cp_bench_client_candidate_submission"
    )
    assert payload["cp_bench_submission_gate"]["official_scores_claimed"] is False
    assert payload["cp_bench_submission_gate"]["tool"] == "write_cp_bench_submission_gate"
    assert payload["smol_worldcup_live_verification"]["official_scores_claimed"] is False
    assert payload["smol_worldcup_live_verification"]["tool"] == (
        "write_smol_worldcup_live_verification"
    )
    assert payload["smol_worldcup_prompt_leakage_audit"]["official_scores_claimed"] is False
    assert payload["smol_worldcup_prompt_leakage_audit"]["tool"] == (
        "write_smol_worldcup_prompt_leakage_audit"
    )
    assert payload["smol_worldcup_local_baseline"]["official_scores_claimed"] is False
    assert payload["smol_worldcup_local_baseline"]["tool"] == (
        "run_smol_worldcup_local_baseline"
    )
    assert payload["smol_worldcup_model_eval"]["official_scores_claimed"] is False
    assert payload["smol_worldcup_model_eval"]["tool"] == "run_smol_worldcup_model_eval"
    assert payload["smol_worldcup_model_eval"]["default_model"] == "openai/gpt-oss-20b"
    assert payload["smol_worldcup_proposal_round"]["official_scores_claimed"] is False
    assert payload["smol_worldcup_proposal_round"]["tool"] == (
        "run_smol_worldcup_proposal_round"
    )
    assert payload["smol_worldcup_proposal_round"]["promotion_split"] == "canary"
    assert payload["smol_worldcup_rescore"]["official_scores_claimed"] is False
    assert payload["smol_worldcup_rescore"]["tool"] == "run_smol_worldcup_rescore"
    assert payload["recommended_workflows"][0]["tools"][0] == "research_task"
    assert (
        "python3 scripts/proposal_contract_smoke.py "
        "--output-dir .demo_runs/proposal-contract --json"
    ) in payload["acceptance_commands"]
    assert "plan_research_case" in payload["required_tools"]
    assert "run_hypothesis_experiment" in payload["required_tools"]
    assert "run_client_patch_experiment" in payload["required_tools"]
    assert "apply_client_code_patch" in payload["required_tools"]
    assert "build_proposal_context" in payload["required_tools"]
    assert "validate_client_proposal_contract" in payload["required_tools"]
    assert "write_proposal_reflection" in payload["required_tools"]
    assert "summarize_proposal_search" in payload["required_tools"]
    assert "run_next_experiment_from_review" in payload["required_tools"]
    assert "get_benchmark_harness_probe" in payload["required_tools"]
    assert "write_benchmark_proof_archive" in payload["required_tools"]
    assert "get_hf_external_eval_targets" in payload["required_tools"]
    assert "write_hf_external_eval_plan" in payload["required_tools"]
    assert "write_cp_bench_live_verification" in payload["required_tools"]
    assert "run_cp_bench_local_baseline" in payload["required_tools"]
    assert "run_cp_bench_proposal_round" in payload["required_tools"]
    assert "run_cp_bench_candidate_round" in payload["required_tools"]
    assert "build_cp_bench_proposal_context" in payload["required_tools"]
    assert "write_cp_bench_client_candidate_submission" in payload["required_tools"]
    assert "write_cp_bench_submission_gate" in payload["required_tools"]
    assert "write_smol_worldcup_live_verification" in payload["required_tools"]
    assert "write_smol_worldcup_prompt_leakage_audit" in payload["required_tools"]
    assert "run_smol_worldcup_local_baseline" in payload["required_tools"]
    assert "run_smol_worldcup_model_eval" in payload["required_tools"]
    assert "run_smol_worldcup_proposal_round" in payload["required_tools"]
    assert "run_smol_worldcup_rescore" in payload["required_tools"]
    assert "prepare_official_mle_bench_workspace" in payload["required_tools"]
    assert "grade_official_mle_bench_submission" in payload["required_tools"]
    assert "run_official_mle_bench_round" in payload["required_tools"]
    assert "run_official_mle_bench_patch_round" in payload["required_tools"]
    assert "write_official_mle_bench_patch_round_proof_bundle" in payload["required_tools"]
    assert "run_fasttext_patch_round" in payload["required_tools"]
    assert "write_fasttext_patch_round_proof_bundle" in payload["required_tools"]
    assert "run_fasttext_multi_proposal_loop" in payload["required_tools"]
    assert "write_fasttext_release_proof_bundle" in payload["required_tools"]
    assert "record_research_memory" in payload["required_tools"]
    assert "retrieve_research_memory" in payload["required_tools"]
    assert "suggest_from_memory" in payload["required_tools"]
    assert "promote_memory_card" in payload["required_tools"]
    assert "audit_memory_trace" in payload["required_tools"]
    assert "prepare_paperbench_codex_review_bundle" in payload["required_tools"]
    assert "write_paperbench_codex_review_report" in payload["required_tools"]
    assert payload["planning_signals"] == [
        "cache",
        "cache.cache_scope",
        "cache.freshness_seconds",
        "evidence_quality",
        "evidence_quality.source_class_counts",
        "evidence_citations.source_trace",
        "source.metadata.source_id",
        "deduplication_report",
        "cache_summary",
        "provider_quality_matrix",
        "provider_coverage",
        "source_rankings",
        "retrieval_diagnostics",
        "research_case",
        "research_evidence_gate",
        "dataset_profile",
        "experiment_tree",
        "loop_policy",
        "failure_diagnostics",
        "metric_stop_policy",
        "reproduction.readiness",
        "execution_metadata",
        "code_change_plan",
        "code_change_plan.next_experiment_plan",
        "code_change_plan.next_experiment_plan.proposed_task_patch",
        "code_change_plan.next_experiment_plan.dry_run_validation",
        "code_change_plan.next_experiment_plan.diff_preview",
        "code_change_plan.next_experiment_plan.execution_guardrails",
        "run_next_experiment_from_review.final_review",
        "run_next_experiment_from_review.loop_decision",
        "run_client_patch_experiment.patch_execution",
        "run_client_patch_experiment.loop_decision",
        "apply_client_code_patch.patch_execution",
        "apply_client_code_patch.post_patch_review",
        "apply_client_code_patch.loop_decision",
            "proposal_context",
            "proposal_contract.validation",
            "proposal_reflection",
            "proposal_search.frontier",
            "benchmark_adapters",
        "benchmark_adapters.adapters",
        "benchmark_adapters.combined_smoke",
        "benchmark_harness_probe",
        "benchmark_proof_plan",
        "benchmark_proof_setup",
        "benchmark_proof_publication",
            "benchmark_proof_archive",
                "hf_external_eval_targets",
                "hf_external_eval_plan",
                "cp_bench_live_verification",
                "cp_bench_local_baseline",
                "cp_bench_proposal_round",
                "cp_bench_candidate_round",
                "cp_bench_proposal_context",
                "cp_bench_client_candidate",
                "cp_bench_submission_gate",
                "smol_worldcup_live_verification",
            "smol_worldcup_prompt_leakage_audit",
            "smol_worldcup_local_baseline",
            "smol_worldcup_model_eval",
            "smol_worldcup_proposal_round",
            "smol_worldcup_rescore",
            "smol_worldcup_rescore_proof_archive",
            "smol_worldcup_submission_probe",
            "official_mle_agent_workspace",
        "official_mle_grade_sample",
        "official_mle_solver_round",
        "official_mle_patch_round",
        "official_mle_patch_proof_archive",
        "full_reproduction_fasttext_patch_round",
        "full_reproduction_fasttext_patch_proof_bundle",
        "full_reproduction_fasttext_multi_proposal_loop",
        "full_reproduction_fasttext_release_proof_bundle",
        "paperbench_codex_review_bundle",
        "paperbench_codex_review_report",
        "research_memory",
        "research_memory.suggestions",
        "research_memory.trace",
        "planner_actions",
        "next_round.task_patch",
    ]
    assert set(payload["tool_contracts"]) == set(payload["required_tools"])
    assert any("mcp_auto_next_demo.py" in item for item in payload["acceptance_commands"])
    assert any("mcp_provider_quality_benchmark.py" in item for item in payload["acceptance_commands"])
    assert any("mcp_real_task_code_benchmark.py" in item for item in payload["acceptance_commands"])
    assert any("benchmark_adapter_smoke.py" in item for item in payload["acceptance_commands"])
    assert any("benchmark_harness_probe.py" in item for item in payload["acceptance_commands"])
    assert any("benchmark_proof_plan.py" in item for item in payload["acceptance_commands"])
    assert any("benchmark_proof_setup.py" in item for item in payload["acceptance_commands"])
    assert any("benchmark_proof_publication.py" in item for item in payload["acceptance_commands"])
    assert any("benchmark_proof_archive.py" in item for item in payload["acceptance_commands"])
    assert any("ml-loop hf-eval shortlist" in item for item in payload["acceptance_commands"])
    assert any(
        "smol-worldcup-verify" in item
        for item in payload["acceptance_commands"]
    )
    assert any(
        "smol-worldcup-baseline" in item
        for item in payload["acceptance_commands"]
    )
    assert any("smol-worldcup-rescore" in item for item in payload["acceptance_commands"])
    assert any(
        "smol-worldcup-rescore-proof-archive" in item
        for item in payload["acceptance_commands"]
    )
    assert any(
        "smol-worldcup-submission-probe" in item
        for item in payload["acceptance_commands"]
    )
    assert any("mle-workspace" in item for item in payload["acceptance_commands"])
    assert any("mle-patch-proof" in item for item in payload["acceptance_commands"])
    assert any(
        "paperbench-codex-review-bundle" in item
        for item in payload["acceptance_commands"]
    )
    assert any(
        "paperbench-codex-review-report" in item
        for item in payload["acceptance_commands"]
    )
    assert any(
        workflow["name"] == "paperbench_codex_assisted_review"
        for workflow in payload["recommended_workflows"]
    )
    assert "wall_time_seconds" in payload["execution_metadata_contract"]["required_fields"]
    assert "subprocess_timeout_seconds" in payload["execution_metadata_contract"]["timeout_policy_fields"]
    assert payload["skill_package"]["status"] == "repo_local"
    assert payload["skill_package"]["install_command"] == "ml-loop init-skills"
    assert payload["recommended_skills"] == [
        "ml-research-loop-planner",
        "ml-research-loop-reproduction",
        "ml-research-loop-experiment-optimizer",
        "ml-research-loop-operator",
    ]
    assert set(payload["skill_contracts"]) == set(payload["recommended_skills"])
    planner_contract = payload["skill_contracts"]["ml-research-loop-planner"]
    assert planner_contract["contract_version"] == "2026-04-30.preview.v1"
    assert planner_contract["path"] == "skills/ml-research-loop-planner/SKILL.md"
    assert planner_contract["client_role"] == "workflow_planner"
    assert "get_service_manifest" in planner_contract["required_tools"]
    assert "plan_research_case" in planner_contract["required_tools"]
    assert "review_research_results" in planner_contract["required_tools"]
    assert "get_benchmark_harness_probe" in planner_contract["required_tools"]
    assert "write_benchmark_proof_archive" in planner_contract["required_tools"]
    assert "prepare_official_mle_bench_workspace" in planner_contract["required_tools"]
    assert "grade_official_mle_bench_submission" in planner_contract["required_tools"]
    assert "run_official_mle_bench_round" in planner_contract["required_tools"]
    assert "run_official_mle_bench_patch_round" in planner_contract["required_tools"]
    assert "write_official_mle_bench_patch_round_proof_bundle" in planner_contract["required_tools"]
    assert "run_fasttext_patch_round" in planner_contract["required_tools"]
    assert "write_fasttext_patch_round_proof_bundle" in planner_contract["required_tools"]
    assert "prepare_paperbench_codex_review_bundle" in planner_contract["required_tools"]
    assert "write_paperbench_codex_review_report" in planner_contract["required_tools"]
    assert "build_proposal_context" in planner_contract["required_tools"]
    assert "validate_client_proposal_contract" in planner_contract["required_tools"]
    assert "write_proposal_reflection" in planner_contract["required_tools"]
    assert "research_evidence_gate" in planner_contract["planning_signals"]
    assert "research_case" in planner_contract["planning_signals"]
    assert "benchmark_proof_archive" in planner_contract["planning_signals"]
    assert "official_mle_agent_workspace" in planner_contract["planning_signals"]
    assert "official_mle_solver_round" in planner_contract["planning_signals"]
    assert "official_mle_patch_round" in planner_contract["planning_signals"]
    assert "official_mle_patch_proof_archive" in planner_contract["planning_signals"]
    assert "full_reproduction_fasttext_patch_round" in planner_contract["planning_signals"]
    assert "full_reproduction_fasttext_patch_proof_bundle" in planner_contract["planning_signals"]
    assert "paperbench_codex_review_bundle" in planner_contract["planning_signals"]
    assert "paperbench_codex_review_report" in planner_contract["planning_signals"]
    assert "research_memory" in planner_contract["planning_signals"]
    assert "proposal_context" in planner_contract["planning_signals"]
    assert "human_confirmation" in planner_contract["safety_rules"]
    for tool_name, contract in payload["tool_contracts"].items():
        assert contract["input_schema_version"] == "2026-04-30.preview.v1"
        assert contract["output_schema_version"] == "2026-04-30.preview.v1"
        assert contract["stability"] == "preview"
        assert contract["description"]


def test_retrieve_research_memory_returns_provenance(tmp_path: Path) -> None:
    store = tmp_path / "memory.jsonl"
    artifact = tmp_path / "proof.json"
    artifact.write_text('{"official_scores_claimed": false}', encoding="utf-8")
    ResearchMemoryStore(store).append(
        ResearchMemoryCard(
            card_id="mem-proof",
            memory_type="evidence",
            task_family="text-classification",
            summary="AG News proof memory.",
            paper_ids=["arxiv:1607.01759"],
            datasets=["AG News"],
            artifact_refs=[MemoryArtifactRef.from_path("proof", artifact)],
        )
    )

    payload = mcp_service.retrieve_research_memory_tool(
        {"store": str(store), "query": "AG News", "paper_id": "arxiv:1607.01759"}
    )

    assert payload["status"] == "completed"
    assert payload["executes_tool"] is False
    assert payload["matches"][0]["card"]["card_id"] == "mem-proof"
    assert payload["matches"][0]["card"]["artifact_refs"][0]["sha256"]


def test_build_proposal_context_tool_writes_artifacts(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    current = tmp_path / "current.json"
    rollback = tmp_path / "rollback.json"
    memory_store = tmp_path / "proposal-memory.jsonl"
    baseline.write_text('{"SHIFT": 1}', encoding="utf-8")
    current.write_text('{"SHIFT": 2}', encoding="utf-8")
    rollback.write_text('{"rollback_events": 1}', encoding="utf-8")
    ResearchMemoryStore(memory_store).append(
        ResearchMemoryCard(
            card_id="mcp-fasttext-memory",
            memory_type="procedure",
            task_family="proposal-reflection",
            summary="fastText proposal memory for AG News.",
        )
    )

    payload = mcp_service.build_proposal_context_tool({
        "objective": "Improve local metric",
        "output_dir": str(tmp_path / "context"),
        "baseline_report": str(baseline),
        "current_report": str(current),
        "rollback_summary": str(rollback),
        "memory_store": str(memory_store),
        "memory_query": {"query": "fastText proposal"},
        "memory_limit": 1,
        "resource_constraints": {"max_rounds": 5},
        "allowed_change_surfaces": ["prompt_profile"],
    })

    assert payload["status"] == "ready_for_client_proposal"
    assert payload["executes_tool"] is False
    assert payload["official_scores_claimed"] is False
    assert payload["inputs"]["rollback_summary"]["raw"]["rollback_events"] == 1
    assert payload["inputs"]["memory_cards"]["metrics"]["retrieved_count"] == 1
    assert payload["inputs"]["resource_constraints"]["raw"]["max_rounds"] == 5
    assert payload["artifact_manifest"]["artifacts"]["memory_cards"]["path"] == str(
        memory_store
    )
    assert Path(payload["context_file"]).exists()


def test_validate_client_proposal_contract_tool_rejects_invalid_surface() -> None:
    payload = mcp_service.validate_client_proposal_contract_tool({
        "proposal": {
            "proposal_id": "bad",
            "hypothesis": "Change too much",
            "change_surface": "training_recipe",
            "change_spec": {"single_primary_variable": False},
        },
        "allowed_change_surfaces": ["prompt_profile"],
    })

    assert payload["status"] == "rejected"
    assert "change_surface_not_allowed" in payload["failure_labels"]


def test_write_proposal_reflection_tool_writes_artifacts(tmp_path: Path) -> None:
    payload = mcp_service.write_proposal_reflection_tool({
        "proposal": {
            "proposal_id": "round-001",
            "hypothesis": "A bounded routing change can improve SHIFT.",
            "evidence_used": [{"artifact": "dev_report", "observation": "delta"}],
            "change_surface": "routing",
            "change_spec": {"single_primary_variable": True, "target": "router"},
            "expected_effect": {"primary_metric": "SHIFT", "expected_direction": "increase"},
            "validation_plan": {
                "first_split": "dev",
                "promotion_split": "canary",
                "rollback_if": ["SHIFT_delta_lt_0"],
            },
            "risk_assessment": {"overfit_risk": "low"},
            "next_if_success": "promote_candidate_profile",
            "next_if_failure": "rollback_candidate",
            "claim_boundary": "local diagnostic proposal only",
        },
        "evaluation": {"rollback_reasons": ["canary_not_confirmed"]},
        "output_dir": str(tmp_path / "reflection"),
    })

    assert payload["status"] == "needs_rollback_or_more_evidence"
    assert payload["failure_labels"] == ["canary_not_confirmed"]
    assert Path(payload["reflection_file"]).exists()


def test_suggest_from_memory_is_advisory(tmp_path: Path) -> None:
    store = tmp_path / "memory.jsonl"
    artifact = tmp_path / "patch.json"
    artifact.write_text('{"delta": 0.002}', encoding="utf-8")
    ResearchMemoryStore(store).append(
        ResearchMemoryCard(
            card_id="mem-patch",
            memory_type="patch",
            task_family="text-classification",
            summary="wordNgrams=2 improved local AG News P@1.",
            paper_ids=["arxiv:1607.01759"],
            datasets=["AG News"],
            patch_type="hyperparameter",
            artifact_refs=[MemoryArtifactRef.from_path("patch", artifact)],
            claim_boundary="local proof only",
        )
    )

    payload = mcp_service.suggest_from_memory_tool(
        {"store": str(store), "query": "AG News", "paper_id": "arxiv:1607.01759"}
    )

    assert payload["status"] == "completed"
    assert payload["executes_tool"] is False
    assert payload["suggestions"][0]["executes_tool"] is False
    assert payload["suggestions"][0]["recommended_mcp_tool"] == (
        "run_client_patch_experiment"
    )


def test_record_and_audit_research_memory_tool(tmp_path: Path) -> None:
    store = tmp_path / "memory.jsonl"
    artifact = tmp_path / "review.json"
    artifact.write_text("{}", encoding="utf-8")

    record = mcp_service.record_research_memory_tool(
        {
            "store": str(store),
            "card": {
                "card_id": "mem-review",
                "memory_type": "failure",
                "task_family": "text-classification",
                "summary": "Timeout debug memory.",
                "failure_category": "timeout",
                "artifact_refs": [
                    MemoryArtifactRef.from_path("review", artifact).to_dict()
                ],
                "claim_boundary": "debug memory only",
            },
        }
    )

    assert record["status"] == "recorded"
    assert record["card_ids"] == ["mem-review"]

    trace = mcp_service.audit_memory_trace_tool(
        {"store": str(store), "card_ids": ["mem-review"]}
    )

    assert trace["status"] == "completed"
    assert trace["trace"]["cards"][0]["card_id"] == "mem-review"
    assert trace["trace"]["claim_boundaries"] == ["debug memory only"]


def test_research_memory_mcp_can_sync_and_search_optional_adapters(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    store = tmp_path / "memory.jsonl"
    artifact = tmp_path / "review.json"
    artifact.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        mcp_service,
        "sync_cards_to_adapters",
        lambda cards, adapter_names=None: {
            "status": "completed",
            "adapter_names": adapter_names,
            "card_count": len(cards),
            "results": [{"adapter": "graphiti", "status": "indexed"}],
        },
    )
    monkeypatch.setattr(
        mcp_service,
        "search_memory_adapters",
        lambda *, query, limit=10, adapter_names=None: {
            "status": "completed",
            "adapter_names": adapter_names,
            "results": [{"adapter": "cognee", "text": query, "score": 0.8}],
        },
    )

    record = mcp_service.record_research_memory_tool(
        {
            "store": str(store),
            "sync_adapters": True,
            "adapters": ["graphiti"],
            "card": {
                "card_id": "mem-review",
                "memory_type": "failure",
                "task_family": "text-classification",
                "summary": "Timeout debug memory.",
                "failure_category": "timeout",
                "artifact_refs": [
                    MemoryArtifactRef.from_path("review", artifact).to_dict()
                ],
                "claim_boundary": "debug memory only",
            },
        }
    )

    assert record["adapter_results"]["adapter_names"] == ["graphiti"]
    assert record["adapter_results"]["results"][0]["status"] == "indexed"

    retrieve = mcp_service.retrieve_research_memory_tool(
        {
            "store": str(store),
            "query": "Timeout",
            "include_adapters": True,
            "adapters": ["cognee"],
        }
    )

    assert retrieve["adapter_results"]["adapter_names"] == ["cognee"]
    assert retrieve["adapter_results"]["results"][0]["adapter"] == "cognee"


def test_manifest_reports_fit_first_upstream_patterns() -> None:
    payload = mcp_service.get_service_manifest_tool({})

    assert payload["upstream_patterns"] == {
        "aide": {
            "integration_mode": "architecture_pattern",
            "enabled_features": ["experiment_tree", "best_node_tracking", "loop_policy"],
            "direct_dependency": False,
        },
        "paperbench": {
            "integration_mode": "architecture_pattern",
            "enabled_features": ["reproduction_spec", "rubric_grade_report"],
            "direct_dependency": False,
        },
    }


def test_prepare_official_mle_bench_workspace_tool_returns_agent_handoff(tmp_path) -> None:
    prepared_competition_dir = _write_mcp_prepared_mle_fixture(tmp_path)
    runtime_root = tmp_path / "runtime"

    payload = mcp_service.prepare_official_mle_bench_workspace_tool({
        "competition_id": "spooky-author-identification",
        "prepared_competition_dir": str(prepared_competition_dir),
        "runtime_root": str(runtime_root),
        "workspace_name": "spooky-debug",
    })

    assert payload["status"] == "ready_for_agent"
    assert payload["official_mle_bench"] is True
    assert payload["official_scores_claimed"] is False
    assert payload["workspace"].startswith(str(runtime_root))
    assert payload["execution_metadata"]["artifact_retention"]["runtime_root"] == str(runtime_root)
    assert payload["execution_metadata"]["artifact_retention"]["workspace"] == payload["workspace"]


def test_grade_official_mle_bench_submission_tool_returns_local_score_feedback(
    tmp_path,
) -> None:
    submission = tmp_path / "workspace" / "submission.csv"
    submission.parent.mkdir()
    submission.write_text("id,EAP,HPL,MWS\n2,0.33,0.33,0.34\n", encoding="utf-8")
    data_dir = tmp_path / "mlebench-data"
    data_dir.mkdir()
    mlebench = tmp_path / "bin" / "mlebench"
    mlebench.parent.mkdir()
    mlebench.write_text(
        "\n".join([
            "#!/usr/bin/env python3",
            "import json",
            "print('Competition report:')",
            "print(json.dumps({'score': 1.23, 'valid_submission': True}))",
        ]),
        encoding="utf-8",
    )
    mlebench.chmod(0o755)

    payload = mcp_service.grade_official_mle_bench_submission_tool({
        "competition_id": "spooky-author-identification",
        "submission": str(submission),
        "data_dir": str(data_dir),
        "mlebench": str(mlebench),
        "output_dir": str(tmp_path / "reports"),
        "timeout_seconds": 10,
    })

    assert payload["status"] == "graded"
    assert payload["report"]["score"] == 1.23
    assert payload["official_scores_claimed"] is False
    assert payload["execution_metadata"]["timeout_policy"]["subprocess_timeout_seconds"] == 10


def test_run_official_mle_bench_round_tool_returns_solve_and_grade_artifacts(
    tmp_path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "solve.py").write_text(
        "\n".join([
            "from pathlib import Path",
            "Path('submission.csv').write_text('id,EAP,HPL,MWS\\n2,0.2,0.3,0.5\\n')",
            "print('wrote submission')",
        ]),
        encoding="utf-8",
    )
    data_dir = tmp_path / "mlebench-data"
    data_dir.mkdir()
    mlebench = tmp_path / "bin" / "mlebench"
    mlebench.parent.mkdir()
    mlebench.write_text(
        "\n".join([
            "#!/usr/bin/env python3",
            "import json",
            "print('Competition report:')",
            "print(json.dumps({'score': 1.23, 'valid_submission': True}))",
        ]),
        encoding="utf-8",
    )
    mlebench.chmod(0o755)

    payload = mcp_service.run_official_mle_bench_round_tool({
        "competition_id": "spooky-author-identification",
        "workspace": str(workspace),
        "data_dir": str(data_dir),
        "mlebench": str(mlebench),
        "output_dir": str(tmp_path / "rounds"),
        "python": sys.executable,
        "round_id": "round-001",
        "timeout_seconds": 10,
    })

    assert payload["status"] == "graded"
    assert payload["round_id"] == "round-001"
    assert payload["solve"]["returncode"] == 0
    assert payload["grade"]["report"]["score"] == 1.23
    assert payload["official_scores_claimed"] is False
    assert Path(payload["round_report_path"]).is_file()
    assert payload["execution_metadata"]["timeout_policy"]["subprocess_timeout_seconds"] == 10


def test_run_official_mle_bench_patch_round_tool_applies_patch_then_grades(
    tmp_path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "solve.py").write_text(
        "\n".join([
            "from pathlib import Path",
            "Path('submission.csv').write_text('id,EAP,HPL,MWS\\n2,0.2,0.3,0.5\\n')",
            "print('wrote submission')",
        ]),
        encoding="utf-8",
    )
    data_dir = tmp_path / "mlebench-data"
    data_dir.mkdir()
    mlebench = tmp_path / "bin" / "mlebench"
    mlebench.parent.mkdir()
    mlebench.write_text(
        "\n".join([
            "#!/usr/bin/env python3",
            "import json",
            "print('Competition report:')",
            "print(json.dumps({'score': 1.11, 'valid_submission': True}))",
        ]),
        encoding="utf-8",
    )
    mlebench.chmod(0o755)
    patch = "\n".join([
        "--- a/solve.py",
        "+++ b/solve.py",
        "@@ -1,3 +1,3 @@",
        " from pathlib import Path",
        "-Path('submission.csv').write_text('id,EAP,HPL,MWS\\n2,0.2,0.3,0.5\\n')",
        "-print('wrote submission')",
        "+Path('submission.csv').write_text('id,EAP,HPL,MWS\\n2,0.4,0.3,0.3\\n')",
        "+print('wrote patched submission')",
    ])

    payload = mcp_service.run_official_mle_bench_patch_round_tool({
        "competition_id": "spooky-author-identification",
        "workspace": str(workspace),
        "data_dir": str(data_dir),
        "mlebench": str(mlebench),
        "output_dir": str(tmp_path / "rounds"),
        "patch": patch,
        "python": sys.executable,
        "round_id": "round-002",
        "timeout_seconds": 10,
    })

    assert payload["status"] == "graded"
    assert payload["official_scores_claimed"] is False
    assert payload["round_id"] == "round-002"
    assert payload["patch_execution"]["status"] == "applied"
    assert payload["patch_execution"]["changed_files"] == ["solve.py"]
    assert payload["round"]["status"] == "graded"
    assert payload["round"]["solve"]["returncode"] == 0
    assert payload["round"]["grade"]["report"]["score"] == 1.11
    assert payload["loop_decision"]["recommended_next_action"] == "continue"
    assert payload["loop_decision"]["reason_category"] == "valid_local_score"
    assert "patched" in (workspace / "solve.py").read_text(encoding="utf-8")
    assert Path(payload["round"]["round_report_path"]).is_file()
    patch_round_report = Path(payload["patch_round_report_path"])
    patch_diff = Path(payload["patch_diff_path"])
    assert patch_round_report.is_file()
    assert patch_diff.is_file()
    written_report = json.loads(patch_round_report.read_text(encoding="utf-8"))
    assert written_report["patch_execution"]["status"] == "applied"
    assert written_report["round"]["status"] == "graded"
    assert written_report["official_scores_claimed"] is False
    assert patch_diff.read_text(encoding="utf-8") == patch + "\n"


def test_run_official_mle_bench_patch_round_tool_validates_paths_before_patch(
    tmp_path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    solve_py = workspace / "solve.py"
    original = "print('original')\n"
    solve_py.write_text(original, encoding="utf-8")
    patch = "\n".join([
        "--- a/solve.py",
        "+++ b/solve.py",
        "@@ -1,1 +1,1 @@",
        "-print('original')",
        "+print('patched')",
    ])

    with pytest.raises(mcp_service.MCPToolError) as exc_info:
        mcp_service.run_official_mle_bench_patch_round_tool({
            "competition_id": "spooky-author-identification",
            "workspace": str(workspace),
            "data_dir": str(tmp_path.parent / "outside-mlebench-data"),
            "mlebench": str(tmp_path / "bin" / "mlebench"),
            "output_dir": str(tmp_path / "rounds"),
            "patch": patch,
            "python": sys.executable,
            "round_id": "round-002",
            "timeout_seconds": 10,
        })

    assert exc_info.value.payload["field"] == "data_dir"
    assert solve_py.read_text(encoding="utf-8") == original


def test_run_official_mle_bench_patch_round_tool_rejects_wider_allowed_files(
    tmp_path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "solve.py").write_text(
        "from pathlib import Path\n"
        "Path('submission.csv').write_text('id,EAP,HPL,MWS\\n2,0.2,0.3,0.5\\n')\n",
        encoding="utf-8",
    )
    train_py = workspace / "train.py"
    original_train = "VALUE = 1\n"
    train_py.write_text(original_train, encoding="utf-8")
    data_dir = tmp_path / "mlebench-data"
    data_dir.mkdir()
    mlebench = tmp_path / "bin" / "mlebench"
    mlebench.parent.mkdir()
    mlebench.write_text(
        "\n".join([
            "#!/usr/bin/env python3",
            "import json",
            "print('Competition report:')",
            "print(json.dumps({'score': 1.11, 'valid_submission': True}))",
        ]),
        encoding="utf-8",
    )
    mlebench.chmod(0o755)
    patch = "\n".join([
        "--- a/train.py",
        "+++ b/train.py",
        "@@ -1,1 +1,1 @@",
        "-VALUE = 1",
        "+VALUE = 2",
    ])

    with pytest.raises(mcp_service.MCPToolError) as exc_info:
        mcp_service.run_official_mle_bench_patch_round_tool({
            "competition_id": "spooky-author-identification",
            "workspace": str(workspace),
            "data_dir": str(data_dir),
            "mlebench": str(mlebench),
            "output_dir": str(tmp_path / "rounds"),
            "patch": patch,
            "allowed_files": ["train.py"],
            "python": sys.executable,
            "round_id": "round-002",
            "timeout_seconds": 10,
        })

    assert exc_info.value.payload["error_type"] == "unsupported_mle_patch_files"
    assert train_py.read_text(encoding="utf-8") == original_train


def test_run_fasttext_patch_round_tool_executes_client_hyperparam_proposal(tmp_path) -> None:
    train_csv, test_csv = _write_mcp_ag_news_fixture_csvs(tmp_path)
    fake_binary = _write_mcp_fasttext_binary(tmp_path)
    baseline_report = tmp_path / "baseline-report.json"
    output_dir = tmp_path / "fasttext-patch-round"
    baseline_report.write_text(
        json.dumps({
            "commands": {
                "training": ["fasttext", "supervised", "-input", "data/train.txt", "-output", "model"],
            },
            "dataset": {"is_full_expected_size": False},
            "metric": {"p_at_1": 0.75},
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    payload = mcp_service.run_fasttext_patch_round_tool({
        "target_spec": str(
            mcp_service.PROJECT_ROOT / "docs/reproduction-pilot/full-reproduction-target.json"
        ),
        "output_dir": str(output_dir),
        "ag_news_train_csv": str(train_csv),
        "ag_news_test_csv": str(test_csv),
        "fasttext_binary": str(fake_binary),
        "baseline_report": str(baseline_report),
        "proposal": {
            "proposal_id": "mcp-word-ngrams-2",
            "reason": "Codex proposes bigram features after reviewing baseline artifacts",
            "train_args": {"wordNgrams": 2},
        },
        "max_train_seconds": 30,
    })

    assert payload["status"] == "completed"
    assert payload["stage"] == "p3_fasttext_patch_round"
    assert payload["baseline_p_at_1"] == 0.75
    assert payload["p_at_1"] == 0.875
    assert payload["delta"] == 0.125
    assert payload["official_scores_claimed"] is False
    assert Path(payload["improvement_report"]).is_file()
    assert (output_dir / "client-handoff.json").is_file()


def test_write_fasttext_patch_round_proof_bundle_tool_archives_reviewed_artifacts(
    tmp_path,
) -> None:
    train_csv, test_csv = _write_mcp_ag_news_fixture_csvs(tmp_path)
    fake_binary = _write_mcp_fasttext_binary(tmp_path)
    baseline_report = tmp_path / "baseline-report.json"
    patch_dir = tmp_path / "fasttext-patch-round"
    proof_dir = tmp_path / "fasttext-proof"
    baseline_report.write_text(
        json.dumps({
            "commands": {
                "training": [
                    "fasttext",
                    "supervised",
                    "-input",
                    "data/train.txt",
                    "-output",
                    "model",
                ],
            },
            "dataset": {"is_full_expected_size": False},
            "metric": {"p_at_1": 0.75},
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    patch_payload = mcp_service.run_fasttext_patch_round_tool({
        "target_spec": str(
            mcp_service.PROJECT_ROOT / "docs/reproduction-pilot/full-reproduction-target.json"
        ),
        "output_dir": str(patch_dir),
        "ag_news_train_csv": str(train_csv),
        "ag_news_test_csv": str(test_csv),
        "fasttext_binary": str(fake_binary),
        "baseline_report": str(baseline_report),
        "proposal": {
            "proposal_id": "mcp-proof-word-ngrams-2",
            "reason": "Codex proposes bigram features after reviewing baseline artifacts",
            "train_args": {"wordNgrams": 2},
        },
        "max_train_seconds": 30,
    })

    payload = mcp_service.write_fasttext_patch_round_proof_bundle_tool({
        "patch_round_report": patch_payload["improvement_report"],
        "output_dir": str(proof_dir),
        "reviewer": "mcp-p4-reviewer",
    })

    manifest = json.loads((proof_dir / "proof-manifest.json").read_text())
    assert payload["status"] == "completed"
    assert payload["stage"] == "p4_fasttext_patch_proof_bundle"
    assert payload["official_scores_claimed"] is False
    assert manifest["reviewer"] == "mcp-p4-reviewer"
    assert manifest["artifact_sha256"]["human_review_report"]
    assert (proof_dir / "SHA256SUMS").is_file()


def _write_mcp_prepared_mle_fixture(tmp_path: Path) -> Path:
    competition_dir = tmp_path / "mlebench-data" / "spooky-author-identification"
    public = competition_dir / "prepared" / "public"
    public.mkdir(parents=True)
    (public / "train.csv").write_text("id,text,author\n1,hello,EAP\n", encoding="utf-8")
    (public / "test.csv").write_text("id,text\n2,world\n", encoding="utf-8")
    (public / "sample_submission.csv").write_text(
        "id,EAP,HPL,MWS\n2,0.33,0.33,0.34\n",
        encoding="utf-8",
    )
    return competition_dir


def test_get_experiment_logs_returns_recent_log_tail(tmp_path) -> None:
    workspace = tmp_path / "workdir" / "log-task"
    logs_dir = workspace / "logs"
    logs_dir.mkdir(parents=True)
    (logs_dir / "exp-001.log").write_text(
        "\n".join(f"line {index}" for index in range(1, 8)),
        encoding="utf-8",
    )

    payload = mcp_service.get_experiment_logs_tool({
        "task_id": "log-task",
        "workspace": str(workspace),
        "tail_lines": 3,
    })

    assert payload["task_id"] == "log-task"
    assert payload["log_count"] == 1
    assert payload["logs"][0]["file"].endswith("exp-001.log")
    assert payload["logs"][0]["tail"] == "line 5\nline 6\nline 7"


def test_get_experiment_logs_caps_tail_lines(tmp_path) -> None:
    workspace = tmp_path / "workdir" / "log-task"
    logs_dir = workspace / "logs"
    logs_dir.mkdir(parents=True)
    (logs_dir / "exp-001.log").write_text(
        "\n".join(f"line {index}" for index in range(1, 602)),
        encoding="utf-8",
    )

    payload = mcp_service.get_experiment_logs_tool({
        "task_id": "log-task",
        "workspace": str(workspace),
        "tail_lines": 1000,
    })

    assert len(payload["logs"][0]["tail"].splitlines()) == 500
    assert payload["logs"][0]["tail"].splitlines()[0] == "line 102"


def test_run_next_experiment_from_review_can_include_final_review_and_loop_decision(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    task_file = tmp_path / "tasks" / "loop-task.json"
    task_file.parent.mkdir()
    task_file.write_text("{}", encoding="utf-8")
    reviews = [
        {
            "experiment_state": {
                "best_result": {"val": 1.0},
                "code_change_plan": {
                    "next_experiment_plan": {
                        "metric": {"name": "val_bpb", "direction": "minimize"},
                        "proposed_task_patch": {
                            "hyperparameter_space": {
                                "depth": {"type": "choice", "values": [1, 2]},
                            }
                        },
                    }
                },
                "planner_actions": [
                    {
                        "tool": "run_hypothesis_experiment",
                        "arguments": {
                            "task_config": str(task_file),
                            "runtime_root": str(tmp_path),
                        },
                    }
                ],
            }
        },
        {
            "experiment_state": {
                "best_result": {"val": 0.8},
                "code_change_plan": {
                    "next_experiment_plan": {
                        "metric": {"name": "val_bpb", "direction": "minimize"},
                    }
                },
            }
        },
    ]

    def fake_review(arguments: dict) -> dict:
        del arguments
        return reviews.pop(0)

    monkeypatch.setattr(mcp_service, "review_research_results_tool", fake_review)
    monkeypatch.setattr(
        mcp_service,
        "run_hypothesis_experiment_tool",
        lambda arguments: {"status": "completed", "arguments": arguments},
    )

    payload = mcp_service.run_next_experiment_from_review_tool({
        "task_id": "loop-task",
        "runtime_root": str(tmp_path),
        "include_final_review": True,
    })

    assert payload["status"] == "completed"
    assert payload["final_review"]["experiment_state"]["best_result"]["val"] == 0.8
    assert payload["loop_decision"] == {
        "decision": "continue",
        "reason": "best metric improved; continue with the next reviewed patch",
        "reason_category": "metric_improved",
        "recommended_next_action": "continue_with_reviewed_patch",
        "metric": "val_bpb",
        "metric_direction": "minimize",
        "previous_best": 1.0,
        "current_best": 0.8,
        "improved": True,
    }


def test_build_loop_decision_stops_on_final_reproduction_blocker() -> None:
    decision = mcp_service.build_loop_decision(
        initial_review={
            "experiment_state": {
                "best_result": {"val": 1.0},
                "code_change_plan": {
                    "next_experiment_plan": {
                        "metric": {"name": "val_bpb", "direction": "minimize"},
                    }
                },
            }
        },
        final_review={
            "experiment_state": {
                "best_result": {"val": 0.8},
                "loop_policy": {
                    "decision": "stop",
                    "reason_category": "reproduction_blocked",
                    "recommended_next_action": "fix_reproduction_requirements",
                    "reason": "Reproduction required files are missing or invalid.",
                    "stop_reason": "Stop before running more experiments.",
                },
                "code_change_plan": {
                    "next_experiment_plan": {
                        "metric": {"name": "val_bpb", "direction": "minimize"},
                    }
                },
            }
        },
    )

    assert decision["decision"] == "stop"
    assert decision["reason_category"] == "reproduction_blocked"
    assert decision["recommended_next_action"] == "fix_reproduction_requirements"
    assert decision["improved"] is True


def test_run_next_experiment_from_review_reports_execution_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    task_file = tmp_path / "tasks" / "loop-task.json"
    task_file.parent.mkdir()
    task_file.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        mcp_service,
        "review_research_results_tool",
        lambda arguments: {
            "experiment_state": {
                "planner_actions": [
                    {
                        "tool": "run_hypothesis_experiment",
                        "arguments": {
                            "task_config": str(task_file),
                            "runtime_root": str(tmp_path),
                        },
                    }
                ],
                "code_change_plan": {
                    "next_experiment_plan": {
                        "proposed_task_patch": {"budget": {"max_experiments": 1}},
                    }
                },
            }
        },
    )
    monkeypatch.setattr(
        mcp_service,
        "run_hypothesis_experiment_tool",
        lambda arguments: {"status": "completed", "arguments": arguments},
    )

    payload = mcp_service.run_next_experiment_from_review_tool({
        "task_id": "loop-task",
        "runtime_root": str(tmp_path),
        "max_experiments": 1,
        "experiment_duration": 5,
        "python": sys.executable,
    })

    metadata = payload["execution_metadata"]
    assert metadata["wall_time_seconds"] >= 0
    assert metadata["python_executable"] == sys.executable
    assert metadata["timeout_policy"]["experiment_duration_seconds"] == 5
    assert metadata["timeout_policy"]["max_experiments"] == 1
    assert metadata["artifact_retention"]["runtime_root"] == str(tmp_path)


def test_run_client_patch_experiment_validates_patch_and_runs_review_loop(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    runtime_root = tmp_path / "runtime"
    task_file = runtime_root / "tasks" / "client-task.json"
    workspace = runtime_root / "workdir" / "client-task"
    task_file.parent.mkdir(parents=True)
    workspace.mkdir(parents=True)
    task_file.write_text(
        json.dumps({
            "task_id": "client-task",
            "objective": "minimize val_bpb",
            "metric": {"name": "val_bpb", "direction": "minimize"},
            "hyperparameter_space": {},
        }),
        encoding="utf-8",
    )
    (workspace / "train.py").write_text(
        "\n".join([
            "print('before')",
            "# ======= AUTORESEARCH SEARCH REGION START =======",
            "DEPTH = 1",
            "# ======= AUTORESEARCH SEARCH REGION END =======",
        ]),
        encoding="utf-8",
    )
    captured: dict = {}

    def fake_run(arguments: dict) -> dict:
        captured["run_arguments"] = arguments
        return {
            "status": "completed",
            "result": {
                "task_id": "client-task",
                "best_result": {"val": 0.7},
            },
        }

    reviews = [
        {
            "experiment_state": {
                "best_result": {"val": 0.8},
                "code_change_plan": {
                    "next_experiment_plan": {
                        "metric": {"name": "val_bpb", "direction": "minimize"},
                    },
                },
            }
        },
        {
            "experiment_state": {
                "best_result": {"val": 0.6},
                "code_change_plan": {
                    "next_experiment_plan": {
                        "metric": {"name": "val_bpb", "direction": "minimize"},
                    },
                },
            }
        },
    ]

    def fake_review(arguments: dict) -> dict:
        captured["review_arguments"] = arguments
        return reviews.pop(0)

    monkeypatch.setattr(mcp_service, "run_hypothesis_experiment_tool", fake_run)
    monkeypatch.setattr(mcp_service, "review_research_results_tool", fake_review)

    payload = mcp_service.run_client_patch_experiment_tool({
        "task_config": str(task_file),
        "runtime_root": str(runtime_root),
        "workspace": str(workspace),
        "change_proposal": {
            "change_type": "hyperparam",
            "target": "DEPTH",
            "current_value": "1",
            "proposed_value": "2",
            "reason": "validate a slightly deeper model",
            "confidence": 0.8,
        },
        "max_experiments": 1,
        "experiment_duration": 5,
        "include_final_review": True,
    })

    assert payload["status"] == "completed"
    assert payload["patch_execution"]["status"] == "validated"
    assert payload["patch_execution"]["target"] == "DEPTH"
    assert payload["patch_execution"]["task_patch"] == {
        "hyperparameter_space": {"depth": {"type": "choice", "values": [2]}},
        "program_md_overrides": {
            "hints": ["Client proposal DEPTH: 1 -> 2. Reason: validate a slightly deeper model"],
        },
    }
    assert payload["patch_execution"]["diff_preview"]["before"] == "DEPTH = 1"
    assert payload["patch_execution"]["diff_preview"]["after"] == "DEPTH = 2"
    assert captured["run_arguments"]["task_patch"] == payload["patch_execution"]["task_patch"]
    assert captured["run_arguments"]["max_experiments"] == 1
    assert captured["review_arguments"]["task_id"] == "client-task"
    assert payload["initial_review"]["experiment_state"]["best_result"]["val"] == 0.8
    assert payload["final_review"]["experiment_state"]["best_result"]["val"] == 0.6
    assert payload["loop_decision"]["decision"] == "continue"


def test_run_client_patch_experiment_reports_execution_metadata(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    runtime_root = tmp_path / "runtime"
    task_file = runtime_root / "tasks" / "client-task.json"
    workspace = runtime_root / "workdir" / "client-task"
    task_file.parent.mkdir(parents=True)
    workspace.mkdir(parents=True)
    task_file.write_text('{"task_id": "client-task"}', encoding="utf-8")
    (workspace / "train.py").write_text(
        "\n".join([
            "# ======= AUTORESEARCH SEARCH REGION START =======",
            "DEPTH = 1",
            "# ======= AUTORESEARCH SEARCH REGION END =======",
        ]),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        mcp_service,
        "run_hypothesis_experiment_tool",
        lambda arguments: {"status": "completed", "result": {"task_id": "client-task"}},
    )

    payload = mcp_service.run_client_patch_experiment_tool({
        "task_config": str(task_file),
        "runtime_root": str(runtime_root),
        "workspace": str(workspace),
        "python": sys.executable,
        "change_proposal": {
            "change_type": "hyperparam",
            "target": "DEPTH",
            "current_value": "1",
            "proposed_value": "2",
            "reason": "validate a slightly deeper model",
        },
        "max_experiments": 1,
        "experiment_duration": 5,
    })

    metadata = payload["execution_metadata"]
    assert metadata["python_executable"] == sys.executable
    assert metadata["timeout_policy"]["experiment_duration_seconds"] == 5
    assert metadata["artifact_retention"]["runtime_root"] == str(runtime_root)
    assert metadata["artifact_retention"]["workspace"] == str(workspace)


def test_run_client_patch_experiment_rejects_stale_current_value(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    task_file = runtime_root / "tasks" / "client-task.json"
    workspace = runtime_root / "workdir" / "client-task"
    task_file.parent.mkdir(parents=True)
    workspace.mkdir(parents=True)
    task_file.write_text('{"task_id": "client-task"}', encoding="utf-8")
    (workspace / "train.py").write_text(
        "\n".join([
            "# ======= AUTORESEARCH SEARCH REGION START =======",
            "DEPTH = 1",
            "# ======= AUTORESEARCH SEARCH REGION END =======",
        ]),
        encoding="utf-8",
    )

    with pytest.raises(mcp_service.MCPToolError) as exc_info:
        mcp_service.run_client_patch_experiment_tool({
            "task_config": str(task_file),
            "runtime_root": str(runtime_root),
            "workspace": str(workspace),
            "change_proposal": {
                "change_type": "hyperparam",
                "target": "DEPTH",
                "current_value": "4",
                "proposed_value": "2",
                "reason": "stale client state",
            },
        })

    assert exc_info.value.payload["status"] == "failed"
    assert exc_info.value.payload["error_type"] == "stale_patch"
    assert exc_info.value.payload["actual_value"] == "1"


def test_run_client_patch_experiment_rejects_unknown_search_region_target(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    task_file = runtime_root / "tasks" / "client-task.json"
    workspace = runtime_root / "workdir" / "client-task"
    task_file.parent.mkdir(parents=True)
    workspace.mkdir(parents=True)
    task_file.write_text('{"task_id": "client-task"}', encoding="utf-8")
    (workspace / "train.py").write_text(
        "\n".join([
            "# ======= AUTORESEARCH SEARCH REGION START =======",
            "DEPTH = 1",
            "# ======= AUTORESEARCH SEARCH REGION END =======",
        ]),
        encoding="utf-8",
    )

    with pytest.raises(mcp_service.MCPToolError) as exc_info:
        mcp_service.run_client_patch_experiment_tool({
            "task_config": str(task_file),
            "runtime_root": str(runtime_root),
            "workspace": str(workspace),
            "change_proposal": {
                "change_type": "hyperparam",
                "target": "DROPOUT",
                "current_value": "0.1",
                "proposed_value": "0.2",
                "reason": "not in current SEARCH REGION",
            },
        })

    assert exc_info.value.payload["status"] == "failed"
    assert exc_info.value.payload["error_type"] == "invalid_patch_target"
    assert exc_info.value.payload["available_targets"] == ["DEPTH"]


def test_run_client_patch_experiment_rejects_invalid_confidence(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    task_file = runtime_root / "tasks" / "client-task.json"
    workspace = runtime_root / "workdir" / "client-task"
    task_file.parent.mkdir(parents=True)
    workspace.mkdir(parents=True)
    task_file.write_text('{"task_id": "client-task"}', encoding="utf-8")
    (workspace / "train.py").write_text(
        "\n".join([
            "# ======= AUTORESEARCH SEARCH REGION START =======",
            "DEPTH = 1",
            "# ======= AUTORESEARCH SEARCH REGION END =======",
        ]),
        encoding="utf-8",
    )

    with pytest.raises(mcp_service.MCPToolError) as exc_info:
        mcp_service.run_client_patch_experiment_tool({
            "task_config": str(task_file),
            "runtime_root": str(runtime_root),
            "workspace": str(workspace),
            "change_proposal": {
                "change_type": "hyperparam",
                "target": "DEPTH",
                "current_value": "1",
                "proposed_value": "2",
                "reason": "bad confidence",
                "confidence": "high",
            },
        })

    assert exc_info.value.payload["status"] == "failed"
    assert exc_info.value.payload["error_type"] == "invalid_patch_confidence"


def test_apply_client_code_patch_applies_workspace_patch_and_checks_syntax(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = runtime_root / "workdir" / "patch-task"
    workspace.mkdir(parents=True)
    train_py = workspace / "train.py"
    train_py.write_text("VALUE = 1\nprint(VALUE)\n", encoding="utf-8")

    payload = mcp_service.apply_client_code_patch_tool({
        "runtime_root": str(runtime_root),
        "workspace": str(workspace),
        "patch": "\n".join([
            "--- a/train.py",
            "+++ b/train.py",
            "@@ -1,2 +1,2 @@",
            "-VALUE = 1",
            "+VALUE = 2",
            " print(VALUE)",
            "",
        ]),
        "test_command": [sys.executable, "-m", "py_compile", "train.py"],
    })

    assert payload["status"] == "applied"
    assert payload["patch_execution"]["mode"] == "workspace_unified_diff"
    assert payload["patch_execution"]["changed_files"] == ["train.py"]
    assert payload["patch_execution"]["preflight"]["status"] == "passed"
    assert payload["patch_execution"]["syntax_check"]["status"] == "passed"
    assert payload["patch_execution"]["test_check"]["status"] == "passed"
    assert payload["patch_execution"]["rollback"]["performed"] is False
    assert train_py.read_text(encoding="utf-8") == "VALUE = 2\nprint(VALUE)\n"


def test_apply_client_code_patch_handles_multi_file_patch_and_post_review(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = runtime_root / "workdir" / "patch-task"
    workspace.mkdir(parents=True)
    train_py = workspace / "train.py"
    helper_py = workspace / "helper.py"
    train_py.write_text(
        "from helper import scale\nVALUE = scale(1)\nprint(VALUE)\n",
        encoding="utf-8",
    )
    helper_py.write_text("def scale(value):\n    return value\n", encoding="utf-8")
    captured: dict = {}

    def fake_review(arguments: dict) -> dict:
        captured["review_arguments"] = arguments
        return {
            "status": "completed",
            "experiment_state": {
                "best_result": {"val": 0.5},
                "code_change_plan": {
                    "next_experiment_plan": {
                        "metric": {"name": "val_bpb", "direction": "minimize"},
                    }
                },
            },
        }

    monkeypatch.setattr(mcp_service, "review_research_results_tool", fake_review)

    payload = mcp_service.apply_client_code_patch_tool({
        "runtime_root": str(runtime_root),
        "workspace": str(workspace),
        "task_id": "patch-task",
        "patch": "\n".join([
            "--- a/train.py",
            "+++ b/train.py",
            "@@ -1,3 +1,3 @@",
            " from helper import scale",
            "-VALUE = scale(1)",
            "+VALUE = scale(2)",
            " print(VALUE)",
            "--- a/helper.py",
            "+++ b/helper.py",
            "@@ -1,2 +1,2 @@",
            " def scale(value):",
            "-    return value",
            "+    return value * 2",
            "",
        ]),
        "allowed_files": ["train.py", "helper.py"],
        "test_command": [sys.executable, "-m", "py_compile", "train.py", "helper.py"],
        "include_post_patch_review": True,
        "initial_review": {
            "experiment_state": {
                "best_result": {"val": 1.0},
                "code_change_plan": {
                    "next_experiment_plan": {
                        "metric": {"name": "val_bpb", "direction": "minimize"},
                    }
                },
            }
        },
    })

    assert payload["status"] == "applied"
    assert payload["patch_execution"]["changed_files"] == ["helper.py", "train.py"]
    assert payload["patch_execution"]["syntax_check"]["checked_files"] == ["helper.py", "train.py"]
    assert payload["patch_execution"]["test_check"]["status"] == "passed"
    assert payload["post_patch_review"]["status"] == "completed"
    assert payload["loop_decision"]["decision"] == "continue"
    assert payload["loop_decision"]["reason_category"] == "metric_improved"
    assert captured["review_arguments"] == {
        "task_id": "patch-task",
        "runtime_root": str(runtime_root),
        "workspace": str(workspace),
    }
    assert train_py.read_text(encoding="utf-8") == "from helper import scale\nVALUE = scale(2)\nprint(VALUE)\n"
    assert helper_py.read_text(encoding="utf-8") == "def scale(value):\n    return value * 2\n"


def test_apply_client_code_patch_reports_execution_metadata(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = runtime_root / "workdir" / "patch-task"
    workspace.mkdir(parents=True)
    train_py = workspace / "train.py"
    train_py.write_text("VALUE = 1\nprint(VALUE)\n", encoding="utf-8")

    payload = mcp_service.apply_client_code_patch_tool({
        "runtime_root": str(runtime_root),
        "workspace": str(workspace),
        "patch": "\n".join([
            "--- a/train.py",
            "+++ b/train.py",
            "@@ -1,2 +1,2 @@",
            "-VALUE = 1",
            "+VALUE = 2",
            " print(VALUE)",
            "",
        ]),
        "test_command": [sys.executable, "-m", "py_compile", "train.py"],
        "test_timeout_seconds": 12,
    })

    metadata = payload["execution_metadata"]
    assert metadata["wall_time_seconds"] >= 0
    assert metadata["timeout_policy"]["test_timeout_seconds"] == 12
    assert metadata["artifact_retention"]["runtime_root"] == str(runtime_root)
    assert metadata["artifact_retention"]["workspace"] == str(workspace)


def test_apply_client_code_patch_rolls_back_on_syntax_error(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = runtime_root / "workdir" / "patch-task"
    workspace.mkdir(parents=True)
    train_py = workspace / "train.py"
    original_text = "VALUE = 1\nprint(VALUE)\n"
    train_py.write_text(original_text, encoding="utf-8")

    with pytest.raises(mcp_service.MCPToolError) as exc_info:
        mcp_service.apply_client_code_patch_tool({
            "runtime_root": str(runtime_root),
            "workspace": str(workspace),
            "patch": "\n".join([
                "--- a/train.py",
                "+++ b/train.py",
                "@@ -1,2 +1,2 @@",
                "-VALUE = 1",
                "+VALUE =",
                " print(VALUE)",
                "",
            ]),
        })

    assert exc_info.value.payload["status"] == "failed"
    assert exc_info.value.payload["error_type"] == "syntax_check_failed"
    assert exc_info.value.payload["patch_execution"]["rollback"]["performed"] is True
    assert train_py.read_text(encoding="utf-8") == original_text


def test_apply_client_code_patch_rolls_back_on_test_command_failure(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = runtime_root / "workdir" / "patch-task"
    workspace.mkdir(parents=True)
    train_py = workspace / "train.py"
    original_text = "VALUE = 1\nprint(VALUE)\n"
    train_py.write_text(original_text, encoding="utf-8")

    with pytest.raises(mcp_service.MCPToolError) as exc_info:
        mcp_service.apply_client_code_patch_tool({
            "runtime_root": str(runtime_root),
            "workspace": str(workspace),
            "patch": "\n".join([
                "--- a/train.py",
                "+++ b/train.py",
                "@@ -1,2 +1,2 @@",
                "-VALUE = 1",
                "+VALUE = 2",
                " print(VALUE)",
                "",
            ]),
            "test_command": [sys.executable, "-c", "raise SystemExit(7)"],
        })

    assert exc_info.value.payload["status"] == "failed"
    assert exc_info.value.payload["error_type"] == "test_check_failed"
    assert exc_info.value.payload["patch_execution"]["test_check"]["returncode"] == 7
    assert exc_info.value.payload["patch_execution"]["rollback"]["performed"] is True
    assert train_py.read_text(encoding="utf-8") == original_text


def test_apply_client_code_patch_rejects_path_escape(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    workspace = runtime_root / "workdir" / "patch-task"
    workspace.mkdir(parents=True)

    with pytest.raises(mcp_service.MCPToolError) as exc_info:
        mcp_service.apply_client_code_patch_tool({
            "runtime_root": str(runtime_root),
            "workspace": str(workspace),
            "patch": "\n".join([
                "--- a/../outside.py",
                "+++ b/../outside.py",
                "@@ -1 +1 @@",
                "-VALUE = 1",
                "+VALUE = 2",
                "",
            ]),
        })

    assert exc_info.value.payload["status"] == "failed"
    assert exc_info.value.payload["error_type"] == "unsafe_patch_path"
    assert exc_info.value.payload["patch_execution"]["rollback"]["performed"] is False


def test_runtime_artifact_tools_list_archive_and_clean_task_artifacts(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    runtime_root = tmp_path / "runtime"
    monkeypatch.setenv("ML_RESEARCH_LOOP_ALLOWED_ROOTS", str(runtime_root))
    task_file = runtime_root / "tasks" / "demo.json"
    result_file = runtime_root / "results" / "demo.json"
    progress_file = runtime_root / "results" / "demo-progress.json"
    workspace = runtime_root / "workdir" / "demo"
    task_file.parent.mkdir(parents=True)
    result_file.parent.mkdir(parents=True)
    workspace.mkdir(parents=True)
    task_file.write_text("{}", encoding="utf-8")
    result_file.write_text("{}", encoding="utf-8")
    progress_file.write_text("{}", encoding="utf-8")
    (workspace / "train.py").write_text("print('demo')\n", encoding="utf-8")

    listed = mcp_service.list_runtime_artifacts_tool({"runtime_root": str(runtime_root)})

    assert listed["task_ids"] == ["demo"]
    assert listed["artifacts"]["tasks"]["file_count"] == 1
    assert listed["artifacts"]["results"]["file_count"] == 2
    assert listed["artifacts"]["workdir"]["file_count"] == 1

    archived = mcp_service.archive_runtime_artifacts_tool({
        "runtime_root": str(runtime_root),
        "task_id": "demo",
    })

    assert archived["status"] == "archived"
    assert archived["task_id"] == "demo"
    assert archived["archived_count"] == 3
    assert not task_file.exists()
    assert not result_file.exists()
    assert not workspace.exists()
    assert (runtime_root / "archive").exists()

    new_task_file = runtime_root / "tasks" / "demo.json"
    new_task_file.parent.mkdir(parents=True, exist_ok=True)
    new_task_file.write_text("{}", encoding="utf-8")
    cleaned = mcp_service.clean_runtime_artifacts_tool({
        "runtime_root": str(runtime_root),
        "task_id": "demo",
        "confirm": True,
    })

    assert cleaned["status"] == "cleaned"
    assert cleaned["deleted_count"] == 1
    assert not new_task_file.exists()


def test_clean_runtime_artifacts_requires_confirm(tmp_path) -> None:
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()

    with pytest.raises(mcp_service.MCPToolError) as exc_info:
        mcp_service.clean_runtime_artifacts_tool({
            "runtime_root": str(runtime_root),
            "task_id": "demo",
        })

    assert exc_info.value.payload["status"] == "failed"
    assert "confirm" in exc_info.value.payload["error"]
