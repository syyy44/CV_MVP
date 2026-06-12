from __future__ import annotations

from datetime import UTC, datetime

from app.core.logging import get_logger
from app.models.contracts import ValidationSummary
from app.models.events import DecisionEvent, EventType
from app.storage import repository

log = get_logger(__name__)


class LedgerRecorder:
    """Product-facing decision provenance writer.

    Writes to SQLite regardless of Langfuse availability (local fallback is a
    first-class mode, not degraded mode).
    """

    def __init__(self, run_id: str):
        self.run_id = run_id

    def emit(
        self,
        event_type: EventType,
        *,
        node_name: str,
        candidate_id: str | None = None,
        actor: str = "system",
        **fields,
    ) -> None:
        metadata = fields.pop("metadata", {})
        event = DecisionEvent(
            run_id=self.run_id,
            candidate_id=candidate_id,
            event_type=event_type,
            timestamp=datetime.now(UTC),
            actor=actor,
            node_name=node_name,
            metadata=metadata,
            **fields,
        )
        repository.add_event(event)
        log.info(
            "ledger run=%s candidate=%s %s node=%s",
            self.run_id,
            candidate_id,
            event_type,
            node_name,
        )

    def add_validation(self, summary: ValidationSummary) -> None:
        repository.add_validation_summary(self.run_id, summary)
