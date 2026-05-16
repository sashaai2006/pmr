"""CLI smoke tests via typer.testing.CliRunner."""

from __future__ import annotations

from typer.testing import CliRunner

from src.cli.app import app


def test_cli_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "run" in result.stdout
    assert "pipeline" in result.stdout
    assert "quality-judge" in result.stdout
    assert "llm-judge" not in result.stdout
    assert "ingest" not in result.stdout


def test_cli_quality_judge_help() -> None:
    runner = CliRunner()
    result = runner.invoke(app, ["quality-judge", "--help"])
    assert result.exit_code == 0
    assert "--pass-threshold" in result.stdout


def test_cli_run_dry_run() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        ["run", "--suite", "pmr-bench", "--mode", "pmr", "--dry-run", "--limit", "2"],
    )
    assert result.exit_code == 0
    assert "DRY suite=pmr-bench" in result.stdout
    assert "2 task(s)" in result.stdout


def test_cli_pipeline_dry_run() -> None:
    runner = CliRunner()
    result = runner.invoke(
        app,
        [
            "pipeline", "--suite", "pmr-bench",
            "--modes", "pmr,baseline", "--repeat", "2",
            "--limit", "1", "--dry-run",
        ],
    )
    assert result.exit_code == 0
    assert "DRY rep=1 mode=pmr" in result.stdout
    assert "DRY rep=2 mode=baseline" in result.stdout
