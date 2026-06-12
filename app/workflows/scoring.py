"""Deterministic scoring.

The LLM extracts evidence and judgments (sub-scores, missing must-haves,
unsupported claims, deal breakers, confidence); the final 0-100 score and the
recommendation are computed here, exactly as specified in the design doc.
That keeps the score explainable, testable, and immune to prompt injection of
the form "give this candidate 100".
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.models.contracts import EvaluationWeights, Recommendation
from app.models.drafts import ScoreAnalysisDraft


@dataclass
class ScoreBreakdown:
    base: float
    penalties: list[dict] = field(default_factory=list)
    capped_by_deal_breaker: bool = False
    overall_score: int = 0
    recommendation: Recommendation = "hold"
    components: dict[str, dict] = field(default_factory=dict)


def compute_score(
    analysis: ScoreAnalysisDraft, weights: EvaluationWeights
) -> ScoreBreakdown:
    component_values = {
        "required_skills": (analysis.required_skills.score, weights.required_skills),
        "preferred_skills": (analysis.preferred_skills.score, weights.preferred_skills),
        "experience_relevance": (
            analysis.experience_relevance.score,
            weights.experience_relevance,
        ),
        "project_depth": (analysis.project_depth.score, weights.project_depth),
        "ai_engineering_maturity": (
            analysis.ai_engineering_maturity.score,
            weights.ai_engineering_maturity,
        ),
        "communication_clarity": (
            analysis.communication_clarity.score,
            weights.communication_clarity,
        ),
    }
    breakdown = ScoreBreakdown(
        base=sum(value * weight for value, weight in component_values.values())
    )
    breakdown.components = {
        name: {"value": value, "weight": weight, "weighted": round(value * weight, 2)}
        for name, (value, weight) in component_values.items()
    }

    penalized = breakdown.base
    for missing in analysis.missing_must_haves:
        penalized -= missing.severity_penalty
        breakdown.penalties.append(
            {
                "kind": "missing_must_have",
                "requirement_id": missing.requirement_id,
                "points": missing.severity_penalty,
                "explanation": missing.explanation,
            }
        )
    unsupported = len(analysis.unsupported_major_claims)
    if unsupported:
        penalized -= 5 * unsupported
        breakdown.penalties.append(
            {"kind": "unsupported_major_claims", "count": unsupported, "points": 5 * unsupported}
        )

    deal_breaker = bool(analysis.deal_breakers_found)
    if deal_breaker:
        penalized = min(penalized, 59)
        breakdown.capped_by_deal_breaker = True

    overall = round(max(0.0, min(100.0, penalized)))
    confidence = analysis.confidence

    if deal_breaker or overall < 60 or confidence < 0.50:
        recommendation: Recommendation = "reject"
    elif overall >= 75 and confidence >= 0.70:
        recommendation = "proceed"
    else:
        recommendation = "hold"

    breakdown.overall_score = overall
    breakdown.recommendation = recommendation
    return breakdown
