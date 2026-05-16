"""End-to-end pipeline: run × modes × repeats → eval → LLM quality judge → compare + paired."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from src.application.eval_usecase import EvalUseCase
from src.application.run_usecase import RunUseCase
from src.domain.enums import PromptMode
from src.evaluation.compare import compare_summaries, load_summary, save_comparison
from src.evaluation.paired_stats import paired_stats, save_paired_stats
from src.evaluation.quality_judge import (
    BY_TASK_FILENAME as QUALITY_JUDGE_BY_TASK_FILENAME,
    SUMMARY_FILENAME as QUALITY_JUDGE_SUMMARY_FILENAME,
    QualityJudgeUseCase,
)
from src.infrastructure.run_dir import RunDirManager
from src.llm.client import LLMClient
from src.prompting.strategies import get_strategy
from suites import get_suite

log = logging.getLogger("metabotik.pipeline")


@dataclass
class RunRecord:
    suite: str
    mode: PromptMode
    run_id: str
    run_dir: Path


@dataclass
class PipelineOutcome:
    runs: list[RunRecord] = field(default_factory=list)
    quality_judge_summary_paths: list[Path] = field(default_factory=list)
    comparison_paths: list[Path] = field(default_factory=list)
    paired_stats_paths: list[Path] = field(default_factory=list)


class PipelineUseCase:
    def __init__(
        self,
        *,
        llm: LLMClient,
        run_dir_manager: RunDirManager,
        request_sleep_seconds: float = 0.0,
        save_raw: bool = True,
    ) -> None:
        self._llm = llm
        self._run_dirs = run_dir_manager
        self._sleep = request_sleep_seconds
        self._save_raw = save_raw

    def execute(
        self,
        *,
        suite_name: str,
        modes: list[PromptMode],
        repeat: int = 1,
        limit: int | None = None,
        skip_run: bool = False,
        compare_pairs: list[tuple[PromptMode, PromptMode]] | None = None,
        quality_judge: bool = True,
    ) -> PipelineOutcome:
        suite = get_suite(suite_name)
        all_tasks = suite.load_tasks()
        if limit is not None:
            all_tasks = all_tasks[:limit]
        outcome = PipelineOutcome()
        runs_by_mode: dict[PromptMode, list[RunRecord]] = {m: [] for m in modes}
        tasks_by_id = {task.task_id: task for task in all_tasks}
        gold_v2_by_id = {entry.task_id: entry for entry in suite.load_gold_v2()}

        for rep in range(1, repeat + 1):
            log.info("=== repeat %d/%d ===", rep, repeat)
            for mode in modes:
                run_dir = self._run_dirs.new_run_dir(suite_name, mode.value)
                run_id = run_dir.name
                record = RunRecord(suite=suite_name, mode=mode, run_id=run_id, run_dir=run_dir)
                outcome.runs.append(record)
                runs_by_mode[mode].append(record)
                if not skip_run:
                    strategy = get_strategy(mode)
                    RunUseCase(
                        strategy=strategy,
                        llm=self._llm,
                        out_dir=run_dir,
                        suite=suite_name,
                        mode=mode.value,
                        run_id=run_id,
                        request_sleep_seconds=self._sleep,
                        save_raw=self._save_raw,
                    ).run_all(all_tasks)
                EvalUseCase(
                    run_dir=run_dir,
                    suite=suite_name,
                    mode=mode.value,
                    run_id=run_id,
                ).run()
                if quality_judge and any(run_dir.glob("PMR-*.json")):
                    log.info("quality judge suite=%s mode=%s run_id=%s", suite_name, mode.value, run_id)
                    QualityJudgeUseCase(
                        run_dir=run_dir,
                        tasks_by_id=tasks_by_id,
                        gold_v2_by_id=gold_v2_by_id,
                        llm=self._llm,
                    ).execute(sleep_seconds=self._sleep)
                    outcome.quality_judge_summary_paths.append(
                        run_dir / QUALITY_JUDGE_SUMMARY_FILENAME,
                    )
                elif quality_judge:
                    log.warning("quality judge skipped: no PMR-*.json answers in %s", run_dir)

        if compare_pairs is None:
            compare_pairs = [
                (PromptMode.PMR, baseline)
                for baseline in modes
                if baseline != PromptMode.PMR
            ] if PromptMode.PMR in modes else []

        comparison_dir = self._run_dirs.base / suite_name / "_comparison"
        for cand_mode, base_mode in compare_pairs:
            cand_runs = runs_by_mode.get(cand_mode, [])
            base_runs = runs_by_mode.get(base_mode, [])
            if not cand_runs or not base_runs:
                continue
            cand = cand_runs[-1]
            base = base_runs[-1]
            log.info("compare %s vs %s (run_ids=%s/%s)", cand_mode.value, base_mode.value, cand.run_id, base.run_id)

            cand_eval = cand.run_dir / "summary.json"
            base_eval = base.run_dir / "summary.json"
            cand_quality = cand.run_dir / QUALITY_JUDGE_SUMMARY_FILENAME
            base_quality = base.run_dir / QUALITY_JUDGE_SUMMARY_FILENAME
            if cand_quality.exists() and base_quality.exists():
                cand_summary_path, base_summary_path = cand_quality, base_quality
            else:
                cand_summary_path, base_summary_path = cand_eval, base_eval

            comparison = compare_summaries(
                candidate=load_summary(cand_summary_path),
                baseline=load_summary(base_summary_path),
                candidate_label=cand_mode.value,
                baseline_label=base_mode.value,
            )
            cmp_path = comparison_dir / f"compare_{cand_mode.value}_vs_{base_mode.value}.json"
            save_comparison(comparison, cmp_path)
            outcome.comparison_paths.append(cmp_path)

            cand_bt = cand.run_dir / QUALITY_JUDGE_BY_TASK_FILENAME
            base_bt = base.run_dir / QUALITY_JUDGE_BY_TASK_FILENAME
            if cand_bt.exists() and base_bt.exists():
                paired_cand, paired_base = cand_bt, base_bt
            else:
                paired_cand, paired_base = cand.run_dir / "by_task.jsonl", base.run_dir / "by_task.jsonl"

            try:
                stats = paired_stats(
                    candidate_path=paired_cand,
                    baseline_path=paired_base,
                    candidate_label=cand_mode.value,
                    baseline_label=base_mode.value,
                )
            except ValueError as exc:
                log.warning("paired_stats skipped (%s)", exc)
            else:
                paired_path = comparison_dir / f"paired_{cand_mode.value}_vs_{base_mode.value}.json"
                save_paired_stats(stats, paired_path)
                outcome.paired_stats_paths.append(paired_path)

        return outcome
