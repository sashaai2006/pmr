"""JSON result formatting."""

from __future__ import annotations

import json
from pathlib import Path

from src.domain.schemas import AgentResult


def format_json(result: AgentResult) -> str:
    """Serialize for disk: omit runtime metadata (model, temperature, etc.)."""
    return json.dumps(
        result.model_dump(mode="json", exclude={"metadata"}),
        ensure_ascii=False,
        indent=2,
    )


def save_json(result: AgentResult, output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{result.task_id}.json"
    path.write_text(format_json(result), encoding="utf-8")
    return path
