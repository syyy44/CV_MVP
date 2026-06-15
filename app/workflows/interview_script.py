"""Interview-script builder — backend single source of truth (§6.2, §6.4).

Pure functions over a completed `DecisionDossier`: no LLM calls, no DB. The v3
rule puts claim verification first: questions anchored to needs_probing /
suspicious resume claims lead, then unmet must-haves and the weakest score
dimensions, and the slate always tries to keep one scenario-design question.
Also derives the hold verification checklist, pass criteria, and the board
summary fields.
"""

from __future__ import annotations

import re
from difflib import SequenceMatcher

from app.models.contracts import (
    ClaimVerification,
    ConfidenceBand,
    DecisionDossier,
    InterviewQuestion,
    RequirementResult,
)
from app.models.interview_script import (
    InterviewScriptResponse,
    ScriptQuestion,
    SelectionReason,
    VerificationItem,
)

_DIFFICULTY_WEIGHT = {"expert": 4, "senior": 3, "mid": 2, "junior": 1}
_DIFFICULTY_MINUTES = {"expert": 10, "senior": 8, "mid": 6, "junior": 5}

# 深度题型的建议用时：复原与场景推演需要给候选人现场思考/画图的时间。
_ARCHETYPE_MINUTES = {
    "experience_probe": 12,
    "metric_validation": 8,
    "depth_probe": 8,
    "failure_review": 10,
    "scenario_design": 12,
    "jd_fit": 6,
}

# Tie-break priority when score dimensions are equal (§6.2 step 1).
_DIMENSION_PRIORITY = (
    "required_skills",
    "ai_engineering_maturity",
    "experience_relevance",
    "project_depth",
    "communication_clarity",
    "preferred_skills",
)

# Dimension → competency keyword map (§6.2.1). preferred_skills has no keywords.
_DIMENSION_KEYWORDS: dict[str, tuple[str, ...]] = {
    "required_skills": ("python", "fastapi", "后端", "api"),
    "ai_engineering_maturity": ("langgraph", "llm", "编排", "rag", "prompt", "注入", "安全"),
    "experience_relevance": ("年限", "项目", "上线", "生产"),
    "project_depth": ("架构", "性能", "p95", "吞吐"),
    "communication_clarity": ("沟通", "协作", "文档"),
}

_MUST_ASK_TARGET = 4
_CHECKLIST_CAP = 5
_VERIFICATION_PRIORITY = {
    "injection": 0,
    "claim_probe": 1,
    "must_have_gap": 2,
    "follow_up": 3,
}
_INJECTION_ITEM = "请候选人说明简历中异常指令的来源，以及为何会出现在简历里。"

# 声明核查优先级：suspicious 比 needs_probing 更紧急。
_PROBE_CREDIBILITY_ORDER = {"suspicious": 0, "needs_probing": 1}
_CLAIM_MATCH_MIN_CHARS = 8


def confidence_band(value: float) -> ConfidenceBand:
    if value >= 0.85:
        return "high"
    if value >= 0.65:
        return "medium"
    return "low"


def _suggested_minutes(question: InterviewQuestion) -> int:
    if question.archetype in _ARCHETYPE_MINUTES:
        return _ARCHETYPE_MINUTES[question.archetype]
    return _DIFFICULTY_MINUTES.get(question.difficulty, 6)


def _question_dims(question: InterviewQuestion) -> set[str]:
    haystack = f"{question.competency} {question.question}".lower()
    return {
        dim
        for dim, keywords in _DIMENSION_KEYWORDS.items()
        if any(kw in haystack for kw in keywords)
    }


def _text_dims(text: str) -> set[str]:
    haystack = text.lower()
    return {
        dim
        for dim, keywords in _DIMENSION_KEYWORDS.items()
        if any(kw in haystack for kw in keywords)
    }


def _gap_dimensions(dossier: DecisionDossier) -> list[str]:
    sub = dossier.score.sub_scores
    ranked = sorted(
        _DIMENSION_PRIORITY,
        key=lambda dim: (getattr(sub, dim), _DIMENSION_PRIORITY.index(dim)),
    )
    return ranked[:2]


def _unmet_must_haves(dossier: DecisionDossier) -> list[RequirementResult]:
    unmet = [r for r in dossier.score.requirement_results if not r.met]
    return sorted(unmet, key=lambda r: r.weight, reverse=True)


