from __future__ import annotations

import json
import re
from datetime import UTC, datetime

from app.models.contracts import (
    CandidateRunResult,
    DecisionDossier,
    DocumentSummary,
    NeedsReviewDossier,
    RunMetrics,
    RunSummary,
    ValidationSummary,
)
from app.models.events import DecisionEvent
from app.models.export import EvalResultSummary
from app.storage.db import connect


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
            " parse_status, document_hash, char_count, raw_text, page_texts_json, created_at)"
            " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
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
                _now(),
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


def _row_to_result(row) -> CandidateRunResult:
    dossier = None
    if row["dossier_json"]:
        payload = json.loads(row["dossier_json"])
        if payload.get("status") == "completed":
            dossier = DecisionDossier.model_validate(payload)
        else:
            dossier = NeedsReviewDossier.model_validate(payload)
    return CandidateRunResult(
        candidate_id=row["candidate_id"],
        candidate_name=row["candidate_name"],
        status=row["status"],
        dossier=dossier,
        errors=json.loads(row["errors_json"]),
    )


def get_candidate_results(run_id: str) -> list[CandidateRunResult]:
    with connect() as conn:
        rows = conn.execute(
            "SELECT * FROM candidate_results WHERE run_id = ? ORDER BY sort_score DESC",
            (run_id,),
        ).fetchall()
    return [_row_to_result(r) for r in rows]


def get_candidate(candidate_id: str) -> tuple[str, CandidateRunResult] | None:
    with connect() as conn:
        row = conn.execute(
            "SELECT * FROM candidate_results WHERE candidate_id = ?", (candidate_id,)
        ).fetchone()
    if not row:
        return None
    return row["run_id"], _row_to_result(row)


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
