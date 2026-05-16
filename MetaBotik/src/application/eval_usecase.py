"""Compute deterministic metrics over a run directory and persist them.

Reads `<run_dir>/*.json` answers, optionally a rubric CSV, and writes:

- `<run_dir>/by_task.jsonl` — one row per task with procedural rigor (and rubric if present).
- `<run_dir>/summary.json` — aggregate per-metric stats over the run.
"""

from __future__ import annotations

import logging
import statistics
from pathlib import Path
from typing import Any

from src.domain.schemas import (
    CaseScore,
    EvalReport,
    RubricAxes,
)
from src.evaluation.procedural_metrics import (
    RESULT_ARTIFACT_JSON,
    evaluate_procedural_one,
)
from src.evaluation.rubric_scorer import RubricEntry
from src.infrastructure.repo import read_json, write_json

log = logging.getLogger("metabotik.eval")

PASS_THRESHOLD_DEFAULT = 7


def _discover_answer_paths(run_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in run_dir.glob("*.json")
        if path.name not in RESULT_ARTIFACT_JSON and path.name != "run_summary.json"
    )


class EvalUseCase:
    def __init__(
        self,
        *,
        run_dir: Path,
        suite: str,
        mode: str,
        run_id: str,
        rubric_by_id: dict[str, RubricEntry] | None = None,
        pass_threshold: int = PASS_THRESHOLD_DEFAULT,
    ) -> None:
        self._run_dir = run_dir
        self._suite = suite
        self._mode = mode
        self._run_id = run_id
        self._rubric_by_id = rubric_by_id or {}
        self._pass_threshold = pass_threshold

    def _score_one(self, payload: dict[str, Any], task_id: str) -> CaseScore:
        proc_metrics = evaluate_procedural_one(task_id, self._run_dir / f"{task_id}.json")
        proc_score = proc_metrics.procedural_rigor_score

        rubric_entry = self._rubric_by_id.get(task_id)
        rubric: RubricAxes | None = None
        rubric_total: int | None = None
        pass_binary: bool | None = None
        if rubric_entry is not None:
            rubric = rubric_entry.axes
            rubric_total = rubric_entry.total
            pass_binary = rubric_total >= self._pass_threshold

        return CaseScore(
            task_id=task_id,
            procedural_rigor_score=proc_score,
            rubric=rubric,
            rubric_total=rubric_total,
            pass_threshold=self._pass_threshold,
            pass_binary=pass_binary,
            notes=rubric_entry.notes if rubric_entry else None,
        )

    def run(self) -> EvalReport:
        answer_paths = _discover_answer_paths(self._run_dir)
        log.info("eval suite=%s mode=%s run_id=%s answers=%d", self._suite, self._mode, self._run_id, len(answer_paths))
        scores: list[CaseScore] = []
        for path in answer_paths:
            task_id = path.stem
            try:
                payload = read_json(path)
            except Exception as exc:  # noqa: BLE001
                log.warning("[%s] cannot read %s: %s", task_id, path, exc)
                continue
            if not isinstance(payload, dict):
                log.warning("[%s] payload is not a JSON object: skipping", task_id)
                continue
            scores.append(self._score_one(payload, task_id))

        summary = self._aggregate(scores)
        report = EvalReport(
            suite=self._suite,
            mode=self._mode,
            run_id=self._run_id,
            n_tasks=len(scores),
            by_task=scores,
            summary=summary,
        )
        self._persist(report)
        return report

    def _aggregate(self, scores: list[CaseScore]) -> dict[str, Any]:
        n = len(scores)
        if n == 0:
            return {"n_tasks": 0}

        proc = [s.procedural_rigor_score for s in scores if s.procedural_rigor_score is not None]
        rubric_totals = [s.rubric_total for s in scores if s.rubric_total is not None]
        pass_flags = [s.pass_binary for s in scores if s.pass_binary is not None]

        summary: dict[str, Any] = {
            "n_tasks": n,
            "suite": self._suite,
            "mode": self._mode,
            "run_id": self._run_id,
            "procedural_rigor_mean": round(statistics.mean(proc), 4) if proc else 0.0,
            "procedural_rigor_std": round(statistics.stdev(proc), 4) if len(proc) > 1 else 0.0,
        }
        if rubric_totals:
            summary["rubric_score_mean"] = round(statistics.mean(rubric_totals), 4)
            summary["rubric_score_std"] = round(statistics.stdev(rubric_totals), 4) if len(rubric_totals) > 1 else 0.0
        if pass_flags:
            summary["pass_rate"] = round(sum(pass_flags) / len(pass_flags), 4)
        return summary

    def _persist(self, report: EvalReport) -> None:
        write_json(self._run_dir / "summary.json", report.summary)
        rows: list[dict[str, Any]] = []
        for score in report.by_task:
            row: dict[str, Any] = {
                "task_id": score.task_id,
                "procedural_rigor_score": score.procedural_rigor_score,
            }
            if score.rubric is not None:
                row["rubric"] = score.rubric.model_dump()
                row["rubric_total"] = score.rubric_total
                row["pass_binary"] = score.pass_binary
            if score.notes:
                row["notes"] = score.notes
            rows.append(row)
        # Write JSONL by hand to keep one row per line, with stable ordering.
        out_path = self._run_dir / "by_task.jsonl"
        out_path.parent.mkdir(parents=True, exist_ok=True)
        import json as _json

        with out_path.open("w", encoding="utf-8") as handle:
            for row in rows:
                handle.write(_json.dumps(row, ensure_ascii=False))
                handle.write("\n")
        log.info("eval persisted summary + by_task -> %s", self._run_dir)
