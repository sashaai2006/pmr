"""score_benchmark.py — Scoring engine for the PMR benchmark.

Computes per-case, per-model and A/B (PMR vs baseline) metrics from a judge's
filled-in answers files against the gold reference.

Inputs (JSONL files):
  - benchmark file (agent-visible): id, domain, difficulty, task_description
  - gold file (judge-only): expected_meta_elements, evaluation_rubric, metadata
  - answers file(s): id, rubric_scores (5 axes, each 0-2), claims_hit
                    (binary lists matching gold expected_meta_elements lengths)

Outputs:
  - report.json: machine-readable, full structured data
  - report.md:   human-readable summary with tables

Usage:
  python3 score_benchmark.py \\
      --benchmark pmr_benchmark.jsonl \\
      --gold pmr_gold.jsonl \\
      --answers answers_pmr.jsonl \\
      [--baseline answers_baseline.jsonl] \\
      [--judge-mode manual|llm|hybrid] \\
      [--out report.json --report-md report.md] \\
      [--bootstrap-iters 1000]

Utility modes:
  --init-template <path>  emit an empty answers template from the gold file
  --self-test             run end-to-end on synthetic data (no I/O of real answers)

Dependencies: stdlib only. scipy is optional — used for an exact Wilcoxon
signed-rank p-value; if absent, falls back to a normal approximation.
"""
from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from pathlib import Path
from typing import Any


RUBRIC_AXES: tuple[str, ...] = (
    "procedural_self_awareness",
    "decomposition_justification",
    "rejected_alternatives",
    "critical_points_and_adaptation",
    "reproducibility_meta_protocol",
)

CLAIM_CATEGORIES: tuple[str, ...] = (
    "decomposition",
    "rejected_alternatives",
    "critical_points",
    "meta_protocol",
)

PASS_THRESHOLD: int = 7
AXIS_MAX: int = 2
RUBRIC_TOTAL_MAX: int = AXIS_MAX * len(RUBRIC_AXES)  # 10


# ---------------------------------------------------------------------------
# IO + validation
# ---------------------------------------------------------------------------


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_benchmark(path: Path) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for entry in _load_jsonl(path):
        out[entry["id"]] = {
            "domain": entry["domain"],
            "difficulty": entry["difficulty"],
            "task_description": entry["task_description"],
        }
    return out


