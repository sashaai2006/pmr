#!/usr/bin/env python3
"""Score PMR-Bench with a manual 5-axis rubric (0–2) and claim coverage.

Primary experiment pipeline lives in MetaBotik (`metabotik pipeline` + quality judge).
This tool is for human/LLM-assisted scoring against gold claims and rubric.json.
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

REPO_ROOT = Path(__file__).resolve().parents[1]
SUITE_DIR = REPO_ROOT / "MetaBotik" / "suites" / "pmr_bench"
DEFAULT_BENCHMARK = SUITE_DIR / "benchmark.jsonl"
DEFAULT_GOLD = SUITE_DIR / "gold.jsonl"
DEFAULT_RUBRIC = SUITE_DIR / "rubric.json"

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


def _task_id(entry: dict[str, Any]) -> str:
    return str(entry.get("id") or entry["task_id"])


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def load_shared_rubric(rubric_path: Path) -> dict[str, Any]:
    if not rubric_path.is_file():
        raise FileNotFoundError(f"rubric not found: {rubric_path}")
    return json.loads(rubric_path.read_text(encoding="utf-8"))


def load_benchmark(path: Path) -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for entry in _load_jsonl(path):
        tid = _task_id(entry)
        out[tid] = {
            "domain": entry["domain"],
            "difficulty": entry["difficulty"],
            "task_description": entry["task_description"],
        }
    return out


def load_gold(path: Path, *, rubric_path: Path | None = None) -> dict[str, dict[str, Any]]:
    rubric_path = rubric_path or path.parent / "rubric.json"
    shared_rubric = load_shared_rubric(rubric_path) if rubric_path.is_file() else None
    out: dict[str, dict[str, Any]] = {}
    for entry in _load_jsonl(path):
        tid = _task_id(entry)
        evaluation_rubric = entry.get("evaluation_rubric") or shared_rubric
        if evaluation_rubric is None:
            raise ValueError(
                f"gold entry {tid}: no evaluation_rubric and no rubric at {rubric_path}"
            )
        out[tid] = {
            "expected_meta_elements": entry["expected_meta_elements"],
            "evaluation_rubric": evaluation_rubric,
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


def _wilcoxon_signed_rank(differences: list[float]) -> tuple[float, str]:
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
            {
                "id": c,
                "pmr": pmr_map[c]["rubric_score"],
                "baseline": base_map[c]["rubric_score"],
                "diff": d,
            }
            for c, d in zip(common_ids, diffs)
        ],
    }


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


def emit_template(gold_path: Path, out_path: Path, *, rubric_path: Path | None = None) -> None:
    gold = load_gold(gold_path, rubric_path=rubric_path)
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


def run_self_test() -> int:
    rng = random.Random(0)
    if not DEFAULT_BENCHMARK.is_file() or not DEFAULT_GOLD.is_file():
        print(f"self-test requires suite files under {SUITE_DIR}", file=sys.stderr)
        return 1
    gold = load_gold(DEFAULT_GOLD, rubric_path=DEFAULT_RUBRIC)

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
                cat: [1 if rng.random() < claim_p else 0 for _ in g["expected_meta_elements"][cat]]
                for cat in CLAIM_CATEGORIES
            }
            out.append({
                "id": cid,
                "agent_response": f"synthetic {quality} answer",
                "rubric_scores": axes_scores,
                "claims_hit": claims_hit,
            })
        return out

    tmp = REPO_ROOT / "_selftest_tmp"
    tmp.mkdir(exist_ok=True)
    pmr_path = tmp / "pmr.jsonl"
    base_path = tmp / "baseline.jsonl"
    for p, data in [(pmr_path, synth("high")), (base_path, synth("low"))]:
        with p.open("w", encoding="utf-8") as f:
            for e in data:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")

    rc = main([
        "--answers", str(pmr_path),
        "--baseline", str(base_path),
        "--out", str(tmp / "report.json"),
        "--report-md", str(tmp / "report.md"),
        "--bootstrap-iters", "500",
    ])
    for p in (pmr_path, base_path, tmp / "report.json", tmp / "report.md"):
        p.unlink(missing_ok=True)
    try:
        tmp.rmdir()
    except OSError:
        pass
    return rc


def _resolve_paths(args: argparse.Namespace) -> None:
    if args.benchmark is None:
        args.benchmark = DEFAULT_BENCHMARK
    if args.gold is None:
        args.gold = DEFAULT_GOLD
    if args.rubric is None:
        args.rubric = DEFAULT_RUBRIC


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Score PMR-Bench with manual rubric + claim coverage (legacy path).",
    )
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=None,
        help=f"Tasks JSONL (default: {DEFAULT_BENCHMARK.relative_to(REPO_ROOT)})",
    )
    parser.add_argument(
        "--gold",
        type=Path,
        default=None,
        help=f"Gold JSONL (default: {DEFAULT_GOLD.relative_to(REPO_ROOT)})",
    )
    parser.add_argument("--rubric", type=Path, default=None, help="Shared rubric.json if omitted in gold")
    parser.add_argument("--answers", type=Path, help="Answers JSONL (PMR run)")
    parser.add_argument("--baseline", type=Path, default=None, help="Optional baseline answers for A/B")
    parser.add_argument(
        "--judge-mode",
        choices=("manual", "llm", "hybrid"),
        default="manual",
        help="Informational tag for how rubric_scores were produced",
    )
    parser.add_argument("--out", type=Path, default=Path("report.json"))
    parser.add_argument("--report-md", type=Path, default=Path("report.md"))
    parser.add_argument("--bootstrap-iters", type=int, default=1000)
    parser.add_argument("--init-template", type=Path, default=None, help="Emit blank answers template and exit")
    parser.add_argument("--self-test", action="store_true", help="Synthetic end-to-end check")

    args = parser.parse_args(argv)
    _resolve_paths(args)

    if args.self_test:
        return run_self_test()

    if args.init_template is not None:
        emit_template(args.gold, args.init_template, rubric_path=args.rubric)
        return 0

    if args.answers is None:
        parser.error("--answers is required unless using --init-template or --self-test")

    benchmark = load_benchmark(args.benchmark)
    gold = load_gold(args.gold, rubric_path=args.rubric)
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
    args.report_md.write_text(render_markdown(pmr_rows, pmr_agg, ab, args.judge_mode), encoding="utf-8")

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
