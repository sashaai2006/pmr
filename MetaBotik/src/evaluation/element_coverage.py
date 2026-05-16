"""Deterministic element-coverage metric for PMR-Bench answers.

Coverage is a suite-level check: did the answer cover the specific expected
procedural claims in the gold file? It is intentionally separate from schema
checks on the PMR JSON shape.

The first implementation used plain token overlap. That was useful as a smoke
test, but it punished correct paraphrases. The matcher below still avoids an
LLM judge, but adds three stronger signals:

- light token normalisation/stemming for Russian and English;
- small semantic alias groups for common PMR-Bench concepts;
- category-aware matching against the relevant answer sections instead of a
  blind scan of the whole JSON.

This is still deterministic and auditable. It is not a substitute for a human
or LLM semantic judge, but it is no longer just "same words present".
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any

from src.domain.schemas import (
    CategoryCoverage,
    CoverageScore,
    ExpectedMetaElements,
    GoldEntry,
)

CLAIM_CATEGORIES: tuple[str, ...] = (
    "decomposition",
    "rejected_alternatives",
    "critical_points",
    "meta_protocol",
)

MIN_TOKEN_LEN: int = 4
MATCH_THRESHOLD: float = 0.5
SEMANTIC_MATCH_THRESHOLD: float = 0.45

# Tokens that don't carry semantic load — exclude from match ratio.
STOPWORDS: frozenset[str] = frozenset(
    {
        # Russian
        "этот", "этом", "этой", "которая", "который", "которые", "когда", "потому",
        "также", "более", "менее", "если", "часть", "часто", "тоже", "очень",
        "должны", "должен", "может", "только", "перед", "после", "между", "через",
        "своих", "своим", "своей", "своего", "много", "мало", "новый", "новая",
        "новое", "пока", "ещё", "уже", "будет", "было", "были", "была", "быть",
        # English
        "this", "that", "these", "those", "with", "from", "into", "onto", "upon",
        "have", "having", "must", "should", "would", "could", "such", "than",
        "then", "they", "them", "their", "your", "yours", "ours", "what", "when",
        "where", "while", "which", "without", "within", "between", "before",
        "after", "above", "below", "more", "most", "less", "least", "very",
        "just", "only", "even", "also", "some", "many", "much", "each", "both",
        "either", "neither",
    }
)

_TOKEN_SPLIT = re.compile(r"[^\w\-/&]+", flags=re.UNICODE)

# Broad semantic aliases used by PMR-Bench claims. These are deliberately small
# and transparent: every alias group is an interpretable concept, not a learned
# black-box similarity score.
SEMANTIC_ALIASES: dict[str, tuple[str, ...]] = {
    "regulatory_audit": (
        "audit", "аудит", "сертификац", "regulatory", "регулятор", "iec", "iso", "510",
        "ce-mark", "notified", "соответств",
    ),
    "audit_artifact": (
        "artifact", "артефакт", "документ", "документац", "фиксац", "traceability",
        "трассиров", "sop", "change-control", "scorecard", "рубрика", "шкала",
        "досье", "отчёт", "отчет",
    ),
    "safety_classification": (
        "software safety", "safety classification", "класс", "классификац",
        "критич", "a/b/c", "class", "класс b", "класс c",
    ),
    "hybrid_lifecycle": (
        "гибрид", "hybrid", "v-model", "v-модель", "agile", "итерац", "спринт",
        "инкремент", "waterfall",
    ),
    "ui_component": ("ui", "ux", "интерфейс", "пользовательск", "экран", "визуализац"),
    "vv": ("v&v", "verification", "validation", "верификац", "валидац", "тестирован"),
    "calibration": ("calibration", "калибров", "калибрацион", "согласован", "шкала"),
    "trigger_monitoring": ("trigger", "триггер", "оповещ", "дашборд", "мониторинг", "alert"),
    "cognitive_level": ("блум", "bloom", "когнитив", "уров", "таксоном"),
    "peer_assessment": ("peer", "взаимооцен", "взаимн", "отзыв", "фидбэк"),
    "target_signal": ("signal", "сигнал", "критер", "hire", "no-hire", "scorecard"),
    "interview_format": ("star", "carl", "work-sample", "system design", "интервью"),
    "prioritization_framework": (
        "rice", "wsjf", "moscow", "kano", "cost-of-delay", "backlog", "бэклог",
        "приоритизац",
    ),
    "risk_matrix": ("risk", "риск", "fmea", "iso 14971", "failure", "отказ", "hazard"),
    "functional_analysis": ("abc", "функциональн", "паттерн", "предиктор", "шкала"),
    "therapy_protocol": ("кпт", "cbt", "act", "aaq", "gad", "pswq", "протокол"),
    "root_cause": ("rca", "root cause", "корнев", "причин", "инцидент"),
    "model_validation": ("цифров", "двойн", "валидац", "модель", "верификац"),
    "stakeholder": ("стейкхолдер", "ceo", "заинтересован", "интервьюер", "команд"),
    "adaptation_rule": (
        "если", "при", "заменить", "добавить", "ввести", "адаптир", "модифиц",
        "для класса", "для групп", "для задач",
    ),
}

REJECTION_MARKERS: tuple[str, ...] = (
    "отверг", "не примен", "не подходит", "хуже", "вместо", "альтернатив", "reject",
    "rejected", "avoid", "not suitable",
)

CRITICAL_MARKERS: tuple[str, ...] = (
    "→", "точка", "невозврат", "критичес", "red flag", "риск", "срыв", "провал",
    "ошибка", "без этого", "failure",
)

PROTOCOL_MARKERS: tuple[str, ...] = (
    "если", "при ", "правило", "мета-протокол", "заменить", "ввести", "добавить",
    "модификац", "adapt", "replace", "introduce", "add",
)


@dataclass(frozen=True)
class CoverageDetail:
    """Per-claim coverage info, useful for debugging / report rendering."""

    claim: str
    matched: bool
    match_ratio: float
    tokens_total: int
    tokens_hit: int
    category: str = ""
    semantic_ratio: float = 0.0
    match_method: str = "lexical"


def _claim_tokens(claim: str) -> list[str]:
    tokens = [t.lower() for t in _TOKEN_SPLIT.split(claim) if t]
    return [t for t in tokens if len(t) >= MIN_TOKEN_LEN and t not in STOPWORDS]


def _normalise_token(token: str) -> str:
    token = token.lower().replace("ё", "е")
    token = token.strip("_-/.")
    if len(token) < MIN_TOKEN_LEN:
        return token
    # Lightweight stemming is enough for this metric: the goal is to catch
    # inflectional variants such as "трассировка" / "трассировки" without
    # pretending to be a full morphological analyser.
    for suffix in (
        "иями", "ями", "ами", "ого", "ему", "ыми", "ими", "ией", "ия",
        "ий", "ый", "ой", "ая", "ое", "ые", "ых", "ую", "ом", "ем",
        "ам", "ям", "ах", "ях", "ов", "ев", "иям", "tion", "ing", "ed", "s",
    ):
        if token.endswith(suffix) and len(token) - len(suffix) >= MIN_TOKEN_LEN:
            return token[: -len(suffix)]
    return token


def _normalised_tokens(text: str) -> set[str]:
    return {_normalise_token(token) for token in _claim_tokens(text)}


def _alias_tags(text: str) -> set[str]:
    lowered = text.lower().replace("ё", "е")
    tags: set[str] = set()
    for tag, aliases in SEMANTIC_ALIASES.items():
        if any(alias in lowered for alias in aliases):
            tags.add(tag)
    return tags


def _semantic_units(text: str) -> set[str]:
    return _normalised_tokens(text) | {f"alias:{tag}" for tag in _alias_tags(text)}


def _flatten_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False).lower()


def _texts_from_steps(payload: dict[str, Any], *keys: str) -> list[str]:
    steps = payload.get("solution_steps")
    if not isinstance(steps, list):
        return []
    texts: list[str] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        for key in keys:
            value = step.get(key)
            if isinstance(value, list):
                texts.extend(str(item) for item in value)
            elif value is not None:
                texts.append(str(value))
    return texts


def _texts_from_alternatives(payload: dict[str, Any]) -> list[str]:
    pa = payload.get("procedural_analysis")
    if not isinstance(pa, dict):
        return []
    alts = pa.get("alternative_procedures")
    if not isinstance(alts, list):
        return []
    texts: list[str] = []
    for item in alts:
        if isinstance(item, dict):
            texts.append(f"{item.get('name', '')} {item.get('rejection_reason', '')}")
    return texts


def _texts_from_reflection(payload: dict[str, Any]) -> list[str]:
    reflection = payload.get("reflection")
    if not isinstance(reflection, dict):
        return []
    texts: list[str] = []
    for value in reflection.values():
        if isinstance(value, list):
            texts.extend(str(item) for item in value)
        elif value is not None:
            texts.append(str(value))
    return texts


def _category_texts(payload: dict[str, Any], category: str) -> list[str]:
    if category == "decomposition":
        texts: list[str] = []
        pa = payload.get("procedural_analysis")
        if isinstance(pa, dict):
            texts.extend(str(pa.get(key, "")) for key in ("problem_classification", "selected_procedure", "selection_reasoning"))
        texts.extend(_texts_from_steps(payload, "title", "action", "procedure_logic"))
        return texts or [_flatten_payload(payload)]
    if category == "rejected_alternatives":
        return _texts_from_alternatives(payload) or [_flatten_payload(payload)]
    if category == "critical_points":
        return _texts_from_steps(payload, "critical_points", "procedure_logic", "adaptation_notes") or [_flatten_payload(payload)]
    if category == "meta_protocol":
        return _texts_from_reflection(payload) or [_flatten_payload(payload)]
    return [_flatten_payload(payload)]


def _marker_bonus(category: str, text: str) -> float:
    lowered = text.lower()
    if category == "rejected_alternatives":
        return 0.1 if any(marker in lowered for marker in REJECTION_MARKERS) else -0.15
    if category == "critical_points":
        return 0.1 if any(marker in lowered for marker in CRITICAL_MARKERS) else -0.1
    if category == "meta_protocol":
        return 0.1 if any(marker in lowered for marker in PROTOCOL_MARKERS) else -0.1
    return 0.0


def _claim_match(claim: str, candidate_texts: list[str], category: str) -> CoverageDetail:
    tokens = _claim_tokens(claim)
    if not tokens:
        return CoverageDetail(
            claim=claim,
            matched=False,
            match_ratio=0.0,
            tokens_total=0,
            tokens_hit=0,
            category=category,
        )

    flat_text = " ".join(candidate_texts).lower()
    lexical_hits = sum(1 for token in tokens if token in flat_text)
    lexical_ratio = lexical_hits / len(tokens)

    claim_units = _semantic_units(claim)
    best_semantic = 0.0
    for text in candidate_texts:
        text_units = _semantic_units(text)
        if not claim_units:
            continue
        overlap = len(claim_units & text_units) / len(claim_units)
        best_semantic = max(best_semantic, max(0.0, min(1.0, overlap + _marker_bonus(category, text))))

    matched = lexical_ratio >= MATCH_THRESHOLD or best_semantic >= SEMANTIC_MATCH_THRESHOLD
    method = "lexical" if lexical_ratio >= MATCH_THRESHOLD else "semantic"
    return CoverageDetail(
        claim=claim,
        matched=matched,
        match_ratio=round(lexical_ratio, 4),
        tokens_total=len(tokens),
        tokens_hit=lexical_hits,
        category=category,
        semantic_ratio=round(best_semantic, 4),
        match_method=method,
    )


def evaluate_one(payload: dict[str, Any], gold: GoldEntry) -> tuple[CoverageScore, list[CoverageDetail]]:
    details: list[CoverageDetail] = []
    by_category: dict[str, CategoryCoverage] = {}

    total_expected = 0
    total_matched = 0
    macro_ratios: list[float] = []

    expected: ExpectedMetaElements = gold.expected_meta_elements
    for category in CLAIM_CATEGORIES:
        claims: list[str] = getattr(expected, category)
        candidate_texts = _category_texts(payload, category)
        expected_n = len(claims)
        matched_n = 0
        for claim in claims:
            detail = _claim_match(claim, candidate_texts, category)
            details.append(detail)
            if detail.matched:
                matched_n += 1
        ratio = matched_n / expected_n if expected_n else 0.0
        by_category[category] = CategoryCoverage(matched=matched_n, expected=expected_n, ratio=round(ratio, 4))
        total_expected += expected_n
        total_matched += matched_n
        macro_ratios.append(ratio)

    macro = sum(macro_ratios) / len(macro_ratios) if macro_ratios else 0.0
    micro = total_matched / total_expected if total_expected else 0.0
    score = CoverageScore(
        by_category=by_category,
        macro_ratio=round(macro, 4),
        micro_ratio=round(micro, 4),
    )
    return score, details
