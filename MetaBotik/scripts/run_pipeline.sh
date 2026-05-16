#!/usr/bin/env bash
# Полный прогон PMR-Bench: pipeline (run → eval → quality-judge → compare → paired-stats).
#
# Запуск из любого каталога:
#   bash /path/to/MetaBotik/scripts/run_pipeline.sh
#
# Модель и ключи — из MetaBotik/.env (или переопредели на один запуск):
#   YANDEX_MODEL=deepseek-v32/latest bash .../run_pipeline.sh
#
# Сохранить копию артефактов в ../../results/<имя> (от корня репозитория pmr):
#   RESULT_LABEL=deepseek bash .../run_pipeline.sh

set -euo pipefail

MB="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ROOT="$(cd "$MB/.." && pwd)"
MB_PY="$MB/.venv/bin/metabotik"

if [[ ! -x "$MB_PY" ]]; then
  echo "Нет $MB_PY — сначала: cd \"$MB\" && python3.12 -m venv .venv && .venv/bin/pip install -e ." >&2
  exit 1
fi

cd "$MB"
echo "=== pipeline (cwd=$MB) ==="
"$MB_PY" pipeline --suite pmr-bench --modes pmr,baseline --repeat 1

LABEL="${RESULT_LABEL:-}"
if [[ -n "$LABEL" ]]; then
  OUT="$ROOT/results/$LABEL"
  echo "=== bundle -> $OUT ==="
  rm -rf "$OUT"
  mkdir -p "$OUT"
  cp "$MB/results/pmr-bench/pmr/latest/summary.json" "$OUT/pmr_summary.json"
  cp "$MB/results/pmr-bench/baseline/latest/summary.json" "$OUT/baseline_summary.json"
  cp "$MB/results/pmr-bench/pmr/latest/quality_judge_summary.json" "$OUT/pmr_quality_summary.json"
  cp "$MB/results/pmr-bench/baseline/latest/quality_judge_summary.json" "$OUT/baseline_quality_summary.json"
  cp "$MB/results/pmr-bench/pmr/latest/quality_judge_by_task.jsonl" "$OUT/pmr_quality_by_task.jsonl"
  cp "$MB/results/pmr-bench/baseline/latest/quality_judge_by_task.jsonl" "$OUT/baseline_quality_by_task.jsonl"
  cp "$MB/results/pmr-bench/pmr/latest/by_task.jsonl" "$OUT/pmr_by_task.jsonl"
  cp "$MB/results/pmr-bench/baseline/latest/by_task.jsonl" "$OUT/baseline_by_task.jsonl"
  cp "$MB/results/pmr-bench/_comparison/compare_pmr_vs_baseline.json" "$OUT/compare_pmr_vs_baseline.json"
  cp "$MB/results/pmr-bench/_comparison/paired_pmr_vs_baseline.json" "$OUT/paired_pmr_vs_baseline.json" 2>/dev/null || true
  echo "=== done bundle $OUT ==="
fi

echo "=== finished ==="
