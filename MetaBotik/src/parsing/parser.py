"""Parse and validate LLM JSON output."""

from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from src.domain.schemas import AgentResult
from src.parsing.exceptions import SchemaRepairNeeded
from src.parsing.sanitize import extract_json_payload, summarize_json_shape, summarize_validation_error

log = logging.getLogger("metabotik.parser")


class ResponseParser:
    def parse(self, raw_content: str) -> AgentResult:
        normalized = extract_json_payload(raw_content)
        if normalized != raw_content.strip():
            log.info(
                "normalized LLM response before JSON parsing raw_chars=%d normalized_chars=%d",
                len(raw_content),
                len(normalized),
            )
        try:
            payload = json.loads(normalized)
        except json.JSONDecodeError as exc:
            message = f"JSON decode failed: {summarize_validation_error(exc)}"
            log.warning("%s raw_chars=%d normalized_chars=%d", message, len(raw_content), len(normalized))
            raise SchemaRepairNeeded(message, raw_content) from exc
        log.info("JSON decoded: %s", summarize_json_shape(payload))
        try:
            return AgentResult.model_validate(payload)
        except ValidationError as exc:
            message = f"Schema validation failed: {summarize_validation_error(exc)}"
            log.warning(message)
            raise SchemaRepairNeeded(message, raw_content) from exc
