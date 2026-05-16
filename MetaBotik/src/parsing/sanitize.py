"""Normalize and summarize model output around strict JSON parsing."""

from __future__ import annotations

import re
from typing import Any

from pydantic import ValidationError


def extract_json_payload(raw_content: str) -> str:
    """Extract the most likely JSON object from a model response."""
    text = raw_content.strip()
    if not text:
        return text

    fenced = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, flags=re.IGNORECASE)
    if fenced:
        return fenced.group(1).strip()

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return text[start : end + 1].strip()
    return text


def summarize_validation_error(exc: Exception) -> str:
    if isinstance(exc, ValidationError):
        parts: list[str] = []
        for error in exc.errors()[:10]:
            loc = ".".join(str(item) for item in error.get("loc", ()))
            message = str(error.get("msg", "validation error"))
            parts.append(f"{loc}: {message}" if loc else message)
        if len(exc.errors()) > 10:
            parts.append(f"... {len(exc.errors()) - 10} more errors")
        return "; ".join(parts)
    return str(exc)


def summarize_json_shape(payload: Any) -> str:
    if isinstance(payload, dict):
        keys = ", ".join(sorted(str(key) for key in payload.keys()))
        return f"object keys=[{keys}]"
    if isinstance(payload, list):
        return f"array len={len(payload)}"
    return type(payload).__name__
