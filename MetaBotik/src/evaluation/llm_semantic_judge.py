"""LLM-backed semantic judge for PMR-Bench gold-claim coverage.

This module is intentionally separate from deterministic eval. It answers a
different question: "Does the answer satisfy each expected claim by meaning,
even when it uses different words?"
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from src.domain.schemas import ChatMessage, GoldEntry
from src.evaluation.element_coverage import CLAIM_CATEGORIES
from src.infrastructure.repo import read_json, write_json, write_jsonl
from src.llm.client import LLMClient

log = logging.getLogger("metabotik.llm_judge")


class ClaimJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    category: str
    claim: str
    score: float = Field(ge=0.0, le=1.0)
    verdict: str
    evidence: str
    reason: str


class TaskSemanticJudgment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    claim_judgments: list[ClaimJudgment]
    category_scores: dict[str, float]
    semantic_coverage_macro: float
    semantic_coverage_micro: float
    overall_assessment: str


@dataclass(frozen=True)
class SemanticJudgeReport:
    summary: dict[str, Any]
    by_task: list[dict[str, Any]]


SYSTEM_PROMPT = """Ты — строгий семантический судья PMR-Bench.

Твоя задача — оценить, покрывает ли ответ агента ожидаемые gold-claims ПО СМЫСЛУ,
а не по буквальному совпадению слов. Не оценивай стиль и не награждай за сам факт
наличия PMR-структуры. Проверяй только: присутствует ли в ответе та же процедура,
тот же отвергнутый вариант, та же критическая точка или тот же мета-протокол.

Оценка каждого claim:
- 1.0 = claim покрыт явно или уверенно перефразирован;
- 0.5 = claim частично покрыт: есть близкая идея, но отсутствует важная часть;
- 0.0 = claim отсутствует, противоречит ответу или слишком общий.

Правила строгости:
- Не засчитывай общий текст, если он не фиксирует конкретный смысл claim.
- Не засчитывай альтернативу, если названа другая процедура или причина отказа.
- Не засчитывай critical point, если нет точки отказа/невозврата/условия адаптации.
- Не засчитывай meta_protocol, если нет переносимого правила для похожих задач.
- Используй evidence — короткую цитату или пересказ конкретного места ответа.

Верни только валидный JSON по схеме:
{
  "task_id": "...",
  "claim_judgments": [
    {
      "category": "decomposition|rejected_alternatives|critical_points|meta_protocol",
      "claim": "исходный claim",
      "score": 0.0|0.5|1.0,
      "verdict": "covered|partial|missing",
      "evidence": "короткое свидетельство из ответа или empty",
      "reason": "краткое объяснение оценки"
    }
  ],
  "category_scores": {"decomposition": 0.0, "...": 0.0},
  "semantic_coverage_macro": 0.0,
  "semantic_coverage_micro": 0.0,
  "overall_assessment": "1-3 предложения"
}
"""


def _claims_payload(gold: GoldEntry) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for category in CLAIM_CATEGORIES:
        for claim in getattr(gold.expected_meta_elements, category):
            out.append({"category": category, "claim": claim})
    return out


def _build_messages(task_id: str, answer: dict[str, Any], gold: GoldEntry) -> list[ChatMessage]:
    user_payload = {
        "task_id": task_id,
        "reference_answer_for_context": gold.reference_answer.model_dump(),
        "expected_claims_to_score": _claims_payload(gold),
        "agent_answer": answer,
    }
    return [
        ChatMessage(role="system", content=SYSTEM_PROMPT),
        ChatMessage(
            role="user",
            content=json.dumps(user_payload, ensure_ascii=False, indent=2),
        ),
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
        raise ValueError("semantic judge response must be a JSON object")
    return payload


def _recompute_scores(judgment: TaskSemanticJudgment) -> TaskSemanticJudgment:
    by_category: dict[str, list[float]] = {category: [] for category in CLAIM_CATEGORIES}
    for item in judgment.claim_judgments:
        if item.category in by_category:
            by_category[item.category].append(float(item.score))

    category_scores = {
        category: round(sum(values) / len(values), 4) if values else 0.0
        for category, values in by_category.items()
    }
    all_scores = [score for values in by_category.values() for score in values]
    macro = sum(category_scores.values()) / len(category_scores) if category_scores else 0.0
    micro = sum(all_scores) / len(all_scores) if all_scores else 0.0
    return judgment.model_copy(
        update={
            "category_scores": category_scores,
            "semantic_coverage_macro": round(macro, 4),
            "semantic_coverage_micro": round(micro, 4),
        },
    )


class LLMSemanticJudgeUseCase:
    def __init__(self, *, run_dir: Path, gold_by_id: dict[str, GoldEntry], llm: LLMClient) -> None:
        self._run_dir = run_dir
        self._gold_by_id = gold_by_id
        self._llm = llm

    def judge_one(self, task_id: str) -> TaskSemanticJudgment:
        gold = self._gold_by_id[task_id]
        answer = read_json(self._run_dir / f"{task_id}.json")
        if not isinstance(answer, dict):
            raise ValueError(f"{task_id}: answer is not a JSON object")
        completion = self._llm.complete(_build_messages(task_id, answer, gold), json_response=True)
        try:
            payload = _extract_json(completion.content)
            judgment = TaskSemanticJudgment.model_validate(payload)
        except (json.JSONDecodeError, ValidationError, ValueError) as exc:
            raise ValueError(f"{task_id}: invalid semantic judge response: {exc}") from exc
        if judgment.task_id != task_id:
            judgment = judgment.model_copy(update={"task_id": task_id})
        return _recompute_scores(judgment)

    def execute(self, *, task_ids: list[str] | None = None, sleep_seconds: float = 0.0) -> SemanticJudgeReport:
        if task_ids is None:
            task_ids = sorted(
                path.stem
                for path in self._run_dir.glob("PMR-*.json")
                if path.stem in self._gold_by_id
            )
        rows: list[dict[str, Any]] = []
        for index, task_id in enumerate(task_ids):
            log.info("llm semantic judge task %d/%d %s", index + 1, len(task_ids), task_id)
            judgment = self.judge_one(task_id)
            rows.append(judgment.model_dump(mode="json"))
            if index + 1 < len(task_ids) and sleep_seconds > 0:
                time.sleep(sleep_seconds)

        summary = _summarise(rows)
        write_jsonl(self._run_dir / "llm_judge_by_task.jsonl", rows)
        write_json(self._run_dir / "llm_judge_summary.json", summary)
        return SemanticJudgeReport(summary=summary, by_task=rows)


def _summarise(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"n_tasks": 0}
    macro_values = [float(row.get("semantic_coverage_macro", 0.0)) for row in rows]
    micro_values = [float(row.get("semantic_coverage_micro", 0.0)) for row in rows]
    category_totals: dict[str, list[float]] = {category: [] for category in CLAIM_CATEGORIES}
    for row in rows:
        scores = row.get("category_scores", {})
        if not isinstance(scores, dict):
            continue
        for category in CLAIM_CATEGORIES:
            if category in scores:
                category_totals[category].append(float(scores[category]))

    return {
        "n_tasks": len(rows),
        "semantic_coverage_macro": round(sum(macro_values) / len(macro_values), 4),
        "semantic_coverage_micro": round(sum(micro_values) / len(micro_values), 4),
        "category_scores": {
            category: round(sum(values) / len(values), 4) if values else 0.0
            for category, values in category_totals.items()
        },
    }
