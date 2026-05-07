"""Official MLE-bench prepared-data bridge for client-planned agent loops."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


OFFICIAL_MLE_BENCH = True
OFFICIAL_SCORES_CLAIMED = False


def materialize_official_mle_agent_workspace(
    *,
    competition_id: str,
    prepared_competition_dir: Path,
    runtime_root: Path,
    workspace_name: str | None = None,
) -> dict[str, Any]:
    """Create an agent-editable workspace from official prepared MLE-bench data."""
    prepared_competition_dir = prepared_competition_dir.expanduser().resolve()
    runtime_root = runtime_root.expanduser().resolve()
    public_dir = prepared_competition_dir / "prepared" / "public"
    sample_submission = public_dir / "sample_submission.csv"
    if not sample_submission.is_file():
        raise FileNotFoundError(f"missing official sample submission: {sample_submission}")

    workspace = (
        runtime_root
        / "benchmark-workspaces"
        / "mle-bench"
        / _safe_name(workspace_name or competition_id)
    )
    input_dir = workspace / "input"
    input_dir.mkdir(parents=True, exist_ok=True)
    _copy_tree_contents(public_dir, input_dir)
    shutil.copy2(input_dir / "sample_submission.csv", workspace / "submission.csv")
    _write_default_solver(workspace / "solve.py")
    _write_agent_instructions(
        workspace / "agent_instructions.md",
        competition_id=competition_id,
    )

    contract = _workspace_contract(
        competition_id=competition_id,
        prepared_competition_dir=prepared_competition_dir,
        runtime_root=runtime_root,
        workspace=workspace,
    )
    contract_path = workspace / "benchmark_contract.json"
    contract_path.write_text(
        json.dumps(contract, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    workspace_files = _workspace_public_file_index(input_dir)
    return {
        "status": "ready_for_agent",
        "official_mle_bench": OFFICIAL_MLE_BENCH,
        "official_scores_claimed": OFFICIAL_SCORES_CLAIMED,
        "competition_id": competition_id,
        "prepared_competition_dir": str(prepared_competition_dir),
        "runtime_root": str(runtime_root),
        "workspace": str(workspace),
        "input_dir": str(input_dir),
        "submission_path": str(workspace / "submission.csv"),
        "solver_path": str(workspace / "solve.py"),
        "agent_instructions_path": str(workspace / "agent_instructions.md"),
        "contract_path": str(contract_path),
        "workspace_files": {"public": workspace_files},
        "allowed_patch_files": ["solve.py", "submission.csv"],
        "test_command": [sys.executable, "solve.py"],
        "claim_policy": _claim_policy(),
    }


def grade_official_mle_submission(
    *,
    competition_id: str,
    submission_path: Path,
    data_dir: Path,
    output_dir: Path,
    mlebench_executable: Path,
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    """Run official `mlebench grade-sample` and persist the local scorer report."""
    submission_path = submission_path.expanduser().resolve()
    data_dir = data_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    mlebench_executable = mlebench_executable.expanduser().resolve()
    if not submission_path.is_file():
        raise FileNotFoundError(f"missing submission: {submission_path}")
    if not data_dir.exists():
        raise FileNotFoundError(f"missing MLE-bench data dir: {data_dir}")
    if not mlebench_executable.is_file():
        raise FileNotFoundError(f"missing mlebench executable: {mlebench_executable}")

    output_dir.mkdir(parents=True, exist_ok=True)
    command = [
        str(mlebench_executable),
        "grade-sample",
        str(submission_path),
        competition_id,
        "--data-dir",
        str(data_dir),
    ]
    started_at = _utc_now()
    proc = subprocess.run(
        command,
        env=_external_harness_env(),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=max(1, int(timeout_seconds)),
        check=False,
    )
    finished_at = _utc_now()
    log_path = output_dir / "grade.log"
    log_path.write_text(
        "\n".join([
            f"started_at={started_at}",
            f"finished_at={finished_at}",
            "command=" + json.dumps(command),
            f"returncode={proc.returncode}",
            "",
            proc.stdout,
        ]),
        encoding="utf-8",
    )
    if proc.returncode != 0:
        return {
            "status": "failed",
            "official_mle_bench": OFFICIAL_MLE_BENCH,
            "official_scores_claimed": OFFICIAL_SCORES_CLAIMED,
            "competition_id": competition_id,
            "returncode": proc.returncode,
            "log_path": str(log_path),
            "error": f"mlebench grade-sample exited {proc.returncode}",
            "claim_policy": _claim_policy(),
        }

    report = _parse_json_object(proc.stdout)
    report_path = output_dir / "grade-report.json"
    report_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return {
        "status": "graded",
        "official_mle_bench": OFFICIAL_MLE_BENCH,
        "official_scores_claimed": OFFICIAL_SCORES_CLAIMED,
        "competition_id": competition_id,
        "submission_path": str(submission_path),
        "data_dir": str(data_dir),
        "mlebench_executable": str(mlebench_executable),
        "report_path": str(report_path),
        "log_path": str(log_path),
        "report": report,
        "returncode": proc.returncode,
        "claim_policy": _claim_policy(),
    }


def run_official_mle_solver_round(
    *,
    competition_id: str,
    workspace: Path,
    data_dir: Path,
    output_dir: Path,
    mlebench_executable: Path,
    python_executable: Path | str = sys.executable,
    round_id: str = "round-001",
    timeout_seconds: int = 300,
) -> dict[str, Any]:
    """Run `solve.py`, grade `submission.csv`, and persist one round report."""
    workspace = workspace.expanduser().resolve()
    data_dir = data_dir.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    mlebench_executable = mlebench_executable.expanduser().resolve()
    round_dir = output_dir / _safe_name(round_id)
    round_dir.mkdir(parents=True, exist_ok=True)
    solve_path = workspace / "solve.py"
    submission_path = workspace / "submission.csv"
    if not solve_path.is_file():
        raise FileNotFoundError(f"missing solver: {solve_path}")

    solve = _run_solver(
        workspace=workspace,
        python_executable=python_executable,
        timeout_seconds=timeout_seconds,
        log_path=round_dir / "solve.log",
    )
    payload: dict[str, Any] = {
        "status": "failed",
        "stage": "solve",
        "official_mle_bench": OFFICIAL_MLE_BENCH,
        "official_scores_claimed": OFFICIAL_SCORES_CLAIMED,
        "round_id": round_id,
        "competition_id": competition_id,
        "workspace": str(workspace),
        "submission_path": str(submission_path),
        "solve": solve,
        "grade": None,
        "round_report_path": str(round_dir / "round-report.json"),
        "claim_policy": _claim_policy(),
    }

    if solve["returncode"] != 0:
        _write_round_report(payload)
        return payload
    if not submission_path.is_file():
        payload["stage"] = "submission"
        payload["error"] = f"solver completed but did not write {submission_path.name}"
        _write_round_report(payload)
        return payload

    try:
        grade = grade_official_mle_submission(
            competition_id=competition_id,
            submission_path=submission_path,
            data_dir=data_dir,
            output_dir=round_dir,
            mlebench_executable=mlebench_executable,
            timeout_seconds=timeout_seconds,
        )
    except Exception as exc:
        payload["stage"] = "grade"
        payload["error"] = str(exc)
        _write_round_report(payload)
        return payload

    payload["stage"] = "grade"
    payload["grade"] = grade
    if grade.get("status") == "graded":
        payload["status"] = "graded"
    _write_round_report(payload)
    return payload


def _workspace_contract(
    *,
    competition_id: str,
    prepared_competition_dir: Path,
    runtime_root: Path,
    workspace: Path,
) -> dict[str, Any]:
    return {
        "contract_version": "2026-05-07.official-mle-agent-loop.v1",
        "generated_at": _utc_now(),
        "competition_id": competition_id,
        "official_mle_bench": OFFICIAL_MLE_BENCH,
        "official_scores_claimed": OFFICIAL_SCORES_CLAIMED,
        "prepared_competition_dir": str(prepared_competition_dir),
        "runtime_root": str(runtime_root),
        "workspace": str(workspace),
        "input_dir": str(workspace / "input"),
        "submission_path": str(workspace / "submission.csv"),
        "allowed_patch_files": ["solve.py", "submission.csv"],
        "solve_command": [sys.executable, "solve.py"],
        "grade_tool": {
            "tool_name": "grade_official_mle_bench_submission",
            "submission_path": str(workspace / "submission.csv"),
            "competition_id": competition_id,
        },
        "claim_policy": _claim_policy(),
    }


def _copy_tree_contents(source: Path, destination: Path) -> None:
    for item in source.iterdir():
        target = destination / item.name
        if item.is_dir():
            shutil.copytree(item, target, dirs_exist_ok=True)
        elif item.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def _write_default_solver(path: Path) -> None:
    path.write_text(
        "\n".join([
            "from __future__ import annotations",
            "",
            "import shutil",
            "from pathlib import Path",
            "",
            "",
            "def main() -> None:",
            "    sample_submission = Path('input') / 'sample_submission.csv'",
            "    submission = Path('submission.csv')",
            "    shutil.copyfile(sample_submission, submission)",
            "    print(f'wrote {submission}')",
            "",
            "",
            "if __name__ == '__main__':",
            "    main()",
            "",
        ]),
        encoding="utf-8",
    )


def _write_agent_instructions(path: Path, *, competition_id: str) -> None:
    path.write_text(
        "\n".join([
            f"# Official MLE-bench Workspace: {competition_id}",
            "",
            "Use the files under `input/` as the public prepared competition data.",
            "Generate `submission.csv` with the same schema as `input/sample_submission.csv`.",
            "You may edit `solve.py` and `submission.csv` only unless the operator expands the allowlist.",
            "Run `python solve.py` before grading.",
            "",
            "This workspace uses the official MLE-bench prepared data shape, but local",
            "`grade-sample` feedback is not a leaderboard score. Do not claim an official",
            "public benchmark result unless a separate evidence bundle explicitly allows it.",
            "",
        ]),
        encoding="utf-8",
    )


def _workspace_public_file_index(input_dir: Path) -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for path in sorted(item for item in input_dir.rglob("*") if item.is_file()):
        relative = path.relative_to(input_dir).as_posix()
        index[relative] = {
            "path": str(path),
            "role": _public_file_role(relative),
            "size_bytes": path.stat().st_size,
        }
    return index


def _public_file_role(relative: str) -> str:
    name = Path(relative).name
    if name == "sample_submission.csv":
        return "sample_submission"
    if name == "train.csv":
        return "train"
    if name == "test.csv":
        return "test"
    if name in {"description.md", "description_obfuscated.md"}:
        return "description"
    return "public_data"


def _parse_json_object(stdout: str) -> dict[str, Any]:
    start = stdout.find("{")
    end = stdout.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("mlebench grade-sample output did not contain a JSON report")
    return json.loads(stdout[start : end + 1])


def _run_solver(
    *,
    workspace: Path,
    python_executable: Path | str,
    timeout_seconds: int,
    log_path: Path,
) -> dict[str, Any]:
    command = [str(python_executable), "solve.py"]
    started_at = _utc_now()
    try:
        proc = subprocess.run(
            command,
            cwd=str(workspace),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=max(1, int(timeout_seconds)),
            check=False,
        )
        stdout = proc.stdout
        returncode = proc.returncode
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        stdout = _timeout_output(exc)
        returncode = -1
        timed_out = True
    finished_at = _utc_now()
    log_path.write_text(
        "\n".join([
            f"started_at={started_at}",
            f"finished_at={finished_at}",
            "command=" + json.dumps(command),
            f"returncode={returncode}",
            f"timed_out={str(timed_out).lower()}",
            "",
            stdout,
        ]),
        encoding="utf-8",
    )
    return {
        "returncode": returncode,
        "timed_out": timed_out,
        "stdout_tail": _tail(stdout),
        "log_path": str(log_path),
    }


def _write_round_report(payload: dict[str, Any]) -> None:
    Path(payload["round_report_path"]).write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _timeout_output(exc: subprocess.TimeoutExpired) -> str:
    output = exc.stdout or exc.output or ""
    if isinstance(output, bytes):
        return output.decode("utf-8", errors="replace")
    return str(output)


def _tail(text: str, max_lines: int = 80) -> str:
    return "\n".join(text.splitlines()[-max_lines:])


def _external_harness_env() -> dict[str, str]:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)
    env["PYTHONNOUSERSITE"] = "1"
    return env


def _safe_name(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_"} else "-" for char in value)


def _claim_policy() -> dict[str, Any]:
    return {
        "leaderboard_score": "blocked",
        "local_grade_sample": "allowed_with_limitations",
        "official_score_evidence_required": True,
    }


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()
