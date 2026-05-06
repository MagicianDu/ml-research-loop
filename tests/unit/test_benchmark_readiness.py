from __future__ import annotations

from lib.benchmarks import build_benchmark_readiness


def test_benchmark_readiness_lists_non_official_adapter_flows() -> None:
    payload = build_benchmark_readiness()

    assert payload["status"] == "compatibility_ready"
    assert payload["official_scores_claimed"] is False
    assert [adapter["name"] for adapter in payload["adapters"]] == [
        "mle_bench",
        "paperbench",
    ]
    assert payload["adapters"][0]["official"] is False
    assert payload["adapters"][0]["demo_command"][0] == "python"
    assert "submission_path" in payload["adapters"][0]["artifact_fields"]
    assert payload["adapters"][1]["official"] is False
    assert "grading.score" in payload["adapters"][1]["artifact_fields"]
    assert payload["next_milestones"] == [
        "P13 combined compatibility smoke",
        "P14 official harness feasibility probes",
        "P15 public proof run",
    ]
