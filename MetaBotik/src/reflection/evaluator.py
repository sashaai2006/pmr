"""Procedural quality gates."""

from __future__ import annotations

from src.domain.schemas import AgentResult
from src.parsing.exceptions import ValidationFailure
from src.parsing.validators import validate_agent_result


class ProceduralEvaluator:
    def evaluate(self, result: AgentResult) -> None:
        validate_agent_result(result)
        if not result.reflection.limitations:
            raise ValidationFailure("reflection.limitations must not be empty")
        if not result.reflection.future_modifications:
            raise ValidationFailure("reflection.future_modifications must not be empty")
        if not result.procedural_analysis.selection_reasoning.strip():
            raise ValidationFailure("procedural_analysis.selection_reasoning must not be empty")
