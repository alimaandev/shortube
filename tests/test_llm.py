"""Tests for the LLM client layer: factory, retry, and JSON handling."""

from __future__ import annotations

import json

import pytest

from shortube.llm import (
    LLMError,
    OpenAICompatibleClient,
    _clean_json,
    _recover_json,
    create_llm,
)


class FakeCompletions:
    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        content = item if item is not None else None
        message = type("M", (), {"content": content})()
        choice = type("C", (), {"message": message})()
        resp = type("R", (), {"choices": [choice]})()
        return resp


class FakeClient:
    def __init__(self, responses):
        self.chat = type("Chat", (), {"completions": FakeCompletions(responses)})()


def make_client(monkeypatch, responses):
    monkeypatch.setattr("openai.OpenAI", lambda **kwargs: FakeClient(responses))
    return OpenAICompatibleClient(
        base_url="http://test", api_key="k", model="m", provider_name="Test"
    )


def test_create_llm_unknown_provider():
    with pytest.raises(LLMError, match="Unknown LLM provider"):
        create_llm(provider="nope", api_key="k")


def test_create_llm_groq_requires_key():
    with pytest.raises(LLMError, match="GROQ_API_KEY"):
        create_llm(provider="groq", api_key="")


def test_create_llm_openrouter_requires_key():
    with pytest.raises(LLMError, match="OPENROUTER_API_KEY"):
        create_llm(provider="openrouter", api_key="")


def test_create_llm_uses_provider_default_model():
    client = create_llm(provider="groq", api_key="k")
    assert client._model == "llama-3.3-70b-versatile"
    client = create_llm(provider="openrouter", api_key="k")
    assert client._model == "meta-llama/llama-4-scout:free"


def test_generate_returns_content(monkeypatch):
    client = make_client(monkeypatch, ["hello world"])
    assert client.generate("sys", "user") == "hello world"


def test_generate_raises_on_empty_content(monkeypatch):
    client = make_client(monkeypatch, [None, None, None])
    with pytest.raises(LLMError, match="empty response"):
        client.generate("sys", "user")


def test_generate_retries_then_succeeds(monkeypatch):
    client = make_client(monkeypatch, [RuntimeError("boom"), "ok"])
    assert client.generate("sys", "user") == "ok"
    assert len(client._client.chat.completions.calls) == 2


def test_generate_exhausts_retries(monkeypatch):
    client = make_client(monkeypatch, [RuntimeError("boom")] * 3)
    with pytest.raises(LLMError, match="after 3 attempts"):
        client.generate("sys", "user")
    assert len(client._client.chat.completions.calls) == 3


def test_generate_json_parses_fenced_output(monkeypatch):
    client = make_client(monkeypatch, ['```json\n{"a": 1}\n```'])
    assert client.generate_json("sys", "user") == {"a": 1}


def test_generate_json_recovers_from_braces(monkeypatch):
    client = make_client(monkeypatch, ['prefix {"a": 1} suffix'])
    assert client.generate_json("sys", "user") == {"a": 1}


def test_generate_json_failure_includes_raw(monkeypatch):
    client = make_client(monkeypatch, ["not json at all"])
    with pytest.raises(LLMError, match="not json at all"):
        client.generate_json("sys", "user")


def test_clean_json_strips_fences():
    assert _clean_json("```json\n{\"a\": 1}\n```") == '{"a": 1}'
    assert _clean_json(' {"b": 2} ') == '{"b": 2}'


def test_recover_json_unbalanced_braces():
    assert _recover_json('{"a": 1') == {"a": 1}


def test_recover_json_kv_pairs():
    assert _recover_json('junk "a": "x" junk "b": "y"') == {"a": "x", "b": "y"}


def test_recover_json_returns_none_for_garbage():
    assert _recover_json("totally not json") is None


def test_recover_json_returns_valid_json_directly():
    assert _recover_json('{"a": 1}') == {"a": 1}


def test_generate_json_parses_plain(monkeypatch):
    client = make_client(monkeypatch, [json.dumps({"k": "v"})])
    assert client.generate_json("sys", "user") == {"k": "v"}


def test_ollama_create_uses_settings_base_url(monkeypatch, settings):
    settings.ollama_base_url = "http://ollama.local"
    seen = {}

    def fake_openai(**kwargs):
        seen.update(kwargs)
        return FakeClient(["ok"])

    monkeypatch.setattr("openai.OpenAI", fake_openai)
    monkeypatch.setattr("shortube.config.get_settings", lambda: settings)
    client = create_llm(provider="ollama", api_key="")
    assert client._model == "qwen2.5:7b"
    assert seen["base_url"] == "http://ollama.local/v1"