"""Run orchestration: creation, background execution, status derivation."""

from __future__ import annotations

import json
import time
import uuid

from app.core.config import get_settings
from app.core.errors import (
    ConfigurationError,
    DomainError,
    MissingDocumentError,
    ReplayFixtureMissingError,
    RunNotFoundError,
    TooManyResumesError,
)
from app.core.logging import get_logger
from app.ledger.events import LedgerRecorder
from app.llm.client import LiveLLMProvider
from app.locale import zh_CN as msg
from app.models.contracts import CandidateRunResult
from app.observability.tracing import Tracer
from app.replay.provider import ReplayProvider
from app.storage import repository
from app.workflows.context import MetricsCollector, WorkflowContext
from app.workflows.graph import build_run_graph
from app.workflows.parsing import ParsedDocument, parse_upload

log = get_logger(__name__)


def _new_run_id() -> str:
    return uuid.uuid4().hex[:12]


def _new_document_id() -> str:
    return uuid.uuid4().hex[:12]


def store_parsed_document(run_id: str, source_type: str, parsed: ParsedDocument) -> None:
    repository.add_document(
        {
            "document_id": _new_document_id(),
            "run_id": run_id,
            "source_type": source_type,
            "filename": parsed.filename,
            "slug": parsed.slug,
            "parse_status": parsed.parse_status,
            "document_hash": parsed.document_hash,
            "char_count": parsed.char_count,
            "text": parsed.text,
            "page_texts": parsed.page_texts or ([parsed.text] if parsed.text else []),
        }
    )


def load_demo_manifest() -> dict:
    settings = get_settings()
    manifest_path = settings.fixtures_dir / "demo" / "manifest.json"
    if not manifest_path.exists():
        raise ReplayFixtureMissingError(msg.demo_manifest_not_found(str(manifest_path)))
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def _ingest_tracer() -> Tracer:
    return Tracer(get_settings())


def create_run_from_fixtures(idempotency_key: str | None) -> str:
    settings = get_settings()
    manifest = load_demo_manifest()
    demo_dir = settings.fixtures_dir / "demo"

    run_id = _new_run_id()
    repository.create_run(run_id, "replay", idempotency_key)
    tracer = _ingest_tracer()

    jd_path = demo_dir / manifest["jd"]
    if not jd_path.exists():
        raise ReplayFixtureMissingError(msg.demo_jd_fixture_missing(str(jd_path)))
    store_parsed_document(
        run_id, "jd", parse_upload(jd_path.name, jd_path.read_bytes(), tracer=tracer)
    )

    for rel in manifest["resumes"]:
        resume_path = demo_dir / rel
        if not resume_path.exists():
            raise ReplayFixtureMissingError(msg.demo_resume_fixture_missing(str(resume_path)))
        parsed = parse_upload(resume_path.name, resume_path.read_bytes(), tracer=tracer)
        store_parsed_document(run_id, "resume", parsed)

    tracer.flush()
    return run_id


def create_run_from_uploads(
    jd: tuple[str, bytes] | None,
    resumes: list[tuple[str, bytes]],
    idempotency_key: str | None,
) -> str:
    settings = get_settings()
    if not settings.llm_api_key:
        raise ConfigurationError(msg.live_requires_api_key())
    if jd is None:
        raise MissingDocumentError(msg.jd_required())
    if not resumes:
        raise MissingDocumentError(msg.resume_required())
    if len(resumes) > settings.max_resumes:
        raise TooManyResumesError(msg.too_many_resumes(settings.max_resumes, len(resumes)))

    run_id = _new_run_id()
    repository.create_run(run_id, "live", idempotency_key)
    tracer = _ingest_tracer()
    store_parsed_document(run_id, "jd", parse_upload(jd[0], jd[1], tracer=tracer))
    for filename, data in resumes:
        store_parsed_document(run_id, "resume", parse_upload(filename, data, tracer=tracer))
    tracer.flush()
    return run_id


def derive_run_status(results: list[CandidateRunResult]) -> str:
    if not results:
        return "failed"
    statuses = {r.status for r in results}
    if statuses == {"completed"}:
        return "completed"
    if statuses == {"failed"}:
        return "failed"
    return "needs_review"


def execute_run(run_id: str, *, eval_suite: str | None = None) -> None:
    settings = get_settings()
    run = repository.get_run(run_id)
    if run is None:
        raise RunNotFoundError(msg.run_not_found(run_id))

    docs = repository.get_documents(run_id)
    jd_docs = [d for d in docs if d["source_type"] == "jd"]
    resume_docs = [d for d in docs if d["source_type"] == "resume"]

    if run.mode in ("replay", "eval"):
        provider = ReplayProvider(settings)
        red_team = frozenset(load_demo_manifest().get("red_team_slugs", []))
    else:
        provider = LiveLLMProvider(settings)
        red_team = frozenset()

    tracer = Tracer(settings)
    ctx = WorkflowContext(
        run_id=run_id,
        mode=run.mode,
        settings=settings,
        provider=provider,
        ledger=LedgerRecorder(run_id),
        tracer=tracer,
        metrics=MetricsCollector(),
        red_team_slugs=red_team,
    )

    repository.mark_run_started(run_id)
    started = time.monotonic()
    try:
        if not jd_docs:
            raise MissingDocumentError(msg.run_has_no_jd())
        provider_name = getattr(provider, "name", "unknown")
        with tracer.run(
            run_id,
            run.mode,
            resume_count=len(resume_docs),
            provider=provider_name,
            model_name=settings.model_name,
            eval_suite=eval_suite,
        ) as run_span:
            output = build_run_graph().invoke(
                {
                    "ctx": ctx,
                    "jd_doc": jd_docs[0],
                    "resume_docs": resume_docs,
                    "candidate_results": [],
                }
            )
            statuses = sorted({r.status for r in output.get("candidate_results", [])})
            metrics = ctx.metrics.to_run_metrics(settings, time.monotonic() - started)
            run_span.update(
                output={
                    "candidate_count": len(output.get("candidate_results", [])),
                    "statuses": statuses,
                    "llm_calls": metrics.llm_calls,
                    "input_tokens": metrics.input_tokens,
                    "output_tokens": metrics.output_tokens,
                    "duration_s": metrics.duration_s,
                }
            )
        status = derive_run_status(output.get("candidate_results", []))
        repository.mark_run_finished(run_id, status)
    except DomainError as exc:
        log.error("run %s failed: %s", run_id, exc.message)
        repository.mark_run_finished(run_id, "failed", error=exc.message)
    except Exception as exc:
        log.exception("run %s crashed", run_id)
        repository.mark_run_finished(run_id, "failed", error=msg.unexpected_error(str(exc)))
    finally:
        duration = time.monotonic() - started
        repository.set_run_metrics(run_id, ctx.metrics.to_run_metrics(settings, duration))
        tracer.flush()
