"""Generic comparison between two run summaries (no Zarn-specific dictionary).

Reads two `summary.json` files produced by `EvalUseCase` and emits a deltas
table per scalar metric: candidate minus baseline, with optional relative
percent change, win label, and a short Markdown render.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

NON_COMPARABLE_KEYS: frozenset[str] = frozenset(
    {
        "task_count",
        "failed_tasks",
        "n_tasks",
        "n_cases",
        "suite",
        "mode",
        "run_id",
        # Legacy: deterministic gold-token overlap (removed from eval).
        "coverage_macro",
        "coverage_micro",
    },
)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _winner(label_a: str, label_b: str, delta: float) -> str:
    if delta > 0:
        return label_a
    if delta < 0:
        return label_b
    return "tie"


def _change_label(delta: float) -> str:
    if delta > 0:
        return "improved"
    if delta < 0:
        return "regressed"
    return "no_change"


def _round(value: float | None) -> float | None:
    if value is None:
        return None
    return round(float(value), 4)


def load_summary(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise TypeError(f"summary must be a JSON object: {path}")
    return payload


def compare_summaries(
    *,
    candidate: dict[str, Any],
    baseline: dict[str, Any],
    candidate_label: str = "candidate",
    baseline_label: str = "baseline",
) -> dict[str, Any]:
    """Compare two summaries. Treats every shared scalar key as a metric."""

    metric_names = sorted(
        key
        for key in candidate.keys() | baseline.keys()
        if key not in NON_COMPARABLE_KEYS
        and _is_number(candidate.get(key))
        and _is_number(baseline.get(key))
    )
    metric_rows: list[dict[str, Any]] = []
    for name in metric_names:
        cand = float(candidate[name])
        base = float(baseline[name])
        delta = cand - base
        relative = None if base == 0.0 else (delta / abs(base)) * 100.0
        metric_rows.append({
            "metric": name,
            f"{candidate_label}_value": _round(cand),
            f"{baseline_label}_value": _round(base),
            "delta": _round(delta),
            "relative_change_percent": _round(relative),
            "winner": _winner(candidate_label, baseline_label, delta),
            "change_label": _change_label(delta),
        })

    return {
        "title": f"{candidate_label} vs {baseline_label}",
        "candidate_label": candidate_label,
        "baseline_label": baseline_label,
        "metrics": metric_rows,
    }


def save_comparison(comparison: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(comparison, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path = output_path.with_suffix(".md")
    md_path.write_text(format_markdown(comparison), encoding="utf-8")


def format_markdown(comparison: dict[str, Any]) -> str:
    cand = comparison["candidate_label"]
    base = comparison["baseline_label"]
    lines = [
        f"# {comparison['title']}",
        "",
        f"| Metric | {cand} | {base} | Δ | rel % | winner |",
        "|---|---:|---:|---:|---:|:---:|",
    ]
    for row in comparison["metrics"]:
        rel = row["relative_change_percent"]
        rel_str = "—" if rel is None else f"{rel:+.2f}%"
        delta = row["delta"]
        lines.append(
            f"| `{row['metric']}` | {row[f'{cand}_value']:.4f} | {row[f'{base}_value']:.4f}"
            f" | {delta:+.4f} | {rel_str} | {row['winner']} |"
        )
    return "\n".join(lines) + "\n"
