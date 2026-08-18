"""LLM access: one OpenAI-compatible client, one JSON handler.

Groq, OpenRouter and Ollama all expose OpenAI-compatible chat
completions endpoints, so a single adapter serves all three providers.
Retry policy lives in exactly one place (inside `generate`), and JSON
extraction/recovery is shared by every provider.
"""

from __future__ import annotations

import json
import logging
import re
import time
from typing import Any, Protocol

logger = logging.getLogger(__name__)

# Single source of truth for the default model per provider.
PROVIDER_DEFAULT_MODELS: dict[str, str] = {
    "groq": "llama-3.3-70b-versatile",
    "openrouter": "meta-llama/llama-4-scout:free",
    "ollama": "qwen2.5:7b",
}


class LLMError(Exception):
    pass


class LLMClient(Protocol):
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
    ) -> dict[str, Any]: ...


# ── JSON extraction / recovery (shared by every provider) ─────────────


def _clean_json(raw: str) -> str:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(?:json)?\s*", "", raw)
        raw = re.sub(r"\s*```$", "", raw)
    return raw.strip()


def _recover_json(text: str) -> dict[str, Any] | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    brace_match = re.search(r"\{.*\}", text, re.DOTALL)
    if brace_match:
        try:
            return json.loads(brace_match.group())
        except json.JSONDecodeError:
            pass
    fixed = text.rstrip(", \n")
    open_braces = fixed.count("{")
    close_braces = fixed.count("}")
    fixed += "}" * (open_braces - close_braces)
    try:
        parsed = json.loads(fixed)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass
    kv_match = re.findall(r'"(\w+)":\s*"([^"]*)"', text)
    if kv_match:
        return {k: v for k, v in kv_match}
    return None


# ── The single client implementation ──────────────────────────────────


class OpenAICompatibleClient:
    """Chat completions adapter for any OpenAI-compatible endpoint."""

    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        model: str,
        provider_name: str,
        timeout: int = 60,
        max_attempts: int = 3,
        retry_delay: float = 1.0,
    ) -> None:
        try:
            from openai import OpenAI
        except ImportError:
            raise LLMError(
                "openai package not installed. Run: pip install openai"
            ) from None
        self._client = OpenAI(base_url=base_url, api_key=api_key, timeout=timeout)
        self._model = model
        self._provider_name = provider_name
        self._max_attempts = max_attempts
        self._retry_delay = retry_delay

    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
        last: LLMError | None = None
        for attempt in range(self._max_attempts):
            try:
                resp = self._client.chat.completions.create(
                    model=self._model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                content = resp.choices[0].message.content
                if content is None:
                    raise LLMError("LLM returned empty response")
                return content
            except LLMError as e:
                last = e
            except Exception as e:  # noqa: BLE001 - SDK boundary, wrap into LLMError
                last = LLMError(f"{self._provider_name} API call failed: {e}")
                last.__cause__ = e
            if attempt < self._max_attempts - 1:
                time.sleep(self._retry_delay * (2 ** attempt))
        raise LLMError(
            f"{self._provider_name} API call failed after "
            f"{self._max_attempts} attempts: {last}"
        ) from last

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        raw = self.generate(system_prompt, user_prompt, temperature, max_tokens)
        cleaned = _clean_json(raw)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            recovered = _recover_json(cleaned)
            if recovered is not None:
                return recovered
            raise LLMError(
                f"Failed to parse LLM response as JSON.\nRaw: {raw[:500]}"
            ) from None


# ── Provider factory ──────────────────────────────────────────────────


def create_llm(
    provider: str = "groq",
    api_key: str = "",
    model: str = "",
) -> OpenAICompatibleClient:
    """Build the client for a provider, using the provider's default model."""
    model = model or PROVIDER_DEFAULT_MODELS.get(provider, "")

    if provider == "groq":
        if not api_key:
            raise LLMError("GROQ_API_KEY is not set")
        return OpenAICompatibleClient(
            base_url="https://api.groq.com/openai/v1",
            api_key=api_key,
            model=model,
            provider_name="Groq",
        )

    if provider == "openrouter":
        if not api_key:
            raise LLMError("OPENROUTER_API_KEY is not set")
        return OpenAICompatibleClient(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
            model=model,
            provider_name="OpenRouter",
        )

    if provider == "ollama":
        from shortube.config import get_settings

        base_url = get_settings().ollama_base_url.rstrip("/") + "/v1"
        return OpenAICompatibleClient(
            base_url=base_url,
            api_key="ollama",
            model=model,
            provider_name="Ollama",
            timeout=30,
        )

    raise LLMError(
        f"Unknown LLM provider: {provider}. Available: {sorted(PROVIDER_DEFAULT_MODELS)}"
    )