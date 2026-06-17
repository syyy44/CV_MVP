from __future__ import annotations

from pathlib import Path
from typing import Literal
from urllib.parse import quote

from fastapi import APIRouter, BackgroundTasks, File, Form, Query, UploadFile
from fastapi.responses import FileResponse

import app as app_pkg
from app.api.schemas import (
    DecisionPatchRequest,
    HealthResponse,
    NoteCreateRequest,
    RunCreateResponse,
    RunListItem,
    RunStatusResponse,
    TestDataFile,
    TestDataManifest,
)
from app.core.config import get_settings
from app.core.errors import (
    CandidateNotCompletedError,
    CandidateNotFoundError,
    CompareNotComparableError,
    FileTooLargeError,
    MissingDocumentError,
    RunNotCancellableError,
    RunNotFoundError,
    UnsupportedFileTypeError,
)
from app.ledger.events import LedgerRecorder
from app.ledger.export import assemble_audit_export
from app.locale import zh_CN as msg
from app.models.contracts import (
    CandidateComparison,
    CandidateNote,
    CandidateRunResult,
    DecisionDossier,
    HumanOverride,
    RunSummary,
)
from app.models.events import DecisionEvent
from app.models.export import AuditExport, EvalResultSummary
from app.models.interview_script import InterviewScriptResponse
from app.observability.tracing import langfuse_credentials_verified
from app.storage import repository
from app.workflows.compare import build_comparison
from app.workflows.interview_script import build_interview_script
from app.workflows.parsing import ALLOWED_EXTENSIONS
from app.workflows.runner import (
    create_run_from_fixtures,
    create_run_from_test_data,
    process_run,
    stage_run_from_uploads,
)
from app.workflows.test_data import list_test_data_files, resolve_test_data_file

router = APIRouter()


async def _resolve_jd_payload(
    jd: UploadFile | None,
    jd_text: str | None,
) -> tuple[str, bytes] | None:
    has_file = jd is not None
    text = (jd_text or "").strip()
    has_text = bool(text)
    if has_file and has_text:
        raise MissingDocumentError(msg.jd_upload_and_text_conflict())
    if has_text:
        settings = get_settings()
        data = text.encode("utf-8")
        if len(data) > settings.max_file_bytes:
            raise FileTooLargeError(msg.file_too_large("jd.txt", settings.max_file_mb))
        return "jd.txt", data
    if has_file:
        return await _read_upload(jd)
    return None


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
    source: Literal["upload", "test"] | None = Query(default=None),
    idempotency_key: str | None = Form(default=None),
    jd: UploadFile | None = File(default=None),  # noqa: B008
    jd_text: str | None = Form(default=None),
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
        if source == "test":
            if jd is not None or resumes:
                raise MissingDocumentError(msg.test_data_rejects_uploads())
            run_id = create_run_from_test_data(idempotency_key)
        else:
            jd_payload = await _resolve_jd_payload(jd, jd_text)
            resume_payloads = [await _read_upload(upload) for upload in resumes]
            run_id = stage_run_from_uploads(jd_payload, resume_payloads, idempotency_key)

    background_tasks.add_task(process_run, run_id)
    return RunCreateResponse(run_id=run_id, status="queued")


@router.get("/api/runs", response_model=list[RunListItem])
def list_runs(limit: int = Query(default=30, ge=1, le=100)) -> list[RunListItem]:
    return [RunListItem(**item) for item in repository.list_runs(limit)]


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


@router.post("/api/runs/{run_id}/cancel", response_model=RunSummary)
def cancel_run(run_id: str) -> RunSummary:
    run = repository.get_run(run_id)
    if run is None:
        raise RunNotFoundError(msg.run_not_found(run_id))
    if run.status == "cancelled":
        return run
    if run.status not in ("queued", "running"):
        raise RunNotCancellableError(msg.run_not_cancellable(run_id, run.status))
    repository.cancel_run(run_id)
    cancelled = repository.get_run(run_id)
    assert cancelled is not None
    return cancelled


@router.get("/api/runs/{run_id}/events", response_model=list[DecisionEvent])
def get_run_events(run_id: str) -> list[DecisionEvent]:
    if repository.get_run(run_id) is None:
        raise RunNotFoundError(msg.run_not_found(run_id))
    return repository.get_events(run_id)


@router.get("/api/runs/{run_id}/audit-export", response_model=AuditExport)
def get_audit_export(run_id: str) -> AuditExport:
    return assemble_audit_export(run_id)


