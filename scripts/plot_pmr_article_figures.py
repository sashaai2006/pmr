#!/usr/bin/env python3
"""Генерация рисунков для статьи (boxplot I и LPQ по системам и условиям)."""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib as mpl

# Кириллица в подписях (DejaVu Sans поддерживает кириллицу)
mpl.rcParams["font.family"] = "DejaVu Sans"
mpl.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parents[1]
PAPER_FIGURES = ROOT / "docs" / "paper" / "figures"


def load_metric(path: Path, metric: str) -> list[float]:
    out: list[float] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if metric == "ai_score":
            out.append(float(row["ai_score"]))
        else:
            out.append(float(row[metric]["score"]))
    return out


def main() -> None:
    systems = [
        ("Qwen3\n235B", ROOT / "results/qwen"),
        ("DeepSeek\n3.2", ROOT / "results/deepseek"),
        ("YandexGPT\n5.1 Pro", ROOT / "results/yandexgpt"),
    ]
    fig, axes = plt.subplots(1, 2, figsize=(10.2, 4.6), dpi=150)

    for ax, metric, title in zip(
        axes,
        ("ai_score", "latent_pattern_quality"),
        ("Интегральный показатель $I$", "LPQ (скрытые зависимости)"),
    ):
        positions: list[float] = []
        data: list[list[float]] = []
        labels: list[str] = []
        pos = 0.0
        step = 3.0
        for sys_name, base in systems:
            pmr = load_metric(base / "pmr_quality_by_task.jsonl", metric)
            bl = load_metric(base / "baseline_quality_by_task.jsonl", metric)
            for arr, suffix in ((bl, "база"), (pmr, "цель")):
                data.append(arr)
                labels.append(f"{sys_name}\n{suffix}")
                positions.append(pos)
                pos += 1.0
            pos += 0.35  # зазор между системами

        bp = ax.boxplot(
            data,
            positions=positions,
            widths=0.62,
            patch_artist=True,
            showmeans=True,
            meanline=True,
        )
        for patch, p in zip(bp["boxes"], positions):
            # чётные — база, нечётные — цель внутри каждой тройки по смыслу: мы кладём bl, pmr поочерёдно
            idx = positions.index(p)
            patch.set_facecolor("#c8e6f3" if idx % 2 == 0 else "#fff3c4")
            patch.set_alpha(0.92)
        ax.set_xticks(positions)
        ax.set_xticklabels(labels, fontsize=7.5)
        ax.set_ylim(0, 10.5)
        ax.set_ylabel("Балл (0–10)")
        ax.set_title(title)
        ax.grid(True, axis="y", linestyle=":", alpha=0.75)

    fig.suptitle(
        "Распределения по 10 задачам: целевое (PMR) и базовое условие",
        fontsize=11,
        y=1.02,
    )
    fig.tight_layout()
    PAPER_FIGURES.mkdir(parents=True, exist_ok=True)
    out_png = PAPER_FIGURES / "pmr_I_LPQ_boxplots.png"
    fig.savefig(out_png, bbox_inches="tight")
    print("Wrote", out_png)


if __name__ == "__main__":
    main()
