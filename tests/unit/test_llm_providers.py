from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings
from app.llm.providers import PROVIDER_PRESETS, resolve_provider_settings


def test_dashscope_preset_applies_base_url_and_default_model():
    base_url, model = resolve_provider_settings(
        llm_provider="dashscope",
        openai_base_url=None,
        model_name=None,
    )
    preset = PROVIDER_PRESETS["dashscope"]
    assert base_url == preset.base_url
    assert model == preset.default_model


def test_siliconflow_preset_applies_cn_endpoint():
    base_url, model = resolve_provider_settings(
        llm_provider="siliconflow",
        openai_base_url=None,
        model_name=None,
    )
    preset = PROVIDER_PRESETS["siliconflow"]
    assert base_url == "https://api.siliconflow.cn/v1"
    assert model == preset.default_model


def test_model_name_override_is_preserved():
    _, model = resolve_provider_settings(
        llm_provider="siliconflow",
        openai_base_url=None,
        model_name="Qwen/Qwen2.5-7B-Instruct",
    )
    assert model == "Qwen/Qwen2.5-7B-Instruct"


def test_custom_provider_requires_explicit_endpoint():
    with pytest.raises(ValueError, match="LLM_PROVIDER=custom"):
        resolve_provider_settings(
            llm_provider="custom",
            openai_base_url=None,
            model_name="my-model",
        )


def test_settings_resolves_siliconflow_from_env(monkeypatch):
    monkeypatch.delenv("MODEL_NAME", raising=False)
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    settings = Settings(_env_file=None, llm_provider="siliconflow")
    assert settings.llm_provider == "siliconflow"
    assert settings.openai_base_url == PROVIDER_PRESETS["siliconflow"].base_url
    assert settings.model_name == PROVIDER_PRESETS["siliconflow"].default_model


def test_settings_custom_provider_validation(monkeypatch):
    monkeypatch.delenv("OPENAI_BASE_URL", raising=False)
    monkeypatch.delenv("MODEL_NAME", raising=False)
    with pytest.raises(ValidationError):
        Settings(_env_file=None, llm_provider="custom")
