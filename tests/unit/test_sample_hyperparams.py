"""Tests for sample_hyperparams.py."""


from scripts.sample_hyperparams import sample_hyperparameters
from lib.task_protocol import HyperparamSpace


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
