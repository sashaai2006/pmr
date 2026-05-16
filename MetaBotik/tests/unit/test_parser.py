import json

import pytest

from src.domain.enums import Difficulty, TaskType
from src.parsing.exceptions import SchemaRepairNeeded
from src.parsing.parser import ResponseParser
from src.parsing.sanitize import extract_json_payload


def valid_agent_result_payload() -> dict[str, object]:
    return {
        "task_id": "FINAL-A01",
        "task_type": "diagnostic",
        "difficulty": "expert",
        "procedural_analysis": {
            "problem_classification": "Diagnostic metacognitive task",
            "selected_procedure": "diagnostic verification procedure",
            "selection_reasoning": "The task requires trap detection and revision.",
            "alternative_procedures": [
                {
                    "name": "linear staged execution",
                    "rejection_reason": "A fixed sequence cannot verify hidden traps.",
                },
                {
                    "name": "cyclic refinement loop",
                    "rejection_reason": "Overkill for a single-pass diagnostic task.",
                },
            ],
        },
        "solution_steps": [
            {
                "step": 1,
                "title": "Frame the task",
                "action": "Extract the goal and constraints.",
                "procedure_logic": "Framing prevents premature commitment.",
                "critical_points": ["Missing constraints can invalidate the answer."],
                "adaptation_notes": ["Ask for missing inputs if needed."],
            },
            {
                "step": 2,
                "title": "Identify the hidden trap",
                "action": "Scan for implicit assumptions and contradictions.",
                "procedure_logic": "Trap detection before solving avoids incorrect paths.",
                "critical_points": ["Trap may require domain knowledge to spot."],
                "adaptation_notes": ["Flag ambiguity and state assumptions explicitly."],
            },
            {
                "step": 3,
                "title": "Solve and verify",
                "action": "Apply the diagnostic procedure and cross-check the result.",
                "procedure_logic": "Verification closes the diagnostic loop.",
                "critical_points": ["Final answer may differ from initial intuition."],
                "adaptation_notes": ["Revise if verification reveals inconsistency."],
            },
        ],
        "reflection": {
            "effectiveness": "The diagnostic procedure exposed the hidden trap.",
            "limitations": [
                "Requires explicit uncertainty tracking.",
                "May miss traps that require external domain knowledge.",
            ],
            "best_use_cases": ["Trap-heavy expert tasks"],
            "future_modifications": ["Add an explicit error-recovery checkpoint."],
        },
        "metadata": {
            "model": "mock-model",
            "temperature": 0.3,
            "top_p": 0.9,
            "timestamp": "2026-05-13T20:00:00+00:00",
        },
    }


def test_parser_accepts_valid_json() -> None:
    parser = ResponseParser()
    result = parser.parse(json.dumps(valid_agent_result_payload()))
    assert result.task_id == "FINAL-A01"
    assert result.task_type == TaskType.DIAGNOSTIC
    assert result.difficulty == Difficulty.EXPERT


def test_parser_accepts_fenced_json() -> None:
    parser = ResponseParser()
    payload = json.dumps(valid_agent_result_payload())
    result = parser.parse(f"```json\n{payload}\n```")
    assert result.task_id == "FINAL-A01"


def test_extract_json_payload_from_wrapped_text() -> None:
    payload = '{"task_id":"FINAL-A01"}'
    assert extract_json_payload(f"Here is JSON:\n{payload}\nDone.") == payload


def test_parser_normalizes_common_model_schema_drift() -> None:
    """Verify that single strings are coerced to lists for array fields."""
    payload = valid_agent_result_payload()
    step = payload["solution_steps"][0]  # type: ignore[index]
    step["critical_points"] = "Single critical point"  # type: ignore[index]
    step["adaptation_notes"] = "Single adaptation note"  # type: ignore[index]
    reflection = payload["reflection"]  # type: ignore[index]
    reflection.pop("effectiveness")  # type: ignore[union-attr]
    # limitations requires min 2 items — provide a list to satisfy the constraint
    reflection["limitations"] = ["First limitation", "Second limitation"]  # type: ignore[index]
    reflection["best_use_cases"] = "Single use case"  # type: ignore[index]
    reflection["future_modifications"] = "Single modification"  # type: ignore[index]

    result = ResponseParser().parse(json.dumps(payload))

    assert result.solution_steps[0].critical_points == ["Single critical point"]
    assert result.solution_steps[0].adaptation_notes == ["Single adaptation note"]
    assert result.reflection.effectiveness
    assert result.reflection.limitations == ["First limitation", "Second limitation"]
    assert result.reflection.best_use_cases == ["Single use case"]
    assert result.reflection.future_modifications == ["Single modification"]


def test_parser_accepts_single_solution_step() -> None:
    """Cognitive economy: schema allows 1–7 steps; a genuinely atomic task may use one."""
    payload = valid_agent_result_payload()
    payload["solution_steps"] = [
        {
            "step": 1,
            "title": "Integrate and deliver",
            "action": "Delivered artifact: policy IF severity=critical THEN page_now ELSE next_day.",
            "procedure_logic": (
                "Transition: there is no prior step; inputs are the task statement and explicit assumptions. "
                "One atomic stage suffices because the task is a single decision-policy synthesis."
            ),
            "critical_points": ["Underspecified severity taxonomy would make the policy misfire."],
            "adaptation_notes": ["Add SLAs if paging windows differ by region."],
        }
    ]
    result = ResponseParser().parse(json.dumps(payload))
    assert len(result.solution_steps) == 1
    assert result.solution_steps[0].step == 1


def test_parser_raises_repair_for_invalid_json() -> None:
    parser = ResponseParser()
    with pytest.raises(SchemaRepairNeeded):
        parser.parse("{not-json")
