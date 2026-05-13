"""Planning helpers for full-paper reproduction and improvement tracks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import json
from pathlib import Path
from typing import Any


DEFAULT_MAX_RUNTIME_MINUTES = 90
BLOCKED_FULL_REPRODUCTION_CLAIMS = [
    "full_paper_all_tables",
    "official_benchmark_or_sota",
    "unattended_research_replacement",
]


@dataclass(frozen=True)
class FullReproductionCandidate:
    """A candidate paper before it becomes a full-reproduction track."""

    paper_id: str
    title: str
    paper_url: str
    code_url: str
    task: str
    primary_metric: str
    dataset_track: str
    baseline_command: str
    evaluation_command: str
    resource_profile: str
    expected_runtime_minutes: int
    target_claim: str
    improvement_objective: str
    blockers: list[str]
    official_scores_claimed: bool = False


@dataclass(frozen=True)
class FullReproductionTargetSpec:
    """Machine-readable target spec for a full-reproduction track."""

    schema_version: str
    decision: str
    paper_id: str
    title: str
    paper_url: str
    code_url: str
    track_scope: str
    task: str
    primary_metric: str
    dataset_track: str
    baseline_command: str
    evaluation_command: str
    resource_profile: str
    expected_runtime_minutes: int
    target_claim: str
    improvement_objective: str
    baseline_required: bool
    improvement_required: bool
    required_artifacts: list[str]
    blockers: list[str]
    blocked_claims: list[str]
    official_scores_claimed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def evaluate_full_reproduction_candidate(
    candidate: FullReproductionCandidate,
    *,
    max_runtime_minutes: int = DEFAULT_MAX_RUNTIME_MINUTES,
) -> FullReproductionTargetSpec:
    """Turn a paper candidate into an accepted/deferred full-reproduction target."""
    blockers = list(candidate.blockers)
    if candidate.official_scores_claimed:
        blockers.append("official_scores_claimed_not_allowed")
    if candidate.expected_runtime_minutes > max_runtime_minutes:
        blockers.append("runtime_budget_exceeds_default_limit")

    if "requires_gpu" in blockers or "requires_legacy_python36_stack" in blockers:
        decision = "deferred_needs_gpu_or_legacy_stack"
    elif blockers:
        decision = "blocked_until_repaired"
    else:
        decision = "accepted_for_full_reproduction_track"

    return FullReproductionTargetSpec(
        schema_version="2026-05-13.full-reproduction-target.v1",
        decision=decision,
        paper_id=candidate.paper_id,
        title=candidate.title,
        paper_url=candidate.paper_url,
        code_url=candidate.code_url,
        track_scope="core_experiment_track",
        task=candidate.task,
        primary_metric=candidate.primary_metric,
        dataset_track=candidate.dataset_track,
        baseline_command=candidate.baseline_command,
        evaluation_command=candidate.evaluation_command,
        resource_profile=candidate.resource_profile,
        expected_runtime_minutes=candidate.expected_runtime_minutes,
        target_claim=candidate.target_claim,
        improvement_objective=candidate.improvement_objective,
        baseline_required=True,
        improvement_required=True,
        required_artifacts=[
            "target-spec.json",
            "dataset-provenance.json",
            "baseline-report.json",
            "evaluation-report.json",
            "client-handoff.json",
            "patch-diff.patch",
            "improvement-report.json",
            "human-review-report.json",
            "proof-manifest.json",
        ],
        blockers=blockers,
        blocked_claims=list(BLOCKED_FULL_REPRODUCTION_CLAIMS),
        official_scores_claimed=False,
    )


def write_full_reproduction_target(
    spec: FullReproductionTargetSpec,
    output_dir: Path,
) -> dict[str, Path]:
    """Write a target JSON and Chinese markdown target brief."""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "full-reproduction-target.json"
    markdown_path = output_dir / _markdown_file_name(spec)
    json_path.write_text(
        json.dumps(spec.to_dict(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    markdown_path.write_text(_render_target_markdown(spec), encoding="utf-8")
    return {
        "target_json": json_path,
        "target_markdown": markdown_path,
    }


def _markdown_file_name(spec: FullReproductionTargetSpec) -> str:
    if spec.paper_id == "arxiv:1607.01759":
        return "full-reproduction-fasttext-target-cn.md"
    return f"full-reproduction-{_slug(spec.paper_id)}-target-cn.md"


def _render_target_markdown(spec: FullReproductionTargetSpec) -> str:
    required_artifacts = "\n".join(f"- `{artifact}`" for artifact in spec.required_artifacts)
    blocked_claims = "\n".join(f"- `{claim}`" for claim in spec.blocked_claims)
    blockers = "\n".join(f"- `{blocker}`" for blocker in spec.blockers) or "- 无"
    return f"""# {spec.title} 完整复现目标

## 目标

本目标用于把 bounded pilot 升级为完整复现轨道。当前 decision 为 `{spec.decision}`，scope 为 `{spec.track_scope}`。

| 字段 | 内容 |
| --- | --- |
| 论文 | {spec.title} |
| 论文 ID | `{spec.paper_id}` |
| 论文链接 | {spec.paper_url} |
| 代码链接 | {spec.code_url} |
| 任务 | {spec.task} |
| 主指标 | `{spec.primary_metric}` |
| 数据轨道 | {spec.dataset_track} |
| baseline 命令 | `{spec.baseline_command}` |
| evaluation 命令 | `{spec.evaluation_command}` |
| 资源画像 | `{spec.resource_profile}` |
| 预计运行时间 | {spec.expected_runtime_minutes} 分钟 |

## 完整复现定义

本阶段的“完整复现”指复现论文的一个核心实验轨道：数据准备、baseline 训练、评测、结果归档和人工复核必须闭环。它不是一次性复现所有表格，也不是官方 leaderboard 成绩。

## 自动提升定义

在 baseline 可信之后，客户端模型可以提出 patch 或超参改动；MCP 负责执行、评测、记录 diff 和回滚。只有在 held-out/test 指标优于本地 baseline 时，才能写入 `improvement-report.json`。

## 必需 artifact

{required_artifacts}

## 当前 blockers

{blockers}

## 不能宣称

{blocked_claims}

所有输出必须保留 `official_scores_claimed=false`，除非后续真实跑过官方 scorer 或论文官方复现脚本并归档完整证据。
"""


def _slug(value: str) -> str:
    return (
        value.lower()
        .replace(":", "-")
        .replace(".", "-")
        .replace("/", "-")
    )
