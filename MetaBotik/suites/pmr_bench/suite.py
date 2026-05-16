"""PMR-Bench suite: 10 procedural meta-reflection tasks across 4 domains."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.domain.enums import Difficulty, MetricKind
from src.domain.schemas import GoldEntry, GoldV2Entry, NormalizedTask

_ROOT = Path(__file__).resolve().parent
_BENCHMARK_PATH = _ROOT / "benchmark.jsonl"
_GOLD_PATH = _ROOT / "gold.jsonl"
_GOLD_V2_PATH = _ROOT / "gold_v2.jsonl"
_RUBRIC_PATH = _ROOT / "rubric.json"
_TITLE_PREVIEW_CHARS = 60


def _difficulty(raw: str) -> Difficulty:
    """`Intermediate` / `Advanced` / `expert` -> Difficulty enum."""
    return Difficulty(raw.strip().lower())


def _make_title(domain: str, task_description: str) -> str:
    preview = task_description.strip().split("\n", 1)[0]
    if len(preview) > _TITLE_PREVIEW_CHARS:
        preview = preview[: _TITLE_PREVIEW_CHARS - 1].rstrip() + "…"
    return f"{domain} — {preview}"


def _normalize_task(raw: dict[str, Any]) -> NormalizedTask:
    return NormalizedTask(
        task_id=str(raw["id"]),
        domain=str(raw["domain"]),
        title=_make_title(str(raw["domain"]), str(raw["task_description"])),
        prompt=str(raw["task_description"]),
        difficulty=_difficulty(str(raw["difficulty"])),
    )


def _iter_jsonl(path: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


class PmrBenchSuite:
    """PMR-Bench: 10 procedural meta-reflection tasks across 4 domains."""

    name: str = "pmr-bench"
    description: str = (
        "PMR-Bench: 10 tasks (5 Intermediate + 5 Advanced) "
        "across Engineering / Education / Management / Therapy"
    )

    @property
    def root(self) -> Path:
        return _ROOT

    @lru_cache(maxsize=1)
    def load_tasks(self) -> list[NormalizedTask]:
        return [_normalize_task(row) for row in _iter_jsonl(_BENCHMARK_PATH)]

    @lru_cache(maxsize=1)
    def load_gold(self) -> list[GoldEntry]:
        return [GoldEntry.model_validate(row) for row in _iter_jsonl(_GOLD_PATH)]

    @lru_cache(maxsize=1)
    def load_gold_v2(self) -> list[GoldV2Entry]:
        if not _GOLD_V2_PATH.exists():
            return []
        return [GoldV2Entry.model_validate(row) for row in _iter_jsonl(_GOLD_V2_PATH)]

    @lru_cache(maxsize=1)
    def load_rubric(self) -> dict[str, object]:
        payload: dict[str, object] = json.loads(_RUBRIC_PATH.read_text(encoding="utf-8"))
        return payload

    def supported_metrics(self) -> tuple[str, ...]:
        return (MetricKind.RUBRIC.value,)
