"""`metabotik ingest` — validate that a suite's tasks/gold/rubric load cleanly."""

from __future__ import annotations

import typer

from src.cli._logging import setup_logging
from suites import SUITES, get_suite


def ingest_cmd(
    suite: str = typer.Option("pmr-bench", "--suite", help="Suite name."),
) -> None:
    setup_logging()
    if suite not in SUITES:
        typer.echo(f"Unknown suite: {suite!r}. Known: {sorted(SUITES)}", err=True)
        raise typer.Exit(code=2)
    s = get_suite(suite)
    tasks = s.load_tasks()
    gold = s.load_gold()
    rubric = s.load_rubric()
    task_ids = {t.task_id for t in tasks}
    gold_ids = {g.task_id for g in gold}
    only_tasks = sorted(task_ids - gold_ids)
    only_gold = sorted(gold_ids - task_ids)
    typer.echo(f"suite: {s.name}")
    typer.echo(f"description: {s.description}")
    typer.echo(f"tasks: {len(tasks)}  gold: {len(gold)}")
    typer.echo(f"rubric: total_max={rubric['total_max']}  pass_threshold={rubric['pass_threshold']}")
    typer.echo(f"metrics: {', '.join(s.supported_metrics())}")
    if only_tasks:
        typer.echo(f"WARNING tasks without gold: {only_tasks}", err=True)
    if only_gold:
        typer.echo(f"WARNING gold without tasks: {only_gold}", err=True)
    if only_tasks or only_gold:
        raise typer.Exit(code=1)
    typer.echo("OK: tasks and gold are aligned 1:1.")
