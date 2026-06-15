from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

EventType = Literal[
    "document_parsed",
    "rubric_extracted",
    "candidate_started",
    "llm_call_started",
    "candidate_profile_extracted",
    "schema_validation_failed",
    "repair_attempted",
    "repair_succeeded",
    "repair_failed",
    "score_component_computed",
    "recommendation_derived",
    "questions_generated",
    "dossier_completed",
    "human_override_recorded",
    "note_added",
]


class DecisionEvent(BaseModel):
    """Product-facing decision provenance (distinct from Langfuse maintainer traces)."""

    id: int | None = None
    run_id: str
    candidate_id: str | None = None
    event_type: EventType
    timestamp: datetime
    actor: Literal["system", "human"] = "system"
    node_name: str
    model: str | None = None
    prompt_name: str | None = None
    prompt_version: str | None = None
    input_hash: str | None = None
    output_hash: str | None = None
    schema_name: str | None = None
    validation_status: Literal["valid", "repaired", "failed"] | None = None
    repair_attempt: int | None = None
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    metadata: dict = Field(default_factory=dict)
