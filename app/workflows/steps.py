"""Workflow steps shared by LangGraph nodes and the eval runner."""

from __future__ import annotations

import json

from app.llm.prompts import (
    EXTRACT_CANDIDATE_PROFILE,
    EXTRACT_JD_RUBRIC,
    GENERATE_INTERVIEW_PACK,
    SCORE_CANDIDATE,
)
from app.llm.structured import GenerationMeta, generate_structured
from app.locale import zh_CN as msg
from app.models.contracts import (
    CandidateProfile,
    CandidateScore,
    CandidateSubScores,
    FollowUpQuestion,
    InterviewQuestion,
    JobRubric,
    ProjectItem,
    WorkExperience,
)
from app.models.drafts import (
    CandidateProfileDraft,
    InterviewPackDraft,
    ProjectItemDraft,
    ScoreAnalysisDraft,
    WorkExperienceDraft,
)
from app.workflows.context import WorkflowContext
from app.workflows.evidence import dedupe_spans, render_numbered_source, resolve_drafts
from app.workflows.scoring import ScoreBreakdown, compute_score

_BAND_RANGES = {
    "strong": (75, 100),
    "adequate": (55, 74),
    "weak": (30, 54),
    "absent": (0, 29),
}

_DIMENSION_FIELDS = (
    "required_skills",
    "preferred_skills",
    "experience_relevance",
    "project_depth",
    "ai_engineering_maturity",
    "communication_clarity",
)


def sub_scores_from_analysis(analysis: ScoreAnalysisDraft) -> CandidateSubScores:
    return CandidateSubScores(
        **{field: getattr(analysis, field).score for field in _DIMENSION_FIELDS}
    )


def _band_consistency_problems(analysis: ScoreAnalysisDraft) -> list[str]:
    problems: list[str] = []
    for field in _DIMENSION_FIELDS:
        assessment = getattr(analysis, field)
        low, high = _BAND_RANGES[assessment.band]
        if not low <= assessment.score <= high:
            problems.append(
                msg.band_score_mismatch(field, assessment.band, assessment.score)
            )
    return problems


def _docs_by_type(jd_doc: dict, resume_doc: dict | None = None) -> dict[str, dict]:
    docs = {"jd": jd_doc}
    if resume_doc is not None:
        docs["resume"] = resume_doc
    return docs


def _tags_for(ctx: WorkflowContext, slug: str) -> dict:
    return {"tags": ["red_team"]} if slug in ctx.red_team_slugs else {}


def _traced_post_validate(ctx: WorkflowContext, draft, validate_fn):
    """Run evidence/domain validation under a Langfuse span."""
    with ctx.tracer.span("validate_evidence") as span:
        problems = validate_fn(draft)
        span.update(
            output={
                "problem_count": len(problems),
                "problems": problems[:3],
            }
        )
        return problems


def extract_rubric(ctx: WorkflowContext, jd_doc: dict) -> tuple[JobRubric, GenerationMeta]:
    with ctx.tracer.span("extract_jd_rubric", {"run_id": ctx.run_id}):
        rubric, meta = generate_structured(
            ctx,
            EXTRACT_JD_RUBRIC,
            JobRubric,
            {"jd_document_id": jd_doc["document_id"], "jd_text": jd_doc["text"]},
            node_name="extract_jd_rubric",
            fixture_key="rubric",
        )
    ctx.ledger.emit(
        "rubric_extracted",
        node_name="extract_jd_rubric",
        model=meta.model,
        prompt_name=meta.prompt_name,
        prompt_version=meta.prompt_version,
        input_hash=meta.input_hash,
        output_hash=meta.output_hash,
        latency_ms=meta.latency_ms,
        input_tokens=meta.input_tokens,
        output_tokens=meta.output_tokens,
        metadata={
            "role_title": rubric.role_title,
            "must_haves": [r.id for r in rubric.must_have_requirements],
        },
    )
    return rubric, meta


def _coerce_work_experience(item: WorkExperienceDraft | dict) -> WorkExperience:
    """Map draft or legacy dict shapes into strict WorkExperience contracts."""
    if isinstance(item, WorkExperienceDraft):
        return WorkExperience(
            title=item.title,
            company=item.company,
            duration=item.duration,
            highlights=item.highlights,
        )
    highlights = item.get("highlights") or item.get("responsibilities") or []
    return WorkExperience(
        title=str(item.get("title") or item.get("role") or msg.UNKNOWN_TITLE),
        company=str(item.get("company") or item.get("employer") or msg.UNKNOWN_COMPANY),
        duration=str(
            item.get("duration") or item.get("dates") or item.get("period") or msg.UNKNOWN_DURATION
        ),
        highlights=[str(h) for h in highlights],
    )


