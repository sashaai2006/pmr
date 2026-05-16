"""`metabotik run` — run one strategy over a suite, write results/<suite>/<mode>/<run_id>/."""

from __future__ import annotations

from pathlib import Path

import typer

from src.application.run_usecase import RunUseCase
from src.cli._logging import setup_logging
from src.domain.enums import PromptMode
from src.infrastructure.run_dir import RunDirManager
from src.llm.client import YandexLLMClient
from src.llm.settings import LLMSettings
from src.prompting.strategies import get_strategy
from suites import get_suite


def run_cmd(
    suite: str = typer.Option("pmr-bench", "--suite"),
    mode: PromptMode = typer.Option(PromptMode.PMR, "--mode"),
    limit: int | None = typer.Option(None, "--limit"),
    start_after: str | None = typer.Option(None, "--start-after"),
    only_task: str | None = typer.Option(None, "--task-id"),
    force: bool = typer.Option(False, "--force", help="Re-run tasks even if results exist."),
    dry_run: bool = typer.Option(False, "--dry-run", help="List tasks, do not call LLM."),
    run_id: str | None = typer.Option(None, "--run-id"),
    log_file: Path | None = typer.Option(None, "--log-file"),
) -> None:
    setup_logging(log_file)
    suite_obj = get_suite(suite)
    tasks = suite_obj.load_tasks()
    if only_task is not None:
        tasks = [t for t in tasks if t.task_id == only_task]
        if not tasks:
            typer.echo(f"task not found: {only_task}", err=True)
            raise typer.Exit(code=2)
    else:
        if start_after is not None:
            ids = [t.task_id for t in tasks]
            if start_after not in ids:
                typer.echo(f"--start-after task not found: {start_after}", err=True)
                raise typer.Exit(code=2)
            tasks = tasks[ids.index(start_after) + 1 :]
        if limit is not None:
            tasks = tasks[:limit]

    if dry_run:
        for task in tasks:
            typer.echo(f"DRY suite={suite} mode={mode.value} task_id={task.task_id} difficulty={task.difficulty.value}")
        typer.echo(f"--- {len(tasks)} task(s) would be processed ---")
        return

    settings = LLMSettings()  # type: ignore[call-arg]
    llm = YandexLLMClient(settings)
    run_dirs = RunDirManager()
    out_dir = run_dirs.new_run_dir(suite, mode.value, run_id=run_id)
    rid = out_dir.name
    typer.echo(f"run_id={rid} out_dir={out_dir}")
    summary = RunUseCase(
        strategy=get_strategy(mode),
        llm=llm,
        out_dir=out_dir,
        suite=suite,
        mode=mode.value,
        run_id=rid,
        request_sleep_seconds=settings.llm_request_sleep_seconds,
        save_raw=settings.llm_save_raw_responses,
    ).run_all(tasks, skip_existing=not force)
    typer.echo(
        f"DONE completed={summary.n_completed}/{summary.n_tasks} failed={summary.n_failed} "
        f"repair={summary.repair_attempts} elapsed={summary.elapsed_seconds}s",
    )
    if summary.n_failed:
        raise typer.Exit(code=1)
