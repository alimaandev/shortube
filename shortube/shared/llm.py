from __future__ import annotations

import json
import logging
import re
from abc import ABC, abstractmethod
from typing import Any

from shortube.core.exceptions import LLMError
from shortube.shared.retry import retry

logger = logging.getLogger(__name__)


class LLMProvider(ABC):
    @abstractmethod
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str: ...

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        raw = self.generate(system_prompt, user_prompt, temperature, max_tokens)
        cleaned = self._clean_json(raw)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as e:
            raise LLMError(f"Failed to parse LLM response as JSON: {e}\nRaw: {raw[:500]}")

    @staticmethod
    def _clean_json(raw: str) -> str:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        return raw.strip()


class GroqProvider(LLMProvider):
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        if not api_key:
            raise LLMError("GROQ_API_KEY is not set")
        try:
            from groq import Groq
        except ImportError:
            raise LLMError("groq package not installed. Run: pip install groq")
        self._client = Groq(api_key=api_key, timeout=60)
        self._model = model

    @retry(max_attempts=3, exceptions=(Exception,))
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]
        try:
            resp = self._client.chat.completions.create(
                model=self._model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
            )
            content = resp.choices[0].message.content
            if content is None:
                raise LLMError("LLM returned empty response")
            return content
        except Exception as e:
            raise LLMError(f"Groq API call failed: {e}")


_PROVIDER_REGISTRY: dict[str, type[LLMProvider]] = {
    "groq": GroqProvider,
}


def register_provider(name: str, cls: type[LLMProvider]) -> None:
    _PROVIDER_REGISTRY[name] = cls


def create_llm(
    provider: str = "groq",
    api_key: str = "",
    model: str = "llama-3.3-70b-versatile",
) -> LLMProvider:
    cls = _PROVIDER_REGISTRY.get(provider)
    if cls is None:
        raise LLMError(f"Unknown LLM provider: {provider}. Available: {list(_PROVIDER_REGISTRY)}")
    return cls(api_key=api_key, model=model)
