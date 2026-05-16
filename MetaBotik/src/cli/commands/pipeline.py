"""`metabotik pipeline` — run × modes × repeats → eval per run → compare + paired."""

from __future__ import annotations

from pathlib import Path

import typer

from src.application.pipeline_usecase import PipelineUseCase
from src.cli._logging import setup_logging
from src.domain.enums import PromptMode
from src.infrastructure.run_dir import RunDirManager
from src.llm.client import YandexLLMClient
from src.llm.settings import LLMSettings


def _parse_modes(value: str) -> list[PromptMode]:
    items = [v.strip() for v in value.split(",") if v.strip()]
    out: list[PromptMode] = []
    for item in items:
        try:
            out.append(PromptMode(item))
        except ValueError as exc:
            raise typer.BadParameter(f"Unknown mode: {item!r}") from exc
    return out


def pipeline_cmd(
    suite: str = typer.Option("pmr-bench", "--suite"),
    modes: str = typer.Option("pmr,baseline", "--modes", help="Comma-separated prompt modes."),
    repeat: int = typer.Option(1, "--repeat"),
    limit: int | None = typer.Option(None, "--limit"),
    skip_run: bool = typer.Option(False, "--skip-run", help="Eval-only, do not call LLM."),
    dry_run: bool = typer.Option(False, "--dry-run"),
    log_file: Path | None = typer.Option(None, "--log-file"),
) -> None:
    setup_logging(log_file)
    mode_list = _parse_modes(modes)
    typer.echo(f"pipeline suite={suite} modes={[m.value for m in mode_list]} repeat={repeat} limit={limit}")
    if dry_run:
        from suites import get_suite

        s = get_suite(suite)
        tasks = s.load_tasks()
        if limit is not None:
            tasks = tasks[:limit]
        for rep in range(1, repeat + 1):
            for mode in mode_list:
                typer.echo(f"DRY rep={rep} mode={mode.value} tasks={len(tasks)}")
        return

    settings = LLMSettings()  # type: ignore[call-arg]
    llm = YandexLLMClient(settings)
    use_case = PipelineUseCase(
        llm=llm,
        run_dir_manager=RunDirManager(),
        request_sleep_seconds=settings.llm_request_sleep_seconds,
        save_raw=settings.llm_save_raw_responses,
    )
    outcome = use_case.execute(
        suite_name=suite,
        modes=mode_list,
        repeat=repeat,
        limit=limit,
        skip_run=skip_run,
    )
    typer.echo(f"runs: {len(outcome.runs)}")
    for run in outcome.runs:
        typer.echo(f"  {run.suite}/{run.mode.value}/{run.run_id}")
    for cmp_path in outcome.comparison_paths:
        typer.echo(f"comparison: {cmp_path}")
    for paired_path in outcome.paired_stats_paths:
        typer.echo(f"paired: {paired_path}")
