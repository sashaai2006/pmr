# Essential Brief for Article-Writing Agent

This brief contains the minimum complete context needed to write a paper/article about the MetaBotik experiment on **Procedural Meta-Reflection (PMR)**. Use only the facts below unless you inspect the referenced project files directly.

---

## 1. Project Identity

**Project name:** MetaBotik  
**Core method:** Procedural Meta-Reflection (PMR), as formalized in Dushkin's *Metacognitive Prompt Engineering* (Russian: *Метакогнитивная промпт-инженерия*).  
**Goal:** Build and evaluate a Python LLM-agent pipeline that solves workflow automation tasks while explicitly exposing the procedure used to solve them.

The PMR agent is not just expected to output a correct workflow answer. It must also:

1. classify the procedure type;
2. justify why that procedure fits the task;
3. solve step by step;
4. explain procedural logic at each step;
5. identify critical points and adaptation conditions;
6. conclude with procedural reflection.

The important conceptual distinction:

- **Outcome quality:** Did the answer solve the task correctly?
- **Procedural quality:** Did the answer make the reasoning procedure explicit, reproducible, and auditable?

The paper should focus on the second dimension as the main contribution.

---

## 2. Repository Context

Relevant paths:

```text
prompts/system/core_system_prompt.md          # PMR prompt, treated as fixed/ideal
prompts/baseline_promt.txt                    # structured baseline prompt
datasets/processed/dataset.jsonl              # evaluated task set
datasets/processed/zarn_gold.jsonl            # gold labels for outcome metrics
src/evaluation/zarn_metrics.py                # outcome metrics
src/evaluation/quality_judge.py               # PMR-Bench LLM semantic quality judge
src/evaluation/paired_stats.py                # paired t-test, Cohen's d, bootstrap CI
scripts/run_pipeline_repeated_aggregate.py    # repeated experiment runner
results_pipeline_mc/                          # final 3-run results
results_comparison/EXPERIMENT_RESULTS.md      # detailed experiment report
```

The PMR prompt **must not be described as tuned during the experiment**. It was fixed and treated as the main method under evaluation.

---

## 3. Experimental Design

The experiment compares two prompt conditions on the same dataset.

| Condition | Description |
|-----------|-------------|
| **PMR** | Full Procedural Meta-Reflection protocol using `prompts/system/core_system_prompt.md`. |
| **Structured baseline** | Strong baseline using task + JSON schema + chain-of-thought style instructions in `prompts/baseline_promt.txt`. It is not a deliberately weak baseline. |

Experiment settings:

| Parameter | Value |
|-----------|-------|
| Dataset size | 10 tasks |
| Task type | Zarn workflow automation, expert-level tasks |
| Number of repeated runs | 3 |
| Model | `qwen3-235b-a22b-fp8/latest` through Yandex AI Studio |
| Temperature | 0.2 |
| Max tokens | 15000 |
| Main command pattern | `python -m src.main pipeline --mode both --force` |
| Aggregation | mean ± stdev across 3 runs |

Important procedural note:

- `run_01` was the original valid run.
- `run_02` and `run_03` were rerun fully through the LLM after a procedural-metric artifact issue was discovered.
- Final `results_pipeline_mc/run_01`, `run_02`, and `run_03` all have `task_count = 10`.
- Do not mention or use the intermediate bugged procedural aggregates except as internal history.

---

## 4. Metric Families

### 4.1. Outcome Metrics: Zarn

Implemented in `src/evaluation/zarn_metrics.py`.

These measure whether the workflow answer is correct relative to gold labels.

Key metrics:

- `overall_score`: weighted aggregate outcome score.
- `schema_validity`: valid required output structure.
- `required_artifact_coverage`: whether required artifacts are produced.
- `blocker_visibility`: whether blockers/uncertainties are surfaced.
- `policy_compliance`: whether constraints/policies are respected.
- `workspace_surface_recall`: whether relevant surfaces are mentioned.
- `workflow_operation_f1`: quality of operation selection.
- `handoff_completeness`: quality of handoff context.
- `calendar_uncertainty_compliance`: handling of uncertain scheduling.

