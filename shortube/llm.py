from __future__ import annotations

import functools
import json
import logging
import re
import time
from typing import Any

logger = logging.getLogger(__name__)


class LLMError(Exception):
    pass


def retry(max_attempts: int = 3, delay: float = 1.0):
    def decorator(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            last = None
            for attempt in range(max_attempts):
                try:
                    return fn(*args, **kwargs)
                except Exception as e:
                    last = e
                    if attempt < max_attempts - 1:
                        time.sleep(delay * (2 ** attempt))
            raise last
        return wrapper
    return decorator


class GroqProvider:
    def __init__(self, api_key: str, model: str = "llama-3.3-70b-versatile"):
        if not api_key:
            raise LLMError("GROQ_API_KEY is not set")
        try:
            from groq import Groq
        except ImportError:
            raise LLMError("groq package not installed. Run: pip install groq")
        self._client = Groq(api_key=api_key, timeout=60)
        self._model = model

    @retry(max_attempts=3)
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
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
        except Exception as e:
            raise LLMError(f"Groq API call failed: {e}")

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
        except json.JSONDecodeError:
            recovered = self._attempt_json_recovery(cleaned)
            if recovered is not None:
                return recovered
            raise LLMError(
                f"Failed to parse LLM response as JSON.\nRaw: {raw[:500]}"
            )

    @staticmethod
    def _clean_json(raw: str) -> str:
        raw = raw.strip()
        if raw.startswith("```"):
            raw = re.sub(r"^```(?:json)?\s*", "", raw)
            raw = re.sub(r"\s*```$", "", raw)
        return raw.strip()

    @staticmethod
    def _attempt_json_recovery(text: str) -> dict[str, Any] | None:
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


class OpenRouterProvider:
    def __init__(self, api_key: str, model: str = "meta-llama/llama-4-scout:free"):
        if not api_key:
            raise LLMError("OPENROUTER_API_KEY is not set")
        try:
            from openai import OpenAI
        except ImportError:
            raise LLMError("openai package not installed. Run: pip install openai")
        self._client = OpenAI(
            base_url="https://openrouter.ai/api/v1",
            api_key=api_key,
        )
        self._model = model

    @retry(max_attempts=3)
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
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
        except Exception as e:
            raise LLMError(f"OpenRouter API call failed: {e}")

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        raw = self.generate(system_prompt, user_prompt, temperature, max_tokens)
        cleaned = GroqProvider._clean_json(raw)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            recovered = GroqProvider._attempt_json_recovery(cleaned)
            if recovered is not None:
                return recovered
            raise LLMError(
                f"Failed to parse LLM response as JSON.\nRaw: {raw[:500]}"
            )


class OllamaProvider:
    def __init__(self, api_key: str, model: str = "qwen2.5:7b"):
        try:
            from openai import OpenAI
        except ImportError:
            raise LLMError("openai package not installed. Run: pip install openai")
        from shortube.config import get_settings
        base_url = get_settings().ollama_base_url.rstrip("/") + "/v1"
        self._client = OpenAI(base_url=base_url, api_key="ollama")
        self._model = model

    @retry(max_attempts=3)
    def generate(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> str:
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
        except Exception as e:
            raise LLMError(f"Ollama API call failed: {e}")

    def generate_json(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.7,
        max_tokens: int = 1024,
    ) -> dict[str, Any]:
        raw = self.generate(system_prompt, user_prompt, temperature, max_tokens)
        cleaned = GroqProvider._clean_json(raw)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            recovered = GroqProvider._attempt_json_recovery(cleaned)
            if recovered is not None:
                return recovered
            raise LLMError(
                f"Failed to parse LLM response as JSON.\nRaw: {raw[:500]}"
            )


_PROVIDERS: dict[str, type] = {
    "groq": GroqProvider,
    "openrouter": OpenRouterProvider,
    "ollama": OllamaProvider,
}


def create_llm(
    provider: str = "groq",
    api_key: str = "",
    model: str = "llama-3.3-70b-versatile",
) -> GroqProvider:
    cls = _PROVIDERS.get(provider)
    if cls is None:
        raise LLMError(
            f"Unknown LLM provider: {provider}. Available: {list(_PROVIDERS)}"
        )
    return cls(api_key=api_key, model=model)
