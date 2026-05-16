# PMR Benchmark — Procedural Meta-Reflection

Бенчмарк из 10 кейсов для проверки техники **«Процедурная мета-рефлексия»** (раздел 4.3 книги Р. В. Душкина «Метакогнитивная промпт-инженерия»). Назначение — измерить, насколько ИИ-агент способен не просто решить профессиональную задачу, а явно обосновать процедурный выбор: декомпозицию, отвергнутые альтернативы, точки невозврата и переиспользуемый мета-протокол.

## Структура артефактов

| Файл | Назначение | Кому виден |
|---|---|---|
| `pmr_benchmark.jsonl` | Постановки задач (10 строк) | Тестируемому ИИ-агенту |
| `pmr_gold.jsonl` | Эталон-«полуответы» + рубрика + claims | Только судье (никогда не подавать агенту) |
| `score_benchmark.py` | Подсчёт метрик и генерация отчёта | Только судье |
| `ДРВ_Метакогнитивная_промпт_инженерия.pdf` | Первоисточник техники (стр. 70-75) | — |

Изоляция критична: `pmr_benchmark.jsonl` намеренно не содержит ни `reference_answer`, ни `expected_meta_elements`, ни `evaluation_rubric`. Утечка любого поля из эталона в контекст агента обесценивает измерение.

## Состав 10 кейсов

| ID | Domain | Difficulty | Содержание |
|---|---|---|---|
| PMR-001 | Engineering | Intermediate | Жизненный цикл ПО медицинского устройства по IEC 62304 |
| PMR-002 | Education | Intermediate | Формирующее оценивание на онлайн-курсе с 500 студентами |
| PMR-003 | Management | Intermediate | Финальное структурированное интервью senior-инженера |
| PMR-004 | Management | Intermediate | Приоритизация разнотипного backlog (47 задач) |
| PMR-005 | Therapy | Intermediate | Выбор протокола психотерапии при ГТР |
| PMR-006 | Engineering | Advanced | RCA многофакторного банковского инцидента |
| PMR-007 | Engineering | Advanced | V&V цифрового двойника турбины |
| PMR-008 | Education | Advanced | Межпредметный проект под ФГОС при нулевом бюджете |
| PMR-009 | Management | Advanced | Кризис репутации производителя детского питания |
| PMR-010 | Therapy | Advanced | Работа с сопротивлением в долгосрочной КПТ |

Распределение: 5 Intermediate + 5 Advanced, по доменам Engineering / Education / Management / Therapy (3 / 2 / 3 / 2 соответственно).

## Схемы файлов

### `pmr_benchmark.jsonl` (что видит агент)

```json
{
  "id": "PMR-001",
  "domain": "Engineering",
  "difficulty": "Intermediate",
  "task_description": "<нейтрально сформулированная задача>"
}
```

### `pmr_gold.jsonl` (что видит судья)

```json
{
  "id": "PMR-001",
  "reference_answer": {
    "stage_1_procedural_analysis": "Скелет ~80-120 слов по этапу 1 техники PMR",
    "stage_2_solution_with_commentary": "Скелет ~80-120 слов по этапу 2",
    "stage_3_reflection": "Скелет ~80-120 слов по этапу 3"
  },
  "expected_meta_elements": {
    "decomposition": ["claim 1", "claim 2", "claim 3"],
    "rejected_alternatives": ["альтернатива X — почему отвергнута", "..."],
    "critical_points": ["точка адаптации/невозврата 1", "..."],
    "meta_protocol": ["правило обобщения 1", "..."]
  },
  "evaluation_rubric": {
    "procedural_self_awareness_0_2": "0 = ...; 1 = ...; 2 = ...",
    "decomposition_justification_0_2": "...",
    "rejected_alternatives_0_2": "...",
    "critical_points_and_adaptation_0_2": "...",
    "reproducibility_meta_protocol_0_2": "...",
    "total_max": 10,
    "pass_threshold": 7
  },
  "metadata": {
    "target_skill": "...",
    "source_section": "4.3 Procedural Meta-Reflection",
    "discriminator_note": "Почему без PMR кейс провалится"
  }
}
```

### Файл ответов судьи (создаётся вами)

```json
{
  "id": "PMR-001",
  "agent_response": "<полный ответ агента>",
  "rubric_scores": {
    "procedural_self_awareness": 2,
    "decomposition_justification": 1,
    "rejected_alternatives": 0,
    "critical_points_and_adaptation": 2,
    "reproducibility_meta_protocol": 1
  },
  "claims_hit": {
    "decomposition":         [1, 1, 0],
    "rejected_alternatives": [1, 1, 0],
    "critical_points":       [1, 0, 1],
    "meta_protocol":         [0, 1]
  }
}
```

