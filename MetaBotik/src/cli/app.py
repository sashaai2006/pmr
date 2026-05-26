"""Typer CLI entry point.

Sub-commands are registered in `src.cli.commands.*` and composed here.
"""

from __future__ import annotations

import typer
from dotenv import load_dotenv

from src.cli.commands import (
    compare,
    eval_cmd,
    paired,
    pipeline,
    quality_judge,
    run,
    status,
)

load_dotenv()

app = typer.Typer(
    help="MetaBotik — Procedural Meta-Reflection (PMR; Dushkin, Metacognitive Prompt Engineering) agent pipeline.",
    no_args_is_help=True,
)

app.command("run")(run.run_cmd)
app.command("pipeline")(pipeline.pipeline_cmd)
app.command("eval")(eval_cmd.eval_cmd)
app.command("compare")(compare.compare_cmd)
app.command("paired-stats")(paired.paired_cmd)
app.command("quality-judge")(quality_judge.quality_judge_cmd)
app.command("status")(status.status_cmd)


def main() -> None:
    """Console script entrypoint (`metabotik = "src.cli.app:main"`)."""
    app()


if __name__ == "__main__":  # pragma: no cover
    main()
