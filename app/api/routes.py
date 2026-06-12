from __future__ import annotations

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, File, Form, Query, UploadFile

import app as app_pkg
from app.api.schemas import (
    HealthResponse,
    InterviewPreviewResponse,
    RunCreateResponse,
    RunStatusResponse,
)
from app.core.config import get_settings
from app.core.errors import (
    CandidateNotFoundError,
    FileTooLargeError,
    MissingDocumentError,
    RunNotFoundError,
    UnsupportedFileTypeError,
)
from app.ledger.export import assemble_audit_export
from app.locale import zh_CN as msg
from app.models.contracts import CandidateRunResult
from app.models.events import DecisionEvent
from app.models.export import AuditExport, EvalResultSummary
from app.observability.tracing import langfuse_credentials_verified
from app.storage import repository
from app.workflows.parsing import ALLOWED_EXTENSIONS
from app.workflows.runner import (
    create_run_from_fixtures,
    create_run_from_uploads,
    execute_run,
)

router = APIRouter()


async def _read_upload(upload: UploadFile) -> tuple[str, bytes]:
    settings = get_settings()
    filename = upload.filename or "unnamed"
    if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
        raise UnsupportedFileTypeError(msg.unsupported_file_type(filename))
    data = await upload.read()
    if len(data) > settings.max_file_bytes:
        raise FileTooLargeError(msg.file_too_large(filename, settings.max_file_mb))
    if not data:
        raise MissingDocumentError(msg.file_empty(filename))
    return filename, data


@router.post("/api/runs", response_model=RunCreateResponse, status_code=202)
async def create_run(
    background_tasks: BackgroundTasks,
    mode: Literal["live", "replay"] | None = Query(default=None),
    idempotency_key: str | None = Form(default=None),
    jd: UploadFile | None = File(default=None),  # noqa: B008
    resumes: list[UploadFile] = File(default=[]),  # noqa: B008
) -> RunCreateResponse:
    settings = get_settings()
    effective_mode = mode or settings.demo_mode

    if idempotency_key:
        existing = repository.find_run_by_idempotency_key(idempotency_key)
        if existing:
            run = repository.get_run(existing)
            return RunCreateResponse(run_id=existing, status=run.status, existing=True)

    if effective_mode == "replay":
        if jd is not None or resumes:
            raise MissingDocumentError(msg.replay_rejects_uploads())
        run_id = create_run_from_fixtures(idempotency_key)
    else:
        jd_payload = await _read_upload(jd) if jd is not None else None
        resume_payloads = [await _read_upload(upload) for upload in resumes]
        run_id = create_run_from_uploads(jd_payload, resume_payloads, idempotency_key)

    background_tasks.add_task(execute_run, run_id)
    return RunCreateResponse(run_id=run_id, status="queued")


@router.get("/api/runs/{run_id}", response_model=RunStatusResponse)
def get_run(run_id: str) -> RunStatusResponse:
    run = repository.get_run(run_id)
    if run is None:
        raise RunNotFoundError(msg.run_not_found(run_id))
    return RunStatusResponse(
        run=run,
        candidates=repository.get_candidate_results(run_id),
        documents=repository.document_summaries(run_id),
    )


@router.get("/api/runs/{run_id}/events", response_model=list[DecisionEvent])
def get_run_events(run_id: str) -> list[DecisionEvent]:
    if repository.get_run(run_id) is None:
        raise RunNotFoundError(msg.run_not_found(run_id))
    return repository.get_events(run_id)


@router.get("/api/runs/{run_id}/audit-export", response_model=AuditExport)
def get_audit_export(run_id: str) -> AuditExport:
    return assemble_audit_export(run_id)


@router.get("/api/candidates/{candidate_id}/dossier", response_model=CandidateRunResult)
def get_candidate_dossier(candidate_id: str) -> CandidateRunResult:
    found = repository.get_candidate(candidate_id)
    if found is None:
        raise CandidateNotFoundError(msg.candidate_not_found(candidate_id))
    _run_id, result = found
    return result


@router.get(
    "/api/candidates/{candidate_id}/interview/preview",
    response_model=InterviewPreviewResponse,
)
def get_interview_preview(candidate_id: str) -> InterviewPreviewResponse:
    found = repository.get_candidate(candidate_id)
    if found is None:
        raise CandidateNotFoundError(msg.candidate_not_found(candidate_id))
    _run_id, result = found
    if result.dossier is None or result.status != "completed":
        raise MissingDocumentError(msg.interview_preview_requires_dossier())

    score = result.dossier.score
    top_risks = score.risk_flags[:2]
    follow_ups = [follow_up.question for follow_up in result.dossier.follow_ups[:2]]
    if score.recommendation == "proceed":
        persona = "严谨的技术负责人，验证深度和真实生产经验"
    elif score.recommendation == "hold":
        persona = "关注落地风险的部门负责人，先追问模糊点和风险"
    else:
        persona = "亲切但直接的 HR，确认是否有转岗或培养空间"
    opening = follow_ups[0] if follow_ups else result.dossier.questions[0].question
    return InterviewPreviewResponse(
        candidate_id=candidate_id,
        candidate_name=result.dossier.candidate_name,
        interviewer_persona=persona,
        opening_question=opening,
        focus_areas=[
            f"{msg.FOCUS_RECOMMENDATION}={score.recommendation}",
            f"{msg.FOCUS_SCORE}={score.overall_score}",
            *top_risks,
        ],
    )


@router.get("/api/evals", response_model=list[EvalResultSummary])
def get_evals() -> list[EvalResultSummary]:
    return repository.get_eval_results()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        mode=settings.demo_mode,
        version=app_pkg.__version__,
        langfuse_enabled=settings.langfuse_configured,
        langfuse_verified=langfuse_credentials_verified(settings),
    )