Длины массивов в `claims_hit` обязаны совпадать с длинами `expected_meta_elements` в `pmr_gold.jsonl` — скрипт это проверяет.

## Воркфлоу проведения замера

1. **Подайте `pmr_benchmark.jsonl` тестируемому агенту.** Каждая строка — независимый запрос. Подавать `pmr_gold.jsonl` агенту запрещено.
2. **Соберите ответы агента в файл `answers_pmr.jsonl`.** Для генерации пустого шаблона:
   ```bash
   python3 score_benchmark.py --gold pmr_gold.jsonl --init-template answers_pmr.jsonl
   ```
3. **Заполните `rubric_scores` (0-2 по 5 осям) и `claims_hit` (0/1 по позициям claims).** Судья — человек-эксперт, LLM-судья или гибрид; в любом случае руководствуется текстами `evaluation_rubric` и `expected_meta_elements` из эталона.
4. **(Опционально) Соберите baseline.** Прогоните того же агента на тех же задачах с обычным промптом (без PMR-инструкций) и оцените тем же судьёй. Сохраните в `answers_baseline.jsonl`.
5. **Запустите подсчёт:**
   ```bash
   python3 score_benchmark.py \
       --benchmark pmr_benchmark.jsonl \
       --gold pmr_gold.jsonl \
       --answers answers_pmr.jsonl \
       --baseline answers_baseline.jsonl \
       --judge-mode manual \
       --out report.json \
       --report-md report.md
   ```

## Метрики

### Per-case (на один кейс)

| Метрика | Диапазон | Формула |
|---|---|---|
| `rubric_score` | 0–10 | сумма 5 осей × 0–2 |
| `element_coverage` | 0–1 | hits / total claims (по 4 категориям) |
| `pass_binary` | {0, 1} | `rubric_score ≥ 7` |

### Per-model aggregate (10 кейсов)

- `mean_score`, `std_score`, `median_score`, `min/max`
- `pass_rate` — доля кейсов с `pass_binary = 1`
- `coverage_macro` — среднее `element_coverage` по кейсам
- `coverage_micro` — общий hit rate по всем claims в выборке
- Разбивка по `difficulty` (Intermediate vs Advanced) и `domain` (4 группы)
- Per-axis средние по 5 рубрикам — показывает, какой компонент PMR проседает у модели

### A/B (PMR-промпт vs baseline)

- `Δmean_score = mean(PMR) − mean(baseline)`
- **Cohen's d** для парных измерений: `d = mean(diff) / std(diff)`
- **Paired Wilcoxon signed-rank** двусторонний p-value (`scipy.stats.wilcoxon` если установлен, иначе нормальное приближение)
- `win_rate` — доля кейсов, где `rubric_score(PMR) ≥ rubric_score(baseline) + 1`
- 95% bootstrap CI для `Δmean` (1000 resamples по умолчанию, настраивается `--bootstrap-iters`)

## Self-test

Перед боевым прогоном можно проверить связность всей инфраструктуры:

```bash
python3 score_benchmark.py --self-test
```

Скрипт сгенерирует пару синтетических наборов ответов (один «высокий», один «низкий»), прогонит весь конвейер и удалит временные файлы. Ожидаемый результат: mean_score ≈ 8 / 10, Δmean ≈ +5, Cohen's d > 2, Wilcoxon p < 0.01.

## Что НЕ включено в первую версию

- **Cronbach's α / ICC между судьями** — требует двух и более независимых судей в отдельной серии. Добавляется во вторую версию при наличии повторных замеров.
- **Item difficulty и item discrimination** — требуют выборку из 5+ разных моделей. Полезно для будущей валидации инструмента, не для первой статьи.
- **LLM-судья «из коробки»** — `--judge-mode llm` сейчас информационный тег. Реализация LLM-судьи отнесена в отдельный модуль (вне области бенчмарка).

## Источник техники

Душкин Р. В. «Метакогнитивная промпт-инженерия», раздел **4.3 «Процедурная мета-рефлексия»** (стр. 70–75 в [`ДРВ_Метакогнитивная_промпт_инженерия.pdf`](ДРВ_Метакогнитивная_промпт_инженерия.pdf)). Четыре операциональных компонента, на которые опирается рубрика бенчмарка:

1. Процедурная самоосознанность (отличение «как» от «что»).
2. Обоснование декомпозиции и приоритизации этапов.
3. Анализ отвергнутых процедурных альтернатив.
4. Воспроизводимость и переиспользуемый мета-протокол.

## Лицензия

Бенчмарк предназначен для исследовательских целей в рамках публикации по технике PMR. Использование при цитировании работы Душкина Р. В.
