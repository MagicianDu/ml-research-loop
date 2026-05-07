from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.benchmarks.official_mle_bridge import (
    grade_official_mle_submission,
    materialize_official_mle_agent_workspace,
)
from lib.benchmarks import official_mle_bridge


def test_materialize_official_mle_workspace_copies_public_files_and_writes_contract(
    tmp_path: Path,
) -> None:
    prepared_competition_dir = _write_prepared_spooky_fixture(tmp_path)

    payload = materialize_official_mle_agent_workspace(
        competition_id="spooky-author-identification",
        prepared_competition_dir=prepared_competition_dir,
        runtime_root=tmp_path / "runtime",
        workspace_name="spooky-debug",
    )

    workspace = Path(payload["workspace"])
    contract = json.loads((workspace / "benchmark_contract.json").read_text(encoding="utf-8"))

    assert payload["status"] == "ready_for_agent"
    assert payload["official_mle_bench"] is True
    assert payload["official_scores_claimed"] is False
    assert payload["competition_id"] == "spooky-author-identification"
    assert payload["claim_policy"]["leaderboard_score"] == "blocked"
    assert payload["workspace_files"]["public"]["sample_submission.csv"]["role"] == "sample_submission"
    assert payload["allowed_patch_files"] == ["solve.py", "submission.csv"]
    assert payload["test_command"][-1] == "solve.py"
    assert (workspace / "input" / "train.csv").read_text(encoding="utf-8").startswith(
        "id,text,author"
    )
    assert (workspace / "solve.py").is_file()
    assert (workspace / "agent_instructions.md").is_file()
    assert (workspace / "submission.csv").read_text(encoding="utf-8").startswith(
        "id,EAP,HPL,MWS"
    )
    assert contract["competition_id"] == "spooky-author-identification"
    assert contract["official_scores_claimed"] is False
    assert contract["grade_tool"]["tool_name"] == "grade_official_mle_bench_submission"


def test_materialize_official_mle_workspace_rejects_missing_sample_submission(
    tmp_path: Path,
) -> None:
    prepared_competition_dir = tmp_path / "data" / "spooky-author-identification"
    (prepared_competition_dir / "prepared" / "public").mkdir(parents=True)

    with pytest.raises(FileNotFoundError, match="sample_submission.csv"):
        materialize_official_mle_agent_workspace(
            competition_id="spooky-author-identification",
            prepared_competition_dir=prepared_competition_dir,
            runtime_root=tmp_path / "runtime",
        )


def test_grade_official_mle_submission_parses_report_and_writes_artifacts(
    tmp_path: Path,
) -> None:
    submission = tmp_path / "submission.csv"
    submission.write_text("id,EAP,HPL,MWS\n2,0.33,0.33,0.34\n", encoding="utf-8")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    mlebench = tmp_path / "mlebench"
    mlebench.write_text(
        "\n".join([
            "#!/usr/bin/env python3",
            "import json",
            "print('Competition report:')",
            "print(json.dumps({",
            "    'competition_id': 'spooky-author-identification',",
            "    'score': 1.23,",
            "    'valid_submission': True,",
            "    'submission_exists': True,",
            "}))",
        ]),
        encoding="utf-8",
    )
    mlebench.chmod(0o755)

    payload = grade_official_mle_submission(
        competition_id="spooky-author-identification",
        submission_path=submission,
        data_dir=data_dir,
        output_dir=tmp_path / "reports",
        mlebench_executable=mlebench,
        timeout_seconds=10,
    )

    assert payload["status"] == "graded"
    assert payload["official_mle_bench"] is True
    assert payload["official_scores_claimed"] is False
    assert payload["report"]["score"] == 1.23
    assert payload["report"]["valid_submission"] is True
    assert Path(payload["report_path"]).is_file()
    assert Path(payload["log_path"]).is_file()
    assert "grade-sample" in Path(payload["log_path"]).read_text(encoding="utf-8")


