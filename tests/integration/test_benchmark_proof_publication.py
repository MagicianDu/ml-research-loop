from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_benchmark_proof_publication_script_writes_publication_bundle(tmp_path: Path) -> None:
    artifact_root = tmp_path / "artifacts"
    artifact_paths = {
        "command_lines": "commands.txt",
        "resolved_config": "config.json",
        "environment_manifest": "environment.json",
        "raw_logs": "logs/run.log",
        "raw_reports": "reports/report.json",
        "limitations_note": "LIMITATIONS.md",
    }
    for relative in artifact_paths.values():
        path = artifact_root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"{relative}\n", encoding="utf-8")
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(
        json.dumps({
            "benchmark_name": "mle_bench",
            "run_mode": "official_debug",
            "official_scores_claimed": False,
            "limitations": ["debug proof only"],
            "artifacts": artifact_paths,
        }),
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "PYTHONPATH": (
            f"{PROJECT_ROOT}{os.pathsep}"
            f"{PROJECT_ROOT / '.venv' / 'lib' / 'python3.13' / 'site-packages'}"
        ),
    }

    proc = subprocess.run(
        [
            sys.executable,
            str(PROJECT_ROOT / "scripts" / "benchmark_proof_publication.py"),
            "--manifest",
            str(manifest_path),
            "--artifact-root",
            str(artifact_root),
            "--output-dir",
            str(tmp_path / "publication"),
            "--json",
        ],
        cwd=PROJECT_ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        timeout=30,
    )

    assert proc.returncode == 0, proc.stdout
    payload = json.loads(proc.stdout.splitlines()[-1])
    assert payload["status"] == "written"
    assert Path(payload["json_path"]).exists()
    bundle = json.loads(Path(payload["json_path"]).read_text(encoding="utf-8"))
    assert bundle["status"] == "publishable_with_limitations"
    assert bundle["official_scores_claimed"] is False
