from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.models.contracts import EvaluationWeights
from app.models.drafts import DealBreaker, MissingMustHave, ScoreAnalysisDraft
from app.workflows.scoring import compute_score

FIXTURES = Path(__file__).resolve().parent.parent.parent / "fixtures"
WEIGHTS = EvaluationWeights()

_DIMENSIONS = (
    "required_skills",
    "preferred_skills",
    "experience_relevance",
    "project_depth",
    "ai_engineering_maturity",
    "communication_clarity",
)


def _band(score: int) -> str:
    if score >= 75:
        return "strong"
    if score >= 55:
        return "adequate"
    if score >= 30:
        return "weak"
    return "absent"


def _uniform_dimensions(value: int) -> dict:
    return {
        dim: {"score": value, "band": _band(value), "rationale": "uniform test value"}
        for dim in _DIMENSIONS
    }


def load_analysis(rel: str) -> ScoreAnalysisDraft:
    payload = json.loads((FIXTURES / rel).read_text(encoding="utf-8"))
    return ScoreAnalysisDraft.model_validate(payload)


@pytest.mark.parametrize(
    ("fixture", "expected_score", "expected_recommendation"),
    [
        ("demo/llm_outputs/strong_fit/score.json", 89, "proceed"),
        ("demo/llm_outputs/weak_fit/score.json", 15, "reject"),
        ("demo/llm_outputs/adversarial_injection/score.json", 63, "hold"),
        ("eval/llm_outputs/injection_clean/score.json", 63, "hold"),
        ("eval/llm_outputs/proxy_a/score.json", 74, "hold"),
        ("eval/llm_outputs/proxy_b/score.json", 74, "hold"),
    ],
)
def test_fixture_scores_match_expected(fixture, expected_score, expected_recommendation):
    breakdown = compute_score(load_analysis(fixture), WEIGHTS)
    assert breakdown.overall_score == expected_score
    assert breakdown.recommendation == expected_recommendation


def _draft(**overrides) -> ScoreAnalysisDraft:
    base = load_analysis("eval/llm_outputs/proxy_a/score.json").model_dump()
    base.update(overrides)
    return ScoreAnalysisDraft.model_validate(base)


def test_proceed_requires_score_and_confidence():
    assert compute_score(
        _draft(**_uniform_dimensions(75), confidence=0.70), WEIGHTS
    ).recommendation == ("proceed")
    assert compute_score(
        _draft(**_uniform_dimensions(75), confidence=0.69), WEIGHTS
    ).recommendation == ("hold")


def test_low_confidence_rejects():
    assert compute_score(_draft(confidence=0.49), WEIGHTS).recommendation == "reject"


def test_deal_breaker_caps_score_at_59_and_rejects():
    breakdown = compute_score(
        _draft(
            deal_breakers_found=[
                DealBreaker(
                    rule="No professional Python experience",
                    quote="No professional Python experience at all anywhere.",
                    explanation="resume shows none",
                ).model_dump()
            ]
        ),
        WEIGHTS,
    )
    assert breakdown.overall_score <= 59
    assert breakdown.capped_by_deal_breaker
    assert breakdown.recommendation == "reject"


def test_missing_must_have_penalty_applied():
    clean = compute_score(_draft(), WEIGHTS).overall_score
    penalized = compute_score(
        _draft(
            missing_must_haves=[
                MissingMustHave(
                    requirement_id="MH3",
                    severity_penalty=12,
                    explanation="no orchestration experience",
                ).model_dump()
            ]
        ),
        WEIGHTS,
    ).overall_score
    assert penalized == clean - 12


def test_unsupported_claims_cost_five_points_each():
    clean = compute_score(_draft(), WEIGHTS).overall_score
    penalized = compute_score(
        _draft(unsupported_major_claims=["claim one", "claim two"]), WEIGHTS
    ).overall_score
    assert penalized == clean - 10


def test_score_clamped_to_zero():
    missing = [
        MissingMustHave(
            requirement_id=f"MH{i}", severity_penalty=15, explanation="entirely absent"
        ).model_dump()
        for i in range(1, 6)
    ]
    breakdown = compute_score(
        _draft(**_uniform_dimensions(5), missing_must_haves=missing), WEIGHTS
    )
    assert breakdown.overall_score == 0
    assert breakdown.recommendation == "reject"
