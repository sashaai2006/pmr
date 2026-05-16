"""Yandex AI Studio client via OpenAI-compatible API."""

from __future__ import annotations

import logging
import time
from typing import Any, Protocol

from openai import APIConnectionError, APIError, APIStatusError, APITimeoutError, OpenAI, RateLimitError

from src.domain.schemas import ChatMessage, RawCompletion
from src.llm.settings import LLMSettings

log = logging.getLogger("metabotik.llm")


class LLMClient(Protocol):
    def complete(
        self,
        messages: list[ChatMessage],
        *,
        json_response: bool = True,
        use_baseline_packager_model: bool = False,
    ) -> RawCompletion: ...


class YandexLLMClient:
    def __init__(self, settings: LLMSettings, client: OpenAI | None = None) -> None:
        self._settings = settings
        self._client = client or OpenAI(
            api_key=settings.yandex_api_key,
            base_url=settings.yandex_base_url,
            default_headers={
                "x-folder-id": settings.yandex_folder_id,
                "x-data-logging-enabled": "false",
            },
        )

    def _to_api_messages(self, messages: list[ChatMessage]) -> list[dict[str, Any]]:
        system_parts: list[str] = []
        payload: list[dict[str, Any]] = []
        for message in messages:
            if message.role in {"system", "developer"}:
                system_parts.append(message.content)
                continue
            payload.append({"role": message.role, "content": message.content})
        if system_parts:
            payload.insert(0, {"role": "system", "content": "\n\n".join(system_parts)})
        return payload

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        json_response: bool = True,
        use_baseline_packager_model: bool = False,
    ) -> RawCompletion:
        payload = self._to_api_messages(messages)
        api_model = (
            self._settings.baseline_packager_model_uri
            if use_baseline_packager_model
            else self._settings.model_uri
        )
        model_slug = (
            self._settings.baseline_packager_model_slug
            if use_baseline_packager_model
            else self._settings.yandex_model
        )
        last_error: Exception | None = None
        for attempt in range(self._settings.llm_max_retries):
            attempt_no = attempt + 1
            started = time.perf_counter()
            try:
                prompt_chars = sum(len(str(message.get("content", ""))) for message in payload)
                log.info(
                    "LLM request attempt %d/%d model=%s json=%s messages=%d prompt_chars=%d max_tokens=%d timeout=%ss",
                    attempt_no,
                    self._settings.llm_max_retries,
                    model_slug,
                    json_response,
                    len(payload),
                    prompt_chars,
                    self._settings.llm_max_tokens,
                    self._settings.llm_timeout_seconds,
                )
                create_kwargs: dict[str, Any] = {
                    "model": api_model,
                    "messages": payload,
                    "temperature": self._settings.llm_temperature,
                    "top_p": self._settings.llm_top_p,
                    "max_tokens": self._settings.llm_max_tokens,
                    "timeout": self._settings.llm_timeout_seconds,
                }
                if json_response:
                    create_kwargs["response_format"] = {"type": "json_object"}
                response = self._client.chat.completions.create(**create_kwargs)
                content = response.choices[0].message.content or ""
                elapsed = time.perf_counter() - started
                finish_reason = response.choices[0].finish_reason
                response_id = getattr(response, "id", None)
                log.info(
                    "LLM response attempt %d/%d status=ok elapsed=%.2fs chars=%d finish_reason=%s response_id=%s",
                    attempt_no,
                    self._settings.llm_max_retries,
                    elapsed,
                    len(content),
                    finish_reason,
                    response_id,
                )
                return RawCompletion(
                    content=content,
                    model=model_slug,
                    temperature=self._settings.llm_temperature,
                    top_p=self._settings.llm_top_p,
                    elapsed_seconds=elapsed,
                    response_id=response_id,
                    finish_reason=finish_reason,
                )
            except (APITimeoutError, APIConnectionError, RateLimitError, APIStatusError, APIError) as exc:
                last_error = exc
                elapsed = time.perf_counter() - started
                status_code = getattr(exc, "status_code", None)
                log.warning(
                    "LLM request attempt %d/%d failed elapsed=%.2fs type=%s status=%s message=%s",
                    attempt_no,
                    self._settings.llm_max_retries,
                    elapsed,
                    type(exc).__name__,
                    status_code,
                    str(exc)[:500],
                )
                if attempt + 1 >= self._settings.llm_max_retries:
                    break
                sleep_seconds = 0.5 * (2**attempt)
                log.info("LLM retry sleep %.2fs", sleep_seconds)
                time.sleep(sleep_seconds)
        assert last_error is not None
        raise last_error


class MockLLMClient:
    def __init__(self, content: str, model: str = "mock-model") -> None:
        self._content = content
        self._model = model
        self.calls: list[list[ChatMessage]] = []

    def complete(
        self,
        messages: list[ChatMessage],
        *,
        json_response: bool = True,
        use_baseline_packager_model: bool = False,
    ) -> RawCompletion:
        self.calls.append(messages)
        return RawCompletion(
            content=self._content,
            model=self._model,
            temperature=0.2,
            top_p=0.9,
        )
