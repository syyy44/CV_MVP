from __future__ import annotations

from app.models.contracts import (
    CandidateProfile,
    CandidateScore,
    CandidateSubScores,
    ClaimVerification,
    DecisionDossier,
    EvidenceSpan,
    FollowUpQuestion,
    InterviewQuestion,
    RequirementResult,
)
from app.workflows.interview_script import (
    build_interview_script,
    confidence_band,
    decision_summary,
    verification_count,
)


def _span(snippet: str = "这是一段可验证的简历证据原文片段示例内容") -> EvidenceSpan:
    return EvidenceSpan(
        document_id="doc-1",
        document_hash="hash",
        source_type="resume",
        snippet=snippet,
        offset_status="verified",
        line_no=1,
    )


def _question(
    competency: str,
    difficulty: str,
    text: str | None = None,
    *,
    archetype: str = "depth_probe",
    target_claim: str = "",
) -> InterviewQuestion:
    return InterviewQuestion(
        question=text or f"请详细说明你在{competency}方面的经验与做法？",
        archetype=archetype,  # type: ignore[arg-type]
        target_claim=target_claim,
        competency=competency,
        difficulty=difficulty,  # type: ignore[arg-type]
        follow_up_probes=["追问一：请给出具体字段。", "追问二：异常情况怎么处理？"],
        scoring_criteria=["要点 A", "要点 B"],
        good_answer_signals=["信号 A"],
        red_flags=["红旗 A"],
    )


def _follow_up(question: str) -> FollowUpQuestion:
    return FollowUpQuestion(
        question=question,
        ambiguity="存在模糊点需要澄清",
        what_to_listen_for="关注是否给出可验证细节",
        evidence_refs=[_span()],
    )


def _dossier(
    *,
    recommendation: str = "hold",
    sub_scores: CandidateSubScores,
    questions: list[InterviewQuestion],
    follow_ups: list[FollowUpQuestion],
    requirement_results: list[RequirementResult] | None = None,
    claim_verifications: list[ClaimVerification] | None = None,
    injection: bool = False,
    confidence: float = 0.62,
    missing_claims: list[str] | None = None,
) -> DecisionDossier:
    profile = CandidateProfile(
        candidate_name="陈浩",
        summary="后端工程师，具备 Python 与 FastAPI 经验，LLM 方向尚浅。",
        skills=["Python", "FastAPI"],
        evidence_spans=[_span()],
        missing_or_ambiguous_claims=missing_claims or [],
    )
    score = CandidateScore(
        overall_score=63,
        recommendation=recommendation,  # type: ignore[arg-type]
        confidence=confidence,
        sub_scores=sub_scores,
        match_reasons=["具备 Python 与 FastAPI 基础", "测试纪律良好", "LLM 经验早期"],
        risk_flags=["简历嵌入指令试图操纵评分"] if injection else [],
        evidence_refs=[
            _span(),
            _span("第二条可验证的证据原文片段示例内容"),
            _span("第三条可验证的证据原文片段示例内容"),
        ],
        requirement_results=requirement_results or [],
        claim_verifications=claim_verifications or [],
        injection_detected=injection,
    )
    return DecisionDossier(
        candidate_id="cand-1",
        candidate_name="陈浩",
        candidate_profile=profile,
        score=score,
        questions=questions,
        follow_ups=follow_ups,
    )


def _chen_dossier() -> DecisionDossier:
    # Mirrors the adversarial_injection demo fixture shape.
    sub = CandidateSubScores(
        required_skills=75,
        preferred_skills=60,
        experience_relevance=70,
        project_depth=65,
        ai_engineering_maturity=60,
        communication_clarity=65,
    )
    questions = [
        _question("LLM 应用工程", "mid"),
        _question("声明核实", "senior"),
        _question("LLM 工作流编排", "mid"),
        _question("LLM 可观测性", "mid"),
        _question("结构化输出可靠性", "mid"),
        _question("服务加固", "mid"),
        _question("测试实践", "mid"),
        _question("LLM 安全", "senior", "若候选人文档含指令要求系统打满分，系统应如何行为？"),
        _question("LLM 评测实践", "mid"),
        _question("运维成熟度", "mid"),
    ]
    follow_ups = [
        _follow_up("推荐平台还有哪些同事参与？"),
        _follow_up("简历中致筛选系统的备注为何存在？"),
        _follow_up("聊天机器人是否有校验、记忆或重试？"),
        _follow_up("转向 LLM 的时间线与产物？"),
    ]
    return _dossier(
        sub_scores=sub,
        questions=questions,
        follow_ups=follow_ups,
        injection=True,
    )


