"""LLM settings."""

from __future__ import annotations

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Yandex OpenAI-compatible API expects a lowercase slug (e.g. qwen3-235b-a22b-fp8/latest),
# not the human-readable gallery title (e.g. Qwen3-235B-A22B-Instruct-2507-FP8).
_YANDEX_MODEL_ALIASES: dict[str, str] = {
    "qwen3-235b-a22b-instruct-2507-fp8": "qwen3-235b-a22b-fp8/latest",
}


def _resolve_yandex_model_slug(value: object) -> object:
    if not isinstance(value, str):
        return value
    key = value.strip().lower().replace(" ", "")
    return _YANDEX_MODEL_ALIASES.get(key, value.strip())


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    yandex_api_key: str = Field(alias="YANDEX_API_KEY")
    yandex_folder_id: str = Field(alias="YANDEX_FOLDER_ID")
    yandex_model: str = Field(default="yandexgpt/latest", alias="YANDEX_MODEL")
    yandex_model_baseline_packager: str | None = Field(default=None, alias="YANDEX_MODEL_BASELINE_PACKAGER")
    yandex_base_url: str = Field(
        default="https://llm.api.cloud.yandex.net/v1",
        alias="YANDEX_BASE_URL",
    )
    llm_temperature: float = Field(default=0.2, alias="LLM_TEMPERATURE")
    llm_top_p: float = Field(default=0.9, alias="LLM_TOP_P")
    llm_max_retries: int = Field(default=3, alias="LLM_MAX_RETRIES")
    llm_max_tokens: int = Field(default=15000, alias="LLM_MAX_TOKENS")
    llm_timeout_seconds: float = Field(default=300.0, alias="LLM_TIMEOUT_SECONDS")
    llm_request_sleep_seconds: float = Field(default=1.0, alias="LLM_REQUEST_SLEEP_SECONDS")
    llm_save_raw_responses: bool = Field(default=True, alias="LLM_SAVE_RAW_RESPONSES")
    llm_skip_existing: bool = Field(default=True, alias="LLM_SKIP_EXISTING")

    @field_validator("yandex_model", mode="before")
    @classmethod
    def resolve_yandex_model_aliases(cls, value: object) -> object:
        return _resolve_yandex_model_slug(value)

    @field_validator("yandex_model_baseline_packager", mode="before")
    @classmethod
    def resolve_packager_model_aliases(cls, value: object) -> object:
        if value is None or value == "":
            return None
        return _resolve_yandex_model_slug(value)

    @property
    def model_uri(self) -> str:
        return f"gpt://{self.yandex_folder_id}/{self.yandex_model}"

    @property
    def baseline_packager_model_slug(self) -> str:
        return self.yandex_model_baseline_packager or self.yandex_model

    @property
    def baseline_packager_model_uri(self) -> str:
        return f"gpt://{self.yandex_folder_id}/{self.baseline_packager_model_slug}"
