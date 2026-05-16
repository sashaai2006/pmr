# MetaBotik

**Procedural Meta-Reflection (PMR / MKPI 4.3) benchmark and agent pipeline.**

MetaBotik measures whether a language model not only solves a procedural task,
but also makes its problem-solving method conscious, justified and reproducible
— the core claim of the *MKPI 4.3 — Procedural Meta-Reflection* technique.

The default suite is **PMR-Bench**: 10 hand-crafted tasks (5 Intermediate + 5
Advanced) across four domains — Engineering, Education, Management, Therapy.
Every task is paired with a gold "skeleton + claims" reference so that the
evaluator can score procedural transparency separately from answer correctness.

---

## Layout

```
MetaBotik/
├── suites/
│   └── pmr_bench/
│       ├── benchmark.jsonl     # 10 tasks (agent-visible)
│       ├── gold.jsonl          # reference answers + expected claims
│       ├── rubric.json         # shared 5-axis (0-2) rubric, total_max=10
│       └── tools/build_gold.py # how the gold file was produced
├── src/
│   ├── domain/                 # pure types (NormalizedTask, AgentResult, GoldEntry, …)
│   ├── prompting/              # PromptStrategy registry (pmr / baseline / minimal / two-stage)
│   ├── evaluation/             # quality_judge, rubric_scorer, paired_stats, compare
│   ├── application/            # RunUseCase, EvalUseCase, JudgeUseCase, PipelineUseCase
│   ├── infrastructure/         # RunDirManager (results/<suite>/<mode>/<run_id>/), file repo
│   ├── cli/                    # Typer commands (run, pipeline, eval, compare, paired-stats, quality-judge, status)
│   ├── llm/                    # Yandex AI Studio client + settings
│   ├── parsing/                # JSON parser + schema-repair loop
│   ├── planning/               # procedure-family hints per domain
│   ├── reflection/             # post-LLM evaluator (quality gates)
│   └── formatting/             # JSON/Markdown serialisation of AgentResult
├── prompts/
│   ├── system/core_system_prompt.md   # the PMR system prompt (research IP)
│   ├── baseline_prompt.txt            # one-shot JSON baseline
│   ├── baseline_minimal.txt           # minimal free-text-in-JSON baseline
│   ├── baseline_twostage_solve.txt    # baseline stage 1 (free-form text)
│   ├── baseline_twostage_packager.md  # baseline stage 2 (text → JSON)
│   └── validators/schema_repair.txt   # repair prompt used on validation failure
├── docs/
│   ├── papers/                 # source PDFs (gitignored)
│   └── research/               # historical experiment notes (Qwen3-235B, 3 runs)
└── tests/                      # 52 unit/smoke tests
```

Every run writes to `results/<suite>/<mode>/<run_id>/` and updates the
`results/<suite>/<mode>/latest` symlink to point at the freshest run.

---

## Install

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env  # fill YANDEX_API_KEY, YANDEX_FOLDER_ID, optional model overrides
```

After installation the `metabotik` console script is available globally inside the venv.

### Troubleshooting

- **`zsh: command not found: metabotik`** — activate the venv first: `source .venv/bin/activate`, or call `python -m src.cli.app` from the repo root with `PYTHONPATH=.` (not recommended for daily use).
- **`ModuleNotFoundError: No module named 'src.main'`** — the console script was generated from an **old editable install** that pointed at another checkout (for example `~/MetaBotik` instead of this repo). Fix: remove the broken environment and reinstall from **this** directory only:

```bash
cd /path/to/MetaBotik   # the repo that contains suites/ and src/cli/
rm -rf .venv
python3.12 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Then verify: `head -6 .venv/bin/metabotik` must show `from src.cli.app import main` (not `src.main`).

---

## Commands

```bash
# 1. Generate answers from the LLM
metabotik run --suite pmr-bench --mode pmr      # produces results/pmr-bench/pmr/<run_id>/
metabotik run --suite pmr-bench --mode baseline
metabotik run --suite pmr-bench --mode baseline-minimal
metabotik run --suite pmr-bench --mode baseline-two-stage

# 2. Refresh run summary + by_task.jsonl (optional rubric_scores.csv if present)
metabotik eval --suite pmr-bench --mode pmr --run-id latest

# 3. Score semantic answer quality with an LLM judge
metabotik quality-judge --suite pmr-bench --mode pmr --run-id latest

# 4. Compare two runs (pipeline uses quality_judge_summary.json when present)
metabotik compare \
  --candidate results/pmr-bench/pmr/latest/quality_judge_summary.json \
  --baseline  results/pmr-bench/baseline/latest/quality_judge_summary.json \
  --output    results/pmr-bench/_comparison/compare.json

# 5. Paired statistical test (Cohen's d + bootstrap 95% CI)
# Prefer `quality_judge_by_task.jsonl` when comparing semantic axes; `by_task.jsonl` works for flat numeric rows.
metabotik paired-stats \
  --candidate results/pmr-bench/pmr/latest/quality_judge_by_task.jsonl \
  --baseline  results/pmr-bench/baseline/latest/quality_judge_by_task.jsonl

# Full cycle (run × modes × repeats → eval → LLM quality judge → compare → paired)
metabotik pipeline --suite pmr-bench --modes pmr,baseline --repeat 3
# Same without quality judge (saves tokens)
metabotik pipeline --suite pmr-bench --modes pmr,baseline --skip-quality-judge

# Inspect known suites and latest runs
metabotik status
```

