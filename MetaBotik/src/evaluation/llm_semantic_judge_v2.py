"""LLM-backed semantic judge for flexible PMR-Bench gold v2 rubrics."""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.domain.schemas import ChatMessage, GoldV2Entry
from src.infrastructure.repo import read_json, write_json, write_jsonl
from src.llm.client import LLMClient

log = logging.getLogger("metabotik.llm_judge_v2")

BY_TASK_FILENAME = "llm_judge_v2_by_task.jsonl"
SUMMARY_FILENAME = "llm_judge_v2_summary.json"
FATAL_DIMENSIONS = {"fatal_omission", "fatal"}


class V2CriterionJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    dimension: str
    criterion_id: str
    score: float = Field(ge=0.0, le=1.0)
    verdict: str
    evidence: str
    reason: str


class V2TaskSemanticJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    selected_solution_family_id: str | None = None
    solution_family_reason: str
    judgments: list[V2CriterionJudgment]
    must_have_score: float = Field(ge=0.0, le=1.0)
    optional_score: float = Field(ge=0.0, le=1.0)
    fatal_penalty: float = Field(ge=0.0, le=1.0)
    overall_score: float = Field(ge=0.0, le=1.0)
    pass_binary: bool
    overall_assessment: str


@dataclass(frozen=True)
class SemanticJudgeV2Report:
    summary: dict[str, Any]
    by_task: list[dict[str, Any]]


SYSTEM_PROMPT = """Ты — строгий семантический судья PMR-Bench gold_v2.

Цель: оценить ответ агента без one-rigid-answer bias. Не сравнивай ответ с
единственным эталонным текстом. Вместо этого:
1. Определи, к какой acceptable_solution_family относится ответ, если относится.
2. Оцени must_have_invariants по смыслу: 1.0 = выполнено, 0.5 = частично,
   0.0 = отсутствует/противоречит.
3. Оцени fatal_omissions как триггеры: 1.0 = fatal проблема явно есть,
   0.5 = частично есть, 0.0 = fatal проблема отсутствует.
4. Оцени optional_nice_to_have так же, как обычные положительные критерии.

Строгость:
- Не награждай за красивые слова о PMR, если нет конкретной процедуры.
- Засчитывай разные формулировки и разные допустимые семьи решений, если
  сохранены must-have invariants.
- Fatal omission должен снижать итог даже при хорошем стиле ответа.
- Evidence — короткая цитата или точный пересказ места в ответе.

Верни только валидный JSON по схеме:
{
  "task_id": "...",
  "selected_solution_family_id": "family id or null",
  "solution_family_reason": "краткое объяснение",
  "judgments": [
    {
      "dimension": "must_have|fatal_omission|optional",
      "criterion_id": "id из gold_v2",
      "score": 0.0,
      "verdict": "satisfied|partial|missing|triggered|not_triggered",
      "evidence": "короткое свидетельство или empty",
      "reason": "краткое объяснение"
    }
  ],
  "must_have_score": 0.0,
  "optional_score": 0.0,
  "fatal_penalty": 0.0,
  "overall_score": 0.0,
  "pass_binary": false,
  "overall_assessment": "1-3 предложения"
}
"""


