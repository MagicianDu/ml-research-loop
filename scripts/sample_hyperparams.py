"""
sample_hyperparams — sample hyperparameters from search space definitions.
"""

from __future__ import annotations

import math
import random
from collections.abc import Mapping
from typing import Any

from lib.task_protocol import HyperparamSpace


def sample_hyperparameters(
    space: dict[str, HyperparamSpace],
    experiment_history: list[dict[str, Any]] | None = None,
    rng: Any = None,
) -> dict[str, Any]:
    """
    Sample one configuration from the hyperparameter search space.

    Supported space types:
        - "uniform": uniform float in [min, max]
        - "log_uniform": log-uniform float in [min, max]
        - "choice": random choice from values list
        - "q_uniform": quantized uniform float (round(mid * q) / q)
        - "q_log_uniform": quantized log-uniform float
    """
    random_source = rng or random
    history = experiment_history or []
    if not history:
        return _sample_once(space, random_source)

    candidate_count = max(16, min(64, len(history) * 4))
    candidates = [_sample_once(space, random_source) for _ in range(candidate_count)]
    return max(candidates, key=lambda candidate: _candidate_score(candidate, history))


def _sample_once(space: dict[str, HyperparamSpace], rng: Any) -> dict[str, Any]:
    params = {}
    for name, spec in space.items():
        if spec.type == "uniform":
            params[name] = rng.uniform(spec.min, spec.max)
        elif spec.type == "log_uniform":
            log_min = math.log(spec.min)
            log_max = math.log(spec.max)
            params[name] = math.exp(rng.uniform(log_min, log_max))
        elif spec.type == "choice":
            params[name] = rng.choice(spec.values)
        elif spec.type == "q_uniform":
            mid = (spec.min + spec.max) / 2.0
            q = spec.q or 1.0
            params[name] = round(mid / q) * q
        elif spec.type == "q_log_uniform":
            log_min = math.log(spec.min)
            log_max = math.log(spec.max)
            q = spec.q or 1.0
            val = math.exp(rng.uniform(log_min, log_max))
            params[name] = round(val / q) * q
        else:
            raise ValueError(f"Unknown hyperparameter type: {spec.type!r}")
    return params


def _candidate_score(candidate: Mapping[str, Any], history: list[dict[str, Any]]) -> float:
    score = 0.0
    accepted_params = [
        record.get("params", {})
        for record in history
        if record.get("accepted") and isinstance(record.get("params"), dict)
    ]

    for record in history:
        params = record.get("params")
        if not isinstance(params, dict):
            continue
        if _same_params(candidate, params):
            score -= 1000.0
            if record.get("error"):
                score -= 100.0
            if not record.get("accepted"):
                score -= 100.0

    if accepted_params:
        score += max(_similarity(candidate, params) for params in accepted_params)

    return score


def _same_params(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    return dict(left) == dict(right)


def _similarity(candidate: Mapping[str, Any], baseline: Mapping[str, Any]) -> float:
    score = 0.0
    for key, value in candidate.items():
        if key not in baseline:
            continue
        baseline_value = baseline[key]
        if isinstance(value, (int, float)) and isinstance(baseline_value, (int, float)):
            distance = abs(float(value) - float(baseline_value))
            scale = max(abs(float(baseline_value)), 1.0)
            score += max(0.0, 1.0 - distance / scale)
        elif value == baseline_value:
            score += 0.5
    return score
