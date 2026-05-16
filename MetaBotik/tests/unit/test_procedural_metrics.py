from __future__ import annotations

import json
from pathlib import Path

from src.evaluation.procedural_metrics import RESULT_ARTIFACT_JSON, discover_task_ids, evaluate_procedural


def test_discover_task_ids_ignores_evaluation_artifacts(tmp_path: Path) -> None:
    (tmp_path / "zarn_task_a.json").write_text("{}", encoding="utf-8")
    for name in RESULT_ARTIFACT_JSON:
        (tmp_path / name).write_text("{}", encoding="utf-8")

    assert discover_task_ids(tmp_path) == ["zarn_task_a"]


def test_evaluate_procedural_does_not_count_procedural_summary(tmp_path: Path) -> None:
    task_payload = {
        "task_id": "zarn_task_a",
        "task_type": "linear",
        "procedural_analysis": {
            "problem_classification": "linear workflow",
            "selected_procedure": "linear staged rollout",
            "selection_reasoning": "sequential dependencies",
            "alternative_procedures": [
                {"name": "branching", "rejection_reason": "no major forks"},
            ],
        },
        "solution_steps": [
            {
                "step": 1,
                "title": "Plan",
                "action": "Define scope",
                "procedure_logic": "scope first",
                "critical_points": ["missing owner"],
                "adaptation_notes": ["if blocked, escalate"],
            },
        ],
        "reflection": {
            "effectiveness": "worked",
            "limitations": ["data gaps"],
            "best_use_cases": ["ops handoffs"],
            "future_modifications": ["add checklist"],
        },
    }
    (tmp_path / "zarn_task_a.json").write_text(
        json.dumps(task_payload),
        encoding="utf-8",
    )
    (tmp_path / "procedural_summary.json").write_text('{"task_count": 1}', encoding="utf-8")

    evaluation = evaluate_procedural(tmp_path)

    assert evaluation.summary["task_count"] == 1
    assert [m.task_id for m in evaluation.by_task] == ["zarn_task_a"]
