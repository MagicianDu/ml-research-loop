from lib.experiment_tree import ExperimentTree, build_experiment_tree


def test_build_experiment_tree_selects_best_minimize_node() -> None:
    experiments = [
        {"experiment_id": "exp-001", "metric": 1.20, "params": {"lr": 0.001}, "accepted": True},
        {"experiment_id": "exp-002", "metric": 0.95, "params": {"lr": 0.0005}, "accepted": True},
        {"experiment_id": "exp-003", "error_type": "training_timeout", "accepted": False},
    ]

    tree = build_experiment_tree(
        experiments=experiments,
        metric_name="val_bpb",
        metric_direction="minimize",
    )

    assert isinstance(tree, ExperimentTree)
    assert tree.best_node_id == "exp-002"
    assert tree.nodes["exp-001"].stage == "draft"
    assert tree.nodes["exp-002"].stage == "improve"
    assert tree.nodes["exp-003"].stage == "debug"
    assert tree.recommended_next_action["mode"] == "debug_failures"
    assert tree.recommended_next_action["target_node_id"] == "exp-003"


def test_build_experiment_tree_uses_metric_name_and_maximize_direction() -> None:
    experiments = [
        {"experiment_id": "exp-001", "metrics": {"accuracy": 0.81}, "accepted": True},
        {"experiment_id": "exp-002", "metrics": {"accuracy": 0.87}, "accepted": True},
    ]

    tree = build_experiment_tree(
        experiments=experiments,
        metric_name="accuracy",
        metric_direction="maximize",
    )

    assert tree.best_node_id == "exp-002"
    assert tree.nodes["exp-002"].parent_id == "exp-001"
    assert tree.recommended_next_action == {
        "mode": "improve_best",
        "target_node_id": "exp-002",
    }
