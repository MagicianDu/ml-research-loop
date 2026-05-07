"""Benchmark adapter readiness metadata."""

from __future__ import annotations

from typing import Any


def build_benchmark_readiness() -> dict[str, Any]:
    """Return public benchmark adapter readiness for CLI and MCP clients."""
    return {
        "status": "compatibility_ready",
        "official_scores_claimed": False,
        "adapters": [
            {
                "name": "mle_bench",
                "display_name": "MLE-bench compatibility adapter",
                "status": "local_fixture_ready",
                "official": False,
                "script": "scripts/mle_bench_adapter_demo.py",
                "demo_command": [
                    "python",
                    "scripts/mle_bench_adapter_demo.py",
                    "--runtime-root",
                    "<runtime-root>",
                    "--json",
                ],
                "artifact_fields": [
                    "competition_id",
                    "run_group",
                    "submission_path",
                    "metadata_path",
                    "benchmark_report_path",
                    "best_metric",
                ],
                "next_step": "Replace the deterministic fixture with official competition hydration and grading.",
            },
            {
                "name": "paperbench",
                "display_name": "PaperBench compatibility adapter",
                "status": "local_fixture_ready",
                "official": False,
                "script": "scripts/paperbench_adapter_demo.py",
                "demo_command": [
                    "python",
                    "scripts/paperbench_adapter_demo.py",
                    "--runtime-root",
                    "<runtime-root>",
                    "--json",
                ],
                "artifact_fields": [
                    "paper_id",
                    "submission_dir",
                    "reproduction_report_path",
                    "grade_report_path",
                    "benchmark_report_path",
                    "grading.score",
                    "grading.rubric_leaf_results",
                ],
                "next_step": "Probe official paper samples, direct submission grading, and evaluator requirements.",
            },
        ],
        "combined_smoke": {
            "script": "scripts/benchmark_adapter_smoke.py",
            "command": [
                "python",
                "scripts/benchmark_adapter_smoke.py",
                "--runtime-root",
                "<runtime-root>",
                "--json",
            ],
        },
        "next_milestones": [
            "P13 combined compatibility smoke",
            "P14 official harness feasibility probes",
            "P15 public proof run",
        ],
    }
