"""Tests for the four PromptStrategy implementations."""

from __future__ import annotations

import json
from typing import Any

from src.domain.enums import PromptMode
from src.prompting.strategies import (
    BaselineMinimalStrategy,
    BaselineStrategy,
    BaselineTwoStageStrategy,
    PmrStrategy,
    RunContext,
    STRATEGIES,
    get_strategy,
)
from tests.conftest import FakeLLMClient, make_task, valid_agent_payload


def test_registry_has_all_four_modes() -> None:
    assert set(STRATEGIES) == {
        PromptMode.PMR,
        PromptMode.BASELINE,
        PromptMode.BASELINE_MINIMAL,
        PromptMode.BASELINE_TWO_STAGE,
    }


def test_get_strategy_accepts_str_and_enum() -> None:
    assert isinstance(get_strategy("pmr"), PmrStrategy)
    assert isinstance(get_strategy(PromptMode.BASELINE), BaselineStrategy)


def test_pmr_strategy_builds_two_messages() -> None:
    task = make_task()
    strategy = PmrStrategy()
    plan = strategy._planner.plan(task)
    messages = strategy._build_messages(task, plan)
    assert len(messages) == 2
    assert messages[0].role == "system"
    assert messages[1].role == "user"
    assert "MKPI 4.3" in messages[0].content
    assert f"- task_id: {task.task_id}" in messages[1].content


def test_pmr_strategy_full_run_with_fake_llm() -> None:
    task = make_task()
    payload = valid_agent_payload(task.task_id)
    llm = FakeLLMClient(json.dumps(payload))
    captured: list[tuple[str, str]] = []
    ctx = RunContext(save_raw=lambda stage, content: captured.append((stage, content[:30])))

    output = PmrStrategy().run(task, llm, ctx)
    assert output.payload["task_id"] == task.task_id
    assert output.payload["procedural_analysis"]["selected_procedure"]
    assert output.repair_attempted is False
    assert any(stage == "initial" for stage, _ in captured)


def test_baseline_strategy_passes_json_through() -> None:
    task = make_task()
    payload: dict[str, Any] = {
        "task_id": task.task_id,
        "summary": "A concise solution.",
        "plan": [{"step": 1, "title": "A", "what_to_do": "B"}],
        "key_decisions": [{"choice": "C", "rationale": "D"}],
        "risks": ["R"],
        "rationale": "Because it fits the task.",
    }
    llm = FakeLLMClient(json.dumps(payload))
    output = BaselineStrategy().run(task, llm, RunContext())
    assert output.payload["plan"][0]["what_to_do"] == "B"
    assert output.payload["example_id"] == task.task_id


def test_baseline_minimal_strategy_loads_minimal_prompt() -> None:
    task = make_task()
    llm = FakeLLMClient(json.dumps({"answer": "x"}))
    output = BaselineMinimalStrategy().run(task, llm, RunContext())
    # Verify the prompt that was sent included the task statement
    sent = llm.calls[0][0].content
    assert task.prompt in sent
    assert '"answer"' in sent
    assert "key_decisions" not in sent
    assert output.payload["task_id"] == task.task_id


def test_baseline_two_stage_invokes_llm_twice() -> None:
    task = make_task()
    free_text = "Free-form narrative answer."
    packed = json.dumps({
        "summary": "x",
        "plan": [],
        "key_decisions": [],
        "risks": [],
        "rationale": "x",
    })

    class TwoStepLLM:
        def __init__(self) -> None:
            self.calls: list[dict[str, Any]] = []

        def complete(
            self,
            messages: list[Any],
            *,
            json_response: bool = True,
            use_baseline_packager_model: bool = False,
        ) -> Any:
            self.calls.append({"json": json_response, "packager": use_baseline_packager_model})
            from src.domain.schemas import RawCompletion

            if json_response:
                return RawCompletion(content=packed, model="m", temperature=0.2, top_p=0.9)
            return RawCompletion(content=free_text, model="m", temperature=0.2, top_p=0.9)

    llm = TwoStepLLM()
    output = BaselineTwoStageStrategy().run(task, llm, RunContext())
    assert len(llm.calls) == 2
    assert llm.calls[0]["json"] is False  # solve step is text
    assert llm.calls[1]["json"] is True   # packager step is JSON
    assert llm.calls[1]["packager"] is True
    assert output.payload["task_id"] == task.task_id
