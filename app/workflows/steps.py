"""Workflow steps shared by LangGraph nodes and the eval runner."""

from __future__ import annotations

import json
from collections import Counter

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
    ClaimVerification,
    FollowUpQuestion,
    InterviewQuestion,
    JobRubric,
    ProjectItem,
    RequirementResult,
    ScoreBreakdownExplanation,
    ScoreDimensionExplanation,
    ScoreExplanation,
    ScorePenaltyExplanation,
    WorkExperience,
)
from app.models.drafts import (
    CandidateProfileDraft,
    InterviewPackDraft,
    ProjectItemDraft,
    ScoreAnalysisDraft,
    WorkExperienceDraft,
)
from app.models.education import coerce_education_item
from app.workflows.context import WorkflowContext
from app.workflows.evidence import dedupe_spans, render_numbered_source, resolve_drafts
from app.workflows.grounding import (
    claim_number_problems,
    quantified_claim_problems,
    relevance,
    support_relevance_problems,
)
from app.workflows.requirement_refs import build_jd_evidence_refs
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

_NEGATIVE_REASON_MARKERS = (
    "未",
    "缺",
    "不足",
    "尚未",
    "低于",
    "风险",
    "不匹配",
    "存疑",
    "口径",
    "无",
    "弱",
)

# 深度面试题的题型配比下限（资深面试官方法论；与 GENERATE_INTERVIEW_PACK v8 一致）。
_ARCHETYPE_MINIMUMS = {
    "experience_probe": 2,
    "metric_validation": 1,
    "depth_probe": 1,
    "failure_review": 1,
    "scenario_design": 1,
    "jd_fit": 1,
}

# 这些题型必须锚定简历中的具体声明，否则会退化成通用八股题。
_CLAIM_ANCHORED_ARCHETYPES = {
    "experience_probe",
    "metric_validation",
    "depth_probe",
    "failure_review",
}

_MIN_PROBE_CHAIN = 2


def sub_scores_from_analysis(analysis: ScoreAnalysisDraft) -> CandidateSubScores:
    return CandidateSubScores(
        **{field: getattr(analysis, field).score for field in _DIMENSION_FIELDS}
    )


def _requirement_label(text: str, limit: int = 28) -> str:
    """Short, human label for a must-have (no rubric code), per UX-014."""
    head = text.strip().rstrip("。.")
    return head if len(head) <= limit else f"{head[:limit]}…"


def _requirement_results(
    rubric: JobRubric, analysis: ScoreAnalysisDraft, jd_doc: dict | None = None
) -> list[RequirementResult]:
    """Resolve each must-have into met/unmet using the model's missing list.

    Derived deterministically from already-validated data — no new LLM output —
    so it works identically in live and replay.
    """
    missing = {m.requirement_id for m in analysis.missing_must_haves}
    return [
        RequirementResult(
            requirement_id=req.id,
            display_label=_requirement_label(req.text),
            met=req.id not in missing,
            weight=req.severity_penalty,
            jd_evidence_refs=(
                build_jd_evidence_refs(req.id, req.text, jd_doc) if jd_doc else []
            ),
        )
        for req in rubric.must_have_requirements
    ]


def _met_requirement_resume_citation_problems(
    analysis: ScoreAnalysisDraft, rubric: JobRubric
) -> list[str]:
    missing_ids = {item.requirement_id for item in analysis.missing_must_haves}
    cited_resume_ids = {
        evidence.requirement_id
        for reason in analysis.match_reasons
        for evidence in reason.evidence
        if evidence.source_type == "resume" and evidence.requirement_id
    }
    problems: list[str] = []
    for req in rubric.must_have_requirements:
        if req.id in missing_ids or req.id in cited_resume_ids:
            continue
        problems.append(msg.met_requirement_missing_resume_evidence(req.id))
    return problems


def _dedupe_texts(items: list[str], limit: int) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        text = " ".join(str(item).split())
        if not text or text in seen:
            continue
        result.append(text)
        seen.add(text)
        if len(result) >= limit:
            break
    return result


def _is_gap_reason(text: str) -> bool:
    return any(marker in text for marker in _NEGATIVE_REASON_MARKERS)


def _recommendation_rule_text(breakdown: ScoreBreakdown, confidence: float) -> str:
    if breakdown.capped_by_deal_breaker:
        return "命中一票否决，总分封顶 59，因此推荐拒绝。"
    if breakdown.overall_score < 60:
        return "最终分低于 60 分，因此推荐拒绝。"
    if confidence < 0.50:
        return "评分置信度低于 0.50，因此推荐拒绝。"
    if breakdown.overall_score >= 75 and confidence >= 0.70:
        return "最终分不低于 75 且置信度不低于 0.70，因此推荐通过。"
    return "未达到通过阈值且未触发拒绝阈值，因此推荐待定。"


