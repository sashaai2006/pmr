"""Markdown result formatting."""

from __future__ import annotations

from pathlib import Path

from src.domain.schemas import AgentResult


def format_markdown(result: AgentResult) -> str:
    lines = [
        f"# {result.task_id}",
        "",
        "## 1. Procedural analysis of the task",
        result.procedural_analysis.problem_classification,
        "",
        "## 2. Chosen procedure and justification",
        result.procedural_analysis.selected_procedure,
        result.procedural_analysis.selection_reasoning,
        "",
        "## 3. Step-by-step solution with procedural commentary",
    ]
    for step in result.solution_steps:
        lines.extend(
            [
                f"### Step {step.step}: {step.title}",
                step.action,
                step.procedure_logic,
                "",
            ]
        )
    lines.extend(
        [
            "## 4. Critical points and adaptation notes",
        ]
    )
    for step in result.solution_steps:
        for point in step.critical_points:
            lines.append(f"- {point}")
    lines.extend(
        [
            "",
            "## 5. Procedural reflection",
            result.reflection.effectiveness,
            "",
            "## 6. Modifications for similar tasks",
        ]
    )
    for item in result.reflection.future_modifications:
        lines.append(f"- {item}")
    return "\n".join(lines).strip() + "\n"


def save_markdown(result: AgentResult, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{result.task_id}.md"
    path.write_text(format_markdown(result), encoding="utf-8")
    return path
