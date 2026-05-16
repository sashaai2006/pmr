"""Benchmark suite registry.

A *suite* is a (tasks, gold, expected-metrics) bundle that the agent can be
evaluated against. Each suite implements `SuiteProtocol` and is registered in
`SUITES` so the CLI can resolve `--suite <name>` dynamically.
"""

from __future__ import annotations

from suites.pmr_bench.suite import PmrBenchSuite
from suites.protocol import SuiteProtocol

SUITES: dict[str, SuiteProtocol] = {
    PmrBenchSuite.name: PmrBenchSuite(),
}


def get_suite(name: str) -> SuiteProtocol:
    if name not in SUITES:
        raise KeyError(
            f"Unknown suite: {name!r}. Known: {sorted(SUITES)}",
        )
    return SUITES[name]


__all__ = ["SUITES", "SuiteProtocol", "get_suite"]
