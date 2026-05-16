"""Protocol every benchmark suite must implement."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from src.domain.schemas import GoldEntry, GoldV2Entry, NormalizedTask


class SuiteProtocol(Protocol):
    """A benchmark suite groups tasks, gold and metric expectations together."""

    name: str
    """Stable CLI name, e.g. `pmr-bench`."""

    description: str
    """One-line human description for `status` / `--help`."""

    @property
    def root(self) -> Path: ...

    def load_tasks(self) -> list[NormalizedTask]:
        """Return all tasks, already converted to the shared NormalizedTask shape."""

    def load_gold(self) -> list[GoldEntry]:
        """Return per-task gold entries (skeleton + claims + metadata)."""

    def load_gold_v2(self) -> list[GoldV2Entry]:
        """Return optional flexible semantic gold entries."""

    def load_rubric(self) -> dict[str, object]:
        """Return the rubric definition shared across all tasks in the suite."""

    def supported_metrics(self) -> tuple[str, ...]:
        """Names of `MetricKind` values this suite produces by default."""
