import json
import subprocess
import sys

from lib.full_reproduction import (
    FullReproductionCandidate,
    evaluate_full_reproduction_candidate,
    write_full_reproduction_target,
)


def test_fasttext_candidate_is_accepted_for_full_reproduction_track(tmp_path) -> None:
    candidate = FullReproductionCandidate(
        paper_id="arxiv:1607.01759",
        title="Bag of Tricks for Efficient Text Classification",
        paper_url="https://arxiv.org/abs/1607.01759",
        code_url="https://github.com/facebookresearch/fastText",
        task="supervised text classification",
        primary_metric="accuracy",
        dataset_track="AG News or equivalent public text classification dataset",
        baseline_command="fasttext supervised -input train.txt -output model",
        evaluation_command="fasttext test model.bin test.txt",
        resource_profile="cpu_standard_hardware",
        expected_runtime_minutes=30,
        target_claim="fastText-style supervised classifier reproduces a core text classification track",
        improvement_objective="improve local held-out accuracy over the reproduced baseline",
        blockers=[],
        official_scores_claimed=False,
    )

    spec = evaluate_full_reproduction_candidate(candidate)

    assert spec.decision == "accepted_for_full_reproduction_track"
    assert spec.paper_id == "arxiv:1607.01759"
    assert spec.track_scope == "core_experiment_track"
    assert spec.baseline_required is True
    assert spec.improvement_required is True
    assert spec.official_scores_claimed is False
    assert "full_paper_all_tables" in spec.blocked_claims
    assert "official_benchmark_or_sota" in spec.blocked_claims
    assert "baseline-report.json" in spec.required_artifacts
    assert "improvement-report.json" in spec.required_artifacts

    written = write_full_reproduction_target(spec, tmp_path)
    json_payload = json.loads(written["target_json"].read_text(encoding="utf-8"))
    markdown = written["target_markdown"].read_text(encoding="utf-8")

    assert json_payload["decision"] == "accepted_for_full_reproduction_track"
    assert json_payload["paper_id"] == "arxiv:1607.01759"
    assert "完整复现目标" in markdown
    assert "不能宣称" in markdown
    assert "official_scores_claimed=false" in markdown


def test_mixup_candidate_is_deferred_for_gpu_and_legacy_stack() -> None:
    candidate = FullReproductionCandidate(
        paper_id="arxiv:1710.09412",
        title="mixup: Beyond Empirical Risk Minimization",
        paper_url="https://arxiv.org/abs/1710.09412",
        code_url="https://github.com/facebookresearch/mixup-cifar10",
        task="CIFAR-10 image classification",
        primary_metric="top1_accuracy",
        dataset_track="CIFAR-10",
        baseline_command="python train.py --lr=0.1 --seed=20170922 --decay=1e-4",
        evaluation_command="python train.py test checkpoint",
        resource_profile="gpu_legacy_python_stack",
        expected_runtime_minutes=240,
        target_claim="mixup improves image classification generalization",
        improvement_objective="improve local validation accuracy over reproduced baseline",
        blockers=["requires_gpu", "requires_legacy_python36_stack"],
        official_scores_claimed=False,
    )

    spec = evaluate_full_reproduction_candidate(candidate)

    assert spec.decision == "deferred_needs_gpu_or_legacy_stack"
    assert "requires_gpu" in spec.blockers
    assert "requires_legacy_python36_stack" in spec.blockers
    assert spec.official_scores_claimed is False


def test_full_reproduction_target_cli_writes_fasttext_target(tmp_path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "scripts/full_reproduction_target.py",
            "--paper-id",
            "arxiv:1607.01759",
            "--output-dir",
            str(tmp_path),
            "--json",
        ],
        check=True,
        capture_output=True,
        text=True,
    )

    payload = json.loads(result.stdout)
    target_payload = json.loads((tmp_path / "full-reproduction-target.json").read_text())

    assert payload["status"] == "completed"
    assert payload["decision"] == "accepted_for_full_reproduction_track"
    assert payload["paper_id"] == "arxiv:1607.01759"
    assert payload["official_scores_claimed"] is False
    assert target_payload["improvement_required"] is True
    assert (tmp_path / "full-reproduction-fasttext-target-cn.md").exists()