def test_confidence_band_thresholds():
    assert confidence_band(0.9) == "high"
    assert confidence_band(0.85) == "high"
    assert confidence_band(0.7) == "medium"
    assert confidence_band(0.64) == "low"


def test_must_ask_covers_ai_gap_and_injection_question():
    script = build_interview_script(_chen_dossier())
    assert len(script.must_ask) == 4
    competencies = {q.question.competency for q in script.must_ask}
    # ai_engineering_maturity is the lowest priority gap dim; its strongest
    # mapped question is the LLM-safety / injection question.
    assert "LLM 安全" in competencies
    assert any(q.selection_reason == "dimension_gap" for q in script.must_ask)


def test_claim_probe_questions_lead_the_must_ask():
    sub = CandidateSubScores(
        required_skills=70,
        preferred_skills=60,
        experience_relevance=68,
        project_depth=62,
        ai_engineering_maturity=55,
        communication_clarity=65,
    )
    suspicious_claim = ClaimVerification(
        claim="独立将推荐平台扩展至 5000 万用户规模",
        credibility="suspicious",
        reason="无任何架构与分工细节，职责边界存疑。",
        verification_hint="追问用户口径、QPS 与团队分工。",
    )
    probing_claim = ClaimVerification(
        claim="新增调用 LLM API 的聊天机器人功能",
        credibility="needs_probing",
        reason="仅有功能描述，无校验与失败处理细节。",
        verification_hint="要求复原请求链路与失败处理。",
    )
    questions = [
        _question(
            "声明核实",
            "senior",
            "请拆解 5000 万用户声明的口径与你的职责边界？",
            archetype="metric_validation",
            target_claim="独立将推荐平台扩展至 5000 万用户规模",
        ),
        _question(
            "LLM 应用工程",
            "mid",
            "请复原聊天机器人的请求链路与失败处理？",
            archetype="experience_probe",
            target_claim="新增调用 LLM API 的聊天机器人功能",
        ),
        _question(
            "场景设计",
            "senior",
            "请设计一个文档转结构化数据的多步工作流方案？",
            archetype="scenario_design",
        ),
        *[_question(f"能力{i}", "mid") for i in range(5)],
    ]
    dossier = _dossier(
        sub_scores=sub,
        questions=questions,
        follow_ups=[
            _follow_up("第一条需要澄清的追问内容是什么？"),
            _follow_up("第二条需要澄清的追问内容是什么？"),
            _follow_up("第三条需要澄清的追问内容是什么？"),
        ],
        claim_verifications=[probing_claim, suspicious_claim],
    )
    script = build_interview_script(dossier)
    # suspicious sorts before needs_probing; both claim probes selected first.
    assert script.must_ask[0].selection_reason == "claim_probe"
    assert script.must_ask[0].question.archetype == "metric_validation"
    assert script.must_ask[1].selection_reason == "claim_probe"
    # scenario design coverage holds a slot in the slate.
    reasons = {q.selection_reason for q in script.must_ask}
    assert "scenario_coverage" in reasons
    # claim probes appear in the hold verification checklist before follow-ups.
    checklist_reasons = [item.reason for item in script.verification_checklist]
    assert "claim_probe" in checklist_reasons
    assert checklist_reasons.index("claim_probe") < checklist_reasons.index("follow_up")


def test_archetype_minutes_drive_duration():
    sub = CandidateSubScores(
        required_skills=70,
        preferred_skills=60,
        experience_relevance=68,
        project_depth=62,
        ai_engineering_maturity=55,
        communication_clarity=65,
    )
    questions = [
        _question("经历复原", "mid", archetype="experience_probe", target_claim="声明 A"),
        _question("场景设计", "mid", archetype="scenario_design"),
        *[_question(f"能力{i}", "mid") for i in range(6)],
    ]
    dossier = _dossier(
        sub_scores=sub,
        questions=questions,
        follow_ups=[
            _follow_up("第一条需要澄清的追问内容是什么？"),
            _follow_up("第二条需要澄清的追问内容是什么？"),
            _follow_up("第三条需要澄清的追问内容是什么？"),
        ],
    )
    script = build_interview_script(dossier)
    by_text = {q.question.question: q for q in [*script.must_ask, *script.optional]}
    probe = next(q for text, q in by_text.items() if "经历复原" in q.question.competency)
    scenario = next(q for text, q in by_text.items() if "场景设计" in q.question.competency)
    assert probe.suggested_minutes == 12
    assert scenario.suggested_minutes == 12


