from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_mcp_provider_quality_benchmark_reports_cache_and_recovery(tmp_path: Path) -> None:
    env = {
        **os.environ,
        "PYTHONPATH": (
            f"{PROJECT_ROOT}{os.pathsep}"
            f"{PROJECT_ROOT / '.venv' / 'lib' / 'python3.13' / 'site-packages'}"
        ),
        "ML_RESEARCH_LOOP_ALLOWED_ROOTS": str(tmp_path / "mcp-runtime"),
    }

    proc = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "mcp_provider_quality_benchmark.py"),
            "--runtime-root",
            str(tmp_path / "mcp-runtime"),
        ],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=60,
    )

    assert proc.returncode == 0, proc.stdout
    payload = json.loads(proc.stdout.splitlines()[-1])

    assert payload["status"] == "completed"
    assert payload["mode"] == "fixture"
    assert [item["name"] for item in payload["benchmarks"]] == [
        "paper-heavy",
        "dataset-heavy",
    ]
    for benchmark in payload["benchmarks"]:
        assert benchmark["provider_counts"]["provider_count"] >= 1
        assert benchmark["cache"]["first_hit"] is False
        assert benchmark["cache"]["second_hit"] is True
        assert benchmark["retrieval_diagnostics"]["summary"]["used_cache"] is True
        assert benchmark["rate_limit_diagnostics"]["summary"]["rate_limited_backend_count"] == 1
        assert "wait_for_rate_limit_reset" in benchmark["recovery_hints"]
        assert benchmark["evidence_citations"]
        assert benchmark["source_rankings"][0]["provider"] in {"arxiv", "huggingface"}

