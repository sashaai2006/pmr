"""`metabotik llm-judge-v2` — semantic judging with flexible gold_v2 rubrics."""

from __future__ import annotations

from pathlib import Path

import typer

from src.cli._logging import setup_logging
from src.domain.enums import PromptMode
from src.evaluation.llm_semantic_judge_v2 import (
    BY_TASK_FILENAME,
    SUMMARY_FILENAME,
    LLMSemanticJudgeV2UseCase,
)
from src.infrastructure.run_dir import RunDirManager
from src.llm.client import YandexLLMClient
from src.llm.settings import LLMSettings
from suites import get_suite


def _parse_task_ids(value: str | None) -> list[str] | None:
    if not value:
        return None
    return [item.strip() for item in value.split(",") if item.strip()]


def llm_judge_v2_cmd(
    suite: str = typer.Option("pmr-bench", "--suite"),
    mode: PromptMode = typer.Option(PromptMode.PMR, "--mode"),
    run_id: str = typer.Option("latest", "--run-id"),
    task_ids: str | None = typer.Option(None, "--task-ids", help="Comma-separated task IDs."),
    limit: int | None = typer.Option(None, "--limit"),
    log_file: Path | None = typer.Option(None, "--log-file"),
) -> None:
    setup_logging(log_file)
    settings = LLMSettings()  # type: ignore[call-arg]
    run_dir = RunDirManager().resolve(suite, mode.value, run_id)
    suite_obj = get_suite(suite)
    if not hasattr(suite_obj, "load_gold_v2"):
        raise typer.BadParameter(f"Suite {suite!r} does not provide gold_v2.")
    gold_by_id = {gold.task_id: gold for gold in suite_obj.load_gold_v2()}
    selected_task_ids = _parse_task_ids(task_ids)
    if selected_task_ids is not None and limit is not None:
        selected_task_ids = selected_task_ids[:limit]
    elif selected_task_ids is None and limit is not None:
        selected_task_ids = [
            path.stem
            for path in sorted(run_dir.glob("PMR-*.json"))
            if path.stem in gold_by_id
        ][:limit]

    report = LLMSemanticJudgeV2UseCase(
        run_dir=run_dir,
        gold_by_id=gold_by_id,
        llm=YandexLLMClient(settings),
    ).execute(task_ids=selected_task_ids, sleep_seconds=settings.llm_request_sleep_seconds)

    typer.echo(f"run_dir={run_dir}")
    typer.echo(f"wrote {run_dir / SUMMARY_FILENAME}")
    typer.echo(f"wrote {run_dir / BY_TASK_FILENAME}")
    typer.echo(f"summary: {report.summary}")
