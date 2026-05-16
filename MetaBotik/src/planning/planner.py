"""Procedure planning."""

from __future__ import annotations

from src.domain.enums import TaskType
from src.domain.schemas import AlternativeProcedure, NormalizedTask, ProcedureChoice
from src.planning.heuristics import classify_task_type

PROCEDURE_NAMES: dict[TaskType, str] = {
    TaskType.LINEAR: "linear staged execution",
    TaskType.BRANCHING: "branching decision procedure",
    TaskType.CYCLIC: "iterative self-correction loop",
    TaskType.ANALYTICAL: "analytical decomposition procedure",
    TaskType.DIAGNOSTIC: "diagnostic verification procedure",
    TaskType.CREATIVE: "creative synthesis procedure",
    TaskType.MIXED: "mixed multi-stage procedure",
}

ALTERNATIVES: dict[TaskType, list[AlternativeProcedure]] = {
    TaskType.ANALYTICAL: [
        AlternativeProcedure(
            name="linear staged execution",
            rejection_reason="The task requires explicit decomposition and evidence checks.",
        ),
        AlternativeProcedure(
            name="creative synthesis procedure",
            rejection_reason="The task depends on structured reasoning rather than open synthesis.",
        ),
    ],
    TaskType.DIAGNOSTIC: [
        AlternativeProcedure(
            name="linear staged execution",
            rejection_reason="Hidden traps require explicit verification and revision points.",
        ),
        AlternativeProcedure(
            name="branching decision procedure",
            rejection_reason="The primary risk is undetected error, not branch selection alone.",
        ),
    ],
    TaskType.MIXED: [
        AlternativeProcedure(
            name="linear staged execution",
            rejection_reason="Multiple constraints require alternating analysis and integration.",
        ),
        AlternativeProcedure(
            name="analytical decomposition procedure",
            rejection_reason="The task also needs synthesis across competing perspectives.",
        ),
    ],
}


class ProcedurePlanner:
    def plan(self, task: NormalizedTask) -> ProcedureChoice:
        task_type = classify_task_type(task.domain)
        selected_procedure = PROCEDURE_NAMES[task_type]
        reasoning = (
            f"Domain {task.domain} maps to a {task_type.value} procedure because the task requires explicit "
            "procedure-aware reasoning rather than a single-pass answer."
        )
        alternatives = ALTERNATIVES.get(
            task_type,
            [
                AlternativeProcedure(
                    name="linear staged execution",
                    rejection_reason="A single fixed sequence cannot cover the task constraints.",
                )
            ],
        )
        return ProcedureChoice(
            task_type=task_type,
            selected_procedure=selected_procedure,
            selection_reasoning=reasoning,
            alternative_procedures=alternatives,
        )
