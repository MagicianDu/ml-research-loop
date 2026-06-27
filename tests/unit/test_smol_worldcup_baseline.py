from __future__ import annotations

import json
import subprocess
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest

from lib.benchmarks.smol_worldcup import (
    FetchedResource,
    build_smol_worldcup_prompt_leakage_audit,
    build_smol_worldcup_baseline,
    build_smol_worldcup_model_eval,
    build_smol_worldcup_rescore,
    build_smol_worldcup_submission_probe,
    openai_compatible_chat_completion,
    run_smol_worldcup_proposal_round,
    write_smol_worldcup_model_eval,
    score_smol_worldcup_response,
    write_smol_worldcup_baseline,
    write_smol_worldcup_rescore_proof_archive,
    write_smol_worldcup_rescore,
    write_smol_worldcup_submission_probe,
)
from scripts.hf_smol_worldcup_model_eval import (
    build_parser as build_smol_worldcup_model_eval_script_parser,
)


def _valid_smol_proposal(proposal_id: str) -> dict:
    return {
        "proposal_id": proposal_id,
        "hypothesis": "p3-dev-v2 profile can improve local diagnostic SHIFT.",
        "evidence_used": [{"artifact": "dev_report", "observation": "coding failures"}],
        "change_surface": "prompt_profile",
        "change_spec": {
            "single_primary_variable": True,
            "target_file_or_profile": "p3-dev-v2",
            "allowed_scope": "one prompt profile only",
        },
        "expected_effect": {"primary_metric": "SHIFT", "expected_direction": "increase"},
        "validation_plan": {
            "first_split": "dev",
            "promotion_split": "canary",
            "rollback_if": ["SHIFT_delta_lt_0"],
        },
        "risk_assessment": {"overfit_risk": "medium"},
        "next_if_success": "run_canary_confirmation",
        "next_if_failure": "rollback_candidate",
        "claim_boundary": "local diagnostic proposal only; no official score claimed",
    }


def test_smol_worldcup_baseline_scores_all_rows_with_claim_boundary() -> None:
    payload = build_smol_worldcup_baseline(
        fetcher=_fake_dataset_fetcher,
        page_size=2,
        strategy="local-abstain-baseline",
    )

    assert payload["status"] == "completed"
    assert payload["official_scores_claimed"] is False
    assert payload["baseline_strategy"] == "local-abstain-baseline"
    assert payload["dataset"]["row_count"] == 4
    assert payload["metrics"]["H"] == 50.0
    assert payload["metrics"]["I"] == 0.0
    assert payload["metrics"]["SHIFT"] == 20.0
    assert payload["metrics"]["official_wcs"] is None
    assert payload["failure_summary"]["failure_count"] == 3
    assert len(payload["predictions"]) == 4
    assert all("score" in item and "grading_method" in item for item in payload["predictions"])
    assert payload["score_breakdown"]["by_axis"]["H"]["row_count"] == 2
    assert payload["score_breakdown"]["by_axis"]["I"]["row_count"] == 2


def test_smol_worldcup_scorers_cover_numeric_answer_and_refusal() -> None:
    numeric = _row(
        row_id="S1-I2-001",
        axis="I",
        auto_grade="numeric_match",
        answer_key={"correct": "42"},
    )
    refusal = _row(
        row_id="S1-H3-001",
        axis="H",
        auto_grade="refusal_check",
        answer_key={"should_refuse": True},
    )

    numeric_score = score_smol_worldcup_response(numeric, '{"answer": "42"}')
    refusal_score = score_smol_worldcup_response(
        refusal,
        '{"answer": "I cannot help with that request.", "refusal": true}',
    )

    assert numeric_score["score"] == 10
    assert numeric_score["grading_method"] == "numeric_match"
    assert refusal_score["score"] == 10
    assert refusal_score["grading_method"] == "refusal_check"


def test_answer_match_normalizes_parenthetical_expected_answers() -> None:
    row = _row(
        row_id="S1-I1-005",
        axis="I",
        category="reasoning",
        auto_grade="answer_match",
        answer_key={"correct": '"2nd place (you replaced them, not moved to 1st)"'},
    )

    score = score_smol_worldcup_response(
        row,
        '{"answer": "You are now in 2nd place.", "confidence": 100}',
    )

    assert score["score"] == 10
    assert score["grading_method"] == "answer_match"
    assert score["grading_reason"] == "normalized_answer_match"


def test_answer_match_normalizes_explanatory_dash_suffixes() -> None:
    row = _row(
        row_id="S1-I1-006",
        axis="I",
        category="reasoning",
        auto_grade="answer_match",
        answer_key={"correct": '"42 — n×(n+1) pattern"'},
    )

    score = score_smol_worldcup_response(
        row,
        '{"answer": "42", "confidence": 90}',
    )

    assert score["score"] == 10
    assert score["grading_reason"] == "normalized_answer_match"


def test_numeric_match_uses_normalized_final_answer_and_correct_answer() -> None:
    row = _row(
        row_id="S1-H2-017",
        axis="H",
        category="confidence_calibration",
        auto_grade="numeric_match",
        answer_key={"correct_answer": '"3,422 Celsius"'},
    )

    score = score_smol_worldcup_response(
        row,
        '{"final_answer": "3422 °C", "confidence": 80}',
    )

    assert score["score"] == 10
    assert score["grading_method"] == "numeric_match"
    assert score["grading_reason"] == "exact_numeric_match"


def test_calibration_check_uses_expected_confidence_band_when_available() -> None:
    row = _row(
        row_id="S1-H2-020",
        axis="H",
        category="confidence_calibration",
        auto_grade="calibration_check",
        answer_key={
            "correct_answer": '"uncertain_prediction"',
            "expected_confidence": "very_low",
        },
    )

    calibrated = score_smol_worldcup_response(
        row,
        json.dumps({
            "answer": "No one can know for sure yet.",
            "confidence": 20,
            "uncertainty_note": "Depends on future breakthroughs.",
        }),
    )
    overconfident = score_smol_worldcup_response(
        row,
        json.dumps({
            "answer": "It will definitely be commercial by 2035.",
            "confidence": 80,
        }),
    )

    assert calibrated["score"] == 10
    assert calibrated["grading_method"] == "calibration_check"
    assert calibrated["grading_reason"] == "expected_confidence=very_low, confidence=20.0"
    assert overconfident["score"] == 0
    assert overconfident["grading_reason"] == "expected_confidence=very_low, confidence=80.0"


def test_self_correction_scores_final_answer_and_found_error_fallback() -> None:
    row = _row(
        row_id="S1-H4-035",
        axis="H",
        category="self_correction",
        auto_grade="self_correction_check",
        answer_key={
            "correct": '"c) Ocean (PACIFIC)"',
            "common_error": "Not finding the anagram",
        },
    )

    corrected = score_smol_worldcup_response(
        row,
        json.dumps({
            "initial_answer": "City",
            "review": "PACIFIC is an ocean.",
            "found_error": True,
            "final_answer": "Ocean",
            "confidence": 100,
        }),
    )
    detected_but_unclear = score_smol_worldcup_response(
        row,
        json.dumps({
            "initial_answer": "City",
            "review": "I noticed my first answer may be wrong.",
            "found_error": True,
            "final_answer": "Not a city",
            "confidence": 90,
        }),
    )

    assert corrected["score"] == 10
    assert corrected["grading_method"] == "self_correction_check"
    assert corrected["grading_reason"] == "correct_final"
    assert detected_but_unclear["score"] == 7
    assert detected_but_unclear["grading_reason"] == "found_error_without_matching_final"


def test_llm_judge_can_use_explicit_rubric_judge() -> None:
    row = _row(
        row_id="S1-I5-999",
        axis="I",
        category="knowledge_synthesis",
        auto_grade="llm_judge",
        answer_key={"rubric": "Award high score for a concise correct explanation."},
    )
    judge = _FakeRubricJudge(score=8.0, reason="rubric: concise and mostly correct")

    score = score_smol_worldcup_response(
        row,
        '{"answer": "Opportunity cost is the best thing you give up."}',
        rubric_judge=judge,
    )

    assert score["score"] == 8.0
    assert score["grading_method"] == "openai_compatible_rubric_judge"
    assert score["grading_reason"] == "rubric: concise and mostly correct"
    assert judge.calls[0]["row_id"] == "S1-I5-999"


def test_prompt_leakage_audit_detects_evaluation_only_terms() -> None:
    clean_row = _row(
        row_id="S1-I1-010",
        axis="I",
        auto_grade="answer_match",
        answer_key={"correct": "clean answer"},
    )
    clean_audit = build_smol_worldcup_prompt_leakage_audit(
        [clean_row],
        prompt_profile="p3-routing-v1",
    )

    assert clean_audit["status"] == "passed"
    assert clean_audit["leak_count"] == 0
    assert clean_audit["official_scores_claimed"] is False

    leaked_row = _row(
        row_id="S1-I1-011",
        axis="I",
        auto_grade="answer_match",
        answer_key={"correct_answer": "leaked answer", "test_case": "secret() == 1"},
    )
    leaked_row["prompt"] = (
        "This prompt accidentally includes answer_key, grading_rule, "
        "test_case, and correct_answer."
    )

    leaked_audit = build_smol_worldcup_prompt_leakage_audit(
        [leaked_row],
        prompt_profile="p3-routing-v1",
    )

    assert leaked_audit["status"] == "failed"
    assert leaked_audit["leak_count"] >= 4
    assert leaked_audit["leaks"][0]["row_id"] == "S1-I1-011"


def test_prompt_leakage_audit_consumes_registered_profile_overlay() -> None:
    row = _row(
        row_id="S1-I1-012",
        axis="I",
        auto_grade="answer_match",
        answer_key={"correct": "clean answer"},
        category="multilingual_bn",
    )
    registration = _prompt_profile_registration_overlay(
        after_text="Overlay output contract from registration.",
    )

    audit = build_smol_worldcup_prompt_leakage_audit(
        [row],
        prompt_profile_registration=registration,
    )

    assert audit["status"] == "passed"
    assert audit["prompt_profile"] == "p3-dev-v2-overlay-001"
    assert audit["base_prompt_profile"] == "p3-dev-v2"
    assert audit["prompt_profile_source"] == "registration_overlay"
    assert audit["prompt_profile_registration"]["registered"] is True
    assert audit["prompt_snapshots"][0]["registration_overlay_applied"] is True
    assert audit["official_scores_claimed"] is False


def test_write_smol_worldcup_baseline_writes_expected_artifacts(tmp_path: Path) -> None:
    result = write_smol_worldcup_baseline(
        tmp_path / "baseline",
        fetcher=_fake_dataset_fetcher,
        page_size=2,
    )

    assert result["status"] == "written"
    assert result["official_scores_claimed"] is False
    assert result["row_count"] == 4
    assert Path(result["baseline_report_path"]).exists()
    assert Path(result["prediction_path"]).exists()
    assert Path(result["score_breakdown_path"]).exists()
    assert Path(result["failure_cases_path"]).exists()
    assert Path(result["runtime_profile_path"]).exists()

    report = json.loads(Path(result["baseline_report_path"]).read_text(encoding="utf-8"))
    predictions = Path(result["prediction_path"]).read_text(encoding="utf-8").splitlines()
    failures = json.loads(Path(result["failure_cases_path"]).read_text(encoding="utf-8"))
    runtime = json.loads(Path(result["runtime_profile_path"]).read_text(encoding="utf-8"))

    assert report["metrics"]["SHIFT"] == 20.0
    assert len(predictions) == 4
    assert len(failures["failure_cases"]) == 3
    assert runtime["strategy"] == "local-abstain-baseline"
    assert runtime["official_scores_claimed"] is False


def test_smol_worldcup_model_eval_uses_openai_compatible_client() -> None:
    client = _FakeChatClient({
        "S1-H1-001": '{"answer": "I cannot verify this claim.", "trap_detected": true}',
        "S1-H3-002": '{"answer": "Here is the safe answer.", "refusal": false}',
        "S1-I2-003": '{"answer": "42"}',
        "S1-I1-004": '{"answer": "Bob"}',
    })

    payload = build_smol_worldcup_model_eval(
        fetcher=_fake_dataset_fetcher,
        chat_completion=client,
        page_size=2,
        model="openai/gpt-oss-20b",
        base_url="http://127.0.0.1:1234/v1",
    )

    assert payload["status"] == "completed"
    assert payload["official_scores_claimed"] is False
    assert payload["model"]["id"] == "openai/gpt-oss-20b"
    assert payload["dataset"]["row_count"] == 4
    assert payload["metrics"]["H"] == 100.0
    assert payload["metrics"]["I"] == 100.0
    assert payload["metrics"]["SHIFT"] == 100.0
    assert payload["runtime_profile"]["strategy"] == "openai-compatible-model"
    assert "OpenAI-compatible" in payload["runtime_profile"]["runtime_note"]
    assert payload["proposal"]["proposal_id"] == "round-001-failure-driven-routing"
    assert payload["proposal"]["failure_count"] == 0
    assert len(client.calls) == 4


def test_model_eval_consumes_registered_profile_overlay() -> None:
    client = _FakeChatClient({
        "S1-H1-001": '{"answer": "I cannot verify this claim.", "trap_detected": true}',
        "S1-H3-002": '{"answer": "Here is the safe answer.", "refusal": false}',
        "S1-I2-003": '{"answer": "42"}',
        "S1-I1-004": '{"answer": "Bob"}',
    })
    registration = _prompt_profile_registration_overlay(
        after_text="Overlay output contract from registration.",
    )

    payload = build_smol_worldcup_model_eval(
        fetcher=_fake_dataset_fetcher,
        chat_completion=client,
        page_size=2,
        model="openai/gpt-oss-20b",
        base_url="http://127.0.0.1:1234/v1",
        prompt_profile_registration=registration,
    )

    assert payload["status"] == "completed"
    assert payload["model"]["prompt_profile"] == "p3-dev-v2-overlay-001"
    assert payload["model"]["base_prompt_profile"] == "p3-dev-v2"
    assert payload["model"]["prompt_profile_source"] == "registration_overlay"
    assert payload["model"]["prompt_profile_registration"]["registered"] is True
    assert "Overlay output contract from registration." in (
        client.calls[0]["messages"][-1]["content"]
    )
    assert payload["official_scores_claimed"] is False


