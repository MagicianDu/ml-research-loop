from __future__ import annotations

import json
from pathlib import Path

import lib.failure_driven_proposal as fdp
from lib.failure_driven_proposal import (
    build_cp_bench_proposal_effectiveness_bundle,
    build_mixed_signal_proposal_effectiveness_audit,
    build_multi_optimizer_candidate_race,
    build_proposal_effectiveness_claim_audit,
    build_cross_task_proposal_effectiveness_summary,
    build_fasttext_proposal_effectiveness_bundle,
    build_real_paper_proposal_effectiveness_bundle,
    build_smol_worldcup_canary_control_arm_handoff,
    build_smol_worldcup_canary_control_arm_execution_bundle,
    build_smol_worldcup_canary_failure_slice_audit,
    build_smol_worldcup_promotion_gate_refresh,
    build_smol_worldcup_proposal_effectiveness_bundle,
    build_smol_worldcup_promotion_gate,
    build_smol_worldcup_cached_confidence_scoring_gate,
    build_smol_worldcup_confidence_variance_gate,
    build_smol_worldcup_result_analysis,
    build_failure_driven_proposal_context,
    build_failure_driven_client_proposal_templates,
    build_failure_driven_proposal_handoff,
    build_proposal_pattern_memory,
    bridge_failure_driven_outcome_to_memory_card,
    evaluate_failure_driven_proposal_effectiveness,
    extract_failure_records,
    generate_failure_driven_proposals,
    rank_failure_driven_proposals,
    retrieve_proposal_patterns,
    record_proposal_outcome,
    run_multi_optimizer_candidate_race,
    run_method_search_trajectory,
)
from lib.proposal_contract import validate_client_proposal
from lib.research_memory import ResearchMemoryCard


def _proposal_card() -> dict:
    return {
        "proposal_id": "round-002-canary-fix",
        "proposal_type": "failure_fix",
        "based_on_failures": ["round-001:canary_not_confirmed:1"],
        "intent": "Tighten one routing branch to preserve dev gain on canary.",
        "change_surface": "routing",
        "target_scope": "single router prompt block",
        "verification_plan": {"first_split": "dev", "promotion_split": "canary"},
        "rollback_rule": {"if": ["canary_delta_lt_0"]},
        "claim_boundary": "local proposal only",
        "official_scores_claimed": False,
    }


def _race_proposal(proposal_id: str, operator_id: str, optimizer: str) -> dict:
    return {
        "proposal_id": proposal_id,
        "operator_id": operator_id,
        "why_this_operator_applies": (
            f"{operator_id} matches the {optimizer} candidate change surface."
        ),
        "hypothesis": f"{optimizer} may improve the target slice after gate validation.",
        "change_surface": "prompt_or_model_candidate",
        "expected_effect": "gate outcome decides whether this candidate improves anything",
        "risk": "candidate may overfit local evidence",
        "cheapest_validation": "run the shared dev/canary gate",
        "rollback_or_stop_condition": "stop on hard blocker or non-positive gate delta",
    }


def _race_slice_repair_context() -> dict:
    return {
        "schema_version": "test.slice-repair-context.v1",
        "recommended_patch_contract": {
            "module_id": "router",
            "section_id": "country_aliases",
            "target_slice": "alias_confusion",
            "based_on_slices": ["alias_confusion"],
            "before_text": "Resolve country aliases conservatively.",
            "protected_slices": ["exact_match"],
            "protected_sections": ["role"],
        },
        "official_scores_claimed": False,
    }


def _write_fixture_optimizer_package(tmp_path: Path) -> str:
    package_dir = tmp_path / "race_fixture_optimizer"
    package_dir.mkdir()
    (package_dir / "__init__.py").write_text(
        """
__version__ = "0.1.0"


class FixtureOptimizerAdapter:
    def generate_slice_patch_candidate(self, payload):
        contract = payload["contract"]
        return {
            "after_text": (
                contract.get("before_text", "")
                + "\\nfixture optimizer: add an alias-confusion guard"
            ),
            "critic_feedback": "Fixture optimizer runtime generated this candidate.",
            "candidate_strategy": "fixture_python_package_runtime",
        }
""".lstrip(),
        encoding="utf-8",
    )
    return "race_fixture_optimizer"


def _python_package_optimizer_manifest(package_import: str) -> dict:
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
                    "package_runtime_candidate",
                ],
                "runtime_entrypoint": {
                    "kind": "python-package",
                    "package_import": package_import,
                    "package_name": package_import,
                    "adapter_class": "FixtureOptimizerAdapter",
                    "candidate_method": "generate_slice_patch_candidate",
                },
            }
        ],
        "gate_policies": [],
        "official_scores_claimed": False,
    }


def _smol_readiness_rows() -> list[dict]:
    return [
        {
            "id": "S1-H1-001",
            "shift_axis": "H",
            "category": "reasoning",
            "subcategory": "answer_match",
            "auto_grade": "answer_match",
            "max_score": 10,
            "prompt": "Which country won the 2002 FIFA World Cup?",
            "answer_key": {"answer": "Brazil"},
        },
        {
            "id": "S1-H1-002",
            "shift_axis": "H",
            "category": "reasoning",
            "subcategory": "answer_match",
            "auto_grade": "answer_match",
            "max_score": 10,
            "prompt": "Which country hosted the 2010 FIFA World Cup?",
            "answer_key": {"answer": "South Africa"},
        },
        {
            "id": "S1-I1-003",
            "shift_axis": "I",
            "category": "reasoning",
            "subcategory": "answer_match",
            "auto_grade": "answer_match",
            "max_score": 10,
            "prompt": "Which country won the 2018 FIFA World Cup?",
            "answer_key": {"answer": "France"},
        },
        {
            "id": "S1-I1-004",
            "shift_axis": "I",
            "category": "reasoning",
            "subcategory": "answer_match",
            "auto_grade": "answer_match",
            "max_score": 10,
            "prompt": "Which country won the 2022 FIFA World Cup?",
            "answer_key": {"answer": "Argentina"},
        },
    ]


def _smol_readiness_completion(**kwargs: object) -> dict[str, object]:
    messages = kwargs.get("messages")
    text = "\n".join(
        str(message.get("content") or "")
        for message in messages
        if isinstance(message, dict)
    )
    answers = {
        "S1-H1-001": "Brazil",
        "S1-H1-002": "South Africa",
        "S1-I1-003": "France",
        "S1-I1-004": "Argentina",
    }
    answer = "wrong"
    if "fixture optimizer: add an alias-confusion guard" in text:
        for row_id, expected in answers.items():
            if row_id in text:
                answer = expected
                break
    return {
        "content": json.dumps(
            {
                "answer": answer,
                "confidence": 90,
                "is_verified": True,
                "source_note": "fixture local eval",
            }
        ),
        "input_tokens_estimate": 8,
        "output_tokens_estimate": 4,
        "latency_seconds": 0.001,
    }


def test_real_benchmark_readiness_run_generates_gate_from_smol_eval(
    tmp_path: Path,
    monkeypatch,
) -> None:
    package_import = _write_fixture_optimizer_package(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))

    payload = fdp.run_real_benchmark_readiness_run(
        run_name="smol-worldcup-real-readiness",
        benchmark_id="smol_worldcup",
        objective="use real local benchmark outcomes to gate optimizer candidates",
        rows=_smol_readiness_rows(),
        chat_completion=_smol_readiness_completion,
        context=_race_slice_repair_context(),
        round_count=3,
        optimizer_sources=["python-package-optimizer-plugin"],
        operators=["adapt", "combine"],
        optimizer_gate_plugin_manifests=[
            _python_package_optimizer_manifest(package_import)
        ],
        output_dir=tmp_path / "readiness",
        output_path=tmp_path / "real-benchmark-readiness-run.json",
    )

    assert payload["schema_version"] == "2026-06-27.real-benchmark-readiness-run.v1"
    assert payload["status"] == "completed"
    assert payload["benchmark_id"] == "smol_worldcup"
    assert payload["round_count"] == 3
    assert payload["baseline"]["dev"]["metrics"]["SHIFT"] == 0.0
    assert payload["baseline"]["canary"]["metrics"]["SHIFT"] == 0.0
    assert payload["real_optimizer_candidate_count"] == 3
    assert payload["fallback_candidate_count"] == 0
    assert payload["real_eval_outcome_count"] == 3
    assert payload["rounds"][0]["gate_results"][0]["status"] == "passed"
    assert payload["rounds"][0]["gate_results"][0]["score"] > 0.0
    assert payload["rounds"][0]["gate_results"][0]["eval_outcome"]["dev_delta"]["SHIFT"] > 0.0
    assert payload["rounds"][0]["gate_results"][0]["eval_outcome"]["canary_delta"]["SHIFT"] >= 0.0
    assert payload["rounds"][0]["winner"]["proposal_id"] == "python-package-optimizer-plugin-001"
    assert payload["gate_feedback_memory"]["operator_weights"]["adapt"] > 1.0
    assert payload["acceptance_answers"] == {
        "baseline_reproduced": True,
        "real_optimizer_source_executed": True,
        "real_source_candidate_entered_method_search_trial": True,
        "gate_winner_selected": True,
        "gate_from_real_eval_outcomes": True,
        "memory_weight_updated": True,
        "sampler_changed_direction_across_rounds": True,
        "official_scores_claimed": False,
        "current_evidence_scope": "local_benchmark_readiness_run",
    }
    assert payload["claim_boundary"]["official_scores_claimed"] is False
    assert payload["executes_experiment"] is True
    assert Path(payload["output_path"]).exists()
    assert (
        tmp_path
        / "readiness"
        / "round-001"
        / "candidate-evals"
        / "python-package-optimizer-plugin-001"
        / "dev-eval.json"
    ).exists()


