"""Output validation helpers."""

from __future__ import annotations

from src.domain.schemas import AgentResult
from src.parsing.exceptions import ValidationFailure


def validate_agent_result(result: AgentResult) -> None:
    if not result.procedural_analysis.alternative_procedures:
        raise ValidationFailure("alternative_procedures must not be empty")
    if not result.reflection.effectiveness.strip():
        raise ValidationFailure("reflection.effectiveness must not be empty")
    for step in result.solution_steps:
        if not step.critical_points:
            raise ValidationFailure(f"step {step.step} is missing critical_points")
