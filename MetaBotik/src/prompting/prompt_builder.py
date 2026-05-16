"""Build chat messages for the LLM."""

from __future__ import annotations

from src.domain.schemas import ChatMessage, NormalizedTask, ProcedureChoice
from src.prompting.templates import load_prompt, render_string

# One file on disk; split at runtime so the API gets system (rules) + user (task payload).
# Some OpenAI-compatible backends return empty assistant content when the entire prompt is only `system`.
_PROMPT_SPLIT_MARKER = "\n\n---\n\n## Current run (substituted values)\n"


class PromptBuilder:
    def build(self, task: NormalizedTask, plan: ProcedureChoice) -> list[ChatMessage]:
        full = load_prompt("system/core_system_prompt.md")
        if _PROMPT_SPLIT_MARKER not in full:
            raise ValueError(
                f"Prompt file must contain split marker {_PROMPT_SPLIT_MARKER!r} "
                "between static instructions and the per-task user payload.",
            )
        system_instructions, user_tail = full.split(_PROMPT_SPLIT_MARKER, 1)
        user_prompt = render_string(
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
            ChatMessage(role="system", content=system_instructions.strip()),
            ChatMessage(role="user", content=user_prompt),
        ]


class BaselinePromptBuilder:
    """Structured baseline (JSON schema in prompt file)."""

    def __init__(self, prompt_relative_path: str = "baseline_prompt.txt") -> None:
        self._prompt_relative_path = prompt_relative_path

    def build(self, task: NormalizedTask) -> list[ChatMessage]:
        prompt = render_string(
            load_prompt(self._prompt_relative_path),
            task_id=task.task_id,
            domain=task.domain,
            title=task.title,
            task=task.prompt,
        )
        return [ChatMessage(role="user", content=prompt)]
