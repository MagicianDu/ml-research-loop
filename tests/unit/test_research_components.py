from lib.llm_providers import MockLLMProvider
from lib.research_components import AnalyzeResult, ChangeExecutor, ChangeProposal, ChangeProposer


def test_change_executor_replaces_existing_search_region_value(tmp_path):
    train_py = tmp_path / "train.py"
    train_py.write_text(
        "OUTSIDE = 1\n"
        "# ======= AUTORESEARCH SEARCH REGION START =======\n"
        "DEPTH = 4\n"
        "# ======= AUTORESEARCH SEARCH REGION END =======\n",
        encoding="utf-8",
    )
    executor = ChangeExecutor(tmp_path)

    result = executor.execute(
        ChangeProposal(
            change_type="hyperparam",
            target="DEPTH",
            current_value="4",
            proposed_value="8",
            reason="test",
        )
    )

    content = train_py.read_text(encoding="utf-8")
    assert result.success is True
    assert "DEPTH = 8" in content
    assert "OUTSIDE = 1" in content


def test_change_executor_rejects_unknown_non_hyperparam_type(tmp_path):
    train_py = tmp_path / "train.py"
    train_py.write_text(
        "# ======= AUTORESEARCH SEARCH REGION START =======\n"
        "DEPTH = 4\n"
        "# ======= AUTORESEARCH SEARCH REGION END =======\n",
        encoding="utf-8",
    )
    executor = ChangeExecutor(tmp_path)

    result = executor.execute(
        ChangeProposal(
            change_type="architecture",
            target="NEW_LAYER",
            current_value="none",
            proposed_value="enabled",
            reason="test",
        )
    )

    assert result.success is False
    assert "Unsupported change_type" in result.error


def test_change_proposer_prompt_uses_metric_context():
    provider = MockLLMProvider(
        {
            "change_type": "hyperparam",
            "target": "DEPTH",
            "current_value": "4",
            "proposed_value": "8",
            "reason": "test",
            "confidence": 0.8,
        }
    )
    proposer = ChangeProposer(
        provider,
        metric_name="val_accuracy",
        metric_direction="maximize",
    )

    proposer.propose(AnalyzeResult("code", "history", "trend"))

    assert "val_accuracy" in provider.last_prompt
    assert "maximize" in provider.last_prompt
