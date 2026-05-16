"""Rubric scoring for PMR-Bench answers.

The rubric has 5 axes scored 0-2 each (total 0-10):
  - procedural_self_awareness
  - decomposition_quality (→ stored as decomposition_quality)
  - justification_depth
  - reflection_actionability
  - reproducibility

Two scoring sources are supported:

1.  `manual` — load a CSV produced by a human judge. The CSV has columns
    `task_id,procedural_self_awareness,decomposition_quality,justification_depth,
    reflection_actionability,reproducibility[,notes]`.

2.  `llm_judge` — invoke an LLM to fill the rubric. NotImplemented yet — left
    as an extension hook for future automation.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.domain.schemas import RubricAxes

DEFAULT_PASS_THRESHOLD = 7

RUBRIC_AXES: tuple[str, ...] = (
    "procedural_self_awareness",
    "decomposition_quality",
    "justification_depth",
    "reflection_actionability",
    "reproducibility",
)


@dataclass(frozen=True)
class RubricEntry:
    task_id: str
    axes: RubricAxes
    notes: str | None = None

    @property
    def total(self) -> int:
        return self.axes.total


def load_manual_csv(path: Path) -> dict[str, RubricEntry]:
    """Load a CSV with one row per task_id."""
    out: dict[str, RubricEntry] = {}
    with path.open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError(f"empty rubric CSV: {path}")
        missing = [c for c in ("task_id", *RUBRIC_AXES) if c not in reader.fieldnames]
        if missing:
            raise ValueError(f"rubric CSV missing columns: {missing}")
        for row in reader:
            task_id = row["task_id"].strip()
            if not task_id:
                continue
            axes = RubricAxes(
                procedural_self_awareness=int(row["procedural_self_awareness"]),
                decomposition_quality=int(row["decomposition_quality"]),
                justification_depth=int(row["justification_depth"]),
                reflection_actionability=int(row["reflection_actionability"]),
                reproducibility=int(row["reproducibility"]),
            )
            out[task_id] = RubricEntry(task_id=task_id, axes=axes, notes=row.get("notes") or None)
    return out


def emit_blank_csv(path: Path, task_ids: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["task_id", *RUBRIC_AXES, "notes"])
        for task_id in task_ids:
            writer.writerow([task_id, 0, 0, 0, 0, 0, ""])


def score_with_llm_judge(
    *,
    payload: dict[str, Any],  # noqa: ARG001
    rubric_text: str,  # noqa: ARG001
    judge_prompt_path: Path | None = None,  # noqa: ARG001
) -> RubricAxes:
    """Stub for the LLM-as-judge variant. Wire up in `judge_usecase.py`."""
    raise NotImplementedError(
        "LLM-judge rubric scoring is not yet implemented. "
        "Use manual CSV via load_manual_csv() or add a judge use-case.",
    )