### 4.2. PMR-Bench semantic quality (current)

For **PMR-Bench**, MetaBotik uses `src/evaluation/quality_judge.py`: LLM-scored axes
`completeness`, `accuracy`, `latent_pattern_quality`, `practical_value`, plus a
code-computed `ai_score` (see module for weights). The historical Zarn-era
deterministic legacy form-density stack (removed from codebase)
from the codebase.

---

## 5. Final Results

All final numbers below come from `results_pipeline_mc/aggregate_*.json` after replacing run_02 and run_03 with fresh reruns.

### 5.1. Outcome Results

Mean across 3 runs:

| Metric | PMR | Baseline | Difference |
|--------|-----|----------|------------|
| `overall_score` | **0.846 ± 0.029** | **0.787 ± 0.017** | **+0.060 points**, about **+7.7% relative** |
| `blocker_visibility` | **0.900 ± 0.033** | **0.578 ± 0.069** | **+32.2 percentage points** |
| `required_artifact_coverage` | **0.867 ± 0.031** | **0.800 ± 0.000** | **+6.7 percentage points** |
| `handoff_completeness` | **1.000 ± 0.000** | **0.900 ± 0.020** | **+10.0 percentage points** |

Per-run `overall_score`:

| Run | PMR | Baseline | Relative delta |
|-----|-----|----------|----------------|
| run_01 | 0.869 | 0.769 | +13.0% |
| run_02 | 0.813 | 0.802 | +1.5% |
| run_03 | 0.857 | 0.789 | +8.6% |
| **Mean** | **0.846** | **0.787** | **+7.7%** |

Important nuance:

- PMR wins on average in all three runs.
- Overall-score significance is not stable across all runs.
- The outcome claim should be phrased as a moderate average improvement, not as a universally statistically decisive improvement.
- Stronger outcome effects appear in specific submetrics such as `blocker_visibility` and `handoff_completeness`.

### 5.2. Historical procedural rigor (Zarn, archived)

The legacy Zarn table of form-density composite means (PMR **0.886 ± 0.012** vs baseline **0.009 ± 0.005**)
refers to the **legacy Zarn pipeline** and the removed deterministic scorer. Do not
present those numbers as current PMR-Bench methodology; cite them only as historical
context or reproduce them from git history if needed.

---

## 6. Main Scientific Claim

Recommended framing:

> PMR provides a moderate improvement in outcome quality while producing a very large improvement in procedural transparency.

More precise:

> On 10 expert workflow automation tasks across 3 runs, PMR improved the mean Zarn outcome score from 0.787 to 0.846 (+7.7% relative). Separately, the legacy deterministic procedural transparency stack (now removed) reported a very large PMR vs baseline gap; for PMR-Bench, use quality-judge outputs instead.

The paper should not claim:

- “PMR is 87% accurate and baseline is 76% accurate.”
- “PMR is universally statistically superior on overall_score.”
- “Baseline is dumb.”
- “Procedural rigor proves PMR is objectively better at all reasoning.”

The paper can claim:

- PMR is better on average in outcome score.
- PMR is much better at exposing procedure.
- PMR improves blocker visibility and handoff completeness.
- Baseline remains a credible comparison because it has JSON schema and CoT-style instructions.

---

## 7. Suggested Article Structure

### Title Ideas

1. **Procedural Meta-Reflection Improves Transparency in LLM Workflow Agents**
2. **Beyond Correct Answers: Measuring Procedural Rigor in LLM Agents**
3. **Procedural Meta-Reflection for Explainable Workflow Automation**

### Abstract Skeleton

Mention:

- LLM agents often produce useful outputs without exposing procedural reasoning.
- PMR makes procedure selection, step logic, critical points, and reflection explicit.
- Experiment: 10 expert workflow automation tasks, 3 repeated runs, PMR vs structured baseline.
- Outcome: PMR improves `overall_score` from 0.787 to 0.846 (+7.7%).
- Semantic (PMR-Bench): compare `ai_score` / axis means from `quality_judge_summary.json`.
- Conclusion: PMR is most valuable as an explainability/reproducibility layer, not only as a raw outcome optimizer.