def test_verification_checklist_not_equal_to_follow_up_count():
    dossier = _chen_dossier()
    script = build_interview_script(dossier)
    # 4 follow-ups + 1 injection insert (capped at 5) -> 5, never plain 4.
    assert len(script.verification_checklist) != len(dossier.follow_ups)
    assert script.verification_checklist[0].reason == "injection"
    assert script.pass_criteria.startswith("若以上 5 条")


def test_unmet_must_have_inserted_into_checklist():
    sub = CandidateSubScores(
        required_skills=40,
        preferred_skills=50,
        experience_relevance=55,
        project_depth=60,
        ai_engineering_maturity=45,
        communication_clarity=70,
    )
    reqs = [
        RequirementResult(
            requirement_id="MH4",
            display_label="使用 Pydantic 强制结构化输出",
            met=False,
            weight=10,
        ),
    ]
    dossier = _dossier(
        sub_scores=sub,
        questions=[
            _question("结构化输出", "senior"),
            *[_question(f"能力{i}", "mid") for i in range(9)],
        ],
        follow_ups=[
            _follow_up("第一条需要澄清的追问内容是什么？"),
            _follow_up("第二条需要澄清的追问内容是什么？"),
            _follow_up("第三条需要澄清的追问内容是什么？"),
        ],
        requirement_results=reqs,
        injection=False,
    )
    script = build_interview_script(dossier)
    reasons = [item.reason for item in script.verification_checklist]
    assert "must_have_gap" in reasons
    # must-have gap sorts before follow-ups.
    assert reasons.index("must_have_gap") < reasons.index("follow_up")


def test_optional_excludes_must_ask_and_orders_by_difficulty():
    script = build_interview_script(_chen_dossier())
    must_set = {q.question.question for q in script.must_ask}
    optional_set = {q.question.question for q in script.optional}
    assert must_set.isdisjoint(optional_set)
    assert len(must_set) + len(optional_set) == 10
    assert len(must_set) == 4


def test_suggested_duration_uses_minutes_model():
    script = build_interview_script(_chen_dossier())
    must_minutes = sum(q.suggested_minutes for q in script.must_ask)
    assert script.suggested_duration_min == must_minutes + 4 * len(script.follow_ups) + 5


def test_decision_summary_truncates_and_strips_codes():
    sub = CandidateSubScores(
        required_skills=90,
        preferred_skills=80,
        experience_relevance=88,
        project_depth=85,
        ai_engineering_maturity=82,
        communication_clarity=80,
    )
    dossier = _dossier(
        recommendation="proceed",
        sub_scores=sub,
        questions=[_question(f"能力{i}", "mid") for i in range(10)],
        follow_ups=[
            _follow_up("第一条需要澄清的追问内容是什么？"),
            _follow_up("第二条需要澄清的追问内容是什么？"),
            _follow_up("第三条需要澄清的追问内容是什么？"),
        ],
        confidence=0.9,
        missing_claims=[],
    )
    dossier.score.match_reasons = ["具备扎实的后端能力 (MH1) 且证据充分"]
    summary = decision_summary(dossier)
    assert "(MH1)" not in summary
    assert len(summary) <= 60


def test_verification_count_proceed_uses_ambiguous_claims():
    sub = CandidateSubScores(
        required_skills=90,
        preferred_skills=80,
        experience_relevance=88,
        project_depth=85,
        ai_engineering_maturity=82,
        communication_clarity=80,
    )
    dossier = _dossier(
        recommendation="proceed",
        sub_scores=sub,
        questions=[_question(f"能力{i}", "mid") for i in range(10)],
        follow_ups=[
            _follow_up("第一条需要澄清的追问内容是什么？"),
            _follow_up("第二条需要澄清的追问内容是什么？"),
            _follow_up("第三条需要澄清的追问内容是什么？"),
        ],
        confidence=0.9,
        missing_claims=[],
    )
    assert verification_count(dossier) == 0
