"""Interview-script response contract (`GET /api/candidates/{id}/interview-script`).

The backend is the single source of truth for the script (v3 claim-first rule,
verification checklist, suggested timings); the frontend renders this shape
verbatim. See docs/V2_UI_PROPOSAL.md §6.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from app.models.contracts import (
    ConfidenceBand,
    EvidenceSpan,
    FollowUpQuestion,
    InterviewQuestion,
    Recommendation,
)

SelectionReason = Literal[
    "claim_probe",
    "must_have_gap",
    "dimension_gap",
    "scenario_coverage",
    "difficulty_fill",
]
VerificationReason = Literal["injection", "claim_probe", "must_have_gap", "follow_up"]


class ScriptQuestion(BaseModel):
    index: int
    question: InterviewQuestion
    suggested_minutes: int
    # Debug-only provenance (§6.2); the UI does not render this.
    selection_reason: SelectionReason | None = None


class VerificationItem(BaseModel):
    item: str
    reason: VerificationReason
    evidence_refs: list[EvidenceSpan] = Field(default_factory=list)


class InterviewScriptResponse(BaseModel):
    candidate_id: str
    candidate_name: str
    recommendation: Recommendation
    overall_score: int
    confidence: float
    confidence_band: ConfidenceBand
    script_rule_version: Literal["v3"] = "v3"
    suggested_duration_min: int
    must_ask: list[ScriptQuestion]
    follow_ups: list[FollowUpQuestion]
    optional: list[ScriptQuestion]
    verification_checklist: list[VerificationItem]
    pass_criteria: str
