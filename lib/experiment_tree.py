"""Lightweight experiment-tree state for planner handoff."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal


Stage = Literal["draft", "improve", "debug"]


@dataclass
class ExperimentNode:
    """One experiment attempt represented as a node in a search tree."""

    node_id: str
    stage: Stage
    metric: float | None = None
    params: dict[str, Any] = field(default_factory=dict)
    accepted: bool = False
    parent_id: str | None = None
    error_type: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExperimentTree:
    """A compact AIDE-style search-tree summary built from existing experiments."""

    nodes: dict[str, ExperimentNode]
    root_ids: list[str]
    best_node_id: str | None
    recommended_next_action: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": {key: node.to_dict() for key, node in self.nodes.items()},
            "root_ids": self.root_ids,
            "best_node_id": self.best_node_id,
            "recommended_next_action": self.recommended_next_action,
        }


def build_experiment_tree(
    experiments: list[dict[str, Any]],
    metric_name: str,
    metric_direction: str,
) -> ExperimentTree:
    """Build tree state without changing the linear result artifact shape."""
    nodes: dict[str, ExperimentNode] = {}
    root_ids: list[str] = []
    best_node_id: str | None = None
    best_metric: float | None = None
    last_good_id: str | None = None
    last_metric_node_id: str | None = None
    lower_is_better = metric_direction == "minimize"

    for index, experiment in enumerate(experiments):
        node_id = str(experiment.get("experiment_id") or f"exp-{index + 1:03d}")
        metric = _metric_value(experiment, metric_name)
        error_type = _error_type(experiment)
        stage: Stage = _node_stage(has_prior_nodes=bool(nodes), error_type=error_type)
        parent_id = last_good_id if stage in {"improve", "debug"} else None
        if parent_id is None:
            root_ids.append(node_id)

        accepted = bool(experiment.get("accepted", metric is not None and not error_type))
        nodes[node_id] = ExperimentNode(
            node_id=node_id,
            stage=stage,
            metric=metric,
            params=dict(experiment.get("params") or {}),
            accepted=accepted,
            parent_id=parent_id,
            error_type=error_type,
        )

        if metric is not None and error_type is None:
            last_metric_node_id = node_id
            if _is_better(metric, best_metric, lower_is_better):
                best_metric = metric
                best_node_id = node_id
            last_good_id = node_id

    failures = [node for node in nodes.values() if node.error_type]
    return ExperimentTree(
        nodes=nodes,
        root_ids=root_ids,
        best_node_id=best_node_id,
        recommended_next_action=_recommended_next_action(
            failures=failures,
            best_node_id=best_node_id,
            last_metric_node_id=last_metric_node_id,
            metric_name=metric_name,
        ),
    )


def _metric_value(experiment: dict[str, Any], metric_name: str) -> float | None:
    value = experiment.get("metric")
    if value is None:
        metrics = experiment.get("metrics")
        if isinstance(metrics, dict):
            value = metrics.get(metric_name, metrics.get("val", metrics.get("val_bpb")))
    if isinstance(value, int | float):
        return float(value)
    return None


def _error_type(experiment: dict[str, Any]) -> str | None:
    value = experiment.get("error_type") or experiment.get("error")
    return str(value) if value else None


def _recommended_next_action(
    failures: list[ExperimentNode],
    best_node_id: str | None,
    last_metric_node_id: str | None,
    metric_name: str,
) -> dict[str, Any]:
    if failures:
        return {
            "mode": "debug_failures",
            "target_node_id": failures[-1].node_id,
            "reason_category": "experiment_failed",
            "reason": "Latest failed experiment should be debugged before sampling new parameters.",
            "stop_reason": (
                "Stop before sampling new parameters until the failure is reproduced or explained."
            ),
        }
    if best_node_id is None:
        return {
            "mode": "start_experiment",
            "target_node_id": None,
            "reason_category": "no_completed_experiment",
            "reason": "No successful experiment has produced a metric yet.",
            "stop_reason": "Stop after the first metric-bearing experiment is reviewed.",
        }
    if last_metric_node_id == best_node_id:
        return {
            "mode": "improve_best",
            "target_node_id": best_node_id,
            "reason_category": "metric_improved",
            "reason": f"Latest successful node is the current best {metric_name}.",
            "stop_reason": f"Stop when the next candidate does not improve {metric_name}.",
        }
    return {
        "mode": "revise_search_space",
        "target_node_id": best_node_id,
        "reason_category": "metric_not_improved",
        "reason": f"Latest successful node did not improve the current best {metric_name}.",
        "stop_reason": "Stop local refinement and revise the search space before continuing.",
    }


def _node_stage(has_prior_nodes: bool, error_type: str | None) -> Stage:
    if not has_prior_nodes:
        return "draft"
    if error_type:
        return "debug"
    return "improve"


def _is_better(
    metric: float,
    best_metric: float | None,
    lower_is_better: bool,
) -> bool:
    if best_metric is None:
        return True
    if lower_is_better:
        return metric < best_metric
    return metric > best_metric
