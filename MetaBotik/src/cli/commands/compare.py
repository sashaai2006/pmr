"""`metabotik compare` — delta between two run summaries."""

from __future__ import annotations

from pathlib import Path

import typer

from src.cli._logging import setup_logging
from src.evaluation.compare import compare_summaries, load_summary, save_comparison


def compare_cmd(
    candidate: Path = typer.Option(..., "--candidate", help="Path to candidate summary.json."),
    baseline: Path = typer.Option(..., "--baseline", help="Path to baseline summary.json."),
    candidate_label: str = typer.Option("pmr", "--candidate-label"),
    baseline_label: str = typer.Option("baseline", "--baseline-label"),
    output: Path = typer.Option(Path("compare.json"), "--output"),
    log_file: Path | None = typer.Option(None, "--log-file"),
) -> None:
    setup_logging(log_file)
    cand = load_summary(candidate)
    base = load_summary(baseline)
    comparison = compare_summaries(
        candidate=cand,
        baseline=base,
        candidate_label=candidate_label,
        baseline_label=baseline_label,
    )
    save_comparison(comparison, output)
    typer.echo(f"wrote {output} (and {output.with_suffix('.md')})")
    for row in comparison["metrics"]:
        typer.echo(
            f"  {row['metric']}: {row[f'{candidate_label}_value']:.4f} vs "
            f"{row[f'{baseline_label}_value']:.4f} Δ={row['delta']:+.4f} winner={row['winner']}",
        )
