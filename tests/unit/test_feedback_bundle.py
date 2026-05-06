from __future__ import annotations

import json
import sys
from pathlib import Path

from lib.feedback_bundle import (
    build_feedback_bundle,
    redact_text,
    render_feedback_markdown,
    write_feedback_bundle,
)


def test_redact_text_masks_home_paths_and_common_tokens() -> None:
    text = (
        "/Users/alice/projects/ml-research-loop failed with "
        "ghp_1234567890abcdefghijklmnopqrstuv and sk-proj-abcdef123456"
    )

    redacted = redact_text(text, home=Path("/Users/alice"))

    assert "/Users/alice" not in redacted
    assert "~/projects/ml-research-loop" in redacted
    assert "ghp_" not in redacted
    assert "sk-proj-" not in redacted
    assert "[REDACTED_TOKEN]" in redacted


def test_build_feedback_bundle_collects_redacted_logs_and_artifacts(tmp_path: Path) -> None:
    project_root = tmp_path / "checkout"
    project_root.mkdir()
    runtime_root = tmp_path / "runtime"
    result_dir = runtime_root / "results"
    log_dir = runtime_root / "workdir" / "demo" / "logs"
    result_dir.mkdir(parents=True)
    log_dir.mkdir(parents=True)
    (result_dir / "demo.json").write_text(
        json.dumps({
            "task_id": "demo",
            "status": "failed",
            "error": "token ghp_1234567890abcdefghijklmnopqrstuv",
        }),
        encoding="utf-8",
    )
    (runtime_root / "snapshots" / "demo" / "exp-001").mkdir(parents=True)
    (log_dir / "exp-001.log").write_text(
        "\n".join([
            "line 1",
            f"private path {Path.home() / 'secret'}",
            "OPENAI_API_KEY=sk-proj-abcdef1234567890",
        ]),
        encoding="utf-8",
    )

    bundle = build_feedback_bundle(
        project_root=project_root,
        runtime_root=runtime_root,
        task_id="demo",
        log_lines=5,
        python_executable=sys.executable,
    )

    assert bundle["bundle_version"] == "2026-05-06.preview-feedback.v1"
    assert bundle["service"]["contract_version"] == "2026-04-30.preview.v1"
    assert bundle["runtime"]["runtime_root"] == str(runtime_root)
    assert bundle["task"]["status"] == "failed"
    assert bundle["artifacts"]["results"] == [str(result_dir / "demo.json")]
    assert bundle["artifacts"]["snapshots"] == [str(runtime_root / "snapshots" / "demo")]

    serialized = json.dumps(bundle, ensure_ascii=False)
    assert "ghp_" not in serialized
    assert "sk-proj-" not in serialized
    assert str(Path.home()) not in serialized


def test_write_feedback_bundle_writes_json_and_markdown(tmp_path: Path) -> None:
    bundle = {
        "bundle_version": "2026-05-06.preview-feedback.v1",
        "generated_at": "2026-05-06T00:00:00+00:00",
        "service": {"contract_version": "2026-04-30.preview.v1"},
        "environment": {"python_executable": sys.executable},
        "git": {"commit": "abc123", "branch": "main", "dirty": False},
        "runtime": {"runtime_root": str(tmp_path / "runtime")},
        "task": {"task_id": "demo", "status": "completed"},
        "artifacts": {"results": [str(tmp_path / "runtime" / "results" / "demo.json")]},
        "logs": [],
        "diagnostics": [],
    }

    output = write_feedback_bundle(bundle, tmp_path / "out")

    assert output["status"] == "written"
    json_path = Path(output["json_path"])
    markdown_path = Path(output["markdown_path"])
    assert json.loads(json_path.read_text(encoding="utf-8"))["bundle_version"] == (
        "2026-05-06.preview-feedback.v1"
    )
    markdown = markdown_path.read_text(encoding="utf-8")
    assert "ML Research Loop Preview Feedback Bundle" in markdown
    assert "2026-04-30.preview.v1" in markdown
    assert render_feedback_markdown(bundle) == markdown
