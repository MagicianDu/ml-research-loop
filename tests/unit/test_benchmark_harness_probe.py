from __future__ import annotations

from pathlib import Path

from lib.benchmarks import build_official_harness_probe


def test_official_harness_probe_reports_ready_when_prerequisites_are_present(
    tmp_path: Path,
) -> None:
    mle_repo = tmp_path / "mle-bench"
    (mle_repo / "mlebench").mkdir(parents=True)
    (mle_repo / "environment").mkdir()
    (mle_repo / "environment" / "Dockerfile").write_text("FROM python:3.11\n", encoding="utf-8")
    (mle_repo / "experiments").mkdir()
    paperbench_repo = tmp_path / "frontier-evals"
    paperbench_project = paperbench_repo / "project" / "paperbench"
    (paperbench_project / "paperbench").mkdir(parents=True)
    (paperbench_project / "pyproject.toml").write_text("[project]\nname='paperbench'\n", encoding="utf-8")
    paperbench_data = tmp_path / "paperbench-data"
    paperbench_data.mkdir()

    payload = build_official_harness_probe(
        mle_bench_repo=mle_repo,
        paperbench_repo=paperbench_repo,
        paperbench_data_dir=paperbench_data,
        env={
            "KAGGLE_USERNAME": "user",
            "KAGGLE_KEY": "secret",
            "OPENAI_API_KEY": "secret",
        },
        command_lookup=lambda command: f"/usr/bin/{command}",
    )

    assert payload["status"] == "ready"
    assert payload["read_only"] is True
    assert payload["official_scores_claimed"] is False
    assert payload["blocking_issue_count"] == 0
    assert [harness["name"] for harness in payload["harnesses"]] == [
        "mle_bench",
        "paperbench",
    ]
    assert payload["harnesses"][0]["status"] == "ready"
    assert payload["harnesses"][1]["status"] == "ready"
    assert all(check["status"] == "available" for check in payload["harnesses"][0]["required_checks"])
    assert all(check["status"] == "available" for check in payload["harnesses"][1]["required_checks"])


def test_official_harness_probe_reports_missing_prerequisites_without_secrets(
    tmp_path: Path,
) -> None:
    payload = build_official_harness_probe(
        mle_bench_repo=tmp_path / "missing-mle",
        paperbench_repo=tmp_path / "missing-paperbench",
        env={},
        command_lookup=lambda command: None,
    )

    assert payload["status"] == "needs_setup"
    assert payload["read_only"] is True
    assert payload["official_scores_claimed"] is False
    assert payload["blocking_issue_count"] > 0
    assert payload["harnesses"][0]["status"] == "needs_setup"
    assert payload["harnesses"][1]["status"] == "needs_setup"
    assert payload["next_actions"]
    payload_text = str(payload)
    assert "secret" not in payload_text
    assert "KAGGLE_KEY=" not in payload_text
    assert "OPENAI_API_KEY=" not in payload_text
