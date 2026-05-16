"""Tests for the 5-axis LLM quality judge."""

from __future__ import annotations

import json

from src.evaluation.quality_judge import (
    BY_TASK_FILENAME,
    SUMMARY_FILENAME,
    QualityJudgeUseCase,
    compute_ai_score,
    summarise_quality_rows,
)
from src.infrastructure.repo import read_json, write_json
from suites import get_suite
from tests.conftest import FakeLLMClient, valid_agent_payload


def _quality_response() -> dict[str, object]:
    return {
        "task_id": "PMR-001",
        "completeness": {
            "score": 8.0,
            "rationale": "Covers the main requirements and constraints.",
            "evidence": "Compliance bootstrap and V&V plan are explicit.",
        },
        "accuracy": {
            "score": 6.0,
            "rationale": "Mostly correct but some regulatory details are underspecified.",
            "evidence": "Mentions IEC 62304 without explaining the safety class workflow.",
        },
        "latent_pattern_quality": {
            "score": 9.0,
            "rationale": "Identifies the hybrid lifecycle pattern and audit trade-off.",
            "evidence": "Hybrid V-model plus agile increments.",
        },
        "practical_value": {
            "score": 7.0,
            "rationale": "Actionable steps are present, but success criteria could be sharper.",
            "evidence": "Freeze SOPs, decompose architecture, assign V&V depth.",
        },
        "ai_score": 1.0,
        "pass_binary": False,
        "overall_assessment": "Strong answer with a few missing details.",
    }


def test_compute_ai_score_uses_weighted_formula() -> None:
    score = compute_ai_score(
        completeness=8.0,
        accuracy=6.0,
        latent_pattern_quality=9.0,
        practical_value=7.0,
    )

    assert score == 7.35


def test_quality_judge_recomputes_scores_and_writes_report(temp_run_dir) -> None:  # type: ignore[no-untyped-def]
    suite = get_suite("pmr-bench")
    task = suite.load_tasks()[0]
    write_json(temp_run_dir / "PMR-001.json", valid_agent_payload())
    fake_llm = FakeLLMClient(json.dumps(_quality_response()))

    report = QualityJudgeUseCase(
        run_dir=temp_run_dir,
        tasks_by_id={"PMR-001": task},
        llm=fake_llm,
    ).execute(task_ids=["PMR-001"])

    row = report.by_task[0]
    assert row["ai_score"] == 7.35
    assert row["pass_binary"] is True
    assert report.summary["ai_score_mean"] == 7.35
    assert report.summary["pass_rate"] == 1.0
    assert (temp_run_dir / BY_TASK_FILENAME).exists()
    assert read_json(temp_run_dir / SUMMARY_FILENAME)["accuracy_mean"] == 6.0


def test_quality_summary_aggregates_axis_means() -> None:
    rows = [
        _quality_response() | {"ai_score": 7.35, "pass_binary": True},
        _quality_response()
        | {
            "completeness": {"score": 4.0, "rationale": "partial", "evidence": ""},
            "accuracy": {"score": 5.0, "rationale": "partial", "evidence": ""},
            "latent_pattern_quality": {"score": 6.0, "rationale": "partial", "evidence": ""},
            "practical_value": {"score": 3.0, "rationale": "partial", "evidence": ""},
            "ai_score": 4.45,
            "pass_binary": False,
        },
    ]

    summary = summarise_quality_rows(rows)

    assert summary["n_tasks"] == 2
    assert summary["completeness_mean"] == 6.0
    assert summary["accuracy_mean"] == 5.5
    assert summary["latent_pattern_quality_mean"] == 7.5
    assert summary["practical_value_mean"] == 5.0
    assert summary["ai_score_mean"] == 5.9
    assert summary["pass_rate"] == 0.5
