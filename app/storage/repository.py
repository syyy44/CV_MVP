from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, datetime

from app.models.contracts import (
    CandidateNote,
    CandidateRunResult,
    DecisionDossier,
    DocumentSummary,
    EvidenceContextLine,
    EvidenceSpan,
    HumanOverride,
    NeedsReviewDossier,
    Recommendation,
    RunMetrics,
    RunSummary,
    ValidationSummary,
)
from app.models.events import DecisionEvent
from app.models.export import EvalResultSummary
from app.storage.db import connect
from app.workflows import interview_script as script_lib
from app.workflows.evidence import build_context_lines, number_lines
from app.workflows.grounding import relevance
from app.workflows.requirement_refs import build_jd_evidence_refs


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _parse_dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


# ---- runs ---------------------------------------------------------------------


def create_run(run_id: str, mode: str, idempotency_key: str | None) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO runs (run_id, status, mode, idempotency_key, created_at)"
            " VALUES (?, 'queued', ?, ?, ?)",
            (run_id, mode, idempotency_key, _now()),
        )


def find_run_by_idempotency_key(key: str) -> str | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT run_id FROM runs WHERE idempotency_key = ?", (key,)
        ).fetchone()
    return row["run_id"] if row else None


def get_run(run_id: str) -> RunSummary | None:
    with connect() as conn:
        row = conn.execute("SELECT * FROM runs WHERE run_id = ?", (run_id,)).fetchone()
    if not row:
        return None
    return _row_to_run_summary(row)


def _row_to_run_summary(row: sqlite3.Row) -> RunSummary:
    metrics = RunMetrics(**json.loads(row["metrics_json"])) if row["metrics_json"] else None
    return RunSummary(
        run_id=row["run_id"],
        status=row["status"],
        mode=row["mode"],
        created_at=_parse_dt(row["created_at"]),
        started_at=_parse_dt(row["started_at"]),
        finished_at=_parse_dt(row["finished_at"]),
        error=row["error"],
        metrics=metrics,
    )


