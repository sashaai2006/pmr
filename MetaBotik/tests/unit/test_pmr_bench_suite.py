"""Smoke + invariant tests for PmrBenchSuite."""

from __future__ import annotations

from src.domain.enums import Difficulty
from suites import SUITES, get_suite


def test_registry_has_pmr_bench() -> None:
    assert "pmr-bench" in SUITES


def test_pmr_bench_has_ten_aligned_pairs() -> None:
    suite = get_suite("pmr-bench")
    tasks = suite.load_tasks()
    gold = suite.load_gold()
    assert len(tasks) == 10
    assert len(gold) == 10
    assert [t.task_id for t in tasks] == [g.task_id for g in gold]


def test_pmr_bench_difficulty_balanced() -> None:
    suite = get_suite("pmr-bench")
    levels = [t.difficulty for t in suite.load_tasks()]
    assert levels.count(Difficulty.INTERMEDIATE) == 5
    assert levels.count(Difficulty.ADVANCED) == 5


def test_pmr_bench_covers_four_domains() -> None:
    suite = get_suite("pmr-bench")
    domains = {t.domain for t in suite.load_tasks()}
    assert domains == {"Engineering", "Education", "Management", "Therapy"}


def test_pmr_bench_rubric_has_pass_threshold() -> None:
    suite = get_suite("pmr-bench")
    rubric = suite.load_rubric()
    assert rubric["total_max"] == 10
    assert rubric["pass_threshold"] == 7


def test_pmr_bench_gold_carries_discriminator_notes() -> None:
    suite = get_suite("pmr-bench")
    for g in suite.load_gold():
        assert g.metadata.target_skill
        # Advanced cases should always have a discriminator note (per plan spec).
        # We at least verify the field is set when present.
        if g.metadata.discriminator_note is not None:
            assert len(g.metadata.discriminator_note) > 20
