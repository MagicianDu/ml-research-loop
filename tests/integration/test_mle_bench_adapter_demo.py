from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_mle_bench_adapter_demo_writes_benchmark_shaped_artifacts(tmp_path: Path) -> None:
    env = {
        **os.environ,
        "PYTHONPATH": (
            f"{PROJECT_ROOT}{os.pathsep}"
            f"{PROJECT_ROOT / '.venv' / 'lib' / 'python3.13' / 'site-packages'}"
        ),
        "ML_RESEARCH_LOOP_PYTHON": sys.executable,
    }

    proc = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "mle_bench_adapter_demo.py"),
            "--runtime-root",
            str(tmp_path / "runtime"),
            "--json",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=120,
    )

    assert proc.returncode == 0, proc.stdout
    payload = json.loads(proc.stdout.splitlines()[-1])

    assert payload["status"] == "completed"
    assert payload["competition_id"] == "mlrl-byte-lm"
    assert payload["official_mle_bench"] is False
    assert payload["best_metric"]["name"] == "val_bpb"
    assert payload["best_metric"]["value"] is not None
    assert Path(payload["submission_path"]).exists()
    assert Path(payload["metadata_path"]).exists()
    assert Path(payload["benchmark_report_path"]).exists()

    report = json.loads(Path(payload["benchmark_report_path"]).read_text(encoding="utf-8"))
    metadata = json.loads(Path(payload["metadata_path"]).read_text(encoding="utf-8"))
    with Path(payload["submission_path"]).open(newline="", encoding="utf-8") as handle:
        header = next(csv.reader(handle))

    assert report["official_mle_bench"] is False
    assert report["best_metric"]["value"] == payload["best_metric"]["value"]
    assert metadata["official_mle_bench"] is False
    assert metadata["result_file"] == payload["result_file"]
    assert header == ["competition_id", "val_bpb"]