def list_runs(limit: int = 30) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            """
            SELECT
                r.*,
                (
                    SELECT filename FROM documents
                    WHERE run_id = r.run_id AND source_type = 'jd'
                    LIMIT 1
                ) AS jd_filename,
                (
                    SELECT COUNT(*) FROM documents
                    WHERE run_id = r.run_id AND source_type = 'resume'
                ) AS resume_count,
                (
                    SELECT COUNT(*) FROM candidate_results
                    WHERE run_id = r.run_id
                ) AS candidate_count,
                (
                    SELECT candidate_name FROM candidate_results
                    WHERE run_id = r.run_id AND sort_score >= 0
                    ORDER BY sort_score DESC
                    LIMIT 1
                ) AS top_candidate_name,
                (
                    SELECT sort_score FROM candidate_results
                    WHERE run_id = r.run_id AND sort_score >= 0
                    ORDER BY sort_score DESC
                    LIMIT 1
                ) AS top_score
            FROM runs r
            ORDER BY r.created_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [
        {
            "run": _row_to_run_summary(row),
            "jd_filename": row["jd_filename"],
            "resume_count": row["resume_count"],
            "candidate_count": row["candidate_count"],
            "top_candidate_name": row["top_candidate_name"],
            "top_score": row["top_score"],
        }
        for row in rows
    ]


def mark_run_started(run_id: str) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE runs SET status = 'running', started_at = ? WHERE run_id = ?",
            (_now(), run_id),
        )


def mark_run_finished(run_id: str, status: str, error: str | None = None) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE runs SET status = ?, finished_at = ?, error = ? WHERE run_id = ?",
            (status, _now(), error, run_id),
        )


def set_run_metrics(run_id: str, metrics: RunMetrics) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE runs SET metrics_json = ? WHERE run_id = ?",
            (json.dumps(metrics.model_dump()), run_id),
        )


# ---- documents -----------------------------------------------------------------


def add_document(doc: dict) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO documents (document_id, run_id, source_type, filename, slug,"
            " parse_status, document_hash, char_count, raw_text, page_texts_json,"
            " source_bytes, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                doc["document_id"],
                doc["run_id"],
                doc["source_type"],
                doc["filename"],
                doc["slug"],
                doc["parse_status"],
                doc.get("document_hash"),
                doc.get("char_count", 0),
                doc.get("text", ""),
                json.dumps(doc.get("page_texts", [])),
                doc.get("source_bytes"),
                _now(),
            ),
        )


def has_pending_documents(run_id: str) -> bool:
    with connect() as conn:
        row = conn.execute(
            "SELECT 1 FROM documents WHERE run_id = ? AND parse_status = 'pending_ingest'"
            " LIMIT 1",
            (run_id,),
        ).fetchone()
    return row is not None


def get_document_source_bytes(document_id: str) -> bytes | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT source_bytes FROM documents WHERE document_id = ?",
            (document_id,),
        ).fetchone()
    if row is None or row["source_bytes"] is None:
        return None
    return bytes(row["source_bytes"])


def finalize_document(document_id: str, parsed: dict) -> None:
    with connect() as conn:
        conn.execute(
            "UPDATE documents SET slug = ?, parse_status = ?, document_hash = ?,"
            " char_count = ?, raw_text = ?, page_texts_json = ?, source_bytes = NULL"
            " WHERE document_id = ?",
            (
                parsed["slug"],
                parsed["parse_status"],
                parsed.get("document_hash"),
                parsed.get("char_count", 0),
                parsed.get("text", ""),
                json.dumps(parsed.get("page_texts", [])),
                document_id,
            ),
        )


def get_documents(run_id: str) -> list[dict]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM documents WHERE run_id = ? ORDER BY created_at", (run_id,)
        ).fetchall()
    return [
        {
            "document_id": r["document_id"],
            "run_id": r["run_id"],
            "source_type": r["source_type"],
            "filename": r["filename"],
            "slug": r["slug"],
            "parse_status": r["parse_status"],
            "document_hash": r["document_hash"],
            "char_count": r["char_count"],
            "text": r["raw_text"],
            "page_texts": json.loads(r["page_texts_json"]),
        }
        for r in rows
    ]


_EMAIL_RE = re.compile(r"\S+@\S+")


def document_summaries(run_id: str) -> list[DocumentSummary]:
    # Raw text never leaves storage through this path: preview is capped, email
    # addresses are scrubbed, and the AuditExport contract has no raw-text
    # field (Upload & Privacy Contract).
    return [
        DocumentSummary(
            document_id=d["document_id"],
            run_id=d["run_id"],
            source_type=d["source_type"],
            filename=d["filename"],
            parse_status=d["parse_status"],
            document_hash=d["document_hash"],
            char_count=d["char_count"],
            preview=_EMAIL_RE.sub("[email-redacted]", " ".join(d["text"].split()))[:160],
        )
        for d in get_documents(run_id)
    ]


# ---- candidate results -----------------------------------------------------------


def save_candidate_result(run_id: str, result: CandidateRunResult) -> None:
    sort_score = -1
    if isinstance(result.dossier, DecisionDossier):
        sort_score = result.dossier.score.overall_score
    with connect() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO candidate_results"
            " (candidate_id, run_id, candidate_name, status, dossier_json, errors_json,"
            " sort_score, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                result.candidate_id,
                run_id,
                result.candidate_name,
                result.status,
                json.dumps(result.dossier.model_dump(mode="json")) if result.dossier else None,
                json.dumps(result.errors),
                sort_score,
                _now(),
            ),
        )


def _override_from_row(row) -> HumanOverride | None:
    keys = row.keys()
    if "override_recommendation" not in keys or not row["override_recommendation"]:
        return None
    return HumanOverride(
        recommendation=row["override_recommendation"],
        rationale=row["override_rationale"] or "",
        actor=row["override_actor"] or "human",
        at=_parse_dt(row["override_at"]) or datetime.now(UTC),
    )


def _enrich_summary(result: CandidateRunResult) -> CandidateRunResult:
    """Populate board-summary fields (§6.3) for completed candidates."""
    if isinstance(result.dossier, DecisionDossier):
        dossier = result.dossier
        result.decision_summary = script_lib.decision_summary(dossier)
        result.risk_count = len(dossier.score.risk_flags)
        result.verification_count = script_lib.verification_count(dossier)
        result.confidence_band = script_lib.confidence_band(dossier.score.confidence)
    return result


def _row_to_result(row) -> CandidateRunResult:
    dossier = None
    if row["dossier_json"]:
        payload = json.loads(row["dossier_json"])
        if payload.get("status") == "completed":
            dossier = DecisionDossier.model_validate(payload)
        else:
            dossier = NeedsReviewDossier.model_validate(payload)
    result = CandidateRunResult(
        candidate_id=row["candidate_id"],
        candidate_name=row["candidate_name"],
        status=row["status"],
        dossier=dossier,
        errors=json.loads(row["errors_json"]),
        human_override=_override_from_row(row),
    )
    return _enrich_summary(result)


def _context_lines_for_span(span: EvidenceSpan, doc: dict) -> list[EvidenceContextLine]:
    if span.line_no is None:
        return []
    numbered = number_lines(doc.get("text", ""))
    return build_context_lines(numbered, span.line_no)


def _iter_evidence_spans(result: CandidateRunResult):
    dossier = result.dossier
    if not isinstance(dossier, DecisionDossier):
        return
    yield from dossier.score.evidence_refs
    for req in dossier.score.requirement_results:
        yield from req.jd_evidence_refs
    for claim in dossier.score.claim_verifications:
        yield from claim.evidence_refs
    for follow_up in dossier.follow_ups:
        yield from follow_up.evidence_refs


def _enrich_evidence_context(result: CandidateRunResult, documents_by_id: dict[str, dict]) -> None:
    for span in _iter_evidence_spans(result) or []:
        if span.context_lines:
            continue
        doc = documents_by_id.get(span.document_id)
        if doc is None:
            continue
        span.context_lines = _context_lines_for_span(span, doc)


def _dedupe_spans_by_line(spans: list[EvidenceSpan]) -> list[EvidenceSpan]:
    seen: set[tuple[str, int | None, str]] = set()
    unique: list[EvidenceSpan] = []
    for span in spans:
        key = (span.document_id, span.line_no, span.snippet)
        if key in seen:
            continue
        seen.add(key)
        unique.append(span)
    return unique


def _rank_jd_refs_for_requirement(
    spans: list[EvidenceSpan], requirement_text: str, *, limit: int = 2
) -> list[EvidenceSpan]:
    return sorted(
        spans,
        key=lambda span: (-relevance(requirement_text, span.snippet), span.line_no or 0),
    )[:limit]


def _shared_jd_refs_by_requirement(
    results: list[CandidateRunResult],
) -> dict[str, list[EvidenceSpan]]:
    refs_by_requirement: dict[str, list[EvidenceSpan]] = {}
    for result in results:
        dossier = result.dossier
        if not isinstance(dossier, DecisionDossier):
            continue
        for span in dossier.score.evidence_refs:
            if span.source_type != "jd" or not span.requirement_id:
                continue
            refs_by_requirement.setdefault(span.requirement_id, []).append(span)
    return {
        requirement_id: _dedupe_spans_by_line(spans)
        for requirement_id, spans in refs_by_requirement.items()
    }


def _enrich_requirement_jd_refs(
    results: list[CandidateRunResult],
    documents_by_id: dict[str, dict],
) -> None:
    jd_doc = next((doc for doc in documents_by_id.values() if doc["source_type"] == "jd"), None)
    shared_refs = _shared_jd_refs_by_requirement(results)
    for result in results:
        dossier = result.dossier
        if not isinstance(dossier, DecisionDossier):
            continue
        for req in dossier.score.requirement_results:
            if req.jd_evidence_refs:
                continue
            req.jd_evidence_refs = _rank_jd_refs_for_requirement(
                shared_refs.get(req.requirement_id, []),
                req.display_label,
            )
            if not req.jd_evidence_refs and jd_doc is not None:
                req.jd_evidence_refs = build_jd_evidence_refs(
                    req.requirement_id,
                    req.display_label,
                    jd_doc,
                )
    for result in results:
        _enrich_evidence_context(result, documents_by_id)


def get_candidate_results(run_id: str) -> list[CandidateRunResult]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM candidate_results WHERE run_id = ? ORDER BY sort_score DESC",
            (run_id,),
        ).fetchall()
    documents_by_id = {doc["document_id"]: doc for doc in get_documents(run_id)}
    results = [_row_to_result(r) for r in rows]
    _enrich_requirement_jd_refs(results, documents_by_id)
    return results


def get_candidate(candidate_id: str) -> tuple[str, CandidateRunResult] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM candidate_results WHERE candidate_id = ?", (candidate_id,)
        ).fetchone()
    if not row:
        return None
    result = _row_to_result(row)
    documents_by_id = {doc["document_id"]: doc for doc in get_documents(row["run_id"])}
    _enrich_requirement_jd_refs([result], documents_by_id)
    return row["run_id"], result


def set_candidate_override(
    candidate_id: str,
    recommendation: Recommendation,
    rationale: str,
    actor: str = "human",
) -> HumanOverride:
    override = HumanOverride(
        recommendation=recommendation,
        rationale=rationale,
        actor=actor,
        at=datetime.now(UTC),
    )
    with connect() as conn:
        conn.execute(
            "UPDATE candidate_results SET override_recommendation = ?,"
            " override_rationale = ?, override_actor = ?, override_at = ?"
            " WHERE candidate_id = ?",
            (
                override.recommendation,
                override.rationale,
                override.actor,
                override.at.isoformat(),
                candidate_id,
            ),
        )
    return override


# ---- candidate notes -------------------------------------------------------------


def add_note(candidate_id: str, run_id: str, body: str, author: str) -> CandidateNote:
    created_at = _now()
    with connect() as conn:
        cursor = conn.execute(
            "INSERT INTO candidate_notes (candidate_id, run_id, body, author, created_at)"
            " VALUES (?, ?, ?, ?, ?)",
            (candidate_id, run_id, body, author, created_at),
        )
        note_id = cursor.lastrowid
    return CandidateNote(
        id=note_id,
        candidate_id=candidate_id,
        run_id=run_id,
        body=body,
        author=author,
        created_at=_parse_dt(created_at),
    )


def get_notes(candidate_id: str) -> list[CandidateNote]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM candidate_notes WHERE candidate_id = ? ORDER BY id",
            (candidate_id,),
        ).fetchall()
    return [
        CandidateNote(
            id=r["id"],
            candidate_id=r["candidate_id"],
            run_id=r["run_id"],
            body=r["body"],
            author=r["author"],
            created_at=_parse_dt(r["created_at"]),
        )
        for r in rows
    ]


# ---- decision events ---------------------------------------------------------------


def add_event(event: DecisionEvent) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO decision_events (run_id, candidate_id, event_type, ts, actor,"
            " node_name, model, prompt_name, prompt_version, input_hash, output_hash,"
            " schema_name, validation_status, repair_attempt, latency_ms, input_tokens,"
            " output_tokens, metadata_json)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                event.run_id,
                event.candidate_id,
                event.event_type,
                event.timestamp.isoformat(),
                event.actor,
                event.node_name,
                event.model,
                event.prompt_name,
                event.prompt_version,
                event.input_hash,
                event.output_hash,
                event.schema_name,
                event.validation_status,
                event.repair_attempt,
                event.latency_ms,
                event.input_tokens,
                event.output_tokens,
                json.dumps(event.metadata),
            ),
        )


def get_events(run_id: str) -> list[DecisionEvent]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM decision_events WHERE run_id = ? ORDER BY id", (run_id,)
        ).fetchall()
    return [
        DecisionEvent(
            id=r["id"],
            run_id=r["run_id"],
            candidate_id=r["candidate_id"],
            event_type=r["event_type"],
            timestamp=_parse_dt(r["ts"]),
            actor=r["actor"],
            node_name=r["node_name"],
            model=r["model"],
            prompt_name=r["prompt_name"],
            prompt_version=r["prompt_version"],
            input_hash=r["input_hash"],
            output_hash=r["output_hash"],
            schema_name=r["schema_name"],
            validation_status=r["validation_status"],
            repair_attempt=r["repair_attempt"],
            latency_ms=r["latency_ms"],
            input_tokens=r["input_tokens"],
            output_tokens=r["output_tokens"],
            metadata=json.loads(r["metadata_json"]),
        )
        for r in rows
    ]


# ---- validation summaries -----------------------------------------------------------


def add_validation_summary(run_id: str, summary: ValidationSummary) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO validation_summaries (run_id, candidate_id, node_name, schema_name,"
            " status, error_count, repair_attempts, messages_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                summary.candidate_id,
                summary.node_name,
                summary.schema_name,
                summary.status,
                summary.error_count,
                summary.repair_attempts,
                json.dumps(summary.messages),
                _now(),
            ),
        )


def get_validation_summaries(run_id: str) -> list[ValidationSummary]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM validation_summaries WHERE run_id = ? ORDER BY id", (run_id,)
        ).fetchall()
    return [
        ValidationSummary(
            schema_name=r["schema_name"],
            node_name=r["node_name"],
            candidate_id=r["candidate_id"],
            status=r["status"],
            error_count=r["error_count"],
            repair_attempts=r["repair_attempts"],
            messages=json.loads(r["messages_json"]),
        )
        for r in rows
    ]


# ---- eval results ---------------------------------------------------------------------


def add_eval_result(
    name: str,
    status: str,
    value: float | None = None,
    details: str = "",
    run_id: str | None = None,
) -> None:
    with connect() as conn:
        conn.execute(
            "INSERT INTO eval_results (run_id, name, status, value, details, ts)"
            " VALUES (?, ?, ?, ?, ?, ?)",
            (run_id, name, status, value, details, _now()),
        )


def get_eval_results(
    run_id: str | None = None, *, include_suite: bool = True
) -> list[EvalResultSummary]:
    with connect() as conn:
        if run_id:
            if include_suite:
                rows = conn.execute(
                    "SELECT * FROM eval_results WHERE run_id = ? OR run_id IS NULL ORDER BY id",
                    (run_id,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM eval_results WHERE run_id = ? ORDER BY id",
                    (run_id,),
                ).fetchall()
        else:
            if include_suite:
                rows = conn.execute("SELECT * FROM eval_results ORDER BY id").fetchall()
            else:
                rows = []
    return [
        EvalResultSummary(
            run_id=r["run_id"],
            scope="run" if r["run_id"] else "suite",
            name=r["name"],
            status=r["status"],
            value=r["value"],
            details=r["details"],
            ts=_parse_dt(r["ts"]),
        )
        for r in rows
    ]


def get_suite_eval_results() -> list[EvalResultSummary]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM eval_results WHERE run_id IS NULL ORDER BY id"
        ).fetchall()
    return [
        EvalResultSummary(
            run_id=None,
            scope="suite",
            name=r["name"],
            status=r["status"],
            value=r["value"],
            details=r["details"],
            ts=_parse_dt(r["ts"]),
        )
        for r in rows
    ]


def clear_eval_results() -> None:
    with connect() as conn:
        conn.execute("DELETE FROM eval_results")
