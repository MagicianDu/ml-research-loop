"""Tests for sample_hyperparams.py."""


from scripts.sample_hyperparams import sample_hyperparameters
from lib.task_protocol import HyperparamSpace


class SequenceRandom:
    def __init__(self, choices):
        self.choices = list(choices)
        self.index = 0

    def choice(self, values):
        if self.index < len(self.choices):
            value = self.choices[self.index]
            self.index += 1
            assert value in values
            return value
        return values[0]

    def uniform(self, min_value, max_value):
        del max_value
        return min_value


class TestSampleHyperparameters:
    def test_uniform(self):
        space = {"x": HyperparamSpace(type="uniform", min=0.0, max=1.0)}
        for _ in range(10):
            params = sample_hyperparameters(space)
            assert 0.0 <= params["x"] <= 1.0

    def test_log_uniform(self):
        space = {"lr": HyperparamSpace(type="log_uniform", min=1e-5, max=1e-1)}
        for _ in range(10):
            params = sample_hyperparameters(space)
            assert 1e-5 <= params["lr"] <= 1e-1

    def test_choice(self):
        space = {"depth": HyperparamSpace(type="choice", values=[4, 6, 8, 12])}
        valid_values = {4, 6, 8, 12}
        for _ in range(20):
            params = sample_hyperparameters(space)
            assert params["depth"] in valid_values

    def test_q_uniform(self):
        space = {"lr": HyperparamSpace(type="q_uniform", min=0.0, max=1.0, q=0.1)}
        for _ in range(10):
            params = sample_hyperparameters(space)
            # Should be rounded to nearest 0.1
            rounded = round(params["lr"] / 0.1) * 0.1
            assert abs(params["lr"] - rounded) < 1e-9

    def test_multiple_params(self):
        space = {
            "lr": HyperparamSpace(type="log_uniform", min=1e-5, max=1e-2),
            "depth": HyperparamSpace(type="choice", values=[4, 6, 8]),
            "dim": HyperparamSpace(type="uniform", min=128, max=512),
        }
        params = sample_hyperparameters(space)
        assert "lr" in params
        assert "depth" in params
        assert "dim" in params
        assert params["depth"] in {4, 6, 8}

    def test_history_aware_sampling_avoids_rejected_duplicate(self):
        space = {
            "depth": HyperparamSpace(type="choice", values=[1, 2]),
            "dim": HyperparamSpace(type="choice", values=[32]),
        }
        history = [
            {
                "params": {"depth": 1, "dim": 32},
                "accepted": False,
            }
        ]

        params = sample_hyperparameters(
            space,
            experiment_history=history,
            rng=SequenceRandom([1, 32, 2, 32]),
        )

        assert params == {"depth": 2, "dim": 32}