def _coerce_project(item: ProjectItemDraft | dict) -> ProjectItem:
    if isinstance(item, ProjectItemDraft):
        return ProjectItem(
            name=item.name,
            description=item.description,
            technologies=item.technologies,
        )
    return ProjectItem(
        name=str(item.get("name") or item.get("title") or msg.UNNAMED_PROJECT),
        description=str(
            item.get("description") or item.get("summary") or msg.NO_PROJECT_DESCRIPTION
        ),
        technologies=[str(t) for t in item.get("technologies") or item.get("tech") or []],
    )


def extract_profile(
    ctx: WorkflowContext, candidate_id: str, slug: str, jd_doc: dict, resume_doc: dict
) -> tuple[CandidateProfile, GenerationMeta]:
    docs = _docs_by_type(jd_doc, resume_doc)

    def post_validate(draft: CandidateProfileDraft) -> list[str]:
        def validate(d: CandidateProfileDraft) -> list[str]:
            _, problems = resolve_drafts(d.evidence, docs)
            return problems

        return _traced_post_validate(ctx, draft, validate)

    with ctx.tracer.span(
        "extract_candidate_profile", {"run_id": ctx.run_id, "candidate_id": candidate_id}
    ):
        draft, meta = generate_structured(
            ctx,
            EXTRACT_CANDIDATE_PROFILE,
            CandidateProfileDraft,
            {
                "resume_document_id": resume_doc["document_id"],
                "filename": resume_doc["filename"],
                "resume_text": render_numbered_source(resume_doc["text"], "resume"),
            },
            node_name="extract_candidate_profile",
            candidate_id=candidate_id,
            fixture_key=f"{slug}/profile",
            post_validate=post_validate,
        )

    spans, _ = resolve_drafts(draft.evidence, docs)
    profile = CandidateProfile(
        candidate_name=draft.candidate_name,
        summary=draft.summary,
        skills=draft.skills,
        work_experiences=[_coerce_work_experience(w) for w in draft.work_experiences],
        projects=[_coerce_project(p) for p in draft.projects],
        education=draft.education,
        certifications=draft.certifications,
        evidence_spans=spans,
        missing_or_ambiguous_claims=draft.missing_or_ambiguous_claims,
    )
    ctx.ledger.emit(
        "candidate_profile_extracted",
        node_name="extract_candidate_profile",
        candidate_id=candidate_id,
        model=meta.model,
        prompt_name=meta.prompt_name,
        prompt_version=meta.prompt_version,
        input_hash=meta.input_hash,
        output_hash=meta.output_hash,
        latency_ms=meta.latency_ms,
        input_tokens=meta.input_tokens,
        output_tokens=meta.output_tokens,
        metadata={
            "candidate_name": profile.candidate_name,
            "evidence_count": len(profile.evidence_spans),
            "ambiguous_claims": len(profile.missing_or_ambiguous_claims),
            **_tags_for(ctx, slug),
        },
    )
    return profile, meta


def analyze_and_score(
    ctx: WorkflowContext,
    candidate_id: str,
    slug: str,
    rubric: JobRubric,
    profile: CandidateProfile,
    jd_doc: dict,
    resume_doc: dict,
) -> tuple[ScoreAnalysisDraft, CandidateScore, ScoreBreakdown, GenerationMeta]:
    docs = _docs_by_type(jd_doc, resume_doc)
    rubric_ids = {r.id for r in rubric.must_have_requirements}

    def post_validate(draft: ScoreAnalysisDraft) -> list[str]:
        def validate(d: ScoreAnalysisDraft) -> list[str]:
            problems: list[str] = []
            all_drafts = [e for reason in d.match_reasons for e in reason.evidence]
            spans, evidence_problems = resolve_drafts(all_drafts, docs)
            problems.extend(evidence_problems)
            if len(dedupe_spans(spans)) < 3:
                problems.append(msg.match_reasons_need_three_quotes())
            for missing in d.missing_must_haves:
                if missing.requirement_id not in rubric_ids:
                    problems.append(msg.missing_must_have_unknown_id(missing.requirement_id))
            problems.extend(_band_consistency_problems(d))
            return problems

        return _traced_post_validate(ctx, draft, validate)

    with ctx.tracer.span(
        "score_candidate", {"run_id": ctx.run_id, "candidate_id": candidate_id}
    ):
        analysis, meta = generate_structured(
            ctx,
            SCORE_CANDIDATE,
            ScoreAnalysisDraft,
            {
                "rubric_json": rubric.model_dump_json(),
                "profile_json": profile.model_dump_json(),
                "jd_document_id": jd_doc["document_id"],
                "jd_text": render_numbered_source(jd_doc["text"], "jd"),
                "resume_document_id": resume_doc["document_id"],
                "resume_text": render_numbered_source(resume_doc["text"], "resume"),
            },
            node_name="score_candidate",
            candidate_id=candidate_id,
            fixture_key=f"{slug}/score",
            post_validate=post_validate,
        )

    with ctx.tracer.span("compute_score") as score_span:
        breakdown = compute_score(analysis, rubric.evaluation_weights)
        score_span.update(
            output={
                "overall_score": breakdown.overall_score,
                "recommendation": breakdown.recommendation,
                "confidence": analysis.confidence,
                "capped_by_deal_breaker": breakdown.capped_by_deal_breaker,
            }
        )

    all_drafts = [e for reason in analysis.match_reasons for e in reason.evidence]
    spans, _ = resolve_drafts(all_drafts, docs)
    score = CandidateScore(
        overall_score=breakdown.overall_score,
        recommendation=breakdown.recommendation,
        confidence=analysis.confidence,
        sub_scores=sub_scores_from_analysis(analysis),
        match_reasons=[reason.reason for reason in analysis.match_reasons],
        risk_flags=[flag.description for flag in analysis.risk_flags],
        evidence_refs=dedupe_spans(spans),
    )

    evidence_excerpts = [span.snippet[:80] for span in score.evidence_refs[:3]]
    for name, component in breakdown.components.items():
        ctx.ledger.emit(
            "score_component_computed",
            node_name="score_candidate",
            candidate_id=candidate_id,
            model=meta.model,
            metadata={"component": name, **component, "evidence_refs": evidence_excerpts},
        )
    ctx.ledger.emit(
        "recommendation_derived",
        node_name="score_candidate",
        candidate_id=candidate_id,
        model=meta.model,
        prompt_name=meta.prompt_name,
        prompt_version=meta.prompt_version,
        output_hash=meta.output_hash,
        latency_ms=meta.latency_ms,
        metadata={
            "overall_score": score.overall_score,
            "recommendation": score.recommendation,
            "confidence": score.confidence,
            "base": round(breakdown.base, 2),
            "penalties": breakdown.penalties,
            "capped_by_deal_breaker": breakdown.capped_by_deal_breaker,
            **_tags_for(ctx, slug),
        },
    )
    return analysis, score, breakdown, meta


