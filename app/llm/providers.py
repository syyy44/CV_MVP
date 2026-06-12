"""OpenAI-compatible LLM provider presets.

Switch gateways via `LLM_PROVIDER` in `.env` instead of hand-copying base URLs.
Set `LLM_PROVIDER=custom` when you need a non-listed endpoint.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from app.locale import zh_CN as msg

LLMProviderName = Literal["dashscope", "siliconflow", "custom"]


@dataclass(frozen=True)
class ProviderPreset:
    label: str
    base_url: str
    default_model: str
    docs_url: str


PROVIDER_PRESETS: dict[LLMProviderName, ProviderPreset] = {
    "dashscope": ProviderPreset(
        label="DashScope (Alibaba Cloud)",
        base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        default_model="qwen-plus",
        docs_url="https://help.aliyun.com/zh/model-studio/developer-reference/use-qwen-by-calling-api",
    ),
    "siliconflow": ProviderPreset(
        label="SiliconFlow",
        base_url="https://api.siliconflow.cn/v1",
        default_model="deepseek-ai/DeepSeek-V3",
        docs_url="https://docs.siliconflow.cn/",
    ),
}


def resolve_provider_settings(
    *,
    llm_provider: LLMProviderName,
    openai_base_url: str | None,
    model_name: str | None,
) -> tuple[str, str]:
    """Return `(base_url, model_name)` after applying provider presets."""
    if llm_provider == "custom":
        if not openai_base_url or not model_name:
            raise ValueError(msg.llm_provider_custom_requires_config())
        return openai_base_url, model_name

    preset = PROVIDER_PRESETS[llm_provider]
    resolved_base_url = preset.base_url
    resolved_model = model_name or preset.default_model
    return resolved_base_url, resolved_model