def _claims_to_probe(dossier: DecisionDossier) -> list[ClaimVerification]:
    """Claims that must be probed in the interview, most urgent first."""
    flagged = [
        cv
        for cv in dossier.score.claim_verifications
        if cv.credibility in _PROBE_CREDIBILITY_ORDER
    ]
    return sorted(flagged, key=lambda cv: _PROBE_CREDIBILITY_ORDER[cv.credibility])


def _normalize_text(text: str) -> str:
    return re.sub(r"\s+", "", text).lower()


def _question_matches_claim(question: InterviewQuestion, claim: ClaimVerification) -> bool:
    """A question covers a claim when their anchored texts share real overlap."""
    anchor = _normalize_text(question.target_claim)
    target = _normalize_text(claim.claim)
    if not anchor or not target:
        return False
    if anchor in target or target in anchor:
        return True
    match = SequenceMatcher(None, anchor, target).find_longest_match(
        0, len(anchor), 0, len(target)
    )
    return match.size >= _CLAIM_MATCH_MIN_CHARS


def _pick_question(
    candidates: list[InterviewQuestion],
    used: set[str],
    dims: set[str],
) -> InterviewQuestion | None:
    """Highest-difficulty unused question mapping to any of `dims`."""
    matches = [
        q
        for q in candidates
        if q.question not in used and (_question_dims(q) & dims)
    ]
    if not matches:
        return None
    matches.sort(key=lambda q: _DIFFICULTY_WEIGHT.get(q.difficulty, 0), reverse=True)
    return matches[0]


def _pick_claim_probe(
    candidates: list[InterviewQuestion],
    used: set[str],
    claim: ClaimVerification,
) -> InterviewQuestion | None:
    """Best unused question anchored to `claim` (metric/experience probes first)."""
    matches = [
        q
        for q in candidates
        if q.question not in used and _question_matches_claim(q, claim)
    ]
    if not matches:
        return None
    archetype_rank = {"metric_validation": 0, "experience_probe": 1}
    matches.sort(
        key=lambda q: (
            archetype_rank.get(q.archetype, 2),
            -_DIFFICULTY_WEIGHT.get(q.difficulty, 0),
        )
    )
    return matches[0]


def _select_must_ask(dossier: DecisionDossier) -> list[tuple[InterviewQuestion, SelectionReason]]:
    questions = list(dossier.questions)
    used: set[str] = set()
    selected: list[tuple[InterviewQuestion, SelectionReason]] = []

    def take(question: InterviewQuestion | None, reason: SelectionReason) -> None:
        if question is not None and question.question not in used:
            used.add(question.question)
            selected.append((question, reason))

    # 1) questions probing suspicious / needs_probing resume claims (cap 2 so
    #    gaps and scenarios still fit in the slate).
    for claim in _claims_to_probe(dossier):
        if len(selected) >= 2:
            break
        take(_pick_claim_probe(questions, used, claim), "claim_probe")

    # 2) one question per unmet must-have (highest difficulty), weight desc.
    for req in _unmet_must_haves(dossier):
        if len(selected) >= _MUST_ASK_TARGET:
            break
        dims = _text_dims(req.display_label) or set(_DIMENSION_KEYWORDS)
        take(_pick_question(questions, used, dims), "must_have_gap")

    # 3) one question per weakest dimension.
    for dim in _gap_dimensions(dossier):
        if len(selected) >= _MUST_ASK_TARGET - 1:
            break
        take(_pick_question(questions, used, {dim}), "dimension_gap")

    # 4) keep one scenario-design question in the slate when there is room.
    if len(selected) < _MUST_ASK_TARGET and not any(
        q.archetype == "scenario_design" for q, _ in selected
    ):
        scenario = next(
            (
                q
                for q in questions
                if q.question not in used and q.archetype == "scenario_design"
            ),
            None,
        )
        take(scenario, "scenario_coverage")

    # 5) fill remaining slots by difficulty.
    by_difficulty = sorted(
        (q for q in questions if q.question not in used),
        key=lambda q: _DIFFICULTY_WEIGHT.get(q.difficulty, 0),
        reverse=True,
    )
    for question in by_difficulty:
        if len(selected) >= _MUST_ASK_TARGET:
            break
        take(question, "difficulty_fill")

    return selected[:_MUST_ASK_TARGET]


