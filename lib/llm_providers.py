"""
LLM Provider abstraction for AI-driven autoresearch.
Supports MiniMax, OpenAI, and Mock providers for testing.
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from typing import Optional


class LLMProvider(ABC):
    """Abstract base class for LLM providers."""

    @abstractmethod
    def generate(self, prompt: str, system: str = "", max_tokens: int = 1024) -> str:
        """Generate text from LLM."""
        pass

    @property
    def name(self) -> str:
        return self.__class__.__name__


class MiniMaxProvider(LLMProvider):
    """
    MiniMax LLM provider using direct API calls.
    Set MINIMAX_API_KEY environment variable to use.
    """

    API_KEY: Optional[str] = os.environ.get("MINIMAX_API_KEY")
    API_URL: str = "https://api.minimax.chat/v1/text/chatcompletion_v2"
    MODEL: str = "MiniMax-M2.7"

    def __init__(self, model: str = "MiniMax-M2.7", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key or self.API_KEY
        self.call_count = 0

    def generate(self, prompt: str, system: str = "", max_tokens: int = 1024) -> str:
        """Call MiniMax API to generate text."""
        self.call_count += 1

        if not self.api_key:
            raise RuntimeError(
                "MINIMAX_API_KEY not set. Set environment variable or pass api_key."
            )

        import requests

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }

        resp = requests.post(self.API_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()

        data = resp.json()
        return data["choices"][0]["message"]["content"]

    @property
    def name(self) -> str:
        return f"MiniMaxProvider({self.model})"


class OpenAIProvider(LLMProvider):
    """
    OpenAI LLM provider using direct API calls.
    Set OPENAI_API_KEY environment variable to use.
    """

    API_KEY: Optional[str] = os.environ.get("OPENAI_API_KEY")
    API_URL: str = "https://api.openai.com/v1/chat/completions"
    MODEL: str = "gpt-4o"

    def __init__(self, model: str = "gpt-4o", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key or self.API_KEY
        self.call_count = 0

    def generate(self, prompt: str, system: str = "", max_tokens: int = 1024) -> str:
        """Call OpenAI API to generate text."""
        self.call_count += 1

        if not self.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY not set. Set environment variable or pass api_key."
            )

        import requests

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }

        resp = requests.post(self.API_URL, headers=headers, json=payload, timeout=60)
        resp.raise_for_status()

        data = resp.json()
        return data["choices"][0]["message"]["content"]

    @property
    def name(self) -> str:
        return f"OpenAIProvider({self.model})"


class MockLLMProvider(LLMProvider):
    """
    Mock LLM provider that returns a fixed response.
    Used for testing and development without API calls.
    """

    def __init__(self, fixed_response: dict):
        self.fixed_response = fixed_response
        self.call_count = 0
        self.last_prompt: Optional[str] = None

    def generate(self, prompt: str, system: str = "", max_tokens: int = 1024) -> str:
        """Return fixed JSON response."""
        self.call_count += 1
        self.last_prompt = prompt
        return json.dumps(self.fixed_response)

    @property
    def name(self) -> str:
        return "MockLLMProvider"