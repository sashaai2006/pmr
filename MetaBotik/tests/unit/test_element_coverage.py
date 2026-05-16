"""Tests for deterministic claim coverage."""

from __future__ import annotations

from src.evaluation.element_coverage import (
    CLAIM_CATEGORIES,
    MATCH_THRESHOLD,
    _claim_tokens,
    evaluate_one,
)
from suites import get_suite


def test_claim_tokens_filter_stopwords_and_short() -> None:
    tokens = _claim_tokens("Software safety classification — точка невозврата")
    assert "software" in tokens
    assert "safety" in tokens
    assert "classification" in tokens
    assert "точка" in tokens
    assert "невозврата" in tokens


def test_high_quality_payload_maxes_coverage() -> None:
    suite = get_suite("pmr-bench")
    gold = suite.load_gold()[0]
    inlined = " ".join(
        gold.expected_meta_elements.decomposition
        + gold.expected_meta_elements.rejected_alternatives
        + gold.expected_meta_elements.critical_points
        + gold.expected_meta_elements.meta_protocol
    )
    score, _details = evaluate_one({"text": inlined}, gold)
    assert score.macro_ratio == 1.0
    assert score.micro_ratio == 1.0
    for cat in CLAIM_CATEGORIES:
        assert score.by_category[cat].ratio == 1.0


def test_unrelated_payload_scores_zero() -> None:
    suite = get_suite("pmr-bench")
    gold = suite.load_gold()[0]
    payload = {"text": "the quick brown fox jumps over the lazy dog hello world"}
    score, _ = evaluate_one(payload, gold)
    assert score.macro_ratio == 0.0
    assert score.micro_ratio == 0.0


def test_partial_payload_scales_between() -> None:
    """A payload that embeds only one category should score >0 in that category."""
    suite = get_suite("pmr-bench")
    gold = suite.load_gold()[0]
    partial = " ".join(gold.expected_meta_elements.decomposition)
    score, _ = evaluate_one({"text": partial}, gold)
    assert score.by_category["decomposition"].ratio == 1.0
    assert 0.0 < score.macro_ratio < 1.0


def test_semantic_paraphrase_matches_rejected_alternative() -> None:
    suite = get_suite("pmr-bench")
    gold = suite.load_gold()[0]
    payload = {
        "procedural_analysis": {
            "alternative_procedures": [
                {
                    "name": "Agile без регуляторного контура",
                    "rejection_reason": (
                        "отвергнут, потому что отсутствие строгой документации, "
                        "трассировки и формальных контрольных вех создаёт риск провала аудита"
                    ),
                }
            ]
        }
    }
    score, details = evaluate_one(payload, gold)
    rejected = [detail for detail in details if detail.claim.startswith("Чистая Agile")]
    assert rejected
    assert rejected[0].matched
    assert rejected[0].match_method == "semantic"
    assert score.by_category["rejected_alternatives"].matched >= 1


def test_match_threshold_constant_in_range() -> None:
    assert 0.0 < MATCH_THRESHOLD < 1.0
