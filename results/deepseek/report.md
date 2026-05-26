# Отчёт по эксперименту DeepSeek 3.2 на PMR-Bench

## Постановка эксперимента

- **Модель ответа и судья:** DeepSeek 3.2 (одна и та же модель в этом прогоне; конечная точка: `deepseek-v32/latest`)
- **Бенчмарк:** PMR-Bench, 10 задач
- **Условия сравнения:** PMR prompt против структурированного non-PMR baseline
- **PMR run_id:** `20260516T135636Z-d28d`
- **Baseline run_id:** `20260516T143358Z-3fca`

## Основные результаты

| Метрика | PMR | Baseline | Δ |
|---|---:|---:|---:|
| `accuracy_mean` | 7.75 | 5.5 | 2.25 |
| `ai_score_mean` | 7.23 | 4.885 | 2.345 |
| `completeness_mean` | 6.7 | 4.9 | 1.8 |
| `latent_pattern_quality_mean` | 5.9 | 3.3 | 2.6 |
| `pass_rate` | 0.6 | 0.0 | 0.6 |
| `practical_value_mean` | 8.2 | 5.4 | 2.8 |

## Результаты по уровню сложности

| Уровень сложности | n | PMR `AI Score` | Baseline `AI Score` | Δ | PMR `Latent Patterns` | Baseline `Latent Patterns` | Δ |
|---|---:|---:|---:|---:|---:|---:|---:|
| Advanced | 5 | 7.07 | 4.56 | 2.51 | 5.8 | 3.0 | 2.8 |
| Intermediate | 5 | 7.39 | 5.21 | 2.18 | 6.0 | 3.6 | 2.4 |

## Результаты по доменам

| Домен | n | PMR `AI Score` | Baseline `AI Score` | Δ | PMR `Latent Patterns` | Baseline `Latent Patterns` | Δ |
|---|---:|---:|---:|---:|---:|---:|---:|
| Education | 2 | 6.975 | 5.225 | 1.75 | 5.5 | 4.0 | 1.5 |
| Engineering | 3 | 7.2333 | 4.3667 | 2.8667 | 5.6667 | 2.6667 | 3.0 |
| Management | 3 | 7.4833 | 4.7833 | 2.7 | 6.3333 | 3.0 | 3.3333 |
| Therapy | 2 | 7.1 | 5.475 | 1.625 | 6.0 | 4.0 | 2.0 |

## Интерпретация

Quality judge — LLM-оценка по осям и `AI Score` по формуле в коде. В этом прогоне судья совпадает с answer-моделью (DeepSeek 3.2).

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
