"""Domain enumerations."""

from enum import StrEnum


class TaskType(StrEnum):
    LINEAR = "linear"
    BRANCHING = "branching"
    CYCLIC = "cyclic"
    ANALYTICAL = "analytical"
    DIAGNOSTIC = "diagnostic"
    CREATIVE = "creative"
    MIXED = "mixed"


class Difficulty(StrEnum):
    BASIC = "basic"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"
    EXPERT = "expert"


class PromptMode(StrEnum):
    PMR = "pmr"
    BASELINE = "baseline"
    BASELINE_MINIMAL = "baseline-minimal"
    BASELINE_TWO_STAGE = "baseline-two-stage"


class SuiteName(StrEnum):
    PMR_BENCH = "pmr-bench"


class MetricKind(StrEnum):
    """Names of the deterministic per-case metric blocks emitted by the eval layer."""

    PROCEDURAL_RIGOR = "procedural_rigor"
    RUBRIC = "rubric_score"


class AgentState(StrEnum):
    IDLE = "IDLE"
    LOAD_TASK = "LOAD_TASK"
    NORMALIZE_TASK = "NORMALIZE_TASK"
    CLASSIFY_PROCEDURE = "CLASSIFY_PROCEDURE"
    SELECT_PROCEDURE = "SELECT_PROCEDURE"
    BUILD_PROMPT = "BUILD_PROMPT"
    LLM_EXECUTION = "LLM_EXECUTION"
    PARSE_OUTPUT = "PARSE_OUTPUT"
    VALIDATE_SCHEMA = "VALIDATE_SCHEMA"
    CRITICAL_POINT_CHECK = "CRITICAL_POINT_CHECK"
    PROCEDURAL_REFLECTION = "PROCEDURAL_REFLECTION"
    FORMAT_RESULT = "FORMAT_RESULT"
    SAVE_RESULT = "SAVE_RESULT"
    COMPLETE = "COMPLETE"
    PARSE_FAILURE = "PARSE_FAILURE"
    VALIDATION_FAILURE = "VALIDATION_FAILURE"
    REFLECTION_MISSING = "REFLECTION_MISSING"
    PROCEDURE_MISSING = "PROCEDURE_MISSING"
    SCHEMA_REPAIR = "SCHEMA_REPAIR"
    RETRY = "RETRY"
    FATAL_ERROR = "FATAL_ERROR"
