"""Evaluation modules for PMR-Bench answers.

- `quality_judge`: LLM-backed semantic quality scoring.
- `element_coverage`: legacy helpers / claim categories; not used in default `eval`.
- `rubric_scorer`: legacy 5-axis 0-2 rubric scoring (manual CSV).
- `paired_stats`: paired t-test + Cohen's d + bootstrap 95% CI.
- `compare`: generic deltas between two summary JSON files.
"""
