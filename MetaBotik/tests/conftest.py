"""Shared pytest fixtures + helpers for MetaBotik tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.domain.enums import Difficulty
from src.domain.schemas import (
    NormalizedTask,
    RawCompletion,
)


def valid_agent_payload(task_id: str = "PMR-001") -> dict[str, Any]:
    """A minimal but schema-valid PMR JSON answer."""
    return {
        "task_id": task_id,
        "task_type": "analytical",
        "difficulty": "intermediate",
        "procedural_analysis": {
            "problem_classification": "Procedural design under regulatory constraints.",
            "selected_procedure": "hybrid V-model + agile increments",
            "selection_reasoning": "Hybrid keeps audit traceability while preserving iteration speed.",
            "alternative_procedures": [
                {"name": "pure Agile", "rejection_reason": "No fixed V&V artefact baseline for audit."},
                {"name": "pure V-model", "rejection_reason": "Slow adaptation for UI iteration cycles."},
            ],
        },
        "solution_steps": [
            {
                "step": 1,
                "title": "Compliance bootstrap",
                "action": "Train team on IEC 62304 and freeze SOPs before coding.",
                "procedure_logic": "Without baseline SOPs an audit reviewer cannot reconstruct trace.",
                "critical_points": ["Software safety classification is a point of no return."],
                "adaptation_notes": ["For class C add independent verification team."],
            },
            {
                "step": 2,
                "title": "Architecture + V&V planning",
                "action": "Decompose architecture by safety class and assign V&V depth per component.",
                "procedure_logic": "Architecture fixes the V&V scope for the whole project.",
                "critical_points": ["Late refactors trigger full re-verification."],
                "adaptation_notes": ["Re-run risk analysis on each major architecture change."],
            },
        ],
        "reflection": {
            "effectiveness": "Procedure preserves both auditability and iteration speed.",
            "limitations": [
                "Requires definition of regulatory done per increment.",
                "Demands compliance literacy across the entire team.",
            ],
            "best_use_cases": ["Class B medical software with mixed regulatory + UX workload."],
            "future_modifications": [
                "Introduce automated traceability tooling and add an independent V&V audit.",
            ],
        },
        "metadata": {
            "model": "mock-model",
            "temperature": 0.2,
            "top_p": 0.9,
            "timestamp": "2026-05-15T12:00:00+00:00",
        },
    }


def low_quality_payload(task_id: str = "PMR-001") -> dict[str, Any]:
    """An answer with no procedural layer at all (baseline-shaped)."""
    return {
        "task_id": task_id,
        "answer": "Просто следуйте agile подходу и регулярно встречайтесь с командой.",
    }


def make_task(task_id: str = "PMR-001", domain: str = "Engineering") -> NormalizedTask:
    return NormalizedTask(
        task_id=task_id,
        domain=domain,
        title=f"{domain} — toy task",
        prompt="Toy task prompt body.",
        difficulty=Difficulty.INTERMEDIATE,
    )


class FakeLLMClient:
    """Deterministic LLMClient stub returning a pre-supplied JSON string."""

    def __init__(self, content: str, model: str = "fake") -> None:
        self.content = content
        self.model = model
        self.calls: list[list[Any]] = []

    def complete(
        self,
        messages: list[Any],
        *,
        json_response: bool = True,
        use_baseline_packager_model: bool = False,
    ) -> RawCompletion:
        self.calls.append(messages)
        return RawCompletion(content=self.content, model=self.model, temperature=0.2, top_p=0.9)


@pytest.fixture
def pmr_payload() -> dict[str, Any]:
    return valid_agent_payload()


@pytest.fixture
def low_payload() -> dict[str, Any]:
    return low_quality_payload()


@pytest.fixture
def fake_llm_pmr() -> FakeLLMClient:
    return FakeLLMClient(json.dumps(valid_agent_payload()))


@pytest.fixture
def temp_run_dir(tmp_path: Path) -> Path:
    out = tmp_path / "run"
    out.mkdir()
    return out


@pytest.fixture
def normalized_task() -> NormalizedTask:
    return make_task()
