"""Procedure classification heuristics.

The classifier returns a *hint* for the LLM (passed as `selected_procedure_hint`
into the PMR prompt). The system prompt explicitly tells the model that this
is a recommendation only and to override it via its own procedural analysis,
so the mapping just needs to be plausible per domain, not authoritative.
"""

from __future__ import annotations

from src.domain.enums import TaskType

# PMR-Bench domains -> procedure-family hint.
DOMAIN_TO_TASK_TYPE: dict[str, TaskType] = {
    "Engineering": TaskType.ANALYTICAL,
    "Education": TaskType.ANALYTICAL,
    "Management": TaskType.BRANCHING,
    "Therapy": TaskType.DIAGNOSTIC,
}


def classify_task_type(domain: str) -> TaskType:
    return DOMAIN_TO_TASK_TYPE.get(domain, TaskType.MIXED)
