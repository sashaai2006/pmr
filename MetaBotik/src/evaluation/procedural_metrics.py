"""Deterministic procedural-rigor metrics for PMR vs baseline outputs.

These metrics measure how explicit the procedural reasoning is in the saved JSON,
NOT whether the workflow answer is correct (Zarn already covers that).

Design contract:
- Pure functions, no LLM calls.
- Same scoring logic applies to PMR JSON and baseline JSON.
- PMR's explicit fields (procedural_analysis, solution_steps, reflection) score high
  because they exist by construction; baseline scores low when those fields are
  absent and rarely appears in plain text. This is the legitimate signal we measure:
  "Does the answer expose its procedure or not?"
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from typing import Any

# Evaluation artifacts written into results_dir; must not be scored as tasks.
RESULT_ARTIFACT_JSON: frozenset[str] = frozenset(
    {
        "summary.json",
        "procedural_summary.json",
        "coverage_summary.json",
        "rubric_summary.json",
        "metrics_summary.json",
        "slice_breakdown.json",
    }
)

PROCEDURE_TYPE_TOKENS: tuple[str, ...] = (
    "linear",
    "branching",
    "cyclic",
    "analytical",
    "diagnostic",
    "creative",
    "mixed",
    "линейн",
    "ветвящ",
    "цикл",
    "аналитич",
    "диагностич",
    "креативн",
    "смешан",
)

ACTIONABLE_VERBS: tuple[str, ...] = (
    "introduce",
    "replace",
    "add",
    "remove",
    "tighten",
    "loosen",
    "swap",
    "expand",
    "narrow",
    "validate",
    "automate",
    "split",
    "ввести",
    "заменить",
    "добавить",
    "удалить",
    "разбить",
    "автоматизир",
    "проверить",
    "усилить",
    "уточнить",
)

REFLECTION_KEYS: tuple[str, ...] = (
    "effectiveness",
    "limitations",
    "best_use_cases",
    "future_modifications",
)


@dataclass(frozen=True)
class ProceduralTaskMetrics:
    task_id: str
    procedure_classification: float
    procedure_justification: float
    alternative_procedures: float
    critical_points_density: float
    adaptation_specificity: float
    reflection_actionability: float
    procedural_rigor_score: float
    procedural_trace_present: float
    error: str | None = None


@dataclass(frozen=True)
class ProceduralEvaluation:
    summary: dict[str, Any]
    by_task: list[ProceduralTaskMetrics]


def discover_task_ids(results_dir: Path) -> list[str]:
    """Return task result stems in results_dir, excluding evaluation artifact JSON files."""
    return sorted(
        path.stem
        for path in results_dir.glob("*.json")
        if path.name not in RESULT_ARTIFACT_JSON
    )


def evaluate_procedural(results_dir: Path, task_ids: list[str] | None = None) -> ProceduralEvaluation:
    if task_ids is None:
        task_ids = discover_task_ids(results_dir)
    by_task = [evaluate_procedural_one(task_id, results_dir / f"{task_id}.json") for task_id in task_ids]
    summary = _aggregate(by_task)
    return ProceduralEvaluation(summary=summary, by_task=by_task)


def save_procedural_evaluation(evaluation: ProceduralEvaluation, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "procedural_summary.json").write_text(
        json.dumps(evaluation.summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    with (output_dir / "procedural_by_task.jsonl").open("w", encoding="utf-8") as handle:
        for metrics in evaluation.by_task:
            handle.write(json.dumps(asdict(metrics), ensure_ascii=False))
            handle.write("\n")


def evaluate_procedural_one(task_id: str, result_path: Path) -> ProceduralTaskMetrics:
    try:
        result = json.loads(result_path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return _empty(task_id, f"missing result: {result_path}")
    except json.JSONDecodeError as exc:
        return _empty(task_id, f"invalid JSON: {exc}")
    if not isinstance(result, dict):
        return _empty(task_id, "result is not a JSON object")

    trace = _trace_present(result)
    classification = _classification_score(result)
    justification = _justification_score(result)
    alternatives = _alternatives_score(result)
    critical = _critical_points_score(result)
    adaptation = _adaptation_score(result)
    reflection = _reflection_score(result)
    rigor = _rigor_composite(
        classification=classification,
        justification=justification,
        alternatives=alternatives,
        critical=critical,
        adaptation=adaptation,
        reflection=reflection,
    )
    return ProceduralTaskMetrics(
        task_id=task_id,
        procedure_classification=classification,
        procedure_justification=justification,
        alternative_procedures=alternatives,
        critical_points_density=critical,
        adaptation_specificity=adaptation,
        reflection_actionability=reflection,
        procedural_rigor_score=rigor,
        procedural_trace_present=trace,
    )


def _trace_present(result: dict[str, Any]) -> float:
    has_pa = isinstance(result.get("procedural_analysis"), dict)
    has_steps = isinstance(result.get("solution_steps"), list) and result["solution_steps"]
    has_reflection = isinstance(result.get("reflection"), dict)
    return 1.0 if (has_pa and has_steps and has_reflection) else 0.0


def _classification_score(result: dict[str, Any]) -> float:
    pa = result.get("procedural_analysis")
    if isinstance(pa, dict):
        problem = str(pa.get("problem_classification", "")).strip()
        selected = str(pa.get("selected_procedure", "")).strip()
        if problem and selected:
            return 1.0
        if problem or selected:
            return 0.5
    text = _flatten_text(result).lower()
    matches = sum(1 for token in PROCEDURE_TYPE_TOKENS if token in text)
    if matches >= 2:
        return 0.5
    if matches == 1:
        return 0.25
    return 0.0


def _justification_score(result: dict[str, Any]) -> float:
    pa = result.get("procedural_analysis")
    if isinstance(pa, dict):
        reasoning = str(pa.get("selection_reasoning", "")).strip()
        if reasoning:
            length_score = min(len(reasoning) / 240.0, 1.0)
            cause_marker = any(
                token in reasoning.lower()
                for token in (
                    "because",
                    "since",
                    "in order to",
                    "to ensure",
                    "to avoid",
                    "потому что",
                    "так как",
                    "чтобы",
                    "поскольку",
                )
            )
            return _round(0.5 * length_score + 0.5 * (1.0 if cause_marker else 0.0))
    return 0.0


def _alternatives_score(result: dict[str, Any]) -> float:
    pa = result.get("procedural_analysis")
    if isinstance(pa, dict):
        alts = pa.get("alternative_procedures")
        if isinstance(alts, list) and alts:
            valid = 0
            for item in alts:
                if not isinstance(item, dict):
                    continue
                name = str(item.get("name", "")).strip()
                reason = str(item.get("rejection_reason", "")).strip()
                if name and reason and len(reason) >= 20:
                    valid += 1
            return _round(min(valid / 2.0, 1.0))
    return 0.0


def _critical_points_score(result: dict[str, Any]) -> float:
    steps = result.get("solution_steps")
    if isinstance(steps, list) and steps:
        counts: list[int] = []
        for step in steps:
            if not isinstance(step, dict):
                counts.append(0)
                continue
            critical = step.get("critical_points")
            count = len([item for item in (critical or []) if str(item).strip()])
            counts.append(count)
        if counts:
            average = mean(counts)
            return _round(min(average / 1.5, 1.0))
        return 0.0
    text = _flatten_text(result).lower()
    matches = sum(
        text.count(marker)
        for marker in ("critical point", "risk:", "watch out", "критическ", "риск", "точка отказа")
    )
    return _round(min(matches / 5.0, 1.0))


def _adaptation_score(result: dict[str, Any]) -> float:
    steps = result.get("solution_steps")
    if isinstance(steps, list) and steps:
        per_step: list[float] = []
        for step in steps:
            if not isinstance(step, dict):
                per_step.append(0.0)
                continue
            notes = step.get("adaptation_notes")
            if not isinstance(notes, list) or not notes:
                per_step.append(0.0)
                continue
            specific = 0
            for note in notes:
                value = str(note).strip()
                if len(value) >= 30 and any(ch in value for ch in (",", ":", ";", "—", "-")):
                    specific += 1
            per_step.append(min(specific / 2.0, 1.0))
        if per_step:
            return _round(mean(per_step))
    return 0.0


def _reflection_score(result: dict[str, Any]) -> float:
    reflection = result.get("reflection")
    if not isinstance(reflection, dict):
        return 0.0
    present_keys = sum(1 for key in REFLECTION_KEYS if reflection.get(key))
    key_coverage = present_keys / len(REFLECTION_KEYS)
    future = reflection.get("future_modifications")
    actionable_ratio = 0.0
    if isinstance(future, list) and future:
        actionable = 0
        for item in future:
            text = str(item).lower()
            if len(text) < 25:
                continue
            if any(verb in text for verb in ACTIONABLE_VERBS):
                actionable += 1
        actionable_ratio = min(actionable / max(len(future), 1), 1.0)
    return _round(0.4 * key_coverage + 0.6 * actionable_ratio)


def _rigor_composite(
    *,
    classification: float,
    justification: float,
    alternatives: float,
    critical: float,
    adaptation: float,
    reflection: float,
) -> float:
    return _round(
        0.15 * classification
        + 0.15 * justification
        + 0.15 * alternatives
        + 0.20 * critical
        + 0.20 * adaptation
        + 0.15 * reflection
    )


def _flatten_text(result: dict[str, Any]) -> str:
    return json.dumps(result, ensure_ascii=False)


def _empty(task_id: str, error: str) -> ProceduralTaskMetrics:
    return ProceduralTaskMetrics(
        task_id=task_id,
        procedure_classification=0.0,
        procedure_justification=0.0,
        alternative_procedures=0.0,
        critical_points_density=0.0,
        adaptation_specificity=0.0,
        reflection_actionability=0.0,
        procedural_rigor_score=0.0,
        procedural_trace_present=0.0,
        error=error,
    )


def _aggregate(by_task: list[ProceduralTaskMetrics]) -> dict[str, Any]:
    fields = [
        "procedure_classification",
        "procedure_justification",
        "alternative_procedures",
        "critical_points_density",
        "adaptation_specificity",
        "reflection_actionability",
        "procedural_rigor_score",
        "procedural_trace_present",
    ]
    summary: dict[str, Any] = {"task_count": len(by_task)}
    for name in fields:
        values = [float(getattr(task, name)) for task in by_task]
        summary[name] = _round(mean(values)) if values else 0.0
    summary["failed_tasks"] = [task.task_id for task in by_task if task.error is not None]
    return summary


def _round(value: float) -> float:
    if not isinstance(value, (int, float)):
        return 0.0
    return round(float(value), 4)
