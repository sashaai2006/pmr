# Результаты эксперимента: PMR vs Structured Baseline

**Дата:** 15 мая 2026  
**Проект:** MetaBotik — Procedural Meta-Reflection (Душкин Р. В., *Метакогнитивная промпт-инженерия*)  
**Статус:** финальные агрегаты после 3 прогонов (run_02 и run_03 — полный перезапуск LLM)

---

## 1. Цель эксперимента

На одном датасете (10 задач) сравнить два режима промптинга:

| Условие | Промпт | Что измеряем в первую очередь |
|---------|--------|-------------------------------|
| **PMR** | `prompts/system/core_system_prompt.md` (не менялся) | **Процедурная прозрачность** + качество решения |
| **Baseline** | `prompts/baseline_promt.txt` (задача + JSON-схема + CoT) | Качество решения в той же схеме |

**Центральный вопрос статьи:** даёт ли PMR не только «правильный ответ», но и **явный, воспроизводимый алгоритм** его получения?

Для этого введены **две независимые оси метрик** (в историческом Zarn-эксперименте):

1. **Outcome (Zarn)** — насколько ответ **верен** относительно эталона (артефакты, блокеры, policy).
2. **Procedural rigor** (архив) — детерминированный скоринг явности процедуры в сохранённом JSON; **в текущем MetaBotik модуль удалён**, для PMR-Bench используется LLM **quality judge** (`completeness`, `accuracy`, `latent_pattern_quality`, `practical_value`, `ai_score`).

---

## 2. Дизайн эксперимента (кратко)

| Параметр | Значение |
|----------|----------|
| Задач | **10** (Zarn workflow automation, expert) |
| Прогонов | **3** (`run_01`, `run_02`, `run_03`) |
| Модель | `qwen3-235b-a22b-fp8/latest`, temperature **0.2** |
| Цикл | PMR run → baseline run → Zarn eval → paired stats |
| Агрегаты | mean ± stdev по 3 прогонам |

run_02 и run_03 пересчитаны **заново через LLM** (не формульная правка).

---

# Часть A. Архив: procedural rigor (снято из кодовой базы)

Исторический Zarn-эксперимент использовал детерминированный композитный скоринг формы PMR-JSON (семь подметрик: классификация процедуры, обоснование, альтернативы, плотность critical points, adaptation notes, reflection и т.д.). Полные определения и числа **0.886 vs 0.009** остаются в истории git (модуль детерминированного скоринга удалён).

Для актуального **PMR-Bench** сравнение PMR vs structured baseline по смыслу выполняется через `metabotik quality-judge` и парную статистику по `quality_judge_by_task.jsonl`.


# Часть B. Outcome-метрики (Zarn) — кратко

Оценивают **правильность решения** по `datasets/processed/zarn_gold.jsonl`.

| Метрика | PMR | Baseline | Δ |
|---------|-----|----------|---|
| **overall_score** | **0.846 ± 0.029** | 0.787 ± 0.017 | **+7.7%** |
| blocker_visibility | 0.900 ± 0.033 | 0.578 ± 0.069 | +32 п.п. |
| required_artifact_coverage | 0.867 ± 0.031 | 0.800 ± 0.000 | +6.7 п.п. |
| handoff_completeness | 1.000 ± 0.000 | 0.900 ± 0.020 | +10 п.п. |

По прогонам overall: 0.869 / 0.813 / 0.857 (PMR) vs 0.769 / 0.802 / 0.789 (baseline).

Парная значимость overall нестабильна между прогонами (p≈0.008 в run_01, p≈0.095 в run_03); **blocker_visibility** значима во всех 3 (p<0.01).

---

# Часть C. Сводная таблица «две оси»

| Ось | Метрика | PMR | Baseline | Главный вывод |
|-----|---------|-----|----------|---------------|
| **Решение задачи** | overall_score (Zarn) | 0.846 | 0.787 | PMR лучше ~8% |
| **Смысловое качество (PMR-Bench)** | quality judge / `ai_score` | см. `results/*/pmr_quality_summary.json` | см. `baseline_quality_summary.json` | отдельные прогоны моделей |
| **Структура PMR** | procedural_trace_present | 1.0 | 0.0 | Форматы ответа принципиально разные |

---

## Ограничения

1. **10 задач, 3 прогона** — пилот, не промышленный бенчмарк.
2. **Исторический procedural rigor** был привязан к схеме PMR; для новых отчётов используйте quality judge.
3. **Одна модель** (Qwen3-235B-FP8).
4. **Outcome не всегда значим** по overall при α=0.05 — не преувеличивать p-values.
5. **Не подставлять выдуманные 87/76** — фактические overall: **84.6% / 78.7%**.

---

## Артефакты

| Что | Путь |
|-----|------|
| Агрегаты procedural | `results_pipeline_mc/aggregate_pmr_procedural.json`, `aggregate_baseline_procedural.json` |
| Парная статистика procedural | `results_pipeline_mc/aggregate_paired_procedural.json` |
| Снимки прогонов | `results_pipeline_mc/run_01/` … `run_03/` |
| По задачам (procedural) | `results/procedural_by_task.jsonl`, `results_baseline/procedural_by_task.jsonl` |
| Код quality judge (PMR-Bench) | `src/evaluation/quality_judge.py` |
| Примеры ответов | `results/{task_id}.json`, `results_baseline/{task_id}.json` |

---

*Обновлено: раздел procedural rigor сжат до архивной ссылки; outcome сжат до справочного блока.*