def test_grade_official_mle_submission_does_not_pollute_harness_pythonpath(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("PYTHONPATH", "/tmp/project-pythonpath-that-must-not-leak")
    submission = tmp_path / "submission.csv"
    submission.write_text("id,EAP,HPL,MWS\n2,0.33,0.33,0.34\n", encoding="utf-8")
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    mlebench = tmp_path / "mlebench"
    mlebench.write_text(
        "\n".join([
            "#!/usr/bin/env python3",
            "import json",
            "import os",
            "print(json.dumps({'score': 1.23, 'pythonpath': os.environ.get('PYTHONPATH')}))",
        ]),
        encoding="utf-8",
    )
    mlebench.chmod(0o755)

    payload = grade_official_mle_submission(
        competition_id="spooky-author-identification",
        submission_path=submission,
        data_dir=data_dir,
        output_dir=tmp_path / "reports",
        mlebench_executable=mlebench,
        timeout_seconds=10,
    )

    assert payload["report"]["pythonpath"] in {None, ""}


def test_run_official_mle_solver_round_runs_solver_then_grades_submission(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "solve.py").write_text(
        "\n".join([
            "from pathlib import Path",
            "Path('submission.csv').write_text('id,EAP,HPL,MWS\\n2,0.2,0.3,0.5\\n')",
            "print('solver wrote submission.csv')",
        ]),
        encoding="utf-8",
    )
    data_dir = tmp_path / "mlebench-data"
    data_dir.mkdir()
    mlebench = _write_fake_mlebench(tmp_path)

    payload = official_mle_bridge.run_official_mle_solver_round(
        competition_id="spooky-author-identification",
        workspace=workspace,
        data_dir=data_dir,
        output_dir=tmp_path / "rounds",
        mlebench_executable=mlebench,
        python_executable=Path("python3"),
        round_id="round-001",
        timeout_seconds=10,
    )

    assert payload["status"] == "graded"
    assert payload["official_mle_bench"] is True
    assert payload["official_scores_claimed"] is False
    assert payload["round_id"] == "round-001"
    assert payload["submission_path"] == str(workspace.resolve() / "submission.csv")
    assert payload["solve"]["returncode"] == 0
    assert "solver wrote submission.csv" in payload["solve"]["stdout_tail"]
    assert payload["grade"]["report"]["score"] == 1.23
    assert payload["grade"]["report"]["valid_submission"] is True
    assert Path(payload["solve"]["log_path"]).is_file()
    assert Path(payload["round_report_path"]).is_file()
    report = json.loads(Path(payload["round_report_path"]).read_text(encoding="utf-8"))
    assert report["status"] == "graded"
    assert report["grade"]["report"]["score"] == 1.23


def test_run_official_mle_solver_round_stops_before_grade_when_solver_fails(
    tmp_path: Path,
) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "solve.py").write_text(
        "import sys\nprint('boom')\nsys.exit(17)\n",
        encoding="utf-8",
    )
    data_dir = tmp_path / "mlebench-data"
    data_dir.mkdir()

    payload = official_mle_bridge.run_official_mle_solver_round(
        competition_id="spooky-author-identification",
        workspace=workspace,
        data_dir=data_dir,
        output_dir=tmp_path / "rounds",
        mlebench_executable=tmp_path / "missing-mlebench",
        python_executable=Path("python3"),
        round_id="round-001",
        timeout_seconds=10,
    )

    assert payload["status"] == "failed"
    assert payload["stage"] == "solve"
    assert payload["solve"]["returncode"] == 17
    assert "boom" in payload["solve"]["stdout_tail"]
    assert payload["grade"] is None
    assert Path(payload["solve"]["log_path"]).is_file()
    assert Path(payload["round_report_path"]).is_file()


def _write_prepared_spooky_fixture(tmp_path: Path) -> Path:
    prepared_competition_dir = tmp_path / "data" / "spooky-author-identification"
    prepared = prepared_competition_dir / "prepared"
    public = prepared / "public"
    private = prepared / "private"
    public.mkdir(parents=True)
    private.mkdir(parents=True)
    (public / "train.csv").write_text("id,text,author\n1,hello,EAP\n", encoding="utf-8")
    (public / "test.csv").write_text("id,text\n2,world\n", encoding="utf-8")
    (public / "sample_submission.csv").write_text(
        "id,EAP,HPL,MWS\n2,0.33,0.33,0.34\n",
        encoding="utf-8",
    )
    (public / "description.md").write_text("# Task\n", encoding="utf-8")
    (private / "test.csv").write_text("id,author\n2,EAP\n", encoding="utf-8")
    return prepared_competition_dir


def _write_fake_mlebench(tmp_path: Path) -> Path:
    mlebench = tmp_path / "mlebench"
    mlebench.write_text(
        "\n".join([
            "#!/usr/bin/env python3",
            "import json",
            "print('Competition report:')",
            "print(json.dumps({",
            "    'competition_id': 'spooky-author-identification',",
            "    'score': 1.23,",
            "    'valid_submission': True,",
            "    'submission_exists': True,",
            "}))",
        ]),
        encoding="utf-8",
    )
    mlebench.chmod(0o755)
    return mlebench
