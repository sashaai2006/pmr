"""Prompt strategies — one class per prompt mode (`pmr`, `baseline`,
`baseline-minimal`, `baseline-two-stage`).

Each strategy is fully self-contained: it builds its own messages, parses its
own JSON shape, and decides whether the second-stage packager call is needed.
The runner only sees `PromptStrategy.run(task, llm, ctx) -> RunOutput`.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, ClassVar, Protocol

from src.domain.enums import PromptMode
from src.domain.schemas import (
    ChatMessage,
    NormalizedTask,
    ProcedureChoice,
    RawCompletion,
    ResultMetadata,
    utc_timestamp,
)
from src.llm.client import LLMClient
from src.parsing.exceptions import SchemaRepairNeeded
from src.parsing.parser import ResponseParser
from src.parsing.repair import ResponseRepairer
from src.planning.planner import ProcedurePlanner
from src.prompting.templates import load_prompt, render_string

log = logging.getLogger("metabotik.strategy")

_PMR_SPLIT_MARKER = "\n\n---\n\n## Current run (substituted values)\n"


@dataclass(frozen=True)
class RunContext:
    """Side-effect surface a strategy needs (logging, raw save).

    Decoupled from the file-system so strategies stay easy to unit-test.
    """

    save_raw: Callable[[str, str], None] | None = None
    """`(stage, content) -> None`. Persists the raw LLM response for debugging."""


@dataclass
class RunOutput:
    """End-to-end output of a single strategy run on a single task."""

    payload: dict[str, Any]
    completions: list[RawCompletion] = field(default_factory=list)
    repair_attempted: bool = False


class PromptStrategy(Protocol):
    name: ClassVar[PromptMode]

    def run(
        self,
        task: NormalizedTask,
        llm: LLMClient,
        ctx: RunContext,
    ) -> RunOutput: ...


def _task_template_values(task: NormalizedTask) -> dict[str, str]:
    return {
        "task_id": task.task_id,
        "domain": task.domain,
        "title": task.title,
        "task": task.prompt,
    }


def _save_raw(ctx: RunContext, stage: str, content: str) -> None:
    if ctx.save_raw is not None:
        ctx.save_raw(stage, content)


class PmrStrategy:
    """Procedural Meta-Reflection mode.

    Loads the full `system/core_system_prompt.md`, splits it at the marker,
    sends (system, user) to the LLM, validates response against `AgentResult`,
    and invokes the schema-repair loop on validation failure.
    """

    name: ClassVar[PromptMode] = PromptMode.PMR

    def __init__(
        self,
        planner: ProcedurePlanner | None = None,
        parser: ResponseParser | None = None,
        repairer_factory: Callable[[LLMClient, ResponseParser], ResponseRepairer] | None = None,
    ) -> None:
        self._planner = planner or ProcedurePlanner()
        self._parser = parser or ResponseParser()
        self._repairer_factory = repairer_factory or (
            lambda llm, parser: ResponseRepairer(llm, parser)
        )

    def _build_messages(self, task: NormalizedTask, plan: ProcedureChoice) -> list[ChatMessage]:
        full = load_prompt("system/core_system_prompt.md")
        if _PMR_SPLIT_MARKER not in full:
            raise ValueError(
                f"PMR prompt must contain split marker {_PMR_SPLIT_MARKER!r}",
            )
        system_part, user_tail = full.split(_PMR_SPLIT_MARKER, 1)
        user_part = render_string(
            user_tail,
            task_id=task.task_id,
            domain=task.domain,
            title=task.title,
            task_type=plan.task_type.value,
            difficulty=task.difficulty.value,
            selected_procedure=plan.selected_procedure,
            task=task.prompt,
        )
        return [
            ChatMessage(role="system", content=system_part.strip()),
            ChatMessage(role="user", content=user_part),
        ]

    def run(
        self,
        task: NormalizedTask,
        llm: LLMClient,
        ctx: RunContext,
    ) -> RunOutput:
        plan = self._planner.plan(task)
        messages = self._build_messages(task, plan)
        completion = llm.complete(messages, json_response=True)
        _save_raw(ctx, "initial", completion.content)

        repair_attempted = False
        try:
            result = self._parser.parse(completion.content)
        except SchemaRepairNeeded as exc:
            repair_attempted = True
            log.warning(
                "[%s] PMR initial parse failed: %s; running schema repair",
                task.task_id,
                str(exc)[:200],
            )
            _save_raw(ctx, "initial-invalid", exc.raw_content)
            repairer = self._repairer_factory(llm, self._parser)
            result = repairer.repair(task, plan, exc.raw_content, str(exc))

        result.metadata = ResultMetadata(
            model=completion.model,
            temperature=completion.temperature,
            top_p=completion.top_p,
            timestamp=utc_timestamp(),
        )
        payload: dict[str, Any] = result.model_dump(mode="json")
        return RunOutput(payload=payload, completions=[completion], repair_attempted=repair_attempted)


class _SingleShotJsonStrategy:
    """Common helper for one-shot baseline JSON strategies."""

    prompt_path: ClassVar[str]
    raw_stage: ClassVar[str]

    def run(
        self,
        task: NormalizedTask,
        llm: LLMClient,
        ctx: RunContext,
    ) -> RunOutput:
        prompt = render_string(load_prompt(self.prompt_path), **_task_template_values(task))
        messages = [ChatMessage(role="user", content=prompt)]
        completion = llm.complete(messages, json_response=True)
        _save_raw(ctx, self.raw_stage, completion.content)
        try:
            payload = json.loads(completion.content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"baseline response is not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("baseline response must be a JSON object")
        payload.setdefault("task_id", task.task_id)
        payload.setdefault("example_id", task.task_id)
        return RunOutput(payload=payload, completions=[completion])


class BaselineStrategy(_SingleShotJsonStrategy):
    """One-shot baseline with chain-of-thought hint and an explicit JSON schema."""

    name: ClassVar[PromptMode] = PromptMode.BASELINE
    prompt_path: ClassVar[str] = "baseline_prompt.txt"
    raw_stage: ClassVar[str] = "baseline"


class BaselineMinimalStrategy(_SingleShotJsonStrategy):
    """Smallest possible JSON baseline (no system instructions, just schema + task)."""

    name: ClassVar[PromptMode] = PromptMode.BASELINE_MINIMAL
    prompt_path: ClassVar[str] = "baseline_minimal.txt"
    raw_stage: ClassVar[str] = "baseline-minimal"


class BaselineTwoStageStrategy:
    """Two-stage baseline: free-form text solve, then a deterministic JSON packager."""

    name: ClassVar[PromptMode] = PromptMode.BASELINE_TWO_STAGE
    solve_prompt_path: ClassVar[str] = "baseline_twostage_solve.txt"
    packager_prompt_path: ClassVar[str] = "baseline_twostage_packager.md"

    def run(
        self,
        task: NormalizedTask,
        llm: LLMClient,
        ctx: RunContext,
    ) -> RunOutput:
        solve_prompt = render_string(
            load_prompt(self.solve_prompt_path),
            **_task_template_values(task),
        )
        solve_completion = llm.complete(
            [ChatMessage(role="user", content=solve_prompt)],
            json_response=False,
        )
        _save_raw(ctx, "baseline-freeform", solve_completion.content)

        packager_prompt = render_string(
            load_prompt(self.packager_prompt_path),
            **_task_template_values(task),
            narrative=solve_completion.content.strip(),
        )
        pack_completion = llm.complete(
            [ChatMessage(role="user", content=packager_prompt)],
            json_response=True,
            use_baseline_packager_model=True,
        )
        _save_raw(ctx, "baseline-packager", pack_completion.content)

        try:
            payload = json.loads(pack_completion.content)
        except json.JSONDecodeError as exc:
            raise ValueError(f"packager response is not valid JSON: {exc}") from exc
        if not isinstance(payload, dict):
            raise ValueError("packager response must be a JSON object")
        payload.setdefault("task_id", task.task_id)
        payload.setdefault("example_id", task.task_id)
        return RunOutput(payload=payload, completions=[solve_completion, pack_completion])


# Registry. CLI looks up strategies by enum value; pyproject pinned `pmr`/`baseline`/...
STRATEGIES: dict[PromptMode, type[PromptStrategy]] = {
    PmrStrategy.name: PmrStrategy,
    BaselineStrategy.name: BaselineStrategy,
    BaselineMinimalStrategy.name: BaselineMinimalStrategy,
    BaselineTwoStageStrategy.name: BaselineTwoStageStrategy,
}


def get_strategy(mode: PromptMode | str) -> PromptStrategy:
    if isinstance(mode, str):
        mode = PromptMode(mode)
    klass = STRATEGIES[mode]
    return klass()