def test_multi_optimizer_candidate_race_selects_gate_winner_and_updates_memory(
    tmp_path: Path,
) -> None:
    candidate_sources = {
        "sources": [
            {
                "source_id": "llm-hexagon",
                "optimizer": "llm",
                "proposals": [_race_proposal("llm-001", "adapt", "llm")],
            },
            {
                "source_id": "optuna-tpe",
                "optimizer": "optuna",
                "proposals": [_race_proposal("optuna-049", "combine", "optuna")],
            },
            {
                "source_id": "textgrad-package",
                "optimizer": "textgrad",
                "proposals": [_race_proposal("textgrad-001", "adapt", "textgrad")],
            },
            {
                "source_id": "dspy-mipro",
                "optimizer": "dspy",
                "proposals": [_race_proposal("dspy-001", "combine", "dspy")],
            },
            {
                "source_id": "heuristic-control",
                "optimizer": "heuristic",
                "proposals": [_race_proposal("heuristic-001", "invert", "heuristic")],
            },
        ]
    }
    gate_results = {
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
                "score": 0.70,
                "metric_delta": {"accuracy": 0.01},
                "hard_blockers": [],
            },
            {
                "proposal_id": "textgrad-001",
                "operator_id": "adapt",
                "status": "passed",
                "score": 0.69,
                "metric_delta": {"accuracy": 0.0},
                "hard_blockers": [],
            },
            {
                "proposal_id": "dspy-001",
                "operator_id": "combine",
                "status": "blocked",
                "score": 0.68,
                "hard_blockers": ["cost_budget_exceeded"],
            },
            {
                "proposal_id": "heuristic-001",
                "operator_id": "invert",
                "status": "blocked",
                "score": 0.65,
                "hard_blockers": ["no_local_improvement"],
            },
        ]
    }

    payload = build_multi_optimizer_candidate_race(
        race_name="sst2-multi-optimizer-race",
        objective="let multiple optimizer sources compete under one gate",
        candidate_sources=candidate_sources,
        gate_results=gate_results,
        operators=["combine", "adapt", "invert"],
        output_dir=tmp_path / "race-artifacts",
        feedback_store_path=tmp_path / "gate-feedback-memory-store.json",
        output_path=tmp_path / "multi-optimizer-candidate-race.json",
    )

    assert payload["schema_version"] == "2026-06-25.multi-optimizer-candidate-race.v1"
    assert payload["source_count"] == 5
    assert payload["candidate_count"] == 5
    assert payload["winner"]["proposal_id"] == "optuna-049"
    assert payload["winner"]["optimizer"] == "optuna"
    assert payload["winner"]["score"] == 0.7
    assert payload["study"]["trial_count"] == 5
    assert {trial["state"] for trial in payload["study"]["trials"]} == {
        "COMPLETE",
        "PRUNED",
    }
    assert payload["gate_feedback_memory"]["operator_weights"]["invert"] < 1.0
    promoted_proposal_ids = {
        item["proposal_id"] for item in payload["gate_feedback_memory"]["promoted_patterns"]
    }
    blocked_proposal_ids = {
        item["proposal_id"] for item in payload["gate_feedback_memory"]["blocked_patterns"]
    }
    assert "optuna-049" in promoted_proposal_ids
    assert {"llm-001", "dspy-001", "heuristic-001"}.issubset(blocked_proposal_ids)
    assert payload["acceptance_answers"]["winner_selected_by_gate"] is True
    assert payload["official_scores_claimed"] is False
    assert Path(payload["output_path"]).exists()


def test_run_multi_optimizer_candidate_race_generates_sources_then_gate_races(
    tmp_path: Path,
) -> None:
    context = {
        "schema_version": "test.slice-repair-context.v1",
        "recommended_patch_contract": {
            "module_id": "router",
            "section_id": "country_aliases",
            "target_slice": "alias_confusion",
            "based_on_slices": ["alias_confusion"],
            "before_text": "Resolve country aliases conservatively.",
            "protected_slices": ["exact_match"],
            "protected_sections": ["role"],
        },
        "official_scores_claimed": False,
    }
    gate_results = {
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
                "score": 0.71,
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
    }

    payload = run_multi_optimizer_candidate_race(
        race_name="execution-capable-race",
        objective="generate and compare multiple optimizer candidates",
        context=context,
        gate_results=gate_results,
        optimizer_sources=["llm", "optuna", "textgrad", "dspy", "heuristic"],
        operators=["combine", "adapt", "separate"],
        llm_proposals={"proposals": [_race_proposal("llm-001", "adapt", "llm")]},
        execute_optimizer_runtimes=False,
        allow_style_fallback=True,
        output_dir=tmp_path / "run",
        feedback_store_path=tmp_path / "gate-feedback-memory-store.json",
        output_path=tmp_path / "multi-optimizer-candidate-race-run.json",
    )

    assert payload["schema_version"] == (
        "2026-06-25.multi-optimizer-candidate-race-run.v1"
    )
    assert payload["status"] == "completed"
    assert payload["source_generation"]["source_count"] == 5
    assert payload["source_generation"]["generated_candidate_count"] == 5
    assert payload["acceptance_answers"]["parallel_generation_used"] is True
    assert payload["winner"]["proposal_id"] == "optuna-001"
    assert payload["winner"]["optimizer"] == "optuna"
    assert payload["race"]["study"]["trial_count"] == 5
    assert payload["gate_feedback_memory"]["operator_feedback"]
    assert payload["official_scores_claimed"] is False
    assert Path(payload["output_path"]).exists()
    assert (tmp_path / "run" / "generated-candidate-sources.json").exists()


