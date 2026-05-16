"""`metabotik eval` — compute deterministic metrics over an existing run."""

from __future__ import annotations

from pathlib import Path

import typer

from src.application.eval_usecase import EvalUseCase
from src.application.judge_usecase import JudgeUseCase
from src.cli._logging import setup_logging
from src.domain.enums import PromptMode
from src.infrastructure.run_dir import RunDirManager


def eval_cmd(
    suite: str = typer.Option("pmr-bench", "--suite"),
    mode: PromptMode = typer.Option(PromptMode.PMR, "--mode"),
    run_id: str = typer.Option("latest", "--run-id"),
    include_rubric: bool = typer.Option(True, "--rubric/--no-rubric", help="Load rubric_scores.csv if present."),
    log_file: Path | None = typer.Option(None, "--log-file"),
) -> None:
    setup_logging(log_file)
    run_dirs = RunDirManager()
    run_dir = run_dirs.resolve(suite, mode.value, run_id)
    rubric_by_id = None
    if include_rubric:
        rubric_by_id = JudgeUseCase(run_dir).load() or None

    report = EvalUseCase(
        run_dir=run_dir,
        suite=suite,
        mode=mode.value,
        run_id=run_dir.name,
        rubric_by_id=rubric_by_id,
    ).run()
    typer.echo(f"run_dir={run_dir}")
    typer.echo(f"n_tasks={report.n_tasks}")
    typer.echo(f"summary: {report.summary}")