def load_gold(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for entry in _load_jsonl(path):
        out[entry["id"]] = {
            "expected_meta_elements": entry["expected_meta_elements"],
            "evaluation_rubric": entry["evaluation_rubric"],
            "metadata": entry.get("metadata", {}),
        }
    return out


def load_answers(path: Path, gold: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for entry in _load_jsonl(path):
        cid = entry["id"]
        if cid not in gold:
            raise ValueError(f"answers file: id {cid} not in gold")

        rubric_scores = entry["rubric_scores"]
        missing_axes = [a for a in RUBRIC_AXES if a not in rubric_scores]
        if missing_axes:
            raise ValueError(f"answers[{cid}].rubric_scores missing axes: {missing_axes}")
        for axis, val in rubric_scores.items():
            if axis not in RUBRIC_AXES:
                raise ValueError(f"answers[{cid}].rubric_scores unknown axis: {axis}")
            if not (0 <= int(val) <= AXIS_MAX):
                raise ValueError(f"answers[{cid}].rubric_scores[{axis}]={val} out of [0,{AXIS_MAX}]")

        claims_hit = entry["claims_hit"]
        gold_claims = gold[cid]["expected_meta_elements"]
        for cat in CLAIM_CATEGORIES:
            if cat not in claims_hit:
                raise ValueError(f"answers[{cid}].claims_hit missing category: {cat}")
            actual_len = len(claims_hit[cat])
            expected_len = len(gold_claims[cat])
            if actual_len != expected_len:
                raise ValueError(
                    f"answers[{cid}].claims_hit[{cat}] length {actual_len} ≠ gold {expected_len}"
                )
            for v in claims_hit[cat]:
                if int(v) not in (0, 1):
                    raise ValueError(f"answers[{cid}].claims_hit[{cat}] non-binary: {v}")

        out[cid] = {
            "rubric_scores": {a: int(rubric_scores[a]) for a in RUBRIC_AXES},
            "claims_hit": {c: [int(v) for v in claims_hit[c]] for c in CLAIM_CATEGORIES},
            "agent_response": entry.get("agent_response", ""),
        }

    missing = set(gold.keys()) - set(out.keys())
    if missing:
        raise ValueError(f"answers file missing ids present in gold: {sorted(missing)}")
    return out


# ---------------------------------------------------------------------------
# Per-case + per-model metrics
# ---------------------------------------------------------------------------


def per_case_metrics(
    answers: dict[str, dict[str, Any]],
    gold: dict[str, dict[str, Any]],
    benchmark: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cid in sorted(answers.keys()):
        rubric_scores = answers[cid]["rubric_scores"]
        claims_hit = answers[cid]["claims_hit"]
        rubric_score = sum(rubric_scores.values())

        total_claims = 0
        total_hits = 0
        per_cat: dict[str, dict[str, float]] = {}
        for cat in CLAIM_CATEGORIES:
            hits = sum(claims_hit[cat])
            n = len(claims_hit[cat])
            per_cat[cat] = {"hits": hits, "total": n, "ratio": hits / n if n else 0.0}
            total_hits += hits
            total_claims += n

        rows.append({
            "id": cid,
            "domain": benchmark[cid]["domain"],
            "difficulty": benchmark[cid]["difficulty"],
            "rubric_scores": rubric_scores,
            "rubric_score": rubric_score,
            "rubric_max": RUBRIC_TOTAL_MAX,
            "pass": int(rubric_score >= PASS_THRESHOLD),
            "element_coverage": total_hits / total_claims if total_claims else 0.0,
            "claims_per_category": per_cat,
            "claims_total_hits": total_hits,
            "claims_total": total_claims,
        })
    return rows


def per_model_aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    scores = [r["rubric_score"] for r in rows]
    coverages = [r["element_coverage"] for r in rows]
    passes = [r["pass"] for r in rows]

    total_hits = sum(r["claims_total_hits"] for r in rows)
    total_claims = sum(r["claims_total"] for r in rows)

    agg: dict[str, Any] = {
        "n_cases": len(rows),
        "mean_score": statistics.mean(scores) if scores else 0.0,
        "std_score": statistics.stdev(scores) if len(scores) > 1 else 0.0,
        "median_score": statistics.median(scores) if scores else 0.0,
        "min_score": min(scores) if scores else 0,
        "max_score": max(scores) if scores else 0,
        "pass_rate": sum(passes) / len(passes) if passes else 0.0,
        "coverage_macro": statistics.mean(coverages) if coverages else 0.0,
        "coverage_micro": total_hits / total_claims if total_claims else 0.0,
        "per_axis_mean": {
            axis: statistics.mean(r["rubric_scores"][axis] for r in rows) if rows else 0.0
            for axis in RUBRIC_AXES
        },
        "by_difficulty": {},
        "by_domain": {},
    }

    for key in ("difficulty", "domain"):
        groups: dict[str, list[dict[str, Any]]] = {}
        for r in rows:
            groups.setdefault(r[key], []).append(r)
        bucket: dict[str, Any] = {}
        for group_name, group_rows in groups.items():
            group_scores = [r["rubric_score"] for r in group_rows]
            group_pass = [r["pass"] for r in group_rows]
            group_cov = [r["element_coverage"] for r in group_rows]
            bucket[group_name] = {
                "n": len(group_rows),
                "mean_score": statistics.mean(group_scores),
                "pass_rate": sum(group_pass) / len(group_pass),
                "coverage_macro": statistics.mean(group_cov),
            }
        target_key = "by_difficulty" if key == "difficulty" else "by_domain"
        agg[target_key] = bucket

    return agg


# ---------------------------------------------------------------------------
# A/B statistics
# ---------------------------------------------------------------------------


def _wilcoxon_signed_rank(differences: list[float]) -> tuple[float, str]:
    """Two-sided Wilcoxon signed-rank p-value.

    Uses scipy.stats.wilcoxon when available (exact for small n), else a normal
    approximation suitable for n >= 6 (Pratt zero-handling).
    """
    non_zero = [d for d in differences if d != 0]
    if not non_zero:
        return 1.0, "all_diffs_zero"

    try:
        from scipy.stats import wilcoxon  # type: ignore

        res = wilcoxon(non_zero, zero_method="wilcox", correction=False, alternative="two-sided")
        return float(res.pvalue), "scipy_exact_or_approx"
    except ImportError:
        pass

    abs_sorted = sorted(((abs(d), 1 if d > 0 else -1) for d in non_zero), key=lambda x: x[0])
    ranks: list[float] = [0.0] * len(abs_sorted)
    i = 0
    while i < len(abs_sorted):
        j = i
        while j + 1 < len(abs_sorted) and abs_sorted[j + 1][0] == abs_sorted[i][0]:
            j += 1
        avg_rank = (i + j) / 2 + 1
        for k in range(i, j + 1):
            ranks[k] = avg_rank
        i = j + 1

    w_pos = sum(rank for rank, (_, sign) in zip(ranks, abs_sorted) if sign > 0)
    w_neg = sum(rank for rank, (_, sign) in zip(ranks, abs_sorted) if sign < 0)
    w = min(w_pos, w_neg)
    n = len(non_zero)
    mean_w = n * (n + 1) / 4
    var_w = n * (n + 1) * (2 * n + 1) / 24
    if var_w == 0:
        return 1.0, "degenerate_variance"
    z = (w - mean_w) / math.sqrt(var_w)
    p = 2 * (1 - 0.5 * (1 + math.erf(abs(z) / math.sqrt(2))))
    return float(p), "normal_approximation"


def _bootstrap_ci_mean_diff(
    diffs: list[float],
    iters: int = 1000,
    alpha: float = 0.05,
    seed: int = 42,
) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(diffs)
    if n == 0:
        return 0.0, 0.0
    means: list[float] = []
    for _ in range(iters):
        resample = [diffs[rng.randint(0, n - 1)] for _ in range(n)]
        means.append(statistics.mean(resample))
    means.sort()
    lower_idx = int((alpha / 2) * iters)
    upper_idx = int((1 - alpha / 2) * iters) - 1
    return means[lower_idx], means[upper_idx]


def ab_statistics(
    pmr_rows: list[dict[str, Any]],
    baseline_rows: list[dict[str, Any]],
    bootstrap_iters: int = 1000,
) -> dict[str, Any]:
    pmr_map = {r["id"]: r for r in pmr_rows}
    base_map = {r["id"]: r for r in baseline_rows}
    common_ids = sorted(set(pmr_map.keys()) & set(base_map.keys()))
    if not common_ids:
        raise ValueError("A/B: no overlapping ids between PMR and baseline answers")

    pmr_scores = [pmr_map[c]["rubric_score"] for c in common_ids]
    base_scores = [base_map[c]["rubric_score"] for c in common_ids]
    diffs = [float(p - b) for p, b in zip(pmr_scores, base_scores)]

    delta_mean = statistics.mean(diffs)
    delta_std = statistics.stdev(diffs) if len(diffs) > 1 else 0.0
    cohens_d = delta_mean / delta_std if delta_std > 0 else 0.0
    p_value, p_method = _wilcoxon_signed_rank(diffs)
    win_rate = sum(1 for d in diffs if d >= 1) / len(diffs)
    ci_low, ci_high = _bootstrap_ci_mean_diff(diffs, iters=bootstrap_iters)

    return {
        "n_paired": len(common_ids),
        "delta_mean_score": delta_mean,
        "delta_std": delta_std,
        "cohens_d_paired": cohens_d,
        "wilcoxon_p_two_sided": p_value,
        "wilcoxon_method": p_method,
        "win_rate_pmr_geq_plus1": win_rate,
        "bootstrap_ci95_delta_mean": [ci_low, ci_high],
        "bootstrap_iters": bootstrap_iters,
        "per_case_diffs": [
            {"id": c, "pmr": pmr_map[c]["rubric_score"], "baseline": base_map[c]["rubric_score"],
             "diff": d}
            for c, d in zip(common_ids, diffs)
        ],
    }


# ---------------------------------------------------------------------------
# Report writers
# ---------------------------------------------------------------------------


def _fmt(x: float, p: int = 2) -> str:
    return f"{x:.{p}f}"


def render_markdown(
    rows: list[dict[str, Any]],
    aggregate: dict[str, Any],
    ab: dict[str, Any] | None,
    judge_mode: str,
) -> str:
    md: list[str] = []
    md.append("# PMR Benchmark — Scoring Report")
    md.append("")
    md.append(f"- Judge mode: `{judge_mode}`")
    md.append(f"- Cases scored: **{aggregate['n_cases']}**")
    md.append(f"- Rubric max per case: {RUBRIC_TOTAL_MAX} · pass threshold: ≥{PASS_THRESHOLD}")
    md.append("")

    md.append("## Per-model aggregate (PMR run)")
    md.append("")
    md.append("| Metric | Value |")
    md.append("|---|---|")
    md.append(f"| mean_score | {_fmt(aggregate['mean_score'])} / {RUBRIC_TOTAL_MAX} |")
    md.append(f"| std_score | {_fmt(aggregate['std_score'])} |")
    md.append(f"| median_score | {_fmt(aggregate['median_score'])} |")
    md.append(f"| min / max | {aggregate['min_score']} / {aggregate['max_score']} |")
    md.append(f"| pass_rate (≥{PASS_THRESHOLD}) | {_fmt(aggregate['pass_rate'] * 100, 1)}% |")
    md.append(f"| coverage_macro | {_fmt(aggregate['coverage_macro'] * 100, 1)}% |")
    md.append(f"| coverage_micro | {_fmt(aggregate['coverage_micro'] * 100, 1)}% |")
    md.append("")

    md.append("### Per-axis mean (0-2 scale)")
    md.append("")
    md.append("| Axis | Mean |")
    md.append("|---|---|")
    for axis in RUBRIC_AXES:
        md.append(f"| {axis} | {_fmt(aggregate['per_axis_mean'][axis])} |")
    md.append("")

    md.append("### Breakdown by difficulty")
    md.append("")
    md.append("| Difficulty | N | Mean score | Pass rate | Coverage macro |")
    md.append("|---|---|---|---|---|")
    for k, v in aggregate["by_difficulty"].items():
        md.append(
            f"| {k} | {v['n']} | {_fmt(v['mean_score'])} | "
            f"{_fmt(v['pass_rate'] * 100, 1)}% | {_fmt(v['coverage_macro'] * 100, 1)}% |"
        )
    md.append("")

    md.append("### Breakdown by domain")
    md.append("")
    md.append("| Domain | N | Mean score | Pass rate | Coverage macro |")
    md.append("|---|---|---|---|---|")
    for k, v in aggregate["by_domain"].items():
        md.append(
            f"| {k} | {v['n']} | {_fmt(v['mean_score'])} | "
            f"{_fmt(v['pass_rate'] * 100, 1)}% | {_fmt(v['coverage_macro'] * 100, 1)}% |"
        )
    md.append("")

    md.append("## Per-case scores")
    md.append("")
    md.append("| ID | Domain | Difficulty | Score | Pass | Coverage |")
    md.append("|---|---|---|---|---|---|")
    for r in rows:
        md.append(
            f"| {r['id']} | {r['domain']} | {r['difficulty']} | "
            f"{r['rubric_score']} / {r['rubric_max']} | "
            f"{'✓' if r['pass'] else '✗'} | "
            f"{_fmt(r['element_coverage'] * 100, 1)}% "
            f"({r['claims_total_hits']}/{r['claims_total']}) |"
        )
    md.append("")

    if ab is not None:
        md.append("## A/B: PMR vs baseline")
        md.append("")
        md.append("| Metric | Value |")
        md.append("|---|---|")
        md.append(f"| n_paired | {ab['n_paired']} |")
        md.append(f"| Δmean_score | {_fmt(ab['delta_mean_score'])} |")
        md.append(f"| Cohen's d (paired) | {_fmt(ab['cohens_d_paired'])} |")
        md.append(
            f"| Wilcoxon p (two-sided, {ab['wilcoxon_method']}) | "
            f"{_fmt(ab['wilcoxon_p_two_sided'], 4)} |"
        )
        md.append(f"| win_rate (Δ ≥ +1) | {_fmt(ab['win_rate_pmr_geq_plus1'] * 100, 1)}% |")
        ci = ab["bootstrap_ci95_delta_mean"]
        md.append(f"| 95% bootstrap CI for Δmean | [{_fmt(ci[0])}, {_fmt(ci[1])}] |")
        md.append("")
        md.append("### Per-case diffs")
        md.append("")
        md.append("| ID | PMR | Baseline | Diff |")
        md.append("|---|---|---|---|")
        for d in ab["per_case_diffs"]:
            md.append(f"| {d['id']} | {d['pmr']} | {d['baseline']} | {d['diff']:+.0f} |")
        md.append("")

    return "\n".join(md)


# ---------------------------------------------------------------------------
# Templates and self-test
# ---------------------------------------------------------------------------


def emit_template(gold_path: Path, out_path: Path) -> None:
    gold = load_gold(gold_path)
    with out_path.open("w", encoding="utf-8") as f:
        for cid in sorted(gold.keys()):
            entry = {
                "id": cid,
                "agent_response": "<полный ответ агента сюда>",
                "rubric_scores": {axis: 0 for axis in RUBRIC_AXES},
                "claims_hit": {
                    cat: [0] * len(gold[cid]["expected_meta_elements"][cat])
                    for cat in CLAIM_CATEGORIES
                },
            }
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"Emitted answers template at {out_path} ({len(gold)} rows).")


def run_self_test(workdir: Path) -> int:
    rng = random.Random(0)
    bench_path = workdir / "pmr_benchmark.jsonl"
    gold_path = workdir / "pmr_gold.jsonl"
    if not bench_path.exists() or not gold_path.exists():
        print(f"self-test requires {bench_path} and {gold_path}", file=sys.stderr)
        return 1
    gold = load_gold(gold_path)

    def synth(quality: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for cid, g in gold.items():
            if quality == "high":
                axes_scores = {a: rng.choice([1, 2, 2, 2]) for a in RUBRIC_AXES}
                claim_p = 0.8
            else:
                axes_scores = {a: rng.choice([0, 0, 1, 1]) for a in RUBRIC_AXES}
                claim_p = 0.25
            claims_hit = {
                cat: [1 if rng.random() < claim_p else 0
                      for _ in g["expected_meta_elements"][cat]]
                for cat in CLAIM_CATEGORIES
            }
            out.append({
                "id": cid,
                "agent_response": f"synthetic {quality} answer",
                "rubric_scores": axes_scores,
                "claims_hit": claims_hit,
            })
        return out

    pmr_answers = synth("high")
    base_answers = synth("low")
    pmr_path = workdir / "_selftest_pmr.jsonl"
    base_path = workdir / "_selftest_baseline.jsonl"
    for p, data in [(pmr_path, pmr_answers), (base_path, base_answers)]:
        with p.open("w", encoding="utf-8") as f:
            for e in data:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

    out_json = workdir / "_selftest_report.json"
    out_md = workdir / "_selftest_report.md"
    rc = main([
        "--benchmark", str(bench_path),
        "--gold", str(gold_path),
        "--answers", str(pmr_path),
        "--baseline", str(base_path),
        "--out", str(out_json),
        "--report-md", str(out_md),
        "--bootstrap-iters", "500",
    ])
    for p in (pmr_path, base_path):
        p.unlink(missing_ok=True)
    return rc


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Score the PMR benchmark.")
    parser.add_argument("--benchmark", type=Path, help="Path to pmr_benchmark.jsonl")
    parser.add_argument("--gold", type=Path, help="Path to pmr_gold.jsonl")
    parser.add_argument("--answers", type=Path, help="Path to answers JSONL (PMR run)")
    parser.add_argument("--baseline", type=Path, default=None,
                        help="Optional baseline answers JSONL (no-PMR run) for A/B")
    parser.add_argument("--judge-mode", choices=("manual", "llm", "hybrid"),
                        default="manual",
                        help="Informational tag for how rubric_scores were produced")
    parser.add_argument("--out", type=Path, default=Path("report.json"),
                        help="Output path for the machine-readable JSON report")
    parser.add_argument("--report-md", type=Path, default=Path("report.md"),
                        help="Output path for the human-readable Markdown report")
    parser.add_argument("--bootstrap-iters", type=int, default=1000,
                        help="Bootstrap iterations for A/B 95%% CI on Δmean")
    parser.add_argument("--init-template", type=Path, default=None,
                        help="Emit a blank answers template from --gold and exit")
    parser.add_argument("--self-test", action="store_true",
                        help="Run end-to-end on synthetic data using files in CWD")

    args = parser.parse_args(argv)

    if args.self_test:
        return run_self_test(Path.cwd())

    if args.init_template is not None:
        if args.gold is None:
            parser.error("--init-template requires --gold")
        emit_template(args.gold, args.init_template)
        return 0

    missing = [name for name in ("benchmark", "gold", "answers") if getattr(args, name) is None]
    if missing:
        parser.error(f"required arguments missing: {missing}")

    benchmark = load_benchmark(args.benchmark)
    gold = load_gold(args.gold)
    if set(benchmark) != set(gold):
        raise ValueError(
            f"benchmark/gold id mismatch: benchmark-only={set(benchmark) - set(gold)}, "
            f"gold-only={set(gold) - set(benchmark)}"
        )

    pmr_answers = load_answers(args.answers, gold)
    pmr_rows = per_case_metrics(pmr_answers, gold, benchmark)
    pmr_agg = per_model_aggregate(pmr_rows)

    report: dict[str, Any] = {
        "judge_mode": args.judge_mode,
        "rubric_axes": list(RUBRIC_AXES),
        "claim_categories": list(CLAIM_CATEGORIES),
        "pass_threshold": PASS_THRESHOLD,
        "rubric_total_max": RUBRIC_TOTAL_MAX,
        "pmr_run": {
            "answers_path": str(args.answers),
            "per_case": pmr_rows,
            "aggregate": pmr_agg,
        },
    }

    ab = None
    if args.baseline is not None:
        baseline_answers = load_answers(args.baseline, gold)
        baseline_rows = per_case_metrics(baseline_answers, gold, benchmark)
        baseline_agg = per_model_aggregate(baseline_rows)
        ab = ab_statistics(pmr_rows, baseline_rows, bootstrap_iters=args.bootstrap_iters)
        report["baseline_run"] = {
            "answers_path": str(args.baseline),
            "per_case": baseline_rows,
            "aggregate": baseline_agg,
        }
        report["ab"] = ab

    args.out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_text = render_markdown(pmr_rows, pmr_agg, ab, args.judge_mode)
    args.report_md.write_text(md_text, encoding="utf-8")

    print(f"Wrote {args.out} and {args.report_md}")
    print(f"  mean_score = {pmr_agg['mean_score']:.2f} / {RUBRIC_TOTAL_MAX}")
    print(f"  pass_rate  = {pmr_agg['pass_rate']*100:.1f}%")
    if ab is not None:
        print(f"  Δmean_score = {ab['delta_mean_score']:+.2f}")
        print(f"  Cohen's d   = {ab['cohens_d_paired']:.2f}")
        print(f"  Wilcoxon p  = {ab['wilcoxon_p_two_sided']:.4f} ({ab['wilcoxon_method']})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
