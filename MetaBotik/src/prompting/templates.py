"""Prompt assembly."""

from __future__ import annotations

from pathlib import Path

PROMPTS_ROOT = Path(__file__).resolve().parents[2] / "prompts"


def load_prompt(relative_path: str) -> str:
    path = PROMPTS_ROOT / relative_path
    if not path.exists():
        raise FileNotFoundError(f"Prompt file not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def render_string(template: str, **values: str) -> str:
    rendered = template
    for key, value in values.items():
        rendered = rendered.replace(f"{{{{{key}}}}}", value)
    return rendered.strip()


def render_template(relative_path: str, **values: str) -> str:
    return render_string(load_prompt(relative_path), **values)
