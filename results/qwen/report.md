# Отчёт по эксперименту Qwen на PMR-Bench
## Постановка эксперимента
- **Модель:** `qwen3-235b-a22b-fp8/latest`
- **Бенчмарк:** PMR-Bench, 10 задач
- **Условия сравнения:** PMR prompt против структурированного non-PMR baseline
- **Оценивание:** детерминированный `procedural_rigor_score` + LLM quality judge (`completeness`, `accuracy`, `latent_pattern_quality`, `practical_value`, вычисляемый `ai_score`)

## Основные результаты
| Метрика | PMR | Baseline | Δ |
|---|---:|---:|---:|
| `procedural_rigor_mean` | 0.8825 | 0.0833 | 0.7992 |
| `completeness_mean` | 7.8 | 6.5 | 1.3 |
| `accuracy_mean` | 8.8 | 7.4 | 1.4 |
| `latent_pattern_quality_mean` | 7.75 | 5.6 | 2.15 |
| `practical_value_mean` | 8.75 | 7.6 | 1.15 |
| `ai_score_mean` | 8.3275 | 6.865 | 1.4625 |
| `pass_rate` | 0.7 | 0.4 | 0.3 |

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
PMR превосходит baseline как по процедурной прослеживаемости, так и по смысловому качеству ответа. Наиболее выраженный прирост наблюдается в метрике `latent_pattern_quality`: это поддерживает гипотезу о том, что Procedural Meta-Reflection помогает модели лучше выявлять скрытую структуру задачи, trade-offs, точки отказа и переносимые процедурные паттерны.

Эффект сильнее выражен на задачах уровня Advanced: прирост по `AI Score` составляет 1.665 против 1.26 на Intermediate. По доменам наибольший прирост наблюдается в Management и Engineering, где задачи чаще требуют работы с множественными ограничениями, конфликтующими критериями и процедурными trade-offs.

## Включённые артефакты
- `baseline_procedural_by_task.jsonl`
- `baseline_quality_by_task.jsonl`
- `baseline_quality_summary.json`
- `baseline_summary.json`
- `compare_pmr_vs_baseline.json`
- `paired_pmr_vs_baseline.json`
- `pmr_procedural_by_task.jsonl`
- `pmr_quality_by_task.jsonl`
- `pmr_quality_summary.json`
- `pmr_summary.json`
