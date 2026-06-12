"""LangGraph nodes.

Run graph: ingest -> extract_rubric -> Send fan-out per resume -> aggregate.
Candidate subgraph: extract_profile -> score -> interview pack -> assemble,
with conditional edges that short-circuit to `assemble` once a step halts.
A halted candidate becomes a visible `needs_review`/`failed` result; one bad
resume never sinks the run (only an unparseable JD does).
"""

from __future__ import annotations

import uuid

from app.core.errors import (
    DomainError,
    EvidenceMissingError,
    LLMRateLimitError,
    LLMTimeoutError,
    ParseFailedError,
    RepairExhaustedError,
)
from app.core.logging import get_logger
from app.locale import zh_CN as msg
from app.models.contracts import (
    CandidateRunResult,
    DecisionDossier,
    NeedsReviewDossier,
    ValidationSummary,
)
from app.observability.tracing import sanitize_trace_output
from app.storage import repository
from app.workflows import steps
from app.workflows.state import CandidateState, RunGraphState

log = get_logger(__name__)


def new_candidate_id() -> str:
    return uuid.uuid4().hex[:12]


def _trace_url(ctx, trace_id: str | None) -> str | None:
    return ctx.tracer.trace_url(trace_id)


def _validation_pass(summaries: list[ValidationSummary]) -> int:
    if not summaries:
        return 0
    return int(all(s.status == "valid" for s in summaries))


def _max_repair_attempts(summaries: list[ValidationSummary]) -> int:
    return max((s.repair_attempts for s in summaries), default=0)


# ---- run graph nodes -----------------------------------------------------------


def ingest_node(state: RunGraphState) -> dict:
    ctx = state["ctx"]
    jd_doc = state["jd_doc"]
    failed_results: list[CandidateRunResult] = []
    parsed_resumes: list[dict] = []

    with ctx.tracer.span(
        "ingest_files",
        input={
            "jd_status": jd_doc["parse_status"],
            "resume_count": len(state["resume_docs"]),
        },
    ) as ingest_span:
        for doc in [jd_doc, *state["resume_docs"]]:
            ctx.ledger.emit(
                "document_parsed",
                node_name="ingest_files",
                metadata={
                    "document_id": doc["document_id"],
                    "filename": doc["filename"],
                    "source_type": doc["source_type"],
                    "parse_status": doc["parse_status"],
                    "char_count": doc["char_count"],
                    "document_hash": doc["document_hash"],
                },
            )

        if jd_doc["parse_status"] != "parsed":
            raise ParseFailedError(
                msg.jd_parse_failed(jd_doc["filename"], jd_doc["parse_status"])
            )

        for doc in state["resume_docs"]:
            if doc["parse_status"] == "parsed":
                parsed_resumes.append(doc)
            else:
                result = CandidateRunResult(
                    candidate_id=new_candidate_id(),
                    candidate_name=None,
                    status="failed",
                    dossier=None,
                    errors=[msg.resume_not_usable(doc["filename"], doc["parse_status"])],
                )
                repository.save_candidate_result(ctx.run_id, result)
                failed_results.append(result)

        ingest_span.update(
            output={
                "parsed_count": len(parsed_resumes),
                "failed_parse_count": len(failed_results),
            }
        )

    return {"resume_docs": parsed_resumes, "candidate_results": failed_results}


def extract_rubric_node(state: RunGraphState) -> dict:
    rubric, _meta = steps.extract_rubric(state["ctx"], state["jd_doc"])
    return {"rubric": rubric}


def aggregate_node(state: RunGraphState) -> dict:
    results = state.get("candidate_results", [])
    status_breakdown: dict[str, int] = {}
    for result in results:
        status_breakdown[result.status] = status_breakdown.get(result.status, 0) + 1

    with state["ctx"].tracer.span("aggregate_results") as agg_span:
        log.info(
            "run %s aggregated %d candidate results (%s)",
            state["ctx"].run_id,
            len(results),
            ", ".join(sorted({r.status for r in results})) or "none",
        )
        agg_span.update(
            output={
                "total_candidates": len(results),
                "status_breakdown": status_breakdown,
            }
        )
    return {}


