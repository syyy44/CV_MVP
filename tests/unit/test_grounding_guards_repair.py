"""End-to-end: grounding guards bounce fabrications through the repair loop.

Proves the guards are wired into the production scoring path (not just unit
correct): a fabricated metric or a misattributed citation in a
``claim_verification`` triggers repair, recovers when the next attempt is
clean, and surfaces as ``RepairExhaustedError`` (→ needs_review) when it does
not. ``match_reasons`` are intentionally NOT gated, so a gap reason citing by
contrast must never trip the guard.
"""

from __future__ import annotations

import copy
import json

import pytest

from app.core.errors import RepairExhaustedError
from app.models.contracts import CandidateProfile, EvidenceSpan, JobRubric
from app.storage import repository
from app.workflows import steps
from tests.conftest import ScriptedProvider, make_workflow_context

# Résumé with only long lines, so line_no == 1-based line index (R1..R4).
RESUME_LINES = [
    "构建并运维日均 40000 次请求的生产级 FastAPI 服务",
    "设计基于 LangGraph 的文档筛选工作流，包含校验与修复节点",
    "使用 Pydantic 模式强制执行结构化输出，并设定有界修复重试",
    "为每个工作流节点接入 Langfuse 追踪与延迟指标统计",
]
RESUME_TEXT = "\n".join(RESUME_LINES)
JD_TEXT = "\n".join(
    [
        "招聘资深后端工程师，要求精通 Python 与 FastAPI 生产实践",
        "需要具备 LangGraph 等 LLM 编排框架的实战经验",
        "熟悉结构化输出校验与可观测性实践者优先",
    ]
)


def _doc(doc_id: str, text: str) -> dict:
    return {"document_id": doc_id, "document_hash": f"{doc_id}-hash", "text": text}


def _rubric() -> JobRubric:
    return JobRubric.model_validate(
        {
            "role_title": "资深后端 AI 工程师",
            "must_have_requirements": [
                {"id": "MH1", "text": "精通 Python 与 FastAPI 生产实践", "severity_penalty": 12}
            ],
        }
    )


def _profile() -> CandidateProfile:
    return CandidateProfile(
        candidate_name="测试候选人",
        summary="资深后端工程师，具备 FastAPI 与 LangGraph 工作流交付经验，用于测试。",
        skills=["Python", "FastAPI", "LangGraph"],
        evidence_spans=[
            EvidenceSpan(
                document_id="resume",
                document_hash="resume-hash",
                source_type="resume",
                snippet=RESUME_LINES[0],
                line_no=1,
                offset_status="verified",
            )
        ],
    )


def _dimension(score: int = 65, band: str = "adequate") -> dict:
    return {
        "score": score,
        "band": band,
        "rationale": "证据以结果性声明为主，过程细节有限，取中档评分。",
    }


def _valid_score() -> dict:
    return {
        "required_skills": _dimension(),
        "preferred_skills": _dimension(),
        "experience_relevance": _dimension(),
        "project_depth": _dimension(),
        "ai_engineering_maturity": _dimension(),
        "communication_clarity": _dimension(),
        "confidence": 0.72,
        "confidence_rationale": "简历信息基本完整，关键结论有直接证据支撑。",
        "match_reasons": [
            {
                "reason": "具备 FastAPI 生产服务经验。",
                "evidence": [{"source_type": "resume", "line_no": 1, "requirement_id": "MH1"}],
            },
            {
                "reason": "交付 LangGraph 文档工作流。",
                "evidence": [{"source_type": "resume", "line_no": 2}],
            },
            {
                "reason": "采用 Pydantic 结构化输出校验。",
                "evidence": [{"source_type": "resume", "line_no": 3}],
            },
        ],
        "missing_must_haves": [],
        "unsupported_major_claims": [],
        "deal_breakers_found": [],
        "risk_flags": [],
        "claim_verifications": [
            {
                "claim": "构建并运维日均 40000 次请求的生产级 FastAPI 服务",
                "credibility": "plausible",
                "reason": "有运维语境支撑，但缺少延迟分位与统计口径。",
                "verification_hint": "追问 40000 次的统计口径与 P95 延迟。",
                "evidence": [{"source_type": "resume", "line_no": 1}],
            }
        ],
    }


def _with_fabricated_number() -> dict:
    bad = copy.deepcopy(_valid_score())
    # High lexical overlap with R1 (relevance passes) but 88888 is not in source.
    bad["claim_verifications"][0]["claim"] = "构建并运维日均 88888 次请求的生产级 FastAPI 服务"
    return bad


def _with_misattributed_citation() -> dict:
    bad = copy.deepcopy(_valid_score())
    # Claim is the LangGraph workflow line (R2) but cites the FastAPI line (R1).
    bad["claim_verifications"][0]["claim"] = RESUME_LINES[1]
    bad["claim_verifications"][0]["evidence"] = [{"source_type": "resume", "line_no": 1}]
    return bad


def _run(run_id: str, responses: list[dict]):
    repository.create_run(run_id, "replay", None)
    provider = ScriptedProvider([json.dumps(r, ensure_ascii=False) for r in responses])
    ctx = make_workflow_context(run_id, provider)
    return steps.analyze_and_score(
        ctx,
        candidate_id="cand-1",
        slug="cand",
        rubric=_rubric(),
        profile=_profile(),
        jd_doc=_doc("jd", JD_TEXT),
        resume_doc=_doc("resume", RESUME_TEXT),
    )


def test_valid_score_passes_without_repair(app_env):
    _analysis, score, _breakdown, meta = _run("g-valid", [_valid_score()])
    assert meta.attempts == 1 and not meta.repaired
    assert score.overall_score > 0


def test_fabricated_number_triggers_repair_then_recovers(app_env):
    _analysis, _score, _breakdown, meta = _run(
        "g-fab-recover", [_with_fabricated_number(), _valid_score()]
    )
    assert meta.repaired and meta.attempts == 2
    events = [e.event_type for e in repository.get_events("g-fab-recover")]
    assert "schema_validation_failed" in events and "repair_succeeded" in events


def test_persistent_fabrication_exhausts_to_needs_review(app_env):
    with pytest.raises(RepairExhaustedError):
        _run("g-fab-fail", [_with_fabricated_number()])
    summaries = repository.get_validation_summaries("g-fab-fail")
    assert summaries[-1].status == "failed"
    assert any("未在简历" in m or "均未出现" in m for m in summaries[-1].messages)


def test_misattributed_citation_triggers_repair_then_recovers(app_env):
    _analysis, _score, _breakdown, meta = _run(
        "g-misattr", [_with_misattributed_citation(), _valid_score()]
    )
    assert meta.repaired and meta.attempts == 2


def test_guards_can_be_disabled_via_settings(app_env, monkeypatch):
    monkeypatch.setenv("GROUNDING_GUARDS_ENABLED", "false")
    from app.core.config import reset_settings_cache

    reset_settings_cache()
    # With guards off, a fabricated number is no longer caught -> first attempt passes.
    _analysis, _score, _breakdown, meta = _run("g-disabled", [_with_fabricated_number()])
    assert meta.attempts == 1 and not meta.repaired
