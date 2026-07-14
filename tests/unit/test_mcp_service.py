from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, SimpleHTTPRequestHandler, ThreadingHTTPServer
import os
import subprocess
import sys
import threading
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


class _QuietSimpleHTTPRequestHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):  # noqa: A002
        return


def _serve_directory(directory: Path) -> tuple[ThreadingHTTPServer, threading.Thread]:
    def handler(*args, **kwargs):
        return _QuietSimpleHTTPRequestHandler(
            *args,
            directory=str(directory),
            **kwargs,
        )

    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def _serve_submission_endpoint(
    response_payload: dict,
) -> tuple[ThreadingHTTPServer, threading.Thread, list[dict]]:
    received: list[dict] = []

    class _SubmissionHandler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            received.append(json.loads(body.decode("utf-8")))
            encoded = json.dumps(response_payload).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)

        def log_message(self, format, *args):  # noqa: A002
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), _SubmissionHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread, received


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

    unsupported_top_level_schema_keys = {"allOf", "anyOf", "enum", "not", "oneOf"}
    for tool in response["result"]["tools"]:
        input_schema = tool["inputSchema"]
        assert input_schema["type"] == "object"
        assert unsupported_top_level_schema_keys.isdisjoint(input_schema)

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
        "extract_failure_records",
        "record_proposal_outcome",
        "build_proposal_pattern_memory",
        "retrieve_proposal_patterns",
        "build_fasttext_proposal_effectiveness_bundle",
        "build_smol_worldcup_proposal_effectiveness_bundle",
        "build_real_paper_proposal_effectiveness_bundle",
        "build_cross_task_proposal_effectiveness_summary",
        "build_proposal_effectiveness_claim_audit",
        "build_mixed_signal_proposal_effectiveness_audit",
        "build_smol_worldcup_promotion_gate",
        "build_smol_worldcup_canary_control_arm_handoff",
        "build_smol_worldcup_canary_control_arm_execution_bundle",
        "build_smol_worldcup_promotion_gate_refresh",
        "build_prompt_module_spec",
        "build_paired_repeat_manifest",
        "probe_optimizer_runtime",
        "build_optimizer_package_runtime_benefit_audit",
        "build_method_proposal_generation_trace",
        "build_multi_optimizer_candidate_race",
        "run_real_benchmark_readiness_run",
        "build_prompt_profile_registration_plan",
        "register_prompt_profile_from_plan",
        "build_model_runtime_preflight",
        "build_failure_driven_proposal_context",
        "generate_failure_driven_proposals",
        "rank_failure_driven_proposals",
        "build_failure_driven_proposal_handoff",
        "build_failure_driven_client_proposal_templates",
        "bridge_failure_driven_outcome_to_memory_card",
        "evaluate_failure_driven_proposal_effectiveness",
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
        "method_search",
        "optuna_export",
        "gate_policy",
        "registered_profile",
        "slice_patch",
        "cp_bench",
        "optimizer_gate",
    }.issubset(tool_names)
    research_case_tool = next(
        tool for tool in response["result"]["tools"]
        if tool["name"] == "plan_research_case"
    )
    optimizer_gate_tool = next(
        tool for tool in response["result"]["tools"]
        if tool["name"] == "optimizer_gate"
    )
    scheduler_loop_tool = optimizer_gate_tool
    smol_model_eval_tool = next(
        tool for tool in response["result"]["tools"]
        if tool["name"] == "run_smol_worldcup_model_eval"
    )
    smol_leakage_audit_tool = next(
        tool for tool in response["result"]["tools"]
        if tool["name"] == "write_smol_worldcup_prompt_leakage_audit"
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
    assert scheduler_loop_tool["inputSchema"]["properties"][
        "auto_refresh_scheduler_plan"
    ] == {"type": "boolean", "default": False}
    # optimizer_gate consolidates 20 former standalone tools into one
    # stage-dispatched tool (see lib/mcp_service.py's optimizer_gate_tool
    # dispatcher). The schema's own `required` is only ["stage"] -- each
    # stage's specific required fields are enforced by the underlying
    # handler function at call time, not by the JSON schema (oneOf/
    # if-then-else conditionals are disallowed at the schema top level,
    # see unsupported_top_level_schema_keys above). So this test checks
    # stage coverage and property presence rather than per-stage
    # required-field sets.
    assert set(optimizer_gate_tool["inputSchema"]["required"]) == {"stage"}
    optimizer_gate_stages = set(
        optimizer_gate_tool["inputSchema"]["properties"]["stage"]["enum"]
    )
    assert optimizer_gate_stages == {
        "build_canary_runner_bundle",
        "build_execution_plan",
        "build_execution_preflight",
        "build_human_promotion_approval",
        "build_official_claim",
        "build_official_submission",
        "build_promotion_review_queue",
        "build_run",
        "build_scheduler_handoff",
        "build_scheduler_plan",
        "build_system_spec",
        "fetch_public_result",
        "run_canary_runner_bundle",
        "run_executable_loop",
        "run_external_submission_action",
        "run_local_promotion_action",
        "run_local_promotion_rollback",
        "run_scheduler_action",
        "run_scheduler_loop",
        "verify_public_result",
    }
    optimizer_gate_props = optimizer_gate_tool["inputSchema"]["properties"]
    assert optimizer_gate_props["auto_refresh_scheduler_plan"] == {
        "type": "boolean",
        "default": False,
    }
    for expected_property in (
        "optimizer_gate_scheduler_loop",
        "optimizer_gate_scheduler_loop_file",
        "optimizer_gate_scheduler_handoff",
        "registered_profile_execution_run_file",
        "optimizer_gate_canary_runner_bundle",
        "optimizer_gate_canary_runner_bundle_file",
        "canary_result_gate_file",
        "approved",
        "approved_by",
        "promotion_review_queue",
        "promotion_review_queue_file",
        "human_promotion_approval",
        "human_promotion_approval_file",
        "profile_registry_file",
        "registry_output_path",
        "rollback_output_path",
        "audit_log_path",
        "benchmark_id",
        "submission_id",
        "public_url",
        "submitted_by",
        "submission_url",
        "local_promotion_action",
        "local_promotion_action_file",
        "submission_payload",
        "submission_payload_file",
        "public_result_url",
        "claim_id",
        "slice_repair_context",
        "canary_result_gate",
        "output_path",
        "output_dir",
    ):
        assert expected_property in optimizer_gate_props, expected_property
    assert "p3-semantic-v1" in (
        smol_model_eval_tool["inputSchema"]["properties"]["prompt_profile"]["enum"]
    )
    assert "p3-semantic-v2" in (
        smol_model_eval_tool["inputSchema"]["properties"]["prompt_profile"]["enum"]
    )
    assert "p3-canary-repair-v7" in (
        smol_model_eval_tool["inputSchema"]["properties"]["prompt_profile"]["enum"]
    )
    assert "p3-slice-metacognition-textgrad-v1" in (
        smol_model_eval_tool["inputSchema"]["properties"]["prompt_profile"]["enum"]
    )
    assert "p3-v7-metacognition-textgrad-v2" in (
        smol_model_eval_tool["inputSchema"]["properties"]["prompt_profile"]["enum"]
    )
    assert "p3-v7-metacognition-textgrad-pw-ar-v3" in (
        smol_model_eval_tool["inputSchema"]["properties"]["prompt_profile"]["enum"]
    )
    assert "p3-canary-repair-v1" in (
        smol_model_eval_tool["inputSchema"]["properties"]["prompt_profile"]["enum"]
    )
    assert smol_model_eval_tool["inputSchema"]["properties"]["dataset_offset"]["default"] == 0
    assert "prompt_profile_registration" in (
        smol_model_eval_tool["inputSchema"]["properties"]
    )
    assert "prompt_profile_registration_file" in (
        smol_model_eval_tool["inputSchema"]["properties"]
    )
    assert "prompt_profile_registration" in (
        smol_leakage_audit_tool["inputSchema"]["properties"]
    )
    assert "prompt_profile_registration_file" in (
        smol_leakage_audit_tool["inputSchema"]["properties"]
    )
    assert set(smol_proposal_round_tool["inputSchema"]["required"]) == {"output_dir"}
    assert "proposal" in smol_proposal_round_tool["inputSchema"]["properties"]
    assert "proposal_file" in smol_proposal_round_tool["inputSchema"]["properties"]
    assert "p3-dev-v2" in (
        smol_proposal_round_tool["inputSchema"]["properties"]["prompt_profile"]["enum"]
    )
    assert "p3-canary-repair-v1" in (
        smol_proposal_round_tool["inputSchema"]["properties"]["prompt_profile"]["enum"]
    )
    assert "p3-canary-repair-v7" in (
        smol_proposal_round_tool["inputSchema"]["properties"]["prompt_profile"]["enum"]
    )
    assert "p3-slice-metacognition-textgrad-v1" in (
        smol_proposal_round_tool["inputSchema"]["properties"]["prompt_profile"]["enum"]
    )
    assert "p3-v7-metacognition-textgrad-v2" in (
        smol_proposal_round_tool["inputSchema"]["properties"]["prompt_profile"]["enum"]
    )
    assert "p3-v7-metacognition-textgrad-pw-ar-v3" in (
        smol_proposal_round_tool["inputSchema"]["properties"]["prompt_profile"]["enum"]
    )
    assert smol_proposal_round_tool["inputSchema"]["properties"]["dataset_offset"]["default"] == 0
    assert "proposal" in proposal_reflection_tool["inputSchema"]["properties"]
    assert "proposal_file" in proposal_reflection_tool["inputSchema"]["properties"]
    assert "evaluation" in proposal_reflection_tool["inputSchema"]["properties"]
    assert "evaluation_file" in proposal_reflection_tool["inputSchema"]["properties"]
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

    assert payload["contract_version"] == "2026-07-10.preview.v1"
    assert payload["schema_versions"] == {
        "service_manifest": "2026-07-10.preview.v1",
        "tool_inputs": "2026-07-10.preview.v1",
        "tool_outputs": "2026-07-10.preview.v1",
        "runtime_artifacts": "2026-07-10.preview.v1",
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
        == "arguard-b1-binary-classification"
    )
    assert payload["cp_bench_live_verification"]["official_scores_claimed"] is False
    assert payload["cp_bench_live_verification"]["tool"] == "cp_bench"
    assert payload["cp_bench_live_verification"]["tool_stage"] == "write_live_verification"
    assert payload["cp_bench_local_baseline"]["official_scores_claimed"] is False
    assert payload["cp_bench_local_baseline"]["tool"] == "cp_bench"
    assert payload["cp_bench_local_baseline"]["tool_stage"] == "run_local_baseline"
    assert payload["cp_bench_proposal_round"]["official_scores_claimed"] is False
    assert payload["cp_bench_proposal_round"]["tool"] == "cp_bench"
    assert payload["cp_bench_proposal_round"]["tool_stage"] == "run_proposal_round"
    assert payload["cp_bench_candidate_round"]["official_scores_claimed"] is False
    assert payload["cp_bench_candidate_round"]["tool"] == "cp_bench"
    assert payload["cp_bench_candidate_round"]["tool_stage"] == "run_candidate_round"
    assert payload["cp_bench_proposal_context"]["official_scores_claimed"] is False
    assert payload["cp_bench_proposal_context"]["tool"] == "cp_bench"
    assert payload["cp_bench_proposal_context"]["tool_stage"] == "build_proposal_context"
    assert payload["cp_bench_client_candidate"]["official_scores_claimed"] is False
    assert payload["cp_bench_client_candidate"]["tool"] == "cp_bench"
    assert payload["cp_bench_client_candidate"]["tool_stage"] == (
        "write_client_candidate_submission"
    )
    assert payload["cp_bench_submission_gate"]["official_scores_claimed"] is False
    assert payload["cp_bench_submission_gate"]["tool"] == "cp_bench"
    assert payload["cp_bench_submission_gate"]["tool_stage"] == "write_submission_gate"
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
    assert "cp_bench" in payload["required_tools"]
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
    assert planner_contract["contract_version"] == "2026-07-10.preview.v1"
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
        assert contract["input_schema_version"] == "2026-07-10.preview.v1"
        assert contract["output_schema_version"] == "2026-07-10.preview.v1"
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


def test_extract_failure_records_tool_writes_jsonl(tmp_path: Path) -> None:
    reflection = tmp_path / "proposal-reflection.json"
    reflection.write_text(
        json.dumps(
            {
                "proposal_id": "round-001",
                "status": "needs_rollback_or_more_evidence",
                "proposal": {
                    "proposal_id": "round-001",
                    "change_surface": "routing",
                    "hypothesis": "A bounded routing change should survive canary.",
                },
                "failure_labels": ["canary_not_confirmed"],
                "evaluation": {"canary_delta": {"SHIFT": -0.2}},
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    payload = mcp_service.extract_failure_records_tool(
        {
            "source_artifact": str(reflection),
            "output_path": str(tmp_path / "failure-records.jsonl"),
        }
    )

    assert payload["status"] == "completed"
    assert payload["record_count"] == 1
    assert payload["records"][0]["failure_type"] == "canary_not_confirmed"
    assert Path(payload["output_path"]).exists()


def test_record_proposal_outcome_tool_writes_artifact(tmp_path: Path) -> None:
    payload = mcp_service.record_proposal_outcome_tool(
        {
            "proposal": {
                "proposal_id": "round-002",
                "proposal_type": "failure_fix",
                "based_on_failures": ["canary_not_confirmed"],
                "intent": "Preserve dev gain on canary.",
                "change_surface": "routing",
                "target_scope": "single routing block",
                "verification_plan": {"first_split": "dev", "promotion_split": "canary"},
                "rollback_rule": {"if": ["canary_delta_lt_0"]},
                "claim_boundary": "local proposal only",
                "official_scores_claimed": False,
            },
            "evaluation": {
                "dev_delta": {"SHIFT": 0.7},
                "canary_delta": {"SHIFT": 0.1},
            },
            "output_path": str(tmp_path / "proposal-outcome.json"),
        }
    )

    assert payload["status"] == "completed"
    assert payload["accepted"] is True
    assert payload["metric_delta"]["dev"] == 0.7
    assert Path(payload["output_path"]).exists()


def test_build_proposal_pattern_memory_tool_aggregates_outcomes(tmp_path: Path) -> None:
    outcomes = tmp_path / "proposal-outcomes.jsonl"
    outcomes.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema_version": "2026-06-02.proposal-outcome.v1",
                        "outcome_id": "o1",
                        "proposal_id": "p1",
                        "proposal_type": "failure_fix",
                        "based_on_failures": ["canary_not_confirmed"],
                        "executed": True,
                        "accepted": True,
                        "metric_delta": {"dev": 0.5, "canary": 0.1},
                        "rollback_triggered": False,
                        "claim_boundary": "local outcome only",
                        "official_scores_claimed": False,
                    }
                ),
                json.dumps(
                    {
                        "schema_version": "2026-06-02.proposal-outcome.v1",
                        "outcome_id": "o2",
                        "proposal_id": "p2",
                        "proposal_type": "failure_fix",
                        "based_on_failures": ["canary_not_confirmed"],
                        "executed": True,
                        "accepted": False,
                        "metric_delta": {"dev": 0.1, "canary": -0.3},
                        "rollback_triggered": True,
                        "failure_labels": ["canary_not_confirmed"],
                        "claim_boundary": "local outcome only",
                        "official_scores_claimed": False,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = mcp_service.build_proposal_pattern_memory_tool(
        {
            "outcomes_file": str(outcomes),
            "output_path": str(tmp_path / "proposal-pattern-memory.jsonl"),
        }
    )

    assert payload["status"] == "completed"
    assert payload["pattern_count"] == 1
    assert payload["patterns"][0]["historical_success_rate"] == 0.5
    assert Path(payload["output_path"]).exists()


def test_build_failure_driven_proposal_context_tool(tmp_path: Path) -> None:
    failures = tmp_path / "failure-records.jsonl"
    patterns = tmp_path / "proposal-pattern-memory.jsonl"
    failures.write_text(
        json.dumps(
            {
                "schema_version": "2026-06-02.failure-record.v1",
                "failure_id": "f1",
                "task_id": "round-001",
                "failure_type": "canary_not_confirmed",
                "symptom": "canary regressed",
                "severity": "medium",
                "claim_boundary": "local only",
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    patterns.write_text(
        json.dumps(
            {
                "schema_version": "2026-06-02.proposal-pattern-memory.v1",
                "pattern_id": "failure_fix::canary_not_confirmed",
                "pattern_summary": "failure_fix against canary_not_confirmed",
                "proposal_type": "failure_fix",
                "applicable_when": ["canary_not_confirmed"],
                "historical_success_rate": 0.8,
                "historical_failure_rate": 0.2,
                "claim_boundary": "local only",
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    payload = mcp_service.build_failure_driven_proposal_context_tool(
        {
            "objective": "Preserve canary gain",
            "failure_records_file": str(failures),
            "pattern_memory_file": str(patterns),
            "output_path": str(tmp_path / "failure-context.json"),
        }
    )

    assert payload["status"] == "ready_for_failure_driven_proposals"
    assert payload["failure_summary"]["record_count"] == 1
    assert Path(payload["output_path"]).exists()


def test_build_slice_eval_matrix_tool_writes_non_executing_artifact(
    tmp_path: Path,
) -> None:
    baseline = tmp_path / "baseline.json"
    candidate = tmp_path / "candidate.json"
    output = tmp_path / "slice-matrix.json"
    baseline.write_text(
        json.dumps(
            {
                "metrics": {"SHIFT": 80.0},
                "dataset": {"evaluation_split": "dev"},
                "score_breakdown": {
                    "by_category": {
                        "multilingual_pt": {"row_count": 3, "score_percent": 53.0}
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    candidate.write_text(
        json.dumps(
            {
                "metrics": {"SHIFT": 70.0},
                "dataset": {"evaluation_split": "dev"},
                "score_breakdown": {
                    "by_category": {
                        "multilingual_pt": {"row_count": 3, "score_percent": 23.0}
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    payload = mcp_service.build_slice_eval_matrix_tool(
        {
            "baseline_report_file": str(baseline),
            "candidate_report_file": str(candidate),
            "output_path": str(output),
        }
    )

    assert payload["status"] == "completed"
    assert payload["executes_tool"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_evaluate_slice_variance_gate_tool_writes_non_executing_artifact(
    tmp_path: Path,
) -> None:
    matrix = tmp_path / "slice-matrix.json"
    output = tmp_path / "slice-variance-gate.json"
    matrix.write_text(
        json.dumps(
            {
                "schema_version": "2026-06-04.slice-eval-matrix.v1",
                "split": "dev",
                "metric_delta": {"SHIFT": 0.1},
                "slices": [
                    {
                        "slice_key": "dev/category/multilingual_bn",
                        "slice_name": "multilingual_bn",
                        "delta": -10.0,
                        "gate": "blocked",
                    }
                ],
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    payload = mcp_service.evaluate_slice_variance_gate_tool(
        {
            "slice_matrix_files": [str(matrix)],
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == "2026-06-05.slice-variance-gate-decision.v1"
    assert payload["status"] == "needs_paired_repeat"
    assert payload["executes_tool"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_paired_repeat_manifest_tools_feed_variance_gate(tmp_path: Path) -> None:
    manifest_output = tmp_path / "paired-repeat-manifest.json"
    decision_output = tmp_path / "slice-variance-gate.json"
    first = {
        "schema_version": "2026-06-04.slice-eval-matrix.v1",
        "task_family": "generic_fixture",
        "baseline_ref": "baseline-profile-a",
        "candidate_ref": "candidate-profile-b",
        "split": "dev",
        "metric_delta": {"SHIFT": 0.1},
        "slices": [
            {
                "slice_key": "dev/category/multilingual_bn",
                "slice_name": "multilingual_bn",
                "delta": -10.0,
                "gate": "blocked",
            }
        ],
        "official_scores_claimed": False,
    }
    second = dict(first)
    second["metric_delta"] = {"SHIFT": 0.2}
    second["slices"] = [
        {
            "slice_key": "dev/category/multilingual_bn",
            "slice_name": "multilingual_bn",
            "delta": -8.0,
            "gate": "blocked",
        }
    ]

    manifest = mcp_service.build_paired_repeat_manifest_tool(
        {
            "slice_matrices": [first, second],
            "task_family": "generic_fixture",
            "output_path": str(manifest_output),
        }
    )

    assert manifest["schema_version"] == "2026-06-05.paired-repeat-manifest.v1"
    assert manifest["repeat_count"] == 2
    assert manifest["executes_experiment"] is False
    assert manifest_output.exists()

    decision = mcp_service.evaluate_slice_variance_gate_tool(
        {
            "paired_repeat_manifest_file": str(manifest_output),
            "output_path": str(decision_output),
        }
    )

    assert decision["status"] == "blocked"
    assert decision["paired_repeat_manifest_ref"] == str(manifest_output)
    assert "stable_slice_regression" in decision["hard_blockers"]
    assert decision["official_scores_claimed"] is False
    assert decision_output.exists()


def test_build_prompt_module_spec_tool_writes_non_executing_artifact(
    tmp_path: Path,
) -> None:
    output = tmp_path / "prompt-modules.json"

    payload = mcp_service.build_prompt_module_spec_tool(
        {
            "profile_id": "p3-dev-v2",
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == "2026-06-04.prompt-module-spec.v1"
    assert payload["profile_id"] == "p3-dev-v2"
    assert payload["executes_tool"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_generate_slice_patch_candidates_tool_executes_textgrad_qwen_adapter(
    monkeypatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "slice-patches.json"
    calls: list[dict] = []

    def fake_chat(**kwargs):
        calls.append(kwargs)
        return {
            "content": json.dumps(
                {
                    "critic_feedback": "Use a section-local multilingual cue.",
                    "after_text": "return concise JSON with protected locale constraints",
                }
            ),
            "raw_response": {"id": "chatcmpl-mcp"},
        }

    monkeypatch.setattr(
        "lib.failure_driven_proposal._call_openai_compatible_chat",
        fake_chat,
    )

    payload = mcp_service.generate_slice_patch_candidates_tool(
        {
            "context": {
                "recommended_patch_contract": {
                    "module_id": "multilingual_variant_explanation",
                    "section_id": "output_format",
                    "based_on_slices": ["dev/category/multilingual_pt"],
                    "target_slice": "multilingual_pt",
                    "before_text": "return concise JSON",
                    "protected_slices": ["multilingual_th"],
                    "protected_sections": ["role"],
                },
                "official_scores_claimed": False,
            },
            "optimizer": "textgrad-openai-compatible",
            "execute_optimizer": True,
            "optimizer_model": "qwen/qwen3-8b",
            "optimizer_base_url": "http://127.0.0.1:1234/v1",
            "output_path": str(output),
        }
    )

    assert calls[0]["model"] == "qwen/qwen3-8b"
    assert payload["optimizer_runtime"]["status"] == "executed"
    assert payload["executes_tool"] is True
    assert payload["candidates"][0]["candidate_strategy"] == "textgrad_openai_compatible"
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_generate_slice_patch_candidates_tool_executes_runtime_plugin_adapter(
    monkeypatch,
    tmp_path: Path,
) -> None:
    output = tmp_path / "slice-patches.json"
    calls: list[dict] = []

    def fake_chat(**kwargs):
        calls.append(kwargs)
        return {
            "content": json.dumps(
                {
                    "critic_feedback": "Use a section-local multilingual cue.",
                    "after_text": "return concise JSON with protected locale constraints",
                }
            ),
            "raw_response": {"id": "chatcmpl-mcp-runtime-plugin"},
        }

    monkeypatch.setattr(
        "lib.failure_driven_proposal._call_openai_compatible_chat",
        fake_chat,
    )

    payload = mcp_service.generate_slice_patch_candidates_tool(
        {
            "context": {
                "recommended_patch_contract": {
                    "module_id": "multilingual_variant_explanation",
                    "section_id": "output_format",
                    "based_on_slices": ["dev/category/multilingual_pt"],
                    "target_slice": "multilingual_pt",
                    "before_text": "return concise JSON",
                    "protected_slices": ["multilingual_th"],
                    "protected_sections": ["role"],
                },
                "official_scores_claimed": False,
            },
            "optimizer": "runtime-textgrad-plugin",
            "plugin_manifests": [_runtime_optimizer_plugin_manifest_fixture()],
            "execute_optimizer": True,
            "output_path": str(output),
        }
    )

    assert calls[0]["model"] == "qwen/qwen3-8b"
    assert payload["optimizer"] == "runtime-textgrad-plugin"
    assert payload["optimizer_runtime"]["status"] == "executed"
    assert payload["executes_tool"] is True
    assert payload["executes_experiment"] is False
    assert payload["candidates"][0]["candidate_strategy"] == (
        "plugin_openai_compatible"
    )
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_generate_slice_patch_candidates_tool_executes_subprocess_plugin_adapter(
    tmp_path: Path,
) -> None:
    output = tmp_path / "slice-patches.json"
    runtime_script = tmp_path / "subprocess_optimizer.py"
    runtime_script.write_text(
        "import json, sys\n"
        "payload = json.load(sys.stdin)\n"
        "contract = payload['contract']\n"
        "json.dump({\n"
        "  'critic_feedback': 'subprocess optimizer saw ' + payload['optimizer'],\n"
        "  'after_text': contract.get('before_text', '') + '\\nsubprocess runtime patch',\n"
        "  'response_id': 'subprocess-mcp-001'\n"
        "}, sys.stdout)\n",
        encoding="utf-8",
    )

    payload = mcp_service.generate_slice_patch_candidates_tool(
        {
            "context": {
                "recommended_patch_contract": {
                    "module_id": "multilingual_variant_explanation",
                    "section_id": "output_format",
                    "based_on_slices": ["dev/category/multilingual_pt"],
                    "target_slice": "multilingual_pt",
                    "before_text": "return concise JSON",
                    "protected_slices": ["multilingual_th"],
                    "protected_sections": ["role"],
                },
                "official_scores_claimed": False,
            },
            "optimizer": "subprocess-textgrad-plugin",
            "plugin_manifests": [
                _subprocess_optimizer_plugin_manifest_fixture(
                    command=[sys.executable, str(runtime_script)]
                )
            ],
            "execute_optimizer": True,
            "output_path": str(output),
        }
    )

    assert payload["optimizer"] == "subprocess-textgrad-plugin"
    assert payload["optimizer_runtime"]["status"] == "executed"
    assert payload["optimizer_runtime"]["provider"] == "local-subprocess-json"
    assert payload["executes_tool"] is True
    assert payload["executes_experiment"] is False
    assert payload["candidates"][0]["candidate_strategy"] == "plugin_subprocess_json"
    assert "subprocess runtime patch" in payload["candidates"][0]["after_text"]
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_generate_slice_patch_candidates_tool_executes_python_package_adapter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    package_dir = tmp_path / "mcp_optimizer_runtime"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text(
        "\n".join(
            [
                "__version__ = '1.1.0'",
                "class FixtureOptimizerAdapter:",
                "    def generate_slice_patch_candidate(self, payload):",
                "        return {",
                "            'after_text': payload['contract']['before_text'] + '\\nmcp package patch',",
                "            'critic_feedback': 'mcp package adapter called',",
                "            'candidate_strategy': 'mcp_python_package_runtime',",
                "        }",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    output = tmp_path / "slice-patches.json"

    payload = mcp_service.generate_slice_patch_candidates_tool(
        {
            "context": {
                "recommended_patch_contract": {
                    "module_id": "multilingual_variant_explanation",
                    "section_id": "output_format",
                    "based_on_slices": ["dev/category/multilingual_pt"],
                    "target_slice": "multilingual_pt",
                    "before_text": "return concise JSON",
                    "protected_slices": ["multilingual_th"],
                    "protected_sections": ["role"],
                },
                "official_scores_claimed": False,
            },
            "optimizer": "python-package-optimizer-plugin",
            "plugin_manifests": [
                _python_package_optimizer_plugin_manifest_fixture(
                    package_import="mcp_optimizer_runtime",
                    candidate_method="generate_slice_patch_candidate",
                )
            ],
            "execute_optimizer": True,
            "output_path": str(output),
        }
    )

    assert payload["status"] == "completed"
    assert payload["optimizer_runtime"]["status"] == "executed"
    assert payload["optimizer_runtime"]["provider"] == "python-package"
    assert payload["optimizer_runtime"]["package_version"] == "1.1.0"
    assert payload["optimizer_runtime"]["fallback_used"] is False
    assert payload["executes_tool"] is True
    assert payload["executes_optimizer_runtime"] is True
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert payload["candidates"][0]["candidate_strategy"] == (
        "mcp_python_package_runtime"
    )
    assert "mcp package patch" in payload["candidates"][0]["after_text"]
    assert output.exists()


def test_generate_slice_patch_candidates_tool_executes_dspy_mipro_package_adapter(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dspy_runtime_path = (
        Path(__file__).resolve().parents[2]
        / ".research_cache"
        / "optimizer-runtime-packages"
        / "dspy"
    )
    if not (dspy_runtime_path / "dspy").exists():
        pytest.skip("dspy package runtime cache is not installed")
    monkeypatch.syspath_prepend(str(dspy_runtime_path))
    output = tmp_path / "slice-patches.json"

    payload = mcp_service.generate_slice_patch_candidates_tool(
        {
            "context": {
                "recommended_patch_contract": {
                    "module_id": "multilingual_variant_explanation",
                    "section_id": "output_format",
                    "based_on_slices": ["dev/category/multilingual_pt"],
                    "target_slice": "multilingual_pt",
                    "before_text": "return concise JSON",
                    "protected_slices": ["multilingual_th"],
                    "protected_sections": ["role"],
                },
                "official_scores_claimed": False,
            },
            "optimizer": "dspy-mipro-package",
            "execute_optimizer": True,
            "output_path": str(output),
        }
    )

    assert payload["status"] == "completed"
    assert payload["optimizer"] == "dspy-mipro-package"
    assert payload["optimizer_runtime"]["status"] == "executed"
    assert payload["optimizer_runtime"]["provider"] == "python-package"
    assert payload["optimizer_runtime"]["package_import"] == "dspy"
    assert payload["optimizer_runtime"]["package_version"] == "3.2.1"
    assert payload["optimizer_runtime"]["dspy_api"]["mipro_class"] == "MIPROv2"
    assert payload["optimizer_runtime"]["fallback_used"] is False
    assert payload["executes_tool"] is True
    assert payload["executes_optimizer_runtime"] is True
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert payload["candidates"][0]["candidate_strategy"] == (
        "dspy_mipro_package_runtime"
    )
    assert "multilingual_pt" in payload["candidates"][0]["after_text"]
    assert output.exists()


def test_probe_optimizer_runtime_tool_executes_subprocess_readiness_check(
    tmp_path: Path,
) -> None:
    output = tmp_path / "optimizer-runtime-probe.json"
    runtime_script = tmp_path / "subprocess_optimizer.py"
    runtime_script.write_text(
        "import json, sys\n"
        "payload = json.load(sys.stdin)\n"
        "if payload.get('task') == 'probe_optimizer_runtime':\n"
        "    json.dump({\n"
        "      'status': 'ready',\n"
        "      'runtime_ready': True,\n"
        "      'probe_detail': 'subprocess probe ok',\n"
        "      'response_id': 'probe-mcp-001'\n"
        "    }, sys.stdout)\n"
        "    raise SystemExit(0)\n"
        "json.dump({'status': 'unexpected'}, sys.stdout)\n",
        encoding="utf-8",
    )

    payload = mcp_service.probe_optimizer_runtime_tool(
        {
            "optimizer": "subprocess-textgrad-plugin",
            "plugin_manifests": [
                _subprocess_optimizer_plugin_manifest_fixture(
                    command=[sys.executable, str(runtime_script)]
                )
            ],
            "execute_probe": True,
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == "2026-06-05.optimizer-runtime-probe.v1"
    assert payload["status"] == "ready"
    assert payload["runtime_ready"] is True
    assert payload["runtime"]["provider"] == "local-subprocess-json"
    assert payload["executes_tool"] is True
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_probe_optimizer_runtime_tool_checks_python_package_readiness(
    tmp_path: Path,
) -> None:
    output = tmp_path / "optimizer-runtime-probe.json"

    payload = mcp_service.probe_optimizer_runtime_tool(
        {
            "optimizer": "python-package-optimizer-plugin",
            "plugin_manifests": [
                _python_package_optimizer_plugin_manifest_fixture(
                    package_import="json"
                )
            ],
            "execute_probe": True,
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == "2026-06-05.optimizer-runtime-probe.v1"
    assert payload["status"] == "ready"
    assert payload["runtime_ready"] is True
    assert payload["runtime"]["provider"] == "python-package"
    assert payload["probe_result"]["package_import"] == "json"
    assert payload["probe_result"]["import_available"] is True
    assert payload["executes_tool"] is True
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_optimizer_package_runtime_benefit_audit_tool_builds_artifact(
    tmp_path: Path,
) -> None:
    output = tmp_path / "optimizer-package-runtime-benefit-audit.json"

    payload = mcp_service.build_optimizer_package_runtime_benefit_audit_tool(
        {
            "optimizer_runtime_probe": {
                "schema_version": "2026-06-05.optimizer-runtime-probe.v1",
                "status": "ready",
                "runtime_ready": True,
                "optimizer": {"name": "promptwizard-python-package"},
                "probe_result": {
                    "package_import": "promptwizard",
                    "package_version": "1.0.0",
                    "promptwizard_api": {
                        "candidate_method": (
                            "prompt_generation.generate_candidate_prompts"
                        )
                    },
                },
                "official_scores_claimed": False,
            },
            "slice_patch_candidates": {
                "schema_version": "2026-06-04.slice-patch-candidates.v1",
                "status": "completed",
                "optimizer": "promptwizard-python-package",
                "candidate_count": 1,
                "candidates": [{"patch_id": "patch-mcp-001"}],
                "official_scores_claimed": False,
            },
            "gate_decision": {
                "schema_version": "2026-06-05.gate-policy-decision.v1",
                "status": "passed_for_canary",
                "metric_delta": {"SHIFT": 0.75},
                "gate": {"canary_allowed": True},
                "hard_blockers": [],
                "official_scores_claimed": False,
            },
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == (
        "2026-06-16.optimizer-package-runtime-benefit-audit.v1"
    )
    assert payload["status"] == "benefit_verified"
    assert payload["gate"]["benefit_verified"] is True
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_method_proposal_generation_trace_tool_builds_artifact(
    tmp_path: Path,
) -> None:
    output = tmp_path / "method-proposal-generation-trace.json"

    payload = mcp_service.build_method_proposal_generation_trace_tool(
        {
            "generation_context": {
                "task_family": "smol_worldcup",
                "failure_slice": "multilingual_bn",
                "objective": "search for robust prompt repair methods",
            },
            "generation_run": {
                "generator": "llm-method-search",
                "model": "qwen/qwen3-8b",
                "prompt_template_id": "method-search-v1",
            },
            "reasoning_trace": {
                "trace_kind": "structured_rationale",
                "steps": [
                    {
                        "step_id": "reason-mcp-001",
                        "summary": "Try the narrow locale format patch first.",
                        "proposal_ids": ["proposal-mcp-001"],
                    }
                ],
            },
            "proposals": [
                {
                    "proposal_id": "proposal-mcp-001",
                    "method": "section_patch",
                    "target_scope": "multilingual_variant_explanation/output_format",
                    "rationale": "Constrain output format for BN cases.",
                },
                {
                    "proposal_id": "proposal-mcp-002",
                    "method": "global_prompt_rewrite",
                    "target_scope": "global",
                    "rationale": "Rewrite all answer instructions.",
                },
            ],
            "ranking_decisions": [
                {
                    "proposal_id": "proposal-mcp-001",
                    "rank": 1,
                    "decision": "selected_for_validation",
                    "score": 0.8,
                    "rationale": "Narrower patch.",
                },
                {
                    "proposal_id": "proposal-mcp-002",
                    "rank": 2,
                    "decision": "rejected",
                    "score": 0.2,
                    "rationale": "Too broad for current gate.",
                },
            ],
            "selected_proposal_ids": ["proposal-mcp-001"],
            "gate_results": [
                {
                    "proposal_id": "proposal-mcp-001",
                    "gate_status": "blocked",
                    "metric_delta": {"SHIFT": 0.1},
                    "hard_blockers": ["slice_regression"],
                }
            ],
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == (
        "2026-06-16.method-proposal-generation-trace.v1"
    )
    assert payload["proposal_count"] == 2
    assert payload["selected_proposal_count"] == 1
    assert payload["pruned_proposal_count"] == 1
    assert payload["reasoning_trace"]["records_private_chain_of_thought"] is False
    assert payload["validation_links"][0]["gate_status"] == "blocked"
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_method_search_study_mcp_tools_run_ask_tell_chain(
    tmp_path: Path,
) -> None:
    study_output = tmp_path / "method-search-study.json"
    ask_output = tmp_path / "method-search-ask.json"
    tell_output = tmp_path / "method-search-tell.json"
    feedback_store = tmp_path / "gate-feedback-memory-store.json"
    sampler_adapter_output = tmp_path / "optuna-sampler-adapter.json"
    storage_adapter_output = tmp_path / "optuna-storage-adapter.json"
    dashboard_export_output = tmp_path / "optuna-dashboard-export.json"

    study = mcp_service.build_method_search_study_tool(
        {
            "study_name": "smol-method-search",
            "objective": "search local repair methods",
            "operators": ["combine", "adapt"],
            "output_path": str(study_output),
        }
    )
    ask_payload = mcp_service.ask_method_search_trial_tool(
        {
            "study": study,
            "objective": "reduce BN failures with local gate evidence only",
            "operators": ["combine", "adapt"],
            "llm_proposals": [
                {
                    "proposal_id": "proposal-mcp-combine",
                    "operator_id": "combine",
                    "why_this_operator_applies": "Combine locale evidence with strict JSON output.",
                    "hypothesis": "A section-local combined instruction may reduce BN errors.",
                    "change_surface": "prompt_section",
                    "expected_effect": "local gate may improve the target slice",
                    "risk": "protected slices may regress",
                    "cheapest_validation": "run local slice gate on dev rows",
                    "rollback_or_stop_condition": "stop on hard blocker",
                }
            ],
            "model": "qwen/qwen3-8b",
            "adapter": "llm-method-search-fixture",
            "slice_id": "dev/category/multilingual_bn",
            "patch_scope": "single_module_single_section",
            "budget": {"max_candidates": 1},
            "output_path": str(ask_output),
        }
    )
    trial = ask_payload["trials"][0]
    told = mcp_service.tell_method_search_trial_tool(
        {
            "study": ask_payload["study"],
            "trial": trial,
            "gate_result": {
                "proposal_id": trial["proposal_id"],
                "operator_id": trial["params"]["operator"],
                "status": "blocked",
                "score": 0.0,
                "hard_blockers": ["slice_regression"],
                "official_scores_claimed": False,
            },
            "output_path": str(tell_output),
            "feedback_store_path": str(feedback_store),
        }
    )
    sampler_adapter = mcp_service.build_optuna_sampler_adapter_tool(
        {
            "study": told["study"],
            "output_path": str(sampler_adapter_output),
        }
    )
    storage_adapter = mcp_service.build_optuna_storage_adapter_tool(
        {
            "study": told["study"],
            "gate_feedback_memory_store_file": str(feedback_store),
            "output_path": str(storage_adapter_output),
        }
    )
    dashboard_export = mcp_service.build_optuna_dashboard_export_tool(
        {
            "study": told["study"],
            "gate_feedback_memory_store_file": str(feedback_store),
            "output_path": str(dashboard_export_output),
        }
    )

    assert study["schema_version"] == "2026-06-19.method-search-study.v1"
    assert ask_payload["schema_version"] == "2026-06-19.method-search-ask.v1"
    assert trial["state"] == "WAITING"
    assert told["schema_version"] == "2026-06-19.method-search-tell.v1"
    assert told["trial"]["state"] == "PRUNED"
    assert told["gate_feedback_memory"]["operator_weights"]["combine"] < 1.0
    assert told["feedback_store"]["path"] == str(feedback_store)
    assert told["official_scores_claimed"] is False
    assert sampler_adapter["adapter_name"] == "OptunaSamplerAdapter"
    assert storage_adapter["adapter_name"] == "OptunaStorageAdapter"
    assert dashboard_export["export_name"] == "OptunaDashboardExport"
    assert tell_output.exists()


def test_multi_optimizer_candidate_race_mcp_tool_writes_winner_bundle(
    tmp_path: Path,
) -> None:
    output = tmp_path / "multi-optimizer-candidate-race.json"
    output_dir = tmp_path / "race-artifacts"
    feedback_store = tmp_path / "gate-feedback-memory-store.json"

    payload = mcp_service.build_multi_optimizer_candidate_race_tool(
        {
            "race_name": "sst2-race",
            "objective": "pick the best optimizer candidate under one gate",
            "operators": ["combine", "adapt"],
            "candidate_sources": {
                "sources": [
                    {
                        "source_id": "llm-hexagon",
                        "optimizer": "llm",
                        "proposals": [
                            {
                                "proposal_id": "llm-001",
                                "operator_id": "adapt",
                                "why_this_operator_applies": "Adapt targets a failure slice.",
                                "hypothesis": "The LLM proposal may reduce slice errors.",
                                "change_surface": "prompt_section",
                                "expected_effect": "gate decides the effect",
                                "risk": "canary regression",
                                "cheapest_validation": "run shared gate",
                                "rollback_or_stop_condition": "stop on hard blocker",
                            }
                        ],
                    },
                    {
                        "source_id": "optuna-tpe",
                        "optimizer": "optuna",
                        "proposals": [
                            {
                                "proposal_id": "optuna-049",
                                "operator_id": "combine",
                                "why_this_operator_applies": "Combine feature families.",
                                "hypothesis": "Optuna may find a better local configuration.",
                                "change_surface": "classifier_features",
                                "expected_effect": "gate decides the effect",
                                "risk": "local overfit",
                                "cheapest_validation": "run shared gate",
                                "rollback_or_stop_condition": "stop on hard blocker",
                            }
                        ],
                    },
                ]
            },
            "gate_results": {
                "gate_results": [
                    {
                        "proposal_id": "llm-001",
                        "operator_id": "adapt",
                        "status": "blocked",
                        "score": 0.66,
                        "hard_blockers": ["canary_regression"],
                    },
                    {
                        "proposal_id": "optuna-049",
                        "operator_id": "combine",
                        "status": "passed",
                        "score": 0.7,
                        "metric_delta": {"accuracy": 0.01},
                        "hard_blockers": [],
                    },
                ]
            },
            "output_dir": str(output_dir),
            "feedback_store_path": str(feedback_store),
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == "2026-06-25.multi-optimizer-candidate-race.v1"
    assert payload["winner"]["proposal_id"] == "optuna-049"
    assert payload["winner"]["optimizer"] == "optuna"
    assert payload["study"]["trial_count"] == 2
    assert payload["acceptance_answers"]["winner_selected_by_gate"] is True
    assert payload["official_scores_claimed"] is False
    assert output.exists()
    assert feedback_store.exists()


def test_run_multi_optimizer_candidate_race_mcp_tool_generates_and_races(
    tmp_path: Path,
) -> None:
    output = tmp_path / "multi-optimizer-candidate-race-run.json"
    output_dir = tmp_path / "run"
    feedback_store = tmp_path / "gate-feedback-memory-store.json"

    payload = mcp_service.run_multi_optimizer_candidate_race_tool(
        {
            "race_name": "execution-capable-race",
            "objective": "generate and compare multiple optimizer candidates",
            "mode": "review/dry-run",
            "context": {
                "recommended_patch_contract": {
                    "module_id": "router",
                    "section_id": "country_aliases",
                    "target_slice": "alias_confusion",
                    "based_on_slices": ["alias_confusion"],
                    "before_text": "Resolve aliases conservatively.",
                    "protected_slices": ["exact_match"],
                },
                "official_scores_claimed": False,
            },
            "gate_results": {
                "gate_results": [
                    {
                        "proposal_id": "llm-001",
                        "operator_id": "adapt",
                        "status": "blocked",
                        "score": 0.61,
                        "hard_blockers": ["canary_regression"],
                    },
                    {
                        "proposal_id": "optuna-001",
                        "operator_id": "combine",
                        "status": "passed",
                        "score": 0.72,
                        "hard_blockers": [],
                    },
                    {
                        "proposal_id": "textgrad-001",
                        "operator_id": "adapt",
                        "status": "passed",
                        "score": 0.69,
                        "hard_blockers": [],
                    },
                    {
                        "proposal_id": "dspy-001",
                        "operator_id": "combine",
                        "status": "blocked",
                        "score": 0.63,
                        "hard_blockers": ["fallback_not_real_runtime"],
                    },
                    {
                        "proposal_id": "heuristic-001",
                        "operator_id": "separate",
                        "status": "blocked",
                        "score": 0.60,
                        "hard_blockers": ["no_local_improvement"],
                    },
                ]
            },
            "llm_proposals": {
                "proposals": [
                    {
                        "proposal_id": "llm-001",
                        "operator_id": "adapt",
                        "why_this_operator_applies": "Adapt targets the failing slice.",
                        "hypothesis": "The LLM proposal may reduce slice errors.",
                        "change_surface": "prompt_section",
                        "expected_effect": "gate decides the effect",
                        "risk": "canary regression",
                        "cheapest_validation": "run shared gate",
                        "rollback_or_stop_condition": "stop on hard blocker",
                    }
                ]
            },
            "optimizer_sources": ["llm", "optuna", "textgrad", "dspy", "heuristic"],
            "operators": ["combine", "adapt", "separate"],
            "output_dir": str(output_dir),
            "feedback_store_path": str(feedback_store),
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == (
        "2026-06-25.multi-optimizer-candidate-race-run.v1"
    )
    assert payload["winner"]["proposal_id"] == "optuna-001"
    assert payload["source_generation"]["generated_candidate_count"] == 5
    assert payload["acceptance_answers"]["parallel_generation_used"] is True
    assert output.exists()
    assert feedback_store.exists()


def test_run_real_benchmark_readiness_mcp_tool_dispatches_runner(
    tmp_path: Path,
    monkeypatch,
) -> None:
    output = tmp_path / "real-benchmark-readiness-run.json"
    output_dir = tmp_path / "readiness"
    feedback_store = tmp_path / "gate-feedback-memory-store.json"
    captured: dict[str, object] = {}

    def fake_run_real_benchmark_readiness_run(**kwargs: object) -> dict[str, object]:
        captured.update(kwargs)
        return {
            "schema_version": "2026-06-27.real-benchmark-readiness-run.v1",
            "status": "completed",
            "benchmark_id": kwargs["benchmark_id"],
            "round_count": kwargs["round_count"],
            "official_scores_claimed": False,
        }

    monkeypatch.setattr(
        mcp_service,
        "run_real_benchmark_readiness_run",
        fake_run_real_benchmark_readiness_run,
    )

    payload = mcp_service.run_real_benchmark_readiness_run_tool(
        {
            "run_name": "mcp-readiness",
            "objective": "gate optimizer candidates from local benchmark eval",
            "benchmark_id": "smol_worldcup",
            "rows": {
                "rows": [
                    {
                        "id": "S1-H1-001",
                        "shift_axis": "H",
                        "category": "reasoning",
                        "subcategory": "answer_match",
                        "auto_grade": "answer_match",
                        "max_score": 10,
                        "prompt": "Which country won the 2002 FIFA World Cup?",
                        "answer_key": {"answer": "Brazil"},
                    }
                ]
            },
            "context": {
                "recommended_patch_contract": {
                    "module_id": "router",
                    "section_id": "country_aliases",
                    "target_slice": "alias_confusion",
                    "based_on_slices": ["alias_confusion"],
                    "before_text": "Resolve aliases conservatively.",
                    "protected_slices": ["exact_match"],
                },
                "official_scores_claimed": False,
            },
            "round_count": 3,
            "optimizer_sources": ["python-package-optimizer-plugin"],
            "operators": ["adapt", "combine"],
            "optimizer_gate_plugin_manifest_files": [
                str(
                    tmp_path
                    / "missing-but-dispatch-path-checked-by-monkeypatch.json"
                )
            ],
            "model": "fixture-model",
            "base_url": "http://127.0.0.1:8000/v1",
            "output_dir": str(output_dir),
            "feedback_store_path": str(feedback_store),
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == "2026-06-27.real-benchmark-readiness-run.v1"
    assert captured["run_name"] == "mcp-readiness"
    assert captured["rows"] == {
        "rows": [
            {
                "id": "S1-H1-001",
                "shift_axis": "H",
                "category": "reasoning",
                "subcategory": "answer_match",
                "auto_grade": "answer_match",
                "max_score": 10,
                "prompt": "Which country won the 2002 FIFA World Cup?",
                "answer_key": {"answer": "Brazil"},
            }
        ]
    }
    assert captured["optimizer_sources"] == ["python-package-optimizer-plugin"]
    assert captured["operators"] == ["adapt", "combine"]
    assert captured["optimizer_gate_plugin_manifests"] == [
        tmp_path / "missing-but-dispatch-path-checked-by-monkeypatch.json"
    ]
    assert captured["model"] == "fixture-model"
    assert captured["output_dir"] == output_dir
    assert captured["output_path"] == output
    assert payload["official_scores_claimed"] is False


def test_materialize_slice_patch_candidate_tool_writes_review_bundle(
    tmp_path: Path,
) -> None:
    output = tmp_path / "slice-patch-materialization.json"

    payload = mcp_service.materialize_slice_patch_candidate_tool(
        {
            "candidate": {
                "patch_id": "slice-patch-001",
                "module_id": "multilingual_variant_explanation",
                "section_id": "output_format",
                "before_text": "return concise JSON",
                "after_text": "return concise JSON with locale evidence",
                "protected_slices": ["multilingual_th"],
                "protected_sections": ["role"],
                "official_scores_claimed": False,
            },
            "base_profile_id": "p3-dev-v2",
            "output_path": str(output),
        }
    )

    assert payload["status"] == "needs_prompt_profile_registration"
    assert payload["materialized_change"]["edit_scope"] == "single_section"
    assert payload["execution_ready"] is False
    assert payload["executes_experiment"] is False
    assert output.exists()
    assert payload["official_scores_claimed"] is False


def test_record_slice_patch_outcome_tool_writes_learning_artifact(
    tmp_path: Path,
) -> None:
    output = tmp_path / "slice-patch-outcome.json"

    payload = mcp_service.record_slice_patch_outcome_tool(
        {
            "candidate": {
                "schema_version": "2026-06-04.slice-patch-candidate.v1",
                "patch_id": "slice-patch-001",
                "module_id": "multilingual_variant_explanation",
                "section_id": "output_format",
                "optimizer": "promptwizard-constrained",
                "candidate_strategy": "constraint_guard_variant",
                "based_on_slices": ["dev/category/multilingual_bn"],
                "protected_slices": ["multilingual_tr"],
                "before_text": "return concise JSON",
                "after_text": "return concise JSON with locale evidence",
                "edit_scope": "single_section",
                "official_scores_claimed": False,
            },
            "materialization": {
                "schema_version": "2026-06-04.slice-patch-materialization.v1",
                "status": "needs_prompt_profile_registration",
                "base_profile_id": "p3-system-fixture",
                "patch_id": "slice-patch-001",
                "execution_ready": False,
                "official_scores_claimed": False,
            },
            "gate_decision": {
                "schema_version": "2026-06-05.gate-policy-decision.v1",
                "status": "blocked",
                "split": "dev",
                "metric_delta": {"SHIFT": 0.2},
                "gate": {
                    "canary_allowed": False,
                    "promotion_ready": False,
                },
                "hard_blockers": ["slice_regression"],
                "slice_regressions": [
                    {
                        "slice_key": "dev/category/multilingual_bn",
                        "slice_name": "multilingual_bn",
                        "delta": -8.0,
                        "gate": "blocked",
                    }
                ],
                "official_scores_claimed": False,
            },
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == "2026-06-05.slice-patch-outcome.v1"
    assert payload["patch_id"] == "slice-patch-001"
    assert payload["accepted_for_next_stage"] is False
    assert payload["failure_labels"] == ["slice_regression"]
    assert payload["learning_signal"]["outcome"] == "blocked"
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_build_slice_optimizer_selection_tool_uses_outcome_memory(
    tmp_path: Path,
) -> None:
    output = tmp_path / "slice-optimizer-selection.json"

    payload = mcp_service.build_slice_optimizer_selection_tool(
        {
            "outcomes": [
                {
                    "schema_version": "2026-06-05.slice-patch-outcome.v1",
                    "status": "completed",
                    "patch_id": "blocked-pw",
                    "optimizer": "promptwizard-constrained",
                    "module_id": "multilingual_variant_explanation",
                    "section_id": "output_format",
                    "gate_status": "blocked",
                    "accepted_for_next_stage": False,
                    "failure_labels": ["slice_regression"],
                    "learning_signal": {
                        "outcome": "blocked",
                        "target_scope": "multilingual_variant_explanation/output_format",
                        "failure_labels": ["slice_regression"],
                    },
                    "official_scores_claimed": False,
                },
                {
                    "schema_version": "2026-06-05.slice-patch-outcome.v1",
                    "status": "completed",
                    "patch_id": "passed-textgrad",
                    "optimizer": "textgrad-local",
                    "module_id": "multilingual_variant_explanation",
                    "section_id": "output_format",
                    "gate_status": "passed_for_canary",
                    "accepted_for_next_stage": True,
                    "failure_labels": [],
                    "learning_signal": {
                        "outcome": "passed_for_canary",
                        "target_scope": "multilingual_variant_explanation/output_format",
                        "failure_labels": [],
                    },
                    "official_scores_claimed": False,
                },
            ],
            "target_scope": "multilingual_variant_explanation/output_format",
            "failure_labels": ["slice_regression"],
            "candidate_optimizers": ["promptwizard-constrained", "textgrad-local"],
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == "2026-06-05.slice-optimizer-selection.v1"
    assert payload["selected_optimizer"] == "textgrad-local"
    assert payload["optimizer_scores"][0]["optimizer"] == "textgrad-local"
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_build_optimizer_gate_run_tool_writes_non_executing_bundle(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "optimizer-gate-run"

    payload = mcp_service.build_optimizer_gate_run_tool(
        {
            "context": {
                "recommended_patch_contract": {
                    "module_id": "multilingual_variant_explanation",
                    "section_id": "output_format",
                    "based_on_slices": ["dev/category/multilingual_pt"],
                    "target_slice": "multilingual_pt",
                    "before_text": "return concise JSON",
                    "protected_slices": ["multilingual_th"],
                    "protected_sections": ["role"],
                },
                "official_scores_claimed": False,
            },
            "base_profile_id": "p3-system-fixture",
            "optimizer": "promptwizard-constrained",
            "output_dir": str(output_dir),
        }
    )

    assert payload["schema_version"] == "2026-06-05.optimizer-gate-run.v1"
    assert payload["status"] == "needs_prompt_profile_registration"
    assert payload["optimizer"]["name"] == "promptwizard-constrained"
    assert payload["optimizer"]["registry_ref"] == (
        "optimizer_adapter:promptwizard-constrained"
    )
    assert payload["runtime_probe"]["status"] == "not_required"
    assert payload["stages"][0]["name"] == "probe_optimizer_runtime"
    assert "evaluate_gate_policy" in payload["gate_plan"]["required_gates"]
    assert "gate_policy:slice-dev-hard-gate" in payload["gate_plan"]["policy_refs"]
    assert payload["gate_plan"]["canary_allowed"] is False
    assert payload["executes_tool"] is False
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert (output_dir / "optimizer-runtime-probe.json").exists()
    assert (output_dir / "optimizer-gate-run.json").exists()


def test_build_optimizer_gate_system_spec_tool_writes_registry(
    tmp_path: Path,
) -> None:
    output = tmp_path / "optimizer-gate-system-spec.json"

    payload = mcp_service.build_optimizer_gate_system_spec_tool(
        {
            "plugin_manifests": [_optimizer_gate_plugin_manifest_fixture()],
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == "2026-06-05.optimizer-gate-system-spec.v1"
    assert any(
        item["name"] == "textgrad-openai-compatible"
        for item in payload["optimizer_adapters"]
    )
    assert any(
        item["policy_id"] == "slice-dev-hard-gate"
        and item["function"] == "evaluate_gate_policy"
        and item["decision_schema"] == "2026-06-05.gate-policy-decision.v1"
        for item in payload["gate_policies"]
    )
    assert any(
        item["name"] == "dspy-mipro-local" and item["source"] == "plugin"
        for item in payload["optimizer_adapters"]
    )
    assert any(
        item["benchmark_id"] == "smol_worldcup"
        for item in payload["benchmark_adapters"]
    )
    assert payload["plugin_manifests"][0]["plugin_id"] == "local-dspy-fixture"
    assert payload["executes_tool"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_build_optimizer_gate_execution_plan_tool_writes_non_executing_plan(
    tmp_path: Path,
) -> None:
    output = tmp_path / "optimizer-gate-execution-plan.json"
    payload = mcp_service.build_optimizer_gate_execution_plan_tool(
        {
            "optimizer_gate_run": {
                "schema_version": "2026-06-05.optimizer-gate-run.v1",
                "status": "needs_prompt_profile_registration",
                "base_profile_id": "p3-system-fixture",
                "optimizer": {
                    "name": "promptwizard-constrained",
                    "candidate_count": 1,
                },
                "runtime_probe": {
                    "status": "not_required",
                    "runtime_ready": True,
                },
                "materialization": {
                    "status": "needs_prompt_profile_registration",
                    "execution_ready": False,
                },
                "gate_plan": {
                    "required_gates": [
                        "evaluate_gate_policy",
                        "evaluate_slice_variance_gate",
                        "build_gate_policy_composition",
                    ],
                    "canary_allowed": False,
                    "promotion_ready": False,
                },
                "official_scores_claimed": False,
            },
            "benchmark_id": "smol_worldcup",
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == "2026-06-05.optimizer-gate-execution-plan.v1"
    assert payload["status"] == "needs_prompt_profile_registration"
    assert payload["benchmark_adapter"]["benchmark_id"] == "smol_worldcup"
    assert payload["preflight"]["candidate_count"] == 1
    assert payload["preflight"]["hard_blockers"] == []
    assert payload["executes_tool"] is False
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_build_prompt_profile_registration_plan_tool_writes_review_plan(
    tmp_path: Path,
) -> None:
    output = tmp_path / "prompt-profile-registration-plan.json"
    payload = mcp_service.build_prompt_profile_registration_plan_tool(
        {
            "materialization": {
                "schema_version": "2026-06-04.slice-patch-materialization.v1",
                "status": "needs_prompt_profile_registration",
                "base_profile_id": "p3-system-fixture",
                "patch_id": "slice-patch-001",
                "optimizer": "promptwizard-constrained",
                "materialized_change": {
                    "module_id": "multilingual_variant_explanation",
                    "section_id": "output_format",
                    "change_surface": "prompt_section",
                    "edit_scope": "single_section",
                    "before_text": "return concise JSON",
                    "after_text": "return concise JSON with locale evidence",
                    "protected_slices": ["multilingual_tr"],
                    "protected_sections": ["role"],
                },
                "execution_ready": False,
                "official_scores_claimed": False,
            },
            "benchmark_id": "smol_worldcup",
            "proposed_profile_id": "p3-system-fixture-slice-patch-001",
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == (
        "2026-06-05.prompt-profile-registration-plan.v1"
    )
    assert payload["status"] == "ready_for_profile_registration_review"
    assert payload["registry_patch"]["target_profile_id"] == (
        "p3-system-fixture-slice-patch-001"
    )
    assert payload["gate_constraints"]["canary_allowed_before_dev_gate"] is False
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_build_optimizer_gate_execution_preflight_tool_blocks_unregistered_profile(
    tmp_path: Path,
) -> None:
    output = tmp_path / "optimizer-gate-execution-preflight.json"
    payload = mcp_service.build_optimizer_gate_execution_preflight_tool(
        {
            "registration_plan": {
                "schema_version": "2026-06-05.prompt-profile-registration-plan.v1",
                "status": "ready_for_profile_registration_review",
                "benchmark_adapter": {"benchmark_id": "smol_worldcup"},
                "materialization_ref": "inline",
                "base_profile_id": "p3-system-fixture",
                "proposed_profile_id": "p3-system-fixture-slice-patch-001",
                "registry_patch": {"operation": "add_prompt_profile"},
                "required_pre_execution_checks": [],
                "gate_constraints": {"canary_allowed_before_dev_gate": False},
                "claim_boundary": "review-only",
                "official_scores_claimed": False,
            },
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == (
        "2026-06-05.optimizer-gate-execution-preflight.v1"
    )
    assert payload["status"] == "blocked_prompt_profile_not_registered"
    assert payload["hard_blockers"] == ["registered_prompt_profile_missing"]
    assert payload["gate"]["canary_allowed"] is False
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_build_registered_profile_execution_bundle_tool_writes_bundle(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "registered-profile-execution"
    payload = mcp_service.build_registered_profile_execution_bundle_tool(
        {
            "registration_plan": {
                "schema_version": "2026-06-05.prompt-profile-registration-plan.v1",
                "status": "ready_for_profile_registration_review",
                "benchmark_adapter": {"benchmark_id": "smol_worldcup"},
                "materialization_ref": "inline",
                "base_profile_id": "p3-system-fixture",
                "proposed_profile_id": "p3-system-fixture-slice-patch-001",
                "registry_patch": {"operation": "add_prompt_profile"},
                "required_pre_execution_checks": [],
                "gate_constraints": {"canary_allowed_before_dev_gate": False},
                "claim_boundary": "review-only",
                "official_scores_claimed": False,
            },
            "registered_profile": {
                "schema_version": "2026-06-05.prompt-profile-registration.v1",
                "status": "registered",
                "registration_plan_ref": "inline",
                "base_profile_id": "p3-system-fixture",
                "proposed_profile_id": "p3-system-fixture-slice-patch-001",
                "registered_profile": {
                    "registered": True,
                    "registered_profile_id": "p3-system-fixture-slice-patch-001",
                    "expected_profile_id": "p3-system-fixture-slice-patch-001",
                    "registry_ref": "inline",
                },
                "registry_entry": {"profile_id": "p3-system-fixture-slice-patch-001"},
                "required_pre_execution_checks": [],
                "gate": {"canary_allowed": False},
                "claim_boundary": "registration only",
                "official_scores_claimed": False,
            },
            "output_dir": str(output_dir),
        }
    )

    assert payload["schema_version"] == (
        "2026-06-05.registered-profile-execution-bundle.v1"
    )
    assert payload["status"] == "blocked_missing_pre_execution_artifacts"
    assert payload["registered_profile"]["registered"] is True
    assert payload["gate"]["canary_allowed"] is False
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert (output_dir / "registered-profile-execution-bundle.json").exists()


def test_run_registered_profile_execution_tool_generates_leakage_audit(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "registered-profile-execution-run"
    payload = mcp_service.run_registered_profile_execution_tool(
        {
            "registration_plan": {
                "schema_version": "2026-06-05.prompt-profile-registration-plan.v1",
                "status": "ready_for_profile_registration_review",
                "benchmark_adapter": {"benchmark_id": "smol_worldcup"},
                "materialization_ref": "inline",
                "base_profile_id": "p3-dev-v2",
                "proposed_profile_id": "p3-dev-v2-slice-patch-mcp",
                "registry_patch": {"operation": "add_prompt_profile"},
                "required_pre_execution_checks": [],
                "gate_constraints": {"canary_allowed_before_dev_gate": False},
                "claim_boundary": "review-only",
                "official_scores_claimed": False,
            },
            "registered_profile": {
                "schema_version": "2026-06-05.prompt-profile-registration.v1",
                "status": "registered",
                "registration_plan_ref": "inline",
                "base_profile_id": "p3-dev-v2",
                "proposed_profile_id": "p3-dev-v2-slice-patch-mcp",
                "registered_profile": {
                    "registered": True,
                    "registered_profile_id": "p3-dev-v2-slice-patch-mcp",
                    "expected_profile_id": "p3-dev-v2-slice-patch-mcp",
                    "registry_ref": "inline",
                },
                "registry_entry": {
                    "active": True,
                    "profile_id": "p3-dev-v2-slice-patch-mcp",
                    "base_profile_id": "p3-dev-v2",
                    "module_id": "multilingual_variant_explanation",
                    "section_id": "output_format",
                    "materialized_change": {
                        "after_text": "return concise JSON with locale evidence"
                    },
                },
                "required_pre_execution_checks": [],
                "gate": {"canary_allowed": False},
                "claim_boundary": "registration only",
                "official_scores_claimed": False,
            },
            "prompt_leakage_rows": [
                {
                    "id": "S1-I1-001",
                    "shift_axis": "instruction_following",
                    "category": "multilingual_pt",
                    "auto_grade": "json",
                    "prompt": "Return a compact JSON answer about a football result.",
                }
            ],
            "output_dir": str(output_dir),
        }
    )

    assert payload["schema_version"] == "2026-06-05.registered-profile-execution-run.v1"
    assert payload["status"] == "blocked_missing_pre_execution_artifacts"
    assert payload["execution"]["prompt_leakage_audit"]["status"] == "generated"
    assert payload["gate"]["canary_allowed"] is False
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert (output_dir / "prompt-leakage-audit.json").exists()
    assert (output_dir / "registered-profile-execution-run.json").exists()


def test_run_registered_profile_execution_tool_generates_gate_decision(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "registered-profile-execution-run"
    profile_id = "p3-dev-v2-slice-patch-mcp-gate"
    payload = mcp_service.run_registered_profile_execution_tool(
        {
            "registration_plan": {
                "schema_version": "2026-06-05.prompt-profile-registration-plan.v1",
                "status": "ready_for_profile_registration_review",
                "benchmark_adapter": {"benchmark_id": "smol_worldcup"},
                "materialization_ref": "inline",
                "base_profile_id": "p3-dev-v2",
                "proposed_profile_id": profile_id,
                "registry_patch": {"operation": "add_prompt_profile"},
                "required_pre_execution_checks": [],
                "gate_constraints": {"canary_allowed_before_dev_gate": False},
                "claim_boundary": "review-only",
                "official_scores_claimed": False,
            },
            "registered_profile": {
                "schema_version": "2026-06-05.prompt-profile-registration.v1",
                "status": "registered",
                "registration_plan_ref": "inline",
                "base_profile_id": "p3-dev-v2",
                "proposed_profile_id": profile_id,
                "registered_profile": {
                    "registered": True,
                    "registered_profile_id": profile_id,
                    "expected_profile_id": profile_id,
                    "registry_ref": "inline",
                },
                "registry_entry": {
                    "active": True,
                    "profile_id": profile_id,
                    "base_profile_id": "p3-dev-v2",
                    "module_id": "multilingual_variant_explanation",
                    "section_id": "output_format",
                    "materialized_change": {
                        "after_text": "return concise JSON with locale evidence"
                    },
                },
                "required_pre_execution_checks": [],
                "gate": {"canary_allowed": False},
                "claim_boundary": "registration only",
                "official_scores_claimed": False,
            },
            "prompt_leakage_audit": {
                "schema_version": "2026-05-19.smol-worldcup-prompt-leakage-audit.v1",
                "status": "passed",
                "prompt_profile": profile_id,
                "row_count": 1,
                "leak_count": 0,
                "official_scores_claimed": False,
            },
            "target_smoke": {
                "schema_version": "2026-05-20.smol-worldcup-model-eval.v1",
                "status": "completed",
                "model": {"prompt_profile": profile_id},
                "dataset": {"evaluation_split": "dev", "row_count": 1},
                "metrics": {"SHIFT": 80.0},
                "failure_summary": {"runtime_error_count": 0},
                "official_scores_claimed": False,
            },
            "dev_model_eval": {
                "schema_version": "2026-05-20.smol-worldcup-model-eval.v1",
                "status": "completed",
                "model": {"prompt_profile": profile_id},
                "dataset": {"evaluation_split": "dev", "row_count": 3},
                "metric_delta": {"SHIFT": 0.25},
                "slices": [
                    {
                        "slice_key": "dev/category/multilingual_pt",
                        "dimension": "category",
                        "slice_name": "multilingual_pt",
                        "metric": "score_percent",
                        "before": 30.0,
                        "after": 35.0,
                        "delta": 5.0,
                        "row_count": 3,
                        "gate": "passed",
                    }
                ],
                "failure_summary": {"runtime_error_count": 0},
                "official_scores_claimed": False,
            },
            "output_dir": str(output_dir),
        }
    )

    assert payload["schema_version"] == "2026-06-05.registered-profile-execution-run.v1"
    assert payload["status"] == "ready_for_canary_execution"
    assert payload["execution"]["gate_decision"]["status"] == "generated"
    assert payload["gate"]["canary_allowed"] is True
    assert (output_dir / "gate-policy-input.json").exists()
    assert (output_dir / "gate-policy-decision.json").exists()
    assert (output_dir / "gate-policy-composition.json").exists()
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False


def test_build_registered_profile_canary_preflight_tool_blocks_dev_gate_failure(
    tmp_path: Path,
) -> None:
    output = tmp_path / "registered-profile-canary-preflight.json"

    payload = mcp_service.build_registered_profile_canary_preflight_tool(
        {
            "registered_profile_execution_run": {
                "schema_version": "2026-06-05.registered-profile-execution-run.v1",
                "status": "blocked_by_hard_gate",
                "proposed_profile_id": "p3-dev-v2-slice-patch-mcp",
                "gate": {"canary_allowed": False, "promotion_ready": False},
                "hard_blockers": ["min_metric_delta_not_met:SHIFT"],
                "official_scores_claimed": False,
            },
            "canary_rows": [
                {
                    "id": "S1-I2-003",
                    "shift_axis": "I",
                    "category": "math",
                    "auto_grade": "numeric_match",
                    "prompt": "Return JSON.",
                }
            ],
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == (
        "2026-06-06.registered-profile-canary-preflight.v1"
    )
    assert payload["status"] == "blocked_by_dev_hard_gate"
    assert payload["canary_execution"]["allowed"] is False
    assert "canary_not_allowed_by_dev_gate" in payload["hard_blockers"]
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_build_registered_profile_canary_result_gate_tool_blocks_failed_canary(
    tmp_path: Path,
) -> None:
    canary_eval = tmp_path / "canary-model-eval.json"
    output = tmp_path / "registered-profile-canary-result-gate.json"
    canary_eval.write_text(
        json.dumps({
            "schema_version": "2026-05-18.smol-worldcup-model-eval.v1",
            "status": "completed",
            "dataset": {"evaluation_split": "canary", "row_count": 2},
            "failure_summary": {
                "failure_count": 1,
                "runtime_error_count": 0,
                "empty_output_count": 0,
            },
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    payload = mcp_service.build_registered_profile_canary_result_gate_tool(
        {
            "registered_profile_canary_execution": {
                "schema_version": "2026-06-06.registered-profile-canary-execution.v1",
                "status": "canary_completed",
                "proposed_profile_id": "p3-dev-v2-slice-patch-mcp",
                "artifacts": {"canary_model_eval": str(canary_eval)},
                "gate": {"canary_completed": True, "promotion_ready": False},
                "hard_blockers": [],
                "official_scores_claimed": False,
            },
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == (
        "2026-06-06.registered-profile-canary-result-gate.v1"
    )
    assert payload["status"] == "blocked_by_canary_result"
    assert payload["gate"]["promotion_ready"] is False
    assert "canary_model_eval_failure_count_gt_max" in payload["hard_blockers"]
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_build_registered_profile_outcome_schedule_tool_routes_passed_canary(
    tmp_path: Path,
) -> None:
    output = tmp_path / "registered-profile-outcome-schedule.json"

    payload = mcp_service.build_registered_profile_outcome_schedule_tool(
        {
            "registered_profile_canary_result_gate": {
                "schema_version": (
                    "2026-06-06.registered-profile-canary-result-gate.v1"
                ),
                "status": "passed_for_promotion",
                "registered_profile_canary_execution_ref": (
                    "registered-profile-canary-execution.json"
                ),
                "proposed_profile_id": "p3-dev-v2-slice-patch-mcp",
                "canary_result": {
                    "artifact_ref": "canary-model-eval.json",
                    "row_count": 2,
                    "failure_count": 0,
                    "runtime_error_count": 0,
                    "empty_output_count": 0,
                    "status": "completed",
                },
                "gate": {
                    "canary_completed": True,
                    "canary_passed": True,
                    "promotion_ready": True,
                },
                "hard_blockers": [],
                "official_scores_claimed": False,
            },
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == (
        "2026-06-06.registered-profile-outcome-schedule.v1"
    )
    assert payload["status"] == "ready_for_promotion_review"
    assert payload["gate"]["scheduler_allows_promotion_review"] is True
    assert payload["outcome_weighting"]["scheduler_weight"] > 0
    assert payload["executes_experiment"] is False
    assert payload["executes_promotion"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_build_optimizer_gate_scheduler_plan_tool_queues_promotion_review(
    tmp_path: Path,
) -> None:
    output = tmp_path / "optimizer-gate-scheduler-plan.json"

    payload = mcp_service.build_optimizer_gate_scheduler_plan_tool(
        {
            "registered_profile_outcome_schedule": {
                "schema_version": (
                    "2026-06-06.registered-profile-outcome-schedule.v1"
                ),
                "status": "ready_for_promotion_review",
                "proposed_profile_id": "p3-dev-v2-slice-patch-mcp",
                "outcome_weighting": {
                    "scheduler_weight": 1,
                    "positive_signals": ["canary_passed"],
                    "negative_signals": [],
                },
                "scheduled_actions": [
                    "review_promotion_boundary",
                    "record_slice_patch_outcome",
                    "await_human_promotion_review",
                ],
                "gate": {
                    "canary_result_consumed": True,
                    "scheduler_allows_promotion_review": True,
                    "promotion_ready": True,
                },
                "hard_blockers": [],
                "official_scores_claimed": False,
            },
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == "2026-06-07.optimizer-gate-scheduler-plan.v1"
    assert payload["status"] == "ready_for_human_promotion_review"
    assert payload["next_runner_action"] == "review_promotion_boundary"
    assert payload["gate"]["promotion_review_queued"] is True
    assert payload["executes_tool"] is False
    assert payload["executes_experiment"] is False
    assert payload["executes_promotion"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_run_optimizer_gate_scheduler_action_tool_builds_runtime_preflight(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "optimizer-gate-scheduler-action"

    payload = mcp_service.run_optimizer_gate_scheduler_action_tool(
        {
            "optimizer_gate_scheduler_plan": {
                "schema_version": "2026-06-07.optimizer-gate-scheduler-plan.v1",
                "status": "needs_model_runtime_preflight",
                "registered_profile_outcome_schedule_ref": "inline",
                "proposed_profile_id": "p3-dev-v2-slice-patch-mcp-runtime",
                "action_queue": [
                    {
                        "name": "build_model_runtime_preflight",
                        "status": "ready_to_build",
                        "reason": (
                            "canary rerun requires ready model runtime preflight"
                        ),
                    }
                ],
                "next_runner_action": "build_model_runtime_preflight",
                "runtime_readiness": {
                    "status": "missing",
                    "model_runtime_ready": False,
                    "hard_blockers": ["model_runtime_preflight_missing"],
                },
                "optimizer_selection": {
                    "available": False,
                    "selected_optimizer": None,
                },
                "gate": {"executes_promotion": False},
                "hard_blockers": ["model_runtime_preflight_missing"],
                "official_scores_claimed": False,
            },
            "model": "qwen/qwen3-8b",
            "base_url": "http://127.0.0.1:1234/v1",
            "output_dir": str(output_dir),
        }
    )

    assert payload["schema_version"] == "2026-06-07.optimizer-gate-scheduler-action.v1"
    assert payload["status"] == "action_completed"
    assert payload["action_name"] == "build_model_runtime_preflight"
    assert payload["action_result"]["schema_version"] == (
        "2026-06-06.model-runtime-preflight.v1"
    )
    assert payload["executes_tool"] is False
    assert payload["executes_experiment"] is False
    assert payload["executes_promotion"] is False
    assert payload["official_scores_claimed"] is False
    assert (output_dir / "optimizer-gate-scheduler-action.json").exists()
    assert (output_dir / "model-runtime-preflight.json").exists()


def test_run_optimizer_gate_scheduler_action_tool_blocks_allowlisted_canary_budget(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "optimizer-gate-scheduler-action"

    payload = mcp_service.run_optimizer_gate_scheduler_action_tool(
        {
            "optimizer_gate_scheduler_plan": {
                "schema_version": "2026-06-07.optimizer-gate-scheduler-plan.v1",
                "status": "scheduler_actions_planned",
                "registered_profile_outcome_schedule_ref": "inline",
                "proposed_profile_id": "p3-dev-v2-mcp-canary",
                "action_queue": [
                    {
                        "name": "run_registered_profile_canary_execution",
                        "status": "ready_to_run_canary_execution",
                        "reason": "ready model runtime preflight is available",
                    }
                ],
                "next_runner_action": "run_registered_profile_canary_execution",
                "runtime_readiness": {
                    "status": "model_runtime_ready",
                    "model_runtime_ready": True,
                    "hard_blockers": [],
                },
                "optimizer_selection": {
                    "available": False,
                    "selected_optimizer": None,
                },
                "gate": {"canary_rerun_ready": True},
                "hard_blockers": [],
                "official_scores_claimed": False,
            },
            "experiment_action_allowlist": [
                "run_registered_profile_canary_execution"
            ],
            "experiment_budget": {"max_experiment_actions": 0},
            "canary_runner_bundle": {
                "schema_version": (
                    "2026-06-11.optimizer-gate-canary-runner-bundle.v1"
                ),
                "status": "ready_for_explicit_canary_runner",
                "proposed_profile_id": "p3-dev-v2-mcp-canary",
                "runner": {"function": "run_registered_profile_canary_execution"},
                "input_bundle": {"execute_canary_flag": True},
                "gate": {"runner_inputs_ready": True},
                "hard_blockers": [],
                "official_scores_claimed": False,
            },
            "output_dir": str(output_dir),
        }
    )

    assert payload["schema_version"] == "2026-06-07.optimizer-gate-scheduler-action.v1"
    assert payload["status"] == "blocked_scheduler_experiment_budget"
    assert payload["budget"]["experiment_actions_consumed"] == 0
    assert payload["stop_reason"] == "budget_exhausted"
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert (output_dir / "optimizer-gate-scheduler-action.json").exists()
    assert (
        output_dir / "optimizer-gate-scheduler-action-output-manifest.json"
    ).exists()


def test_run_optimizer_gate_scheduler_loop_tool_runs_safe_action_and_stops(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "optimizer-gate-scheduler-loop"

    payload = mcp_service.run_optimizer_gate_scheduler_loop_tool(
        {
            "optimizer_gate_scheduler_plan": {
                "schema_version": "2026-06-07.optimizer-gate-scheduler-plan.v1",
                "status": "needs_model_runtime_preflight",
                "registered_profile_outcome_schedule_ref": "inline",
                "proposed_profile_id": "p3-dev-v2-slice-patch-mcp-loop",
                "action_queue": [
                    {
                        "name": "build_model_runtime_preflight",
                        "status": "ready_to_build",
                        "reason": (
                            "canary rerun requires ready model runtime preflight"
                        ),
                    },
                    {
                        "name": "run_registered_profile_canary_execution",
                        "status": "blocked_by_model_runtime_preflight",
                        "reason": (
                            "canary execution requires ready model runtime preflight"
                        ),
                    },
                ],
                "next_runner_action": "build_model_runtime_preflight",
                "runtime_readiness": {
                    "status": "missing",
                    "model_runtime_ready": False,
                    "hard_blockers": ["model_runtime_preflight_missing"],
                },
                "optimizer_selection": {
                    "available": False,
                    "selected_optimizer": None,
                },
                "gate": {"canary_rerun_ready": False},
                "hard_blockers": ["model_runtime_preflight_missing"],
                "official_scores_claimed": False,
            },
            "model": "qwen/qwen3-8b",
            "base_url": "http://127.0.0.1:1234/v1",
            "output_dir": str(output_dir),
        }
    )

    assert payload["schema_version"] == "2026-06-07.optimizer-gate-scheduler-loop.v1"
    assert payload["status"] == "loop_waiting_for_scheduler_refresh"
    assert payload["action_count"] == 1
    assert payload["action_results"][0]["action_name"] == "build_model_runtime_preflight"
    assert payload["next_runner_action"] == "run_registered_profile_canary_execution"
    assert payload["executes_tool"] is False
    assert payload["executes_experiment"] is False
    assert payload["executes_promotion"] is False
    assert payload["official_scores_claimed"] is False
    assert (output_dir / "optimizer-gate-scheduler-loop.json").exists()


def test_build_optimizer_gate_scheduler_handoff_tool_writes_canary_handoff(
    tmp_path: Path,
) -> None:
    output = tmp_path / "optimizer-gate-scheduler-handoff.json"

    payload = mcp_service.build_optimizer_gate_scheduler_handoff_tool(
        {
            "optimizer_gate_scheduler_loop": {
                "schema_version": "2026-06-07.optimizer-gate-scheduler-loop.v1",
                "status": "loop_stopped_unsupported_action",
                "optimizer_gate_scheduler_plan_ref": "refreshed-plan.json",
                "proposed_profile_id": "p3-dev-v2-slice-patch-runtime-blocked",
                "action_count": 0,
                "action_results": [],
                "refreshed_scheduler_plan_count": 0,
                "refreshed_scheduler_plans": [],
                "artifact_refs": [],
                "stop_reason": "scheduler_action_execution_not_supported",
                "next_runner_action": "run_registered_profile_canary_execution",
                "recommended_next_action": "manual_review_or_explicit_runner",
                "hard_blockers": ["scheduler_action_execution_not_supported"],
                "gate": {
                    "safe_planning_actions_executed": 0,
                    "executes_experiment": False,
                    "executes_promotion": False,
                },
                "claim_boundary": "optimizer/gate scheduler loop only",
                "executes_tool": False,
                "executes_experiment": False,
                "executes_promotion": False,
                "official_scores_claimed": False,
            },
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == "2026-06-07.optimizer-gate-scheduler-handoff.v1"
    assert payload["status"] == "ready_for_explicit_canary_runner"
    assert payload["runner"]["function"] == "run_registered_profile_canary_execution"
    assert payload["executes_experiment"] is False
    assert payload["executes_promotion"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_build_optimizer_gate_canary_runner_bundle_tool_writes_bundle(
    tmp_path: Path,
) -> None:
    output = tmp_path / "optimizer-gate-canary-runner-bundle.json"

    payload = mcp_service.build_optimizer_gate_canary_runner_bundle_tool(
        {
            "optimizer_gate_scheduler_handoff": {
                "schema_version": "2026-06-07.optimizer-gate-scheduler-handoff.v1",
                "status": "ready_for_explicit_canary_runner",
                "optimizer_gate_scheduler_loop_ref": "optimizer-gate-scheduler-loop.json",
                "handoff_type": "explicit_canary_runner_handoff",
                "next_runner_action": "run_registered_profile_canary_execution",
                "runner": {"function": "run_registered_profile_canary_execution"},
                "required_inputs": [
                    "registered_profile_execution_run",
                    "registered_profile",
                    "canary_rows",
                    "model_runtime_preflight",
                    "execute_canary_flag",
                ],
                "manual_review_required": True,
                "claim_boundary": "optimizer/gate scheduler handoff only",
                "official_scores_claimed": False,
            },
            "registered_profile_execution_run": {
                "status": "dev_completed",
                "proposed_profile_id": "p3-dev-v2-slice-patch-runtime-ready",
                "gate": {"canary_allowed": True},
                "hard_blockers": [],
                "official_scores_claimed": False,
            },
            "registered_profile": {
                "proposed_profile_id": "p3-dev-v2-slice-patch-runtime-ready",
                "official_scores_claimed": False,
            },
            "canary_rows": [
                {"id": "canary-1", "question": "Who won?", "answer": "France"}
            ],
            "model_runtime_preflight": {
                "status": "ready_for_model_eval",
                "gate": {"model_runtime_ready": True},
                "hard_blockers": [],
                "official_scores_claimed": False,
            },
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == "2026-06-11.optimizer-gate-canary-runner-bundle.v1"
    assert payload["status"] == "ready_for_explicit_canary_runner"
    assert payload["gate"]["runner_inputs_ready"] is True
    assert payload["input_bundle"]["canary_row_count"] == 1
    assert payload["executes_tool"] is False
    assert payload["executes_experiment"] is False
    assert payload["executes_promotion"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_run_optimizer_gate_canary_runner_bundle_tool_blocks_unready_bundle(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "optimizer-gate-canary-runner-execution"

    payload = mcp_service.run_optimizer_gate_canary_runner_bundle_tool(
        {
            "optimizer_gate_canary_runner_bundle": {
                "schema_version": "2026-06-11.optimizer-gate-canary-runner-bundle.v1",
                "status": "blocked_missing_runner_inputs",
                "proposed_profile_id": "p3-dev-v2-unready-canary",
                "runner": {"function": "run_registered_profile_canary_execution"},
                "input_bundle": {
                    "registered_profile_execution_run_ref": None,
                    "registered_profile_ref": None,
                    "canary_rows_ref": None,
                    "model_runtime_preflight_ref": None,
                    "execute_canary_flag": True,
                    "canary_row_count": 0,
                },
                "gate": {"runner_inputs_ready": False},
                "hard_blockers": ["canary_rows_missing"],
                "official_scores_claimed": False,
            },
            "output_dir": str(output_dir),
        }
    )

    assert payload["schema_version"] == (
        "2026-06-11.optimizer-gate-canary-runner-execution.v1"
    )
    assert payload["status"] == "blocked_by_canary_runner_bundle"
    assert payload["gate"]["runner_inputs_ready"] is False
    assert "canary_rows_missing" in payload["hard_blockers"]
    assert payload["executes_tool"] is False
    assert payload["executes_experiment"] is False
    assert payload["executes_promotion"] is False
    assert payload["official_scores_claimed"] is False
    assert (output_dir / "optimizer-gate-canary-runner-execution.json").exists()


def test_build_optimizer_gate_promotion_review_queue_tool_writes_queue(
    tmp_path: Path,
) -> None:
    output = tmp_path / "optimizer-gate-promotion-review-queue.json"

    payload = mcp_service.build_optimizer_gate_promotion_review_queue_tool(
        {
            "optimizer_gate_scheduler_handoff": {
                "status": "waiting_for_human_promotion_review",
                "proposed_profile_id": "p3-dev-v2-clean-canary",
                "handoff_type": "human_promotion_review_handoff",
                "next_runner_action": "await_human_promotion_review",
                "hard_blockers": ["scheduler_action_execution_not_supported"],
                "official_scores_claimed": False,
            },
            "canary_result_gate": {
                "status": "passed_for_promotion",
                "proposed_profile_id": "p3-dev-v2-clean-canary",
                "gate": {
                    "canary_completed": True,
                    "canary_passed": True,
                    "promotion_ready": True,
                },
                "hard_blockers": [],
                "official_scores_claimed": False,
            },
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == (
        "2026-06-11.optimizer-gate-promotion-review-queue.v1"
    )
    assert payload["status"] == "waiting_for_human_promotion_review"
    assert payload["gate"]["review_queue_ready"] is True
    assert payload["review_queue"][0]["review_type"] == "promotion_boundary"
    assert payload["executes_tool"] is False
    assert payload["executes_experiment"] is False
    assert payload["executes_promotion"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_build_optimizer_gate_human_promotion_approval_tool_writes_decision(
    tmp_path: Path,
) -> None:
    output = tmp_path / "optimizer-gate-human-promotion-approval.json"

    payload = mcp_service.build_optimizer_gate_human_promotion_approval_tool(
        {
            "promotion_review_queue": {
                "schema_version": (
                    "2026-06-11.optimizer-gate-promotion-review-queue.v1"
                ),
                "status": "waiting_for_human_promotion_review",
                "proposed_profile_id": "p3-dev-v2-clean-canary",
                "review_queue": [
                    {
                        "item_id": "p3-dev-v2-clean-canary-promotion-review",
                        "review_type": "promotion_boundary",
                        "status": "waiting_for_human_review",
                        "required_decisions": [
                            "confirm_canary_result_gate",
                            "confirm_claim_boundary",
                            "approve_or_reject_local_promotion_candidate",
                        ],
                    }
                ],
                "gate": {
                    "review_queue_ready": True,
                    "promotion_ready": True,
                    "human_approval_required": True,
                },
                "hard_blockers": [],
                "official_scores_claimed": False,
            },
            "approved": True,
            "approved_by": "unit-test-reviewer",
            "reviewed_at": "2026-06-15T00:00:00Z",
            "decision_notes": "Fixture review accepted.",
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == (
        "2026-06-15.optimizer-gate-human-promotion-approval.v1"
    )
    assert payload["status"] == "approved_for_local_promotion_action"
    assert payload["gate"]["human_approved"] is True
    assert payload["executes_promotion"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_run_optimizer_gate_local_promotion_action_tool_records_action(
    tmp_path: Path,
) -> None:
    output = tmp_path / "optimizer-gate-local-promotion-action.json"
    registry = tmp_path / "local-profile-registry.json"
    rollback = tmp_path / "local-profile-registry-rollback.json"
    audit_log = tmp_path / "local-profile-registry-audit.jsonl"
    registry.write_text(
        json.dumps(
            {
                "schema_version": "2026-06-16.local-profile-registry.v1",
                "active_profile_id": "base-profile",
                "profiles": {
                    "base-profile": {
                        "profile_id": "base-profile",
                        "status": "active",
                    },
                    "p3-dev-v2-clean-canary": {
                        "profile_id": "p3-dev-v2-clean-canary",
                        "status": "candidate",
                    },
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    payload = mcp_service.run_optimizer_gate_local_promotion_action_tool(
        {
            "human_promotion_approval": {
                "schema_version": (
                    "2026-06-15.optimizer-gate-human-promotion-approval.v1"
                ),
                "status": "approved_for_local_promotion_action",
                "proposed_profile_id": "p3-dev-v2-clean-canary",
                "review": {"approved": True, "approved_by": "unit-test-reviewer"},
                "gate": {"human_approved": True, "promotion_ready": True},
                "hard_blockers": [],
                "official_scores_claimed": False,
            },
            "execute_promotion": True,
            "promoted_by": "unit-test-promoter",
            "promoted_at": "2026-06-15T00:00:00Z",
            "profile_registry_file": str(registry),
            "registry_output_path": str(registry),
            "rollback_output_path": str(rollback),
            "audit_log_path": str(audit_log),
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == (
        "2026-06-15.optimizer-gate-local-promotion-action.v1"
    )
    assert payload["status"] == "local_promotion_recorded"
    assert payload["gate"]["promotion_executed"] is True
    assert payload["executes_promotion"] is True
    assert payload["official_scores_claimed"] is False
    assert payload["write_target"]["path"] == str(registry)
    assert json.loads(registry.read_text(encoding="utf-8"))["active_profile_id"] == (
        "p3-dev-v2-clean-canary"
    )
    assert rollback.exists()
    assert audit_log.exists()
    assert output.exists()


def test_run_optimizer_gate_local_promotion_rollback_tool_restores_registry(
    tmp_path: Path,
) -> None:
    registry = tmp_path / "local-profile-registry.json"
    output = tmp_path / "optimizer-gate-local-promotion-rollback.json"
    registry.write_text(
        json.dumps(
            {
                "schema_version": "2026-06-16.local-profile-registry.v1",
                "active_profile_id": "p3-dev-v2-clean-canary",
                "profiles": {
                    "base-profile": {"profile_id": "base-profile", "status": "active"},
                    "p3-dev-v2-clean-canary": {
                        "profile_id": "p3-dev-v2-clean-canary",
                        "status": "active",
                    },
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    payload = mcp_service.run_optimizer_gate_local_promotion_rollback_tool(
        {
            "rollback_record": {
                "schema_version": (
                    "2026-06-16.optimizer-gate-local-promotion-rollback.v1"
                ),
                "status": "rollback_ready",
                "target": {"kind": "local_profile_registry", "path": str(registry)},
                "restore_registry": {
                    "schema_version": "2026-06-16.local-profile-registry.v1",
                    "active_profile_id": "base-profile",
                    "profiles": {
                        "base-profile": {
                            "profile_id": "base-profile",
                            "status": "active",
                        },
                        "p3-dev-v2-clean-canary": {
                            "profile_id": "p3-dev-v2-clean-canary",
                            "status": "candidate",
                        },
                    },
                    "official_scores_claimed": False,
                },
                "official_scores_claimed": False,
            },
            "rolled_back_by": "unit-test-operator",
            "rolled_back_at": "2026-06-16T00:05:00Z",
            "output_path": str(output),
        }
    )

    assert payload["status"] == "local_registry_rollback_applied"
    assert payload["executes_rollback"] is True
    assert payload["official_scores_claimed"] is False
    assert json.loads(registry.read_text(encoding="utf-8"))["active_profile_id"] == (
        "base-profile"
    )
    assert output.exists()


def test_optimizer_gate_official_claim_tools_require_public_verifier(
    tmp_path: Path,
) -> None:
    submission_output = tmp_path / "optimizer-gate-official-submission.json"
    verifier_output = tmp_path / "optimizer-gate-public-result-verifier.json"
    claim_output = tmp_path / "optimizer-gate-official-claim.json"

    submission = mcp_service.build_optimizer_gate_official_submission_tool(
        {
            "local_promotion_action": {
                "schema_version": (
                    "2026-06-15.optimizer-gate-local-promotion-action.v1"
                ),
                "status": "local_promotion_recorded",
                "proposed_profile_id": "p3-dev-v2-clean-canary",
                "write_target": {
                    "kind": "local_profile_registry",
                    "path": "local-profile-registry.json",
                    "written": True,
                },
                "gate": {"promotion_executed": True},
                "executes_promotion": True,
                "official_scores_claimed": False,
            },
            "benchmark_id": "smol-worldcup",
            "submission_id": "official-submission-001",
            "public_url": "https://example.test/results/official-submission-001",
            "submitted_by": "unit-test-submitter",
            "submitted_at": "2026-06-16T00:10:00Z",
            "output_path": str(submission_output),
        }
    )
    assert submission["status"] == "official_submission_recorded"
    assert submission["official_scores_claimed"] is False

    verifier = mcp_service.verify_optimizer_gate_public_result_tool(
        {
            "official_submission": submission,
            "public_result": {
                "submission_id": "official-submission-001",
                "public_url": "https://example.test/results/official-submission-001",
                "published_at": "2026-06-16T00:20:00Z",
                "metrics": {"SHIFT": 83.3},
                "denominator": {"row_count": 100},
            },
            "output_path": str(verifier_output),
        }
    )
    assert verifier["status"] == "public_result_verified"
    assert verifier["official_scores_claimed"] is False

    claim = mcp_service.build_optimizer_gate_official_claim_tool(
        {
            "public_result_verifier": verifier,
            "claim_id": "official-claim-001",
            "output_path": str(claim_output),
        }
    )
    assert claim["status"] == "official_claim_verified"
    assert claim["official_scores_claimed"] is True
    assert claim["claim"]["submission_id"] == "official-submission-001"


def test_optimizer_gate_external_submission_action_tool_posts_and_verifies_html(
    tmp_path: Path,
) -> None:
    action_output = tmp_path / "optimizer-gate-external-submission-action.json"
    payload_file = tmp_path / "submission-payload.json"
    fetch_output = tmp_path / "optimizer-gate-public-result-fetch.json"
    verifier_output = tmp_path / "optimizer-gate-public-result-verifier.json"
    payload_file.write_text(
        json.dumps({"artifact_uri": "s3://example/submission.jsonl"}),
        encoding="utf-8",
    )
    public_result_html = tmp_path / "public-result.html"
    public_result_html.write_text(
        """
        <html><body>
        <script type="application/json" id="optimizer-gate-public-result">
        {
          "submission_id": "external-submission-001",
          "public_url": "https://benchmark.example/results/external-submission-001",
          "published_at": "2026-06-16T00:20:00Z",
          "metrics": {"SHIFT": 85.1},
          "denominator": {"row_count": 100}
        }
        </script>
        </body></html>
        """,
        encoding="utf-8",
    )
    result_server, result_thread = _serve_directory(tmp_path)
    result_url = f"http://127.0.0.1:{result_server.server_address[1]}/public-result.html"
    submission_server, submission_thread, received = _serve_submission_endpoint(
        {
            "submission_id": "external-submission-001",
            "public_url": "https://benchmark.example/results/external-submission-001",
            "submitted_at": "2026-06-16T00:10:00Z",
            "raw_response_id": "response-001",
        }
    )
    submission_url = (
        f"http://127.0.0.1:{submission_server.server_address[1]}/submit"
    )
    try:
        action = mcp_service.run_optimizer_gate_external_submission_action_tool(
            {
                "local_promotion_action": {
                    "schema_version": (
                        "2026-06-15.optimizer-gate-local-promotion-action.v1"
                    ),
                    "status": "local_promotion_recorded",
                    "proposed_profile_id": "p3-dev-v2-clean-canary",
                    "write_target": {
                        "kind": "local_profile_registry",
                        "path": "local-profile-registry.json",
                        "written": True,
                    },
                    "gate": {"promotion_executed": True},
                    "executes_promotion": True,
                    "official_scores_claimed": False,
                },
                "benchmark_id": "smol-worldcup",
                "submission_url": submission_url,
                "submission_payload_file": str(payload_file),
                "submitted_by": "unit-test-submitter",
                "execute_submission": True,
                "timeout_seconds": 5,
                "output_path": str(action_output),
            }
        )
        fetched = mcp_service.fetch_optimizer_gate_public_result_tool(
            {
                "public_result_url": result_url,
                "timeout_seconds": 5,
                "output_path": str(fetch_output),
            }
        )
        verifier = mcp_service.verify_optimizer_gate_public_result_tool(
            {
                "official_submission": action,
                "public_result": fetched,
                "output_path": str(verifier_output),
            }
        )
    finally:
        submission_server.shutdown()
        submission_server.server_close()
        submission_thread.join(timeout=5)
        result_server.shutdown()
        result_server.server_close()
        result_thread.join(timeout=5)

    assert received == [{"artifact_uri": "s3://example/submission.jsonl"}]
    assert action["status"] == "external_submission_submitted"
    assert action["submission"]["submission_id"] == "external-submission-001"
    assert action["gate"]["external_submission_executed"] is True
    assert action["official_scores_claimed"] is False
    assert fetched["status"] == "public_result_fetched"
    assert fetched["source"]["parser"] == "html_embedded_json"
    assert verifier["status"] == "public_result_verified"
    assert verifier["official_submission_source"]["kind"] == (
        "external_submission_action_artifact"
    )
    assert verifier["gate"]["public_result_verified"] is True


def test_optimizer_gate_public_result_fetch_tool_uses_http_url(
    tmp_path: Path,
) -> None:
    submission_output = tmp_path / "optimizer-gate-official-submission.json"
    fetch_output = tmp_path / "optimizer-gate-public-result-fetch.json"
    verifier_output = tmp_path / "optimizer-gate-public-result-verifier.json"
    remote_result = tmp_path / "public-result-live.json"
    remote_result.write_text(
        json.dumps(
            {
                "submission_id": "official-submission-001",
                "public_url": "https://example.test/results/official-submission-001",
                "published_at": "2026-06-16T00:20:00Z",
                "metrics": {"SHIFT": 83.3},
                "denominator": {"row_count": 100},
            }
        ),
        encoding="utf-8",
    )
    server, thread = _serve_directory(tmp_path)
    public_result_url = (
        f"http://127.0.0.1:{server.server_address[1]}/public-result-live.json"
    )
    try:
        submission = mcp_service.build_optimizer_gate_official_submission_tool(
            {
                "local_promotion_action": {
                    "schema_version": (
                        "2026-06-15.optimizer-gate-local-promotion-action.v1"
                    ),
                    "status": "local_promotion_recorded",
                    "proposed_profile_id": "p3-dev-v2-clean-canary",
                    "write_target": {
                        "kind": "local_profile_registry",
                        "path": "local-profile-registry.json",
                        "written": True,
                    },
                    "gate": {"promotion_executed": True},
                    "executes_promotion": True,
                    "official_scores_claimed": False,
                },
                "benchmark_id": "smol-worldcup",
                "submission_id": "official-submission-001",
                "public_url": "https://example.test/results/official-submission-001",
                "submitted_by": "unit-test-submitter",
                "submitted_at": "2026-06-16T00:10:00Z",
                "output_path": str(submission_output),
            }
        )
        fetched = mcp_service.fetch_optimizer_gate_public_result_tool(
            {
                "public_result_url": public_result_url,
                "timeout_seconds": 5,
                "output_path": str(fetch_output),
            }
        )
        assert fetched["status"] == "public_result_fetched"
        assert fetched["source"]["public_result_url"] == public_result_url
        assert fetched["executes_tool"] is True
        assert fetched["official_scores_claimed"] is False

        verifier = mcp_service.verify_optimizer_gate_public_result_tool(
            {
                "official_submission": submission,
                "public_result": fetched,
                "output_path": str(verifier_output),
            }
        )
        assert verifier["status"] == "public_result_verified"
        assert verifier["public_result_source"]["kind"] == (
            "public_result_fetch_artifact"
        )
        assert verifier["public_result_source"]["public_result_url"] == public_result_url
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_run_optimizer_gate_executable_loop_tool_runs_bounded_loop(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "optimizer-gate-executable-loop"

    payload = mcp_service.run_optimizer_gate_executable_loop_tool(
        {
            "canary_result_gate": {
                "schema_version": (
                    "2026-06-06.registered-profile-canary-result-gate.v1"
                ),
                "status": "blocked_by_canary_result",
                "proposed_profile_id": "p3-loop-previous",
                "canary_result": {
                    "status": "completed",
                    "row_count": 2,
                    "failure_count": 2,
                    "runtime_error_count": 0,
                    "empty_output_count": 0,
                },
                "gate": {
                    "canary_completed": True,
                    "canary_passed": False,
                    "promotion_ready": False,
                },
                "hard_blockers": ["canary_model_eval_failure_count_gt_max"],
                "official_scores_claimed": False,
            },
            "slice_repair_context": {
                "schema_version": "2026-06-04.slice-repair-context.v1",
                "recommended_patch_contract": {
                    "module_id": "multilingual_variant_explanation",
                    "section_id": "output_format",
                    "edit_scope": "single_section",
                    "based_on_slices": ["dev/category/multilingual_pt"],
                    "target_slice": "multilingual_pt",
                    "before_text": "return concise JSON",
                    "protected_slices": ["multilingual_th"],
                    "protected_sections": ["role"],
                },
                "official_scores_claimed": False,
            },
            "candidate_optimizers": ["manual-template"],
            "base_profile_id": "p3-dev-v2",
            "proposed_profile_prefix": "p3-loop-next",
            "max_iterations": 1,
            "max_candidates": 1,
            "output_dir": str(output_dir),
        }
    )

    assert payload["schema_version"] == "2026-06-16.optimizer-gate-executable-loop.v1"
    assert payload["status"] == "stopped_at_human_review_boundary"
    assert payload["stop_reason"] == "human_review_boundary"
    assert payload["official_scores_claimed"] is False
    assert (output_dir / "optimizer-gate-executable-loop.json").exists()


def test_run_optimizer_gate_executable_loop_tool_passes_dev_gate_args(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run_optimizer_gate_executable_loop(**kwargs):
        captured.update(kwargs)
        return {
            "schema_version": "2026-06-16.optimizer-gate-executable-loop.v1",
            "status": "stopped_gate_blocked",
            "official_scores_claimed": False,
        }

    monkeypatch.setattr(
        mcp_service,
        "run_optimizer_gate_executable_loop",
        fake_run_optimizer_gate_executable_loop,
    )

    payload = mcp_service.run_optimizer_gate_executable_loop_tool(
        {
            "canary_result_gate": {
                "schema_version": (
                    "2026-06-06.registered-profile-canary-result-gate.v1"
                ),
                "status": "blocked_by_canary_result",
                "official_scores_claimed": False,
            },
            "slice_repair_context": {
                "schema_version": "2026-06-04.slice-repair-context.v1",
                "official_scores_claimed": False,
            },
            "auto_approve_registration": True,
            "approved_by": "mcp-loop-test",
            "prompt_leakage_rows": [{"id": "S1-I2-003"}],
            "prompt_leakage_audit": {
                "schema_version": "2026-06-05.prompt-leakage-audit.v1",
                "status": "passed",
            },
            "target_smoke": {
                "schema_version": "2026-05-18.smol-worldcup-model-eval.v1",
                "status": "completed",
            },
            "dev_model_eval": {
                "schema_version": "2026-05-18.smol-worldcup-model-eval.v1",
                "status": "completed",
            },
            "dev_baseline_eval": {
                "schema_version": "2026-05-18.smol-worldcup-model-eval.v1",
                "status": "completed",
            },
            "dev_gate_source": {
                "schema_version": "2026-06-04.slice-eval-matrix.v1",
                "status": "completed",
            },
            "model_runtime_preflight": {
                "schema_version": "2026-06-06.model-runtime-preflight.v1",
                "status": "model_runtime_ready",
            },
            "execute_model_eval": True,
            "target_smoke_rows": [{"id": "S1-I2-003"}],
            "dev_model_eval_rows": [{"id": "S1-I1-004"}],
            "execute_canary_runner": True,
            "canary_rows": [{"id": "S1-C1-001"}],
            "model_eval_model": "qwen/qwen3-8b",
            "model_eval_base_url": "http://127.0.0.1:1234/v1",
            "model_eval_model_provider": "openai-compatible",
            "model_eval_api_key_env": "QWEN_API_KEY",
            "model_eval_timeout_seconds": 3,
            "model_eval_temperature": 0.1,
            "model_eval_max_tokens": 64,
            "model_eval_judge_mode": "exact",
            "min_canary_row_count": 2,
            "max_canary_failure_count": 0,
            "max_canary_runtime_error_count": 0,
            "max_canary_empty_output_count": 0,
            "output_dir": str(tmp_path / "optimizer-gate-executable-loop"),
        }
    )

    assert payload["status"] == "stopped_gate_blocked"
    assert captured["auto_approve_registration"] is True
    assert captured["approved_by"] == "mcp-loop-test"
    assert captured["prompt_leakage_rows"] == [{"id": "S1-I2-003"}]
    assert captured["prompt_leakage_audit"]["status"] == "passed"
    assert captured["target_smoke"]["status"] == "completed"
    assert captured["dev_model_eval"]["status"] == "completed"
    assert captured["dev_baseline_eval"]["status"] == "completed"
    assert captured["dev_gate_source"]["schema_version"] == (
        "2026-06-04.slice-eval-matrix.v1"
    )
    assert captured["model_runtime_preflight"]["status"] == "model_runtime_ready"
    assert captured["execute_model_eval"] is True
    assert captured["target_smoke_rows"] == [{"id": "S1-I2-003"}]
    assert captured["dev_model_eval_rows"] == [{"id": "S1-I1-004"}]
    assert captured["execute_canary_runner"] is True
    assert captured["canary_rows"] == [{"id": "S1-C1-001"}]
    assert captured["model_eval_model"] == "qwen/qwen3-8b"
    assert captured["model_eval_base_url"] == "http://127.0.0.1:1234/v1"
    assert captured["model_eval_model_provider"] == "openai-compatible"
    assert captured["model_eval_api_key_env"] == "QWEN_API_KEY"
    assert captured["model_eval_timeout_seconds"] == 3
    assert captured["model_eval_temperature"] == 0.1
    assert captured["model_eval_max_tokens"] == 64
    assert captured["model_eval_judge_mode"] == "exact"
    assert captured["min_canary_row_count"] == 2
    assert captured["max_canary_failure_count"] == 0
    assert captured["max_canary_runtime_error_count"] == 0
    assert captured["max_canary_empty_output_count"] == 0


def test_build_model_runtime_preflight_tool_writes_non_executing_artifact(
    tmp_path: Path,
) -> None:
    output = tmp_path / "model-runtime-preflight.json"

    payload = mcp_service.build_model_runtime_preflight_tool(
        {
            "model": "qwen/qwen3-8b",
            "base_url": "http://127.0.0.1:1234/v1",
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == "2026-06-06.model-runtime-preflight.v1"
    assert payload["status"] == "needs_model_runtime_probe"
    assert payload["probe"]["execute_probe"] is False
    assert payload["probe"]["no_think_applied"] is True
    assert "model_runtime_probe_not_executed" in payload["hard_blockers"]
    assert payload["executes_tool"] is False
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_run_registered_profile_execution_tool_passes_explicit_model_eval_args(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run_registered_profile_execution(**kwargs):
        captured.update(kwargs)
        return {
            "schema_version": "2026-06-05.registered-profile-execution-run.v1",
            "status": "blocked_missing_pre_execution_artifacts",
            "official_scores_claimed": False,
        }

    monkeypatch.setattr(
        mcp_service,
        "run_registered_profile_execution",
        fake_run_registered_profile_execution,
    )

    payload = mcp_service.run_registered_profile_execution_tool(
        {
            "registration_plan": {
                "schema_version": "2026-06-05.prompt-profile-registration-plan.v1",
                "proposed_profile_id": "p3-dev-v2-slice-patch-mcp-exec",
                "official_scores_claimed": False,
            },
            "execute_model_eval": True,
            "target_smoke_rows": [{"id": "S1-I2-003"}],
            "dev_model_eval_rows": [{"id": "S1-I1-004"}],
            "dev_baseline_eval": {
                "schema_version": "2026-05-18.smol-worldcup-model-eval.v1",
                "status": "completed",
                "official_scores_claimed": False,
            },
            "dev_gate_source": {
                "schema_version": "2026-06-04.slice-eval-matrix.v1",
                "status": "completed",
                "official_scores_claimed": False,
            },
            "model_runtime_preflight": {
                "schema_version": "2026-06-06.model-runtime-preflight.v1",
                "status": "model_runtime_ready",
                "runtime": {
                    "provider": "openai-compatible",
                    "model": "qwen/qwen3-8b",
                    "base_url": "http://127.0.0.1:1234/v1",
                },
                "gate": {"model_runtime_ready": True, "canary_allowed": True},
                "hard_blockers": [],
                "official_scores_claimed": False,
            },
            "model_eval_model": "qwen/qwen3-8b",
            "model_eval_base_url": "http://127.0.0.1:1234/v1",
            "model_eval_timeout_seconds": 3,
            "output_dir": str(tmp_path / "registered-profile-execution-run"),
        }
    )

    assert payload["status"] == "blocked_missing_pre_execution_artifacts"
    assert captured["execute_model_eval"] is True
    assert captured["target_smoke_rows"] == [{"id": "S1-I2-003"}]
    assert captured["dev_model_eval_rows"] == [{"id": "S1-I1-004"}]
    assert captured["dev_baseline_eval"]["status"] == "completed"
    assert captured["dev_gate_source"]["schema_version"] == (
        "2026-06-04.slice-eval-matrix.v1"
    )
    assert captured["model_runtime_preflight"]["status"] == "model_runtime_ready"
    assert captured["model_eval_model"] == "qwen/qwen3-8b"
    assert captured["model_eval_base_url"] == "http://127.0.0.1:1234/v1"
    assert captured["model_eval_timeout_seconds"] == 3


def test_run_registered_profile_canary_execution_tool_passes_model_runtime_preflight(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_run_registered_profile_canary_execution(**kwargs):
        captured.update(kwargs)
        return {
            "schema_version": "2026-06-06.registered-profile-canary-execution.v1",
            "status": "blocked_model_runtime_preflight",
            "official_scores_claimed": False,
        }

    monkeypatch.setattr(
        mcp_service,
        "run_registered_profile_canary_execution",
        fake_run_registered_profile_canary_execution,
    )

    payload = mcp_service.run_registered_profile_canary_execution_tool(
        {
            "registered_profile_execution_run": {
                "schema_version": "2026-06-05.registered-profile-execution-run.v1",
                "status": "ready_for_canary_execution",
                "proposed_profile_id": "p3-dev-v2-slice-patch-mcp-canary",
                "gate": {"canary_allowed": True, "promotion_ready": False},
                "hard_blockers": [],
                "official_scores_claimed": False,
            },
            "registered_profile": {
                "schema_version": "2026-06-05.prompt-profile-registration.v1",
                "proposed_profile_id": "p3-dev-v2-slice-patch-mcp-canary",
                "official_scores_claimed": False,
            },
            "execute_canary": True,
            "canary_rows": [{"id": "S1-I2-003"}],
            "model_runtime_preflight": {
                "schema_version": "2026-06-06.model-runtime-preflight.v1",
                "status": "model_runtime_ready",
                "runtime": {
                    "provider": "openai-compatible",
                    "model": "qwen/qwen3-8b",
                    "base_url": "http://127.0.0.1:1234/v1",
                },
                "gate": {"model_runtime_ready": True, "canary_allowed": True},
                "hard_blockers": [],
                "official_scores_claimed": False,
            },
            "output_dir": str(tmp_path / "registered-profile-canary-execution"),
        }
    )

    assert payload["status"] == "blocked_model_runtime_preflight"
    assert captured["execute_canary"] is True
    assert captured["model_runtime_preflight"]["status"] == "model_runtime_ready"
    assert captured["canary_rows"] == [{"id": "S1-I2-003"}]


def test_register_prompt_profile_from_plan_tool_writes_registration_artifact(
    tmp_path: Path,
) -> None:
    output = tmp_path / "prompt-profile-registration.json"
    payload = mcp_service.register_prompt_profile_from_plan_tool(
        {
            "registration_plan": {
                "schema_version": "2026-06-05.prompt-profile-registration-plan.v1",
                "status": "ready_for_profile_registration_review",
                "benchmark_adapter": {"benchmark_id": "smol_worldcup"},
                "materialization_ref": "inline",
                "base_profile_id": "p3-system-fixture",
                "proposed_profile_id": "p3-system-fixture-slice-patch-001",
                "patch_id": "slice-patch-001",
                "materialized_change": {
                    "module_id": "multilingual_variant_explanation",
                    "section_id": "output_format",
                    "change_surface": "prompt_section",
                    "edit_scope": "single_section",
                    "before_text": "return concise JSON",
                    "after_text": "return concise JSON with locale evidence",
                    "protected_slices": ["multilingual_tr"],
                    "protected_sections": ["role"],
                },
                "registry_patch": {
                    "operation": "add_prompt_profile",
                    "target_profile_id": "p3-system-fixture-slice-patch-001",
                    "base_profile_id": "p3-system-fixture",
                },
                "required_pre_execution_checks": [],
                "gate_constraints": {"canary_allowed_before_dev_gate": False},
                "claim_boundary": "review-only",
                "official_scores_claimed": False,
            },
            "approved": True,
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == "2026-06-05.prompt-profile-registration.v1"
    assert payload["status"] == "registered"
    assert payload["registered_profile"]["registered"] is True
    assert payload["registry_entry"]["profile_id"] == (
        "p3-system-fixture-slice-patch-001"
    )
    assert payload["executes_experiment"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_gate_policy_tools_write_benchmark_agnostic_input_and_decision(
    tmp_path: Path,
) -> None:
    gate_input_path = tmp_path / "gate-policy-input.json"
    gate_decision_path = tmp_path / "gate-policy-decision.json"

    gate_input = mcp_service.build_gate_policy_input_tool(
        {
            "policy_id": "slice-dev-hard-gate",
            "task_family": "generic-fixture",
            "split": "dev",
            "metric_table": [
                {"metric": "SHIFT", "baseline": 80.0, "candidate": 75.0},
            ],
            "slice_table": [
                {
                    "dimension": "category",
                    "slice_name": "locale_bn",
                    "baseline": 50.0,
                    "candidate": 42.5,
                }
            ],
            "output_path": str(gate_input_path),
        }
    )

    assert gate_input["schema_version"] == "2026-06-05.gate-policy-input.v1"
    assert gate_input["metric_delta"]["SHIFT"] == -5.0
    assert gate_input["official_scores_claimed"] is False
    assert gate_input_path.exists()

    decision = mcp_service.evaluate_gate_policy_tool(
        {
            "gate_input_file": str(gate_input_path),
            "output_path": str(gate_decision_path),
        }
    )

    assert decision["schema_version"] == "2026-06-05.gate-policy-decision.v1"
    assert decision["status"] == "blocked"
    assert decision["gate"]["canary_allowed"] is False
    assert decision["official_scores_claimed"] is False
    assert gate_decision_path.exists()


def test_gate_policy_input_tool_passes_quality_constraints(tmp_path: Path) -> None:
    gate_input_path = tmp_path / "gate-policy-input.json"

    gate_input = mcp_service.build_gate_policy_input_tool(
        {
            "policy_id": "slice-dev-hard-gate",
            "task_family": "generic-fixture",
            "split": "dev",
            "metric_table": [
                {"metric": "SHIFT", "baseline": 0.0, "candidate": 0.0},
            ],
            "slice_table": [
                {
                    "dimension": "category",
                    "slice_name": "math",
                    "baseline": 0.0,
                    "candidate": 0.0,
                }
            ],
            "quality_constraints": {
                "min_metric_delta": {"SHIFT": 0.000001},
                "min_slice_score_percent": 1.0,
            },
            "execution_quality": {
                "target_smoke": {"failure_count": 0, "runtime_error_count": 0},
                "dev_model_eval": {"runtime_error_count": 0},
            },
            "output_path": str(gate_input_path),
        }
    )

    assert "min_metric_delta_not_met:SHIFT" in gate_input["hard_blockers"]
    assert "min_slice_score_percent_not_met" in gate_input["hard_blockers"]
    assert gate_input["quality_checks"]["passed"] is False
    assert gate_input_path.exists()


def test_gate_policy_composition_tool_blocks_when_any_gate_blocks(
    tmp_path: Path,
) -> None:
    output = tmp_path / "gate-policy-composition.json"

    payload = mcp_service.build_gate_policy_composition_tool(
        {
            "decisions": [
                {
                    "schema_version": "2026-06-05.gate-policy-decision.v1",
                    "status": "passed_for_canary",
                    "policy_id": "slice-dev-hard-gate",
                    "split": "dev",
                    "gate": {
                        "canary_allowed": True,
                        "promotion_ready": False,
                    },
                    "hard_blockers": [],
                    "official_scores_claimed": False,
                },
                {
                    "schema_version": "2026-06-05.slice-variance-gate-decision.v1",
                    "status": "blocked",
                    "policy_id": "paired-repeat-variance-gate",
                    "split": "dev",
                    "gate": {
                        "canary_allowed": False,
                        "promotion_ready": False,
                    },
                    "hard_blockers": ["stable_slice_regression"],
                    "stable_repair_targets": [
                        {
                            "slice_key": "dev/category/multilingual_bn",
                            "classification": "stable_regression",
                        }
                    ],
                    "official_scores_claimed": False,
                },
            ],
            "composition_id": "dev-hard-gate-composition",
            "output_path": str(output),
        }
    )

    assert payload["schema_version"] == "2026-06-05.gate-policy-composition.v1"
    assert payload["status"] == "blocked"
    assert payload["blocking_policies"] == ["paired-repeat-variance-gate"]
    assert payload["gate"]["canary_allowed"] is False
    assert payload["official_scores_claimed"] is False
    assert output.exists()


def test_gate_policy_graph_tool_blocks_only_required_policy_failures(
    tmp_path: Path,
) -> None:
    graph_path = tmp_path / "gate-policy-graph.json"
    decision_path = tmp_path / "gate-policy-graph-decision.json"
    graph = mcp_service.build_gate_policy_graph_tool(
        {
            "graph_id": "dev-policy-graph",
            "required_policies": [
                "slice-dev-hard-gate",
                "paired-repeat-variance-gate",
            ],
            "optional_policies": ["cost-ceiling-gate"],
            "output_path": str(graph_path),
        }
    )
    decision = mcp_service.evaluate_gate_policy_graph_tool(
        {
            "policy_graph_file": str(graph_path),
            "decisions": [
                {
                    "schema_version": "2026-06-05.gate-policy-decision.v1",
                    "status": "passed_for_canary",
                    "policy_id": "slice-dev-hard-gate",
                    "split": "dev",
                    "gate": {"canary_allowed": True, "promotion_ready": False},
                    "hard_blockers": [],
                    "official_scores_claimed": False,
                },
                {
                    "schema_version": "2026-06-05.slice-variance-gate-decision.v1",
                    "status": "blocked",
                    "policy_id": "paired-repeat-variance-gate",
                    "split": "dev",
                    "gate": {"canary_allowed": False, "promotion_ready": False},
                    "hard_blockers": ["stable_slice_regression"],
                    "official_scores_claimed": False,
                },
                {
                    "schema_version": "2026-06-05.gate-policy-decision.v1",
                    "status": "blocked",
                    "policy_id": "cost-ceiling-gate",
                    "split": "dev",
                    "gate": {"canary_allowed": False, "promotion_ready": False},
                    "hard_blockers": ["cost_too_high"],
                    "official_scores_claimed": False,
                },
            ],
            "output_path": str(decision_path),
        }
    )

    assert graph["schema_version"] == "2026-06-05.gate-policy-graph.v1"
    assert decision["schema_version"] == "2026-06-05.gate-policy-graph-decision.v1"
    assert decision["blocking_policies"] == ["paired-repeat-variance-gate"]
    assert decision["advisory_blocking_policies"] == ["cost-ceiling-gate"]
    assert decision["gate"]["canary_allowed"] is False
    assert decision["official_scores_claimed"] is False
    assert decision_path.exists()


def test_rank_failure_driven_proposals_tool(tmp_path: Path) -> None:
    failures = tmp_path / "failure-records.jsonl"
    patterns = tmp_path / "proposal-pattern-memory.jsonl"
    proposals = tmp_path / "proposal-cards.json"
    failures.write_text(
        json.dumps(
            {
                "schema_version": "2026-06-02.failure-record.v1",
                "failure_id": "f1",
                "task_id": "round-001",
                "failure_type": "canary_not_confirmed",
                "symptom": "canary regressed",
                "severity": "medium",
                "claim_boundary": "local only",
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    patterns.write_text(
        json.dumps(
            {
                "schema_version": "2026-06-02.proposal-pattern-memory.v1",
                "pattern_id": "failure_fix::canary_not_confirmed",
                "pattern_summary": "failure_fix against canary_not_confirmed",
                "proposal_type": "failure_fix",
                "applicable_when": ["canary_not_confirmed"],
                "historical_success_rate": 0.8,
                "historical_failure_rate": 0.2,
                "claim_boundary": "local only",
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    proposals.write_text(
        json.dumps(
            [
                {
                    "proposal_id": "p1",
                    "proposal_type": "failure_fix",
                    "based_on_failures": ["f1"],
                    "intent": "Preserve canary behavior.",
                    "change_surface": "routing",
                    "target_scope": "single routing block",
                    "expected_gain": {"score": 0.9},
                    "risk_level": "low",
                    "verification_plan": {"first_split": "dev"},
                    "rollback_rule": {"if": ["canary_delta_lt_0"]},
                    "claim_boundary": "local only",
                    "official_scores_claimed": False,
                }
            ]
        ),
        encoding="utf-8",
    )

    payload = mcp_service.rank_failure_driven_proposals_tool(
        {
            "proposals_file": str(proposals),
            "failure_records_file": str(failures),
            "pattern_memory_file": str(patterns),
            "output_path": str(tmp_path / "ranked-proposals.json"),
        }
    )

    assert payload["status"] == "completed"
    assert payload["ranked_proposals"][0]["proposal_id"] == "p1"
    assert payload["ranked_proposals"][0]["change_surface"] == "routing"
    assert payload["ranked_proposals"][0]["rollback_rule"]["if"] == ["canary_delta_lt_0"]
    assert Path(payload["output_path"]).exists()


def test_build_failure_driven_proposal_handoff_tool(tmp_path: Path) -> None:
    context = tmp_path / "failure-context.json"
    ranking = tmp_path / "ranked-proposals.json"
    context.write_text(
        json.dumps(
            {
                "status": "ready_for_failure_driven_proposals",
                "objective": "Preserve canary gain",
                "failure_summary": {
                    "record_count": 1,
                    "records": [
                        {
                            "failure_id": "f1",
                            "failure_type": "canary_not_confirmed",
                            "symptom": "canary regressed",
                        }
                    ],
                },
                "pattern_summary": {"matched_patterns": []},
                "claim_boundary": "local only",
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    ranking.write_text(
        json.dumps(
            {
                "status": "completed",
                "ranked_proposals": [
                    {
                        "proposal_id": "p1",
                        "proposal_type": "failure_fix",
                        "based_on_failures": ["f1"],
                        "change_surface": "prompt_profile",
                        "target_scope": "prompt_profile",
                        "verification_plan": {"first_split": "dev", "promotion_split": "canary"},
                        "rollback_rule": {"if": ["canary_delta_lt_0"]},
                        "score": 1.2,
                        "rank": 1,
                        "gate_labels": [],
                        "score_breakdown": {"pattern_prior": 0.8},
                        "claim_boundary": "local only",
                        "official_scores_claimed": False,
                    }
                ],
                "claim_boundary": "local only",
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    payload = mcp_service.build_failure_driven_proposal_handoff_tool(
        {
            "context_file": str(context),
            "ranking_file": str(ranking),
            "output_dir": str(tmp_path / "handoff"),
            "max_selected": 1,
        }
    )

    assert payload["status"] == "completed"
    assert payload["selected_next_proposals"][0]["proposal_id"] == "p1"
    assert payload["selected_next_proposals"][0]["change_surface"] == "prompt_profile"
    assert payload["memory_bridge"][0]["future_memory_type"] == "patch_or_failure"
    assert Path(payload["proposal_file"]).exists()


def test_build_failure_driven_client_proposal_templates_tool(tmp_path: Path) -> None:
    handoff = tmp_path / "failure-handoff.json"
    handoff.write_text(
        json.dumps(
            {
                "status": "completed",
                "objective": "Preserve canary gain",
                "selected_next_proposals": [
                    {
                        "proposal_id": "p1",
                        "proposal_type": "failure_fix",
                        "based_on_failures": ["f1"],
                        "change_surface": "prompt_profile",
                        "target_scope": "single prompt-profile scope",
                        "verification_plan": {
                            "first_split": "canary",
                            "promotion_split": "canary",
                            "max_rounds": 1,
                        },
                        "rollback_rule": {"if": ["canary_delta_lt_0"]},
                        "score": 1.2,
                        "rank": 1,
                        "requires_client_review": True,
                    }
                ],
                "failure_summary": {
                    "records": [
                        {
                            "failure_id": "f1",
                            "failure_type": "canary_not_confirmed",
                            "symptom": "canary regressed",
                        }
                    ]
                },
                "claim_boundary": "local only",
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    payload = mcp_service.build_failure_driven_client_proposal_templates_tool(
        {
            "handoff_file": str(handoff),
            "output_dir": str(tmp_path / "templates"),
        }
    )

    assert payload["status"] == "completed"
    assert payload["proposal_templates"][0]["proposal_id"].startswith("p1")
    assert payload["proposal_templates"][0]["change_surface"] == "prompt_profile"
    assert payload["proposal_templates"][0]["validation_plan"]["first_split"] == "canary"
    assert payload["proposal_templates"][0]["expected_effect"]["primary_metric"] == "SHIFT"
    assert Path(payload["proposal_file"]).exists()


def test_bridge_failure_driven_outcome_to_memory_card_tool(tmp_path: Path) -> None:
    handoff = tmp_path / "failure-handoff.json"
    outcome = tmp_path / "proposal-outcome.json"
    handoff.write_text(
        json.dumps(
            {
                "status": "completed",
                "objective": "Preserve canary gain",
                "selected_next_proposals": [{"proposal_id": "p1", "based_on_failures": ["f1"]}],
                "failure_summary": {
                    "records": [
                        {
                            "failure_id": "f1",
                            "failure_type": "canary_not_confirmed",
                            "symptom": "canary regressed",
                        }
                    ]
                },
                "claim_boundary": "local only",
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    outcome.write_text(
        json.dumps(
            {
                "status": "completed",
                "schema_version": "2026-06-02.proposal-outcome.v1",
                "outcome_id": "p1-outcome",
                "proposal_id": "p1",
                "proposal_type": "failure_fix",
                "based_on_failures": ["f1"],
                "change_surface": "routing",
                "target_scope": "single routing block",
                "executed": True,
                "accepted": True,
                "metric_delta": {"dev": 0.5, "canary": 0.1},
                "rollback_triggered": False,
                "failure_labels": [],
                "claim_boundary": "local only",
                "official_scores_claimed": False,
                "output_path": str(outcome),
            }
        ),
        encoding="utf-8",
    )

    payload = mcp_service.bridge_failure_driven_outcome_to_memory_card_tool(
        {
            "outcome_file": str(outcome),
            "handoff_file": str(handoff),
            "output_path": str(tmp_path / "memory-card-candidate.json"),
        }
    )

    assert payload["status"] == "completed"
    assert payload["memory_card_candidate"]["card_id"] == "failure-driven-p1"
    assert Path(payload["output_path"]).exists()


def test_record_memory_card_candidate_tool_requires_confirm_and_records(
    tmp_path: Path,
) -> None:
    store = tmp_path / "memory.jsonl"
    artifact = tmp_path / "proposal-outcome.json"
    artifact.write_text("{}", encoding="utf-8")
    candidate = tmp_path / "memory-card-candidate.json"
    candidate.write_text(
        json.dumps(
            {
                "status": "completed",
                "memory_card_candidate": {
                    "card_id": "failure-driven-p1",
                    "memory_type": "patch",
                    "task_family": "failure-driven-proposal",
                    "summary": "Failure-driven proposal p1 outcome=accepted.",
                    "patch_type": "routing",
                    "failure_category": "canary_not_confirmed",
                    "artifact_refs": [
                        {
                            "name": "failure_driven_outcome",
                            "path": str(artifact),
                            "sha256": "abc123",
                            "artifact_type": "proposal_outcome",
                        }
                    ],
                    "claim_boundary": "local candidate only",
                    "official_scores_claimed": False,
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(mcp_service.MCPToolError):
        mcp_service.record_memory_card_candidate_tool(
            {
                "store": str(store),
                "candidate_file": str(candidate),
            }
        )

    payload = mcp_service.record_memory_card_candidate_tool(
        {
            "store": str(store),
            "candidate_file": str(candidate),
            "confirm": True,
        }
    )

    assert payload["status"] == "recorded"
    assert payload["card_ids"] == ["failure-driven-p1"]


def test_evaluate_failure_driven_proposal_effectiveness_tool_writes_report(
    tmp_path: Path,
) -> None:
    control = tmp_path / "control-outcomes.jsonl"
    treatment = tmp_path / "treatment-outcomes.jsonl"
    control.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "outcome_id": "c1",
                        "accepted": False,
                        "metric_delta": {"dev": 0.2, "canary": -0.2},
                        "rollback_triggered": True,
                        "failure_labels": ["canary_not_confirmed"],
                        "official_scores_claimed": False,
                    }
                ),
                json.dumps(
                    {
                        "outcome_id": "c2",
                        "accepted": True,
                        "metric_delta": {"dev": 0.3, "canary": 0.0},
                        "rollback_triggered": False,
                        "failure_labels": ["canary_not_confirmed"],
                        "official_scores_claimed": False,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    treatment.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "outcome_id": "t1",
                        "accepted": True,
                        "metric_delta": {"dev": 0.4, "canary": 0.2},
                        "rollback_triggered": False,
                        "failure_labels": [],
                        "official_scores_claimed": False,
                    }
                ),
                json.dumps(
                    {
                        "outcome_id": "t2",
                        "accepted": True,
                        "metric_delta": {"dev": 0.1, "canary": 0.1},
                        "rollback_triggered": False,
                        "failure_labels": [],
                        "official_scores_claimed": False,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = mcp_service.evaluate_failure_driven_proposal_effectiveness_tool(
        {
            "control_outcomes_file": str(control),
            "treatment_outcomes_file": str(treatment),
            "output_path": str(tmp_path / "proposal-effectiveness.json"),
        }
    )

    assert payload["status"] == "completed"
    assert payload["comparison"]["proposal_accept_rate_lift"] == 0.5
    assert payload["comparison"]["verdict"] == "treatment_improved_on_measured_metrics"
    assert Path(payload["output_path"]).exists()


def test_generate_failure_driven_proposals_tool_writes_report(tmp_path: Path) -> None:
    context = tmp_path / "failure-context.json"
    context.write_text(
        json.dumps(
            {
                "status": "ready_for_failure_driven_proposals",
                "schema_version": "2026-06-02.failure-driven-context.v1",
                "objective": "Preserve local gain on canary.",
                "max_proposals": 1,
                "failure_summary": {
                    "record_count": 1,
                    "records": [
                        {
                            "failure_id": "f1",
                            "failure_type": "canary_not_confirmed",
                            "severity": "medium",
                            "scope": "single routing block",
                            "official_scores_claimed": False,
                        }
                    ],
                },
                "pattern_summary": {
                    "pattern_count": 1,
                    "matched_patterns": [
                        {
                            "pattern_id": "failure_fix::canary_not_confirmed",
                            "proposal_type": "failure_fix",
                            "applicable_when": ["canary_not_confirmed"],
                            "historical_success_rate": 0.8,
                            "official_scores_claimed": False,
                        }
                    ],
                },
                "prompt_markdown": "failure-driven prompt",
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    payload = mcp_service.generate_failure_driven_proposals_tool(
        {
            "context_file": str(context),
            "output_path": str(tmp_path / "generated-proposals.json"),
            "preferred_change_surfaces": ["routing"],
        }
    )

    assert payload["status"] == "completed"
    assert payload["proposal_count"] == 1
    assert payload["proposals"][0]["change_surface"] == "routing"
    assert Path(payload["output_path"]).exists()


def test_retrieve_proposal_patterns_tool_filters_matches(tmp_path: Path) -> None:
    pattern_memory = tmp_path / "proposal-pattern-memory.jsonl"
    pattern_memory.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "schema_version": "2026-06-02.proposal-pattern-memory.v1",
                        "pattern_id": "failure_fix::canary_not_confirmed",
                        "pattern_summary": "canary fix",
                        "proposal_type": "failure_fix",
                        "applicable_when": ["canary_not_confirmed"],
                        "task_family": "smol_worldcup",
                        "metric_names": ["canary", "dev"],
                        "historical_success_rate": 0.8,
                        "historical_failure_rate": 0.2,
                        "claim_boundary": "local only",
                        "official_scores_claimed": False,
                    }
                ),
                json.dumps(
                    {
                        "schema_version": "2026-06-02.proposal-pattern-memory.v1",
                        "pattern_id": "strategy_shift::no_improvement",
                        "pattern_summary": "strategy shift",
                        "proposal_type": "strategy_shift",
                        "applicable_when": ["no_improvement"],
                        "task_family": "smol_worldcup",
                        "metric_names": ["dev"],
                        "historical_success_rate": 0.4,
                        "historical_failure_rate": 0.6,
                        "claim_boundary": "local only",
                        "official_scores_claimed": False,
                    }
                ),
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    payload = mcp_service.retrieve_proposal_patterns_tool(
        {
            "pattern_memory_file": str(pattern_memory),
            "failure_type": "canary_not_confirmed",
            "metric_name": "canary",
        }
    )

    assert payload["status"] == "completed"
    assert payload["match_count"] == 1
    assert payload["matches"][0]["pattern"]["pattern_id"] == "failure_fix::canary_not_confirmed"


def test_build_cp_bench_proposal_effectiveness_bundle_tool_writes_report(
    tmp_path: Path,
) -> None:
    round_report = tmp_path / "cp-bench-candidate-round-report.json"
    round_report.write_text(
        json.dumps(
            {
                "status": "improved",
                "target_id": "cp-bench-constraint-modeling",
                "proposal": {
                    "proposal_id": "cp-bench-p15-client-solver-expansion",
                    "change_type": "code_patch",
                },
                "before_summary": {
                    "submitted_models": 21,
                    "coverage_percent": 33.33,
                    "consistency_percent": 0.0,
                    "final_solution_accuracy_percent": 0.0,
                },
                "after_summary": {
                    "submitted_models": 21,
                    "coverage_percent": 33.33,
                    "consistency_percent": 31.75,
                    "final_solution_accuracy_percent": 31.75,
                },
                "failure_summary": {
                    "by_failure_type": {
                        "consistency_or_objective_failed": 1,
                    }
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    payload = mcp_service.build_cp_bench_proposal_effectiveness_bundle_tool(
        {
            "round_reports": [str(round_report)],
            "output_dir": str(tmp_path / "bundle"),
        }
    )

    assert payload["status"] == "completed"
    assert payload["treatment_outcome_count"] == 1
    assert payload["comparison"]["proposal_accept_rate_lift"] == 1.0


def test_build_fasttext_proposal_effectiveness_bundle_tool_writes_report(
    tmp_path: Path,
) -> None:
    multi_round_report = tmp_path / "multi-round-report.json"
    multi_round_report.write_text(
        json.dumps(
            {
                "status": "completed_with_failures",
                "stage": "p5_fasttext_multi_proposal_loop",
                "rounds": [
                    {
                        "round_index": 1,
                        "proposal_id": "p5-wordngrams-2",
                        "status": "completed",
                        "delta_vs_baseline": 0.002,
                        "improved_best": True,
                        "rollback_action": "promote_to_best",
                        "official_scores_claimed": False,
                    },
                    {
                        "round_index": 2,
                        "proposal_id": "p5-invalid-bucket",
                        "status": "failed",
                        "error": "unsupported fastText patch arg '-bucket'",
                        "rollback_action": "keep_best_so_far",
                        "official_scores_claimed": False,
                    },
                ],
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    payload = mcp_service.build_fasttext_proposal_effectiveness_bundle_tool(
        {
            "multi_round_reports": [str(multi_round_report)],
            "output_dir": str(tmp_path / "bundle"),
        }
    )

    assert payload["status"] == "completed"
    assert payload["treatment_outcome_count"] == 2
    assert payload["comparison"]["proposal_accept_rate_lift"] == 0.5


def test_build_fasttext_proposal_effectiveness_bundle_tool_completed_only(
    tmp_path: Path,
) -> None:
    multi_round_report = tmp_path / "multi-round-report.json"
    multi_round_report.write_text(
        json.dumps(
            {
                "status": "completed_with_failures",
                "rounds": [
                    {
                        "proposal_id": "p5-wordngrams-2",
                        "status": "completed",
                        "delta_vs_baseline": 0.002,
                        "improved_best": True,
                        "rollback_action": "promote_to_best",
                        "official_scores_claimed": False,
                    },
                    {
                        "proposal_id": "p5-invalid-bucket",
                        "status": "failed",
                        "error": "unsupported fastText patch arg '-bucket'",
                        "rollback_action": "keep_best_so_far",
                        "official_scores_claimed": False,
                    },
                ],
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    payload = mcp_service.build_fasttext_proposal_effectiveness_bundle_tool(
        {
            "multi_round_reports": [str(multi_round_report)],
            "output_dir": str(tmp_path / "bundle"),
            "include_failed_rounds": False,
        }
    )

    assert payload["status"] == "completed"
    assert payload["include_failed_rounds"] is False
    assert payload["treatment_outcome_count"] == 1
    assert payload["comparison"]["proposal_accept_rate_lift"] == 1.0


def test_build_smol_worldcup_proposal_effectiveness_bundle_tool_writes_report(
    tmp_path: Path,
) -> None:
    control_dev = tmp_path / "control-dev.json"
    treatment_dev = tmp_path / "treatment-dev.json"
    control_canary = tmp_path / "control-canary.json"
    treatment_canary = tmp_path / "treatment-canary.json"
    control_dev.write_text(
        json.dumps(
            {
                "round_id": "qwen3-8b-dev-round-002-dev-v2-20260521",
                "dataset": {"evaluation_split": "dev", "row_count": 100},
                "model": {"prompt_profile": "p3-dev-v2"},
                "proposal": {
                    "proposal_id": "qwen3-8b-dev-round-002-dev-v2-20260521-failure-driven-routing",
                    "top_failure_categories": [{"category": "confidence_calibration", "count": 7}],
                },
                "metrics": {
                    "H": 92.424242,
                    "I": 73.880597,
                    "SHIFT": 81.298055,
                    "WCS_local_diagnostic": 90.165434,
                },
                "failure_summary": {"failure_count": 35},
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    treatment_dev.write_text(
        json.dumps(
            {
                "round_id": "qwen3-8b-dev-round-004-semantic-v2-20260521",
                "dataset": {"evaluation_split": "dev", "row_count": 100},
                "model": {"prompt_profile": "p3-semantic-v2"},
                "proposal": {
                    "proposal_id": "qwen3-8b-dev-round-004-semantic-v2-20260521-failure-driven-routing",
                    "top_failure_categories": [{"category": "knowledge_synthesis", "count": 4}],
                },
                "metrics": {
                    "H": 92.424242,
                    "I": 75.447761,
                    "SHIFT": 82.238353,
                    "WCS_local_diagnostic": 90.685365,
                },
                "failure_summary": {"failure_count": 36},
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    control_canary.write_text(
        json.dumps(
            {
                "round_id": "qwen3-8b-canary-round-002-dev-v2-20260521",
                "dataset": {"evaluation_split": "canary", "row_count": 25},
                "model": {"prompt_profile": "p3-dev-v2"},
                "proposal": {
                    "proposal_id": "qwen3-8b-canary-round-002-dev-v2-20260521-failure-driven-routing",
                    "top_failure_categories": [{"category": "reasoning", "count": 3}],
                },
                "metrics": {
                    "H": 77.857143,
                    "I": 77.777778,
                    "SHIFT": 77.809524,
                    "WCS_local_diagnostic": 88.209707,
                },
                "failure_summary": {"failure_count": 12},
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    treatment_canary.write_text(
        json.dumps(
            {
                "round_id": "qwen3-8b-canary-round-004-semantic-v2-20260521",
                "dataset": {"evaluation_split": "canary", "row_count": 25},
                "model": {"prompt_profile": "p3-semantic-v2"},
                "proposal": {
                    "proposal_id": "qwen3-8b-canary-round-004-semantic-v2-20260521-failure-driven-routing",
                    "top_failure_categories": [{"category": "reasoning", "count": 2}],
                },
                "metrics": {
                    "H": 77.857143,
                    "I": 77.222222,
                    "SHIFT": 77.47619,
                    "WCS_local_diagnostic": 88.02056,
                },
                "failure_summary": {"failure_count": 11},
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    payload = mcp_service.build_smol_worldcup_proposal_effectiveness_bundle_tool(
        {
            "control_reports": [str(control_dev), str(control_canary)],
            "treatment_reports": [str(treatment_dev), str(treatment_canary)],
            "output_dir": str(tmp_path / "bundle"),
        }
    )

    assert payload["status"] == "completed"
    assert payload["treatment_outcome_count"] == 2
    assert payload["comparison"]["proposal_accept_rate_lift"] == 0.5
    assert payload["comparison"]["verdict"] == "mixed_signal"


def test_build_smol_worldcup_proposal_effectiveness_bundle_tool_split_filter_dev(
    tmp_path: Path,
) -> None:
    control_dev = tmp_path / "control-dev.json"
    treatment_dev = tmp_path / "treatment-dev.json"
    control_canary = tmp_path / "control-canary.json"
    treatment_canary = tmp_path / "treatment-canary.json"
    control_dev.write_text(
        json.dumps(
            {
                "round_id": "qwen3-8b-dev-round-002-dev-v2-20260521",
                "dataset": {"evaluation_split": "dev", "row_count": 100},
                "model": {"prompt_profile": "p3-dev-v2"},
                "proposal": {"proposal_id": "dev-control"},
                "metrics": {
                    "H": 92.424242,
                    "I": 73.880597,
                    "SHIFT": 81.298055,
                    "WCS_local_diagnostic": 90.165434,
                },
                "failure_summary": {"failure_count": 35},
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    treatment_dev.write_text(
        json.dumps(
            {
                "round_id": "qwen3-8b-dev-round-004-semantic-v2-20260521",
                "dataset": {"evaluation_split": "dev", "row_count": 100},
                "model": {"prompt_profile": "p3-semantic-v2"},
                "proposal": {"proposal_id": "dev-treatment"},
                "metrics": {
                    "H": 92.424242,
                    "I": 75.447761,
                    "SHIFT": 82.238353,
                    "WCS_local_diagnostic": 90.685365,
                },
                "failure_summary": {"failure_count": 36},
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    control_canary.write_text(
        json.dumps(
            {
                "round_id": "qwen3-8b-canary-round-002-dev-v2-20260521",
                "dataset": {"evaluation_split": "canary", "row_count": 25},
                "model": {"prompt_profile": "p3-dev-v2"},
                "proposal": {"proposal_id": "canary-control"},
                "metrics": {
                    "H": 77.857143,
                    "I": 77.777778,
                    "SHIFT": 77.809524,
                    "WCS_local_diagnostic": 88.209707,
                },
                "failure_summary": {"failure_count": 12},
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    treatment_canary.write_text(
        json.dumps(
            {
                "round_id": "qwen3-8b-canary-round-004-semantic-v2-20260521",
                "dataset": {"evaluation_split": "canary", "row_count": 25},
                "model": {"prompt_profile": "p3-semantic-v2"},
                "proposal": {"proposal_id": "canary-treatment"},
                "metrics": {
                    "H": 77.857143,
                    "I": 77.222222,
                    "SHIFT": 77.47619,
                    "WCS_local_diagnostic": 88.02056,
                },
                "failure_summary": {"failure_count": 11},
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    payload = mcp_service.build_smol_worldcup_proposal_effectiveness_bundle_tool(
        {
            "control_reports": [str(control_dev), str(control_canary)],
            "treatment_reports": [str(treatment_dev), str(treatment_canary)],
            "split_filter": "dev",
            "output_dir": str(tmp_path / "bundle"),
        }
    )

    assert payload["status"] == "completed"
    assert payload["split_filter"] == "dev"
    assert payload["comparison_pair_count"] == 1
    assert payload["comparison"]["proposal_accept_rate_lift"] == 1.0


def test_build_smol_worldcup_promotion_gate_tool_writes_report(
    tmp_path: Path,
) -> None:
    dev_report = tmp_path / "dev-effectiveness.json"
    canary_report = tmp_path / "canary-effectiveness.json"
    dev_report.write_text(
        json.dumps(
            {
                "comparison": {
                    "proposal_accept_rate_lift": 1.0,
                    "rollback_rate_reduction": 0.0,
                    "avg_metric_delta_lift": {"SHIFT": 0.9403},
                    "verdict": "treatment_improved_on_measured_metrics",
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    canary_report.write_text(
        json.dumps(
            {
                "comparison": {
                    "proposal_accept_rate_lift": 0.0,
                    "rollback_rate_reduction": -1.0,
                    "avg_metric_delta_lift": {"SHIFT": -0.3333},
                    "verdict": "treatment_regressed_on_measured_metrics",
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    payload = mcp_service.build_smol_worldcup_promotion_gate_tool(
        {
            "dev_effectiveness_report": str(dev_report),
            "canary_effectiveness_report": str(canary_report),
            "output_dir": str(tmp_path / "promotion-gate"),
        }
    )

    assert payload["status"] == "blocked_on_canary_confirmation"
    assert payload["dev_gate"]["passed"] is True
    assert payload["canary_gate"]["passed"] is False


def test_build_smol_worldcup_canary_failure_slice_audit_tool_writes_report(
    tmp_path: Path,
) -> None:
    canary_report = tmp_path / "canary-effectiveness.json"
    promotion_gate = tmp_path / "promotion-gate.json"
    control_outcomes = tmp_path / "control-outcomes.jsonl"
    treatment_outcomes = tmp_path / "treatment-outcomes.jsonl"
    canary_report.write_text(
        json.dumps(
            {
                "comparison": {
                    "proposal_accept_rate_lift": 0.0,
                    "rollback_rate_reduction": -1.0,
                    "avg_metric_delta_lift": {
                        "I": -0.5556,
                        "SHIFT": -0.3333,
                    },
                    "verdict": "treatment_regressed_on_measured_metrics",
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    promotion_gate.write_text(
        json.dumps(
            {
                "status": "blocked_on_canary_confirmation",
                "canary_gate": {
                    "blockers": [
                        "proposal_accept_rate_not_positive",
                        "rollback_rate_worsened",
                    ]
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    control_outcomes.write_text(
        json.dumps(
            {
                "outcome_id": "control-1",
                "failure_labels": ["no_improvement"],
                "rollback_reasons": [],
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )
    treatment_outcomes.write_text(
        json.dumps(
            {
                "outcome_id": "treatment-1",
                "failure_labels": ["canary_not_confirmed", "no_improvement"],
                "rollback_reasons": ["canary_not_confirmed"],
                "official_scores_claimed": False,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    payload = mcp_service.build_smol_worldcup_canary_failure_slice_audit_tool(
        {
            "canary_effectiveness_report": str(canary_report),
            "promotion_gate": str(promotion_gate),
            "control_outcomes": str(control_outcomes),
            "treatment_outcomes": str(treatment_outcomes),
            "output_dir": str(tmp_path / "canary-failure-slice-audit"),
        }
    )

    assert payload["status"] == "failure_slice_control_arm_required"
    assert payload["failure_slice_label"] == "canary_not_confirmed"
    assert "proposal_accept_rate_not_positive" in payload["canary_gate_blockers"]


def test_build_smol_worldcup_canary_control_arm_handoff_tool_writes_report(
    tmp_path: Path,
) -> None:
    failure_slice_audit = tmp_path / "failure-slice-audit.json"
    failure_slice_audit.write_text(
        json.dumps(
            {
                "status": "failure_slice_control_arm_required",
                "gate_status": "blocked_on_canary_confirmation",
                "failure_slice_label": "canary_not_confirmed",
                "canary_gate_blockers": [
                    "proposal_accept_rate_not_positive",
                    "rollback_rate_worsened",
                ],
                "control_arm_spec": {
                    "task_family": "smol_worldcup_prompt_routing",
                    "evaluation_split": "canary",
                    "failure_slice_label": "canary_not_confirmed",
                    "baseline_requirement": "matched_canary_negative_control",
                    "comparison_requirement": "same_metric_family_and_split",
                    "success_criteria": [
                        "proposal_accept_rate_lift_gt_0",
                        "rollback_rate_reduction_gte_0",
                    ],
                    "promotion_rule": "do_not_promote_until_failure_slice_control_arm_passes",
                },
                "recommended_next_action": "add_failure_slice_specific_control_arm",
                "audit_path": "docs/evidence/smol-worldcup-qwen3-canary-failure-slice-audit/smol-worldcup-canary-failure-slice-audit.json",
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    payload = mcp_service.build_smol_worldcup_canary_control_arm_handoff_tool(
        {
            "failure_slice_audit": str(failure_slice_audit),
            "output_dir": str(tmp_path / "control-arm-handoff"),
        }
    )

    assert payload["status"] == "ready_for_client_review"
    assert payload["proposal_template"]["based_on_failures"] == ["canary_not_confirmed"]
    assert payload["proposal_template"]["change_surface"] == "prompt_profile"
    assert "validate_client_proposal_contract" == payload["recommended_next_step"]["mcp_tool"]


def test_build_smol_worldcup_canary_control_arm_execution_bundle_tool_writes_report(
    tmp_path: Path,
) -> None:
    handoff = tmp_path / "control-arm-handoff.json"
    handoff.write_text(
        json.dumps(
            {
                "status": "ready_for_client_review",
                "failure_slice_label": "canary_not_confirmed",
                "control_outcome_ids": [
                    "qwen3-8b-canary-round-002-dev-v2-20260521-failure-driven-routing-control"
                ],
                "proposal_template": {
                    "proposal_id": "smol-worldcup-canary-control-arm-canary-not-confirmed",
                    "hypothesis": "Run matched canary control arm.",
                    "evidence_used": [
                        {"artifact": "slice-audit", "observation": "canary blocked"}
                    ],
                    "change_surface": "prompt_profile",
                    "change_spec": {"single_primary_variable": True},
                    "expected_effect": {
                        "primary_metric": "SHIFT",
                        "expected_direction": "maximize",
                    },
                    "validation_plan": {
                        "first_split": "canary",
                        "promotion_split": "canary",
                        "rollback_if": ["canary_delta_lt_0"],
                    },
                    "risk_assessment": {"primary": "confounded if not matched"},
                    "next_if_success": "rebuild_gate",
                    "next_if_failure": "keep_blocked",
                    "claim_boundary": "local only",
                    "official_scores_claimed": False,
                },
                "validation_result": {"status": "accepted", "failure_labels": []},
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    current_report = tmp_path / "current-report.json"
    current_report.write_text(
        json.dumps({"metrics": {"SHIFT": 70.0, "H": 70.0, "I": 70.0}}),
        encoding="utf-8",
    )

    payload = mcp_service.build_smol_worldcup_canary_control_arm_execution_bundle_tool(
        {
            "handoff": str(handoff),
            "current_report": str(current_report),
            "output_dir": str(tmp_path / "execution-bundle"),
        }
    )

    assert payload["status"] == "ready_for_guarded_execution"
    assert payload["target_prompt_profile"] == "p3-dev-v2"
    assert payload["runtime_config"]["model"] == "qwen/qwen3-8b"
    assert payload["recommended_next_step"]["mcp_tool"] == "run_smol_worldcup_proposal_round"


def test_build_smol_worldcup_canary_control_arm_execution_bundle_tool_resolves_current_report(
    tmp_path: Path,
) -> None:
    handoff = tmp_path / "control-arm-handoff.json"
    handoff.write_text(
        json.dumps(
            {
                "status": "ready_for_client_review",
                "failure_slice_label": "canary_not_confirmed",
                "control_outcome_ids": [
                    "qwen3-8b-canary-round-002-dev-v2-20260521-failure-driven-routing-control"
                ],
                "proposal_template": {
                    "proposal_id": "smol-worldcup-canary-control-arm-canary-not-confirmed",
                    "hypothesis": "Run matched canary control arm.",
                    "evidence_used": [
                        {"artifact": "slice-audit", "observation": "canary blocked"}
                    ],
                    "change_surface": "prompt_profile",
                    "change_spec": {"single_primary_variable": True},
                    "expected_effect": {
                        "primary_metric": "SHIFT",
                        "expected_direction": "maximize",
                    },
                    "validation_plan": {
                        "first_split": "canary",
                        "promotion_split": "canary",
                        "rollback_if": ["canary_delta_lt_0"],
                    },
                    "risk_assessment": {"primary": "confounded if not matched"},
                    "next_if_success": "rebuild_gate",
                    "next_if_failure": "keep_blocked",
                    "claim_boundary": "local only",
                    "official_scores_claimed": False,
                },
                "validation_result": {"status": "accepted", "failure_labels": []},
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    evidence_root = tmp_path / "evidence-root"
    source_report = (
        evidence_root
        / "proof-archives"
        / "smol-worldcup-round-004-canary-formal-rescore-20260520"
        / "artifacts"
        / "source-artifacts"
        / "source-model-eval-report.json"
    )
    source_report.parent.mkdir(parents=True, exist_ok=True)
    source_report.write_text(
        json.dumps(
            {
                "model": {
                    "id": "qwen/qwen3-8b",
                    "prompt_profile": "p3-dev-v2",
                    "provider": "openai-compatible",
                    "base_url": "http://127.0.0.1:1234/v1",
                    "judge_mode": "openai-compatible",
                    "judge_model": "openai/gpt-oss-20b",
                    "judge_base_url": "http://127.0.0.1:1234/v1",
                    "estimated_size_billion": 8.0,
                    "estimated_ram_gb": 16.0,
                },
                "dataset": {"evaluation_split": "canary"},
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    payload = mcp_service.build_smol_worldcup_canary_control_arm_execution_bundle_tool(
        {
            "handoff": str(handoff),
            "evidence_root": str(evidence_root),
            "output_dir": str(tmp_path / "execution-bundle"),
        }
    )

    assert payload["current_report_resolution"]["status"] == "resolved_from_evidence"
    assert payload["current_report_resolution"]["path"] == str(source_report.resolve())
    assert payload["runtime_config"]["model"] == "qwen/qwen3-8b"


def test_build_smol_worldcup_promotion_gate_refresh_tool_writes_report(
    tmp_path: Path,
) -> None:
    previous_gate = tmp_path / "previous-gate.json"
    previous_gate.write_text(
        json.dumps(
            {
                "status": "blocked_on_canary_confirmation",
                "dev_gate": {"passed": True, "official_scores_claimed": False},
                "canary_gate": {"passed": False, "official_scores_claimed": False},
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    proposal_round_summary = tmp_path / "proposal-round-summary.json"
    proposal_round_summary.write_text(
        json.dumps(
            {
                "status": "completed",
                "validation_status": "accepted",
                "selected_prompt_profile": "p3-dev-v2",
                "evaluation_split": "canary",
                "evaluation": {
                    "canary_delta": {"SHIFT": 0.5, "I": 0.2},
                    "rollback_reasons": [],
                    "promotion_gate_passed": True,
                },
                "reflection_status": "needs_promotion_evidence",
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    payload = mcp_service.build_smol_worldcup_promotion_gate_refresh_tool(
        {
            "previous_gate": str(previous_gate),
            "proposal_round_summary": str(proposal_round_summary),
            "output_dir": str(tmp_path / "promotion-gate-refresh"),
        }
    )

    assert payload["status"] == "ready_for_prompt_profile_promotion"
    assert payload["promotion_ready"] is True
    assert payload["canary_gate_refresh"]["passed"] is True


def test_build_proposal_effectiveness_claim_audit_tool_writes_report(
    tmp_path: Path,
) -> None:
    cross_task_summary = tmp_path / "cross-task-summary.json"
    cross_task_summary.write_text(
        json.dumps(
            {
                "status": "completed",
                "schema_version": "2026-06-02.cross-task-proposal-effectiveness-summary.v1",
                "task_count": 3,
                "task_summaries": [
                    {
                        "task_family": "cp_bench_constraint_model_generation",
                        "verdict": "treatment_improved_on_measured_metrics",
                    },
                    {
                        "task_family": "fasttext_text_classification",
                        "verdict": "mixed_signal",
                    },
                    {
                        "task_family": "smol_worldcup_prompt_routing",
                        "verdict": "mixed_signal",
                    },
                ],
                "aggregate": {
                    "verdict_counts": {
                        "mixed_signal": 2,
                        "treatment_improved_on_measured_metrics": 1,
                    },
                    "consistent_improvements": ["SHIFT"],
                    "tradeoff_metrics": [],
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    payload = mcp_service.build_proposal_effectiveness_claim_audit_tool(
        {
            "cross_task_summary": str(cross_task_summary),
            "output_dir": str(tmp_path / "claim-audit"),
        }
    )

    assert payload["status"] == "completed"
    assert payload["claim_readiness"] == "insufficient_evidence_for_cross_task_effectiveness_claim"
    assert payload["gates"]["no_mixed_signal_tasks"]["passed"] is False
    assert "run_mixed_signal_task_family_audit" in payload["recommended_next_actions"]


def test_build_real_paper_proposal_effectiveness_bundle_tool_writes_report(
    tmp_path: Path,
) -> None:
    memflow_archive = tmp_path / "memflow-proof-archive.json"
    adam_archive = tmp_path / "adam-proof-archive.json"
    memflow_archive.write_text(
        json.dumps(
            {
                "status": "archivable",
                "benchmark_name": "real_paper_pilot",
                "description": "MemFlow bounded public-slice proof",
                "metric_summary": {
                    "metric_name": "selection_accuracy",
                    "metric_before": 0.25,
                    "metric_after": 1.0,
                    "delta": 0.75,
                    "method_family": "routing",
                },
                "review_status": "approved_with_limitations",
                "claim_boundary": "local public-slice proof only",
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    adam_archive.write_text(
        json.dumps(
            {
                "status": "archivable",
                "benchmark_name": "real_paper_pilot",
                "description": "Adam bounded public-slice proof",
                "metric_summary": {
                    "metric_name": "optimizer_progress_score",
                    "metric_before": 0.422823,
                    "metric_after": 0.881488,
                    "delta": 0.458665,
                    "method_family": "optimizer",
                },
                "review_status": "approved_with_limitations",
                "claim_boundary": "local public-slice proof only",
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    payload = mcp_service.build_real_paper_proposal_effectiveness_bundle_tool(
        {
            "proof_archives": [str(memflow_archive), str(adam_archive)],
            "output_dir": str(tmp_path / "bundle"),
        }
    )

    assert payload["status"] == "completed"
    assert payload["treatment_outcome_count"] == 2
    assert payload["comparison"]["proposal_accept_rate_lift"] == 1.0
    assert payload["comparison"]["verdict"] == "treatment_improved_on_measured_metrics"


def test_build_cross_task_proposal_effectiveness_summary_tool_writes_report(
    tmp_path: Path,
) -> None:
    cp_bench_report = tmp_path / "cp-bench-effectiveness.json"
    fasttext_report = tmp_path / "fasttext-effectiveness.json"
    smol_worldcup_report = tmp_path / "smol-worldcup-effectiveness.json"
    real_paper_report = tmp_path / "real-paper-effectiveness.json"
    cp_bench_report.write_text(
        json.dumps(
            {
                "comparison": {
                    "proposal_accept_rate_lift": 1.0,
                    "rollback_rate_reduction": 0.0,
                    "failure_repeat_rate_reduction": 0.8,
                    "avg_metric_delta_lift": {
                        "final_solution_accuracy_percent": 30.794,
                    },
                    "verdict": "treatment_improved_on_measured_metrics",
                },
                "control_summary": {"outcome_count": 5},
                "treatment_summary": {
                    "outcome_count": 5,
                    "best_outcome_id": "cp-bench-p17-treatment",
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    fasttext_report.write_text(
        json.dumps(
            {
                "comparison": {
                    "proposal_accept_rate_lift": 0.5,
                    "rollback_rate_reduction": -0.5,
                    "failure_repeat_rate_reduction": 0.5,
                    "avg_metric_delta_lift": {
                        "p_at_1": 0.001,
                    },
                    "verdict": "mixed_signal",
                },
                "control_summary": {"outcome_count": 2},
                "treatment_summary": {
                    "outcome_count": 2,
                    "best_outcome_id": "p5-wordngrams-2-treatment",
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    smol_worldcup_report.write_text(
        json.dumps(
            {
                "comparison": {
                    "proposal_accept_rate_lift": 0.5,
                    "rollback_rate_reduction": -0.5,
                    "failure_repeat_rate_reduction": 0.0,
                    "avg_metric_delta_lift": {
                        "SHIFT": 0.3035,
                        "I": 0.5059,
                        "WCS_local_diagnostic": 0.1654,
                    },
                    "verdict": "mixed_signal",
                },
                "control_summary": {"outcome_count": 2},
                "treatment_summary": {
                    "outcome_count": 2,
                    "best_outcome_id": "qwen3-8b-dev-round-004-semantic-v2-20260521-treatment",
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    real_paper_report.write_text(
        json.dumps(
            {
                "comparison": {
                    "proposal_accept_rate_lift": 1.0,
                    "rollback_rate_reduction": 0.0,
                    "failure_repeat_rate_reduction": 0.0,
                    "avg_metric_delta_lift": {
                        "selection_accuracy": 0.375,
                        "optimizer_progress_score": 0.2293,
                    },
                    "verdict": "treatment_improved_on_measured_metrics",
                },
                "control_summary": {"outcome_count": 2},
                "treatment_summary": {
                    "outcome_count": 2,
                    "best_outcome_id": "real-paper-adam-treatment",
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    payload = mcp_service.build_cross_task_proposal_effectiveness_summary_tool(
        {
            "effectiveness_reports": [
                str(cp_bench_report),
                str(fasttext_report),
                str(smol_worldcup_report),
                str(real_paper_report),
            ],
            "output_dir": str(tmp_path / "cross-task-summary"),
        }
    )

    assert payload["status"] == "completed"
    assert payload["task_count"] == 4
    assert payload["aggregate"]["verdict_counts"]["mixed_signal"] == 2
    assert payload["aggregate"]["verdict_counts"]["treatment_improved_on_measured_metrics"] == 2


def test_build_mixed_signal_proposal_effectiveness_audit_tool_writes_report(
    tmp_path: Path,
) -> None:
    fasttext_report = tmp_path / "fasttext-effectiveness.json"
    smol_worldcup_report = tmp_path / "smol-worldcup-effectiveness.json"
    fasttext_report.write_text(
        json.dumps(
            {
                "comparison": {
                    "proposal_accept_rate_lift": 0.5,
                    "rollback_rate_reduction": -0.5,
                    "failure_repeat_rate_reduction": 0.5,
                    "avg_metric_delta_lift": {"p_at_1": 0.001},
                    "verdict": "mixed_signal",
                },
                "treatment_summary": {
                    "outcome_count": 2,
                    "best_outcome_id": "p5-wordngrams-2-treatment",
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    smol_worldcup_report.write_text(
        json.dumps(
            {
                "comparison": {
                    "proposal_accept_rate_lift": 0.5,
                    "rollback_rate_reduction": -0.5,
                    "failure_repeat_rate_reduction": 0.0,
                    "avg_metric_delta_lift": {
                        "SHIFT": 0.3035,
                        "I": 0.5059,
                        "WCS_local_diagnostic": 0.1654,
                    },
                    "verdict": "mixed_signal",
                },
                "treatment_summary": {
                    "outcome_count": 2,
                    "best_outcome_id": "qwen3-8b-dev-round-004-semantic-v2-20260521-treatment",
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    payload = mcp_service.build_mixed_signal_proposal_effectiveness_audit_tool(
        {
            "effectiveness_reports": [
                str(fasttext_report),
                str(smol_worldcup_report),
            ],
            "output_dir": str(tmp_path / "mixed-signal-audit"),
        }
    )

    assert payload["status"] == "completed"
    assert payload["mixed_signal_task_count"] == 2
    assert payload["aggregate"]["blocking_signal_counts"]["rollback_rate_worsened"] == 2


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


def _optimizer_gate_plugin_manifest_fixture() -> dict:
    return {
        "schema_version": "2026-06-05.optimizer-gate-plugin-manifest.v1",
        "plugin_id": "local-dspy-fixture",
        "optimizer_adapters": [
            {
                "name": "dspy-mipro-local",
                "adapter_type": "deterministic_local",
                "runtime_status": "plugin_manifest_only",
                "provider": "plugin",
                "candidate_surface": "prompt_section",
                "candidate_schema": "2026-06-04.slice-patch-candidate.v1",
                "supports_execute_optimizer": False,
                "executes_tool_default": False,
                "executes_experiment": False,
                "module_scope": "single_module_single_section",
                "capabilities": ["module_section_instruction_search"],
            }
        ],
        "gate_policies": [
            {
                "policy_id": "cost-ceiling-gate",
                "function": "external_cost_ceiling_gate",
                "decision_schema": "2026-06-05.gate-policy-decision.v1",
                "required_inputs": ["gate_input"],
                "blocks_on": ["cost_too_high"],
                "decision_outputs": ["hard_blockers", "canary_allowed"],
                "canary_allowed_when": "hard_blockers is empty",
                "executes_experiment": False,
            }
        ],
        "claim_boundary": "non-executing plugin registry fixture only",
        "official_scores_claimed": False,
    }


def _runtime_optimizer_plugin_manifest_fixture() -> dict:
    return {
        "schema_version": "2026-06-05.optimizer-gate-plugin-manifest.v1",
        "plugin_id": "runtime-textgrad-fixture",
        "optimizer_adapters": [
            {
                "name": "runtime-textgrad-plugin",
                "adapter_type": "openai_compatible_critic",
                "runtime_status": "runtime_plugin_available",
                "provider": "plugin-openai-compatible",
                "candidate_surface": "prompt_section",
                "candidate_schema": "2026-06-04.slice-patch-candidate.v1",
                "supports_execute_optimizer": True,
                "executes_tool_default": False,
                "executes_experiment": False,
                "module_scope": "single_module_single_section",
                "capabilities": [
                    "section_local_patch",
                    "critic_feedback",
                    "structured_json_candidate",
                ],
                "runtime_entrypoint": {
                    "kind": "openai-compatible-chat-completions",
                    "default_model": "qwen/qwen3-8b",
                    "default_base_url": "http://127.0.0.1:1234/v1",
                    "api_key_env": "ML_RESEARCH_LOOP_TEXTGRAD_API_KEY",
                },
            }
        ],
        "gate_policies": [],
        "claim_boundary": "runtime-capable optimizer plugin fixture only",
        "official_scores_claimed": False,
    }


def _subprocess_optimizer_plugin_manifest_fixture(command: list[str]) -> dict:
    return {
        "schema_version": "2026-06-05.optimizer-gate-plugin-manifest.v1",
        "plugin_id": "subprocess-textgrad-fixture",
        "optimizer_adapters": [
            {
                "name": "subprocess-textgrad-plugin",
                "adapter_type": "subprocess_json_optimizer",
                "runtime_status": "runtime_plugin_available",
                "provider": "plugin-subprocess",
                "candidate_surface": "prompt_section",
                "candidate_schema": "2026-06-04.slice-patch-candidate.v1",
                "supports_execute_optimizer": True,
                "executes_tool_default": False,
                "executes_experiment": False,
                "module_scope": "single_module_single_section",
                "capabilities": [
                    "section_local_patch",
                    "subprocess_json_candidate",
                ],
                "runtime_entrypoint": {
                    "kind": "local-subprocess-json",
                    "command": command,
                },
            }
        ],
        "gate_policies": [],
        "claim_boundary": "subprocess optimizer plugin fixture only",
        "official_scores_claimed": False,
    }


def _python_package_optimizer_plugin_manifest_fixture(
    package_import: str,
    candidate_method: str | None = None,
) -> dict:
    runtime_entrypoint = {
        "kind": "python-package",
        "package_import": package_import,
        "adapter_class": "FixtureOptimizerAdapter",
    }
    if candidate_method:
        runtime_entrypoint["candidate_method"] = candidate_method
    return {
        "schema_version": "2026-06-05.optimizer-gate-plugin-manifest.v1",
        "plugin_id": "python-package-optimizer-fixture",
        "optimizer_adapters": [
            {
                "name": "python-package-optimizer-plugin",
                "adapter_type": "python_package_optimizer",
                "runtime_status": "runtime_plugin_available",
                "provider": "plugin-python-package",
                "candidate_surface": "prompt_section",
                "candidate_schema": "2026-06-04.slice-patch-candidate.v1",
                "supports_execute_optimizer": True,
                "executes_tool_default": False,
                "executes_experiment": False,
                "module_scope": "single_module_single_section",
                "capabilities": [
                    "section_local_patch",
                    "package_runtime_probe",
                ],
                "runtime_entrypoint": runtime_entrypoint,
            }
        ],
        "gate_policies": [],
        "claim_boundary": "python package optimizer probe fixture only",
        "official_scores_claimed": False,
    }


def test_tournament_tool_runs_synthetic_lifecycle(tmp_path, monkeypatch):
    monkeypatch.setenv("ML_RESEARCH_LOOP_ALLOWED_ROOTS", str(tmp_path))
    baseline_artifact = tmp_path / "baseline-report.json"
    baseline_artifact.write_text('{"metric": {"p_at_1": 0.9}}', encoding="utf-8")
    base = {"runtime_root": str(tmp_path), "run_id": "mcp-run"}
    started = mcp_service.tournament_tool({
        "stage": "start", **base, "target_id": "demo",
        "config": {"k": 2, "initial_rounds_per_arm": 1, "halving": 2,
                   "epsilon": 0.001, "metric": "P@1", "direction": "maximize",
                   "budgets": {"max_total_rounds": 6, "max_wall_seconds": 3600,
                               "target_value": 0.92}},
        "baseline": {"value": 0.9, "artifact": str(baseline_artifact)},
        "target": {"kind": "synthetic", "baseline_value": 0.9,
                   "weights": {"a": 0.01, "b": 0.001}},
    })
    assert started["pending_action"] == {"type": "need_direction_proposals", "k": 2}
    mcp_service.tournament_tool({
        "stage": "submit_directions", **base,
        "directions": [
            {"arm_id": "a1", "hypothesis": "push a",
             "first_proposal": {"params": {"a": 1}}},
            {"arm_id": "a2", "hypothesis": "push b",
             "first_proposal": {"params": {"b": 1}}},
        ],
    })
    for _ in range(2):
        mcp_service.tournament_tool({"stage": "step", **base})
    status = mcp_service.tournament_tool({"stage": "status", **base})
    assert status["pending_action"] == {"type": "stage_end"}
    assert status["ledger"]["total_rounds_used"] == 2
    mcp_service.tournament_tool({"stage": "step", **base})   # stage_end
    status = mcp_service.tournament_tool({"stage": "status", **base})
    assert status["pending_action"] == {"type": "need_round_proposal",
                                        "arm_id": "a1"}
    mcp_service.tournament_tool({
        "stage": "submit_proposal", **base,
        "arm_id": "a1", "proposal": {"params": {"a": 2}},
    })
    mcp_service.tournament_tool({"stage": "step", **base})   # hits target 0.92
    mcp_service.tournament_tool({"stage": "step", **base})   # finalize
    report = mcp_service.tournament_tool({"stage": "report", **base})
    assert report["winner"]["arm_id"] == "a1"
    assert report["stop"]["reason"] == "target_reached"


def test_tournament_tool_rejects_unknown_stage_and_outside_root(tmp_path, monkeypatch):
    monkeypatch.setenv("ML_RESEARCH_LOOP_ALLOWED_ROOTS", str(tmp_path))
    with pytest.raises(mcp_service.MCPToolError):
        mcp_service.tournament_tool({"stage": "nope",
                                     "runtime_root": str(tmp_path),
                                     "run_id": "x"})
    with pytest.raises(mcp_service.MCPToolError):
        mcp_service.tournament_tool({"stage": "status",
                                     "runtime_root": "/somewhere/else",
                                     "run_id": "x"})


def test_tournament_tool_is_registered():
    tools_by_name = {tool["name"]: tool for tool in mcp_service.tool_definitions()}
    assert "tournament" in tools_by_name
    stages = set(
        tools_by_name["tournament"]["inputSchema"]["properties"]["stage"]["enum"]
    )
    assert stages == {"start", "status", "submit_directions",
                      "submit_proposal", "step", "report"}
    assert tools_by_name["tournament"]["inputSchema"]["required"] == ["stage"]
    assert "tournament" in mcp_service.REQUIRED_TOOLS
    assert "tournament" in mcp_service.TOOL_CONTRACT_DESCRIPTIONS