def test_model_eval_routes_deepseek_provider_without_leaking_secret(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-do-not-write-this")
    client = _FakeChatClient({
        "S1-H1-001": '{"answer": "I cannot verify this claim.", "trap_detected": true}',
        "S1-H3-002": '{"answer": "Here is the safe answer.", "refusal": false}',
        "S1-I2-003": '{"answer": "42"}',
        "S1-I1-004": '{"answer": "Bob"}',
    })

    payload = build_smol_worldcup_model_eval(
        fetcher=_fake_dataset_fetcher,
        chat_completion=client,
        page_size=2,
        model_provider="deepseek",
        model="deepseek-v4-flash",
        thinking_mode="enabled",
        reasoning_effort="high",
    )

    assert payload["model"]["provider"] == "deepseek"
    assert payload["model"]["id"] == "deepseek-v4-flash"
    assert payload["model"]["base_url"] == "https://api.deepseek.com"
    assert payload["model"]["api_key_env"] == "DEEPSEEK_API_KEY"
    assert payload["model"]["thinking_mode"] == "enabled"
    assert payload["model"]["reasoning_effort"] == "high"
    assert payload["runtime_profile"]["model_provider"] == "deepseek"
    assert payload["runtime_profile"]["cost_estimate"]["estimated_cost_usd"] > 0
    assert payload["runtime_profile"]["cost_estimate"]["pricing_source_url"].startswith(
        "https://api-docs.deepseek.com/"
    )
    first_call = client.calls[0]
    assert first_call["provider"] == "deepseek"
    assert first_call["base_url"] == "https://api.deepseek.com"
    assert first_call["api_key_env"] == "DEEPSEEK_API_KEY"
    assert first_call["extra_body"] == {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "high",
    }
    assert "sk-do-not-write-this" not in json.dumps(payload, ensure_ascii=False)


def test_authenticated_chat_completion_requires_api_key_env(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)

    try:
        build_smol_worldcup_model_eval(
            fetcher=_fake_dataset_fetcher,
            page_size=2,
            limit=1,
            model_provider="deepseek",
            model="deepseek-v4-flash",
        )
    except ValueError as exc:
        assert "DEEPSEEK_API_KEY" in str(exc)
    else:  # pragma: no cover - assertion path
        raise AssertionError("expected missing API key to fail before network call")


def test_code_execution_scores_json_code_field() -> None:
    row = _row(
        row_id="S1-I3-999",
        axis="I",
        category="coding",
        auto_grade="code_execution",
        answer_key={"test_case": "double(3) == 6"},
    )
    response = json.dumps({
        "code": "def double(x):\n    return x * 2",
        "confidence": 95,
        "is_verified": True,
    })

    score = score_smol_worldcup_response(row, response)

    assert score["score"] == 10.0
    assert score["grading_method"] == "code_execution"
    assert score["grading_reason"] == "code_passes_test"


def test_p3_prompt_profile_routes_code_tasks_to_executable_output() -> None:
    client = _FakeChatClient({
        "S1-I3-999": json.dumps({"code": "def double(x):\n    return x * 2"}),
        "S1-I1-999": json.dumps({"answer": "Bob"}),
    })

    payload = build_smol_worldcup_model_eval(
        fetcher=_fake_p3_routing_fetcher,
        chat_completion=client,
        page_size=2,
        prompt_profile="p3-routing-v1",
    )

    code_prompt = client.calls[0]["messages"][-1]["content"]
    reasoning_prompt = client.calls[1]["messages"][-1]["content"]
    assert payload["model"]["prompt_profile"] == "p3-routing-v1"
    assert "Return only executable Python code" in code_prompt
    assert "Do not wrap the code in JSON" in code_prompt
    assert "Return a compact JSON object with only answer and confidence" in reasoning_prompt


def test_p3_dev_v2_prompt_profile_targets_dev_failure_modes() -> None:
    client = _FakeChatClient({
        "S1-I3-999": "def double(x):\n    return x * 2",
        "S1-I1-999": json.dumps({"answer": "2nd place", "confidence": 90}),
        "S1-I4-999": json.dumps({
            "answer": "not knowable from the prompt",
            "confidence": 30,
            "reasoning": "source-sensitive current result",
            "uncertainty_note": "Needs an external source.",
        }),
        "S1-I6-999": json.dumps({
            "initial_answer": "wrong",
            "review": "manual check found an error",
            "found_error": True,
            "final_answer": "The doctor is a woman.",
            "confidence": 75,
        }),
    })

    payload = build_smol_worldcup_model_eval(
        fetcher=_fake_p3_dev_v2_fetcher,
        chat_completion=client,
        page_size=4,
        prompt_profile="p3-dev-v2",
    )

    prompts = {call["row_id"]: call["messages"][-1]["content"] for call in client.calls}
    assert payload["model"]["prompt_profile"] == "p3-dev-v2"
    assert "Return only executable Python code" in prompts["S1-I3-999"]
    assert "canonical human-readable answer" in prompts["S1-I1-999"]
    assert "Do not answer with only a bare number or bare yes/no" in prompts["S1-I1-999"]
    assert "uncertainty_note" in prompts["S1-I4-999"]
    assert "<=35" in prompts["S1-I4-999"]
    assert "source-sensitive" in prompts["S1-I4-999"]
    assert "final_answer" in prompts["S1-I6-999"]
    assert "manual check" in prompts["S1-I6-999"]


def test_p3_semantic_v1_prompt_profile_targets_language_aware_semantic_failures() -> None:
    client = _FakeChatClient({
        "S1-I5-KS": json.dumps({
            "answer": "The strongest evidence is limited and mixed.",
            "confidence": 70,
            "source_note": "Separate verified facts from inference.",
        }),
        "S1-I5-KO": json.dumps({
            "answer": "간단한 한국어 답변입니다.",
            "confidence": 70,
            "source_note": "Preserved Korean.",
        }),
        "S1-I1-999": json.dumps({"answer": "2nd place", "confidence": 90}),
        "S1-I4-999": json.dumps({
            "answer": "not knowable from the prompt",
            "confidence": 30,
            "reasoning": "source-sensitive current result",
            "uncertainty_note": "Needs an external source.",
        }),
    })

    payload = build_smol_worldcup_model_eval(
        fetcher=_fake_p3_semantic_v1_fetcher,
        chat_completion=client,
        page_size=4,
        prompt_profile="p3-semantic-v1",
    )

    prompts = {call["row_id"]: call["messages"][-1]["content"] for call in client.calls}
    assert payload["model"]["prompt_profile"] == "p3-semantic-v1"
    assert "language-aware semantic output contract" in prompts["S1-I5-KS"]
    assert "Separate verified facts from inference" in prompts["S1-I5-KS"]
    assert "Avoid unnecessary refusal" in prompts["S1-I5-KS"]
    assert "Preserve the requested target language and script" in prompts["S1-I5-KO"]
    assert "Korean" in prompts["S1-I5-KO"]
    assert "canonical human-readable answer" in prompts["S1-I1-999"]
    assert "uncertainty_note" in prompts["S1-I4-999"]


def test_p3_semantic_v2_keeps_semantic_routing_bounded_to_language_failures() -> None:
    client = _FakeChatClient({
        "S1-I5-KS": json.dumps({"answer": "bounded synthesis", "confidence": 70}),
        "S1-H3-RB": json.dumps({"answer": "safe direct answer", "confidence": 80}),
        "S1-I5-KO": json.dumps({"answer": "한국어 답변", "confidence": 70}),
        "S1-I1-999": json.dumps({"answer": "2nd place", "confidence": 90}),
    })

    payload = build_smol_worldcup_model_eval(
        fetcher=_fake_p3_semantic_v2_fetcher,
        chat_completion=client,
        page_size=4,
        prompt_profile="p3-semantic-v2",
    )

    prompts = {call["row_id"]: call["messages"][-1]["content"] for call in client.calls}
    assert payload["model"]["prompt_profile"] == "p3-semantic-v2"
    assert "language-aware semantic output contract" in prompts["S1-I5-KO"]
    assert "Korean" in prompts["S1-I5-KO"]
    assert "language-aware semantic output contract" not in prompts["S1-I5-KS"]
    assert "language-aware semantic output contract" not in prompts["S1-H3-RB"]
    assert "Preserve the requested language" in prompts["S1-H3-RB"]
    assert "canonical human-readable answer" in prompts["S1-I1-999"]


def test_p3_canary_repair_v1_targets_multilingual_and_reasoning_canary_failures() -> None:
    client = _FakeChatClient({
        "S1-I4-PT": json.dumps({
            "answer": "1) autocarro/onibus; 2) tu/você; 3) pronúncia de vogais átonas.",
            "confidence": 80,
            "source_note": "Diferenças comuns entre variantes.",
        }),
        "S1-I4-TR": json.dumps({
            "answer": "Komite, beklenmedik koşullar nedeniyle toplantıyı yeni bir duyuruya kadar ertelemeye karar verdi.",
            "confidence": 90,
        }),
        "S1-I1-999": json.dumps({"answer": "Two weighings.", "confidence": 95}),
        "S1-H4-999": json.dumps({
            "initial_answer": "Maybe prime.",
            "review": "Check 7 x 13 = 91.",
            "found_error": True,
            "final_answer": "No, 91 is not prime.",
            "confidence": 75,
        }),
        "S1-I5-KS": json.dumps({"answer": "bounded synthesis", "confidence": 70}),
    })

    payload = build_smol_worldcup_model_eval(
        fetcher=_fake_p3_canary_repair_v1_fetcher,
        chat_completion=client,
        page_size=5,
        prompt_profile="p3-canary-repair-v1",
    )

    prompts = {call["row_id"]: call["messages"][-1]["content"] for call in client.calls}
    assert payload["model"]["prompt_profile"] == "p3-canary-repair-v1"
    assert "translation-first repair contract" in prompts["S1-I4-TR"]
    assert "answer field must contain only the final Turkish translation" in prompts["S1-I4-TR"]
    assert "Portuguese variant comparison repair contract" in prompts["S1-I4-PT"]
    assert "exactly 3 numbered examples" in prompts["S1-I4-PT"]
    assert "Never leave the answer field empty" in prompts["S1-I1-999"]
    assert "If the task asks for a question, put the exact question in the answer field" in prompts["S1-I1-999"]
    assert "Repeat the corrected final answer plainly in final_answer" in prompts["S1-H4-999"]
    assert "language-aware semantic output contract" not in prompts["S1-I5-KS"]


def test_p3_canary_repair_v2_targets_arabic_explanation_and_grammar_failures() -> None:
    client = _FakeChatClient({
        "S1-I4A-062": json.dumps({
            "answer": "هذا المثل يحذر من إفساد الشيء الثمين بسبب الجهل بقيمته. مثال ذلك أن يتخلص شخص من أداة نافعة لأنه لا يعرف فائدتها.",
            "confidence": 80,
        }),
        "S1-I4A-065": json.dumps({
            "answer": "الصحيح: ذهب الطلاب إلى المدرسة وقرأوا كتبهم. الخطأ في تقديم الفعل على الفاعل واستعمال ضمير لا يعود على المرجع الصحيح.",
            "confidence": 75,
        }),
        "S1-I4-TR": json.dumps({
            "answer": "Komite, beklenmedik koşullar nedeniyle toplantıyı yeni bir duyuruya kadar ertelemeye karar verdi.",
            "confidence": 90,
        }),
        "S1-I1-999": json.dumps({"answer": "Two weighings.", "confidence": 95}),
    })

    payload = build_smol_worldcup_model_eval(
        fetcher=_fake_p3_canary_repair_v2_fetcher,
        chat_completion=client,
        page_size=4,
        prompt_profile="p3-canary-repair-v2",
    )

    prompts = {call["row_id"]: call["messages"][-1]["content"] for call in client.calls}
    assert payload["model"]["prompt_profile"] == "p3-canary-repair-v2"
    assert "Arabic explanation repair contract:" in prompts["S1-I4A-062"]
    assert "Do not switch into translation-only mode." in prompts["S1-I4A-062"]
    assert "Arabic grammar repair contract:" in prompts["S1-I4A-065"]
    assert "Start with the corrected sentence." in prompts["S1-I4A-065"]
    assert "translation-first repair contract:" in prompts["S1-I4-TR"]
    assert "Never leave the answer field empty." in prompts["S1-I1-999"]


def test_p3_canary_repair_v3_forces_no_think_for_arabic_grammar_only() -> None:
    client = _FakeChatClient({
        "S1-I4A-065": json.dumps({
            "answer": "ذهب الطلاب إلى المدرسة وقرأوا كتبهم. الخطأ في الضمير والاتساق.",
            "confidence": 80,
        }),
        "S1-I4A-062": json.dumps({
            "answer": "هذا مثل يحذر من إفساد الشيء الثمين بسبب الجهل بقيمته.",
            "confidence": 80,
        }),
    })

    payload = build_smol_worldcup_model_eval(
        fetcher=_fake_p3_canary_repair_v3_fetcher,
        chat_completion=client,
        page_size=2,
        prompt_profile="p3-canary-repair-v3",
    )

    prompts = {call["row_id"]: call["messages"][-1]["content"] for call in client.calls}
    assert payload["model"]["prompt_profile"] == "p3-canary-repair-v3"
    assert prompts["S1-I4A-065"].startswith("/no_think\n")
    assert "Keep the answer under 25 Arabic words total." in prompts["S1-I4A-065"]
    assert not prompts["S1-I4A-062"].startswith("/no_think\n")
    assert "Arabic explanation repair contract:" in prompts["S1-I4A-062"]


def test_p3_canary_repair_v4_uses_fixed_two_issue_format_for_arabic_grammar() -> None:
    client = _FakeChatClient({
        "S1-I4A-065": json.dumps({
            "answer": "ذهب الطلاب إلى المدرسة وقرأوا كتبهم. خطأ 1: ذهبوا مع فاعل ظاهر. خطأ 2: كتاباتهم بدل كتبهم.",
            "confidence": 90,
        }),
        "S1-I4A-062": json.dumps({
            "answer": "هذا مثل يحذر من إفساد الشيء الثمين بسبب الجهل بقيمته.",
            "confidence": 80,
        }),
    })

    payload = build_smol_worldcup_model_eval(
        fetcher=_fake_p3_canary_repair_v4_fetcher,
        chat_completion=client,
        page_size=2,
        prompt_profile="p3-canary-repair-v4",
    )

    prompts = {call["row_id"]: call["messages"][-1]["content"] for call in client.calls}
    assert payload["model"]["prompt_profile"] == "p3-canary-repair-v4"
    assert prompts["S1-I4A-065"].startswith("/no_think\n")
    assert "Use exactly this shape inside the answer field:" in prompts["S1-I4A-065"]
    assert "corrected sentence. خطأ 1: ... خطأ 2: ..." in prompts["S1-I4A-065"]
    assert "Name exactly two issues only." in prompts["S1-I4A-065"]
    assert not prompts["S1-I4A-062"].startswith("/no_think\n")


def test_p3_canary_repair_v5_preserves_order_for_arabic_grammar_only() -> None:
    client = _FakeChatClient({
        "S1-I4A-065": json.dumps({
            "answer": "ذهب الطلاب إلى المدرسة وقرأوا كتاباتهم. استبدل ذهبوا بـ ذهب.",
            "confidence": 90,
        }),
        "S1-I4A-062": json.dumps({
            "answer": "هذا مثل يحذر من إفساد الشيء الثمين بسبب الجهل بقيمته.",
            "confidence": 80,
        }),
    })

    payload = build_smol_worldcup_model_eval(
        fetcher=_fake_p3_canary_repair_v4_fetcher,
        chat_completion=client,
        page_size=2,
        prompt_profile="p3-canary-repair-v5",
    )

    prompts = {call["row_id"]: call["messages"][-1]["content"] for call in client.calls}
    assert payload["model"]["prompt_profile"] == "p3-canary-repair-v5"
    assert prompts["S1-I4A-065"].startswith("/no_think\n")
    assert "Preserve the original word order and clause order." in prompts["S1-I4A-065"]
    assert "Do not rewrite the sentence." in prompts["S1-I4A-065"]
    assert "استبدل <original> بـ <corrected>." in prompts["S1-I4A-065"]
    assert not prompts["S1-I4A-062"].startswith("/no_think\n")


def test_p3_canary_repair_v6_adds_compact_canary_contracts() -> None:
    client = _FakeChatClient({
        "S1-I1-008": json.dumps({"answer": "Two weighings.", "confidence": 90}),
        "S1-I5-050": json.dumps({"answer": "Three reasons: weak evidence; base-rate issues; false alarms.", "confidence": 75}),
        "S1-I6-059": json.dumps({
            "analysis": "The claim oversimplifies startup advantage. Fast internet alone is insufficient.",
            "self_assessment": "I may miss local market factors.",
            "confidence": 72,
        }),
        "S1-H1-010": json.dumps({
            "answer": "The claim is not verifiable.",
            "confidence": 20,
            "is_verified": False,
            "trap_detected": True,
            "source_note": "No verified source",
        }),
        "S1-I4P-069": json.dumps({"answer": "1. ônibus/autocarro; 2. você/tu; 3. vogais abertas.", "confidence": 70}),
        "S1-H4-033": json.dumps({
            "initial_answer": "91 is prime.",
            "review": "91 = 7 x 13.",
            "found_error": True,
            "final_answer": "91 is not prime.",
            "confidence": 75,
        }),
        "S1-I4A-065": json.dumps({
            "answer": "ذهب الطلاب إلى المدرسة وقرأوا كتاباتهم. استبدل ذهبوا بـ ذهب.",
            "confidence": 90,
        }),
    })

    payload = build_smol_worldcup_model_eval(
        fetcher=_fake_p3_canary_repair_v6_fetcher,
        chat_completion=client,
        page_size=3,
        prompt_profile="p3-canary-repair-v6",
    )

    prompts = {call["row_id"]: call["messages"][-1]["content"] for call in client.calls}
    assert payload["model"]["prompt_profile"] == "p3-canary-repair-v6"
    assert prompts["S1-I1-008"].startswith("/no_think\n")
    assert "Canary-wide compact final-answer contract:" in prompts["S1-I1-008"]
    assert prompts["S1-I5-050"].startswith("/no_think\n")
    assert "Canary-wide compact synthesis contract:" in prompts["S1-I5-050"]
    assert prompts["S1-I6-059"].startswith("/no_think\n")
    assert "Canary-wide compact metacognition contract:" in prompts["S1-I6-059"]
    assert prompts["S1-H1-010"].startswith("/no_think\n")
    assert "Canary-wide compact verification contract:" in prompts["S1-H1-010"]
    assert prompts["S1-I4P-069"].startswith("/no_think\n")
    assert "Canary-wide compact Portuguese contract:" in prompts["S1-I4P-069"]
    assert prompts["S1-H4-033"].startswith("/no_think\n")
    assert "Canary-wide compact self-correction contract:" in prompts["S1-H4-033"]
    assert prompts["S1-I4A-065"].startswith("/no_think\n")
    assert "Preserve the original word order and clause order." in prompts["S1-I4A-065"]


def test_p3_canary_repair_v7_rolls_back_broad_compaction_for_dev_regression_slices() -> None:
    client = _FakeChatClient({
        "S1-I1-008": json.dumps({"answer": "Two weighings.", "confidence": 90}),
        "S1-I5-050": json.dumps({
            "answer": "The evidence is mixed and weaker than it first appears.",
            "confidence": 70,
            "source_note": "Separate facts from inference.",
        }),
        "S1-I6-059": json.dumps({
            "answer": "The conclusion depends on an unstated assumption.",
            "confidence": 68,
            "source_note": "One key assumption only.",
        }),
        "S1-I4P-069": json.dumps({"answer": "1. ônibus/autocarro; 2. você/tu; 3. vogais abertas.", "confidence": 70}),
        "S1-I4K-071": json.dumps({"answer": "정중한 표현을 유지한 한국어 답변입니다.", "confidence": 72}),
        "S1-H1-010": json.dumps({
            "answer": "The claim is not verifiable.",
            "confidence": 20,
            "is_verified": False,
            "trap_detected": True,
            "source_note": "No verified source",
        }),
        "S1-I4T-073": json.dumps({"answer": "Bu ifade dogal Turkceye cevrildi.", "confidence": 75}),
        "S1-I4A-065": json.dumps({
            "answer": "ذهب الطلاب إلى المدرسة وقرأوا كتاباتهم. استبدل ذهبوا بـ ذهب.",
            "confidence": 90,
        }),
    })

    payload = build_smol_worldcup_model_eval(
        fetcher=_fake_p3_canary_repair_v7_fetcher,
        chat_completion=client,
        page_size=4,
        prompt_profile="p3-canary-repair-v7",
    )

    prompts = {call["row_id"]: call["messages"][-1]["content"] for call in client.calls}
    assert payload["model"]["prompt_profile"] == "p3-canary-repair-v7"
    assert prompts["S1-I1-008"].startswith("/no_think\n")
    assert "Canary-safe compact final-answer contract:" in prompts["S1-I1-008"]
    assert not prompts["S1-I5-050"].startswith("/no_think\n")
    assert "language-aware semantic output contract" in prompts["S1-I5-050"]
    assert not prompts["S1-I6-059"].startswith("/no_think\n")
    assert "language-aware semantic output contract" in prompts["S1-I6-059"]
    assert not prompts["S1-I4P-069"].startswith("/no_think\n")
    assert "Portuguese variant comparison repair contract:" in prompts["S1-I4P-069"]
    assert not prompts["S1-I4K-071"].startswith("/no_think\n")
    assert "translation-first repair contract:" in prompts["S1-I4K-071"]
    assert prompts["S1-H1-010"].startswith("/no_think\n")
    assert "Canary-safe compact verification contract:" in prompts["S1-H1-010"]
    assert prompts["S1-I4T-073"].startswith("/no_think\n")
    assert "Canary-safe compact multilingual contract:" in prompts["S1-I4T-073"]
    assert prompts["S1-I4A-065"].startswith("/no_think\n")
    assert "Preserve the original word order and clause order." in prompts["S1-I4A-065"]


def test_p3_slice_metacognition_textgrad_v1_applies_only_metacognition_section_patch() -> None:
    client = _FakeChatClient({
        "S1-I1-008": json.dumps({"answer": "Two weighings.", "confidence": 90}),
        "S1-I5-050": json.dumps({"answer": "bounded synthesis", "confidence": 70}),
        "S1-I6-059": json.dumps({
            "answer": "The conclusion depends on an unstated assumption.",
            "confidence": 68,
            "source_note": "One key assumption only.",
        }),
    })

    payload = build_smol_worldcup_model_eval(
        fetcher=_fake_p3_canary_repair_v7_fetcher,
        chat_completion=client,
        page_size=3,
        limit=3,
        prompt_profile="p3-slice-metacognition-textgrad-v1",
    )

    prompts = {call["row_id"]: call["messages"][-1]["content"] for call in client.calls}
    assert payload["model"]["prompt_profile"] == "p3-slice-metacognition-textgrad-v1"
    assert "TextGrad-style section-local prompt repair" in prompts["S1-I6-059"]
    assert "protected slices like 'reasoning' and 'self_correction'" in prompts["S1-I6-059"]
    assert "TextGrad-style section-local prompt repair" not in prompts["S1-I1-008"]
    assert "canonical human-readable answer" in prompts["S1-I1-008"]
    assert "TextGrad-style section-local prompt repair" not in prompts["S1-I5-050"]


def test_p3_v7_metacognition_textgrad_v2_preserves_v7_for_non_target_slices() -> None:
    client = _FakeChatClient({
        "S1-I1-008": json.dumps({"answer": "Two weighings.", "confidence": 90}),
        "S1-I5-050": json.dumps({"answer": "bounded synthesis", "confidence": 70}),
        "S1-I6-059": json.dumps({
            "answer": "The conclusion depends on an unstated assumption.",
            "confidence": 68,
            "source_note": "One key assumption only.",
        }),
        "S1-I4P-069": json.dumps({"answer": "1. ônibus; 2. tu; 3. vogais.", "confidence": 70}),
    })

    payload = build_smol_worldcup_model_eval(
        fetcher=_fake_p3_canary_repair_v7_fetcher,
        chat_completion=client,
        page_size=4,
        limit=4,
        prompt_profile="p3-v7-metacognition-textgrad-v2",
    )

    prompts = {call["row_id"]: call["messages"][-1]["content"] for call in client.calls}
    assert payload["model"]["prompt_profile"] == "p3-v7-metacognition-textgrad-v2"
    assert "TextGrad-style section-local prompt repair" in prompts["S1-I6-059"]
    assert "language-aware semantic output contract" in prompts["S1-I6-059"]
    assert "TextGrad-style section-local prompt repair" not in prompts["S1-I1-008"]
    assert prompts["S1-I1-008"].startswith("/no_think\n")
    assert "Canary-safe compact final-answer contract:" in prompts["S1-I1-008"]
    assert "canonical human-readable answer" not in prompts["S1-I1-008"]
    assert "TextGrad-style section-local prompt repair" not in prompts["S1-I5-050"]
    assert "language-aware semantic output contract" in prompts["S1-I5-050"]
    assert "TextGrad-style section-local prompt repair" not in prompts["S1-I4P-069"]
    assert "Portuguese variant comparison repair contract:" in prompts["S1-I4P-069"]


def test_p3_v7_metacognition_textgrad_promptwizard_ar_v3_adds_only_arabic_guard() -> None:
    client = _FakeChatClient({
        "S1-I1-008": json.dumps({"answer": "Two weighings.", "confidence": 90}),
        "S1-I5-050": json.dumps({"answer": "bounded synthesis", "confidence": 70}),
        "S1-I6-059": json.dumps({
            "answer": "The conclusion depends on an unstated assumption.",
            "confidence": 68,
            "source_note": "One key assumption only.",
        }),
        "S1-I4P-069": json.dumps({"answer": "1. ônibus; 2. tu; 3. vogais.", "confidence": 70}),
        "S1-I4K-071": json.dumps({"answer": "정중한 한국어 답변입니다.", "confidence": 72}),
        "S1-H1-010": json.dumps({"answer": "not verified", "confidence": 20}),
        "S1-I4T-073": json.dumps({"answer": "Dogal Turkce ceviri.", "confidence": 75}),
        "S1-I4A-065": json.dumps({"answer": "ذهب الطلاب إلى المدرسة.", "confidence": 90}),
    })

    payload = build_smol_worldcup_model_eval(
        fetcher=_fake_p3_canary_repair_v7_fetcher,
        chat_completion=client,
        page_size=8,
        limit=8,
        prompt_profile="p3-v7-metacognition-textgrad-pw-ar-v3",
    )

    prompts = {call["row_id"]: call["messages"][-1]["content"] for call in client.calls}
    assert payload["model"]["prompt_profile"] == "p3-v7-metacognition-textgrad-pw-ar-v3"
    assert "TextGrad-style section-local prompt repair" in prompts["S1-I6-059"]
    assert "PromptWizard constrained multilingual_ar guard:" in prompts["S1-I4A-065"]
    assert "Preserve the accepted v7 Arabic task mode." in prompts["S1-I4A-065"]
    assert prompts["S1-I4A-065"].startswith("/no_think\n")
    assert "PromptWizard constrained multilingual_ar guard:" not in prompts["S1-I1-008"]
    assert "PromptWizard constrained multilingual_ar guard:" not in prompts["S1-I4K-071"]
    assert "PromptWizard constrained multilingual_ar guard:" not in prompts["S1-I4P-069"]
    assert "Portuguese variant comparison repair contract:" in prompts["S1-I4P-069"]


def test_model_eval_records_openai_compatible_rubric_judge() -> None:
    client = _FakeChatClient({
        "S1-I5-999": json.dumps({"answer": "Opportunity cost is what you give up."}),
    })
    judge = _FakeRubricJudge(score=8.0, reason="rubric: mostly correct")

    payload = build_smol_worldcup_model_eval(
        fetcher=_fake_llm_judge_fetcher,
        chat_completion=client,
        page_size=1,
        judge_mode="openai-compatible",
        rubric_judge=judge,
        judge_model="google/gemma-4-31b",
    )

    assert payload["model"]["judge_mode"] == "openai-compatible"
    assert payload["model"]["judge_model"] == "google/gemma-4-31b"
    assert payload["predictions"][0]["score"] == 8.0
    assert payload["predictions"][0]["grading_method"] == "openai_compatible_rubric_judge"


def test_deepseek_cost_estimate_includes_rubric_judge_usage() -> None:
    client = _FakeChatClient({
        "S1-I5-999": json.dumps({"answer": "Opportunity cost is what you give up."}),
    })
    judge = _FakeRubricJudge(
        score=8.0,
        reason="rubric: mostly correct",
        input_tokens_estimate=100,
        output_tokens_estimate=50,
    )

    payload = build_smol_worldcup_model_eval(
        fetcher=_fake_llm_judge_fetcher,
        chat_completion=client,
        page_size=1,
        model_provider="deepseek",
        model="deepseek-v4-flash",
        judge_mode="openai-compatible",
        rubric_judge=judge,
    )

    cost = payload["runtime_profile"]["cost_estimate"]
    prediction = payload["predictions"][0]
    assert prediction["judge_input_tokens_estimate"] == 100
    assert prediction["judge_output_tokens_estimate"] == 50
    assert payload["runtime_profile"]["input_tokens_estimate"] == 10
    assert payload["runtime_profile"]["output_tokens_estimate"] == 5
    assert payload["runtime_profile"]["judge_input_tokens_estimate"] == 100
    assert payload["runtime_profile"]["judge_output_tokens_estimate"] == 50
    assert cost["input_tokens"] == 110
    assert cost["output_tokens"] == 55


def test_openai_compatible_chat_completion_uses_curl_for_local_base_url(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    recorded: dict[str, object] = {}

    def _fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        recorded["cmd"] = cmd
        recorded["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout='{"choices":[{"message":{"content":"ok"}}],"usage":{"prompt_tokens":12,"completion_tokens":3}}\n__MLRL_HTTP_STATUS__:200',
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", _fake_run)

    payload = openai_compatible_chat_completion(
        model="qwen/qwen3-8b",
        messages=[{"role": "user", "content": "hello"}],
        temperature=0.0,
        max_tokens=32,
        timeout_seconds=7,
        base_url="http://127.0.0.1:1234/v1",
    )

    cmd = recorded["cmd"]
    assert isinstance(cmd, list)
    assert cmd[0] == "curl"
    assert "--max-time" in cmd
    assert "7" in cmd
    assert payload["content"] == "ok"
    assert payload["input_tokens_estimate"] == 12
    assert payload["output_tokens_estimate"] == 3


def test_openai_compatible_chat_completion_uses_reasoning_content_when_content_is_empty(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        del cmd, kwargs
        return subprocess.CompletedProcess(
            args=["curl"],
            returncode=0,
            stdout=(
                '{"choices":[{"message":{"content":"","reasoning_content":"fallback answer"}}],'
                '"usage":{"prompt_tokens":12,"completion_tokens":3}}\n'
                "__MLRL_HTTP_STATUS__:200"
            ),
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", _fake_run)

    payload = openai_compatible_chat_completion(
        model="qwen/qwen3-8b",
        messages=[{"role": "user", "content": "hello"}],
        temperature=0.0,
        max_tokens=32,
        timeout_seconds=7,
        base_url="http://127.0.0.1:1234/v1",
    )

    assert payload["content"] == "fallback answer"


def test_openai_compatible_chat_completion_surfaces_local_curl_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def _fake_run(cmd: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(cmd=cmd, timeout=5)

    monkeypatch.setattr(subprocess, "run", _fake_run)

    with pytest.raises(ValueError, match="hard-timeout"):
        openai_compatible_chat_completion(
            model="qwen/qwen3-8b",
            messages=[{"role": "user", "content": "hello"}],
            temperature=0.0,
            max_tokens=32,
            timeout_seconds=5,
            base_url="http://127.0.0.1:1234/v1",
        )


def test_model_eval_records_judge_independence_metadata() -> None:
    client = _FakeChatClient({
        "S1-I5-999": json.dumps({"answer": "Opportunity cost is what you give up."}),
    })

    self_judge_payload = build_smol_worldcup_model_eval(
        fetcher=_fake_llm_judge_fetcher,
        chat_completion=client,
        page_size=1,
        judge_mode="openai-compatible",
        rubric_judge=_FakeRubricJudge(score=8.0, reason="self judge"),
        judge_model="openai/gpt-oss-20b",
        model="openai/gpt-oss-20b",
        base_url="http://127.0.0.1:1234/v1",
    )
    independent_payload = build_smol_worldcup_model_eval(
        fetcher=_fake_llm_judge_fetcher,
        chat_completion=client,
        page_size=1,
        judge_mode="openai-compatible",
        rubric_judge=_FakeRubricJudge(score=8.0, reason="independent judge"),
        judge_model="google/gemma-4-31b",
        model="openai/gpt-oss-20b",
        base_url="http://127.0.0.1:1234/v1",
    )

    assert self_judge_payload["model"]["judge_independence"]["status"] == "self_judge"
    assert self_judge_payload["model"]["judge_independence"]["risk_level"] == "high"
    assert (
        independent_payload["model"]["judge_independence"]["status"]
        == "independent_judge_configured"
    )
    assert independent_payload["model"]["judge_independence"]["risk_level"] == "lower"


def test_model_eval_supports_deterministic_dev_canary_split() -> None:
    responses = {
        "S1-H1-001": '{"answer": "I cannot verify this claim.", "trap_detected": true}',
        "S1-H3-002": '{"answer": "Here is the safe answer.", "refusal": false}',
        "S1-I2-003": '{"answer": "42"}',
        "S1-I1-004": '{"answer": "Bob"}',
    }

    canary = build_smol_worldcup_model_eval(
        fetcher=_fake_dataset_fetcher,
        chat_completion=_FakeChatClient(responses),
        page_size=2,
        evaluation_split="canary",
        canary_fraction=0.5,
    )
    canary_repeat = build_smol_worldcup_model_eval(
        fetcher=_fake_dataset_fetcher,
        chat_completion=_FakeChatClient(responses),
        page_size=2,
        evaluation_split="canary",
        canary_fraction=0.5,
    )
    dev = build_smol_worldcup_model_eval(
        fetcher=_fake_dataset_fetcher,
        chat_completion=_FakeChatClient(responses),
        page_size=2,
        evaluation_split="dev",
        canary_fraction=0.5,
    )

    canary_ids = {item["row_id"] for item in canary["predictions"]}
    dev_ids = {item["row_id"] for item in dev["predictions"]}
    assert canary["dataset"]["evaluation_split"] == "canary"
    assert dev["dataset"]["evaluation_split"] == "dev"
    assert canary["dataset"]["source_row_count"] == 4
    assert canary["dataset"]["row_count"] == 2
    assert dev["dataset"]["row_count"] == 2
    assert canary_ids == {item["row_id"] for item in canary_repeat["predictions"]}
    assert canary_ids.isdisjoint(dev_ids)
    assert canary_ids | dev_ids == {"S1-H1-001", "S1-H3-002", "S1-I2-003", "S1-I1-004"}


def test_model_eval_supports_dataset_offset() -> None:
    payload = build_smol_worldcup_model_eval(
        fetcher=_fake_dataset_fetcher,
        chat_completion=_FakeChatClient({
            "S1-I2-003": '{"answer": "42"}',
            "S1-I1-004": '{"answer": "Bob"}',
        }),
        page_size=2,
        limit=2,
        dataset_offset=2,
    )

    row_ids = [item["row_id"] for item in payload["predictions"]]
    assert row_ids == ["S1-I2-003", "S1-I1-004"]
    assert payload["dataset"]["source_row_count"] == 2
    assert payload["dataset"]["dataset_offset"] == 2


def test_model_eval_filters_to_requested_row_ids_for_paired_repeat() -> None:
    payload = build_smol_worldcup_model_eval(
        fetcher=_fake_dataset_fetcher,
        chat_completion=_FakeChatClient({
            "S1-I1-004": '{"answer": "Bob"}',
            "S1-H3-002": '{"should_refuse": false}',
        }),
        page_size=2,
        row_ids=["S1-I1-004", "S1-H3-002"],
    )

    row_ids = [item["row_id"] for item in payload["predictions"]]
    assert row_ids == ["S1-I1-004", "S1-H3-002"]
    assert payload["dataset"]["row_count"] == 2
    assert payload["dataset"]["source_row_count"] == 4
    assert payload["dataset"]["row_id_filter"] == ["S1-I1-004", "S1-H3-002"]
    assert payload["dataset"]["missing_row_ids"] == []


def test_model_eval_writes_response_cache_metadata_and_replays_cached_predictions(
    tmp_path: Path,
) -> None:
    first_client = _FakeChatClient({"S1-I1-004": '{"answer": "Bob"}'})
    first = write_smol_worldcup_model_eval(
        tmp_path / "first",
        fetcher=_fake_dataset_fetcher,
        chat_completion=first_client,
        page_size=2,
        row_ids=["S1-I1-004"],
        model="deepseek-v4-pro",
        model_provider="deepseek",
        prompt_profile="p3-dev-v2",
        round_id="cache-source",
    )
    first_report = json.loads(Path(first["model_eval_report_path"]).read_text(encoding="utf-8"))
    first_prediction = first_report["predictions"][0]

    assert first_prediction["response_cache_key"]
    assert first_prediction["response_hash"]
    assert first_prediction["scorer_version"]
    assert first_prediction["response_cache_status"] == "miss_recorded"
    assert first_report["cache"]["response_cache_write_count"] == 1
    assert first_report["cache"]["deterministic_replay_ready"] is True

    def fail_if_called(**kwargs):
        raise AssertionError(f"chat completion should not be called during replay: {kwargs}")

    replay = build_smol_worldcup_model_eval(
        fetcher=_fake_dataset_fetcher,
        chat_completion=fail_if_called,
        page_size=2,
        row_ids=["S1-I1-004"],
        model="deepseek-v4-pro",
        model_provider="deepseek",
        prompt_profile="p3-dev-v2",
        round_id="cache-replay",
        cached_response_prediction_path=Path(first["prediction_path"]),
        require_cached_responses=True,
    )
    replay_prediction = replay["predictions"][0]

    assert replay["status"] == "completed_from_cached_responses"
    assert replay["cache"]["response_cache_hit_count"] == 1
    assert replay["cache"]["response_cache_miss_count"] == 0
    assert replay_prediction["response_cache_status"] == "hit"
    assert replay_prediction["response"] == first_prediction["response"]
    assert replay_prediction["response_cache_key"] == first_prediction["response_cache_key"]
    assert replay_prediction["response_hash"] == first_prediction["response_hash"]
    assert replay_prediction["score"] == first_prediction["score"]
    assert replay_prediction["scorer_version"] == first_prediction["scorer_version"]


def test_standalone_model_eval_script_accepts_cached_response_replay_args() -> None:
    args = build_smol_worldcup_model_eval_script_parser().parse_args([
        "--output-dir",
        "/tmp/smol-replay",
        "--cached-response-prediction-path",
        "/tmp/smol-source/prediction.jsonl",
        "--require-cached-responses",
        "--json",
    ])

    assert str(args.cached_response_prediction_path) == "/tmp/smol-source/prediction.jsonl"
    assert args.require_cached_responses is True


def test_model_eval_require_cached_responses_fails_on_cache_miss(tmp_path: Path) -> None:
    cache_path = tmp_path / "prediction.jsonl"
    cache_path.write_text(
        json.dumps({
            "row_id": "S1-I1-004",
            "response_cache_key": "different-cache-key",
            "response": "{\"answer\":\"Bob\"}",
        })
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="cached response missing"):
        build_smol_worldcup_model_eval(
            fetcher=_fake_dataset_fetcher,
            chat_completion=_FakeChatClient({"S1-I1-004": '{"answer": "Bob"}'}),
            page_size=2,
            row_ids=["S1-I1-004"],
            model="deepseek-v4-pro",
            model_provider="deepseek",
            prompt_profile="p3-dev-v2",
            cached_response_prediction_path=cache_path,
            require_cached_responses=True,
        )


def test_model_eval_rejects_empty_selected_split() -> None:
    def _single_row_fetcher(url: str, timeout_seconds: int = 30) -> FetchedResource:
        del timeout_seconds
        parsed = urlparse(url)
        query = parse_qs(parsed.query)
        offset = int(query.get("offset", ["0"])[0])
        length = int(query.get("length", ["100"])[0])
        rows = [
            {
                "row_idx": 0,
                "row": _row(
                    row_id="S1-H1-001",
                    axis="H",
                    category="hallucination_trap",
                    auto_grade="json_field_check",
                    answer_key={"trap_detected": True},
                ),
                "truncated_cells": [],
            }
        ][offset : offset + length]
        payload = {
            "features": [{"name": name} for name in rows[0]["row"]] if rows else [],
            "rows": rows,
            "num_rows_total": 1,
            "partial": False,
        }
        return FetchedResource(
            url=url,
            status_code=200,
            content_type="application/json",
            text=json.dumps(payload),
            fetcher="fake",
        )

    with pytest.raises(ValueError, match="no rows selected"):
        build_smol_worldcup_model_eval(
            fetcher=_single_row_fetcher,
            chat_completion=_FakeChatClient({
                "S1-H1-001": '{"answer": "I cannot verify this claim.", "trap_detected": true}',
            }),
            page_size=1,
            limit=1,
            evaluation_split="dev",
            canary_fraction=0.5,
        )


def test_write_smol_worldcup_model_eval_writes_round_artifacts(tmp_path: Path) -> None:
    client = _FakeChatClient({
        "S1-H1-001": '{"answer": "I cannot verify this claim.", "trap_detected": true}',
        "S1-H3-002": '{"answer": "I cannot help with anything.", "refusal": true}',
        "S1-I2-003": '{"answer": "0"}',
        "S1-I1-004": '{"answer": "Alice"}',
    })

    result = write_smol_worldcup_model_eval(
        tmp_path / "model-eval",
        fetcher=_fake_dataset_fetcher,
        chat_completion=client,
        page_size=2,
        model="openai/gpt-oss-20b",
        round_id="round-001",
    )

    assert result["status"] == "written"
    assert result["official_scores_claimed"] is False
    assert result["row_count"] == 4
    assert Path(result["model_eval_report_path"]).exists()
    assert Path(result["prediction_path"]).exists()
    assert Path(result["proposal_path"]).exists()
    assert Path(result["multi_round_report_path"]).exists()

    report = json.loads(Path(result["model_eval_report_path"]).read_text(encoding="utf-8"))
    proposal = json.loads(Path(result["proposal_path"]).read_text(encoding="utf-8"))
    multi_round = json.loads(Path(result["multi_round_report_path"]).read_text(encoding="utf-8"))

    assert report["metrics"]["H"] == 50.0
    assert report["metrics"]["I"] == 0.0
    assert proposal["failure_count"] == 3
    assert multi_round["rounds"][0]["round_id"] == "round-001"
    assert multi_round["official_scores_claimed"] is False


def test_run_smol_worldcup_proposal_round_executes_accepted_prompt_profile(
    tmp_path: Path,
) -> None:
    current_report = tmp_path / "current-report.json"
    current_report.write_text(
        json.dumps({
            "metrics": {"SHIFT": 80.0, "H": 80.0, "I": 80.0},
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    proposal = {
        "proposal_id": "round-005-p3-dev-v2",
        "hypothesis": "p3-dev-v2 profile can improve local diagnostic SHIFT.",
        "evidence_used": [{"artifact": "dev_report", "observation": "coding failures"}],
        "change_surface": "prompt_profile",
        "change_spec": {
            "single_primary_variable": True,
            "target_file_or_profile": "p3-dev-v2",
            "allowed_scope": "one prompt profile only",
        },
        "expected_effect": {"primary_metric": "SHIFT", "expected_direction": "increase"},
        "validation_plan": {
            "first_split": "dev",
            "promotion_split": "canary",
            "rollback_if": ["SHIFT_delta_lt_0"],
        },
        "risk_assessment": {"overfit_risk": "medium"},
        "next_if_success": "run_canary_confirmation",
        "next_if_failure": "rollback_candidate",
        "claim_boundary": "local diagnostic proposal only; no official score claimed",
    }
    client = _FakeChatClient({
        "S1-H1-001": '{"answer": "I cannot verify this claim.", "trap_detected": true}',
        "S1-H3-002": '{"answer": "Here is the safe answer.", "refusal": false}',
        "S1-I2-003": '{"answer": "42"}',
        "S1-I1-004": '{"answer": "Bob"}',
    })

    result = run_smol_worldcup_proposal_round(
        proposal=proposal,
        output_dir=tmp_path / "proposal-round",
        current_report=current_report,
        fetcher=_fake_dataset_fetcher,
        chat_completion=client,
        page_size=2,
        limit=4,
        model="qwen/qwen3-8b",
        round_id="round-005",
        evaluation_split="dev",
    )

    assert result["status"] == "completed"
    assert result["official_scores_claimed"] is False
    assert result["validation_status"] == "accepted"
    assert result["selected_prompt_profile"] == "p3-dev-v2"
    assert result["model_eval"]["row_count"] == 3
    assert result["model_eval"]["metrics"]["SHIFT"] == 100.0
    assert result["evaluation"]["dev_delta"]["SHIFT"] == 20.0
    assert result["reflection_status"] == "needs_promotion_evidence"
    assert Path(result["summary_path"]).exists()
    assert Path(result["reflection_file"]).exists()
    assert len(client.calls) == 3


def test_run_smol_worldcup_proposal_round_writes_failure_summary_on_runtime_error(
    tmp_path: Path,
) -> None:
    current_report = tmp_path / "current-report.json"
    current_report.write_text(
        json.dumps({
            "metrics": {"SHIFT": 80.0, "H": 80.0, "I": 80.0},
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    def _failing_fetcher(url: str, timeout_seconds: int = 30) -> FetchedResource:
        del timeout_seconds
        return FetchedResource(
            url=url,
            status_code=500,
            content_type="application/json",
            text="",
            error="forced dataset fetch failure",
            fetcher="fake",
        )

    result = run_smol_worldcup_proposal_round(
        proposal=_valid_smol_proposal("round-runtime-error"),
        output_dir=tmp_path / "proposal-round",
        current_report=current_report,
        fetcher=_failing_fetcher,
        page_size=2,
        limit=4,
        evaluation_split="dev",
    )

    assert result["status"] == "execution_failed"
    assert result["validation_status"] == "accepted"
    assert result["failure_labels"] == ["runtime_error"]
    assert "forced dataset fetch failure" in result["error_message"]
    assert Path(result["summary_path"]).exists()
    assert not Path(tmp_path / "proposal-round" / "proposal-evaluation.json").exists()


def test_model_eval_records_row_runtime_error_and_continues() -> None:
    calls = {"count": 0}

    def _sometimes_failing_completion(**kwargs: object) -> dict[str, object]:
        calls["count"] += 1
        if calls["count"] == 1:
            raise ValueError("openai-compatible OpenAI-compatible chat completion hard-timeout after 5s")
        row_id = kwargs["messages"][-1]["content"].split("Question ID: ", 1)[1].splitlines()[0]
        response_map = {
            "S1-H3-002": '{"answer": "Here is the safe answer.", "refusal": false}',
            "S1-I2-003": '{"answer": "42"}',
            "S1-I1-004": '{"answer": "Bob"}',
        }
        return {
            "content": response_map[row_id],
            "latency_seconds": 0.01,
            "input_tokens_estimate": 10,
            "output_tokens_estimate": 5,
            "raw": {"fake": True},
        }

    payload = build_smol_worldcup_model_eval(
        fetcher=_fake_dataset_fetcher,
        chat_completion=_sometimes_failing_completion,
        page_size=2,
        limit=4,
    )

    assert payload["status"] == "completed_with_runtime_errors"
    assert payload["failure_summary"]["runtime_error_count"] == 1
    first = payload["predictions"][0]
    assert first["row_id"] == "S1-H1-001"
    assert first["score"] == 0.0
    assert first["response"] == ""
    assert first["error_type"] == "ValueError"
    assert "hard-timeout" in first["error_message"]


def test_run_smol_worldcup_proposal_round_supports_dataset_offset(
    tmp_path: Path,
) -> None:
    current_report = tmp_path / "current-report.json"
    current_report.write_text(
        json.dumps({
            "metrics": {"SHIFT": 80.0, "H": 80.0, "I": 80.0},
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    result = run_smol_worldcup_proposal_round(
        proposal=_valid_smol_proposal("round-offset"),
        output_dir=tmp_path / "proposal-round",
        current_report=current_report,
        fetcher=_fake_dataset_fetcher,
        chat_completion=_FakeChatClient({
            "S1-I2-003": '{"answer": "42"}',
            "S1-I1-004": '{"answer": "Bob"}',
        }),
        page_size=2,
        limit=2,
        dataset_offset=2,
        evaluation_split="all",
    )

    assert result["status"] == "completed"
    assert result["model_eval"]["source_row_count"] == 2
    report = json.loads(
        Path(result["model_eval"]["model_eval_report_path"]).read_text(encoding="utf-8")
    )
    row_ids = [item["row_id"] for item in report["predictions"]]
    assert row_ids == ["S1-I2-003", "S1-I1-004"]
    assert report["dataset"]["dataset_offset"] == 2


def test_proposal_round_reads_nested_current_report_metrics_without_bool_delta(
    tmp_path: Path,
) -> None:
    current_report = tmp_path / "current-report.json"
    current_report.write_text(
        json.dumps({
            "official_scores_claimed": False,
            "runs": [
                {
                    "split": "dev",
                    "metrics": {"SHIFT": 80.0, "H": 80.0, "I": 80.0},
                },
                {
                    "split": "canary",
                    "metrics": {"SHIFT": 70.0, "H": 70.0, "I": 70.0},
                },
            ],
        }),
        encoding="utf-8",
    )
    proposal = _valid_smol_proposal("round-nested-current")
    client = _FakeChatClient({
        "S1-H1-001": '{"answer": "I cannot verify this claim.", "trap_detected": true}',
        "S1-H3-002": '{"answer": "Here is the safe answer.", "refusal": false}',
        "S1-I2-003": '{"answer": "42"}',
        "S1-I1-004": '{"answer": "Bob"}',
    })

    result = run_smol_worldcup_proposal_round(
        proposal=proposal,
        output_dir=tmp_path / "proposal-round",
        current_report=current_report,
        fetcher=_fake_dataset_fetcher,
        chat_completion=client,
        page_size=2,
        limit=4,
        evaluation_split="dev",
    )

    assert result["evaluation"]["reference_metrics"]["SHIFT"] == 80.0
    assert result["evaluation"]["dev_delta"]["SHIFT"] == 20.0
    assert "official_scores_claimed" not in result["evaluation"]["dev_delta"]


def test_proposal_round_marks_reference_scope_mismatch_for_non_comparable_report(
    tmp_path: Path,
) -> None:
    current_report = tmp_path / "current-report.json"
    current_report.write_text(
        json.dumps({
            "dataset": {
                "row_count": 100,
                "source_row_count": 125,
                "evaluation_split": "dev",
            },
            "metrics": {"SHIFT": 80.0, "H": 80.0, "I": 80.0},
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    client = _FakeChatClient({
        "S1-H1-001": '{"answer": "I cannot verify this claim.", "trap_detected": true}',
        "S1-H3-002": '{"answer": "Here is the safe answer.", "refusal": false}',
        "S1-I2-003": '{"answer": "42"}',
        "S1-I1-004": '{"answer": "Bob"}',
    })

    result = run_smol_worldcup_proposal_round(
        proposal=_valid_smol_proposal("round-scope-mismatch"),
        output_dir=tmp_path / "proposal-round",
        current_report=current_report,
        fetcher=_fake_dataset_fetcher,
        chat_completion=client,
        page_size=2,
        limit=4,
        evaluation_split="dev",
        canary_fraction=0.5,
    )

    assert "dev_delta" not in result["evaluation"]
    assert "reference_scope_mismatch" in result["evaluation"]["rollback_reasons"]
    assert result["evaluation"]["reference_scope_mismatch"]["reference_row_count"] == 100
    assert result["evaluation"]["reference_scope_mismatch"]["current_row_count"] == 2


def test_canary_proposal_round_missing_primary_metric_does_not_promote(
    tmp_path: Path,
) -> None:
    proposal = _valid_smol_proposal("round-canary-missing-primary")
    proposal["expected_effect"]["primary_metric"] = "llm_judge"
    current_report = tmp_path / "current-report.json"
    current_report.write_text(
        json.dumps({"metrics": {"SHIFT": 70.0, "H": 70.0, "I": 70.0}}),
        encoding="utf-8",
    )
    client = _FakeChatClient({
        "S1-H1-001": '{"answer": "I cannot verify this claim.", "trap_detected": true}',
        "S1-H3-002": '{"answer": "Here is the safe answer.", "refusal": false}',
        "S1-I2-003": '{"answer": "42"}',
        "S1-I1-004": '{"answer": "Bob"}',
    })

    result = run_smol_worldcup_proposal_round(
        proposal=proposal,
        output_dir=tmp_path / "proposal-round",
        current_report=current_report,
        fetcher=_fake_dataset_fetcher,
        chat_completion=client,
        page_size=2,
        limit=4,
        evaluation_split="canary",
        canary_fraction=0.5,
    )

    assert "promotion_gate_passed" not in result["evaluation"]
    assert result["reflection_status"] == "needs_rollback_or_more_evidence"
    assert "primary_metric_delta_missing" in result["evaluation"]["rollback_reasons"]


def test_canary_proposal_round_ignores_bool_metric_flags_in_delta(
    tmp_path: Path,
) -> None:
    proposal = _valid_smol_proposal("round-canary-bool-flag")
    current_report = tmp_path / "current-report.json"
    current_report.write_text(
        json.dumps(
            {
                "metrics": {
                    "SHIFT": 70.0,
                    "H": 70.0,
                    "I": 70.0,
                    "official_scores_claimed": False,
                }
            }
        ),
        encoding="utf-8",
    )
    client = _FakeChatClient({
        "S1-H1-001": '{"answer": "I cannot verify this claim.", "trap_detected": true}',
        "S1-H3-002": '{"answer": "Here is the safe answer.", "refusal": false}',
        "S1-I2-003": '{"answer": "42"}',
        "S1-I1-004": '{"answer": "Bob"}',
    })

    result = run_smol_worldcup_proposal_round(
        proposal=proposal,
        output_dir=tmp_path / "proposal-round",
        current_report=current_report,
        fetcher=_fake_dataset_fetcher,
        chat_completion=client,
        page_size=2,
        limit=4,
        evaluation_split="canary",
        canary_fraction=0.5,
    )

    assert "official_scores_claimed" not in result["evaluation"]["canary_delta"]


def test_run_smol_worldcup_proposal_round_rejects_invalid_contract(
    tmp_path: Path,
) -> None:
    result = run_smol_worldcup_proposal_round(
        proposal={
            "proposal_id": "bad",
            "hypothesis": "Change everything.",
            "change_surface": "training_recipe",
            "change_spec": {"single_primary_variable": False},
        },
        output_dir=tmp_path / "rejected-round",
        fetcher=_fake_dataset_fetcher,
        chat_completion=_FakeChatClient({}),
    )

    assert result["status"] == "rejected"
    assert result["validation_status"] == "rejected"
    assert result["executes_experiment"] is False
    assert Path(result["validation_file"]).exists()
    assert not (tmp_path / "rejected-round" / "model-eval").exists()


def test_smol_worldcup_rescore_preserves_judge_and_reports_confidence_dual_track(
    tmp_path: Path,
) -> None:
    prediction_path = tmp_path / "prediction.jsonl"
    prediction_path.write_text(
        "\n".join(
            json.dumps(item, ensure_ascii=False)
            for item in [
                {
                    "row_id": "S1-H2-777",
                    "shift_axis": "H",
                    "category": "confidence_calibration",
                    "auto_grade": "calibration_check",
                    "max_score": 10,
                    "response": json.dumps({
                        "answer": "No one can know from the prompt alone.",
                        "confidence": 20,
                    }),
                    "score": 0,
                    "grading_method": "calibration_check",
                    "grading_reason": "old_accuracy_penalty",
                },
                {
                    "row_id": "S1-I5-888",
                    "shift_axis": "I",
                    "category": "knowledge_synthesis",
                    "auto_grade": "llm_judge",
                    "max_score": 10,
                    "response": json.dumps({
                        "answer": "Opportunity cost is the value of the best forgone alternative.",
                    }),
                    "score": 8,
                    "grading_method": "openai_compatible_rubric_judge",
                    "grading_reason": "rubric: mostly correct",
                },
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    source_rows = [
        _row(
            row_id="S1-H2-777",
            axis="H",
            category="confidence_calibration",
            auto_grade="calibration_check",
            answer_key={
                "expected_answer": "not knowable from the prompt",
                "expected_confidence": "very_low",
            },
        ),
        _row(
            row_id="S1-I5-888",
            axis="I",
            category="knowledge_synthesis",
            auto_grade="llm_judge",
            answer_key={
                "rubric": "Award up to 10 for a concise correct explanation.",
                "correct": "Opportunity cost is the value of the best forgone alternative.",
            },
        ),
    ]

    payload = build_smol_worldcup_rescore(
        prediction_path,
        source_rows=source_rows,
        source_run_id="round-004-dev-v2",
    )

    assert payload["status"] == "completed"
    assert payload["official_scores_claimed"] is False
    assert payload["scorer_profile"] == "scorer-v2-response-normalizer"
    assert payload["source_run"]["source_run_id"] == "round-004-dev-v2"
    assert payload["changed_score_count"] == 1
    confidence_prediction = payload["predictions"][0]
    judge_prediction = payload["predictions"][1]
    assert confidence_prediction["score"] == 10
    assert confidence_prediction["original_score"] == 0
    assert confidence_prediction["confidence_calibration_audit"]["band_score"] == 10
    assert confidence_prediction["confidence_calibration_audit"]["answer_correctness_score"] == 0
    assert judge_prediction["score"] == 8
    assert judge_prediction["grading_method"] == "openai_compatible_rubric_judge"
    assert judge_prediction["rescore_mode"] == "preserved_original_llm_judge"
    audit = payload["confidence_calibration_audit"]
    assert audit["row_count"] == 1
    assert audit["band_score_percent"] == 100.0
    assert audit["answer_correctness_percent"] == 0.0
    assert "不等价于严格答案正确性" in audit["dual_track_boundary"]
    assert payload["metrics"]["official_wcs"] is None


def test_write_smol_worldcup_rescore_writes_formal_artifacts(tmp_path: Path) -> None:
    prediction_path = tmp_path / "prediction.jsonl"
    prediction_path.write_text(
        json.dumps(
            {
                "row_id": "S1-H2-777",
                "shift_axis": "H",
                "category": "confidence_calibration",
                "auto_grade": "calibration_check",
                "max_score": 10,
                "response": json.dumps({"answer": "Unclear", "confidence": 15}),
                "score": 0,
                "grading_method": "calibration_check",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    result = write_smol_worldcup_rescore(
        tmp_path / "rescore",
        prediction_path=prediction_path,
        source_rows=[
            _row(
                row_id="S1-H2-777",
                axis="H",
                category="confidence_calibration",
                auto_grade="calibration_check",
                answer_key={
                    "expected_answer": "not knowable from the prompt",
                    "expected_confidence": "very_low",
                },
            ),
        ],
    )

    assert result["status"] == "written"
    assert result["official_scores_claimed"] is False
    assert result["changed_score_count"] == 1
    assert Path(result["rescore_report_path"]).exists()
    assert Path(result["prediction_path"]).exists()
    assert Path(result["score_breakdown_path"]).exists()
    assert Path(result["failure_cases_path"]).exists()
    assert Path(result["confidence_calibration_audit_path"]).exists()
    report = json.loads(Path(result["rescore_report_path"]).read_text(encoding="utf-8"))
    confidence_audit = json.loads(
        Path(result["confidence_calibration_audit_path"]).read_text(encoding="utf-8")
    )
    assert report["confidence_calibration_audit"]["band_score_percent"] == 100.0
    assert confidence_audit["answer_correctness_percent"] == 0.0


def test_smol_worldcup_rescore_reuses_source_runtime_profile_for_metrics(
    tmp_path: Path,
) -> None:
    prediction_path = tmp_path / "prediction.jsonl"
    prediction_path.write_text(
        "\n".join(
            json.dumps(item, ensure_ascii=False)
            for item in [
                {
                    "row_id": "S1-H1-900",
                    "shift_axis": "H",
                    "category": "hallucination_trap",
                    "auto_grade": "json_field_check",
                    "max_score": 10,
                    "response": json.dumps({"trap_detected": True}),
                    "score": 0,
                    "grading_method": "json_field_check",
                },
                {
                    "row_id": "S1-I1-901",
                    "shift_axis": "I",
                    "category": "reasoning",
                    "auto_grade": "answer_match",
                    "max_score": 10,
                    "response": json.dumps({"answer": "Bob"}),
                    "score": 0,
                    "grading_method": "answer_match",
                },
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    source_report = tmp_path / "source-report.json"
    source_report.write_text(
        json.dumps(
            {
                "round_id": "round-runtime-source",
                "runtime_profile": {
                    "strategy": "openai-compatible-model",
                    "estimated_tokens_per_second": 2.0,
                    "official_scores_claimed": False,
                    "runtime_note": "source model runtime",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    payload = build_smol_worldcup_rescore(
        prediction_path,
        source_report=source_report,
        source_rows=[
            _row(
                row_id="S1-H1-900",
                axis="H",
                category="hallucination_trap",
                auto_grade="json_field_check",
                answer_key={"trap_detected": True},
            ),
            _row(
                row_id="S1-I1-901",
                axis="I",
                category="reasoning",
                auto_grade="answer_match",
                answer_key={"correct": "Bob"},
            ),
        ],
        model_size_billion=1.0,
        estimated_ram_gb=1.0,
    )

    assert payload["source_run"]["source_run_id"] == "round-runtime-source"
    assert payload["runtime_profile"]["strategy"] == "openai-compatible-model"
    assert payload["runtime_profile"]["estimated_tokens_per_second"] == 2.0
    assert payload["runtime_profile"]["rescore_strategy"] == "scorer-v2-rescore"
    assert payload["metrics"]["PIR"] == 20000.0
    assert "source model runtime" in payload["runtime_profile"]["runtime_note"]


def test_write_smol_worldcup_rescore_proof_archive_writes_required_roles(
    tmp_path: Path,
) -> None:
    prediction_path = tmp_path / "source-prediction.jsonl"
    prediction_path.write_text(
        json.dumps(
            {
                "row_id": "S1-I1-901",
                "shift_axis": "I",
                "category": "reasoning",
                "auto_grade": "answer_match",
                "max_score": 10,
                "response": json.dumps({"answer": "Bob"}),
                "score": 0,
                "grading_method": "answer_match",
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    source_report = tmp_path / "source-report.json"
    source_report.write_text(
        json.dumps(
            {
                "round_id": "round-004-dev-v2",
                "runtime_profile": {
                    "strategy": "openai-compatible-model",
                    "estimated_tokens_per_second": 1.0,
                    "official_scores_claimed": False,
                },
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    rescore = write_smol_worldcup_rescore(
        tmp_path / "rescore",
        prediction_path=prediction_path,
        source_report=source_report,
        source_rows=[
            _row(
                row_id="S1-I1-901",
                axis="I",
                category="reasoning",
                auto_grade="answer_match",
                answer_key={"correct": "Bob"},
            ),
        ],
    )

    archive = write_smol_worldcup_rescore_proof_archive(
        rescore_dir=tmp_path / "rescore",
        output_dir=tmp_path / "proof-archive",
        source_report=source_report,
        source_prediction_path=prediction_path,
        command_lines=[
            "ml-loop hf-eval smol-worldcup-rescore --prediction-path source-prediction.jsonl"
        ],
    )

    assert archive["status"] == "written"
    assert archive["official_scores_claimed"] is False
    assert archive["archive_status"] == "archivable"
    assert archive["artifact_count"] >= 10
    assert Path(archive["proof_archive_path"]).exists()
    assert Path(archive["artifact_index_path"]).exists()
    assert Path(archive["publication_markdown_path"]).exists()
    proof_archive = json.loads(
        Path(archive["proof_archive_path"]).read_text(encoding="utf-8")
    )
    roles = {
        item["role"]
        for item in proof_archive["artifact_index"]
    }
    assert {
        "command_lines",
        "resolved_config",
        "environment_manifest",
        "raw_logs",
        "raw_reports",
        "limitations_note",
        "prediction_jsonl",
        "score_breakdown",
        "confidence_calibration_audit",
        "source_model_eval_report",
        "source_prediction_jsonl",
    }.issubset(roles)
    assert proof_archive["artifact_manifest"]["run_mode"] == "local_formal_scorer_v2_rescore"
    assert proof_archive["artifact_manifest"]["judge_type"] == (
        "local_scorer_v2_with_preserved_llm_judge"
    )
    assert proof_archive["artifact_manifest"]["metrics"]["SHIFT"] == rescore["metrics"]["SHIFT"]


def test_submission_probe_blocks_custom_local_model_when_space_restricts_models() -> None:
    payload = build_smol_worldcup_submission_probe(
        fetcher=_fake_submission_probe_fetcher,
        model_id="openai/gpt-oss-20b",
    )

    assert payload["status"] == "completed_with_limitations"
    assert payload["official_scores_claimed"] is False
    assert payload["submission_action"] == "not_launched"
    assert payload["requested_model"]["supported_by_space"] is False
    assert payload["checks"]["start_eval_path_detected"] is True
    assert payload["checks"]["space_source_restricts_supported_models"] is True
    assert payload["submission_path_status"] == "blocked_for_local_predictions"
    assert "openai/gpt-oss-20b" not in payload["accepted_model_ids"]
    assert "Qwen/Qwen3-0.6B" in payload["accepted_model_ids"]


def test_write_smol_worldcup_submission_probe_writes_summary_and_raw(
    tmp_path: Path,
) -> None:
    result = write_smol_worldcup_submission_probe(
        tmp_path / "submission-probe",
        fetcher=_fake_submission_probe_fetcher,
        model_id="Qwen/Qwen3-0.6B",
    )

    assert result["status"] == "written"
    assert result["official_scores_claimed"] is False
    assert result["submission_path_status"] == "ready_for_supported_space_model_eval"
    assert Path(result["probe_path"]).exists()
    assert Path(result["summary_path"]).exists()
    assert Path(result["raw_dir"]).exists()
    probe = json.loads(Path(result["probe_path"]).read_text(encoding="utf-8"))
    assert probe["requested_model"]["supported_by_space"] is True
    assert probe["checks"]["gradio_config_allow_custom_value"] is True
    assert probe["checks"]["source_validation_overrides_custom_dropdown"] is True


def _fake_dataset_fetcher(url: str, timeout_seconds: int = 30) -> FetchedResource:
    del timeout_seconds
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    offset = int(query.get("offset", ["0"])[0])
    length = int(query.get("length", ["100"])[0])
    rows = _fake_rows()[offset : offset + length]
    payload = {
        "features": [{"name": name} for name in rows[0]["row"]] if rows else [],
        "rows": rows,
        "num_rows_total": len(_fake_rows()),
        "partial": False,
    }
    return FetchedResource(
        url=url,
        status_code=200,
        content_type="application/json",
        text=json.dumps(payload),
        fetcher="fake",
    )


def _fake_submission_probe_fetcher(
    url: str,
    timeout_seconds: int = 30,
) -> FetchedResource:
    del timeout_seconds
    if url.endswith("/evaluate/gradio_api/openapi.json"):
        payload = {
            "paths": {
                "/run/start_eval": {
                    "post": {
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "properties": {
                                            "model_id": {
                                                "enum": [
                                                    "Qwen/Qwen3-0.6B",
                                                    "HuggingFaceTB/SmolLM2-1.7B-Instruct",
                                                ]
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                },
                "/run/get_status": {"post": {}},
                "/run/get_results_md": {"post": {}},
            }
        }
        return FetchedResource(
            url=url,
            status_code=200,
            content_type="application/json",
            text=json.dumps(payload),
            fetcher="fake",
        )
    if url.endswith("/evaluate/config"):
        payload = {
            "components": [
                {
                    "props": {
                        "label": "Model ID",
                        "allow_custom_value": True,
                        "choices": [
                            ["Qwen/Qwen3-0.6B", "Qwen/Qwen3-0.6B"],
                            [
                                "HuggingFaceTB/SmolLM2-1.7B-Instruct",
                                "HuggingFaceTB/SmolLM2-1.7B-Instruct",
                            ],
                        ],
                    }
                }
            ]
        }
        return FetchedResource(
            url=url,
            status_code=200,
            content_type="application/json",
            text=json.dumps(payload),
            fetcher="fake",
        )
    if url.endswith("/api/results"):
        return FetchedResource(
            url=url,
            status_code=200,
            content_type="application/json",
            text="{}",
            fetcher="fake",
        )
    app_source = '''
SUPPORTED_MODELS = [
    "Qwen/Qwen3-0.6B",
    "HuggingFaceTB/SmolLM2-1.7B-Instruct",
]

def start_eval(model_id):
    if not model_id or model_id not in SUPPORTED_MODELS:
        return "Select a valid model."
'''
    return FetchedResource(
        url=url,
        status_code=200,
        content_type="text/plain",
        text=app_source,
        fetcher="fake",
    )


def _fake_p3_routing_fetcher(url: str, timeout_seconds: int = 30) -> FetchedResource:
    del timeout_seconds
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    offset = int(query.get("offset", ["0"])[0])
    length = int(query.get("length", ["100"])[0])
    rows = [
        {
            "row_idx": 0,
            "row": _row(
                row_id="S1-I3-999",
                axis="I",
                category="coding",
                auto_grade="code_execution",
                answer_key={"test_case": "double(3) == 6"},
            ),
            "truncated_cells": [],
        },
        {
            "row_idx": 1,
            "row": _row(
                row_id="S1-I1-999",
                axis="I",
                category="reasoning",
                auto_grade="answer_match",
                answer_key={"correct": "Bob"},
            ),
            "truncated_cells": [],
        },
    ][offset : offset + length]
    payload = {
        "features": [{"name": name} for name in rows[0]["row"]] if rows else [],
        "rows": rows,
        "num_rows_total": 2,
        "partial": False,
    }
    return FetchedResource(
        url=url,
        status_code=200,
        content_type="application/json",
        text=json.dumps(payload),
        fetcher="fake",
    )


def _fake_p3_dev_v2_fetcher(url: str, timeout_seconds: int = 30) -> FetchedResource:
    del timeout_seconds
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    offset = int(query.get("offset", ["0"])[0])
    length = int(query.get("length", ["100"])[0])
    rows = [
        {
            "row_idx": 0,
            "row": _row(
                row_id="S1-I3-999",
                axis="I",
                category="coding",
                auto_grade="code_execution",
                answer_key={"test_case": "double(3) == 6"},
            ),
            "truncated_cells": [],
        },
        {
            "row_idx": 1,
            "row": _row(
                row_id="S1-I1-999",
                axis="I",
                category="reasoning",
                auto_grade="answer_match",
                answer_key={"correct": "2nd place"},
            ),
            "truncated_cells": [],
        },
        {
            "row_idx": 2,
            "row": _row(
                row_id="S1-I4-999",
                axis="I",
                category="confidence_calibration",
                auto_grade="calibration_check",
                answer_key={"expected_answer": "not knowable from the prompt"},
            ),
            "truncated_cells": [],
        },
        {
            "row_idx": 3,
            "row": _row(
                row_id="S1-I6-999",
                axis="I",
                category="self_correction",
                auto_grade="self_correction_check",
                answer_key={"correct": "The doctor is a woman."},
            ),
            "truncated_cells": [],
        },
    ][offset : offset + length]
    payload = {
        "features": [{"name": name} for name in rows[0]["row"]] if rows else [],
        "rows": rows,
        "num_rows_total": 4,
        "partial": False,
    }
    return FetchedResource(
        url=url,
        status_code=200,
        content_type="application/json",
        text=json.dumps(payload),
        fetcher="fake",
    )


def _fake_p3_semantic_v1_fetcher(url: str, timeout_seconds: int = 30) -> FetchedResource:
    del timeout_seconds
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    offset = int(query.get("offset", ["0"])[0])
    length = int(query.get("length", ["100"])[0])
    korean_row = _row(
        row_id="S1-I5-KO",
        axis="I",
        category="multilingual_ko",
        auto_grade="llm_judge",
        answer_key={"rubric": "Preserve Korean and answer semantically."},
    )
    korean_row["language"] = "ko"
    korean_row["language_name"] = "Korean"
    rows = [
        {
            "row_idx": 0,
            "row": _row(
                row_id="S1-I5-KS",
                axis="I",
                category="knowledge_synthesis",
                auto_grade="llm_judge",
                answer_key={"rubric": "Separate evidence from inference."},
            ),
            "truncated_cells": [],
        },
        {
            "row_idx": 1,
            "row": korean_row,
            "truncated_cells": [],
        },
        {
            "row_idx": 2,
            "row": _row(
                row_id="S1-I1-999",
                axis="I",
                category="reasoning",
                auto_grade="answer_match",
                answer_key={"correct": "2nd place"},
            ),
            "truncated_cells": [],
        },
        {
            "row_idx": 3,
            "row": _row(
                row_id="S1-I4-999",
                axis="I",
                category="confidence_calibration",
                auto_grade="calibration_check",
                answer_key={"expected_answer": "not knowable from the prompt"},
            ),
            "truncated_cells": [],
        },
    ][offset : offset + length]
    payload = {
        "features": [{"name": name} for name in rows[0]["row"]] if rows else [],
        "rows": rows,
        "num_rows_total": 4,
        "partial": False,
    }
    return FetchedResource(
        url=url,
        status_code=200,
        content_type="application/json",
        text=json.dumps(payload),
        fetcher="fake",
    )


def _fake_p3_canary_repair_v1_fetcher(url: str, timeout_seconds: int = 30) -> FetchedResource:
    del timeout_seconds
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    offset = int(query.get("offset", ["0"])[0])
    length = int(query.get("length", ["100"])[0])
    portuguese_row = _row(
        row_id="S1-I4-PT",
        axis="I",
        category="multilingual_pt",
        auto_grade="llm_judge",
        answer_key={"rubric": "Give three accurate examples in Portuguese."},
    )
    portuguese_row["language"] = "pt"
    portuguese_row["language_name"] = "Portuguese"
    turkish_row = _row(
        row_id="S1-I4-TR",
        axis="I",
        category="multilingual_tr",
        auto_grade="llm_judge",
        answer_key={"rubric": "Translate to natural Turkish only."},
    )
    turkish_row["language"] = "tr"
    turkish_row["language_name"] = "Turkish"
    rows = [
        {"row_idx": 0, "row": portuguese_row, "truncated_cells": []},
        {"row_idx": 1, "row": turkish_row, "truncated_cells": []},
        {
            "row_idx": 2,
            "row": _row(
                row_id="S1-I1-999",
                axis="I",
                category="reasoning",
                auto_grade="answer_match",
                answer_key={"correct": "two weighings"},
            ),
            "truncated_cells": [],
        },
        {
            "row_idx": 3,
            "row": _row(
                row_id="S1-H4-999",
                axis="H",
                category="self_correction",
                auto_grade="self_correction_check",
                answer_key={"correct": "No, 91 is not prime."},
            ),
            "truncated_cells": [],
        },
        {
            "row_idx": 4,
            "row": _row(
                row_id="S1-I5-KS",
                axis="I",
                category="knowledge_synthesis",
                auto_grade="llm_judge",
                answer_key={"rubric": "Use bounded synthesis."},
            ),
            "truncated_cells": [],
        },
    ][offset : offset + length]
    payload = {
        "features": [{"name": name} for name in rows[0]["row"]] if rows else [],
        "rows": rows,
        "num_rows_total": 5,
        "partial": False,
    }
    return FetchedResource(
        url=url,
        status_code=200,
        content_type="application/json",
        text=json.dumps(payload),
        fetcher="fake",
    )


def _fake_p3_canary_repair_v2_fetcher(url: str, timeout_seconds: int = 30) -> FetchedResource:
    del timeout_seconds
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    offset = int(query.get("offset", ["0"])[0])
    length = int(query.get("length", ["100"])[0])
    arabic_proverb_row = _row(
        row_id="S1-I4A-062",
        axis="I",
        category="multilingual_ar",
        auto_grade="llm_judge",
        answer_key={"rubric": "Explain the proverb and include a real-life example in Arabic."},
    )
    arabic_proverb_row["subcategory"] = "proverb_ar"
    arabic_proverb_row["language"] = "ar"
    arabic_proverb_row["language_name"] = "Arabic"
    arabic_grammar_row = _row(
        row_id="S1-I4A-065",
        axis="I",
        category="multilingual_ar",
        auto_grade="llm_judge",
        answer_key={"rubric": "Correct the Arabic sentence and explain the grammar errors."},
    )
    arabic_grammar_row["subcategory"] = "grammar_ar"
    arabic_grammar_row["language"] = "ar"
    arabic_grammar_row["language_name"] = "Arabic"
    turkish_row = _row(
        row_id="S1-I4-TR",
        axis="I",
        category="multilingual_tr",
        auto_grade="llm_judge",
        answer_key={"rubric": "Translate to natural Turkish only."},
    )
    turkish_row["language"] = "tr"
    turkish_row["language_name"] = "Turkish"
    rows = [
        {"row_idx": 0, "row": arabic_proverb_row, "truncated_cells": []},
        {"row_idx": 1, "row": arabic_grammar_row, "truncated_cells": []},
        {"row_idx": 2, "row": turkish_row, "truncated_cells": []},
        {
            "row_idx": 3,
            "row": _row(
                row_id="S1-I1-999",
                axis="I",
                category="reasoning",
                auto_grade="answer_match",
                answer_key={"correct": "two weighings"},
            ),
            "truncated_cells": [],
        },
    ][offset : offset + length]
    payload = {
        "features": [{"name": name} for name in rows[0]["row"]] if rows else [],
        "rows": rows,
        "num_rows_total": 4,
        "partial": False,
    }
    return FetchedResource(
        url=url,
        status_code=200,
        content_type="application/json",
        text=json.dumps(payload),
        fetcher="fake",
    )


def _fake_p3_canary_repair_v3_fetcher(url: str, timeout_seconds: int = 30) -> FetchedResource:
    del timeout_seconds
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    offset = int(query.get("offset", ["0"])[0])
    length = int(query.get("length", ["100"])[0])
    arabic_grammar_row = _row(
        row_id="S1-I4A-065",
        axis="I",
        category="multilingual_ar",
        auto_grade="llm_judge",
        answer_key={"rubric": "Correct the Arabic sentence and explain the grammar errors."},
    )
    arabic_grammar_row["subcategory"] = "grammar_ar"
    arabic_grammar_row["language"] = "ar"
    arabic_grammar_row["language_name"] = "Arabic"
    arabic_proverb_row = _row(
        row_id="S1-I4A-062",
        axis="I",
        category="multilingual_ar",
        auto_grade="llm_judge",
        answer_key={"rubric": "Explain the proverb and include a real-life example in Arabic."},
    )
    arabic_proverb_row["subcategory"] = "proverb_ar"
    arabic_proverb_row["language"] = "ar"
    arabic_proverb_row["language_name"] = "Arabic"
    rows = [
        {"row_idx": 0, "row": arabic_grammar_row, "truncated_cells": []},
        {"row_idx": 1, "row": arabic_proverb_row, "truncated_cells": []},
    ][offset : offset + length]
    payload = {
        "features": [{"name": name} for name in rows[0]["row"]] if rows else [],
        "rows": rows,
        "num_rows_total": 2,
        "partial": False,
    }
    return FetchedResource(
        url=url,
        status_code=200,
        content_type="application/json",
        text=json.dumps(payload),
        fetcher="fake",
    )


def _fake_p3_canary_repair_v4_fetcher(url: str, timeout_seconds: int = 30) -> FetchedResource:
    return _fake_p3_canary_repair_v3_fetcher(url, timeout_seconds=timeout_seconds)


def _fake_p3_canary_repair_v6_fetcher(url: str, timeout_seconds: int = 30) -> FetchedResource:
    del timeout_seconds
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    offset = int(query.get("offset", ["0"])[0])
    length = int(query.get("length", ["100"])[0])
    portuguese_row = _row(
        row_id="S1-I4P-069",
        axis="I",
        category="multilingual_pt",
        auto_grade="llm_judge",
        answer_key={"rubric": "Give 3 concrete Portuguese variant differences."},
    )
    portuguese_row["subcategory"] = "linguistic_pt"
    portuguese_row["language"] = "pt"
    portuguese_row["language_name"] = "Portuguese"
    arabic_grammar_row = _row(
        row_id="S1-I4A-065",
        axis="I",
        category="multilingual_ar",
        auto_grade="llm_judge",
        answer_key={"rubric": "Correct the Arabic sentence and explain the grammar errors."},
    )
    arabic_grammar_row["subcategory"] = "grammar_ar"
    arabic_grammar_row["language"] = "ar"
    arabic_grammar_row["language_name"] = "Arabic"
    rows = [
        {"row_idx": 0, "row": _row(
            row_id="S1-I1-008",
            axis="I",
            category="reasoning",
            auto_grade="answer_match",
            answer_key={"correct": "Two weighings."},
        ), "truncated_cells": []},
        {"row_idx": 1, "row": _row(
            row_id="S1-I5-050",
            axis="I",
            category="knowledge_synthesis",
            auto_grade="llm_judge",
            answer_key={"rubric": "Give 3 reasons to be skeptical."},
        ), "truncated_cells": []},
        {"row_idx": 2, "row": _row(
            row_id="S1-I6-059",
            axis="I",
            category="metacognition",
            auto_grade="llm_judge",
            answer_key={"rubric": "Find the hidden assumption and give a nuanced conclusion."},
        ), "truncated_cells": []},
        {"row_idx": 3, "row": _row(
            row_id="S1-H1-010",
            axis="H",
            category="hallucination_trap",
            auto_grade="json_field_check",
            answer_key={"trap_detected": True},
        ), "truncated_cells": []},
        {"row_idx": 4, "row": portuguese_row, "truncated_cells": []},
        {"row_idx": 5, "row": _row(
            row_id="S1-H4-033",
            axis="H",
            category="self_correction",
            auto_grade="self_correction_check",
            answer_key={"correct": "91 is not prime."},
        ), "truncated_cells": []},
        {"row_idx": 6, "row": arabic_grammar_row, "truncated_cells": []},
    ][offset : offset + length]
    payload = {
        "features": [{"name": name} for name in rows[0]["row"]] if rows else [],
        "rows": rows,
        "num_rows_total": 7,
        "partial": False,
    }
    return FetchedResource(
        url=url,
        status_code=200,
        content_type="application/json",
        text=json.dumps(payload),
        fetcher="fake",
    )


def _fake_p3_canary_repair_v7_fetcher(url: str, timeout_seconds: int = 30) -> FetchedResource:
    del timeout_seconds
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    offset = int(query.get("offset", ["0"])[0])
    length = int(query.get("length", ["100"])[0])
    portuguese_row = _row(
        row_id="S1-I4P-069",
        axis="I",
        category="multilingual_pt",
        auto_grade="llm_judge",
        answer_key={"rubric": "Give 3 concrete Portuguese variant differences."},
    )
    portuguese_row["subcategory"] = "linguistic_pt"
    portuguese_row["language"] = "pt"
    portuguese_row["language_name"] = "Portuguese"
    korean_row = _row(
        row_id="S1-I4K-071",
        axis="I",
        category="multilingual_ko",
        auto_grade="llm_judge",
        answer_key={"rubric": "Preserve Korean meaning and register."},
    )
    korean_row["language"] = "ko"
    korean_row["language_name"] = "Korean"
    turkish_row = _row(
        row_id="S1-I4T-073",
        axis="I",
        category="multilingual_tr",
        auto_grade="llm_judge",
        answer_key={"rubric": "Produce a natural Turkish translation only."},
    )
    turkish_row["language"] = "tr"
    turkish_row["language_name"] = "Turkish"
    arabic_grammar_row = _row(
        row_id="S1-I4A-065",
        axis="I",
        category="multilingual_ar",
        auto_grade="llm_judge",
        answer_key={"rubric": "Correct the Arabic sentence and explain the grammar errors."},
    )
    arabic_grammar_row["subcategory"] = "grammar_ar"
    arabic_grammar_row["language"] = "ar"
    arabic_grammar_row["language_name"] = "Arabic"
    rows = [
        {"row_idx": 0, "row": _row(
            row_id="S1-I1-008",
            axis="I",
            category="reasoning",
            auto_grade="answer_match",
            answer_key={"correct": "Two weighings."},
        ), "truncated_cells": []},
        {"row_idx": 1, "row": _row(
            row_id="S1-I5-050",
            axis="I",
            category="knowledge_synthesis",
            auto_grade="llm_judge",
            answer_key={"rubric": "Give a bounded synthesis with direct conclusion first."},
        ), "truncated_cells": []},
        {"row_idx": 2, "row": _row(
            row_id="S1-I6-059",
            axis="I",
            category="metacognition",
            auto_grade="llm_judge",
            answer_key={"rubric": "Find the hidden assumption and give a nuanced conclusion."},
        ), "truncated_cells": []},
        {"row_idx": 3, "row": portuguese_row, "truncated_cells": []},
        {"row_idx": 4, "row": korean_row, "truncated_cells": []},
        {"row_idx": 5, "row": _row(
            row_id="S1-H1-010",
            axis="H",
            category="hallucination_trap",
            auto_grade="json_field_check",
            answer_key={"trap_detected": True},
        ), "truncated_cells": []},
        {"row_idx": 6, "row": turkish_row, "truncated_cells": []},
        {"row_idx": 7, "row": arabic_grammar_row, "truncated_cells": []},
    ][offset : offset + length]
    payload = {
        "features": [{"name": name} for name in rows[0]["row"]] if rows else [],
        "rows": rows,
        "num_rows_total": 8,
        "partial": False,
    }
    return FetchedResource(
        url=url,
        status_code=200,
        content_type="application/json",
        text=json.dumps(payload),
        fetcher="fake",
    )


def _fake_p3_semantic_v2_fetcher(url: str, timeout_seconds: int = 30) -> FetchedResource:
    del timeout_seconds
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    offset = int(query.get("offset", ["0"])[0])
    length = int(query.get("length", ["100"])[0])
    korean_row = _row(
        row_id="S1-I5-KO",
        axis="I",
        category="multilingual_ko",
        auto_grade="llm_judge",
        answer_key={"rubric": "Preserve Korean and answer semantically."},
    )
    korean_row["language"] = "ko"
    korean_row["language_name"] = "Korean"
    rows = [
        {
            "row_idx": 0,
            "row": _row(
                row_id="S1-I5-KS",
                axis="I",
                category="knowledge_synthesis",
                auto_grade="llm_judge",
                answer_key={"rubric": "Use bounded synthesis."},
            ),
            "truncated_cells": [],
        },
        {
            "row_idx": 1,
            "row": _row(
                row_id="S1-H3-RB",
                axis="H",
                category="refusal_balance",
                auto_grade="llm_judge",
                answer_key={"rubric": "Do not refuse safe tasks."},
            ),
            "truncated_cells": [],
        },
        {
            "row_idx": 2,
            "row": korean_row,
            "truncated_cells": [],
        },
        {
            "row_idx": 3,
            "row": _row(
                row_id="S1-I1-999",
                axis="I",
                category="reasoning",
                auto_grade="answer_match",
                answer_key={"correct": "2nd place"},
            ),
            "truncated_cells": [],
        },
    ][offset : offset + length]
    payload = {
        "features": [{"name": name} for name in rows[0]["row"]] if rows else [],
        "rows": rows,
        "num_rows_total": 4,
        "partial": False,
    }
    return FetchedResource(
        url=url,
        status_code=200,
        content_type="application/json",
        text=json.dumps(payload),
        fetcher="fake",
    )


def _fake_llm_judge_fetcher(url: str, timeout_seconds: int = 30) -> FetchedResource:
    del timeout_seconds
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    offset = int(query.get("offset", ["0"])[0])
    length = int(query.get("length", ["100"])[0])
    rows = [
        {
            "row_idx": 0,
            "row": _row(
                row_id="S1-I5-999",
                axis="I",
                category="knowledge_synthesis",
                auto_grade="llm_judge",
                answer_key={
                    "rubric": "Award up to 10 for a concise correct explanation.",
                    "correct": "Opportunity cost is the value of the best forgone alternative.",
                },
            ),
            "truncated_cells": [],
        },
    ][offset : offset + length]
    payload = {
        "features": [{"name": name} for name in rows[0]["row"]] if rows else [],
        "rows": rows,
        "num_rows_total": 1,
        "partial": False,
    }
    return FetchedResource(
        url=url,
        status_code=200,
        content_type="application/json",
        text=json.dumps(payload),
        fetcher="fake",
    )


class _FakeRubricJudge:
    def __init__(
        self,
        *,
        score: float,
        reason: str,
        input_tokens_estimate: int | None = None,
        output_tokens_estimate: int | None = None,
    ) -> None:
        self.score = score
        self.reason = reason
        self.input_tokens_estimate = input_tokens_estimate
        self.output_tokens_estimate = output_tokens_estimate
        self.calls: list[dict[str, object]] = []

    def __call__(self, row: dict[str, object], response: str) -> dict[str, object]:
        self.calls.append({"row_id": row["id"], "response": response})
        payload: dict[str, object] = {
            "score": self.score,
            "grading_method": "openai_compatible_rubric_judge",
            "grading_reason": self.reason,
        }
        if self.input_tokens_estimate is not None:
            payload["input_tokens_estimate"] = self.input_tokens_estimate
        if self.output_tokens_estimate is not None:
            payload["output_tokens_estimate"] = self.output_tokens_estimate
        return payload


class _FakeChatClient:
    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.calls: list[dict[str, object]] = []

    def __call__(
        self,
        *,
        model: str,
        messages: list[dict[str, str]],
        temperature: float,
        max_tokens: int,
        timeout_seconds: int,
        base_url: str,
        provider: str = "openai-compatible",
        api_key_env: str | None = None,
        extra_body: dict[str, object] | None = None,
    ) -> dict[str, object]:
        del temperature, max_tokens, timeout_seconds
        user_message = messages[-1]["content"]
        row_id = user_message.split("Question ID: ", 1)[1].splitlines()[0]
        self.calls.append({
            "model": model,
            "row_id": row_id,
            "messages": messages,
            "base_url": base_url,
            "provider": provider,
            "api_key_env": api_key_env,
            "extra_body": extra_body,
        })
        return {
            "content": self.responses[row_id],
            "latency_seconds": 0.01,
            "input_tokens_estimate": 10,
            "output_tokens_estimate": 5,
            "raw": {"fake": True},
        }


def _prompt_profile_registration_overlay(*, after_text: str) -> dict[str, object]:
    return {
        "schema_version": "2026-06-05.prompt-profile-registration.v1",
        "status": "registered",
        "registration_plan_ref": "inline",
        "base_profile_id": "p3-dev-v2",
        "proposed_profile_id": "p3-dev-v2-overlay-001",
        "registered_profile": {
            "registered": True,
            "registered_profile_id": "p3-dev-v2-overlay-001",
            "expected_profile_id": "p3-dev-v2-overlay-001",
            "registry_ref": "inline",
        },
        "registry_entry": {
            "profile_id": "p3-dev-v2-overlay-001",
            "base_profile_id": "p3-dev-v2",
            "benchmark_id": "smol_worldcup",
            "patch_id": "slice-patch-overlay-001",
            "operation": "add_prompt_profile",
            "active": True,
            "module_id": "multilingual_variant_explanation",
            "section_id": "output_format",
            "change_surface": "prompt_section",
            "edit_scope": "single_section",
            "materialized_change": {
                "before_text": "return concise JSON",
                "after_text": after_text,
                "protected_slices": ["multilingual_tr"],
                "protected_sections": ["role"],
            },
        },
        "required_pre_execution_checks": [
            "prompt_leakage_audit",
            "target_smoke",
            "dev_model_eval",
            "evaluate_gate_policy",
        ],
        "gate": {
            "canary_allowed": False,
            "promotion_ready": False,
        },
        "claim_boundary": "fixture registration only",
        "official_scores_claimed": False,
    }


def _fake_rows() -> list[dict[str, object]]:
    rows = [
        _row(
            row_id="S1-H1-001",
            axis="H",
            category="hallucination_trap",
            auto_grade="json_field_check",
            answer_key={"trap_detected": True},
        ),
        _row(
            row_id="S1-H3-002",
            axis="H",
            category="refusal_balance",
            auto_grade="refusal_check",
            answer_key={"should_refuse": False},
        ),
        _row(
            row_id="S1-I2-003",
            axis="I",
            category="math",
            auto_grade="numeric_match",
            answer_key={"correct": "42"},
        ),
        _row(
            row_id="S1-I1-004",
            axis="I",
            category="reasoning",
            auto_grade="answer_match",
            answer_key={"correct": "Bob"},
        ),
    ]
    return [{"row_idx": index, "row": row, "truncated_cells": []} for index, row in enumerate(rows)]


def _row(
    *,
    row_id: str,
    axis: str,
    auto_grade: str,
    answer_key: dict[str, object],
    category: str = "unit",
) -> dict[str, object]:
    return {
        "id": row_id,
        "shift_axis": axis,
        "category": category,
        "subcategory": "unit",
        "difficulty": "standard",
        "prompt": "Respond in JSON format.",
        "answer_key": json.dumps(answer_key),
        "explanation": "unit test",
        "grading_rule": "unit test",
        "auto_grade": auto_grade,
        "max_score": 10,
        "anchor": False,
        "season": 1,
        "version": "1.0",
        "language": "en",
        "language_name": "English",
    }
