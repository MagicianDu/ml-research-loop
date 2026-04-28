"""Helpers for final task result summaries."""

from __future__ import annotations

from collections.abc import Sequence


def build_result_summary(experiments: Sequence[dict], total_duration_minutes: float) -> dict:
    """Build a stable summary payload for result files and adapters."""
    total_count = len(experiments)
    accepted_count = sum(1 for exp in experiments if exp.get("accepted"))
    rounded_duration = round(total_duration_minutes, 1)

    return {
        "total_experiments": total_count,
        "accepted": accepted_count,
        "rejected": sum(1 for exp in experiments if not exp.get("accepted")),
        "failed": sum(1 for exp in experiments if exp.get("error")),
        "total_duration_minutes": rounded_duration,
        "total_wall_clock_minutes": rounded_duration,
        "success_rate": round(accepted_count / max(total_count, 1), 3),
    }
