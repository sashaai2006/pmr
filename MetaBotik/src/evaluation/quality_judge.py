"""LLM-backed semantic quality judge for PMR-Bench answers.

Separate from lightweight `eval` (task bookkeeping / optional manual rubric): this
module scores answer quality by semantic criteria.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.domain.schemas import ChatMessage, GoldV2Entry, NormalizedTask
from src.infrastructure.repo import read_json, write_json, write_jsonl
from src.llm.client import LLMClient

log = logging.getLogger("metabotik.quality_judge")

BY_TASK_FILENAME = "quality_judge_by_task.jsonl"
SUMMARY_FILENAME = "quality_judge_summary.json"
PASS_THRESHOLD_DEFAULT = 7.0

QUALITY_AXES = (
    "completeness",
    "accuracy",
    "latent_pattern_quality",
    "practical_value",
)
AI_SCORE_WEIGHTS = {
    "completeness": 0.25,
    "accuracy": 0.30,
    "latent_pattern_quality": 0.20,
    "practical_value": 0.25,
}


class QualityAxisJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: float = Field(ge=0.0, le=10.0)
    rationale: str
    evidence: str = ""


class QualityTaskJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    completeness: QualityAxisJudgment
    accuracy: QualityAxisJudgment
    latent_pattern_quality: QualityAxisJudgment
    practical_value: QualityAxisJudgment
    ai_score: float = Field(default=0.0, ge=0.0, le=10.0)
    pass_binary: bool = False
    overall_assessment: str


@dataclass(frozen=True)
class QualityJudgeReport:
    summary: dict[str, Any]
    by_task: list[dict[str, Any]]


from src.evaluation.judge_prompt import QUALITY_JUDGE_SYSTEM_PROMPT

SYSTEM_PROMPT = QUALITY_JUDGE_SYSTEM_PROMPT + """