def test_optimization_run_executes_real_optimizer_source_without_counting_fallback(
    tmp_path: Path,
    monkeypatch,
) -> None:
    package_import = _write_fixture_optimizer_package(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    gate_results = {
        "gate_results": [
            {
                "proposal_id": "python-package-optimizer-plugin-001",
                "operator_id": "adapt",
                "status": "passed",
                "score": 0.74,
                "hard_blockers": [],
            }
        ]
    }

    payload = run_multi_optimizer_candidate_race(
        race_name="optimization-run-real-source",
        objective="try real optimizer runtimes before gate selection",
        context=_race_slice_repair_context(),
        gate_results=gate_results,
        optimizer_sources=["python-package-optimizer-plugin"],
        operators=["adapt", "combine"],
        optimizer_gate_plugin_manifests=[
            _python_package_optimizer_manifest(package_import)
        ],
        mode="optimization-run",
        output_dir=tmp_path / "run",
        feedback_store_path=tmp_path / "gate-feedback-memory-store.json",
        output_path=tmp_path / "multi-optimizer-candidate-race-run.json",
    )

    assert payload["mode"] == "optimization-run"
    assert payload["source_generation"]["real_optimizer_candidate_count"] == 1
    assert payload["source_generation"]["fallback_candidate_count"] == 0
    assert payload["source_generation"]["diagnostic_candidate_count"] == 0
    assert payload["acceptance_answers"]["fallback_candidates_counted_as_real"] is False
    assert payload["acceptance_answers"]["real_optimizer_candidate_count"] == 1
    assert payload["winner"]["proposal_id"] == "python-package-optimizer-plugin-001"
    assert payload["winner"]["winner_kind"] == "optimizer_winner"
    assert payload["winner"]["counts_as_real_optimizer_winner"] is True
    assert payload["acceptance_answers"]["proposal_selection"] == {
        "winner_proposal_id": "python-package-optimizer-plugin-001",
        "selected_candidate_ids": ["python-package-optimizer-plugin-001"],
        "pruned_candidate_ids": [],
        "blocked_candidate_ids": [],
    }
    assert payload["race"]["study"]["trial_count"] == 1
    assert payload["gate_feedback_memory"]["operator_weights"]["adapt"] > 1.0
    assert payload["official_scores_claimed"] is False


def test_optimization_run_executes_configured_llm_source_as_real_candidate(
    tmp_path: Path,
) -> None:
    calls: list[dict[str, object]] = []

    def fake_completion(**kwargs: object) -> dict[str, object]:
        calls.append(kwargs)
        return {
            "payload": {
                "proposals": [
                    {
                        "proposal_id": "llm-live-001",
                        "operator_id": "adapt",
                        "why_this_operator_applies": "adapt targets the failing slice directly",
                        "hypothesis": "A bounded LLM proposal may improve the target slice",
                        "change_surface": "prompt_section",
                        "expected_effect": "gate decides whether the proposal helps",
                        "risk": "may overfit local evidence",
                        "cheapest_validation": "run local gate",
                        "rollback_or_stop_condition": "stop on hard blocker",
                    }
                ]
            }
        }

    payload = run_multi_optimizer_candidate_race(
        race_name="optimization-run-live-llm-source",
        objective="try configured live llm proposal generation",
        context=_race_slice_repair_context(),
        gate_results={
            "gate_results": [
                {
                    "proposal_id": "llm-live-001",
                    "operator_id": "adapt",
                    "status": "passed",
                    "score": 0.77,
                    "hard_blockers": [],
                }
            ]
        },
        optimizer_sources=["llm"],
        operators=["adapt"],
        mode="optimization-run",
        llm_completion_fn=fake_completion,
        optimizer_model="fixture-llm",
        optimizer_base_url="http://127.0.0.1:65535/v1",
        optimizer_api_key="FIXTURE_API_KEY",
        optimizer_timeout_seconds=7,
        optimizer_temperature=0.3,
        optimizer_max_tokens=321,
        output_dir=tmp_path / "run",
        feedback_store_path=tmp_path / "gate-feedback-memory-store.json",
        output_path=tmp_path / "multi-optimizer-candidate-race-run.json",
    )

    assert calls
    assert calls[0]["model"] == "fixture-llm"
    assert calls[0]["base_url"] == "http://127.0.0.1:65535/v1"
    assert calls[0]["api_key_env"] == "FIXTURE_API_KEY"
    assert calls[0]["timeout_seconds"] == 7
    assert calls[0]["temperature"] == 0.3
    assert calls[0]["max_tokens"] == 321
    assert payload["source_generation"]["real_optimizer_candidate_count"] == 1
    assert payload["candidate_pool"][0]["candidate_origin"] == "real_optimizer"
    assert payload["candidate_pool"][0]["counts_as_real_optimizer_candidate"] is True
    assert payload["winner"]["winner_kind"] == "optimizer_winner"
    assert payload["official_scores_claimed"] is False


def test_review_dry_run_fallback_winner_is_diagnostic(tmp_path: Path) -> None:
    gate_results = {
        "gate_results": [
            {
                "proposal_id": "dspy-001",
                "operator_id": "combine",
                "status": "passed",
                "score": 0.81,
                "hard_blockers": [],
            }
        ]
    }

    payload = run_multi_optimizer_candidate_race(
        race_name="review-dry-run-fallback",
        objective="keep fallback available only as review diagnostic evidence",
        context=_race_slice_repair_context(),
        gate_results=gate_results,
        optimizer_sources=["dspy"],
        operators=["combine"],
        mode="review/dry-run",
        output_dir=tmp_path / "run",
        feedback_store_path=tmp_path / "gate-feedback-memory-store.json",
        output_path=tmp_path / "multi-optimizer-candidate-race-run.json",
    )

    assert payload["mode"] == "review/dry-run"
    assert payload["source_generation"]["real_optimizer_candidate_count"] == 0
    assert payload["source_generation"]["fallback_candidate_count"] == 1
    assert payload["winner"]["proposal_id"] == "dspy-001"
    assert payload["winner"]["winner_kind"] == "local_diagnostic_winner"
    assert payload["winner"]["counts_as_real_optimizer_winner"] is False
    assert payload["acceptance_answers"]["fallback_candidates_counted_as_real"] is False
    assert payload["acceptance_answers"]["proposal_selection"] == {
        "winner_proposal_id": "dspy-001",
        "selected_candidate_ids": ["dspy-001"],
        "pruned_candidate_ids": [],
        "blocked_candidate_ids": [],
    }
    assert payload["official_scores_claimed"] is False


def test_run_method_search_trajectory_runs_four_rounds_and_finds_best_path(
    tmp_path: Path,
    monkeypatch,
) -> None:
    package_import = _write_fixture_optimizer_package(tmp_path)
    monkeypatch.syspath_prepend(str(tmp_path))
    completion_calls: list[dict[str, object]] = []

    def fake_completion(**kwargs: object) -> dict[str, object]:
        round_number = len(completion_calls) + 1
        completion_calls.append(kwargs)
        operator_id = "adapt" if round_number == 1 else "combine"
        return {
            "payload": {
                "proposals": [
                    {
                        "proposal_id": f"llm-round-{round_number:03d}",
                        "operator_id": operator_id,
                        "why_this_operator_applies": (
                            f"{operator_id} follows gate memory for round {round_number}"
                        ),
                        "hypothesis": "Gate feedback should decide whether this path improves.",
                        "change_surface": "prompt_section",
                        "expected_effect": "local gate score is the only accepted effect evidence",
                        "risk": "may overfit local validation evidence",
                        "cheapest_validation": "run the shared multi-optimizer gate",
                        "rollback_or_stop_condition": "stop on hard blocker or lower score",
                    }
                ]
            }
        }

    gate_results_by_round = [
        {
            "gate_results": [
                {
                    "proposal_id": "llm-round-001",
                    "operator_id": "adapt",
                    "status": "blocked",
                    "score": 0.61,
                    "hard_blockers": ["canary_regression"],
                },
                {
                    "proposal_id": "python-package-optimizer-plugin-001",
                    "operator_id": "adapt",
                    "status": "blocked",
                    "score": 0.59,
                    "hard_blockers": ["same_surface_regression"],
                },
            ]
        },
        {
            "gate_results": [
                {
                    "proposal_id": "llm-round-002",
                    "operator_id": "combine",
                    "status": "near_pass",
                    "score": 0.72,
                    "hard_blockers": [],
                },
                {
                    "proposal_id": "python-package-optimizer-plugin-001",
                    "operator_id": "adapt",
                    "status": "blocked",
                    "score": 0.64,
                    "hard_blockers": ["repeat_pattern_regression"],
                },
            ]
        },
        {
            "gate_results": [
                {
                    "proposal_id": "llm-round-003",
                    "operator_id": "combine",
                    "status": "passed",
                    "score": 0.78,
                    "hard_blockers": [],
                },
                {
                    "proposal_id": "python-package-optimizer-plugin-001",
                    "operator_id": "adapt",
                    "status": "blocked",
                    "score": 0.65,
                    "hard_blockers": ["repeat_pattern_regression"],
                },
            ]
        },
        {
            "gate_results": [
                {
                    "proposal_id": "llm-round-004",
                    "operator_id": "combine",
                    "status": "passed",
                    "score": 0.80,
                    "hard_blockers": [],
                },
                {
                    "proposal_id": "python-package-optimizer-plugin-001",
                    "operator_id": "adapt",
                    "status": "blocked",
                    "score": 0.63,
                    "hard_blockers": ["repeat_pattern_regression"],
                },
            ]
        },
    ]

    payload = run_method_search_trajectory(
        trajectory_name="four-round-method-search",
        objective="find the best local optimizer path over multiple rounds",
        context=_race_slice_repair_context(),
        gate_results_by_round=gate_results_by_round,
        round_count=4,
        optimizer_sources=["llm", "python-package-optimizer-plugin"],
        operators=["adapt", "combine"],
        optimizer_gate_plugin_manifests=[
            _python_package_optimizer_manifest(package_import)
        ],
        optimizer_model="fixture-llm",
        optimizer_base_url="http://127.0.0.1:65535/v1",
        optimizer_api_key="FIXTURE_API_KEY",
        llm_completion_fn=fake_completion,
        output_dir=tmp_path / "trajectory",
        output_path=tmp_path / "method-search-trajectory.json",
    )

    assert len(completion_calls) == 4
    second_prompt = str(completion_calls[1]["messages"][1]["content"])
    assert "canary_regression" in second_prompt
    assert payload["schema_version"] == "2026-06-27.method-search-trajectory.v1"
    assert payload["status"] == "completed"
    assert payload["round_count"] == 4
    assert payload["real_optimizer_candidate_count"] >= 4
    assert payload["best_path"]["winner"]["proposal_id"] == "llm-round-004"
    assert payload["best_path"]["winner"]["score"] == 0.8
    assert payload["best_path"]["path_summary"]["winning_operator_id"] == "combine"
    assert payload["rounds"][0]["memory_delta"]["downweighted_operator_ids"] == ["adapt"]
    assert "combine" in payload["rounds"][2]["used_operators"]
    assert payload["rounds"][3]["proposal_selection"]["selected_candidate_ids"] == [
        "llm-round-004"
    ]
    assert "python-package-optimizer-plugin-001" in (
        payload["rounds"][3]["proposal_selection"]["pruned_candidate_ids"]
    )
    assert payload["acceptance_answers"]["rounds_executed"] == 4
    assert payload["acceptance_answers"]["best_path_selected_by_gate"] is True
    assert payload["acceptance_answers"]["sampler_changed_direction_across_rounds"] is True
    assert payload["acceptance_answers"]["current_evidence_scope"] == "local_gate_only"
    assert payload["official_scores_claimed"] is False
    assert Path(payload["output_path"]).exists()
    assert (tmp_path / "trajectory" / "round-004" / "multi-optimizer-candidate-race-run.json").exists()


def test_extract_failure_records_from_reflection_writes_jsonl(tmp_path: Path) -> None:
    reflection = tmp_path / "proposal-reflection.json"
    reflection.write_text(
        json.dumps(
            {
                "proposal_id": "round-001",
                "status": "needs_rollback_or_more_evidence",
                "proposal": {
                    "proposal_id": "round-001",
                    "change_surface": "routing",
                    "hypothesis": "A bounded router fix should carry dev gain to canary.",
                },
                "failure_labels": ["canary_not_confirmed"],
                "recommended_next_action": "rollback_or_keep_as_candidate",
                "evaluation": {
                    "metric_before": 80.0,
                    "metric_after": 80.4,
                    "dev_delta": {"SHIFT": 0.4},
                    "canary_delta": {"SHIFT": -0.2},
                    "bad_cases": [{"id": "case-1"}],
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    payload = extract_failure_records(
        reflection,
        output_path=tmp_path / "failure-records.jsonl",
    )

    assert payload["status"] == "completed"
    assert payload["record_count"] == 1
    assert Path(payload["output_path"]).exists()
    record = payload["records"][0]
    assert record["failure_type"] == "canary_not_confirmed"
    assert record["severity"] == "medium"
    assert record["bad_cases"][0]["id"] == "case-1"
    assert record["official_scores_claimed"] is False

    written = [
        json.loads(line)
        for line in Path(payload["output_path"]).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert written[0]["failure_id"] == record["failure_id"]


def test_extract_failure_records_normalizes_metric_rollback_labels_with_canary_split(
    tmp_path: Path,
) -> None:
    reflection = tmp_path / "proposal-reflection.json"
    reflection.write_text(
        json.dumps(
            {
                "proposal_id": "round-002",
                "status": "needs_rollback_or_more_evidence",
                "proposal": {
                    "proposal_id": "round-002",
                    "change_surface": "prompt_profile",
                    "validation_plan": {
                        "first_split": "canary",
                        "promotion_split": "canary",
                    },
                },
                "failure_labels": ["SHIFT_delta_lt_0"],
                "evaluation": {
                    "rollback_reasons": ["SHIFT_delta_lt_0"],
                    "canary_delta": {"SHIFT": -0.4},
                },
            }
        ),
        encoding="utf-8",
    )

    payload = extract_failure_records(reflection)

    assert payload["records"][0]["failure_type"] == "canary_not_confirmed"


def test_extract_failure_records_uses_evaluation_split_before_proposal_promotion_split(
    tmp_path: Path,
) -> None:
    reflection = tmp_path / "proposal-reflection.json"
    reflection.write_text(
        json.dumps(
            {
                "proposal_id": "round-002-dev-check",
                "status": "needs_rollback_or_more_evidence",
                "proposal": {
                    "proposal_id": "round-002-dev-check",
                    "change_surface": "prompt_profile",
                    "validation_plan": {
                        "first_split": "canary",
                        "promotion_split": "canary",
                    },
                },
                "failure_labels": ["SHIFT_delta_lt_0"],
                "evaluation": {
                    "rollback_reasons": ["SHIFT_delta_lt_0"],
                    "dev_delta": {"SHIFT": -6.9},
                    "current_dataset": {"evaluation_split": "dev"},
                },
            }
        ),
        encoding="utf-8",
    )

    payload = extract_failure_records(reflection)

    assert payload["records"][0]["failure_type"] == "metric_regression"
    assert payload["records"][0]["metric_after"] == {"dev": -6.9}


def test_extract_failure_records_derives_bad_cases_from_failure_cases_path(
    tmp_path: Path,
) -> None:
    failure_cases = tmp_path / "failure-cases.json"
    failure_cases.write_text(
        json.dumps(
            [
                {"row_id": "r1", "category": "reasoning", "subcategory": "logic"},
                {"row_id": "r2", "category": "reasoning", "subcategory": "optimization"},
                {"row_id": "r3", "category": "math", "subcategory": "arithmetic"},
                {"row_id": "r4", "category": "multilingual_pt", "subcategory": "idiom_pt"},
            ]
        ),
        encoding="utf-8",
    )
    reflection = tmp_path / "proposal-reflection.json"
    reflection.write_text(
        json.dumps(
            {
                "proposal_id": "round-004",
                "status": "needs_rollback_or_more_evidence",
                "proposal": {
                    "proposal_id": "round-004",
                    "change_surface": "prompt_profile",
                    "hypothesis": "canary should hold",
                    "validation_plan": {
                        "first_split": "canary",
                        "promotion_split": "canary",
                    },
                },
                "failure_labels": ["SHIFT_delta_lt_0"],
                "evaluation": {
                    "rollback_reasons": ["SHIFT_delta_lt_0"],
                    "canary_delta": {"SHIFT": -0.4},
                    "failure_cases_path": str(failure_cases),
                },
            }
        ),
        encoding="utf-8",
    )

    payload = extract_failure_records(reflection)

    record = payload["records"][0]
    assert record["failure_type"] == "canary_not_confirmed"
    assert record["bad_cases"][0]["category"] == "reasoning"
    assert record["bad_cases"][0]["count"] == 2
    assert record["bad_cases"][1]["category"] == "math"
    assert record["bad_cases"][2]["category"] == "multilingual_pt"


def test_extract_failure_records_derives_bad_cases_from_wrapped_failure_cases_path(
    tmp_path: Path,
) -> None:
    failure_cases = tmp_path / "failure-cases.json"
    failure_cases.write_text(
        json.dumps(
            {
                "official_scores_claimed": False,
                "failure_cases": [
                    {"row_id": "r1", "category": "reasoning", "subcategory": "logic"},
                    {"row_id": "r2", "category": "reasoning", "subcategory": "optimization"},
                    {"row_id": "r3", "category": "math", "subcategory": "arithmetic"},
                ],
            }
        ),
        encoding="utf-8",
    )
    reflection = tmp_path / "proposal-reflection.json"
    reflection.write_text(
        json.dumps(
            {
                "proposal_id": "round-005",
                "status": "needs_rollback_or_more_evidence",
                "proposal": {
                    "proposal_id": "round-005",
                    "change_surface": "prompt_profile",
                    "hypothesis": "canary should hold",
                    "validation_plan": {
                        "first_split": "canary",
                        "promotion_split": "canary",
                    },
                },
                "failure_labels": ["SHIFT_delta_lt_0"],
                "evaluation": {
                    "rollback_reasons": ["SHIFT_delta_lt_0"],
                    "canary_delta": {"SHIFT": -0.4},
                    "failure_cases_path": str(failure_cases),
                },
            }
        ),
        encoding="utf-8",
    )

    payload = extract_failure_records(reflection)

    record = payload["records"][0]
    assert record["failure_type"] == "canary_not_confirmed"
    assert record["bad_cases"][0]["category"] == "reasoning"
    assert record["bad_cases"][0]["count"] == 2
    assert record["bad_cases"][1]["category"] == "math"


def test_extract_failure_records_keeps_all_ranked_bad_case_categories(
    tmp_path: Path,
) -> None:
    failure_cases = tmp_path / "failure-cases.json"
    categories = [
        "reasoning",
        "math",
        "metacognition",
        "hallucination_trap",
        "knowledge_synthesis",
        "multilingual_bn",
        "multilingual_ko",
        "multilingual_pt",
        "multilingual_th",
        "multilingual_tr",
        "self_correction",
    ]
    failure_cases.write_text(
        json.dumps(
            {
                "failure_cases": [
                    {"row_id": f"r{idx}", "category": category, "subcategory": f"s{idx}"}
                    for idx, category in enumerate(categories, start=1)
                ]
            }
        ),
        encoding="utf-8",
    )
    reflection = tmp_path / "proposal-reflection.json"
    reflection.write_text(
        json.dumps(
            {
                "proposal_id": "round-006",
                "status": "needs_rollback_or_more_evidence",
                "proposal": {
                    "proposal_id": "round-006",
                    "change_surface": "prompt_profile",
                    "validation_plan": {
                        "first_split": "canary",
                        "promotion_split": "canary",
                    },
                },
                "failure_labels": ["SHIFT_delta_lt_0"],
                "evaluation": {
                    "rollback_reasons": ["SHIFT_delta_lt_0"],
                    "canary_delta": {"SHIFT": -0.4},
                    "failure_cases_path": str(failure_cases),
                },
            }
        ),
        encoding="utf-8",
    )

    payload = extract_failure_records(reflection)

    bad_categories = [item["category"] for item in payload["records"][0]["bad_cases"]]
    assert bad_categories == sorted(categories)


def test_record_proposal_outcome_writes_non_claiming_artifact(tmp_path: Path) -> None:
    payload = record_proposal_outcome(
        proposal=_proposal_card(),
        evaluation={
            "dev_delta": {"SHIFT": 0.8},
            "canary_delta": {"SHIFT": -0.3},
            "rollback_reasons": ["canary_not_confirmed"],
            "artifact_refs": [{"path": "results/dev.json"}],
        },
        output_path=tmp_path / "proposal-outcome.json",
    )

    assert payload["status"] == "completed"
    assert payload["accepted"] is False
    assert payload["regression"] is True
    assert payload["rollback_triggered"] is True
    assert payload["metric_delta"]["dev"] == 0.8
    assert payload["metric_delta"]["canary"] == -0.3
    assert payload["official_scores_claimed"] is False
    assert Path(payload["output_path"]).exists()


def test_record_proposal_outcome_normalizes_metric_rollback_labels_with_canary_split() -> None:
    proposal = {
        "proposal_id": "round-003-canary-fix",
        "change_surface": "prompt_profile",
        "validation_plan": {
            "first_split": "canary",
            "promotion_split": "canary",
        },
        "official_scores_claimed": False,
    }

    payload = record_proposal_outcome(
        proposal=proposal,
        evaluation={
            "canary_delta": {"SHIFT": -0.3},
            "rollback_reasons": ["SHIFT_delta_lt_0"],
        },
    )

    assert payload["failure_labels"] == ["canary_not_confirmed"]


def test_record_proposal_outcome_uses_dev_evaluation_split_before_canary_validation_plan() -> None:
    proposal = {
        "proposal_id": "round-003-dev-check",
        "change_surface": "prompt_profile",
        "validation_plan": {
            "first_split": "canary",
            "promotion_split": "canary",
        },
        "official_scores_claimed": False,
    }

    payload = record_proposal_outcome(
        proposal=proposal,
        evaluation={
            "dev_delta": {"SHIFT": -6.9},
            "current_dataset": {"evaluation_split": "dev"},
            "rollback_reasons": ["SHIFT_delta_lt_0"],
        },
    )

    assert payload["failure_labels"] == ["metric_regression"]
    assert payload["metric_delta"] == {"dev": -6.9}


def test_build_proposal_pattern_memory_aggregates_success_and_failure(tmp_path: Path) -> None:
    outcomes = [
        {
            "schema_version": "2026-06-02.proposal-outcome.v1",
            "outcome_id": "o1",
            "proposal_id": "p1",
            "proposal_type": "failure_fix",
            "based_on_failures": ["canary_not_confirmed"],
            "executed": True,
            "accepted": True,
            "metric_delta": {"dev": 0.6, "canary": 0.1},
            "rollback_triggered": False,
            "failure_labels": [],
            "claim_boundary": "local outcome only",
            "official_scores_claimed": False,
        },
        {
            "schema_version": "2026-06-02.proposal-outcome.v1",
            "outcome_id": "o2",
            "proposal_id": "p2",
            "proposal_type": "failure_fix",
            "based_on_failures": ["canary_not_confirmed"],
            "executed": True,
            "accepted": False,
            "metric_delta": {"dev": 0.2, "canary": -0.4},
            "rollback_triggered": True,
            "failure_labels": ["canary_not_confirmed"],
            "claim_boundary": "local outcome only",
            "official_scores_claimed": False,
        },
    ]

    payload = build_proposal_pattern_memory(
        outcomes,
        output_path=tmp_path / "proposal-pattern-memory.jsonl",
    )

    assert payload["status"] == "completed"
    assert payload["pattern_count"] == 1
    assert Path(payload["output_path"]).exists()
    pattern = payload["patterns"][0]
    assert pattern["proposal_type"] == "failure_fix"
    assert pattern["applicable_when"] == ["canary_not_confirmed"]
    assert pattern["task_family"] is None
    assert pattern["metric_names"] == ["canary", "dev"]
    assert pattern["historical_success_rate"] == 0.5
    assert pattern["historical_failure_rate"] == 0.5
    assert pattern["avg_delta"]["dev"] == 0.4
    assert pattern["official_scores_claimed"] is False


def test_build_proposal_pattern_memory_prefers_observed_failure_labels_for_failed_outcomes(
    tmp_path: Path,
) -> None:
    outcomes = [
        {
            "schema_version": "2026-06-02.proposal-outcome.v1",
            "outcome_id": "o1",
            "proposal_id": "p1",
            "proposal_type": "failure_fix",
            "based_on_failures": ["canary_not_confirmed"],
            "executed": True,
            "accepted": True,
            "metric_delta": {"canary": 0.2},
            "rollback_triggered": False,
            "failure_labels": [],
            "claim_boundary": "local outcome only",
            "official_scores_claimed": False,
        },
        {
            "schema_version": "2026-06-02.proposal-outcome.v1",
            "outcome_id": "o2",
            "proposal_id": "p1",
            "proposal_type": "failure_fix",
            "based_on_failures": ["canary_not_confirmed"],
            "executed": True,
            "accepted": False,
            "metric_delta": {"dev": -6.9},
            "rollback_triggered": True,
            "failure_labels": ["metric_regression"],
            "claim_boundary": "local outcome only",
            "official_scores_claimed": False,
        },
    ]

    payload = build_proposal_pattern_memory(
        outcomes,
        output_path=tmp_path / "proposal-pattern-memory.jsonl",
    )

    assert payload["pattern_count"] == 2
    patterns = {item["pattern_id"]: item for item in payload["patterns"]}
    assert patterns["failure_fix::canary_not_confirmed"]["historical_success_rate"] == 1.0
    assert patterns["failure_fix::metric_regression"]["historical_failure_rate"] == 1.0
    assert patterns["failure_fix::metric_regression"]["avg_delta"] == {"dev": -6.9}


def test_evaluate_failure_driven_proposal_effectiveness_compares_control_and_treatment(
    tmp_path: Path,
) -> None:
    control = [
        {
            "outcome_id": "c1",
            "accepted": False,
            "metric_delta": {"dev": 0.2, "canary": -0.2},
            "rollback_triggered": True,
            "failure_labels": ["canary_not_confirmed"],
            "official_scores_claimed": False,
        },
        {
            "outcome_id": "c2",
            "accepted": True,
            "metric_delta": {"dev": 0.3, "canary": 0.0},
            "rollback_triggered": False,
            "failure_labels": ["canary_not_confirmed"],
            "official_scores_claimed": False,
        },
    ]
    treatment = [
        {
            "outcome_id": "t1",
            "accepted": True,
            "metric_delta": {"dev": 0.4, "canary": 0.2},
            "rollback_triggered": False,
            "failure_labels": [],
            "official_scores_claimed": False,
        },
        {
            "outcome_id": "t2",
            "accepted": True,
            "metric_delta": {"dev": 0.1, "canary": 0.1},
            "rollback_triggered": False,
            "failure_labels": [],
            "official_scores_claimed": False,
        },
    ]

    payload = evaluate_failure_driven_proposal_effectiveness(
        control_outcomes=control,
        treatment_outcomes=treatment,
        output_path=tmp_path / "proposal-effectiveness.json",
    )

    assert payload["status"] == "completed"
    assert payload["control_summary"]["proposal_accept_rate"] == 0.5
    assert payload["treatment_summary"]["proposal_accept_rate"] == 1.0
    assert payload["comparison"]["proposal_accept_rate_lift"] == 0.5
    assert payload["comparison"]["rollback_rate_reduction"] == 0.5
    assert payload["comparison"]["failure_repeat_rate_reduction"] == 0.5
    assert payload["comparison"]["avg_metric_delta_lift"]["canary"] == 0.25
    assert payload["comparison"]["verdict"] == "treatment_improved_on_measured_metrics"
    assert Path(payload["output_path"]).exists()


def test_retrieve_proposal_patterns_filters_and_sorts_matches(tmp_path: Path) -> None:
    patterns = [
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
        },
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
        },
    ]

    payload = retrieve_proposal_patterns(
        pattern_memory=patterns,
        failure_type="canary_not_confirmed",
        task_family="smol_worldcup",
        metric_name="canary",
        output_path=tmp_path / "pattern-matches.json",
    )

    assert payload["status"] == "completed"
    assert payload["match_count"] == 1
    assert payload["matches"][0]["pattern"]["pattern_id"] == "failure_fix::canary_not_confirmed"
    assert "metric_name=canary" in payload["matches"][0]["match_reasons"]
    assert Path(payload["output_path"]).exists()


def test_build_cp_bench_proposal_effectiveness_bundle_writes_real_artifacts(
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

    payload = build_cp_bench_proposal_effectiveness_bundle(
        round_reports=[round_report],
        output_dir=tmp_path / "bundle",
    )

    assert payload["status"] == "completed"
    assert payload["control_outcome_count"] == 1
    assert payload["treatment_outcome_count"] == 1
    assert payload["comparison"]["proposal_accept_rate_lift"] == 1.0
    assert payload["comparison"]["time_to_best_reduction"] is None
    assert payload["comparison"]["verdict"] == "treatment_improved_on_measured_metrics"
    assert Path(payload["effectiveness_report_path"]).exists()
    assert Path(payload["control_outcomes_path"]).exists()
    assert Path(payload["treatment_outcomes_path"]).exists()


def test_build_fasttext_proposal_effectiveness_bundle_writes_real_artifacts(
    tmp_path: Path,
) -> None:
    multi_round_report = tmp_path / "multi-round-report.json"
    multi_round_report.write_text(
        json.dumps(
            {
                "status": "completed_with_failures",
                "stage": "p5_fasttext_multi_proposal_loop",
                "summary": {
                    "proposal_count": 2,
                    "completed_count": 1,
                    "failure_count": 1,
                    "improved_count": 1,
                    "best_metric": 0.916,
                },
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

    payload = build_fasttext_proposal_effectiveness_bundle(
        multi_round_reports=[multi_round_report],
        output_dir=tmp_path / "bundle",
    )

    assert payload["status"] == "completed"
    assert payload["control_outcome_count"] == 2
    assert payload["treatment_outcome_count"] == 2
    assert payload["comparison"]["proposal_accept_rate_lift"] == 0.5
    assert payload["comparison"]["rollback_rate_reduction"] == -0.5
    assert payload["comparison"]["verdict"] == "mixed_signal"
    assert Path(payload["effectiveness_report_path"]).exists()


def test_build_fasttext_proposal_effectiveness_bundle_completed_only_filters_failures(
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

    payload = build_fasttext_proposal_effectiveness_bundle(
        multi_round_reports=[multi_round_report],
        output_dir=tmp_path / "bundle",
        include_failed_rounds=False,
    )

    assert payload["include_failed_rounds"] is False
    assert payload["control_outcome_count"] == 1
    assert payload["treatment_outcome_count"] == 1
    assert payload["comparison"]["proposal_accept_rate_lift"] == 1.0
    assert payload["comparison"]["rollback_rate_reduction"] == 0.0
    assert payload["comparison"]["verdict"] == "treatment_improved_on_measured_metrics"


def test_build_smol_worldcup_proposal_effectiveness_bundle_writes_real_artifacts(
    tmp_path: Path,
) -> None:
    dev_control = tmp_path / "smol-worldcup-dev-control.json"
    dev_treatment = tmp_path / "smol-worldcup-dev-treatment.json"
    canary_control = tmp_path / "smol-worldcup-canary-control.json"
    canary_treatment = tmp_path / "smol-worldcup-canary-treatment.json"
    dev_control.write_text(
        json.dumps(
            {
                "round_id": "qwen3-8b-dev-round-002-dev-v2-20260521",
                "dataset": {"evaluation_split": "dev", "row_count": 100},
                "model": {"prompt_profile": "p3-dev-v2"},
                "proposal": {
                    "proposal_id": "qwen3-8b-dev-round-002-dev-v2-20260521-failure-driven-routing",
                    "top_failure_categories": [
                        {"category": "confidence_calibration", "count": 7},
                        {"category": "knowledge_synthesis", "count": 6},
                    ],
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
    dev_treatment.write_text(
        json.dumps(
            {
                "round_id": "qwen3-8b-dev-round-004-semantic-v2-20260521",
                "dataset": {"evaluation_split": "dev", "row_count": 100},
                "model": {"prompt_profile": "p3-semantic-v2"},
                "proposal": {
                    "proposal_id": "qwen3-8b-dev-round-004-semantic-v2-20260521-failure-driven-routing",
                    "top_failure_categories": [
                        {"category": "multilingual_ko", "count": 5},
                        {"category": "knowledge_synthesis", "count": 4},
                    ],
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
    canary_control.write_text(
        json.dumps(
            {
                "round_id": "qwen3-8b-canary-round-002-dev-v2-20260521",
                "dataset": {"evaluation_split": "canary", "row_count": 25},
                "model": {"prompt_profile": "p3-dev-v2"},
                "proposal": {
                    "proposal_id": "qwen3-8b-canary-round-002-dev-v2-20260521-failure-driven-routing",
                    "top_failure_categories": [
                        {"category": "reasoning", "count": 3},
                    ],
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
    canary_treatment.write_text(
        json.dumps(
            {
                "round_id": "qwen3-8b-canary-round-004-semantic-v2-20260521",
                "dataset": {"evaluation_split": "canary", "row_count": 25},
                "model": {"prompt_profile": "p3-semantic-v2"},
                "proposal": {
                    "proposal_id": "qwen3-8b-canary-round-004-semantic-v2-20260521-failure-driven-routing",
                    "top_failure_categories": [
                        {"category": "reasoning", "count": 2},
                    ],
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

    payload = build_smol_worldcup_proposal_effectiveness_bundle(
        control_reports=[dev_control, canary_control],
        treatment_reports=[dev_treatment, canary_treatment],
        output_dir=tmp_path / "bundle",
    )

    assert payload["status"] == "completed"
    assert payload["control_outcome_count"] == 2
    assert payload["treatment_outcome_count"] == 2
    assert payload["comparison"]["proposal_accept_rate_lift"] == 0.5
    assert payload["comparison"]["rollback_rate_reduction"] == -0.5
    assert payload["comparison"]["avg_metric_delta_lift"]["SHIFT"] == 0.3035
    assert payload["comparison"]["verdict"] == "mixed_signal"
    assert Path(payload["effectiveness_report_path"]).exists()


def test_build_smol_worldcup_proposal_effectiveness_bundle_split_filter_dev_is_positive(
    tmp_path: Path,
) -> None:
    dev_control = tmp_path / "smol-worldcup-dev-control.json"
    dev_treatment = tmp_path / "smol-worldcup-dev-treatment.json"
    canary_control = tmp_path / "smol-worldcup-canary-control.json"
    canary_treatment = tmp_path / "smol-worldcup-canary-treatment.json"
    dev_control.write_text(
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
    dev_treatment.write_text(
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
    canary_control.write_text(
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
    canary_treatment.write_text(
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

    payload = build_smol_worldcup_proposal_effectiveness_bundle(
        control_reports=[dev_control, canary_control],
        treatment_reports=[dev_treatment, canary_treatment],
        output_dir=tmp_path / "bundle",
        split_filter="dev",
    )

    assert payload["split_filter"] == "dev"
    assert payload["comparison_pair_count"] == 1
    assert payload["comparison"]["proposal_accept_rate_lift"] == 1.0
    assert payload["comparison"]["rollback_rate_reduction"] == 0.0
    assert payload["comparison"]["verdict"] == "treatment_improved_on_measured_metrics"


def test_build_smol_worldcup_proposal_effectiveness_bundle_zero_delta_does_not_fake_rollback(
    tmp_path: Path,
) -> None:
    control = tmp_path / "smol-worldcup-control.json"
    treatment = tmp_path / "smol-worldcup-treatment.json"
    control.write_text(
        json.dumps(
            {
                "round_id": "qwen3-8b-dev-round-003-v3",
                "dataset": {"evaluation_split": "all", "row_count": 5},
                "model": {"prompt_profile": "p3-canary-repair-v3"},
                "proposal": {"proposal_id": "neighbor-control"},
                "metrics": {
                    "H": 0.0,
                    "I": 56.0,
                    "SHIFT": 33.6,
                    "WCS_local_diagnostic": 0.0,
                },
                "failure_summary": {"failure_count": 2},
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )
    treatment.write_text(
        json.dumps(
            {
                "round_id": "qwen3-8b-dev-round-004-v5",
                "dataset": {"evaluation_split": "all", "row_count": 5},
                "model": {"prompt_profile": "p3-canary-repair-v5"},
                "proposal": {"proposal_id": "neighbor-treatment"},
                "metrics": {
                    "H": 0.0,
                    "I": 56.0,
                    "SHIFT": 33.6,
                    "WCS_local_diagnostic": 0.0,
                },
                "failure_summary": {"failure_count": 2},
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    payload = build_smol_worldcup_proposal_effectiveness_bundle(
        control_reports=[control],
        treatment_reports=[treatment],
        output_dir=tmp_path / "bundle",
    )

    treatment_outcome = json.loads(
        (tmp_path / "bundle" / "treatment-outcomes.jsonl").read_text(encoding="utf-8").strip()
    )

    assert treatment_outcome["rollback_triggered"] is False
    assert treatment_outcome["rollback_reasons"] == []
    assert treatment_outcome["regression"] is False
    assert payload["comparison"]["rollback_rate_reduction"] == 0.0
    assert payload["comparison"]["avg_metric_delta_lift"]["SHIFT"] == 0.0
    assert payload["comparison"]["verdict"] == "mixed_signal"


def test_build_smol_worldcup_promotion_gate_blocks_on_canary_regression(
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

    payload = build_smol_worldcup_promotion_gate(
        dev_effectiveness_report=dev_report,
        canary_effectiveness_report=canary_report,
        output_dir=tmp_path / "promotion-gate",
    )

    assert payload["status"] == "blocked_on_canary_confirmation"
    assert payload["promotion_ready"] is False
    assert payload["dev_gate"]["passed"] is True
    assert payload["canary_gate"]["passed"] is False
    assert payload["recommended_next_action"] == (
        "tighten_canary_gate_before_prompt_profile_promotion"
    )
    assert Path(payload["gate_path"]).exists()


def test_build_smol_worldcup_promotion_gate_routes_dev_block_to_result_analysis(
    tmp_path: Path,
) -> None:
    dev_report = tmp_path / "dev-effectiveness.json"
    canary_report = tmp_path / "canary-effectiveness.json"
    dev_report.write_text(
        json.dumps({
            "comparison": {
                "proposal_accept_rate_lift": 1.0,
                "rollback_rate_reduction": -1.0,
                "avg_metric_delta_lift": {"H": -0.2941, "SHIFT": 3.7395},
                "verdict": "mixed_signal",
            },
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    canary_report.write_text(
        json.dumps({
            "comparison": {
                "proposal_accept_rate_lift": 1.0,
                "rollback_rate_reduction": 0.0,
                "avg_metric_delta_lift": {"H": 8.3333, "SHIFT": 16.3333},
                "verdict": "treatment_improved_on_measured_metrics",
            },
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    payload = build_smol_worldcup_promotion_gate(
        dev_effectiveness_report=dev_report,
        canary_effectiveness_report=canary_report,
        output_dir=tmp_path / "promotion-gate",
    )

    assert payload["status"] == "blocked_on_dev_signal"
    assert payload["promotion_ready"] is False
    assert payload["recommended_next_action"] == (
        "build_smol_worldcup_result_analysis_before_prompt_changes"
    )


def test_build_smol_worldcup_result_analysis_explains_metric_regression_before_changes(
    tmp_path: Path,
) -> None:
    control = tmp_path / "control.json"
    treatment = tmp_path / "treatment.json"
    control.write_text(
        json.dumps({
            "round_id": "control-dev",
            "dataset": {"evaluation_split": "dev", "row_count": 2},
            "model": {"prompt_profile": "p3-dev-v2"},
            "metrics": {"H": 90.0, "I": 70.0, "SHIFT": 78.0, "WCS_local_diagnostic": 88.0},
            "score_breakdown": {"by_axis": {"H": {"score_percent": 90.0}}},
            "predictions": [
                {
                    "row_id": "S1-H2-012",
                    "shift_axis": "H",
                    "category": "confidence_calibration",
                    "subcategory": "hard_math",
                    "auto_grade": "calibration_check",
                    "max_score": 10,
                    "score": 10,
                    "prompt": "What is the integral of e^(x²) from 0 to 1?",
                    "response": "{\"answer\":\"1.46265\",\"confidence\":50}",
                    "grading_method": "calibration_check",
                    "grading_reason": "expected_confidence=medium, confidence=50.0",
                },
                {
                    "row_id": "S1-H4-036",
                    "shift_axis": "H",
                    "category": "self_correction",
                    "subcategory": "reasoning_trap",
                    "auto_grade": "self_correction_check",
                    "max_score": 10,
                    "score": 2,
                    "prompt": "Which is heavier: a kilogram of steel or a kilogram of feathers?",
                    "response": "{\"final_answer\":\"steel\"}",
                    "grading_method": "self_correction_check",
                },
            ],
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )
    treatment.write_text(
        json.dumps({
            "round_id": "treatment-dev",
            "dataset": {"evaluation_split": "dev", "row_count": 2},
            "model": {"prompt_profile": "p3-v7-metacognition-textgrad-v2"},
            "metrics": {"H": 89.0, "I": 80.0, "SHIFT": 83.6, "WCS_local_diagnostic": 91.4},
            "score_breakdown": {"by_axis": {"H": {"score_percent": 89.0}}},
            "predictions": [
                {
                    "row_id": "S1-H2-012",
                    "shift_axis": "H",
                    "category": "confidence_calibration",
                    "subcategory": "hard_math",
                    "auto_grade": "calibration_check",
                    "max_score": 10,
                    "score": 8.5,
                    "prompt": "What is the integral of e^(x²) from 0 to 1?",
                    "response": "{\"answer\":\"1.46265\",\"confidence\":35}",
                    "grading_method": "calibration_check",
                    "grading_reason": "expected_confidence=medium, confidence=35.0",
                },
                {
                    "row_id": "S1-H4-036",
                    "shift_axis": "H",
                    "category": "self_correction",
                    "subcategory": "reasoning_trap",
                    "auto_grade": "self_correction_check",
                    "max_score": 10,
                    "score": 10,
                    "prompt": "Which is heavier: a kilogram of steel or a kilogram of feathers?",
                    "response": "{\"final_answer\":\"same\"}",
                    "grading_method": "self_correction_check",
                },
            ],
            "official_scores_claimed": False,
        }),
        encoding="utf-8",
    )

    payload = build_smol_worldcup_result_analysis(
        control_reports=[control],
        treatment_reports=[treatment],
        output_dir=tmp_path / "analysis",
    )

    assert payload["status"] == "analysis_required_before_next_change"
    assert payload["metric_regressions"][0]["metric"] == "H"
    assert payload["next_action"] == "run_paired_repeat_before_changing_prompt"
    assert payload["summary"]["regression_row_count"] == 1
    assert payload["summary"]["improvement_row_count"] == 1
    regression = payload["row_deltas"][0]
    assert regression["row_id"] == "S1-H2-012"
    assert regression["prompt_profile_messages_changed"] is False
    assert regression["root_cause_hypothesis"] == "stochastic_or_format_variation"
    assert "repeat_row" in regression["recommended_next_action"]
    assert Path(payload["analysis_path"]).exists()


def test_build_smol_worldcup_confidence_variance_gate_blocks_attribution_when_aa_varies(
    tmp_path: Path,
) -> None:
    aa_analysis = {
        "schema_version": "2026-06-27.smol-worldcup-result-analysis.v1",
        "status": "analysis_required_before_next_change",
        "metric_regressions": [
            {"metric": "H", "delta": -30.0, "split": "dev"},
        ],
        "row_deltas": [
            {
                "row_id": "S1-H2-012",
                "category": "confidence_calibration",
                "score_delta": -7.5,
                "prompt_profile_messages_changed": False,
                "root_cause_hypothesis": "stochastic_or_format_variation",
            },
            {
                "row_id": "S1-H2-020",
                "category": "confidence_calibration",
                "score_delta": 1.5,
                "prompt_profile_messages_changed": False,
                "root_cause_hypothesis": "candidate_improved_row",
            },
        ],
        "official_scores_claimed": False,
    }
    candidate_analysis = {
        "schema_version": "2026-06-27.smol-worldcup-result-analysis.v1",
        "status": "analysis_required_before_next_change",
        "metric_regressions": [
            {"metric": "H", "delta": -42.5, "split": "dev"},
        ],
        "row_deltas": [
            {
                "row_id": "S1-H2-012",
                "category": "confidence_calibration",
                "score_delta": -10.0,
                "prompt_profile_messages_changed": False,
                "root_cause_hypothesis": "stochastic_or_format_variation",
            }
        ],
        "official_scores_claimed": False,
    }

    payload = build_smol_worldcup_confidence_variance_gate(
        aa_result_analysis=aa_analysis,
        candidate_result_analyses=[candidate_analysis],
        output_path=tmp_path / "confidence-variance-gate.json",
    )

    assert payload["schema_version"] == (
        "2026-06-27.smol-worldcup-confidence-variance-gate.v1"
    )
    assert payload["status"] == "blocked_by_aa_confidence_variance"
    assert payload["gate"]["optimizer_regression_attribution_allowed"] is False
    assert payload["gate"]["prompt_repair_allowed"] is False
    assert "aa_confidence_variance_detected" in payload["hard_blockers"]
    assert payload["aa_confidence_variance"]["max_abs_score_delta"] == 7.5
    assert payload["candidate_assessments"][0]["confidence_rows"][0]["row_id"] == (
        "S1-H2-012"
    )
    assert payload["candidate_assessments"][0]["confidence_rows"][0]["classification"] == (
        "exceeds_aa_variance_but_prompt_unchanged"
    )
    assert payload["recommended_next_action"] == (
        "build_cached_confidence_scoring_gate_before_prompt_repair"
    )
    assert payload["official_scores_claimed"] is False
    assert Path(payload["output_path"]).exists()


def test_build_smol_worldcup_cached_confidence_scoring_gate_blocks_uncached_variance(
    tmp_path: Path,
) -> None:
    report_a = {
        "schema_version": "2026-06-27.smol-worldcup-model-eval.v1",
        "round_id": "aa-confidence-rerun-1",
        "dataset": {"evaluation_split": "dev", "row_id_filter": ["S1-H2-012"]},
        "model": {
            "id": "deepseek-v4-pro",
            "provider": "deepseek",
            "prompt_profile": "p3-dev-v2",
            "temperature": 0.0,
        },
        "predictions": [
            {
                "row_id": "S1-H2-012",
                "category": "confidence_calibration",
                "auto_grade": "calibration_check",
                "prompt": "confidence prompt",
                "response": "{\"answer\":\"1.46265\",\"confidence\":50}",
                "score": 10.0,
                "max_score": 10.0,
                "grading_method": "calibration_check",
                "grading_reason": "expected_confidence=medium, confidence=50.0",
            }
        ],
        "official_scores_claimed": False,
    }
    report_b = {
        "schema_version": "2026-06-27.smol-worldcup-model-eval.v1",
        "round_id": "aa-confidence-rerun-2",
        "dataset": {"evaluation_split": "dev", "row_id_filter": ["S1-H2-012"]},
        "model": {
            "id": "deepseek-v4-pro",
            "provider": "deepseek",
            "prompt_profile": "p3-dev-v2",
            "temperature": 0.0,
        },
        "predictions": [
            {
                "row_id": "S1-H2-012",
                "category": "confidence_calibration",
                "auto_grade": "calibration_check",
                "prompt": "confidence prompt",
                "response": "{\"answer\":\"1.46265\",\"confidence\":95}",
                "score": 2.5,
                "max_score": 10.0,
                "grading_method": "calibration_check",
                "grading_reason": "expected_confidence=medium, confidence=95.0",
            }
        ],
        "official_scores_claimed": False,
    }

    payload = build_smol_worldcup_cached_confidence_scoring_gate(
        model_eval_reports=[report_a, report_b],
        output_path=tmp_path / "cached-confidence-scoring-gate.json",
    )

    assert payload["schema_version"] == (
        "2026-06-27.smol-worldcup-cached-confidence-scoring-gate.v1"
    )
    assert payload["status"] == "blocked_cached_confidence_scoring_not_ready"
    assert payload["gate"]["prompt_repair_allowed"] is False
    assert payload["gate"]["optimizer_regression_attribution_allowed"] is False
    assert "missing_response_cache_key" in payload["hard_blockers"]
    assert "missing_confidence_scorer_version" in payload["hard_blockers"]
    assert "confidence_score_variance_detected" in payload["hard_blockers"]
    row = payload["row_diagnostics"][0]
    assert row["row_id"] == "S1-H2-012"
    assert row["repeat_count"] == 2
    assert row["unique_response_hash_count"] == 2
    assert row["score_range"] == 7.5
    assert row["cached_output_ready"] is False
    assert row["scoring_deterministic"] is False
    assert payload["recommended_next_action"] == (
        "add_response_cache_and_scorer_version_then_repeat_confidence_rows"
    )
    assert payload["official_scores_claimed"] is False
    assert Path(payload["output_path"]).exists()


def test_build_smol_worldcup_canary_failure_slice_audit_requires_control_arm(
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
                        "WCS_local_diagnostic": -0.1891,
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
                        "negative_metric_delta_present",
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

    payload = build_smol_worldcup_canary_failure_slice_audit(
        canary_effectiveness_report=canary_report,
        promotion_gate=promotion_gate,
        control_outcomes=control_outcomes,
        treatment_outcomes=treatment_outcomes,
        output_dir=tmp_path / "canary-failure-slice-audit",
    )

    assert payload["status"] == "failure_slice_control_arm_required"
    assert payload["failure_slice_label"] == "canary_not_confirmed"
    assert payload["recommended_next_action"] == "add_failure_slice_specific_control_arm"
    assert payload["negative_metric_names"] == ["I", "SHIFT", "WCS_local_diagnostic"]
    assert payload["control_arm_spec"]["promotion_rule"] == (
        "do_not_promote_until_failure_slice_control_arm_passes"
    )
    assert Path(payload["audit_path"]).exists()


def test_build_smol_worldcup_canary_control_arm_handoff_matches_contract(
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

    payload = build_smol_worldcup_canary_control_arm_handoff(
        failure_slice_audit=failure_slice_audit,
        output_dir=tmp_path / "control-arm-handoff",
    )

    assert payload["status"] == "ready_for_client_review"
    assert payload["failure_slice_label"] == "canary_not_confirmed"
    template = payload["proposal_template"]
    validation = validate_client_proposal(template)
    assert validation["status"] == "accepted"
    assert template["based_on_failures"] == ["canary_not_confirmed"]
    assert template["change_surface"] == "prompt_profile"
    assert template["validation_plan"]["first_split"] == "canary"
    assert template["validation_plan"]["promotion_split"] == "canary"
    assert Path(payload["handoff_path"]).exists()


def test_build_smol_worldcup_canary_control_arm_execution_bundle_writes_request(
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
                        {
                            "artifact": "smol-worldcup-canary-failure-slice-audit",
                            "observation": "canary gate still blocked",
                        }
                    ],
                    "change_surface": "prompt_profile",
                    "change_spec": {
                        "single_primary_variable": True,
                        "control_arm_kind": "matched_canary_negative_control",
                    },
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

    payload = build_smol_worldcup_canary_control_arm_execution_bundle(
        handoff=handoff,
        output_dir=tmp_path / "execution-bundle",
        current_report=current_report,
    )

    assert payload["status"] == "ready_for_guarded_execution"
    assert payload["target_prompt_profile"] == "p3-dev-v2"
    assert payload["recommended_next_step"]["mcp_tool"] == "run_smol_worldcup_proposal_round"
    assert "--prompt-profile" in payload["recommended_command"]
    proposal = json.loads(Path(payload["proposal_path"]).read_text(encoding="utf-8"))
    assert proposal["change_spec"]["target_file_or_profile"] == "p3-dev-v2"
    request_payload = json.loads(
        Path(payload["execution_request_path"]).read_text(encoding="utf-8")
    )
    assert request_payload["evaluation_split"] == "canary"
    assert request_payload["model"] == "qwen/qwen3-8b"
    assert request_payload["judge_mode"] == "openai-compatible"
    assert request_payload["judge_model"] == "openai/gpt-oss-20b"
    assert request_payload["proposal_file"] == str(Path(payload["proposal_path"]))


def test_build_smol_worldcup_canary_control_arm_execution_bundle_resolves_current_report(
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

    payload = build_smol_worldcup_canary_control_arm_execution_bundle(
        handoff=handoff,
        output_dir=tmp_path / "execution-bundle",
        evidence_root=evidence_root,
    )

    assert payload["current_report_resolution"]["status"] == "resolved_from_evidence"
    assert payload["current_report_resolution"]["path"] == str(source_report.resolve())
    assert payload["runtime_config"]["model"] == "qwen/qwen3-8b"
    request_payload = json.loads(
        Path(payload["execution_request_path"]).read_text(encoding="utf-8")
    )
    assert request_payload["current_report"] == str(source_report.resolve())
    assert request_payload["model"] == "qwen/qwen3-8b"


def test_build_smol_worldcup_promotion_gate_refresh_promotes_after_positive_canary_round(
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

    payload = build_smol_worldcup_promotion_gate_refresh(
        previous_gate=previous_gate,
        proposal_round_summary=proposal_round_summary,
        output_dir=tmp_path / "promotion-gate-refresh",
    )

    assert payload["status"] == "ready_for_prompt_profile_promotion"
    assert payload["promotion_ready"] is True
    assert payload["canary_gate_refresh"]["passed"] is True
    assert payload["recommended_next_action"] == "review_and_promote_prompt_profile"
    assert Path(payload["refresh_path"]).exists()


def test_build_real_paper_proposal_effectiveness_bundle_writes_real_artifacts(
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

    payload = build_real_paper_proposal_effectiveness_bundle(
        proof_archives=[memflow_archive, adam_archive],
        output_dir=tmp_path / "bundle",
    )

    assert payload["status"] == "completed"
    assert payload["control_outcome_count"] == 2
    assert payload["treatment_outcome_count"] == 2
    assert payload["comparison"]["proposal_accept_rate_lift"] == 1.0
    assert payload["comparison"]["avg_metric_delta_lift"]["selection_accuracy"] == 0.375
    assert payload["comparison"]["avg_metric_delta_lift"]["optimizer_progress_score"] == 0.2293
    assert payload["comparison"]["verdict"] == "treatment_improved_on_measured_metrics"
    assert Path(payload["effectiveness_report_path"]).exists()


def test_build_cross_task_proposal_effectiveness_summary_writes_report(
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

    payload = build_cross_task_proposal_effectiveness_summary(
        effectiveness_reports=[
            cp_bench_report,
            fasttext_report,
            smol_worldcup_report,
            real_paper_report,
        ],
        output_dir=tmp_path / "cross-task-summary",
    )

    assert payload["status"] == "completed"
    assert payload["task_count"] == 4
    assert payload["aggregate"]["verdict_counts"]["mixed_signal"] == 2
    assert payload["aggregate"]["verdict_counts"]["treatment_improved_on_measured_metrics"] == 2
    assert "final_solution_accuracy_percent" in payload["aggregate"]["consistent_improvements"]
    assert any(
        item["task_family"] == "smol_worldcup_prompt_routing"
        for item in payload["task_summaries"]
    )
    assert any(
        item["task_family"] == "real_paper_public_slice_patch"
        for item in payload["task_summaries"]
    )
    assert Path(payload["summary_path"]).exists()


def test_build_proposal_effectiveness_claim_audit_blocks_cross_task_claim_when_signals_are_mixed(
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
                    "consistent_improvements": [
                        "I",
                        "SHIFT",
                        "final_solution_accuracy_percent",
                    ],
                    "tradeoff_metrics": [],
                },
                "official_scores_claimed": False,
            }
        ),
        encoding="utf-8",
    )

    payload = build_proposal_effectiveness_claim_audit(
        cross_task_summary=cross_task_summary,
        output_dir=tmp_path / "claim-audit",
    )

    assert payload["status"] == "completed"
    assert payload["claim_readiness"] == "insufficient_evidence_for_cross_task_effectiveness_claim"
    assert payload["evidence_snapshot"]["task_count"] == 3
    assert payload["gates"]["minimum_task_count"]["passed"] is True
    assert payload["gates"]["multiple_positive_task_families"]["passed"] is False
    assert payload["gates"]["no_mixed_signal_tasks"]["passed"] is False
    assert "local_multi_task_signal_present" in payload["allowed_claims"]
    assert "proposal_effectiveness_proven_cross_task" in payload["blocked_claims"]
    assert "run_mixed_signal_task_family_audit" in payload["recommended_next_actions"]
    assert Path(payload["audit_path"]).exists()


def test_build_mixed_signal_proposal_effectiveness_audit_writes_report(
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

    payload = build_mixed_signal_proposal_effectiveness_audit(
        effectiveness_reports=[fasttext_report, smol_worldcup_report],
        output_dir=tmp_path / "mixed-signal-audit",
    )

    assert payload["status"] == "completed"
    assert payload["mixed_signal_task_count"] == 2
    assert payload["aggregate"]["blocking_signal_counts"]["rollback_rate_worsened"] == 2
    assert "split_exploration_and_confirmation_arms" in payload["aggregate"]["recommended_actions"]
    assert any(
        item["task_family"] == "fasttext_text_classification"
        and "separate_allowlist_rejections_from_effectiveness_arms"
        in item["recommended_actions"]
        for item in payload["task_audits"]
    )
    assert any(
        item["task_family"] == "smol_worldcup_prompt_routing"
        and "tighten_canary_gate_before_prompt_profile_promotion"
        in item["recommended_actions"]
        for item in payload["task_audits"]
    )
    assert Path(payload["audit_path"]).exists()


def test_build_failure_driven_proposal_context_summarizes_failures_and_patterns(
    tmp_path: Path,
) -> None:
    failure_records = [
        {
            "schema_version": "2026-06-02.failure-record.v1",
            "failure_id": "f1",
            "task_id": "round-001",
            "failure_type": "canary_not_confirmed",
            "symptom": "canary regressed",
            "severity": "medium",
            "claim_boundary": "local only",
            "official_scores_claimed": False,
        },
        {
            "schema_version": "2026-06-02.failure-record.v1",
            "failure_id": "f2",
            "task_id": "round-002",
            "failure_type": "canary_not_confirmed",
            "symptom": "canary regressed again",
            "severity": "medium",
            "claim_boundary": "local only",
            "official_scores_claimed": False,
        },
    ]
    patterns = [
        {
            "schema_version": "2026-06-02.proposal-pattern-memory.v1",
            "pattern_id": "failure_fix::canary_not_confirmed",
            "pattern_summary": "failure_fix against canary_not_confirmed",
            "proposal_type": "failure_fix",
            "applicable_when": ["canary_not_confirmed"],
            "historical_success_rate": 0.75,
            "historical_failure_rate": 0.25,
            "claim_boundary": "local only",
            "official_scores_claimed": False,
        }
    ]

    payload = build_failure_driven_proposal_context(
        objective="Preserve local gain on canary.",
        failure_records=failure_records,
        pattern_memory=patterns,
        max_proposals=4,
        output_path=tmp_path / "failure-driven-context.json",
    )

    assert payload["status"] == "ready_for_failure_driven_proposals"
    assert payload["failure_summary"]["record_count"] == 2
    assert payload["failure_summary"]["top_failure_types"][0]["failure_type"] == (
        "canary_not_confirmed"
    )
    assert payload["pattern_summary"]["matched_patterns"][0]["pattern_id"] == (
        "failure_fix::canary_not_confirmed"
    )
    assert payload["max_proposals"] == 4
    assert "canary_not_confirmed" in payload["prompt_markdown"]
    assert Path(payload["output_path"]).exists()


def test_generate_failure_driven_proposals_builds_rankable_drafts(
    tmp_path: Path,
) -> None:
    context = {
        "status": "ready_for_failure_driven_proposals",
        "schema_version": "2026-06-02.failure-driven-context.v1",
        "objective": "Preserve local gain on canary.",
        "max_proposals": 2,
        "failure_summary": {
            "record_count": 2,
            "records": [
                {
                    "failure_id": "f1",
                    "failure_type": "canary_not_confirmed",
                    "severity": "medium",
                    "scope": "single routing block",
                    "official_scores_claimed": False,
                },
                {
                    "failure_id": "f2",
                    "failure_type": "no_improvement",
                    "severity": "low",
                    "scope": "prompt profile",
                    "official_scores_claimed": False,
                },
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

    payload = generate_failure_driven_proposals(
        context=context,
        output_path=tmp_path / "generated-proposals.json",
    )

    assert payload["status"] == "completed"
    assert payload["proposal_count"] == 2
    assert payload["proposals"][0]["proposal_type"] == "failure_fix"
    assert payload["proposals"][0]["change_surface"] == "routing"
    assert payload["proposals"][0]["expected_gain"]["score"] == 0.8
    assert payload["proposals"][1]["proposal_type"] == "strategy_shift"
    assert payload["recommended_next_step"]["mcp_tool"] == "rank_failure_driven_proposals"
    assert Path(payload["output_path"]).exists()


def test_generate_failure_driven_proposals_canary_broader_shape_prefers_prompt_profile(
    tmp_path: Path,
) -> None:
    context = {
        "status": "ready_for_failure_driven_proposals",
        "schema_version": "2026-06-02.failure-driven-context.v1",
        "objective": "repair broader canary regression",
        "max_proposals": 1,
        "failure_summary": {
            "record_count": 1,
            "records": [
                {
                    "failure_id": "f1",
                    "failure_type": "canary_not_confirmed",
                    "severity": "medium",
                    "scope": "prompt_profile",
                    "bad_cases": [
                        {"category": "reasoning", "count": 3},
                        {"category": "math", "count": 2},
                        {"category": "metacognition", "count": 2},
                        {"category": "hallucination_trap", "count": 1},
                        {"category": "knowledge_synthesis", "count": 1},
                        {"category": "multilingual_ko", "count": 1},
                        {"category": "multilingual_pt", "count": 1},
                        {"category": "multilingual_bn", "count": 1},
                        {"category": "multilingual_th", "count": 1},
                        {"category": "multilingual_tr", "count": 1},
                        {"category": "self_correction", "count": 1},
                    ],
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
                    "historical_success_rate": 0.0,
                    "official_scores_claimed": False,
                }
            ],
        },
        "prompt_markdown": "failure-driven prompt",
        "official_scores_claimed": False,
    }

    payload = generate_failure_driven_proposals(
        context=context,
        output_path=tmp_path / "generated-proposals.json",
    )

    proposal = payload["proposals"][0]
    assert proposal["change_surface"] == "prompt_profile"
    assert proposal["verification_plan"]["first_split"] == "canary"
    assert "reasoning, math, metacognition, hallucination_trap" in proposal["intent"]
    assert "knowledge_synthesis" in proposal["intent"]
    assert "self_correction" in proposal["intent"]
    assert "multilingual_ko" in proposal["intent"]
    assert "multilingual_pt" in proposal["intent"]
    assert "multilingual_th" in proposal["target_scope"]
    assert "multilingual_tr" in proposal["target_scope"]
    assert "multilingual_bn" in proposal["target_scope"]
    assert proposal["target_scope"].startswith("canary broader failure categories")


def test_rank_failure_driven_proposals_uses_pattern_prior_and_redundancy(
    tmp_path: Path,
) -> None:
    failure_records = [
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
    ]
    patterns = [
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
    ]
    proposals = [
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
        },
        {
            "proposal_id": "p2",
            "proposal_type": "failure_fix",
            "based_on_failures": ["f1"],
            "intent": "Same thing again.",
            "change_surface": "routing",
            "target_scope": "single routing block",
            "expected_gain": {"score": 0.9},
            "risk_level": "low",
            "verification_plan": {"first_split": "dev"},
            "rollback_rule": {"if": ["canary_delta_lt_0"]},
            "claim_boundary": "local only",
            "official_scores_claimed": False,
        },
        {
            "proposal_id": "p3",
            "proposal_type": "failure_fix",
            "based_on_failures": ["f1"],
            "intent": "Broader fix with more risk.",
            "change_surface": "training_recipe",
            "target_scope": "training config",
            "expected_gain": {"score": 0.7},
            "risk_level": "high",
            "verification_plan": {"first_split": "dev"},
            "rollback_rule": {"if": ["canary_delta_lt_0"]},
            "claim_boundary": "local only",
            "official_scores_claimed": False,
        },
    ]

    payload = rank_failure_driven_proposals(
        proposals=proposals,
        failure_records=failure_records,
        pattern_memory=patterns,
        output_path=tmp_path / "ranked-proposals.json",
    )

    assert payload["status"] == "completed"
    assert payload["ranked_proposals"][0]["proposal_id"] == "p1"
    assert payload["ranked_proposals"][0]["change_surface"] == "routing"
    assert payload["ranked_proposals"][0]["verification_plan"]["first_split"] == "dev"
    assert payload["ranked_proposals"][0]["rollback_rule"]["if"] == ["canary_delta_lt_0"]
    assert payload["ranked_proposals"][0]["score_breakdown"]["pattern_prior"] == 0.8
    assert payload["ranked_proposals"][1]["score_breakdown"]["redundancy_penalty"] > 0
    assert payload["ranked_proposals"][2]["score_breakdown"]["risk_penalty"] > (
        payload["ranked_proposals"][0]["score_breakdown"]["risk_penalty"]
    )
    assert Path(payload["output_path"]).exists()


def test_build_failure_driven_proposal_handoff_selects_next_proposals_and_bridge(
    tmp_path: Path,
) -> None:
    context = {
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
        "pattern_summary": {
            "matched_patterns": [
                {
                    "pattern_id": "failure_fix::canary_not_confirmed",
                    "historical_success_rate": 0.8,
                }
            ]
        },
        "claim_boundary": "local only",
        "official_scores_claimed": False,
    }
    ranking = {
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
                "score": 1.5,
                "rank": 1,
                "gate_labels": [],
                "score_breakdown": {"pattern_prior": 0.8},
                "claim_boundary": "local only",
                "official_scores_claimed": False,
            },
            {
                "proposal_id": "p2",
                "proposal_type": "failure_fix",
                "based_on_failures": ["f1"],
                "score": 1.0,
                "rank": 2,
                "gate_labels": ["missing_target_scope"],
                "score_breakdown": {"pattern_prior": 0.8},
                "claim_boundary": "local only",
                "official_scores_claimed": False,
            },
        ],
        "claim_boundary": "local only",
        "official_scores_claimed": False,
    }

    payload = build_failure_driven_proposal_handoff(
        context=context,
        ranking=ranking,
        output_dir=tmp_path / "handoff",
        max_selected=1,
    )

    assert payload["status"] == "completed"
    assert payload["selected_next_proposals"][0]["proposal_id"] == "p1"
    assert payload["selected_next_proposals"][0]["requires_client_review"] is True
    assert payload["selected_next_proposals"][0]["change_surface"] == "prompt_profile"
    assert payload["selected_next_proposals"][0]["rollback_rule"]["if"] == ["canary_delta_lt_0"]
    assert payload["recommended_next_step"]["mcp_tool"] == "validate_client_proposal_contract"
    assert payload["memory_bridge"][0]["future_memory_type"] == "patch_or_failure"
    assert payload["memory_bridge"][0]["source_failure_ids"] == ["f1"]
    assert payload["executes_tool"] is False
    assert Path(payload["proposal_file"]).exists()
    assert Path(payload["markdown_file"]).exists()


def test_build_failure_driven_client_proposal_templates_match_contract(
    tmp_path: Path,
) -> None:
    handoff = {
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
                "executes_tool": False,
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

    payload = build_failure_driven_client_proposal_templates(
        handoff=handoff,
        output_dir=tmp_path / "templates",
    )

    assert payload["status"] == "completed"
    template = payload["proposal_templates"][0]
    validation = validate_client_proposal(template)
    assert validation["status"] == "accepted"
    assert template["proposal_id"].startswith("p1")
    assert template["change_surface"] == "prompt_profile"
    assert template["validation_plan"]["first_split"] == "canary"
    assert template["validation_plan"]["rollback_if"] == ["canary_delta_lt_0"]
    assert template["expected_effect"]["primary_metric"] == "SHIFT"
    assert Path(payload["proposal_file"]).exists()
    assert Path(payload["markdown_file"]).exists()


def test_bridge_failure_driven_outcome_to_memory_card_builds_candidate(
    tmp_path: Path,
) -> None:
    outcome = record_proposal_outcome(
        proposal={
            "proposal_id": "p1",
            "proposal_type": "failure_fix",
            "based_on_failures": ["f1"],
            "intent": "Preserve canary gain.",
            "change_surface": "routing",
            "target_scope": "single routing block",
            "claim_boundary": "local only",
            "official_scores_claimed": False,
        },
        evaluation={"dev_delta": {"SHIFT": 0.5}, "canary_delta": {"SHIFT": 0.1}},
        output_path=tmp_path / "proposal-outcome.json",
    )
    handoff = {
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

    payload = bridge_failure_driven_outcome_to_memory_card(
        outcome=outcome,
        handoff=handoff,
        output_path=tmp_path / "memory-card-candidate.json",
    )

    assert payload["status"] == "completed"
    candidate = payload["memory_card_candidate"]
    card = ResearchMemoryCard.from_dict(candidate)
    assert card.card_id == "failure-driven-p1"
    assert card.patch_type == "routing"
    assert card.failure_category == "canary_not_confirmed"
    assert Path(payload["output_path"]).exists()
