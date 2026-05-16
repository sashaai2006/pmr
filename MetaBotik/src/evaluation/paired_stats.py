"""Paired statistics between two per-task JSONL files (e.g. quality_judge_by_task.jsonl).

Scalar fields and nested ``{"score": float}`` axis objects (quality judge) are flattened
for pairing. Provides paired t-test, Cohen's d, and bootstrap 95% CI for mean delta.

No scipy dependency: t-CDF computed via the regularized incomplete beta function
implemented from `math` only (good enough for n>=2 paired samples).
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from statistics import mean, stdev
from typing import Any

# JSON artifact basenames whose stems must never be treated as task_ids in JSONL rows.
RESULT_ARTIFACT_JSON: frozenset[str] = frozenset(
    {
        "summary.json",
        "run_summary.json",
        "procedural_summary.json",
        "coverage_summary.json",
        "rubric_summary.json",
        "metrics_summary.json",
        "slice_breakdown.json",
        "quality_judge_summary.json",
    }
)

ARTIFACT_TASK_IDS: frozenset[str] = frozenset(
    {name.removesuffix(".json") for name in RESULT_ARTIFACT_JSON}
)


def load_by_task(path: Path) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            task_id = str(row["task_id"])
            if task_id in ARTIFACT_TASK_IDS:
                continue
            by_id[task_id] = _flatten_metrics_row(row)
    return by_id


def _flatten_metrics_row(row: dict[str, Any]) -> dict[str, Any]:
    """Keep task_id plus scalar metrics; unwrap ``axis: {score: n}`` from quality judge rows."""

    out: dict[str, Any] = {"task_id": row["task_id"]}
    for key, value in row.items():
        if key == "task_id":
            continue
        if _is_number(value):
            out[key] = float(value)
        elif isinstance(value, dict) and _is_number(value.get("score")):
            out[key] = float(value["score"])
    return out


def paired_stats(
    *,
    candidate_path: Path,
    baseline_path: Path,
    candidate_label: str = "pmr",
    baseline_label: str = "baseline",
    metric_keys: list[str] | None = None,
    bootstrap_samples: int = 2000,
    bootstrap_seed: int = 17,
    alpha: float = 0.05,
) -> dict[str, Any]:
    candidate_rows = load_by_task(candidate_path)
    baseline_rows = load_by_task(baseline_path)
    common_ids = sorted(set(candidate_rows) & set(baseline_rows))
    if not common_ids:
        raise ValueError(
            f"No common task_ids between {candidate_path} and {baseline_path}"
        )
    sample_row = candidate_rows[common_ids[0]]
    if metric_keys is None:
        metric_keys = sorted(
            key
            for key, value in sample_row.items()
            if _is_number(value) and key != "task_id"
        )

    metric_results: list[dict[str, Any]] = []
    for metric in metric_keys:
        cand = [_as_float(candidate_rows[tid].get(metric)) for tid in common_ids]
        base = [_as_float(baseline_rows[tid].get(metric)) for tid in common_ids]
        diffs = [c - b for c, b in zip(cand, base)]
        cand_mean = mean(cand) if cand else 0.0
        base_mean = mean(base) if base else 0.0
        delta_mean = mean(diffs) if diffs else 0.0
        relative_percent = (
            None
            if base_mean == 0
            else round((delta_mean / abs(base_mean)) * 100.0, 2)
        )
        t_stat, p_value = _paired_ttest(diffs)
        cohen_d = _cohen_d_paired(diffs)
        ci_low, ci_high = _bootstrap_ci(diffs, alpha=alpha, samples=bootstrap_samples, seed=bootstrap_seed)
        wins = _win_counts(cand, base, candidate_label, baseline_label)
        metric_results.append({
            "metric": metric,
            f"{candidate_label}_mean": round(cand_mean, 4),
            f"{baseline_label}_mean": round(base_mean, 4),
            "delta_mean": round(delta_mean, 4),
            "relative_change_percent": relative_percent,
            "paired_t_statistic": round(t_stat, 4) if math.isfinite(t_stat) else None,
            "paired_p_value": round(p_value, 6) if math.isfinite(p_value) else None,
            "cohen_d_paired": round(cohen_d, 4) if math.isfinite(cohen_d) else None,
            "ci_95": [round(ci_low, 4), round(ci_high, 4)],
            "significant_at_alpha": (
                bool(math.isfinite(p_value) and p_value < alpha)
            ),
            **wins,
        })

    overall = next((row for row in metric_results if row["metric"] == "ai_score"), None)
    if overall is None and metric_results:
        overall = metric_results[0]
    return {
        "title": f"{candidate_label} vs {baseline_label} (paired)",
        "n_tasks": len(common_ids),
        "alpha": alpha,
        "candidate_label": candidate_label,
        "baseline_label": baseline_label,
        "candidate_path": str(candidate_path),
        "baseline_path": str(baseline_path),
        "overall": overall,
        "metrics": metric_results,
    }


def save_paired_stats(stats: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path = output_path.with_suffix(".md")
    markdown_path.write_text(format_paired_stats_markdown(stats), encoding="utf-8")


def format_paired_stats_markdown(stats: dict[str, Any]) -> str:
    lines: list[str] = [
        f"# Парная статистика ({stats['candidate_label']} vs {stats['baseline_label']})",
        "",
        f"- n задач: **{stats['n_tasks']}**, α = {stats['alpha']}",
        f"- кандидат: `{stats['candidate_path']}`",
        f"- baseline: `{stats['baseline_path']}`",
        "",
        "## Сводка по метрикам",
        "",
        f"| Метрика | {stats['candidate_label']} | {stats['baseline_label']} | Δ | rel% | p | Cohen's d | 95% CI | sig |",
        "|---|---:|---:|---:|---:|---:|---:|---|:---:|",
    ]
    cand = stats["candidate_label"]
    base = stats["baseline_label"]
    for row in stats["metrics"]:
        rel = row["relative_change_percent"]
        rel_str = "—" if rel is None else f"{rel:+.2f}%"
        p_str = "—" if row["paired_p_value"] is None else f"{row['paired_p_value']:.4f}"
        d_str = "—" if row["cohen_d_paired"] is None else f"{row['cohen_d_paired']:.2f}"
        ci = row["ci_95"]
        sig = "✓" if row["significant_at_alpha"] else "·"
        lines.append(
            f"| `{row['metric']}` | {row[f'{cand}_mean']:.4f} | {row[f'{base}_mean']:.4f}"
            f" | {row['delta_mean']:+.4f} | {rel_str} | {p_str} | {d_str}"
            f" | [{ci[0]:+.4f}, {ci[1]:+.4f}] | {sig} |"
        )
    return "\n".join(lines) + "\n"


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _as_float(value: Any) -> float:
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    return 0.0


def _paired_ttest(diffs: list[float]) -> tuple[float, float]:
    n = len(diffs)
    if n < 2:
        return (float("nan"), float("nan"))
    mu = mean(diffs)
    sd = stdev(diffs)
    if sd == 0:
        if mu == 0:
            return (0.0, 1.0)
        return (float("inf"), 0.0)
    t = mu / (sd / math.sqrt(n))
    df = n - 1
    p = _two_sided_t_p_value(t, df)
    return (t, p)


def _two_sided_t_p_value(t: float, df: int) -> float:
    if not math.isfinite(t):
        return 0.0
    x = df / (df + t * t)
    a = df / 2.0
    b = 0.5
    cdf_tail = 0.5 * _betainc_regularized(x, a, b)
    return min(1.0, max(0.0, 2.0 * cdf_tail))


def _betainc_regularized(x: float, a: float, b: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lbeta = math.lgamma(a) + math.lgamma(b) - math.lgamma(a + b)
    front = math.exp(math.log(x) * a + math.log(1.0 - x) * b - lbeta) / a
    cf = _betacf(x, a, b)
    return front * cf


def _betacf(x: float, a: float, b: float, max_iter: int = 200, eps: float = 1e-12) -> float:
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < 1e-300:
        d = 1e-300
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            return h
    return h


def _cohen_d_paired(diffs: list[float]) -> float:
    if len(diffs) < 2:
        return float("nan")
    sd = stdev(diffs)
    if sd == 0:
        if mean(diffs) == 0:
            return 0.0
        return float("inf")
    return mean(diffs) / sd


def _bootstrap_ci(
    diffs: list[float],
    *,
    alpha: float = 0.05,
    samples: int = 2000,
    seed: int = 17,
) -> tuple[float, float]:
    n = len(diffs)
    if n == 0:
        return (0.0, 0.0)
    if n == 1:
        return (diffs[0], diffs[0])
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(samples):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        means.append(sum(sample) / n)
    means.sort()
    lo = means[int((alpha / 2.0) * (samples - 1))]
    hi = means[int((1.0 - alpha / 2.0) * (samples - 1))]
    return (lo, hi)


def _win_counts(
    cand: list[float],
    base: list[float],
    candidate_label: str,
    baseline_label: str,
) -> dict[str, int]:
    wins = ties = losses = 0
    for c, b in zip(cand, base):
        if c > b:
            wins += 1
        elif c < b:
            losses += 1
        else:
            ties += 1
    return {
        f"wins_{candidate_label}": wins,
        f"wins_{baseline_label}": losses,
        "ties": ties,
    }


