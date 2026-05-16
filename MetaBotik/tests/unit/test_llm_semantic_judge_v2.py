"""Tests for the gold_v2 semantic judge."""

from __future__ import annotations

import json

from src.evaluation.llm_semantic_judge_v2 import LLMSemanticJudgeV2UseCase
from src.infrastructure.repo import read_json, write_json
from suites import get_suite
from tests.conftest import FakeLLMClient, valid_agent_payload


def test_suite_loads_gold_v2_exemplar() -> None:
    suite = get_suite("pmr-bench")

    gold_v2 = suite.load_gold_v2()

    assert [item.task_id for item in gold_v2] == [f"PMR-{index:03d}" for index in range(1, 11)]
    assert gold_v2[0].rubric.must_have_invariants
    assert gold_v2[0].rubric.acceptable_solution_families
    assert gold_v2[0].rubric.fatal_omissions


def test_llm_semantic_judge_v2_writes_report(temp_run_dir) -> None:  # type: ignore[no-untyped-def]
    suite = get_suite("pmr-bench")
    gold = suite.load_gold_v2()[0]
    write_json(temp_run_dir / "PMR-001.json", valid_agent_payload())
    response = {
        "task_id": "PMR-001",
        "selected_solution_family_id": "family_vmodel_agile",
        "solution_family_reason": "The answer uses hybrid V-model plus agile increments.",
        "judgments": [
            {
                "dimension": "must_have",
                "criterion_id": "inv_regulatory_first",
                "score": 1.0,
                "verdict": "satisfied",
                "evidence": "IEC 62304 and SOPs before coding",
                "reason": "Regulatory bootstrap is explicit.",
            },
            {
                "dimension": "must_have",
                "criterion_id": "inv_hybrid_lifecycle",
                "score": 0.5,
                "verdict": "partial",
                "evidence": "hybrid V-model + agile increments",
                "reason": "Hybrid is present but not fully split by component.",
            },
            {
                "dimension": "fatal",
                "criterion_id": "fatal_pure_agile",
                "score": 0.5,
                "verdict": "triggered",
                "evidence": "The answer leans on sprinting before audit controls.",
                "reason": "The model used the legacy fatal dimension alias.",
            },
            {
                "dimension": "optional",
                "criterion_id": "opt_class_c_adaptation",
                "score": 1.0,
                "verdict": "satisfied",
                "evidence": "For class C add independent verification.",
                "reason": "Class C adaptation is present.",
            },
        ],
        "must_have_score": 0.0,
        "optional_score": 0.0,
        "fatal_penalty": 0.0,
        "overall_score": 0.0,
        "pass_binary": False,
        "overall_assessment": "good",
    }
    fake_llm = FakeLLMClient(json.dumps(response))

    report = LLMSemanticJudgeV2UseCase(
        run_dir=temp_run_dir,
        gold_by_id={"PMR-001": gold},
        llm=fake_llm,
    ).execute(task_ids=["PMR-001"])

    assert report.summary["n_tasks"] == 1
    assert report.summary["must_have_score"] == 0.75
    assert report.summary["fatal_penalty"] == 0.5
    assert report.summary["overall_score"] == 0.55
    assert (temp_run_dir / "llm_judge_v2_by_task.jsonl").exists()
    assert read_json(temp_run_dir / "llm_judge_v2_summary.json")["pass_rate"] == 0.0


def test_llm_semantic_judge_v2_skips_missing_gold(temp_run_dir) -> None:  # type: ignore[no-untyped-def]
    fake_llm = FakeLLMClient("{}")

    report = LLMSemanticJudgeV2UseCase(
        run_dir=temp_run_dir,
        gold_by_id={},
        llm=fake_llm,
    ).execute(task_ids=["PMR-999"])

    assert report.summary == {"n_tasks": 0}
    assert fake_llm.calls == []