def _claim_item_label(claim: ClaimVerification) -> str:
    head = claim.claim.strip().rstrip("。.")
    if len(head) > 40:
        head = f"{head[:40]}…"
    return f"核实声明「{head}」：{claim.verification_hint}"


def _verification_checklist(dossier: DecisionDossier) -> list[VerificationItem]:
    items: list[VerificationItem] = []

    if dossier.score.injection_detected:
        items.append(VerificationItem(item=_INJECTION_ITEM, reason="injection"))

    for claim in _claims_to_probe(dossier):
        items.append(
            VerificationItem(
                item=_claim_item_label(claim),
                reason="claim_probe",
                evidence_refs=claim.evidence_refs,
            )
        )

    for req in _unmet_must_haves(dossier):
        items.append(
            VerificationItem(
                item=f"请具体说明「{req.display_label}」的满足情况。",
                reason="must_have_gap",
            )
        )

    for follow_up in dossier.follow_ups:
        items.append(
            VerificationItem(
                item=follow_up.question,
                reason="follow_up",
                evidence_refs=follow_up.evidence_refs,
            )
        )

    # Sort risk > must-have > follow-up, then dedupe by text, then cap so the
    # high-priority items always survive the cap.
    items.sort(key=lambda it: _VERIFICATION_PRIORITY[it.reason])
    seen: set[str] = set()
    deduped: list[VerificationItem] = []
    for item in items:
        if item.item in seen:
            continue
        seen.add(item.item)
        deduped.append(item)
    return deduped[:_CHECKLIST_CAP]


def pass_criteria(checklist_len: int) -> str:
    if checklist_len <= 0:
        return "核实关键风险后可调整推荐结论。"
    return (
        f"若以上 {checklist_len} 条核实均有可信、可核对简历或项目的答复，"
        "可将推荐调整为「通过」；否则维持「待定」。"
    )


def build_interview_script(dossier: DecisionDossier) -> InterviewScriptResponse:
    must_ask_raw = _select_must_ask(dossier)
    must_set = {q.question for q, _ in must_ask_raw}

    must_ask = [
        ScriptQuestion(
            index=i + 1,
            question=question,
            suggested_minutes=_suggested_minutes(question),
            selection_reason=reason,
        )
        for i, (question, reason) in enumerate(must_ask_raw)
    ]

    optional_questions = [q for q in dossier.questions if q.question not in must_set]
    optional_questions.sort(
        key=lambda q: _DIFFICULTY_WEIGHT.get(q.difficulty, 0), reverse=True
    )
    optional = [
        ScriptQuestion(
            index=len(must_ask) + i + 1,
            question=question,
            suggested_minutes=_suggested_minutes(question),
        )
        for i, question in enumerate(optional_questions)
    ]

    checklist = _verification_checklist(dossier)
    must_minutes = sum(item.suggested_minutes for item in must_ask)
    suggested_duration_min = must_minutes + 4 * len(dossier.follow_ups) + 5

    return InterviewScriptResponse(
        candidate_id=dossier.candidate_id,
        candidate_name=dossier.candidate_name,
        recommendation=dossier.score.recommendation,
        overall_score=dossier.score.overall_score,
        confidence=dossier.score.confidence,
        confidence_band=confidence_band(dossier.score.confidence),
        suggested_duration_min=suggested_duration_min,
        must_ask=must_ask,
        follow_ups=dossier.follow_ups,
        optional=optional,
        verification_checklist=checklist,
        pass_criteria=pass_criteria(len(checklist)),
    )


# ---- board summary fields (§6.3) ------------------------------------------------

_RUBRIC_CODE_RE = re.compile(r"[（(]\s*[A-Z]{1,3}\d+\s*[)）]")


def _humanize_reason(text: str) -> str:
    return _RUBRIC_CODE_RE.sub("", text).strip()


def decision_summary(dossier: DecisionDossier, limit: int = 60) -> str:
    score = dossier.score
    raw = (
        score.match_reasons[0]
        if score.match_reasons
        else (score.risk_flags[0] if score.risk_flags else dossier.candidate_profile.summary)
    )
    cleaned = _humanize_reason(raw)
    return cleaned[:limit]


def verification_count(dossier: DecisionDossier) -> int:
    if dossier.score.recommendation == "hold":
        return len(_verification_checklist(dossier))
    return len(dossier.candidate_profile.missing_or_ambiguous_claims)
