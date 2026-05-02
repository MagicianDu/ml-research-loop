from __future__ import annotations

import json
from types import SimpleNamespace

from lib.llm_providers import MiniMaxProvider, MockLLMProvider, OpenAIProvider
from scripts.ai_autoresearch_run import build_llm_provider


def test_build_llm_provider_defaults_to_mock_when_requested() -> None:
    provider = build_llm_provider(
        SimpleNamespace(
            mock=True,
            mock_response='{"change_type": "hyperparam", "target": "DEPTH"}',
            llm_provider="mock",
            llm_model=None,
        )
    )

    assert isinstance(provider, MockLLMProvider)
    payload = json.loads(provider.generate("prompt"))
    assert payload["target"] == "DEPTH"


def test_build_llm_provider_supports_openai_without_api_call() -> None:
    provider = build_llm_provider(
        SimpleNamespace(
            mock=False,
            mock_response=None,
            llm_provider="openai",
            llm_model="gpt-5.5",
        )
    )

    assert isinstance(provider, OpenAIProvider)
    assert provider.model == "gpt-5.5"


def test_build_llm_provider_supports_minimax_without_api_call() -> None:
    provider = build_llm_provider(
        SimpleNamespace(
            mock=False,
            mock_response=None,
            llm_provider="minimax",
            llm_model="MiniMax-M2.7",
        )
    )

    assert isinstance(provider, MiniMaxProvider)
    assert provider.model == "MiniMax-M2.7"
