from lib.result_summary import build_result_summary


def test_build_result_summary_contains_adapter_fields():
    experiments = [
        {"accepted": True, "error": None},
        {"accepted": False, "error": None},
        {"accepted": False, "error": "training failed"},
    ]

    summary = build_result_summary(experiments, total_duration_minutes=1.49)

    assert summary == {
        "total_experiments": 3,
        "accepted": 1,
        "rejected": 2,
        "failed": 1,
        "total_duration_minutes": 1.5,
        "total_wall_clock_minutes": 1.5,
        "success_rate": 0.333,
    }


def test_build_result_summary_handles_empty_experiments():
    summary = build_result_summary([], total_duration_minutes=0.0)

    assert summary["total_experiments"] == 0
    assert summary["success_rate"] == 0.0
