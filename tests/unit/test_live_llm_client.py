from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.core.config import Settings
from app.core.errors import (
    LLMProviderError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMTimeoutError,
)
from app.llm.client import LiveLLMProvider


class FakeChatCompletions:
    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls: list[dict] = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


class FakeClient:
    def __init__(self, outcomes):
        self.chat = SimpleNamespace(completions=FakeChatCompletions(outcomes))


def response(content: str | None, *, model: str = "qwen-plus"):
    message = SimpleNamespace(content=content)
    choice = SimpleNamespace(message=message)
    usage = SimpleNamespace(prompt_tokens=11, completion_tokens=7)
    return SimpleNamespace(choices=[choice], model=model, usage=usage)


def settings() -> Settings:
    return Settings(llm_api_key="test-key")


def test_live_provider_uses_json_schema_when_schema_is_provided():
    client = FakeClient([response('{"ok": true}')])
    provider = LiveLLMProvider(settings(), client=client)

    result = provider.complete(
        [{"role": "user", "content": "return json"}],
        response_schema={
            "type": "object",
            "properties": {"ok": {"type": "boolean"}},
            "required": ["ok"],
        },
        response_schema_name="TestSchema",
    )

    assert result.text == '{"ok": true}'
    assert client.chat.completions.calls[0]["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "TestSchema",
            "schema": {
                "type": "object",
                "properties": {"ok": {"type": "boolean"}},
                "required": ["ok"],
            },
            "strict": True,
        },
    }


def test_live_provider_falls_back_to_json_object_when_json_schema_rejected(monkeypatch):
    import openai

    class FakeBadRequest(Exception):
        pass

    monkeypatch.setattr(openai, "BadRequestError", FakeBadRequest)
    client = FakeClient(
        [
            FakeBadRequest("json_schema unsupported"),
            response('{"ok": true}'),
            response('{"again": true}'),
        ]
    )
    provider = LiveLLMProvider(settings(), client=client)

    result = provider.complete(
        [{"role": "user", "content": "return json"}],
        response_schema={"type": "object"},
        response_schema_name="TestSchema",
    )

    assert result.text == '{"ok": true}'
    assert client.chat.completions.calls[0]["response_format"]["type"] == "json_schema"
    assert client.chat.completions.calls[1]["response_format"] == {"type": "json_object"}

    provider.complete(
        [{"role": "user", "content": "again"}],
        response_schema={"type": "object"},
        response_schema_name="TestSchema",
    )
    assert client.chat.completions.calls[2]["response_format"] == {"type": "json_object"}


def test_live_provider_uses_json_mode_then_falls_back_when_gateway_rejects(monkeypatch):
    import openai

    class FakeBadRequest(Exception):
        pass

    monkeypatch.setattr(openai, "BadRequestError", FakeBadRequest)
    client = FakeClient(
        [
            FakeBadRequest("response_format unsupported"),
            response('{"ok": true}'),
            response('{"again": true}'),
        ]
    )
    provider = LiveLLMProvider(settings(), client=client)

    result = provider.complete([{"role": "user", "content": "return json"}])

    assert result.text == '{"ok": true}'
    assert result.input_tokens == 11
    assert result.output_tokens == 7
    assert client.chat.completions.calls[0]["response_format"] == {"type": "json_object"}
    assert "response_format" not in client.chat.completions.calls[1]

    provider.complete([{"role": "user", "content": "again"}])
    assert "response_format" not in client.chat.completions.calls[2]


def test_live_provider_maps_timeout(monkeypatch):
    import openai

    class FakeTimeout(Exception):
        pass

    monkeypatch.setattr(openai, "APITimeoutError", FakeTimeout)
    client = FakeClient([FakeTimeout("timeout")])
    provider = LiveLLMProvider(settings(), client=client)

    with pytest.raises(LLMTimeoutError):
        provider.complete([{"role": "user", "content": "slow"}])


def test_live_provider_maps_rate_limit(monkeypatch):
    import openai

    class FakeRateLimit(Exception):
        pass

    monkeypatch.setattr(openai, "RateLimitError", FakeRateLimit)
    client = FakeClient([FakeRateLimit("429")])
    provider = LiveLLMProvider(settings(), client=client)

    with pytest.raises(LLMRateLimitError):
        provider.complete([{"role": "user", "content": "limited"}])


def test_live_provider_maps_generic_api_error(monkeypatch):
    import openai

    class FakeAPIError(Exception):
        pass

    monkeypatch.setattr(openai, "APIError", FakeAPIError)
    client = FakeClient([FakeAPIError("server broke")])
    provider = LiveLLMProvider(settings(), client=client)

    with pytest.raises(LLMProviderError):
        provider.complete([{"role": "user", "content": "boom"}])


def test_live_provider_rejects_empty_content():
    client = FakeClient([response("")])
    provider = LiveLLMProvider(settings(), client=client)

    with pytest.raises(LLMRefusalError):
        provider.complete([{"role": "user", "content": "empty"}])


def test_live_provider_requires_api_key():
    with pytest.raises(Exception) as excinfo:
        LiveLLMProvider(Settings(llm_api_key=None), client=FakeClient([]))
    assert "LLM_API_KEY" in str(excinfo.value)
