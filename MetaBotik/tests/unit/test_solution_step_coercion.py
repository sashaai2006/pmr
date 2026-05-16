"""SolutionStep tolerates nested structures in string slots (common LLM quirks)."""

from __future__ import annotations

from src.domain.schemas import AgentResult, SolutionStep


def test_solution_step_coerces_dict_action_to_string() -> None:
    step = SolutionStep.model_validate(
        {
            "step": 1,
            "title": {"text": "Plan"},
            "action": {"description": "Gather inputs", "notes": "x"},
            "procedure_logic": "top-down",
            "critical_points": ["cp1"],
        }
    )
    assert step.title == "Plan"
    assert "Gather inputs" in step.action
    assert step.procedure_logic == "top-down"


def test_minimal_agent_payload_with_nested_actions_roundtrips() -> None:
    payload = {
        "task_id": "PMR-999",
        "task_type": "analytical",
        "difficulty": "intermediate",
        "procedural_analysis": {
            "problem_classification": "c",
            "selected_procedure": "p",
            "selection_reasoning": "r",
            "alternative_procedures": [
                {"name": "a1", "rejection_reason": "r1"},
                {"name": "a2", "rejection_reason": "r2"},
            ],
        },
        "solution_steps": [
            {
                "step": 1,
                "title": "T",
                "action": {"what": "nested"},
                "procedure_logic": "L",
                "critical_points": ["c"],
            }
        ],
        "reflection": {
            "effectiveness": "ok",
            "limitations": ["l1", "l2"],
            "best_use_cases": ["u1"],
            "future_modifications": ["m1"],
        },
        "metadata": {
            "model": "x",
            "temperature": 0.1,
            "top_p": 0.9,
            "timestamp": "2026-01-01T00:00:00Z",
        },
    }
    out = AgentResult.model_validate(payload)
    assert isinstance(out.solution_steps[0].action, str)
    assert "nested" in out.solution_steps[0].action
