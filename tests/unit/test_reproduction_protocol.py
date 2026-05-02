from lib.reproduction_protocol import (
    ReproductionSpec,
    RubricTask,
    build_grade_report,
)


def test_grade_report_aggregates_weighted_leaf_scores() -> None:
    rubric = RubricTask(
        id="root",
        requirements="Reproduce the target result",
        weight=1,
        sub_tasks=[
            RubricTask(
                id="code",
                requirements="Implementation exists",
                weight=2,
                task_category="Code Development",
            ),
            RubricTask(
                id="run",
                requirements="Reproduction script runs",
                weight=1,
                task_category="Code Execution",
            ),
        ],
    )

    report = build_grade_report(
        rubric=rubric,
        leaf_scores={"code": 1.0, "run": 0.0},
        grader_log="code exists, run script missing",
    )

    assert report["score"] == 2 / 3
    assert report["num_leaf_nodes"] == 2
    assert report["num_invalid_leaf_nodes"] == 0
    assert [node["id"] for node in report["graded_task_tree"]["graded_leaf_nodes"]] == [
        "code",
        "run",
    ]


def test_reproduction_spec_defaults_required_files() -> None:
    spec = ReproductionSpec(
        mode="local_command",
        command=["python", "train.py"],
        timeout_seconds=60,
    )

    assert spec.to_dict() == {
        "mode": "local_command",
        "command": ["python", "train.py"],
        "timeout_seconds": 60,
        "required_files": ["train.py"],
    }
