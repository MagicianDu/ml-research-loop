"""
Metrics — extensible metric computation.
Register new metrics via @register_metric decorator.
"""

from __future__ import annotations

from typing import Callable, Dict


METRIC_FUNCTIONS: Dict[str, Callable[..., float]] = {}


def register_metric(name: str):
    """Decorator: register a new metric function."""
    def decorator(fn: Callable[..., float]) -> Callable[..., float]:
        METRIC_FUNCTIONS[name] = fn
        return fn
    return decorator


def validate_metric_name(name: str) -> bool:
    """Check if metric is registered."""
    return name in METRIC_FUNCTIONS


def get_metric_fn(name: str) -> Callable[..., float]:
    """Get metric function by name. Raises ValueError if not found."""
    if name not in METRIC_FUNCTIONS:
        available = ", ".join(sorted(METRIC_FUNCTIONS.keys()))
        raise ValueError(
            f"Unknown metric: {name!r}. Available: {available}. "
            "Use @register_metric to add new metrics."
        )
    return METRIC_FUNCTIONS[name]


# ─── Built-in metrics (require real model/data) ──────────────────────────────

@register_metric("val_bpb")
def compute_val_bpb(model, val_loader) -> float:
    """Bits-per-byte for language models."""
    raise NotImplementedError("val_bpb requires model + val_loader")


@register_metric("val_loss")
def compute_val_loss(model, val_loader) -> float:
    """Cross-entropy validation loss."""
    raise NotImplementedError("val_loss requires model + val_loader")


@register_metric("val_accuracy")
def compute_val_accuracy(model, val_loader) -> float:
    """Validation accuracy."""
    raise NotImplementedError("val_accuracy requires model + val_loader")


@register_metric("val_perplexity")
def compute_val_perplexity(model, val_loader) -> float:
    """Validation perplexity."""
    raise NotImplementedError("val_perplexity requires model + val_loader")