@router.get("/api/runs/{run_id}/compare", response_model=CandidateComparison)
def compare_candidates(
    run_id: str,
    a: str = Query(...),
    b: str = Query(...),
) -> CandidateComparison:
    if repository.get_run(run_id) is None:
        raise RunNotFoundError(msg.run_not_found(run_id))
    if a == b:
        raise CompareNotComparableError("请选择两位不同的候选人进行对比。")
    return build_comparison(a, b)


@router.get("/api/candidates/{candidate_id}/dossier", response_model=CandidateRunResult)
def get_candidate_dossier(candidate_id: str) -> CandidateRunResult:
    found = repository.get_candidate(candidate_id)
    if found is None:
        raise CandidateNotFoundError(msg.candidate_not_found(candidate_id))
    _run_id, result = found
    return result


def _require_completed(candidate_id: str) -> tuple[str, CandidateRunResult]:
    found = repository.get_candidate(candidate_id)
    if found is None:
        raise CandidateNotFoundError(msg.candidate_not_found(candidate_id))
    _run_id, result = found
    if not isinstance(result.dossier, DecisionDossier):
        raise CandidateNotCompletedError(msg.candidate_not_completed(candidate_id))
    return found


@router.get(
    "/api/candidates/{candidate_id}/interview-script",
    response_model=InterviewScriptResponse,
)
def get_interview_script(candidate_id: str) -> InterviewScriptResponse:
    _run_id, result = _require_completed(candidate_id)
    assert isinstance(result.dossier, DecisionDossier)
    return build_interview_script(result.dossier)


@router.get("/api/candidates/{candidate_id}/notes", response_model=list[CandidateNote])
def get_candidate_notes(candidate_id: str) -> list[CandidateNote]:
    found = repository.get_candidate(candidate_id)
    if found is None:
        raise CandidateNotFoundError(msg.candidate_not_found(candidate_id))
    return repository.get_notes(candidate_id)


@router.post(
    "/api/candidates/{candidate_id}/notes",
    response_model=CandidateNote,
    status_code=201,
)
def create_candidate_note(candidate_id: str, payload: NoteCreateRequest) -> CandidateNote:
    found = repository.get_candidate(candidate_id)
    if found is None:
        raise CandidateNotFoundError(msg.candidate_not_found(candidate_id))
    run_id, _result = found
    note = repository.add_note(candidate_id, run_id, payload.body, payload.author)
    LedgerRecorder(run_id).emit(
        "note_added",
        node_name="human_review",
        candidate_id=candidate_id,
        actor="human",
        metadata={"author": payload.author, "note": msg.note_added_note(payload.author)},
    )
    return note


@router.patch(
    "/api/candidates/{candidate_id}/decision",
    response_model=HumanOverride,
)
def patch_candidate_decision(
    candidate_id: str, payload: DecisionPatchRequest
) -> HumanOverride:
    run_id, result = _require_completed(candidate_id)
    assert isinstance(result.dossier, DecisionDossier)
    previous = (
        result.human_override.recommendation
        if result.human_override
        else result.dossier.score.recommendation
    )
    override = repository.set_candidate_override(
        candidate_id, payload.recommendation, payload.rationale, payload.actor
    )
    LedgerRecorder(run_id).emit(
        "human_override_recorded",
        node_name="human_review",
        candidate_id=candidate_id,
        actor="human",
        metadata={
            "from": previous,
            "to": payload.recommendation,
            "rationale": payload.rationale,
            "note": msg.decision_override_note(previous, payload.recommendation),
        },
    )
    return override


@router.get("/api/evals", response_model=list[EvalResultSummary])
def get_evals() -> list[EvalResultSummary]:
    return repository.get_eval_results()


@router.get("/api/test-data", response_model=TestDataManifest)
def get_test_data_manifest() -> TestDataManifest:
    paths = list_test_data_files()

    def file_ref(path: Path) -> TestDataFile:
        return TestDataFile(
            filename=path.name,
            url=f"/api/test-data/files/{quote(path.name)}",
        )

    return TestDataManifest(jd=file_ref(paths.jd), resumes=[file_ref(p) for p in paths.resumes])


@router.get("/api/test-data/files/{filename}")
def get_test_data_file(filename: str) -> FileResponse:
    path = resolve_test_data_file(filename)
    return FileResponse(path, filename=path.name)


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    settings = get_settings()
    return HealthResponse(
        mode=settings.demo_mode,
        version=app_pkg.__version__,
        langfuse_enabled=settings.langfuse_configured,
        langfuse_verified=langfuse_credentials_verified(settings),
    )
