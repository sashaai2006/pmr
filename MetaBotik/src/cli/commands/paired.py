"""`metabotik paired-stats` — paired t-test + Cohen's d + bootstrap CI."""

from __future__ import annotations

from pathlib import Path

import typer

from src.cli._logging import setup_logging
from src.evaluation.paired_stats import paired_stats, save_paired_stats


def paired_cmd(
    candidate: Path = typer.Option(..., "--candidate", help="Path to candidate by_task.jsonl."),
    baseline: Path = typer.Option(..., "--baseline", help="Path to baseline by_task.jsonl."),
    candidate_label: str = typer.Option("pmr", "--candidate-label"),
    baseline_label: str = typer.Option("baseline", "--baseline-label"),
    output: Path = typer.Option(Path("paired.json"), "--output"),
    bootstrap_samples: int = typer.Option(2000, "--bootstrap-samples"),
    alpha: float = typer.Option(0.05, "--alpha"),
    log_file: Path | None = typer.Option(None, "--log-file"),
) -> None:
    setup_logging(log_file)
    stats = paired_stats(
        candidate_path=candidate,
        baseline_path=baseline,
        candidate_label=candidate_label,
        baseline_label=baseline_label,
        bootstrap_samples=bootstrap_samples,
        alpha=alpha,
    )
    save_paired_stats(stats, output)
    typer.echo(f"wrote {output} (and {output.with_suffix('.md')})")
    overall = stats.get("overall") or {}
    if overall:
        typer.echo(
            f"  overall metric={overall.get('metric')} delta={overall.get('delta_mean')} "
            f"p={overall.get('paired_p_value')} d={overall.get('cohen_d_paired')}",
        )
