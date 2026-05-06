"""Read-only setup bundle for official benchmark proof runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


SETUP_BUNDLE_VERSION = "2026-05-06.official-proof-setup.v1"


def build_official_proof_setup_bundle(proof_plan: dict[str, Any]) -> dict[str, Any]:
    """Return a setup-only bundle for preparing an external benchmark environment."""
    return {
        "bundle_version": SETUP_BUNDLE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": _bundle_status(proof_plan),
        "read_only": True,
        "official_scores_claimed": False,
        "recommended_environment": proof_plan.get(
            "recommended_environment",
            "external_evaluation_environment",
        ),
        "proof_plan": proof_plan,
        "references": _references(),
        "environment_template": _environment_template(),
        "setup_sections": _setup_sections(),
        "artifact_manifest_template": _artifact_manifest_template(),
        "write_targets": [
            "official-proof-setup.json",
            "official-proof-setup.md",
            "official-proof.env.example",
        ],
    }


def write_official_proof_setup_bundle(
    bundle: dict[str, Any],
    output_dir: Path,
) -> dict[str, Any]:
    """Write setup bundle JSON, markdown, and env example files."""
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "official-proof-setup.json"
    markdown_path = output_dir / "official-proof-setup.md"
    env_example_path = output_dir / "official-proof.env.example"

    json_path.write_text(
        json.dumps(bundle, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(render_official_proof_setup_markdown(bundle), encoding="utf-8")
    env_example_path.write_text(_render_env_example(bundle), encoding="utf-8")
    return {
        "status": "written",
        "json_path": str(json_path),
        "markdown_path": str(markdown_path),
        "env_example_path": str(env_example_path),
        "bundle": {
            "status": bundle.get("status"),
            "read_only": bundle.get("read_only"),
            "official_scores_claimed": bundle.get("official_scores_claimed"),
            "recommended_environment": bundle.get("recommended_environment"),
        },
    }


def render_official_proof_setup_markdown(bundle: dict[str, Any]) -> str:
    """Render a human-readable setup bundle."""
    lines = [
        "# Official Proof Run Setup Bundle",
        "",
        "This is a setup plan, not an official score report.",
        "",
        f"- bundle_version: `{bundle.get('bundle_version')}`",
        f"- status: `{bundle.get('status')}`",
        f"- recommended_environment: `{bundle.get('recommended_environment')}`",
        "- official_scores_claimed=false",
        "",
        "## Environment Template",
        "",
    ]
    for name in bundle.get("environment_template", {}):
        lines.append(f"- `{name}`")
    lines.extend(["", "## Setup Sections", ""])
    for section in bundle.get("setup_sections", []):
        lines.extend([
            f"### {section['display_name']}",
            "",
            f"- reference: {section['reference_url']}",
            "",
            "Commands to run manually in the external evaluation environment:",
            "",
            "```bash",
            *section["manual_commands"],
            "```",
            "",
        ])
    lines.extend(["## Artifact Manifest Template", ""])
    for item in bundle.get("artifact_manifest_template", []):
        lines.append(f"- `{item}`")
    return "\n".join(lines).rstrip() + "\n"


def _bundle_status(proof_plan: dict[str, Any]) -> str:
    if proof_plan.get("status") == "ready_for_debug_run":
        return "ready_for_environment_setup"
    return "blocked"


def _references() -> list[dict[str, str]]:
    return [
        {
            "name": "mle_bench",
            "title": "OpenAI MLE-bench",
            "url": "https://github.com/openai/mle-bench",
        },
        {
            "name": "paperbench",
            "title": "OpenAI PaperBench",
            "url": "https://github.com/openai/frontier-evals/tree/main/project/paperbench",
        },
    ]


def _environment_template() -> dict[str, str]:
    return {
        "ML_RESEARCH_LOOP_REPO": "",
        "MLE_BENCH_REPO": "",
        "PAPERBENCH_REPO": "",
        "PAPERBENCH_DATA_DIR": "",
        "KAGGLE_USERNAME": "",
        "KAGGLE_KEY": "",
        "OPENAI_API_KEY": "",
        "GRADER_OPENAI_API_KEY": "",
        "HF_TOKEN": "",
    }


def _setup_sections() -> list[dict[str, Any]]:
    return [_mle_bench_setup_section(), _paperbench_setup_section()]


def _mle_bench_setup_section() -> dict[str, Any]:
    return {
        "name": "mle_bench",
        "display_name": "MLE-bench",
        "reference_url": "https://github.com/openai/mle-bench",
        "manual_commands": [
            "git clone https://github.com/openai/mle-bench.git",
            "cd mle-bench",
            "git lfs fetch --all",
            "git lfs pull",
            "python -m pip install -e .",
            "export MLE_BENCH_REPO=\"$(pwd)\"",
            "mlebench prepare --lite",
            "docker build --platform=linux/amd64 -t mlebench-env -f environment/Dockerfile .",
            "PYTHONPATH=\"$ML_RESEARCH_LOOP_REPO:$PYTHONPATH\" python \"$ML_RESEARCH_LOOP_REPO/scripts/benchmark_harness_probe.py\" --mle-bench-repo \"$MLE_BENCH_REPO\" --json",
            "PYTHONPATH=\"$ML_RESEARCH_LOOP_REPO:$PYTHONPATH\" python \"$ML_RESEARCH_LOOP_REPO/scripts/benchmark_proof_plan.py\" --mle-bench-repo \"$MLE_BENCH_REPO\" --json",
        ],
        "notes": [
            "Kaggle credentials are required by the official MLE-bench data path.",
            "Run official grading only after the proof plan reports ready_for_debug_run.",
        ],
    }


def _paperbench_setup_section() -> dict[str, Any]:
    return {
        "name": "paperbench",
        "display_name": "PaperBench",
        "reference_url": "https://github.com/openai/frontier-evals/tree/main/project/paperbench",
        "manual_commands": [
            "git clone https://github.com/openai/frontier-evals.git --filter=blob:none",
            "cd frontier-evals",
            "git lfs fetch --include \"project/paperbench/data/**\" --exclude \"\"",
            "git lfs checkout project/paperbench/data",
            "export PAPERBENCH_REPO=\"$(pwd)\"",
            "export PAPERBENCH_DATA_DIR=\"$(pwd)/project/paperbench/data\"",
            "cd project/paperbench",
            "uv sync",
            "cp ../../.env.example .env",
            "source .env",
            "bash paperbench/scripts/build-docker-images.sh",
            "uv run python -m paperbench.nano.entrypoint --help",
            "PYTHONPATH=\"$ML_RESEARCH_LOOP_REPO:$PYTHONPATH\" python \"$ML_RESEARCH_LOOP_REPO/scripts/benchmark_harness_probe.py\" --paperbench-repo \"$PAPERBENCH_REPO\" --paperbench-data-dir \"$PAPERBENCH_DATA_DIR\" --json",
            "PYTHONPATH=\"$ML_RESEARCH_LOOP_REPO:$PYTHONPATH\" python \"$ML_RESEARCH_LOOP_REPO/scripts/benchmark_proof_plan.py\" --paperbench-repo \"$PAPERBENCH_REPO\" --paperbench-data-dir \"$PAPERBENCH_DATA_DIR\" --json",
        ],
        "notes": [
            "Fill .env manually; this bundle never writes secret values.",
            "Use the debug split and dummy judge before any costly grading path.",
        ],
    }


def _artifact_manifest_template() -> list[str]:
    return [
        "command_lines",
        "resolved_config",
        "environment_manifest",
        "dependency_versions",
        "raw_logs",
        "raw_reports",
        "limitations_note",
        "official_scores_claimed=false",
    ]


def _render_env_example(bundle: dict[str, Any]) -> str:
    lines = [
        "# ML Research Loop official proof-run environment template",
        "# Fill values in the external evaluation environment. Do not commit secrets.",
        "",
    ]
    for name, value in bundle.get("environment_template", {}).items():
        lines.append(f"{name}={value}")
    return "\n".join(lines).rstrip() + "\n"
