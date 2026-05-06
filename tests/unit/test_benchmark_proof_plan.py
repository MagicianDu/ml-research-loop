from __future__ import annotations

from lib.benchmarks import build_public_proof_plan


def test_public_proof_plan_blocks_when_probe_needs_setup() -> None:
    probe = {
        "status": "needs_setup",
        "read_only": True,
        "official_scores_claimed": False,
        "harnesses": [
            {
                "name": "mle_bench",
                "status": "needs_setup",
                "required_checks": [
                    {"id": "command:git-lfs", "status": "missing"},
                    {"id": "credentials:kaggle", "status": "missing"},
                ],
                "blocked_commands": ["mlebench prepare"],
            },
            {
                "name": "paperbench",
                "status": "needs_setup",
                "required_checks": [
                    {"id": "command:uv", "status": "missing"},
                    {"id": "official_data", "status": "missing"},
                ],
                "blocked_commands": ["paperbench direct-submission grading"],
            },
        ],
    }

    payload = build_public_proof_plan(probe)

    assert payload["status"] == "blocked"
    assert payload["read_only"] is True
    assert payload["official_scores_claimed"] is False
    assert payload["recommended_environment"] == "external_evaluation_environment"
    assert "mle_bench:command:git-lfs" in payload["missing_prerequisites"]
    assert "mle_bench:credentials:kaggle" in payload["missing_prerequisites"]
    assert "paperbench:command:uv" in payload["missing_prerequisites"]
    assert "paperbench:official_data" in payload["missing_prerequisites"]
    assert "python scripts/benchmark_harness_probe.py --json" in payload["safe_next_commands"]
    assert "python scripts/benchmark_proof_plan.py --json" in payload["safe_next_commands"]
    assert any("missing official harness prerequisites" in action for action in payload["next_actions"])
    assert "mlebench prepare" in payload["blocked_commands"]
    assert "paperbench direct-submission grading" in payload["blocked_commands"]
    assert payload["harness_probe"] is probe


def test_public_proof_plan_is_ready_when_probe_is_ready() -> None:
    probe = {
        "status": "ready",
        "read_only": True,
        "official_scores_claimed": False,
        "harnesses": [
            {
                "name": "mle_bench",
                "status": "ready",
                "required_checks": [
                    {"id": "command:git-lfs", "status": "available"},
                    {"id": "credentials:kaggle", "status": "available"},
                ],
                "blocked_commands": ["mlebench prepare"],
            },
            {
                "name": "paperbench",
                "status": "ready",
                "required_checks": [
                    {"id": "command:uv", "status": "available"},
                    {"id": "official_data", "status": "available"},
                ],
                "blocked_commands": ["paperbench direct-submission grading"],
            },
        ],
    }

    payload = build_public_proof_plan(probe)

    assert payload["status"] == "ready_for_debug_run"
    assert payload["recommended_environment"] == "local_worktree"
    assert payload["missing_prerequisites"] == []
    assert any("official debug" in action for action in payload["next_actions"])
    assert "official_scores_claimed=false" in payload["artifact_requirements"]
    assert payload["blocked_commands"] == []


def test_public_proof_plan_uses_current_machine_for_explicit_ready_probe() -> None:
    probe = {
        "status": "ready",
        "read_only": True,
        "official_scores_claimed": False,
        "preferred_environment": "current_machine",
        "harnesses": [],
    }

    payload = build_public_proof_plan(probe)

    assert payload["status"] == "ready_for_debug_run"
    assert payload["recommended_environment"] == "current_machine"