### Sections

1. Introduction: black-box procedural knowledge problem.
2. Related Work: prompt engineering, chain-of-thought, agent evaluation, explainability.
3. Method: PMR protocol and system pipeline.
4. Evaluation: dataset, baseline, model, metrics.
5. Results: outcome and procedural results.
6. Discussion: why procedural rigor matters, limitations.
7. Conclusion: PMR as a reproducible procedural layer.

---

## 8. Ready-to-Use Results Paragraph

Use this or adapt it:

> We evaluated Procedural Meta-Reflection (PMR) against a structured baseline on 10 expert workflow automation tasks over three independent runs. The baseline was not minimal: it used a JSON output schema and chain-of-thought style instructions. PMR achieved a higher mean Zarn outcome score than the baseline (0.846 ± 0.029 vs. 0.787 ± 0.017), corresponding to a +7.7% relative improvement. The strongest outcome-level improvement appeared in blocker visibility (0.900 vs. 0.578) and handoff completeness (1.000 vs. 0.900). The main effect, however, was procedural: PMR achieved a procedural rigor score of 0.886 ± 0.012, while the structured baseline scored 0.009 ± 0.005. PMR exposed procedure classification, procedure justification, rejected alternatives, critical points, adaptation notes, and actionable reflection consistently across tasks. This supports the interpretation of PMR as a method for making LLM agent outputs more reproducible and auditable, rather than merely optimizing final-answer accuracy.

---

## 9. Method Description Paragraph

Use this or adapt it:

> Procedural Meta-Reflection structures the model response around explicit procedural self-description. For each task, the agent first classifies the procedural family (e.g., linear, branching, cyclic, analytical, diagnostic, creative, or mixed), selects a minimal sufficient procedure, justifies the selection against alternatives, executes the task in ordered steps, identifies critical points where the procedure may fail or require adaptation, and ends with procedural reflection. The resulting JSON contains `procedural_analysis`, `solution_steps`, and `reflection` blocks. This differs from a standard structured baseline, which may produce a valid plan and artifacts but does not necessarily document the procedure by which those artifacts were derived.

---

## 10. Procedural Rigor Explanation Paragraph

Use this or adapt it:

> We introduce procedural rigor as a deterministic measure of how explicitly an answer exposes its procedural structure. The metric is computed directly from the saved JSON output and does not use gold labels. It aggregates six components: procedure classification, procedure justification, alternative procedures, critical-point density, adaptation specificity, and reflection actionability. The composite weights critical points and adaptation notes slightly higher (20% each) because they capture whether the method can be adjusted under uncertainty. A separate binary indicator, `procedural_trace_present`, records whether the answer contains the full PMR trace (`procedural_analysis`, `solution_steps`, and `reflection`). This metric is not intended to replace outcome evaluation; rather, it captures a separate dimension: procedural transparency and reproducibility.

---

## 11. Limitations to State Honestly

1. Dataset is small: 10 tasks, 3 runs.
2. Only one model was used.
3. PMR has an advantage on procedural metrics because the prompt explicitly requires procedural fields. This is acceptable because the method’s purpose is procedural explicitness, but it must be stated.
4. Overall outcome improvement is moderate and not statistically significant in every run.
5. Some baseline outcome submetrics are competitive or better, especially operation F1 / workspace recall / calendar uncertainty.
6. The experiment demonstrates a strong transparency effect and moderate outcome effect, not universal dominance.

---

## 12. Do Not Do This

Do not invent or round results into misleading values.

Correct:

- PMR outcome: **0.846** or **84.6%**
- Baseline outcome: **0.787** or **78.7%**
- PMR procedural rigor: **0.886**
- Baseline procedural rigor: **0.009**

Do not write:

- PMR = 87%, baseline = 76% as final outcome numbers.
- “PMR is statistically significant on overall_score in all runs.”
- “Baseline cannot solve the task.”

---

## 13. Best One-Sentence Thesis

**Procedural Meta-Reflection modestly improves workflow-task outcomes while dramatically increasing the procedural transparency, reproducibility, and auditability of LLM-agent responses.**