All commands accept `--log-file <path>` and most accept `--dry-run` so you can
verify the plan without spending tokens.

---

## Prompt Conditions

The experiment uses one PMR condition and three non-PMR baselines:

| Mode | Prompt strength | Purpose |
|---|---|---|
| `pmr` | Full MKPI 4.3 protocol, Russian PMR-Bench-oriented prompt, `AgentResult` schema | Upper bound for procedural transparency: explicit procedure choice, rejected alternatives, critical points, adaptation notes, reflection. |
| `baseline-minimal` | Minimal instruction, `{task_id, answer}` JSON only | No-structure floor: tests how much PMR-Bench gold signal appears without prompt scaffolding. |
| `baseline` | Medium-strength domain-expert prompt with neutral JSON (`summary`, `plan`, `key_decisions`, `risks`, `rationale`) | Main fair baseline: competent expert answer without meta-reflection scaffolding. |
| `baseline-two-stage` | Medium-strength free-text solve, then neutral JSON packaging | Controls for whether JSON formatting itself explains the metric delta. |

Baseline prompts intentionally avoid CRM/Zarn vocabulary and do not require
procedure-family classification, rejected alternatives, critical-point tracking,
or post-hoc procedural reflection.

---

## Metrics

`metabotik eval` writes `summary.json` + `by_task.jsonl` (task bookkeeping and,
if `rubric_scores.csv` is present, optional manual 5-axis rubric totals).

`metabotik quality-judge` writes the main semantic quality evaluation:

- `completeness` / Полнота, 0-10.
- `accuracy` / Точность, 0-10.
- `latent_pattern_quality` / Quality of Latent Patterns, 0-10.
- `practical_value` / Практическая ценность, 0-10.
- `ai_score`: computed in code as
  `0.25*completeness + 0.30*accuracy + 0.20*latent_pattern_quality + 0.25*practical_value`.

Quality judge artifacts live next to the run:
`quality_judge_by_task.jsonl` and `quality_judge_summary.json`.
`eval` artifacts remain `by_task.jsonl` and `summary.json`.
The pipeline compares `quality_judge_summary.json` when present and runs paired
stats on `quality_judge_by_task.jsonl` (axis scores flattened from nested JSON)
via `src/evaluation/paired_stats.py`.

---

## Adding a new prompt strategy

1. Add an enum value to `PromptMode` in [`src/domain/enums.py`](src/domain/enums.py).
2. Create a class in [`src/prompting/strategies.py`](src/prompting/strategies.py)
   with `name: ClassVar[PromptMode]` and a `run(task, llm, ctx) -> RunOutput`
   method.
3. Register it in the `STRATEGIES` mapping at the bottom of the same file.

The CLI picks up the new mode automatically — no other change needed.

---

## Adding a new suite

1. Create `suites/<name>/{benchmark.jsonl,gold.jsonl,rubric.json}` and a
   `suite.py` exposing a class with `name`, `description`, `load_tasks()`,
   `load_gold()`, `load_rubric()`, `supported_metrics()`.
2. Register it in [`suites/__init__.py`](suites/__init__.py).

`SuiteProtocol` is defined in [`suites/protocol.py`](suites/protocol.py).

---

## Status of the original Qwen3 experiment

Historical notes from the predecessor pipeline (Zarn workflow automation, 3
runs on Qwen3-235B-FP8) live in
[`docs/research/EXPERIMENT_RESULTS.md`](docs/research/EXPERIMENT_RESULTS.md).

The new PMR-Bench is broader (4 domains instead of 1, 5 Intermediate + 5
Advanced instead of 10 Expert) and uses skeleton+claims gold instead of Zarn's
artifact-coverage rubric, so absolute numbers are not directly comparable
across the two suites. Paired statistics (`paired_stats`) remain available for
any flat per-task JSONL (including quality-judge outputs).
