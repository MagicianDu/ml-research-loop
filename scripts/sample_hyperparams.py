"""
sample_hyperparams — sample hyperparameters from search space definitions.
"""

from __future__ import annotations

import random
from typing import Dict

from lib.task_protocol import HyperparamSpace


def sample_hyperparameters(space: Dict[str, HyperparamSpace]) -> Dict[str, any]:
    """
    Sample one configuration from the hyperparameter search space.

    Supported space types:
        - "uniform": uniform float in [min, max]
        - "log_uniform": log-uniform float in [min, max]
        - "choice": random choice from values list
        - "q_uniform": quantized uniform float (round(mid * q) / q)
        - "q_log_uniform": quantized log-uniform float
    """
    params = {}
    for name, spec in space.items():
        if spec.type == "uniform":
            params[name] = random.uniform(spec.min, spec.max)
        elif spec.type == "log_uniform":
            import math
            log_min = math.log(spec.min)
            log_max = math.log(spec.max)
            params[name] = math.exp(random.uniform(log_min, log_max))
        elif spec.type == "choice":
            params[name] = random.choice(spec.values)
        elif spec.type == "q_uniform":
            mid = (spec.min + spec.max) / 2.0
            q = spec.q or 1.0
            params[name] = round(mid / q) * q
        elif spec.type == "q_log_uniform":
            import math
            log_min = math.log(spec.min)
            log_max = math.log(spec.max)
            q = spec.q or 1.0
            val = math.exp(random.uniform(log_min, log_max))
            params[name] = round(val / q) * q
        else:
            raise ValueError(f"Unknown hyperparameter type: {spec.type!r}")
    return params
