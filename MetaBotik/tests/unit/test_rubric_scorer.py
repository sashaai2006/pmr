"""Tests for manual CSV rubric loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from src.evaluation.rubric_scorer import (
    RUBRIC_AXES,
    emit_blank_csv,
    load_manual_csv,
)


def test_emit_blank_csv_has_all_axes(tmp_path: Path) -> None:
    csv_path = tmp_path / "rubric_scores.csv"
    emit_blank_csv(csv_path, ["PMR-001", "PMR-002"])
    lines = csv_path.read_text(encoding="utf-8").splitlines()
    header = lines[0].split(",")
    for axis in RUBRIC_AXES:
        assert axis in header
    assert lines[1].startswith("PMR-001,")
    assert lines[2].startswith("PMR-002,")


def test_load_manual_csv_round_trip(tmp_path: Path) -> None:
    csv_path = tmp_path / "rubric_scores.csv"
    csv_path.write_text(
        "task_id,procedural_self_awareness,decomposition_quality,justification_depth,"
        "reflection_actionability,reproducibility,notes\n"
        "PMR-001,2,2,1,2,2,solid answer\n"
        "PMR-002,1,1,0,1,1,thin reflection\n",
        encoding="utf-8",
    )
    entries = load_manual_csv(csv_path)
    assert set(entries) == {"PMR-001", "PMR-002"}
    assert entries["PMR-001"].total == 9
    assert entries["PMR-002"].total == 4
    assert entries["PMR-001"].notes == "solid answer"


def test_load_manual_csv_rejects_missing_axis(tmp_path: Path) -> None:
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text("task_id,procedural_self_awareness\nPMR-001,2\n", encoding="utf-8")
    with pytest.raises(ValueError, match="missing columns"):
        load_manual_csv(csv_path)


def test_load_manual_csv_axis_out_of_range(tmp_path: Path) -> None:
    csv_path = tmp_path / "bad.csv"
    csv_path.write_text(
        "task_id,procedural_self_awareness,decomposition_quality,justification_depth,"
        "reflection_actionability,reproducibility\n"
        "PMR-001,5,0,0,0,0\n",
        encoding="utf-8",
    )
    with pytest.raises(Exception):
        load_manual_csv(csv_path)
