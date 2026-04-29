from __future__ import annotations

from lib.metrics import select_metric_value


def test_select_metric_value_returns_requested_metric() -> None:
    assert select_metric_value({"val_bpb": 1.23, "actual_duration_seconds": 0.4}, "val_bpb") == 1.23


def test_select_metric_value_does_not_fallback_to_duration() -> None:
    assert select_metric_value({"actual_duration_seconds": 0.4}, "val_bpb") is None
