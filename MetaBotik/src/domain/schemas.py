"""Domain schemas for tasks and agent outputs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.domain.enums import Difficulty, TaskType


def _coerce_llm_text_field(value: Any) -> str:
    """LLMs often nest dicts/lists in string slots; normalize to a single string."""

    if isinstance(value, str):
        return value
    if value is None:
        return ""
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        pieces: list[str] = []
        for item in value:
            coerced = _coerce_llm_text_field(item)
            if coerced:
                pieces.append(coerced)
        return "\n".join(pieces)
    if isinstance(value, dict):
        for key in ("action", "text", "description", "content", "summary", "title", "details"):
            inner = value.get(key)
            if isinstance(inner, str) and inner.strip():
                return inner
            if isinstance(inner, (dict, list)):
                nested = _coerce_llm_text_field(inner)
                if nested:
                    return nested
        if len(value) == 1:
            return _coerce_llm_text_field(next(iter(value.values())))
        return json.dumps(value, ensure_ascii=False)
    return str(value)


class AlternativeProcedure(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str
    rejection_reason: str


class ProceduralAnalysis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    problem_classification: str
    selected_procedure: str
    selection_reasoning: str
    alternative_procedures: list[AlternativeProcedure] = Field(min_length=2)


class SolutionStep(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: int = Field(ge=1)
    title: str
    action: str
    procedure_logic: str
    critical_points: list[str] = Field(min_length=1)
    adaptation_notes: list[str] = Field(default_factory=list)

    @field_validator("title", "action", "procedure_logic", mode="before")
    @classmethod
    def coerce_step_string_fields(cls, value: Any) -> str:
        return _coerce_llm_text_field(value)

    @field_validator("critical_points", "adaptation_notes", mode="before")
    @classmethod
    def coerce_text_to_list(cls, value: Any) -> list[str] | Any:
        if isinstance(value, str):
            return [value]
        return value


class Reflection(BaseModel):
    model_config = ConfigDict(extra="forbid")

    effectiveness: str
    limitations: list[str] = Field(min_length=2)
    best_use_cases: list[str] = Field(min_length=1)
    future_modifications: list[str] = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def fill_missing_effectiveness(cls, value: Any) -> Any:
        if isinstance(value, dict) and not value.get("effectiveness"):
            value = dict(value)
            value["effectiveness"] = (
                "The model did not provide an explicit effectiveness field; "
                "the result was normalized from the available procedural reflection."
            )
        return value

    @field_validator("limitations", "best_use_cases", "future_modifications", mode="before")
    @classmethod
    def coerce_text_to_list(cls, value: Any) -> list[str] | Any:
        if isinstance(value, str):
            return [value]
        return value


class ResultMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model: str
    temperature: float
    top_p: float
    timestamp: str


class AgentResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    task_type: TaskType
    difficulty: Difficulty
    procedural_analysis: ProceduralAnalysis
    solution_steps: list[SolutionStep] = Field(min_length=1, max_length=7)
    reflection: Reflection
    metadata: ResultMetadata


class NormalizedTask(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_id: str
    domain: str
    title: str
    prompt: str
    difficulty: Difficulty = Difficulty.EXPERT


class ProcedureChoice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    task_type: TaskType
    selected_procedure: str
    selection_reasoning: str
    alternative_procedures: list[AlternativeProcedure]


class ChatMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: str
    content: str


class RawCompletion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str
    model: str
    temperature: float
    top_p: float
    elapsed_seconds: float = 0.0
    response_id: str | None = None
    finish_reason: str | None = None


def utc_timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def row_to_dict(row: dict[str, Any] | Any) -> dict[str, Any]:
    if isinstance(row, dict):
        return row
    if hasattr(row, "items"):
        return dict(row.items())
    raise TypeError(f"Unsupported row type: {type(row)!r}")


class GoldReferenceAnswer(BaseModel):
    """Three-stage reference narrative for human judges."""

    model_config = ConfigDict(extra="forbid")

    stage_1_procedural_analysis: str
    stage_2_solution_with_commentary: str
    stage_3_reflection: str


class ExpectedMetaElements(BaseModel):
    """Discrete claims an evaluator can score with deterministic matching."""

    model_config = ConfigDict(extra="forbid")

    decomposition: list[str] = Field(default_factory=list)
    rejected_alternatives: list[str] = Field(default_factory=list)
    critical_points: list[str] = Field(default_factory=list)
    meta_protocol: list[str] = Field(default_factory=list)


class GoldMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_skill: str
    source_section: str = "Душкин Р. В. Метакогнитивная промпт-инженерия (процедурная мета-рефлексия)"
    discriminator_note: str | None = None


class GoldEntry(BaseModel):
    """Gold-standard entry for a single benchmark task.

    Mirrors the per-line schema in suites/<suite>/gold.jsonl.
    """

    model_config = ConfigDict(extra="forbid")

    task_id: str
    reference_answer: GoldReferenceAnswer
    expected_meta_elements: ExpectedMetaElements
    metadata: GoldMetadata


class GoldV2Criterion(BaseModel):
    """Semantically scored rubric item for v2 gold evaluation."""

    model_config = ConfigDict(extra="forbid")

    id: str
    description: str
    weight: float = Field(default=1.0, gt=0.0)
    acceptance_examples: list[str] = Field(default_factory=list)
    partial_credit_guidance: str | None = None


class GoldV2SolutionFamily(BaseModel):
    """One acceptable family of solutions, not a single canonical answer."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str
    required_invariants: list[str] = Field(default_factory=list)
    distinctive_features: list[str] = Field(default_factory=list)


