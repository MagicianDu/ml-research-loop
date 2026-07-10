from __future__ import annotations

import json
from pathlib import Path

from lib.benchmarks.arguard_b1 import write_arguard_b1_live_verification


def test_arguard_b1_live_verification_records_public_state_without_submission(
    tmp_path: Path,
) -> None:
    def fake_fetcher(url: str, timeout_seconds: int) -> dict[str, object]:
        assert timeout_seconds == 9
        if "codabench" in url:
            text = "<title>ArGuard-Subtask-B1-Binary Classification - Codabench</title>"
        elif "main/README.md" in url and "taskB" not in url:
            text = (
                "# ArGuard at ArabicNLP 2026\n"
                "training and development data, and evaluation scripts: May 25, 2026\n"
                "blind test set release: July 25, 2026\n"
                "Final submission deadline and release of final results: July 30, 2026\n"
            )
        else:
            text = (
                "# Task B\n"
                "Subtask B1: Given an Arabic prompt, classify it as safe or unsafe.\n"
                "The official metric for all subtasks is macro-F1.\n"
                "Subtask B1: TSV file with header id<TAB>label<TAB>run_id.\n"
                "Training and development data will be released after task acceptance.\n"
                "The scorer will be released in scorer.\n"
            )
        return {
            "status": "reachable",
            "url": url,
            "status_code": 200,
            "text_excerpt": text[:200],
            "raw_text": text,
        }

    payload = write_arguard_b1_live_verification(
        tmp_path / "arguard-b1-p0",
        timeout_seconds=9,
        include_raw=False,
        fetcher=fake_fetcher,
    )

    json_path = Path(payload["json_path"])
    markdown_path = Path(payload["contract_path"])
    written = json.loads(json_path.read_text(encoding="utf-8"))
    markdown = markdown_path.read_text(encoding="utf-8")

    assert payload["status"] == "written"
    assert payload["verification_status"] == "verified_with_asset_blockers"
    assert payload["official_scores_claimed"] is False
    assert payload["manual_submission_required"] is True
    assert written["target"]["target_id"] == "arguard-b1-binary-classification"
    assert written["target"]["metrics"] == ["macro-F1"]
    assert written["target"]["submission_format"]["format"] == "tsv"
    assert written["asset_status"]["data_and_scorer"] == (
        "not_confirmed_released_in_public_readme"
    )
    assert "released_train_dev_scorer_not_confirmed" in written["hard_blockers"]
    assert {check["check_id"] for check in written["checks"]} == {
        "codabench_competition",
        "repository_readme",
        "task_readme",
    }
    assert "official_scores_claimed: `false`" in markdown
    assert "released_train_dev_scorer_not_confirmed" in markdown