def _build_messages(task_id: str, answer: dict[str, Any], gold: GoldV2Entry) -> list[ChatMessage]:
    user_payload = {
        "task_id": task_id,
        "gold_v2_rubric": gold.rubric.model_dump(mode="json"),
        "reference_answer_for_context_not_canonical": (
            gold.reference_answer.model_dump(mode="json") if gold.reference_answer else None
        ),
        "agent_answer": answer,
        "scoring_contract": {
            "must_have_score": "weighted mean of must_have_invariants",
            "optional_score": "weighted mean of optional_nice_to_have; 0 if none",
            "fatal_penalty": "max fatal_omissions trigger score; 0 if none",
            "overall_score": "clamped 0..1: 0.8 * must_have_score + 0.2 * optional_score - 0.5 * fatal_penalty",
            "pass_binary": "true only if must_have_score >= 0.70, fatal_penalty < 0.50, overall_score >= 0.70",
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
    payload = json.loads(text)
    if not isinstance(payload, dict):
        raise ValueError("semantic judge v2 response must be a JSON object")
    return payload


def _weighted_average(
    judgments: list[V2CriterionJudgment],
    *,
    dimension: str,
    weights: dict[str, float],
) -> float:
    selected = [item for item in judgments if item.dimension == dimension]
    if not selected:
        return 0.0
    total_weight = sum(weights.get(item.criterion_id, 1.0) for item in selected)
    if total_weight <= 0:
        return 0.0
    score = sum(item.score * weights.get(item.criterion_id, 1.0) for item in selected) / total_weight
    return round(score, 4)


def _recompute_scores(judgment: V2TaskSemanticJudgment, gold: GoldV2Entry) -> V2TaskSemanticJudgment:
    must_weights = {item.id: item.weight for item in gold.rubric.must_have_invariants}
    optional_weights = {item.id: item.weight for item in gold.rubric.optional_nice_to_have}
    must_have_score = _weighted_average(judgment.judgments, dimension="must_have", weights=must_weights)
    optional_score = _weighted_average(judgment.judgments, dimension="optional", weights=optional_weights)
    fatal_scores = [item.score for item in judgment.judgments if item.dimension in FATAL_DIMENSIONS]
    fatal_penalty = round(max(fatal_scores), 4) if fatal_scores else 0.0
    overall = max(0.0, min(1.0, 0.8 * must_have_score + 0.2 * optional_score - 0.5 * fatal_penalty))
    overall_score = round(overall, 4)
    pass_binary = must_have_score >= 0.7 and fatal_penalty < 0.5 and overall_score >= 0.7
    return judgment.model_copy(
        update={
            "must_have_score": must_have_score,
            "optional_score": optional_score,
            "fatal_penalty": fatal_penalty,
            "overall_score": overall_score,
            "pass_binary": pass_binary,
        },
    )


class LLMSemanticJudgeV2UseCase:
    def __init__(self, *, run_dir: Path, gold_by_id: dict[str, GoldV2Entry], llm: LLMClient) -> None:
        self._run_dir = run_dir
        self._gold_by_id = gold_by_id
        self._llm = llm

    def judge_one(self, task_id: str) -> V2TaskSemanticJudgment:
        gold = self._gold_by_id[task_id]
        answer = read_json(self._run_dir / f"{task_id}.json")
        if not isinstance(answer, dict):
            raise ValueError(f"{task_id}: answer is not a JSON object")
        completion = self._llm.complete(_build_messages(task_id, answer, gold), json_response=True)
        try:
            payload = _extract_json(completion.content)
            judgment = V2TaskSemanticJudgment.model_validate(payload)
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            raise ValueError(f"{task_id}: invalid semantic judge v2 response: {exc}") from exc
        if judgment.task_id != task_id:
            judgment = judgment.model_copy(update={"task_id": task_id})
        return _recompute_scores(judgment, gold)

    def execute(self, *, task_ids: list[str] | None = None, sleep_seconds: float = 0.0) -> SemanticJudgeV2Report:
        if task_ids is None:
            task_ids = sorted(
                path.stem
                for path in self._run_dir.glob("PMR-*.json")
                if path.stem in self._gold_by_id
            )
        task_ids = [task_id for task_id in task_ids if task_id in self._gold_by_id]
        rows: list[dict[str, Any]] = []
        for index, task_id in enumerate(task_ids):
            log.info("llm semantic judge v2 task %d/%d %s", index + 1, len(task_ids), task_id)
            judgment = self.judge_one(task_id)
            rows.append(judgment.model_dump(mode="json"))
            if index + 1 < len(task_ids) and sleep_seconds > 0:
                time.sleep(sleep_seconds)

        summary = _summarise(rows)
        write_jsonl(self._run_dir / BY_TASK_FILENAME, rows)
        write_json(self._run_dir / SUMMARY_FILENAME, summary)
        return SemanticJudgeV2Report(summary=summary, by_task=rows)


def _summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n_tasks": 0}
    must = [float(row.get("must_have_score", 0.0)) for row in rows]
    optional = [float(row.get("optional_score", 0.0)) for row in rows]
    fatal = [float(row.get("fatal_penalty", 0.0)) for row in rows]
    overall = [float(row.get("overall_score", 0.0)) for row in rows]
    passes = [bool(row.get("pass_binary", False)) for row in rows]
    return {
        "n_tasks": len(rows),
        "must_have_score": round(sum(must) / len(must), 4),
        "optional_score": round(sum(optional) / len(optional), 4),
        "fatal_penalty": round(sum(fatal) / len(fatal), 4),
        "overall_score": round(sum(overall) / len(overall), 4),
        "pass_rate": round(sum(passes) / len(passes), 4),
    }
