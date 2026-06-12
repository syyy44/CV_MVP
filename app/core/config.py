from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.llm.providers import LLMProviderName, resolve_provider_settings


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    demo_mode: Literal["live", "replay"] = "replay"

    llm_api_key: str | None = None
    llm_provider: LLMProviderName = "dashscope"
    openai_base_url: str | None = None
    model_name: str | None = None
    default_temperature: float = 0.2
    llm_timeout_seconds: float = 180.0
    max_repair_attempts: int = 2

    # Upload & Privacy Contract
    max_resumes: int = 5
    max_file_mb: int = 5

    database_url: str = "sqlite:///data/recruiting.db"

    enable_langfuse: bool = False
    langfuse_public_key: str | None = None
    langfuse_secret_key: str | None = None
    langfuse_host: str = "https://cloud.langfuse.com"

    # 百度千帆 PaddleOCR-VL：PDF 优先 OCR，失败回退 pypdf
    qianfan_api_key: str | None = None
    paddle_ocr_timeout_seconds: float = 120.0

    # USD per 1K tokens; estimate only, surfaced in run metrics.
    cost_input_per_1k: float = 0.0008
    cost_output_per_1k: float = 0.002

    fixtures_dir: Path = Path("fixtures")

    @property
    def database_path(self) -> Path:
        url = self.database_url
        if url.startswith("sqlite:///"):
            return Path(url.removeprefix("sqlite:///"))
        return Path(url)

    @property
    def max_file_bytes(self) -> int:
        return self.max_file_mb * 1024 * 1024

    @property
    def langfuse_configured(self) -> bool:
        return bool(
            self.enable_langfuse and self.langfuse_public_key and self.langfuse_secret_key
        )

    @model_validator(mode="after")
    def _resolve_llm_provider(self) -> Self:
        base_url, model = resolve_provider_settings(
            llm_provider=self.llm_provider,
            openai_base_url=self.openai_base_url,
            model_name=self.model_name,
        )
        self.openai_base_url = base_url
        self.model_name = model
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


def reset_settings_cache() -> None:
    """Test helper: settings are cached per-process; tests change env vars."""
    get_settings.cache_clear()
