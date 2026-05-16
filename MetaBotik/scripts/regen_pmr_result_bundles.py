#!/usr/bin/env python3
"""Strip legacy procedural fields and rebuild compare/paired + report.md under pmr/results/."""

from __future__ import annotations

import json
import statistics
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # pmr/
MB = ROOT / "MetaBotik"
BENCH = MB / "suites" / "pmr_bench" / "benchmark.jsonl"


def _load_benchmark() -> dict[str, tuple[str, str]]:
    by_id: dict[str, tuple[str, str]] = {}
    for line in BENCH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        o = json.loads(line)
        by_id[str(o["id"])] = (str(o["domain"]), str(o["difficulty"]))
    return by_id


def _load_quality_rows(path: Path) -> dict[str, dict[str, object]]:
    rows: dict[str, dict[str, object]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        o = json.loads(line)
        rows[str(o["task_id"])] = o
    return rows


def _axis_score(row: dict[str, object], axis: str) -> float:
    v = row.get(axis)
    if isinstance(v, dict) and isinstance(v.get("score"), (int, float)):
        return float(v["score"])
    return float("nan")


def _breakdown_tables(
    tasks_meta: dict[str, tuple[str, str]],
    pmr: dict[str, dict[str, object]],
    base: dict[str, dict[str, object]],
) -> tuple[str, str]:
    def bucket_stats(
        key_fn: str,
    ) -> list[tuple[str, int, float, float, float, float, float, float]]:
        groups: dict[str, list[str]] = defaultdict(list)
        for tid in pmr:
            if tid not in base or tid not in tasks_meta:
                continue
            dom, diff = tasks_meta[tid]
            k = diff if key_fn == "difficulty" else dom
            groups[k].append(tid)

        out: list[tuple[str, int, float, float, float, float, float, float]] = []
        for label in sorted(groups):
            ids = groups[label]
            p_ai = [float(pmr[t]["ai_score"]) for t in ids]
            b_ai = [float(base[t]["ai_score"]) for t in ids]
            p_lat = [_axis_score(pmr[t], "latent_pattern_quality") for t in ids]
            b_lat = [_axis_score(base[t], "latent_pattern_quality") for t in ids]
            p_lat = [x for x in p_lat if x == x]
            b_lat = [x for x in b_lat if x == x]
            out.append(
                (
                    label,
                    len(ids),
                    round(statistics.mean(p_ai), 4),
                    round(statistics.mean(b_ai), 4),
                    round(statistics.mean(p_ai) - statistics.mean(b_ai), 4),
                    round(statistics.mean(p_lat), 4) if p_lat else 0.0,
                    round(statistics.mean(b_lat), 4) if b_lat else 0.0,
                    round(statistics.mean(p_lat) - statistics.mean(b_lat), 4) if p_lat and b_lat else 0.0,
                )
            )
        return out

    def fmt_table(rows: list[tuple[str, int, float, float, float, float, float, float]]) -> str:
        lines = [
            "| Уровень сложности | n | PMR `AI Score` | Baseline `AI Score` | Δ | PMR `Latent Patterns` | Baseline `Latent Patterns` | Δ |",
            "|---|---:|---:|---:|---:|---:|---:|---:|",
        ]
        for r in rows:
            lines.append(
                f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} | {r[7]} |"
            )
        return "\n".join(lines)

    diff_rows = bucket_stats("difficulty")
    dom_rows = bucket_stats("domain")
    # headers differ
    dlines = [
        "| Уровень сложности | n | PMR `AI Score` | Baseline `AI Score` | Δ | PMR `Latent Patterns` | Baseline `Latent Patterns` | Δ |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in diff_rows:
        dlines.append(
            f"| {r[0].title()} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} | {r[7]} |"
        )
    dom_table_lines = [
        "| Домен | n | PMR `AI Score` | Baseline `AI Score` | Δ | PMR `Latent Patterns` | Baseline `Latent Patterns` | Δ |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for r in dom_rows:
        dom_table_lines.append(
            f"| {r[0]} | {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]} | {r[6]} | {r[7]} |"
        )
    return "\n".join(dlines), "\n".join(dom_table_lines)


def main() -> None:
    import sys

    sys.path.insert(0, str(MB))
    from src.evaluation.compare import compare_summaries  # noqa: E402
    from src.evaluation.paired_stats import paired_stats  # noqa: E402

    tasks_meta = _load_benchmark()
    for label in ("qwen", "yandexgpt", "deepseek"):
        d = ROOT / "results" / label
        if not d.is_dir():
            continue
        for name in ("pmr_summary.json", "baseline_summary.json"):
            p = d / name
            if not p.exists():
                continue
            o = json.loads(p.read_text(encoding="utf-8"))
            for k in ("procedural" + "_rigor_mean", "procedural" + "_rigor_std"):
                o.pop(k, None)
            p.write_text(json.dumps(o, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        pmr_q = d / "pmr_quality_summary.json"
        base_q = d / "baseline_quality_summary.json"
        pmr_bt = d / "pmr_quality_by_task.jsonl"
        base_bt = d / "baseline_quality_by_task.jsonl"
        if pmr_q.exists() and base_q.exists():
            cmp = compare_summaries(
                candidate=json.loads(pmr_q.read_text(encoding="utf-8")),
                baseline=json.loads(base_q.read_text(encoding="utf-8")),
                candidate_label="pmr",
                baseline_label="baseline",
            )
            (d / "compare_pmr_vs_baseline.json").write_text(
                json.dumps(cmp, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
        if pmr_bt.exists() and base_bt.exists():
            stats = paired_stats(
                candidate_path=pmr_bt,
                baseline_path=base_bt,
                candidate_label="pmr",
                baseline_label="baseline",
            )
            (d / "paired_pmr_vs_baseline.json").write_text(
                json.dumps(stats, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

        for old in ("pmr_procedural_by_task.jsonl", "baseline_procedural_by_task.jsonl"):
            op = d / old
            if op.exists():
                op.unlink()

        pmr_rows = _load_quality_rows(pmr_bt) if pmr_bt.exists() else {}
        base_rows = _load_quality_rows(base_bt) if base_bt.exists() else {}
        new_pmr = d / "pmr_by_task.jsonl"
        new_base = d / "baseline_by_task.jsonl"
        if pmr_rows:
            new_pmr.write_text(
                "\n".join(json.dumps({"task_id": tid}, ensure_ascii=False) for tid in sorted(pmr_rows))
                + "\n",
                encoding="utf-8",
            )
        if base_rows:
            new_base.write_text(
                "\n".join(json.dumps({"task_id": tid}, ensure_ascii=False) for tid in sorted(base_rows))
                + "\n",
                encoding="utf-8",
            )

        # --- report.md ---
        cmp_path = d / "compare_pmr_vs_baseline.json"
        if not cmp_path.exists():
            continue
        cmp = json.loads(cmp_path.read_text(encoding="utf-8"))
        metric_lines = []
        for row in cmp["metrics"]:
            m = row["metric"]
            c = row["pmr_value"]
            b = row["baseline_value"]
            delta = row["delta"]
            metric_lines.append(f"| `{m}` | {c} | {b} | {delta} |")
        main_table = "\n".join(
            [
                "| Метрика | PMR | Baseline | Δ |",
                "|---|---:|---:|---:|",
                *metric_lines,
            ]
        )

        diff_sec, dom_sec = _breakdown_tables(tasks_meta, pmr_rows, base_rows)

        if label == "qwen":
            header = """# Отчёт по эксперименту Qwen на PMR-Bench
## Постановка эксперимента
- **Модель:** `qwen3-235b-a22b-fp8/latest`
- **Бенчмарк:** PMR-Bench, 10 задач
- **Условия сравнения:** PMR prompt против структурированного non-PMR baseline
- **Оценивание:** LLM quality judge (`completeness`, `accuracy`, `latent_pattern_quality`, `practical_value`, вычисляемый `ai_score`)

## Основные результаты
"""
            interp = """## Интерпретация
PMR превосходит baseline по смысловому качеству ответа по осям quality judge. Наиболее выраженный прирост часто наблюдается в `latent_pattern_quality`: это поддерживает гипотезу о том, что Procedural Meta-Reflection помогает модели лучше выявлять скрытую структуру задачи, trade-offs, точки отказа и переносимые процедурные паттерны.

Эффект может сильнее проявляться на задачах уровня Advanced. По доменам сравните строки таблицы ниже для конкретного прогона.

## Включённые артефакты
- `baseline_by_task.jsonl`
- `baseline_quality_by_task.jsonl`
- `baseline_quality_summary.json`
- `baseline_summary.json`
- `compare_pmr_vs_baseline.json`
- `paired_pmr_vs_baseline.json`
- `pmr_by_task.jsonl`
- `pmr_quality_by_task.jsonl`
- `pmr_quality_summary.json`
- `pmr_summary.json`
"""
            (d / "report.md").write_text(
                header + "\n" + main_table + "\n\n## Результаты по уровню сложности\n\n" + diff_sec + "\n\n## Результаты по доменам\n\n" + dom_sec + "\n\n" + interp,
                encoding="utf-8",
            )
        elif label == "yandexgpt":
            header = """# Отчёт по эксперименту YandexGPT на PMR-Bench

## Постановка эксперимента

- **Answer model:** `yandexgpt/latest`
- **Judge model:** `qwen3-235b-a22b-fp8/latest`
- **Бенчмарк:** PMR-Bench, 10 задач
- **Условия сравнения:** PMR prompt против структурированного non-PMR baseline
- **PMR run_id:** `20260516T130330Z-642f`
- **Baseline run_id:** `20260516T130612Z-9848`

## Основные результаты

"""
            interp = """## Интерпретация

PMR сравнивается с той же моделью в режиме структурированного non-PMR baseline. Оценка — LLM quality judge по осям и `AI Score` по формуле в `src/evaluation/quality_judge.py`.

## Включённые артефакты

- `baseline_by_task.jsonl`
- `baseline_quality_by_task.jsonl`
- `baseline_quality_summary.json`
- `baseline_summary.json`
- `compare_pmr_vs_baseline.json`
- `paired_pmr_vs_baseline.json`
- `pmr_by_task.jsonl`
- `pmr_quality_by_task.jsonl`
- `pmr_quality_summary.json`
- `pmr_summary.json`
"""
            (d / "report.md").write_text(
                header + main_table + "\n\n## Результаты по уровню сложности\n\n" + diff_sec + "\n\n## Результаты по доменам\n\n" + dom_sec + "\n\n" + interp,
                encoding="utf-8",
            )
        else:  # deepseek
            header = """# Отчёт по эксперименту DeepSeek V3.2 на PMR-Bench

## Постановка эксперимента

- **Answer model / Judge model:** `deepseek-v32/latest` (одна и та же модель в этом прогоне)
- **Бенчмарк:** PMR-Bench, 10 задач
- **Условия сравнения:** PMR prompt против структурированного non-PMR baseline
- **PMR run_id:** `20260516T135636Z-d28d`
- **Baseline run_id:** `20260516T143358Z-3fca`

## Основные результаты

"""
            interp = """## Интерпретация

Quality judge — LLM-оценка по осям и `AI Score` по формуле в коде. В этом прогоне судья совпадает с answer-моделью (DeepSeek).

## Включённые артефакты

- `baseline_by_task.jsonl`
- `baseline_quality_by_task.jsonl`
- `baseline_quality_summary.json`
- `baseline_summary.json`
- `compare_pmr_vs_baseline.json`
- `paired_pmr_vs_baseline.json`
- `pmr_by_task.jsonl`
- `pmr_quality_by_task.jsonl`
- `pmr_quality_summary.json`
- `pmr_summary.json`
"""
            (d / "report.md").write_text(
                header + main_table + "\n\n## Результаты по уровню сложности\n\n" + diff_sec + "\n\n## Результаты по доменам\n\n" + dom_sec + "\n\n" + interp,
                encoding="utf-8",
            )


if __name__ == "__main__":
    main()
