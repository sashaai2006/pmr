# Отчёт по эксперименту YandexGPT на PMR-Bench

## Постановка эксперимента

- **Answer model:** `yandexgpt/latest`
- **Judge model:** `qwen3-235b-a22b-fp8/latest`
- **Бенчмарк:** PMR-Bench, 10 задач
- **Условия сравнения:** PMR prompt против структурированного non-PMR baseline
- **PMR run_id:** `20260516T130330Z-642f`
- **Baseline run_id:** `20260516T130612Z-9848`

## Основные результаты

| Метрика | PMR | Baseline | Δ |
|---|---:|---:|---:|
| `accuracy_mean` | 5.35 | 4.9 | 0.45 |
| `ai_score_mean` | 4.585 | 4.29 | 0.295 |
| `completeness_mean` | 4.4 | 4.1 | 0.3 |
| `latent_pattern_quality_mean` | 3.4 | 3.1 | 0.3 |
| `pass_rate` | 0.0 | 0.0 | 0.0 |
| `practical_value_mean` | 4.8 | 4.7 | 0.1 |

## Результаты по уровню сложности

| Уровень сложности | n | PMR `AI Score` | Baseline `AI Score` | Δ | PMR `Latent Patterns` | Baseline `Latent Patterns` | Δ |
|---|---:|---:|---:|---:|---:|---:|---:|
| Advanced | 5 | 4.75 | 4.45 | 0.3 | 3.6 | 3.2 | 0.4 |
| Intermediate | 5 | 4.42 | 4.13 | 0.29 | 3.2 | 3.0 | 0.2 |

## Результаты по доменам

| Домен | n | PMR `AI Score` | Baseline `AI Score` | Δ | PMR `Latent Patterns` | Baseline `Latent Patterns` | Δ |
|---|---:|---:|---:|---:|---:|---:|---:|
| Education | 2 | 4.6 | 4.225 | 0.375 | 3.5 | 3.0 | 0.5 |
| Engineering | 3 | 4.6 | 4.2667 | 0.3333 | 3.3333 | 3.0 | 0.3333 |
| Management | 3 | 4.8833 | 4.0667 | 0.8167 | 3.6667 | 3.0 | 0.6667 |
| Therapy | 2 | 4.1 | 4.725 | -0.625 | 3.0 | 3.5 | -0.5 |

## Интерпретация

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
