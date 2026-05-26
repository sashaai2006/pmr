# tools/

Вспомогательные утилиты **вне** пакета MetaBotik.

## score_benchmark.py

Ручной (или гибридный) подсчёт по **5 осям рубрики 0–2** и покрытию claims из `gold.jsonl`. Не вызывает LLM API.

По умолчанию читает:

- `MetaBotik/suites/pmr_bench/benchmark.jsonl`
- `MetaBotik/suites/pmr_bench/gold.jsonl`
- `MetaBotik/suites/pmr_bench/rubric.json`

Для экспериментов статьи с автоматическим судьёй используйте `metabotik quality-judge` (см. корневой README и MetaBotik/README).
