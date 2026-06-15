from __future__ import annotations

from pydantic import BaseModel, Field

from app.models.contracts import (
    CandidateRunResult,
    DocumentSummary,
    Recommendation,
    RunSummary,
)


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


class RunListItem(BaseModel):
    run: RunSummary
    jd_filename: str | None = None
    resume_count: int = 0
    candidate_count: int = 0
    top_candidate_name: str | None = None
    top_score: int | None = None


class HealthResponse(BaseModel):
    status: str = "ok"
    mode: str
    version: str
    langfuse_enabled: bool
    langfuse_verified: bool = False


class TestDataFile(BaseModel):
    filename: str
    url: str


class TestDataManifest(BaseModel):
    jd: TestDataFile
    resumes: list[TestDataFile]


class NoteCreateRequest(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    author: str = Field(default="面试官", max_length=80)


class DecisionPatchRequest(BaseModel):
    recommendation: Recommendation
    rationale: str = Field(min_length=1, max_length=2000)
    actor: str = Field(default="面试官", max_length=80)