class GoldV2Rubric(BaseModel):
    """Flexible gold rubric that separates invariants from acceptable variation."""

    model_config = ConfigDict(extra="forbid")

    task_goal: str
    must_have_invariants: list[GoldV2Criterion] = Field(default_factory=list)
    acceptable_solution_families: list[GoldV2SolutionFamily] = Field(default_factory=list)
    fatal_omissions: list[GoldV2Criterion] = Field(default_factory=list)
    optional_nice_to_have: list[GoldV2Criterion] = Field(default_factory=list)
    scoring_guidance: str


class GoldV2Entry(BaseModel):
    """Gold v2 entry for semantic judging without one-rigid-answer bias."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    evaluation_version: str = "gold_v2"
    rubric: GoldV2Rubric
    reference_answer: GoldReferenceAnswer | None = None
    metadata: GoldMetadata


class CategoryCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    matched: int
    expected: int
    ratio: float


class CoverageScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    by_category: dict[str, CategoryCoverage]
    macro_ratio: float
    micro_ratio: float


class RubricAxes(BaseModel):
    """Five-axis publication rubric: 0-2 per axis, total 0-10."""

    model_config = ConfigDict(extra="forbid")

    procedural_self_awareness: int = Field(ge=0, le=2)
    decomposition_quality: int = Field(ge=0, le=2)
    justification_depth: int = Field(ge=0, le=2)
    reflection_actionability: int = Field(ge=0, le=2)
    reproducibility: int = Field(ge=0, le=2)

    @property
    def total(self) -> int:
        return (
            self.procedural_self_awareness
            + self.decomposition_quality
            + self.justification_depth
            + self.reflection_actionability
            + self.reproducibility
        )


class CaseScore(BaseModel):
    """Per-case score block: optional manual rubric (CSV) keyed by task_id."""

    model_config = ConfigDict(extra="forbid")

    task_id: str
    rubric: RubricAxes | None = None
    rubric_total: int | None = None
    pass_threshold: int = 7
    pass_binary: bool | None = None
    notes: str | None = None


class EvalReport(BaseModel):
    """Aggregate report for a single (suite, mode, run_id) triple."""

    model_config = ConfigDict(extra="forbid")

    suite: str
    mode: str
    run_id: str
    n_tasks: int
    by_task: list[CaseScore]
    summary: dict[str, Any]
