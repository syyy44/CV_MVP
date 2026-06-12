from __future__ import annotations

import operator
from typing import Annotated, TypedDict

from app.models.contracts import CandidateRunResult, JobRubric
from app.workflows.context import WorkflowContext


class RunGraphState(TypedDict, total=False):
    ctx: WorkflowContext
    jd_doc: dict
    resume_docs: list[dict]
    rubric: JobRubric
    candidate_results: Annotated[list[CandidateRunResult], operator.add]


class CandidateState(TypedDict, total=False):
    ctx: WorkflowContext
    rubric: JobRubric
    jd_doc: dict
    resume_doc: dict
    candidate_id: str
    slug: str
    candidate_trace_id: str
    profile: object
    analysis: object
    score: object
    breakdown: object
    questions: list
    follow_ups: list
    metas: list
    halt: bool
    halt_kind: str
    halt_reason: str
    missing_fields: list[str]
    repair_attempts: int
    result: CandidateRunResult
