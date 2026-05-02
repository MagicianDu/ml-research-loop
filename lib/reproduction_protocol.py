"""Lightweight reproduction and rubric helpers inspired by PaperBench."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True)
class RubricTask:
    """A weighted rubric node for local reproduction grading."""

    id: str
    requirements: str
    weight: float
    sub_tasks: list["RubricTask"] = field(default_factory=list)
    task_category: str | None = None
    finegrained_task_category: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RubricTask":
        return cls(
            id=str(data["id"]),
            requirements=str(data["requirements"]),
            weight=float(data["weight"]),
            sub_tasks=[
                cls.from_dict(item)
                for item in data.get("sub_tasks", [])
                if isinstance(item, dict)
            ],
            task_category=(
                str(data["task_category"])
                if data.get("task_category") is not None
                else None
            ),
            finegrained_task_category=(
                str(data["finegrained_task_category"])
                if data.get("finegrained_task_category") is not None
                else None
            ),
        )

    def leaf_nodes(self) -> list["RubricTask"]:
        if not self.sub_tasks:
            return [self]
        return [leaf for task in self.sub_tasks for leaf in task.leaf_nodes()]

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["sub_tasks"] = [task.to_dict() for task in self.sub_tasks]
        return data


@dataclass(frozen=True)
class ReproductionSpec:
    """A deterministic local reproduction command specification."""

    mode: str
    command: list[str]
    timeout_seconds: int
    required_files: list[str] = field(default_factory=lambda: ["train.py"])

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ReproductionSpec":
        return cls(
            mode=str(data["mode"]),
            command=[str(item) for item in data["command"]],
            timeout_seconds=int(data["timeout_seconds"]),
            required_files=[
                str(item)
                for item in data.get("required_files", ["train.py"])
            ],
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_grade_report(
    rubric: RubricTask,
    leaf_scores: dict[str, float],
    grader_log: str,
) -> dict[str, Any]:
    """Aggregate weighted leaf scores into a compact grade report."""
    leaves = rubric.leaf_nodes()
    total_weight = sum(max(leaf.weight, 0.0) for leaf in leaves)
    weighted_score = 0.0
    invalid_count = 0
    graded_nodes: list[dict[str, Any]] = []

    for leaf in leaves:
        raw_score = leaf_scores.get(leaf.id)
        if raw_score is None or raw_score < 0 or raw_score > 1:
            score = 0.0
            invalid_count += 1
        else:
            score = float(raw_score)
        weighted_score += max(leaf.weight, 0.0) * score
        graded_nodes.append({**leaf.to_dict(), "score": score})

    return {
        "score": weighted_score / total_weight if total_weight else 0.0,
        "num_leaf_nodes": len(leaves),
        "num_invalid_leaf_nodes": invalid_count,
        "graded_task_tree": {
            **rubric.to_dict(),
            "graded_leaf_nodes": graded_nodes,
        },
        "grader_log": grader_log,
    }