def generate_pack(
    ctx: WorkflowContext,
    candidate_id: str,
    slug: str,
    rubric: JobRubric,
    profile: CandidateProfile,
    analysis: ScoreAnalysisDraft,
    jd_doc: dict,
    resume_doc: dict,
) -> tuple[list[InterviewQuestion], list[FollowUpQuestion], GenerationMeta]:
    docs = _docs_by_type(jd_doc, resume_doc)

    def post_validate(draft: InterviewPackDraft) -> list[str]:
        def validate(d: InterviewPackDraft) -> list[str]:
            all_drafts = [e for fu in d.follow_ups for e in fu.evidence]
            _, problems = resolve_drafts(all_drafts, docs)
            return problems

        return _traced_post_validate(ctx, draft, validate)

    with ctx.tracer.span(
        "generate_interview_pack", {"run_id": ctx.run_id, "candidate_id": candidate_id}
    ):
        draft, meta = generate_structured(
            ctx,
            GENERATE_INTERVIEW_PACK,
            InterviewPackDraft,
            {
                "rubric_json": rubric.model_dump_json(),
                "profile_json": profile.model_dump_json(),
                "analysis_json": json.dumps(
                    {
                        "sub_scores": sub_scores_from_analysis(analysis).model_dump(),
                        "dimension_bands": {
                            field: getattr(analysis, field).band
                            for field in _DIMENSION_FIELDS
                        },
                        "missing_must_haves": [m.model_dump() for m in analysis.missing_must_haves],
                        "unsupported_major_claims": analysis.unsupported_major_claims,
                        "risk_flags": [f.model_dump() for f in analysis.risk_flags],
                    },
                    ensure_ascii=False,
                ),
                "resume_document_id": resume_doc["document_id"],
                "resume_text": render_numbered_source(resume_doc["text"], "resume"),
            },
            node_name="generate_interview_pack",
            candidate_id=candidate_id,
            fixture_key=f"{slug}/interview_pack",
            post_validate=post_validate,
        )

    follow_ups = []
    for fu in draft.follow_ups:
        spans, _ = resolve_drafts(fu.evidence, docs)
        follow_ups.append(
            FollowUpQuestion(
                question=fu.question,
                ambiguity=fu.ambiguity,
                what_to_listen_for=fu.what_to_listen_for,
                evidence_refs=spans,
            )
        )
    ctx.ledger.emit(
        "questions_generated",
        node_name="generate_interview_pack",
        candidate_id=candidate_id,
        model=meta.model,
        prompt_name=meta.prompt_name,
        prompt_version=meta.prompt_version,
        output_hash=meta.output_hash,
        latency_ms=meta.latency_ms,
        input_tokens=meta.input_tokens,
        output_tokens=meta.output_tokens,
        metadata={"questions": len(draft.questions), "follow_ups": len(follow_ups)},
    )
    return draft.questions, follow_ups, meta