# ---- candidate subgraph nodes -----------------------------------------------------


def _halt(state: CandidateState, exc: Exception) -> dict:
    if isinstance(exc, RepairExhaustedError):
        kind, attempts = "needs_review", exc.attempts - 1
    elif isinstance(exc, EvidenceMissingError):
        kind, attempts = "needs_review", state.get("repair_attempts", 0)
    elif isinstance(exc, (LLMTimeoutError, LLMRateLimitError)):
        kind, attempts = "needs_review", state.get("repair_attempts", 0)
    elif isinstance(exc, DomainError):
        kind, attempts = "failed", state.get("repair_attempts", 0)
    else:
        kind, attempts = "failed", state.get("repair_attempts", 0)
        log.exception("unexpected candidate failure (run=%s)", state["ctx"].run_id)
    message = exc.message if isinstance(exc, DomainError) else msg.unexpected_error(str(exc))
    return {
        "halt": True,
        "halt_kind": kind,
        "halt_reason": message,
        "repair_attempts": attempts,
    }


def profile_node(state: CandidateState) -> dict:
    try:
        profile, meta = steps.extract_profile(
            state["ctx"],
            state["candidate_id"],
            state["slug"],
            state["jd_doc"],
            state["resume_doc"],
        )
    except Exception as exc:
        return {**_halt(state, exc), "missing_fields": ["profile", "score", "questions"]}
    return {"profile": profile, "metas": [("profile", meta)]}


def score_node(state: CandidateState) -> dict:
    try:
        analysis, score, breakdown, meta = steps.analyze_and_score(
            state["ctx"],
            state["candidate_id"],
            state["slug"],
            state["rubric"],
            state["profile"],
            state["jd_doc"],
            state["resume_doc"],
        )
    except Exception as exc:
        return {**_halt(state, exc), "missing_fields": ["score", "questions"]}
    return {
        "analysis": analysis,
        "score": score,
        "breakdown": breakdown,
        "metas": [*state.get("metas", []), ("score", meta)],
    }


def questions_node(state: CandidateState) -> dict:
    try:
        questions, follow_ups, meta = steps.generate_pack(
            state["ctx"],
            state["candidate_id"],
            state["slug"],
            state["rubric"],
            state["profile"],
            state["analysis"],
            state["jd_doc"],
            state["resume_doc"],
        )
    except Exception as exc:
        return {**_halt(state, exc), "missing_fields": ["questions"]}
    return {
        "questions": questions,
        "follow_ups": follow_ups,
        "metas": [*state.get("metas", []), ("interview_pack", meta)],
    }


def _summaries_from_metas(state: CandidateState) -> list[ValidationSummary]:
    schema_names = {
        "profile": "CandidateProfileDraft",
        "score": "ScoreAnalysisDraft",
        "interview_pack": "InterviewPackDraft",
    }
    node_names = {
        "profile": "extract_candidate_profile",
        "score": "score_candidate",
        "interview_pack": "generate_interview_pack",
    }
    return [
        ValidationSummary(
            schema_name=schema_names[kind],
            node_name=node_names[kind],
            candidate_id=state["candidate_id"],
            status="repaired" if meta.repaired else "valid",
            error_count=len(meta.errors),
            repair_attempts=meta.attempts - 1,
            messages=meta.errors[:10],
        )
        for kind, meta in state.get("metas", [])
    ]


def _assemble_output(state: CandidateState, result: CandidateRunResult) -> dict:
    if not state.get("halt"):
        dossier = result.dossier
        assert dossier is not None
        return {
            "status": result.status,
            "overall_score": dossier.score.overall_score,
            "recommendation": dossier.score.recommendation,
        }
    return {
        "status": result.status,
        "halt_kind": state.get("halt_kind"),
        "halt_reason": sanitize_trace_output(state.get("halt_reason", "")),
    }


