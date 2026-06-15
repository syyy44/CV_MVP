from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Protocol

from app.core.config import Settings
from app.core.errors import (
    ConfigurationError,
    LLMProviderError,
    LLMRateLimitError,
    LLMRefusalError,
    LLMTimeoutError,
)
from app.core.logging import get_logger
from app.locale import zh_CN as msg

log = get_logger(__name__)


@dataclass
class CompletionResult:
    text: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0


class LLMProvider(Protocol):
    name: str

    def complete(
        self,
        messages: list[dict],
        *,
        fixture_key: str | None = None,
        temperature: float | None = None,
        response_schema: dict[str, Any] | None = None,
        response_schema_name: str | None = None,
    ) -> CompletionResult: ...


def _strip_schema_noise(node: Any) -> Any:
    """Compact a JSON Schema for in-prompt delivery (drop prose, keep structure).

    `description`/`title` duplicate what the prompts already explain; removing
    them keeps the schema hint small while preserving every field name, type,
    `required` list and `enum` literal — exactly what the model needs to emit
    a valid shape on the first attempt.
    """
    if isinstance(node, dict):
        return {
            key: _strip_schema_noise(value)
            for key, value in node.items()
            if key not in ("description", "title")
        }
    if isinstance(node, list):
        return [_strip_schema_noise(value) for value in node]
    return node


class LiveLLMProvider:
    """OpenAI-compatible chat completions adapter.

    Default live path is DashScope (`LLM_PROVIDER=dashscope`). SiliconFlow and
    other OpenAI-compatible gateways are selected via `LLM_PROVIDER` or
    `LLM_PROVIDER=custom` with explicit `OPENAI_BASE_URL` + `MODEL_NAME`.
    Structured Outputs are attempted first when a JSON Schema is provided, then
    JSON mode/plain mode are used as fallbacks for less capable gateways. On
    the fallback paths the schema is injected into the prompt instead (e.g.
    DeepSeek rejects `response_format=json_schema`), so the model always sees
    the exact field names, required lists and enum literals.
    """

    name = "live"

    def __init__(self, settings: Settings, client=None):
        if not settings.llm_api_key:
            raise ConfigurationError(msg.live_requires_api_key_extended())
        self._settings = settings
        if client is None:
            from openai import OpenAI

            client = OpenAI(
                api_key=settings.llm_api_key,
                base_url=settings.openai_base_url,
                timeout=settings.llm_timeout_seconds,
                max_retries=0,
            )
        self._client = client
        self._json_schema_supported = True
        self._json_mode_supported = True

    def complete(
        self,
        messages: list[dict],
        *,
        fixture_key: str | None = None,
        temperature: float | None = None,
        response_schema: dict[str, Any] | None = None,
        response_schema_name: str | None = None,
    ) -> CompletionResult:
        import openai

        kwargs: dict = {
            "model": self._settings.model_name,
            "messages": messages,
            "temperature": (
                temperature if temperature is not None else self._settings.default_temperature
            ),
        }
        if self._settings.llm_max_output_tokens:
            kwargs["max_tokens"] = self._settings.llm_max_output_tokens
        try:
            if response_schema is not None and self._json_schema_supported:
                try:
                    response = self._client.chat.completions.create(
                        **kwargs,
                        response_format={
                            "type": "json_schema",
                            "json_schema": {
                                "name": response_schema_name or "StructuredOutput",
                                "schema": response_schema,
                                "strict": True,
                            },
                        },
                    )
                except openai.BadRequestError:
                    self._json_schema_supported = False
                    log.warning(
                        "provider rejected json_schema response_format; "
                        "falling back to json_object"
                    )
                    kwargs["messages"] = self._with_schema_hint(
                        messages, response_schema, response_schema_name
                    )
                    response = self._complete_json_object_or_plain(openai, kwargs)
            else:
                if response_schema is not None:
                    kwargs["messages"] = self._with_schema_hint(
                        messages, response_schema, response_schema_name
                    )
                response = self._complete_json_object_or_plain(openai, kwargs)
        except openai.APITimeoutError as exc:
            raise LLMTimeoutError(msg.llm_timeout(self._settings.llm_timeout_seconds)) from exc
        except openai.APIConnectionError as exc:
            raise LLMTimeoutError(msg.llm_connection_failed(str(exc))) from exc
        except openai.RateLimitError as exc:
            raise LLMRateLimitError(msg.llm_rate_limit()) from exc
        except openai.APIError as exc:
            raise LLMProviderError(msg.llm_provider_error(str(exc))) from exc

        choice = response.choices[0] if response.choices else None
        content = choice.message.content if choice and choice.message else None
        if not content or not content.strip():
            raise LLMRefusalError(msg.llm_no_content())

        usage = getattr(response, "usage", None)
        return CompletionResult(
            text=content,
            model=getattr(response, "model", self._settings.model_name),
            input_tokens=getattr(usage, "prompt_tokens", 0) or 0,
            output_tokens=getattr(usage, "completion_tokens", 0) or 0,
        )

    def _with_schema_hint(
        self,
        messages: list[dict],
        response_schema: dict[str, Any],
        response_schema_name: str | None,
    ) -> list[dict]:
        """Append the schema as an explicit output contract message.

        Used on the json_object/plain fallback paths, where the provider does
        not enforce (or even see) the response schema. Without this, the model
        has to guess field names from prose and first attempts reliably fail
        validation (observed with DeepSeek, which rejects json_schema).
        """
        compact = _strip_schema_noise(response_schema)
        hint = {
            "role": "system",
            "content": (
                f"输出契约（schema 名：{response_schema_name or 'StructuredOutput'}）："
                "当前服务商不支持 json_schema 响应格式，因此在此明确结构。"
                "你的回复必须是且仅是一个符合以下 JSON Schema 的 JSON 对象："
                "字段名必须逐字使用 schema 中的英文键名；required 字段全部必填；"
                "enum 字段只能取列出的枚举值；不要输出 schema 之外的字段。\n"
                + json.dumps(compact, ensure_ascii=False, separators=(",", ":"))
            ),
        }
        return [*messages, hint]

    def _complete_json_object_or_plain(self, openai, kwargs: dict):
        if self._json_mode_supported:
            try:
                return self._client.chat.completions.create(
                    **kwargs, response_format={"type": "json_object"}
                )
            except openai.BadRequestError:
                # Some OpenAI-compatible gateways reject response_format.
                self._json_mode_supported = False
                log.warning("provider rejected response_format; falling back to plain JSON")
                return self._client.chat.completions.create(**kwargs)
        return self._client.chat.completions.create(**kwargs)
