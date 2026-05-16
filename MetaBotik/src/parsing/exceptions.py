"""Parsing exceptions."""

from __future__ import annotations


class SchemaRepairNeeded(Exception):
    def __init__(self, message: str, raw_content: str) -> None:
        super().__init__(message)
        self.raw_content = raw_content


class ValidationFailure(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)
