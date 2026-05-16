"""`metabotik judge` — emit / load a manual rubric CSV for a given run."""

from __future__ import annotations

from pathlib import Path

import typer

from src.application.judge_usecase import JudgeUseCase
from src.cli._logging import setup_logging
from src.domain.enums import PromptMode
from src.infrastructure.run_dir import RunDirManager
from suites import get_suite


def judge_cmd(
    suite: str = typer.Option("pmr-bench", "--suite"),
    mode: PromptMode = typer.Option(PromptMode.PMR, "--mode"),
    run_id: str = typer.Option("latest", "--run-id"),
    init: bool = typer.Option(False, "--init", help="Emit a blank rubric_scores.csv template."),
    log_file: Path | None = typer.Option(None, "--log-file"),
) -> None:
    setup_logging(log_file)
    run_dirs = RunDirManager()
    run_dir = run_dirs.resolve(suite, mode.value, run_id)
    judge = JudgeUseCase(run_dir)

    if init:
        suite_obj = get_suite(suite)
        task_ids = [t.task_id for t in suite_obj.load_tasks()]
        path = judge.emit_template(task_ids)
        typer.echo(f"wrote blank rubric CSV -> {path}")
        return

    entries = judge.load()
    typer.echo(f"loaded {len(entries)} rubric entries from {judge.template_path()}")
    for task_id, entry in entries.items():
        typer.echo(f"  {task_id}: total={entry.total}")
