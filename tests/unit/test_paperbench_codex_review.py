from __future__ import annotations

import json
from pathlib import Path

from lib.benchmarks.paperbench_codex_review import (
    write_paperbench_codex_review_bundle,
    write_paperbench_codex_review_report,
)


def test_write_paperbench_codex_review_bundle_copies_artifacts_and_blocks_official_claims(
    tmp_path: Path,
) -> None:
    paper_dir = _write_paper_fixture(tmp_path)
    run_dir = _write_run_fixture(tmp_path)
    output_dir = tmp_path / "codex-review"
    stale_optional_file = output_dir / "packet" / "run" / "status.json"
    stale_optional_file.parent.mkdir(parents=True)
    stale_optional_file.write_text("stale", encoding="utf-8")

    payload = write_paperbench_codex_review_bundle(
        run_dir=run_dir,
        paper_dir=paper_dir,
        output_dir=output_dir,
    )

    assert payload["status"] == "written"
    assert payload["bundle"]["status"] == "ready_for_codex_review"
    assert payload["bundle"]["judge_type"] == "codex_assisted"
    assert payload["bundle"]["official_scores_claimed"] is False
    assert payload["bundle"]["paperbench_score"] is None
    assert Path(payload["bundle_path"]).is_file()
    assert Path(payload["prompt_path"]).is_file()

    bundle = json.loads(Path(payload["bundle_path"]).read_text(encoding="utf-8"))
    assert bundle["paper_id"] == "rice"
    assert bundle["review_schema"]["required_fields"] == [
        "summary",
        "codex_review_score",
        "leaf_scores",
        "evidence_refs",
        "missing_evidence",
        "confidence",
    ]
    assert bundle["packet_files"]["paper_md"].endswith("paper/paper.md")
    assert bundle["packet_files"]["rubric_json"].endswith("paper/rubric.json")
    assert bundle["packet_files"]["grade_json"].endswith("run/grade.json")
    assert bundle["packet_files"]["agent_log"].endswith("run/agent.log")
    assert bundle["packet_files"]["submission_executed_metadata"].endswith(
        "submissions/submission_executed_metadata.json"
    )
    assert (tmp_path / "codex-review" / "packet" / "paper" / "paper.md").read_text(
        encoding="utf-8"
    ).startswith("# RICE")
    assert not stale_optional_file.exists()

    prompt = Path(payload["prompt_path"]).read_text(encoding="utf-8")
    assert "Codex-assisted rubric review" in prompt
    assert "not an official PaperBench score" in prompt
    assert "official_scores_claimed=false" in prompt


def test_write_paperbench_codex_review_report_preserves_codex_boundary(
    tmp_path: Path,
) -> None:
    paper_dir = _write_paper_fixture(tmp_path)
    run_dir = _write_run_fixture(tmp_path)
    bundle_payload = write_paperbench_codex_review_bundle(
        run_dir=run_dir,
        paper_dir=paper_dir,
        output_dir=tmp_path / "codex-review",
    )
    review_payload = {
        "summary": "The reproduction script exists, but evidence is thin.",
        "codex_review_score": 0.25,
        "official_scores_claimed": True,
        "leaf_scores": [
            {
                "rubric_id": "env",
                "score": 0.5,
                "evidence_refs": ["run/grade.json", "submissions/submission_executed_metadata.json"],
                "missing_evidence": ["training curves"],
                "reasoning_summary": "The run created a script but did not reproduce results.",
                "confidence": 0.7,
            }
        ],
        "evidence_refs": ["run/grade.json"],
        "missing_evidence": ["experiment outputs"],
        "confidence": 0.65,
    }

    payload = write_paperbench_codex_review_report(
        bundle_path=Path(bundle_payload["bundle_path"]),
        review_payload=review_payload,
        output_dir=tmp_path / "codex-review-report",
    )

    assert payload["status"] == "written"
    report = json.loads(Path(payload["json_path"]).read_text(encoding="utf-8"))
    assert report["judge_type"] == "codex_assisted"
    assert report["official_scores_claimed"] is False
    assert report["paperbench_score"] is None
    assert report["codex_review"]["codex_review_score"] == 0.25
    assert report["codex_review"]["leaf_scores"][0]["missing_evidence"] == [
        "training curves"
    ]
    assert "official PaperBench score" in report["blocked_public_claims"]
    assert "Codex-assisted rubric review" in Path(payload["markdown_path"]).read_text(
        encoding="utf-8"
    )


def _write_paper_fixture(tmp_path: Path) -> Path:
    paper_dir = tmp_path / "paperbench-data" / "papers" / "rice"
    paper_dir.mkdir(parents=True)
    (paper_dir / "paper.md").write_text("# RICE\n\nPaper body.\n", encoding="utf-8")
    (paper_dir / "rubric.json").write_text(
        json.dumps({
            "id": "root",
            "requirements": "Reproduce the paper.",
            "sub_tasks": [{"id": "env", "requirements": "Set up environments."}],
        }),
        encoding="utf-8",
    )
    (paper_dir / "addendum.md").write_text("Addendum.\n", encoding="utf-8")
    return paper_dir


def _write_run_fixture(tmp_path: Path) -> Path:
    run_dir = tmp_path / "runs" / "group" / "rice_123"
    submission_dir = run_dir / "submissions" / "2026-05-07T10-08-10-UTC"
    submission_dir.mkdir(parents=True)
    (run_dir / "grade.json").write_text(
        json.dumps({
            "score": 1.0,
            "paperbench_result": {
                "paper_id": "rice",
                "submission_exists": True,
                "judge_output": {"judge_type": "dummy", "score": 1.0},
            },
        }),
        encoding="utf-8",
    )
    (run_dir / "metadata.json").write_text(
        json.dumps({"run_id": "rice_123", "status_exists": True}),
        encoding="utf-8",
    )
    (run_dir / "agent.log").write_text("agent log\n", encoding="utf-8")
    (run_dir / "run.log").write_text("run log\n", encoding="utf-8")
    (submission_dir / "log.json").write_text("{}", encoding="utf-8")
    (submission_dir / "submission_executed_metadata.json").write_text(
        json.dumps({"repro_script_exists": True}),
        encoding="utf-8",
    )
    (submission_dir / "submission_executed_grader_output_0.json").write_text(
        json.dumps({"score": 1.0}),
        encoding="utf-8",
    )
    return run_dir
