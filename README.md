# PMR — Procedural Meta-Reflection Benchmark

Открытый стенд **PMR-Bench** (10 прикладных задач) и конвейер **MetaBotik** для парного сравнения промпта с процедурной мета-рефлексией и структурированного baseline. Техника описана в монографии Р. В. Душкина «Метакогнитивная промпт-инженерия» (разд. 4.3).

## Структура репозитория

```
pmr/
├── README.md                 ← вы здесь
├── MetaBotik/                ← основной код: metabotik CLI, прогоны, LLM-судья
│   └── suites/pmr_bench/     ← единственный источник задач и эталонов (JSONL)
├── results/                  ← агрегаты экспериментов (qwen, deepseek, yandexgpt)
├── docs/
│   └── paper/                ← LaTeX статьи + figures/
├── scripts/                  ← вспомогательные скрипты (графики для статьи)
└── tools/
    └── score_benchmark.py    ← ручная 5-осевая рубрика (без API), опционально
```

| Путь | Назначение |
|------|------------|
| `MetaBotik/suites/pmr_bench/benchmark.jsonl` | Постановки задач — **только агенту** |
| `MetaBotik/suites/pmr_bench/gold.jsonl` | Эталонные скелеты + claims — **только судье** |
| `MetaBotik/suites/pmr_bench/gold_v2.jsonl` | Гибкая рубрика (инварианты, fatal omissions) для LLM-судьи |
| `MetaBotik/suites/pmr_bench/rubric.json` | Общая 5-осевая шкала 0–2 (для `tools/score_benchmark.py`) |
| `results/<model>/` | `pmr_quality_by_task.jsonl`, `paired_pmr_vs_baseline.json`, `report.md` |

**Важно:** не подавайте `gold.jsonl` / `gold_v2.jsonl` испытуемой модели — это обесценивает замер.

## Быстрый старт (основной путь — MetaBotik)

```bash
cd MetaBotik
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # YANDEX_API_KEY, YANDEX_FOLDER_ID

# Проверка, что suite загружается
metabotik ingest --suite pmr-bench

# Полный цикл: PMR + baseline → eval → quality judge → compare → paired stats
metabotik pipeline --suite pmr-bench --modes pmr,baseline
```

Подробности CLI, режимы промптов и метрики **ACC / CMP / LPQ / PV / I** — в [MetaBotik/README.md](MetaBotik/README.md).

## Результаты статьи

Сводные прогоны лежат в `results/`:

- `results/qwen/`, `results/deepseek/`, `results/yandexgpt/`
- В каждой папке: `pmr_quality_by_task.jsonl`, `baseline_quality_by_task.jsonl`, `paired_pmr_vs_baseline.json`, `report.md`

Текст и таблицы — в [docs/paper/](docs/paper/) (`article.tex`, `процедурная_мета_рефлексия.tex`).

Сборка PDF:

```bash
cd docs/paper && xelatex процедурная_мета_рефлексия.tex
```

График для статьи:

```bash
python3 scripts/plot_pmr_article_figures.py
# → docs/paper/figures/pmr_I_LPQ_boxplots.png
```

## Альтернатива: ручная рубрика (без LLM API)

Если вы сами (или эксперт) выставляете баллы 0–2 по пяти осям и отмечаете claims:

```bash
python3 tools/score_benchmark.py --init-template answers_pmr.jsonl
# заполнить rubric_scores и claims_hit
python3 tools/score_benchmark.py \
  --answers answers_pmr.jsonl \
  --baseline answers_baseline.jsonl \
  --out report.json --report-md report.md
```

Пути к `benchmark.jsonl` и `gold.jsonl` по умолчанию указывают на `MetaBotik/suites/pmr_bench/`.

Проверка скрипта:

```bash
python3 tools/score_benchmark.py --self-test
```

## Состав стенда (10 задач)

| ID | Домен | Уровень |
|----|--------|---------|
| PMR-001 … 003 | Engineering / Management / … | см. `benchmark.jsonl` |
| … | Education, Therapy | 5 Intermediate + 5 Advanced |

Полная таблица и схемы полей — в [MetaBotik/README.md](MetaBotik/README.md) и [docs/README.md](docs/README.md).

## Источник техники

Душкин Р. В. «Метакогнитивная промпт-инженерия», разд. **4.3 «Процедурная мета-рефлексия»**.

## Лицензия

Исследовательское использование в рамках публикации по PMR; при цитировании — работа Душкина Р. В.
