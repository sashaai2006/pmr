"""Run a single PromptStrategy over the tasks of a suite, save raw + payload files."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from src.domain.schemas import NormalizedTask, utc_timestamp
from src.formatting.json_formatter import save_json
from src.formatting.markdown_formatter import save_markdown
from src.infrastructure.repo import write_json
from src.llm.client import LLMClient
from src.prompting.strategies import PromptStrategy, RunContext, RunOutput

log = logging.getLogger("metabotik.run")


@dataclass
class RunSummary:
    suite: str
    mode: str
    run_id: str
    n_tasks: int
    n_completed: int
    n_failed: int
    elapsed_seconds: float
    failed_task_ids: list[str] = field(default_factory=list)
    repair_attempts: int = 0


def _save_raw_response(out_dir: Path, task_id: str, stage: str, content: str) -> Path:
    raw_dir = out_dir / "_raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    path = raw_dir / f"{task_id}.{stage}.raw.txt"
    path.write_text(content, encoding="utf-8")
    return path


def _save_error(out_dir: Path, task: NormalizedTask, stage: str, exc: BaseException) -> Path:
    err_dir = out_dir / "_errors"
    err_dir.mkdir(parents=True, exist_ok=True)
    path = err_dir / f"{task.task_id}.{stage}.json"
    payload = {
        "task_id": task.task_id,
        "domain": task.domain,
        "title": task.title,
        "stage": stage,
        "error_type": type(exc).__name__,
        "message": str(exc),
        "timestamp": utc_timestamp(),
    }
    write_json(path, payload)
    return path


def _is_pmr_payload(payload: dict[str, Any]) -> bool:
    return "procedural_analysis" in payload and "solution_steps" in payload


class RunUseCase:
    """Execute a strategy over a list of tasks, persist outputs into `out_dir`."""

    def __init__(
        self,
        *,
        strategy: PromptStrategy,
        llm: LLMClient,
        out_dir: Path,
        suite: str,
        mode: str,
        run_id: str,
        request_sleep_seconds: float = 0.0,
        save_raw: bool = True,
    ) -> None:
        self._strategy = strategy
        self._llm = llm
        self._out_dir = out_dir
        self._suite = suite
        self._mode = mode
        self._run_id = run_id
        self._sleep = request_sleep_seconds
        self._save_raw = save_raw

    def run_one(self, task: NormalizedTask) -> RunOutput:
        save_raw_fn = None
        if self._save_raw:
            def save_raw_fn(stage: str, content: str) -> None:
                _save_raw_response(self._out_dir, task.task_id, stage, content)
        ctx = RunContext(save_raw=save_raw_fn)
        return self._strategy.run(task, self._llm, ctx)

    def _save_output(self, task: NormalizedTask, output: RunOutput) -> None:
        if _is_pmr_payload(output.payload):
            from src.domain.schemas import AgentResult

            payload = dict(output.payload)
            # The prompt asks the LLM to echo these identifiers, but the runner
            # owns the task loop. Normalising here prevents a bad model echo from
            # overwriting another task's result file.
            payload["task_id"] = task.task_id
            payload["difficulty"] = task.difficulty.value
            result = AgentResult.model_validate(payload)
            save_json(result, self._out_dir)
            save_markdown(result, self._out_dir)
        else:
            write_json(self._out_dir / f"{task.task_id}.json", output.payload)

    def run_all(
        self,
        tasks: list[NormalizedTask],
        *,
        skip_existing: bool = False,
    ) -> RunSummary:
        started = time.perf_counter()
        completed: list[str] = []
        failed: list[str] = []
        repair = 0
        log.info(
            "run_all suite=%s mode=%s run_id=%s tasks=%d out=%s",
            self._suite, self._mode, self._run_id, len(tasks), self._out_dir,
        )
        for index, task in enumerate(tasks):
            out_path = self._out_dir / f"{task.task_id}.json"
            if skip_existing and out_path.exists():
                log.info("[%s] SKIP existing %s", task.task_id, out_path)
                completed.append(task.task_id)
                continue
            log.info("--- task %d/%d %s ---", index + 1, len(tasks), task.task_id)
            try:
                output = self.run_one(task)
                self._save_output(task, output)
                if not out_path.exists():
                    raise RuntimeError(f"expected output was not written: {out_path}")
                if output.repair_attempted:
                    repair += 1
                completed.append(task.task_id)
                log.info("[%s] DONE -> %s", task.task_id, out_path)
            except Exception as exc:
                log.exception("[%s] FAILED: %s", task.task_id, exc)
                _save_error(self._out_dir, task, "run", exc)
                failed.append(task.task_id)
            if index + 1 < len(tasks) and self._sleep > 0:
                time.sleep(self._sleep)

        summary = RunSummary(
            suite=self._suite,
            mode=self._mode,
            run_id=self._run_id,
            n_tasks=len(tasks),
            n_completed=len(completed),
            n_failed=len(failed),
            elapsed_seconds=round(time.perf_counter() - started, 3),
            failed_task_ids=failed,
            repair_attempts=repair,
        )
        write_json(
            self._out_dir / "run_summary.json",
            {
                "suite": summary.suite,
                "mode": summary.mode,
                "run_id": summary.run_id,
                "n_tasks": summary.n_tasks,
                "n_completed": summary.n_completed,
                "n_failed": summary.n_failed,
                "failed_task_ids": summary.failed_task_ids,
                "repair_attempts": summary.repair_attempts,
                "elapsed_seconds": summary.elapsed_seconds,
                "timestamp": utc_timestamp(),
            },
        )
        log.info(
            "run_all done: completed=%d failed=%d repair=%d elapsed=%.2fs",
            summary.n_completed, summary.n_failed, summary.repair_attempts, summary.elapsed_seconds,
        )
        return summary
