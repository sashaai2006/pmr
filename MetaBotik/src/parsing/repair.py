"""Repair invalid LLM output with one additional call."""

from __future__ import annotations

import logging

from src.domain.schemas import AgentResult, ChatMessage, NormalizedTask, ProcedureChoice, ResultMetadata, utc_timestamp
from src.llm.client import LLMClient
from src.parsing.parser import ResponseParser
from src.prompting.templates import render_template

log = logging.getLogger("metabotik.repair")


class ResponseRepairer:
    def __init__(self, client: LLMClient, parser: ResponseParser | None = None) -> None:
        self._client = client
        self._parser = parser or ResponseParser()

    def repair(
        self,
        task: NormalizedTask,
        plan: ProcedureChoice,
        invalid_response: str,
        validation_errors: str,
    ) -> AgentResult:
        log.info(
            "repairing invalid LLM response invalid_chars=%d error_summary=%s",
            len(invalid_response),
            validation_errors[:500],
        )
        repair_prompt = render_template(
            "validators/schema_repair.txt",
            expected_task_id=task.task_id,
            expected_task_type=plan.task_type.value,
            expected_difficulty=task.difficulty.value,
            invalid_response=invalid_response,
            validation_errors=validation_errors,
            title=task.title,
            task=task.prompt,
        )
        completion = self._client.complete([ChatMessage(role="user", content=repair_prompt)])
        log.info("repair response received chars=%d", len(completion.content))
        result = self._parser.parse(completion.content)
        result.metadata = ResultMetadata(
            model=completion.model,
            temperature=completion.temperature,
            top_p=completion.top_p,
            timestamp=utc_timestamp(),
        )
        return result