def assemble_node(state: CandidateState) -> dict:
    ctx = state["ctx"]
    candidate_id = state["candidate_id"]
    summaries = _summaries_from_metas(state)
    candidate_trace_id = state.get("candidate_trace_id")
    trace_url = _trace_url(ctx, candidate_trace_id)

    with ctx.tracer.span(
        "assemble_dossier",
        {"run_id": ctx.run_id, "candidate_id": candidate_id, "slug": state["slug"]},
    ) as assemble_span:
        if not state.get("halt"):
            dossier = DecisionDossier(
                candidate_id=candidate_id,
                candidate_name=state["profile"].candidate_name,
                candidate_profile=state["profile"],
                score=state["score"],
                questions=state["questions"],
                follow_ups=state["follow_ups"],
                validation_summaries=summaries,
                trace_url=trace_url,
            )
            result = CandidateRunResult(
                candidate_id=candidate_id,
                candidate_name=dossier.candidate_name,
                status="completed",
                dossier=dossier,
            )
            ctx.ledger.emit(
                "dossier_completed",
                node_name="assemble_dossier",
                candidate_id=candidate_id,
                metadata={
                    "status": "completed",
                    "overall_score": dossier.score.overall_score,
                    "recommendation": dossier.score.recommendation,
                    "ledger_note": msg.dossier_assembled_note(),
                },
            )
            if ctx.mode == "replay" and state["slug"] in ctx.red_team_slugs:
                ctx.ledger.emit(
                    "human_override_recorded",
                    node_name="assemble_dossier",
                    candidate_id=candidate_id,
                    actor="human",
                    metadata={
                        "demo": True,
                        "note": msg.demo_override_note(),
                        "tags": ["red_team"],
                    },
                )
        elif state.get("halt_kind") == "needs_review":
            profile = state.get("profile")
            analysis = state.get("analysis")
            dossier = NeedsReviewDossier(
                candidate_id=candidate_id,
                candidate_name=profile.candidate_name if profile else None,
                partial_profile=profile,
                partial_sub_scores=(
                    steps.sub_scores_from_analysis(analysis) if analysis else None
                ),
                validation_summaries=summaries,
                repair_attempt_count=state.get("repair_attempts", 0),
                missing_fields=state.get("missing_fields", []),
                reviewer_message=state.get("halt_reason", msg.output_failed_validation()),
                trace_url=trace_url,
            )
            result = CandidateRunResult(
                candidate_id=candidate_id,
                candidate_name=dossier.candidate_name,
                status="needs_review",
                dossier=dossier,
                errors=[dossier.reviewer_message],
            )
            ctx.ledger.emit(
                "dossier_completed",
                node_name="assemble_dossier",
                candidate_id=candidate_id,
                metadata={"status": "needs_review", "reason": dossier.reviewer_message},
            )
        else:
            result = CandidateRunResult(
                candidate_id=candidate_id,
                candidate_name=(
                    state["profile"].candidate_name if state.get("profile") else None
                ),
                status="failed",
                dossier=None,
                errors=[state.get("halt_reason", msg.candidate_processing_failed())],
            )

        assemble_span.update(output=_assemble_output(state, result))

        ctx.tracer.score(
            "validation_pass",
            _validation_pass(summaries),
            trace_id=candidate_trace_id,
        )
        ctx.tracer.score(
            "repair_attempts",
            _max_repair_attempts(summaries),
            trace_id=candidate_trace_id,
        )
        if state["slug"] in ctx.red_team_slugs:
            ctx.tracer.score(
                "red_team_detected",
                1,
                trace_id=candidate_trace_id,
            )
        if not state.get("halt") and result.dossier is not None:
            ctx.tracer.score(
                "overall_score",
                result.dossier.score.overall_score,
                trace_id=candidate_trace_id,
            )

    repository.save_candidate_result(ctx.run_id, result)
    return {"result": result}