Верни только валидный JSON по схеме:
{
  "task_id": "...",
  "completeness": {"score": 0.0, "rationale": "...", "evidence": "..."},
  "accuracy": {"score": 0.0, "rationale": "...", "evidence": "..."},
  "latent_pattern_quality": {"score": 0.0, "rationale": "...", "evidence": "..."},
  "practical_value": {"score": 0.0, "rationale": "...", "evidence": "..."},
  "ai_score": 0.0,
  "pass_binary": false,
  "overall_assessment": "1-3 предложения"
}
"""


def _build_messages(
    task: NormalizedTask,
    answer: dict[str, Any],
    gold_v2: GoldV2Entry | None,
) -> list[ChatMessage]:
    user_payload = {
        "task": task.model_dump(mode="json"),
        "gold_v2_context_optional": (
            {
                "rubric": gold_v2.rubric.model_dump(mode="json"),
                "reference_answer_for_context_not_canonical": (
                    gold_v2.reference_answer.model_dump(mode="json")
                    if gold_v2.reference_answer
                    else None
                ),
            }
            if gold_v2 is not None
            else None
        ),
        "agent_answer": answer,
        "scoring_contract": {
            "axis_scale": "0..10 for completeness, accuracy, latent_pattern_quality, practical_value",
            "ai_score": (
                "computed by code as 0.25*completeness + 0.30*accuracy "
                "+ 0.20*latent_pattern_quality + 0.25*practical_value"
            ),
            "pass_binary": "computed by code from ai_score >= pass_threshold",
            "coverage_warning": "do not score by text overlap or claim coverage counts",
        },
    }
    return [
        ChatMessage(role="system", content=SYSTEM_PROMPT),
        ChatMessage(role="user", content=json.dumps(user_payload, ensure_ascii=False, indent=2)),
    ]


def _extract_json(raw: str) -> dict[str, Any]:
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end >= start:
        text = text[start : end + 1]
    payload = json.loads(text, strict=False)
    if not isinstance(payload, dict):
        raise ValueError("quality judge response must be a JSON object")
    return payload


def compute_ai_score(*, completeness: float, accuracy: float, latent_pattern_quality: float, practical_value: float) -> float:
    """Return the weighted integral quality score on the 0..10 scale."""

    score = (
        AI_SCORE_WEIGHTS["completeness"] * completeness
        + AI_SCORE_WEIGHTS["accuracy"] * accuracy
        + AI_SCORE_WEIGHTS["latent_pattern_quality"] * latent_pattern_quality
        + AI_SCORE_WEIGHTS["practical_value"] * practical_value
    )
    return round(max(0.0, min(10.0, score)), 4)


def _recompute_scores(
    judgment: QualityTaskJudgment,
    *,
    pass_threshold: float = PASS_THRESHOLD_DEFAULT,
) -> QualityTaskJudgment:
    ai_score = compute_ai_score(
        completeness=judgment.completeness.score,
        accuracy=judgment.accuracy.score,
        latent_pattern_quality=judgment.latent_pattern_quality.score,
        practical_value=judgment.practical_value.score,
    )
    return judgment.model_copy(
        update={
            "ai_score": ai_score,
            "pass_binary": ai_score >= pass_threshold,
        },
    )


class QualityJudgeUseCase:
    def __init__(
        self,
        *,
        run_dir: Path,
        tasks_by_id: dict[str, NormalizedTask],
        llm: LLMClient,
        gold_v2_by_id: dict[str, GoldV2Entry] | None = None,
        pass_threshold: float = PASS_THRESHOLD_DEFAULT,
    ) -> None:
        self._run_dir = run_dir
        self._tasks_by_id = tasks_by_id
        self._gold_v2_by_id = gold_v2_by_id or {}
        self._llm = llm
        self._pass_threshold = pass_threshold

    def judge_one(self, task_id: str) -> QualityTaskJudgment:
        task = self._tasks_by_id[task_id]
        answer = read_json(self._run_dir / f"{task_id}.json")
        if not isinstance(answer, dict):
            raise ValueError(f"{task_id}: answer is not a JSON object")
        completion = self._llm.complete(
            _build_messages(task, answer, self._gold_v2_by_id.get(task_id)),
            json_response=True,
        )
        try:
            payload = _extract_json(completion.content)
            judgment = QualityTaskJudgment.model_validate(payload)
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            raise ValueError(f"{task_id}: invalid quality judge response: {exc}") from exc
        if judgment.task_id != task_id:
            judgment = judgment.model_copy(update={"task_id": task_id})
        return _recompute_scores(judgment, pass_threshold=self._pass_threshold)

    def execute(self, *, task_ids: list[str] | None = None, sleep_seconds: float = 0.0) -> QualityJudgeReport:
        if task_ids is None:
            task_ids = sorted(
                path.stem
                for path in self._run_dir.glob("PMR-*.json")
                if path.stem in self._tasks_by_id
            )
        task_ids = [task_id for task_id in task_ids if task_id in self._tasks_by_id]
        rows: list[dict[str, Any]] = []
        for index, task_id in enumerate(task_ids):
            log.info("quality judge task %d/%d %s", index + 1, len(task_ids), task_id)
            judgment = self.judge_one(task_id)
            rows.append(judgment.model_dump(mode="json"))
            if index + 1 < len(task_ids) and sleep_seconds > 0:
                time.sleep(sleep_seconds)

        summary = summarise_quality_rows(rows)
        write_jsonl(self._run_dir / BY_TASK_FILENAME, rows)
        write_json(self._run_dir / SUMMARY_FILENAME, summary)
        return QualityJudgeReport(summary=summary, by_task=rows)


def summarise_quality_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n_tasks": 0}

    axis_values: dict[str, list[float]] = {axis: [] for axis in QUALITY_AXES}
    ai_scores: list[float] = []
    passes: list[bool] = []
    for row in rows:
        for axis in QUALITY_AXES:
            value = row.get(axis)
            if isinstance(value, dict) and "score" in value:
                axis_values[axis].append(float(value["score"]))
        ai_scores.append(float(row.get("ai_score", 0.0)))
        passes.append(bool(row.get("pass_binary", False)))

    summary: dict[str, Any] = {
        "n_tasks": len(rows),
        "completeness_mean": _mean(axis_values["completeness"]),
        "accuracy_mean": _mean(axis_values["accuracy"]),
        "latent_pattern_quality_mean": _mean(axis_values["latent_pattern_quality"]),
        "practical_value_mean": _mean(axis_values["practical_value"]),
        "ai_score_mean": _mean(ai_scores),
        "pass_rate": round(sum(passes) / len(passes), 4),
    }
    return summary


def _mean(values: list[float]) -> float:
    return round(sum(values) / len(values), 4) if values else 0.0
