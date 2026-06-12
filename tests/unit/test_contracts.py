from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from app.models.contracts import (
    CandidateScore,
    CandidateSubScores,
    EvaluationWeights,
    EvidenceSpan,
    JobRubric,
)
from app.models.events import DecisionEvent
from app.models.export import AuditExport


def make_span(snippet: str = "a perfectly valid evidence snippet") -> EvidenceSpan:
    return EvidenceSpan(
        document_id="doc1",
        document_hash="hash",
        source_type="resume",
        snippet=snippet,
        offset_status="verified",
    )


def make_subs(value: int = 80) -> CandidateSubScores:
    return CandidateSubScores(
        required_skills=value,
        preferred_skills=value,
        experience_relevance=value,
        project_depth=value,
        ai_engineering_maturity=value,
        communication_clarity=value,
    )


def test_score_rejects_out_of_range_overall():
    with pytest.raises(ValidationError):
        CandidateScore(
            overall_score=101,
            recommendation="proceed",
            confidence=0.9,
            sub_scores=make_subs(),
            match_reasons=["r1", "r2", "r3"],
            evidence_refs=[make_span(), make_span("another valid snippet here"),
                           make_span("third valid snippet right here")],
        )


def test_score_requires_three_evidence_refs():
    with pytest.raises(ValidationError) as excinfo:
        CandidateScore(
            overall_score=80,
            recommendation="proceed",
            confidence=0.9,
            sub_scores=make_subs(),
            match_reasons=["r1", "r2", "r3"],
            evidence_refs=[make_span()],
        )
    assert "evidence_refs" in str(excinfo.value)


def test_evidence_snippet_minimum_length():
    with pytest.raises(ValidationError):
        make_span(snippet="too short")


def test_evaluation_weights_must_sum_to_one():
    with pytest.raises(ValidationError) as excinfo:
        EvaluationWeights(required_skills=0.5)
    assert "1.0" in str(excinfo.value)


def test_rubric_requires_must_haves():
    with pytest.raises(ValidationError):
        JobRubric(role_title="Backend AI Engineer", must_have_requirements=[])


def test_decision_event_rejects_unknown_type():
    with pytest.raises(ValidationError):
        DecisionEvent(
            run_id="r1",
            event_type="made_up_event",
            timestamp=datetime.now(UTC),
            node_name="n",
        )


def test_audit_export_schema_version_is_pinned():
    assert (
        AuditExport.model_fields["schema_version"].default == "audit-export.v1"
    )
    with pytest.raises(ValidationError):
        AuditExport.model_validate({"schema_version": "audit-export.v2"})
