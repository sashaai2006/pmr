"""End-to-end EvalUseCase test with fake PMR-bench answers."""

from __future__ import annotations

import json
from pathlib import Path

from src.application.eval_usecase import EvalUseCase
from suites import get_suite
from tests.conftest import valid_agent_payload, low_quality_payload


def _drop_one_answer(run_dir: Path, task_id: str, payload: dict[str, object]) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / f"{task_id}.json").write_text(
        json.dumps(payload, ensure_ascii=False), encoding="utf-8"
    )


def test_eval_usecase_distinguishes_high_vs_low_payload(tmp_path: Path) -> None:
    suite = get_suite("pmr-bench")
    high_dir = tmp_path / "high"
    low_dir = tmp_path / "low"

    for task in suite.load_tasks():
        _drop_one_answer(high_dir, task.task_id, valid_agent_payload(task.task_id))
        _drop_one_answer(low_dir, task.task_id, low_quality_payload(task.task_id))

    high_report = EvalUseCase(
        run_dir=high_dir, suite="pmr-bench", mode="pmr", run_id="r-high",
    ).run()
    low_report = EvalUseCase(
        run_dir=low_dir, suite="pmr-bench", mode="baseline", run_id="r-low",
    ).run()

    assert high_report.n_tasks == 10
    assert low_report.n_tasks == 10
    assert high_report.summary["procedural_rigor_mean"] > 0.4
    assert low_report.summary["procedural_rigor_mean"] < 0.1
    assert (high_dir / "summary.json").exists()
    assert (high_dir / "by_task.jsonl").exists()