def _score_penalties(
    analysis: ScoreAnalysisDraft, breakdown: ScoreBreakdown
) -> list[ScorePenaltyExplanation]:
    penalties: list[ScorePenaltyExplanation] = []
    missing_by_id = {item.requirement_id: item for item in analysis.missing_must_haves}
    for penalty in breakdown.penalties:
        if penalty["kind"] == "missing_must_have":
            requirement_id = str(penalty.get("requirement_id") or "")
            missing = missing_by_id.get(requirement_id)
            penalties.append(
                ScorePenaltyExplanation(
                    kind="missing_must_have",
                    requirement_id=requirement_id or None,
                    points=int(penalty["points"]),
                    explanation=(
                        missing.explanation
                        if missing
                        else str(penalty.get("explanation") or "缺失必备要求")
                    ),
                )
            )
        elif penalty["kind"] == "unsupported_major_claims":
            penalties.append(
                ScorePenaltyExplanation(
                    kind="unsupported_major_claims",
                    points=int(penalty["points"]),
                    explanation=f"{penalty.get('count', 0)} 条重大声明缺乏足够支撑。",
                )
            )
    return penalties


def _score_dimensions(
    analysis: ScoreAnalysisDraft, breakdown: ScoreBreakdown
) -> list[ScoreDimensionExplanation]:
    dimensions: list[ScoreDimensionExplanation] = []
    for field in _DIMENSION_FIELDS:
        assessment = getattr(analysis, field)
        component = breakdown.components[field]
        dimensions.append(
            ScoreDimensionExplanation(
                key=field,
                score=assessment.score,
                band=assessment.band,
                weight=float(component["weight"]),
                weighted_points=float(component["weighted"]),
                rationale=assessment.rationale,
            )
        )
    return dimensions


def _build_score_explanation(
    analysis: ScoreAnalysisDraft,
    score: CandidateScore,
    breakdown: ScoreBreakdown,
) -> ScoreExplanation:
    match_reasons = [reason.reason for reason in analysis.match_reasons]
    fit_reasons = [reason for reason in match_reasons if not _is_gap_reason(reason)]
    gap_reasons = [reason for reason in match_reasons if _is_gap_reason(reason)]
    gap_reasons.extend(missing.explanation for missing in analysis.missing_must_haves)
    gap_reasons.extend(analysis.unsupported_major_claims)
    gap_reasons.extend(flag.description for flag in analysis.risk_flags)
    gap_reasons.extend(
        f"{claim.claim}：{claim.reason}"
        for claim in analysis.claim_verifications
        if claim.credibility in ("needs_probing", "suspicious")
    )

    verification_priorities = [
        claim.verification_hint
        for claim in analysis.claim_verifications
        if claim.credibility in ("needs_probing", "suspicious")
    ]
    verification_priorities.extend(
        f"围绕缺失必备项「{missing.requirement_id}」要求候选人补充可验证案例。"
        for missing in analysis.missing_must_haves
    )

    verdict = (
        f"推荐{score.recommendation}：最终 {score.overall_score} 分，"
        f"置信度 {score.confidence:.2f}。{_recommendation_rule_text(breakdown, score.confidence)}"
    )

    return ScoreExplanation(
        verdict_summary=verdict,
        fit_reasons=_dedupe_texts(fit_reasons, 3),
        gap_reasons=_dedupe_texts(gap_reasons, 4),
        verification_priorities=_dedupe_texts(verification_priorities, 3),
        confidence_rationale=analysis.confidence_rationale,
        dimensions=_score_dimensions(analysis, breakdown),
        breakdown=ScoreBreakdownExplanation(
            base_score=round(breakdown.base, 2),
            penalties=_score_penalties(analysis, breakdown),
            capped_by_deal_breaker=breakdown.capped_by_deal_breaker,
            final_score=breakdown.overall_score,
            recommendation_rule=_recommendation_rule_text(breakdown, score.confidence),
        ),
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


def _traced_post_validate(ctx: WorkflowContext, draft, validate_fn, diagnostics_fn=None):
    """Run evidence/domain validation under a Langfuse span.

    ``diagnostics_fn`` (optional) returns non-blocking metrics merged into the
    span output — used to observe grounding signals (e.g. evidence alignment)
    that we deliberately do not hard-gate, so thresholds can be tuned from
    real telemetry.
    """
    with ctx.tracer.span("validate_evidence") as span:
        problems = validate_fn(draft)
        output = {"problem_count": len(problems), "problems": problems[:3]}
        if diagnostics_fn is not None:
            output.update(diagnostics_fn(draft))
        span.update(output=output)
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
            source_work_experience=item.source_work_experience,
            technologies=item.technologies,
            role_in_project=item.role_in_project,
            quantified_claims=item.quantified_claims,
            tech_decisions=item.tech_decisions,
        )
    return ProjectItem(
        name=str(item.get("name") or item.get("title") or msg.UNNAMED_PROJECT),
        description=str(
            item.get("description") or item.get("summary") or msg.NO_PROJECT_DESCRIPTION
        ),
        source_work_experience=str(
            item.get("source_work_experience")
            or item.get("work_experience")
            or item.get("experience")
            or ""
        ),
        technologies=[str(t) for t in item.get("technologies") or item.get("tech") or []],
        role_in_project=str(item.get("role_in_project") or ""),
        quantified_claims=[str(c) for c in item.get("quantified_claims") or []],
        tech_decisions=[str(t) for t in item.get("tech_decisions") or []],
    )


