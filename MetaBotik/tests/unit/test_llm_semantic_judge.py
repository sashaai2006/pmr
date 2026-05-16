"""Tests for the LLM-backed semantic judge wrapper."""

from __future__ import annotations

import json

from src.evaluation.llm_semantic_judge import LLMSemanticJudgeUseCase
from src.infrastructure.repo import read_json, write_json
from suites import get_suite
from tests.conftest import FakeLLMClient, valid_agent_payload


def test_llm_semantic_judge_writes_report(temp_run_dir) -> None:  # type: ignore[no-untyped-def]
    suite = get_suite("pmr-bench")
    gold = suite.load_gold()[0]
    write_json(temp_run_dir / "PMR-001.json", valid_agent_payload())
    response = {
        "task_id": "PMR-001",
        "claim_judgments": [
            {
                "category": "decomposition",
                "claim": gold.expected_meta_elements.decomposition[0],
                "score": 1.0,
                "verdict": "covered",
                "evidence": "architecture is decomposed by safety class",
                "reason": "same procedural idea is present",
            },
            {
                "category": "rejected_alternatives",
                "claim": gold.expected_meta_elements.rejected_alternatives[0],
                "score": 0.5,
                "verdict": "partial",
                "evidence": "pure Agile is rejected for audit reasons",
                "reason": "reason is close but not complete",
            },
        ],
        "category_scores": {},
        "semantic_coverage_macro": 0.0,
        "semantic_coverage_micro": 0.0,
        "overall_assessment": "mixed",
    }
    fake_llm = FakeLLMClient(json.dumps(response))

    report = LLMSemanticJudgeUseCase(
        run_dir=temp_run_dir,
        gold_by_id={"PMR-001": gold},
        llm=fake_llm,
    ).execute(task_ids=["PMR-001"])

    assert report.summary["n_tasks"] == 1
    assert report.summary["semantic_coverage_micro"] == 0.75
    assert (temp_run_dir / "llm_judge_by_task.jsonl").exists()
    assert read_json(temp_run_dir / "llm_judge_summary.json")["semantic_coverage_macro"] == 0.375
    assert fake_llm.calls
