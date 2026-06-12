from __future__ import annotations

from pydantic import BaseModel

from app.models.contracts import CandidateRunResult, DocumentSummary, RunSummary


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class RunCreateResponse(BaseModel):
    run_id: str
    status: str
    existing: bool = False


class RunStatusResponse(BaseModel):
    run: RunSummary
    candidates: list[CandidateRunResult]
    documents: list[DocumentSummary]


class HealthResponse(BaseModel):
    status: str = "ok"
    mode: str
    version: str
    langfuse_enabled: bool
    langfuse_verified: bool = False


class InterviewPreviewResponse(BaseModel):
    candidate_id: str
    candidate_name: str
    interviewer_persona: str
    opening_question: str
    focus_areas: list[str]
    source: str = "deterministic_dossier_preview"
