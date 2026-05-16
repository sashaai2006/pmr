"""LLM settings resolution."""

from pydantic_settings import SettingsConfigDict

from src.llm.settings import LLMSettings


class _LLMSettingsNoEnvFile(LLMSettings):
    """Same as LLMSettings but do not read .env (tests must be deterministic)."""

    model_config = SettingsConfigDict(env_file=None, extra="ignore", populate_by_name=True)


def test_qwen_ui_display_name_maps_to_yandex_api_slug() -> None:
    settings = _LLMSettingsNoEnvFile(
        yandex_api_key="dummy",
        yandex_folder_id="b1gtest",
        yandex_model="Qwen3-235B-A22B-Instruct-2507-FP8",
    )
    assert settings.yandex_model == "qwen3-235b-a22b-fp8/latest"
    assert settings.model_uri == "gpt://b1gtest/qwen3-235b-a22b-fp8/latest"


def test_explicit_slug_passes_through() -> None:
    settings = _LLMSettingsNoEnvFile(
        yandex_api_key="dummy",
        yandex_folder_id="b1gtest",
        yandex_model="qwen3-235b-a22b-fp8/latest",
    )
    assert settings.yandex_model == "qwen3-235b-a22b-fp8/latest"


def test_baseline_packager_uri_falls_back_to_main_model() -> None:
    settings = _LLMSettingsNoEnvFile(
        yandex_api_key="dummy",
        yandex_folder_id="b1gtest",
        yandex_model="yandexgpt/latest",
    )
    assert settings.baseline_packager_model_uri == settings.model_uri


def test_baseline_packager_uri_uses_override_slug() -> None:
    settings = _LLMSettingsNoEnvFile(
        yandex_api_key="dummy",
        yandex_folder_id="b1gtest",
        yandex_model="qwen3-235b-a22b-fp8/latest",
        yandex_model_baseline_packager="yandexgpt/latest",
    )
    assert settings.baseline_packager_model_uri == "gpt://b1gtest/yandexgpt/latest"
