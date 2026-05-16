"""Procedure planner heuristics on PMR-Bench domains."""

from __future__ import annotations

from src.domain.enums import Difficulty, TaskType
from src.domain.schemas import NormalizedTask
from src.planning.heuristics import classify_task_type
from src.planning.planner import ProcedurePlanner


def _make(domain: str) -> NormalizedTask:
    return NormalizedTask(
        task_id="PMR-X",
        domain=domain,
        title=f"{domain} — test",
        prompt="test",
        difficulty=Difficulty.INTERMEDIATE,
    )


def test_classify_known_pmr_domains() -> None:
    assert classify_task_type("Engineering") == TaskType.ANALYTICAL
    assert classify_task_type("Education") == TaskType.ANALYTICAL
    assert classify_task_type("Management") == TaskType.BRANCHING
    assert classify_task_type("Therapy") == TaskType.DIAGNOSTIC


def test_unknown_domain_defaults_to_mixed() -> None:
    assert classify_task_type("Unknown Domain") == TaskType.MIXED


def test_planner_produces_alternatives() -> None:
    plan = ProcedurePlanner().plan(_make("Engineering"))
    assert plan.task_type == TaskType.ANALYTICAL
    assert len(plan.alternative_procedures) >= 2
    for alt in plan.alternative_procedures:
        assert alt.name
        assert alt.rejection_reason
