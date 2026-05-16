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
|---|---|---|---|
| procedural_rigor_mean | 0.6951 | 0.012 | 0.6831 |
| completeness_mean | 4.4 | 4.1 | 0.3 |
| accuracy_mean | 5.35 | 4.9 | 0.45 |
| latent_pattern_quality_mean | 3.4 | 3.1 | 0.3 |
| practical_value_mean | 4.8 | 4.7 | 0.1 |
| ai_score_mean | 4.585 | 4.29 | 0.295 |
| pass_rate | 0.0 | 0.0 | 0.0 |

## Результаты по уровню сложности

| Уровень сложности | n | PMR AI Score | Baseline AI Score | Δ | PMR Latent Patterns | Baseline Latent Patterns | Δ |
|---|---|---|---|---|---|---|---|
| Advanced | 5 | 4.75 | 4.45 | 0.3 | 3.6 | 3.2 | 0.4 |
| Intermediate | 5 | 4.42 | 4.13 | 0.29 | 3.2 | 3.0 | 0.2 |

## Результаты по доменам

| Домен | n | PMR AI Score | Baseline AI Score | Δ | PMR Latent Patterns | Baseline Latent Patterns | Δ |
|---|---|---|---|---|---|---|---|
| Education | 2 | 4.6 | 4.225 | 0.375 | 3.5 | 3.0 | 0.5 |
| Engineering | 3 | 4.6 | 4.2667 | 0.3333 | 3.3333 | 3.0 | 0.3333 |
| Management | 3 | 4.8833 | 4.0667 | 0.8167 | 3.6667 | 3.0 | 0.6667 |
| Therapy | 2 | 4.1 | 4.725 | -0.625 | 3.0 | 3.5 | -0.5 |

## Интерпретация

PMR сравнивается с той же моделью в режиме структурированного non-PMR baseline. `procedural_rigor_score` измеряет процедурную форму детерминированно; `quality judge` оценивает смысловое качество и вычисляет `AI Score` по формуле в коде.
