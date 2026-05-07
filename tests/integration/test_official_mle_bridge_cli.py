from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_official_mle_bridge_cli_creates_workspace_and_grades_submission(
    tmp_path: Path,
) -> None:
    prepared_competition_dir = _write_prepared_fixture(tmp_path)
    runtime_root = tmp_path / "runtime"

    workspace_proc = _run_cli([
        "benchmark",
        "mle-workspace",
        "--competition-id",
        "spooky-author-identification",
        "--prepared-competition-dir",
        str(prepared_competition_dir),
        "--runtime-root",
        str(runtime_root),
        "--workspace-name",
        "spooky-debug",
        "--json",
    ])
    assert workspace_proc.returncode == 0, workspace_proc.stdout
    workspace_payload = json.loads(workspace_proc.stdout.splitlines()[-1])
    workspace = Path(workspace_payload["workspace"])

    mlebench = _write_fake_mlebench(tmp_path)
    round_proc = _run_cli([
        "benchmark",
        "mle-round",
        "--competition-id",
        "spooky-author-identification",
        "--workspace",
        str(workspace),
        "--data-dir",
        str(tmp_path / "mlebench-data"),
        "--mlebench",
        str(mlebench),
        "--output-dir",
        str(runtime_root / "benchmark-rounds"),
        "--python",
        sys.executable,
        "--round-id",
        "round-001",
        "--json",
    ])

    assert round_proc.returncode == 0, round_proc.stdout
    round_payload = json.loads(round_proc.stdout.splitlines()[-1])
    assert round_payload["status"] == "graded"
    assert round_payload["solve"]["returncode"] == 0
    assert round_payload["grade"]["report"]["valid_submission"] is True
    assert round_payload["official_scores_claimed"] is False
    assert Path(round_payload["round_report_path"]).is_file()


def _run_cli(args: list[str]) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "PYTHONPATH": (
            f"{PROJECT_ROOT}{os.pathsep}"
            f"{PROJECT_ROOT / '.venv' / 'lib' / 'python3.13' / 'site-packages'}"
        ),
    }
    return subprocess.run(
        [sys.executable, "-m", "scripts.cli", *args],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=60,
        check=False,
    )


def _write_prepared_fixture(tmp_path: Path) -> Path:
    competition_dir = tmp_path / "mlebench-data" / "spooky-author-identification"
    public = competition_dir / "prepared" / "public"
    public.mkdir(parents=True)
    (public / "train.csv").write_text("id,text,author\n1,hello,EAP\n", encoding="utf-8")
    (public / "test.csv").write_text("id,text\n2,world\n", encoding="utf-8")
    (public / "sample_submission.csv").write_text(
        "id,EAP,HPL,MWS\n2,0.33,0.33,0.34\n",
        encoding="utf-8",
    )
    (public / "description.md").write_text("# Spooky\n", encoding="utf-8")
    return competition_dir


def _write_fake_mlebench(tmp_path: Path) -> Path:
    mlebench = tmp_path / "fake-bin" / "mlebench"
    mlebench.parent.mkdir(parents=True)
    mlebench.write_text(
        "\n".join([
            "#!/usr/bin/env python3",
            "import json",
            "print('Competition report:')",
            "print(json.dumps({",
            "    'competition_id': 'spooky-author-identification',",
            "    'score': 1.08468,",
            "    'submission_exists': True,",
            "    'valid_submission': True,",
            "}))",
        ]),
        encoding="utf-8",
    )
    mlebench.chmod(0o755)
    return mlebench
