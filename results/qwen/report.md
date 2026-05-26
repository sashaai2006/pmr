# Отчёт по эксперименту Qwen3 235B A22B Instruct 2507 FP8 на PMR-Bench
## Постановка эксперимента
- **Модель:** Qwen3 235B A22B Instruct 2507 FP8 (конечная точка в конвейере: `qwen3-235b-a22b-fp8/latest`)
- **Бенчмарк:** PMR-Bench, 10 задач
- **Условия сравнения:** PMR prompt против структурированного non-PMR baseline
- **Оценивание:** LLM quality judge (`completeness`, `accuracy`, `latent_pattern_quality`, `practical_value`, вычисляемый `ai_score`)

## Основные результаты

| Метрика | PMR | Baseline | Δ |
|---|---:|---:|---:|
| `accuracy_mean` | 8.8 | 7.4 | 1.4 |
| `ai_score_mean` | 8.3275 | 6.865 | 1.4625 |
| `completeness_mean` | 7.8 | 6.5 | 1.3 |
| `latent_pattern_quality_mean` | 7.75 | 5.6 | 2.15 |
| `pass_rate` | 0.7 | 0.4 | 0.3 |
| `practical_value_mean` | 8.75 | 7.6 | 1.15 |

## Результаты по уровню сложности

| Уровень сложности | n | PMR `AI Score` | Baseline `AI Score` | Δ | PMR `Latent Patterns` | Baseline `Latent Patterns` | Δ |
|---|---:|---:|---:|---:|---:|---:|---:|
| Advanced | 5 | 8.715 | 7.05 | 1.665 | 8.3 | 5.8 | 2.5 |
| Intermediate | 5 | 7.94 | 6.68 | 1.26 | 7.2 | 5.4 | 1.8 |

## Результаты по доменам

| Домен | n | PMR `AI Score` | Baseline `AI Score` | Δ | PMR `Latent Patterns` | Baseline `Latent Patterns` | Δ |
|---|---:|---:|---:|---:|---:|---:|---:|
| Education | 2 | 8.15 | 7.35 | 0.8 | 7.25 | 6.0 | 1.25 |
| Engineering | 3 | 8.325 | 6.6833 | 1.6417 | 7.3333 | 5.3333 | 2.0 |
| Management | 3 | 8.6333 | 6.8167 | 1.8167 | 8.6667 | 5.6667 | 3.0 |
| Therapy | 2 | 8.05 | 6.725 | 1.325 | 7.5 | 5.5 | 2.0 |

## Интерпретация
PMR превосходит baseline по смысловому качеству ответа по осям quality judge. Наиболее выраженный прирост часто наблюдается в `latent_pattern_quality`: это поддерживает гипотезу о том, что Procedural Meta-Reflection помогает модели лучше выявлять скрытую структуру задачи, trade-offs, точки отказа и переносимые процедурные паттерны.

Эффект может сильнее проявляться на задачах уровня Advanced. Срезы по доменам см. в таблице выше.

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
