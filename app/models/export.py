from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.models.contracts import (
    DecisionDossier,
    DocumentSummary,
    NeedsReviewDossier,
    RunSummary,
    ValidationSummary,
)
from app.models.events import DecisionEvent


class RepairAttemptSummary(BaseModel):
    candidate_id: str | None = None
    node_name: str
    schema_name: str | None = None
    attempt: int
    outcome: Literal["repaired", "failed", "attempted"]
    error_excerpt: str = ""


class EvalResultSummary(BaseModel):
    run_id: str | None = None
    scope: Literal["run", "suite"] = "suite"
    name: str
    status: Literal["pass", "fail", "skipped"]
    value: float | None = None
    details: str = ""
    ts: datetime | None = None


class TraceRef(BaseModel):
    candidate_id: str | None = None
    node_name: str | None = None
    trace_id: str
    url: str | None = None


class AuditExport(BaseModel):
    schema_version: Literal["audit-export.v1"] = "audit-export.v1"
    generated_at: datetime
    run: RunSummary
    documents: list[DocumentSummary]
    candidate_dossiers: list[DecisionDossier | NeedsReviewDossier]
    decision_events: list[DecisionEvent]
    validation_summaries: list[ValidationSummary]
    repair_attempts: list[RepairAttemptSummary]
    run_eval_results: list[EvalResultSummary]
    suite_eval_summary: list[EvalResultSummary]
    # Backward-compatible combined view for tools that already read eval_results.
    eval_results: list[EvalResultSummary] = []
    trace_refs: list[TraceRef]
    export_status: Literal["complete", "partial"]
    warnings: list[str] = []
