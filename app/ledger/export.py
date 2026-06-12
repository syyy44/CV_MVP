"""Audit export assembly (`audit-export.v1`).

Redaction rules from the Upload & Privacy Contract: no raw document text, no
API keys, no provider request headers. Documents are represented by hash,
parse metadata, and a short preview; evidence snippets are quotes the system
already validated against source text.
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.errors import (
    AuditExportIncompleteError,
    RunNotExportableError,
    RunNotFoundError,
)
from app.core.redaction import scrub_pii_model
from app.locale import zh_CN as msg
from app.models.contracts import DecisionDossier, NeedsReviewDossier
from app.models.events import DecisionEvent
from app.models.export import (
    AuditExport,
    EvalResultSummary,
    RepairAttemptSummary,
    TraceRef,
)
from app.storage import repository


def _repair_attempts_from_events(events: list[DecisionEvent]) -> list[RepairAttemptSummary]:
    outcome_by_type = {
        "repair_attempted": "attempted",
        "repair_succeeded": "repaired",
        "repair_failed": "failed",
    }
    summaries = []
    for event in events:
        if event.event_type not in outcome_by_type:
            continue
        errors = event.metadata.get("errors", [])
        summaries.append(
            RepairAttemptSummary(
                candidate_id=event.candidate_id,
                node_name=event.node_name,
                schema_name=event.schema_name,
                attempt=event.repair_attempt or 0,
                outcome=outcome_by_type[event.event_type],
                error_excerpt="; ".join(str(e) for e in errors)[:300],
            )
        )
    return summaries


def _trace_refs_from_events(events: list[DecisionEvent]) -> list[TraceRef]:
    refs: dict[str, TraceRef] = {}
    for event in events:
        trace_id = event.metadata.get("trace_id")
        if trace_id and str(trace_id) not in refs:
            refs[str(trace_id)] = TraceRef(
                candidate_id=event.candidate_id,
                node_name=event.node_name,
                trace_id=str(trace_id),
                url=event.metadata.get("trace_url"),
            )
    return list(refs.values())


def assemble_audit_export(run_id: str) -> AuditExport:
    run = repository.get_run(run_id)
    if run is None:
        raise RunNotFoundError(msg.export_run_not_found(run_id))
    if run.status in ("queued", "running"):
        raise RunNotExportableError(msg.export_run_still_running(run_id, run.status))
    if run.status == "failed":
        raise RunNotExportableError(msg.export_run_failed(run_id))

    events = repository.get_events(run_id)
    if not events:
        raise AuditExportIncompleteError(msg.export_no_events(run_id))

    results = repository.get_candidate_results(run_id)
    dossiers = []
    for result in results:
        if isinstance(result.dossier, DecisionDossier):
            dossiers.append(scrub_pii_model(result.dossier, DecisionDossier))
        elif isinstance(result.dossier, NeedsReviewDossier):
            dossiers.append(scrub_pii_model(result.dossier, NeedsReviewDossier))
    if not dossiers:
        raise AuditExportIncompleteError(msg.export_no_dossiers(run_id))

    warnings: list[str] = []
    for result in results:
        if result.status == "needs_review":
            warnings.append(
                msg.export_candidate_needs_review(
                    result.candidate_id, "; ".join(result.errors)[:200]
                )
            )
        elif result.status == "failed":
            warnings.append(
                msg.export_candidate_failed(result.candidate_id, "; ".join(result.errors)[:200])
            )

    run_eval_results: list[EvalResultSummary] = repository.get_eval_results(
        run_id, include_suite=False
    )
    suite_eval_summary: list[EvalResultSummary] = repository.get_suite_eval_results()
    eval_results = [*run_eval_results, *suite_eval_summary]

    return AuditExport(
        generated_at=datetime.now(UTC),
        run=run,
        documents=repository.document_summaries(run_id),
        candidate_dossiers=dossiers,
        decision_events=events,
        validation_summaries=repository.get_validation_summaries(run_id),
        repair_attempts=_repair_attempts_from_events(events),
        run_eval_results=run_eval_results,
        suite_eval_summary=suite_eval_summary,
        eval_results=eval_results,
        trace_refs=_trace_refs_from_events(events),
        export_status="complete" if run.status == "completed" else "partial",
        warnings=warnings,
    )
