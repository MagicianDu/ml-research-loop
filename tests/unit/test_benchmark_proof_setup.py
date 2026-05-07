from __future__ import annotations

import json
from pathlib import Path

from lib.benchmarks import (
    build_official_proof_setup_bundle,
    build_public_proof_plan,
    render_official_proof_setup_markdown,
    write_official_proof_setup_bundle,
)


def _blocked_proof_plan() -> dict[str, object]:
    probe = {
        "status": "needs_setup",
        "read_only": True,
        "official_scores_claimed": False,
        "harnesses": [
            {
                "name": "mle_bench",
                "status": "needs_setup",
                "required_checks": [
                    {"id": "command:git-lfs", "status": "missing"},
                    {"id": "credentials:kaggle", "status": "missing"},
                ],
                "blocked_commands": ["mlebench prepare"],
            },
            {
                "name": "paperbench",
                "status": "needs_setup",
                "required_checks": [
                    {"id": "command:uv", "status": "missing"},
                    {"id": "credentials:paperbench_grader", "status": "missing"},
                ],
                "blocked_commands": ["uv sync"],
            },
        ],
    }
    return build_public_proof_plan(probe)


def test_official_proof_setup_bundle_is_read_only_and_redacted() -> None:
    bundle = build_official_proof_setup_bundle(_blocked_proof_plan())

    assert bundle["status"] == "blocked"
    assert bundle["read_only"] is True
    assert bundle["official_scores_claimed"] is False
    assert bundle["recommended_environment"] == "external_evaluation_environment"
    assert bundle["environment_template"] == {
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
    assert [section["name"] for section in bundle["setup_sections"]] == [
        "mle_bench",
        "paperbench",
    ]
    assert "$ML_RESEARCH_LOOP_REPO/scripts/benchmark_harness_probe.py" in json.dumps(
        bundle["setup_sections"],
        ensure_ascii=False,
    )
    assert "official_scores_claimed=false" in bundle["artifact_manifest_template"]
    serialized = json.dumps(bundle, ensure_ascii=False)
    assert "sk-" not in serialized
    assert "ghp_" not in serialized
    assert "KAGGLE_KEY=secret" not in serialized


def test_official_proof_setup_markdown_warns_against_score_claims() -> None:
    bundle = build_official_proof_setup_bundle(_blocked_proof_plan())

    markdown = render_official_proof_setup_markdown(bundle)

    assert "Official Proof Run Setup Bundle" in markdown
    assert "not an official score report" in markdown
    assert "MLE-bench" in markdown
    assert "PaperBench" in markdown
    assert "official_scores_claimed=false" in markdown


def test_write_official_proof_setup_bundle_writes_three_files(tmp_path: Path) -> None:
    bundle = build_official_proof_setup_bundle(_blocked_proof_plan())

    output = write_official_proof_setup_bundle(bundle, tmp_path / "proof-setup")

    assert output["status"] == "written"
    assert Path(output["json_path"]).exists()
    assert Path(output["markdown_path"]).exists()
    assert Path(output["env_example_path"]).exists()
    assert json.loads(Path(output["json_path"]).read_text(encoding="utf-8"))["read_only"] is True
    env_text = Path(output["env_example_path"]).read_text(encoding="utf-8")
    assert "ML_RESEARCH_LOOP_REPO=" in env_text
    assert "KAGGLE_KEY=" in env_text
    assert "OPENAI_API_KEY=" in env_text
    assert "sk-" not in env_text
