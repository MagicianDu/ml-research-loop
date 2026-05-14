from __future__ import annotations

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_client_planner_template_documents_required_decisions() -> None:
    doc = (PROJECT_ROOT / "docs" / "client-planner-template.md").read_text(encoding="utf-8")

    required_terms = [
        "experiment_state",
        "next_round.task_patch",
        "run_hypothesis_experiment",
        "run_ai_autoresearch",
        "failure_summary",
        "failure_diagnostics",
        "metric_stop_policy",
        "research_evidence_gate",
        "deduplication_report",
        "cache_summary",
        "provider_quality_matrix",
        "planner_actions",
        "next_experiment_plan",
        "proposed_task_patch",
        "dry_run_validation",
        "run_next_experiment_from_review",
        "run_client_patch_experiment",
        "apply_client_code_patch",
        "change_proposal",
        "patch_execution",
        "memory suggestion",
        "provenance",
        "停止",
    ]
    for term in required_terms:
        assert term in doc


def test_codex_claude_prompt_is_reusable() -> None:
    prompt = (
        PROJECT_ROOT / "examples" / "planner" / "codex-claude-planner-prompt.md"
    ).read_text(encoding="utf-8")

    assert "你是 ml-research-loop 的客户端 planner" in prompt
    assert "只在显式需要无人值守时调用 run_ai_autoresearch" in prompt
    assert "planner_actions" in prompt
    assert "run_client_patch_experiment" in prompt
    assert "apply_client_code_patch" in prompt
    assert "输出下一次 MCP 调用 JSON" in prompt
