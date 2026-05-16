"""Rubric scoring use-cases.

Two flows:

- `MANUAL`: emit a blank CSV the human judge fills in, then load it.
- `LLM_JUDGE`: stub for an automated LLM judge (not implemented yet).
"""

from __future__ import annotations

import logging
from pathlib import Path

from src.evaluation.rubric_scorer import RubricEntry, emit_blank_csv, load_manual_csv

log = logging.getLogger("metabotik.judge")


class JudgeUseCase:
    def __init__(self, run_dir: Path) -> None:
        self._run_dir = run_dir

    def template_path(self) -> Path:
        return self._run_dir / "rubric_scores.csv"

    def emit_template(self, task_ids: list[str]) -> Path:
        path = self.template_path()
        emit_blank_csv(path, task_ids)
        log.info("emitted blank rubric CSV with %d rows -> %s", len(task_ids), path)
        return path

    def load(self) -> dict[str, RubricEntry]:
        path = self.template_path()
        if not path.exists():
            log.info("no rubric_scores.csv at %s; returning empty rubric set", path)
            return {}
        entries = load_manual_csv(path)
        log.info("loaded %d manual rubric entries from %s", len(entries), path)
        return entries
