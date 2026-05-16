"""Tests for the generic summary-compare module."""

from __future__ import annotations

import json
from pathlib import Path

from src.evaluation.compare import compare_summaries, load_summary, save_comparison


def test_compare_returns_deltas_for_numeric_keys() -> None:
    cand = {"latency_mean_ms": 120.0, "rubric_score_mean": 0.92, "n_tasks": 10}
    base = {"latency_mean_ms": 200.0, "rubric_score_mean": 0.10, "n_tasks": 10}
    result = compare_summaries(candidate=cand, baseline=base, candidate_label="pmr", baseline_label="bl")
    metrics = {row["metric"]: row for row in result["metrics"]}
    assert "n_tasks" not in metrics  # excluded
    assert metrics["latency_mean_ms"]["delta"] < 0
    assert metrics["latency_mean_ms"]["winner"] == "bl"
    assert metrics["rubric_score_mean"]["winner"] == "pmr"


def test_compare_tie_when_equal() -> None:
    result = compare_summaries(
        candidate={"x": 0.5},
        baseline={"x": 0.5},
    )
    row = result["metrics"][0]
    assert row["delta"] == 0
    assert row["winner"] == "tie"
    assert row["change_label"] == "no_change"


def test_compare_io_round_trip(tmp_path: Path) -> None:
    cand_path = tmp_path / "cand.json"
    base_path = tmp_path / "base.json"
    cand_path.write_text(json.dumps({"score": 0.7}), encoding="utf-8")
    base_path.write_text(json.dumps({"score": 0.3}), encoding="utf-8")
    cmp = compare_summaries(
        candidate=load_summary(cand_path),
        baseline=load_summary(base_path),
    )
    out = tmp_path / "cmp.json"
    save_comparison(cmp, out)
    assert out.exists()
    assert out.with_suffix(".md").exists()
    md_text = out.with_suffix(".md").read_text(encoding="utf-8")
    assert "| `score` |" in md_text
