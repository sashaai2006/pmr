"""Tests for RunDirManager + latest symlink semantics."""

from __future__ import annotations

import time
from pathlib import Path

from src.infrastructure.run_dir import RunDirManager, new_run_id


def test_new_run_id_is_unique_per_call() -> None:
    ids = {new_run_id() for _ in range(20)}
    assert len(ids) == 20


def test_new_run_dir_creates_path_and_latest(tmp_path: Path) -> None:
    rd = RunDirManager(base=tmp_path)
    path = rd.new_run_dir("pmr-bench", "pmr")
    assert path.exists() and path.is_dir()
    link = rd.latest_link("pmr-bench", "pmr")
    assert link.exists()
    assert link.resolve() == path


def test_latest_link_updates_on_second_run(tmp_path: Path) -> None:
    rd = RunDirManager(base=tmp_path)
    first = rd.new_run_dir("pmr-bench", "baseline")
    time.sleep(0.01)
    second = rd.new_run_dir("pmr-bench", "baseline")
    assert first != second
    assert rd.latest_link("pmr-bench", "baseline").resolve() == second


def test_resolve_returns_explicit_run(tmp_path: Path) -> None:
    rd = RunDirManager(base=tmp_path)
    path = rd.new_run_dir("pmr-bench", "pmr", run_id="2026-05-15T120000Z-aabb")
    resolved = rd.resolve("pmr-bench", "pmr", "2026-05-15T120000Z-aabb")
    assert resolved == path


def test_resolve_latest_keyword(tmp_path: Path) -> None:
    rd = RunDirManager(base=tmp_path)
    path = rd.new_run_dir("pmr-bench", "pmr")
    resolved = rd.resolve("pmr-bench", "pmr", "latest")
    assert resolved == path


def test_list_runs_skips_latest_link(tmp_path: Path) -> None:
    rd = RunDirManager(base=tmp_path)
    rd.new_run_dir("pmr-bench", "pmr", run_id="a")
    rd.new_run_dir("pmr-bench", "pmr", run_id="b")
    runs = rd.list_runs("pmr-bench", "pmr")
    assert "latest" not in runs
    assert set(runs) == {"a", "b"}
