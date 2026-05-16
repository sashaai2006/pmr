"""`metabotik status` — list known suites, latest runs, headline metrics."""

from __future__ import annotations

import typer

from src.cli._logging import setup_logging
from src.infrastructure.repo import read_json
from src.infrastructure.run_dir import RunDirManager
from suites import SUITES


def status_cmd() -> None:
    setup_logging()
    run_dirs = RunDirManager()
    typer.echo("=== MetaBotik status ===")
    for suite_name, suite in SUITES.items():
        typer.echo(f"\nSuite: {suite_name}  ({suite.description})")
        suite_root = run_dirs.base / suite_name
        if not suite_root.exists():
            typer.echo("  no runs yet")
            continue
        for mode_dir in sorted(p for p in suite_root.iterdir() if p.is_dir()):
            runs = run_dirs.list_runs(suite_name, mode_dir.name)
            if not runs:
                typer.echo(f"  {mode_dir.name}: no runs")
                continue
            latest = runs[-1]
            summary_path = mode_dir / latest / "summary.json"
            quality_path = mode_dir / latest / "quality_judge_summary.json"
            tail = ""
            if quality_path.exists():
                try:
                    payload = read_json(quality_path)
                    n = payload.get("n_tasks")
                    ai = payload.get("ai_score_mean")
                    tail = f"  n={n} ai_score_mean={ai}"
                except Exception:  # noqa: BLE001
                    tail = "  (quality_judge_summary unreadable)"
            elif summary_path.exists():
                try:
                    payload = read_json(summary_path)
                    n = payload.get("n_tasks")
                    tail = f"  n={n}"
                except Exception:  # noqa: BLE001
                    tail = "  (summary unreadable)"
            typer.echo(f"  {mode_dir.name}: latest={latest} runs={len(runs)}{tail}")
    typer.echo("=== end ===")