def extract_profile(
    ctx: WorkflowContext, candidate_id: str, slug: str, jd_doc: dict, resume_doc: dict
) -> tuple[CandidateProfile, GenerationMeta]:
    docs = _docs_by_type(jd_doc, resume_doc)

    def post_validate(draft: CandidateProfileDraft) -> list[str]:
        def validate(d: CandidateProfileDraft) -> list[str]:
            _, problems = resolve_drafts(d.evidence, docs)
            if ctx.settings.grounding_guards_enabled:
                # quantified_claims are contractually verbatim excerpts; a number
                # that is absent from the résumé is a fabrication, not a paraphrase.
                problems.extend(
                    quantified_claim_problems(d.projects, resume_doc["text"])
                )
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
                "current_date": ctx.evaluation_date,
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
        education=[coerce_education_item(e) for e in draft.education],
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
            "resume_filename": resume_doc["filename"],
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

    def _resolve_units(
        items, text_of
    ) -> tuple[list[tuple[str, list]], list[str]]:
        """Resolve each item's evidence once, returning (claim, spans) units
        plus the collected resolution problems."""
        units: list[tuple[str, list]] = []
        problems: list[str] = []
        for item in items:
            spans, item_problems = resolve_drafts(item.evidence, docs)
            problems.extend(item_problems)
            units.append((text_of(item), spans))
        return units, problems

    def post_validate(draft: ScoreAnalysisDraft) -> list[str]:
        def validate(d: ScoreAnalysisDraft) -> list[str]:
            problems: list[str] = []

            match_units, match_problems = _resolve_units(
                d.match_reasons, lambda r: r.reason
            )
            problems.extend(match_problems)
            match_spans = [span for _, spans in match_units for span in spans]
            if len(dedupe_spans(match_spans)) < 3:
                problems.append(msg.match_reasons_need_three_quotes())

            claim_units, claim_problems = _resolve_units(
                d.claim_verifications, lambda cv: cv.claim
            )
            problems.extend(claim_problems)

            if ctx.settings.grounding_guards_enabled:
                # A claim_verification quotes a résumé statement, so its cited line
                # must lexically overlap it; near-zero overlap means a misattributed
                # citation. match_reasons are deliberately NOT gated — gap reasons
                # legitimately cite by contrast (see grounding.py).
                problems.extend(
                    support_relevance_problems(
                        claim_units,
                        label="claim_verifications",
                        min_relevance=ctx.settings.evidence_relevance_min,
                    )
                )
                # A number in a claim that appears in neither the JD nor the
                # résumé is a near-certain fabrication.
                problems.extend(
                    claim_number_problems(
                        [cv.claim for cv in d.claim_verifications],
                        jd_doc["text"],
                        resume_doc["text"],
                    )
                )

            for missing in d.missing_must_haves:
                if missing.requirement_id not in rubric_ids:
                    problems.append(msg.missing_must_have_unknown_id(missing.requirement_id))
            problems.extend(_met_requirement_resume_citation_problems(d, rubric))
            problems.extend(_band_consistency_problems(d))
            return problems

        def diagnostics(d: ScoreAnalysisDraft) -> dict:
            def _min_align(items, text_of) -> float | None:
                units, _ = _resolve_units(items, text_of)
                aligns = [
                    max((relevance(claim, s.snippet) for s in spans), default=1.0)
                    for claim, spans in units
                    if spans
                ]
                return round(min(aligns), 3) if aligns else None

            return {
                "min_claim_alignment": _min_align(d.claim_verifications, lambda cv: cv.claim),
                "min_match_alignment": _min_align(d.match_reasons, lambda r: r.reason),
            }

        return _traced_post_validate(ctx, draft, validate, diagnostics)

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
    claim_verifications = []
    for cv in analysis.claim_verifications:
        cv_spans, _ = resolve_drafts(cv.evidence, docs)
        claim_verifications.append(
            ClaimVerification(
                claim=cv.claim,
                credibility=cv.credibility,
                reason=cv.reason,
                verification_hint=cv.verification_hint,
                evidence_refs=cv_spans,
            )
        )
    score = CandidateScore(
        overall_score=breakdown.overall_score,
        recommendation=breakdown.recommendation,
        confidence=analysis.confidence,
        sub_scores=sub_scores_from_analysis(analysis),
        match_reasons=[reason.reason for reason in analysis.match_reasons],
        risk_flags=[flag.description for flag in analysis.risk_flags],
        evidence_refs=dedupe_spans(spans),
        requirement_results=_requirement_results(rubric, analysis, jd_doc),
        claim_verifications=claim_verifications,
        injection_detected=any(
            flag.category == "prompt_injection" for flag in analysis.risk_flags
        ),
    )
    score.score_explanation = _build_score_explanation(analysis, score, breakdown)

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


def _anchor_text_matches(anchor: str, claim: str) -> bool:
    anchor_norm = "".join(anchor.split()).lower()
    claim_norm = "".join(claim.split()).lower()
    if not anchor_norm or not claim_norm:
        return False
    if anchor_norm in claim_norm or claim_norm in anchor_norm:
        return True
    return relevance(anchor, claim) >= 0.34


def pack_quality_problems(
    questions: list[InterviewQuestion],
    required_claims: list[str] | None = None,
) -> list[str]:
    """Deterministic guardrails for the v8 deep-interview methodology.

    Enforces the archetype mix, the per-question probe chain, and claim
    anchoring so the pack cannot silently degrade into generic quiz questions.
    Shared by the generation post-validation and the eval suite.
    """
    problems: list[str] = []
    counts = Counter(q.archetype for q in questions)
    for archetype, minimum in _ARCHETYPE_MINIMUMS.items():
        if counts.get(archetype, 0) < minimum:
            problems.append(
                msg.archetype_quota_unmet(archetype, minimum, counts.get(archetype, 0))
            )
    for index, question in enumerate(questions):
        if len(question.follow_up_probes) < _MIN_PROBE_CHAIN:
            problems.append(
                msg.question_needs_probe_chain(index, len(question.follow_up_probes))
            )
        if question.archetype in _CLAIM_ANCHORED_ARCHETYPES and not question.target_claim.strip():
            problems.append(msg.question_needs_target_claim(index, question.archetype))
    for claim in required_claims or []:
        if not any(_anchor_text_matches(question.target_claim, claim) for question in questions):
            problems.append(msg.anchor_claim_not_covered(claim))
    return problems


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
            high_priority_claims = [
                cv.claim
                for cv in analysis.claim_verifications
                if cv.credibility in ("needs_probing", "suspicious")
            ]
            problems.extend(pack_quality_problems(d.questions, high_priority_claims))
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
                "current_date": ctx.evaluation_date,
                "rubric_json": rubric.model_dump_json(),
                "profile_json": profile.model_dump_json(),
                "analysis_json": json.dumps(
                    {
                        "sub_scores": sub_scores_from_analysis(analysis).model_dump(),
                        "dimension_bands": {
                            field: getattr(analysis, field).band
                            for field in _DIMENSION_FIELDS
                        },
                        "claim_verifications": [
                            cv.model_dump(exclude={"evidence"})
                            for cv in analysis.claim_verifications
                        ],
                        "anchor_claims": [
                            {
                                **cv.model_dump(),
                                "priority": (
                                    "high"
                                    if cv.credibility in ("needs_probing", "suspicious")
                                    else "normal"
                                ),
                            }
                            for cv in analysis.claim_verifications
                        ],
                        "missing_must_haves": [m.model_dump() for m in analysis.missing_must_haves],
                        "unsupported_major_claims": analysis.unsupported_major_claims,
                        "risk_flags": [f.model_dump() for f in analysis.risk_flags],
                    },
                    ensure_ascii=False,
                ),
                "jd_document_id": jd_doc["document_id"],
                "jd_text": render_numbered_source(jd_doc["text"], "jd"),
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
