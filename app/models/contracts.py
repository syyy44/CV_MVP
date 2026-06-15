"""Pydantic domain contracts.

These models are the hard boundary for LLM output and the shape of every
persisted/exported artifact. LLM-facing draft models live in `drafts.py`;
this module holds the resolved, trusted contracts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.locale import zh_CN as msg

ParseStatus = Literal[
    "pending_ingest",
    "parsed",
    "unsupported_file_type",
    "parse_failed",
    "empty_text",
    "encrypted_pdf",
    "scanned_pdf_requires_text_upload",
    "candidate_parse_failed",
]

RunStatus = Literal["queued", "running", "completed", "needs_review", "failed"]
Recommendation = Literal["proceed", "hold", "reject"]
SourceType = Literal["jd", "resume"]

EVIDENCE_SNIPPET_MIN_LENGTH = 12


class EvidenceContextLine(BaseModel):
    line_no: int = Field(ge=1)
    text: str = Field(min_length=1, max_length=2000)
    is_focus: bool = False


class EvidenceSpan(BaseModel):
    document_id: str
    document_hash: str
    source_type: SourceType
    snippet: str = Field(
        min_length=EVIDENCE_SNIPPET_MIN_LENGTH,
        max_length=2000,
    )
    page_number: int | None = Field(default=None, ge=1)
    section: str | None = None
    line_no: int | None = Field(default=None, ge=1)
    char_start: int | None = Field(default=None, ge=0)
    char_end: int | None = Field(default=None, ge=0)
    offset_status: Literal["verified", "approximate", "unavailable"]
    requirement_id: str | None = None
    context_lines: list[EvidenceContextLine] = Field(default_factory=list)


class RubricRequirement(BaseModel):
    id: str = Field(
        min_length=2,
        max_length=12,
        description="必备项编号 MH1..MHn；加分项编号 NH1..NHn。",
    )
    text: str = Field(
        min_length=8,
        description="基于 JD 的要求文本，不得编造要求。",
    )
    severity_penalty: int = Field(
        default=10,
        ge=8,
        le=15,
        description="缺失该必备项时从候选人加权总分中直接扣除的分值（8-15）；越关键扣越多。",
    )


class EvaluationWeights(BaseModel):
    required_skills: float = Field(
        default=0.35,
        description="必备技能权重；各权重之和须为 1.0。",
    )
    preferred_skills: float = Field(
        default=0.15,
        description="加分技能权重；各权重之和须为 1.0。",
    )
    experience_relevance: float = Field(
        default=0.20,
        description="经历相关性权重；各权重之和须为 1.0。",
    )
    project_depth: float = Field(
        default=0.15,
        description="项目深度权重；各权重之和须为 1.0。",
    )
    ai_engineering_maturity: float = Field(
        default=0.10,
        description="AI 工程成熟度权重；各权重之和须为 1.0。",
    )
    communication_clarity: float = Field(
        default=0.05,
        description="表达清晰度权重；各权重之和须为 1.0。",
    )

    @model_validator(mode="after")
    def _weights_sum_to_one(self) -> EvaluationWeights:
        total = (
            self.required_skills
            + self.preferred_skills
            + self.experience_relevance
            + self.project_depth
            + self.ai_engineering_maturity
            + self.communication_clarity
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(msg.evaluation_weights_must_sum(total))
        return self


class JobRubric(BaseModel):
    role_title: str = Field(
        min_length=3,
        description="从 JD 提取的岗位名称。",
    )
    must_have_requirements: list[RubricRequirement] = Field(
        min_length=1,
        description=(
            "JD 明确或强隐含的非协商必备要求（MH*）；"
            "缺失会按 severity_penalty 扣分，只收录真正硬性的要求。"
        ),
    )
    nice_to_have_requirements: list[RubricRequirement] = Field(
        default_factory=list,
        description="JD 中的加分但非必备要求。",
    )
    deal_breakers: list[str] = Field(
        default_factory=list,
        description="一票否决条件，存在时须逐字引用 JD；候选人命中任一会被封顶在 59 分（reject）。",
    )
    seniority_expectations: str | None = Field(
        default=None,
        description="JD 中的职级或职责范围预期。",
    )
    domain_signals: list[str] = Field(
        default_factory=list,
        description="定义该岗位的领域、技术栈或问题空间关键词。",
    )
    evaluation_weights: EvaluationWeights = Field(
        default_factory=EvaluationWeights,
        description="各评分维度相对权重，之和须为 1.0。",
    )


class WorkExperience(BaseModel):
    title: str
    company: str
    duration: str
    highlights: list[str] = []


class ProjectItem(BaseModel):
    name: str
    description: str
    source_work_experience: str = Field(
        default="",
        description="该项目所属的工作经历；用于让面试官把项目锚回具体任职阶段。",
    )
    technologies: list[str] = []
    role_in_project: str = Field(
        default="",
        description="候选人在该项目中的职责边界，按简历措辞（如「独立设计」「负责检索模块」「参与」）。",
    )
    quantified_claims: list[str] = Field(
        default_factory=list,
        description="该项目中的量化结果声明原文（如「成功率 63.8%→81.9%」），面试口径核查的锚点。",
    )
    tech_decisions: list[str] = Field(
        default_factory=list,
        description="候选人声称做出的关键技术选型（如 LangGraph、Milvus、SSE、LoRA）。",
    )


class EducationItem(BaseModel):
    school: str
    degree: str = ""
    major: str = ""
    start_date: str = ""
    end_date: str = ""
    gpa: str | None = None
    highlights: list[str] = []

class CandidateProfile(BaseModel):
    candidate_name: str = Field(min_length=2)
    summary: str = Field(min_length=20)
    skills: list[str] = Field(min_length=1)
    work_experiences: list[WorkExperience] = []
    projects: list[ProjectItem] = []
    education: list[EducationItem] = []
    certifications: list[str] = []
    evidence_spans: list[EvidenceSpan] = Field(min_length=1)
    missing_or_ambiguous_claims: list[str] = []

    @field_validator("education", mode="before")
    @classmethod
    def _coerce_education_list(cls, value: object) -> object:
        if not isinstance(value, list):
            return value
        from app.models.education import coerce_education_item

        return [coerce_education_item(item).model_dump() for item in value]


class CandidateSubScores(BaseModel):
    required_skills: int = Field(
        ge=0,
        le=100,
        description="必备技能覆盖度，0-100。",
    )
    preferred_skills: int = Field(
        ge=0,
        le=100,
        description="加分技能覆盖度，0-100。",
    )
    experience_relevance: int = Field(
        ge=0,
        le=100,
        description="经历与岗位相关性，0-100。",
    )
    project_depth: int = Field(
        ge=0,
        le=100,
        description="项目深度与 ownership，0-100。",
    )
    ai_engineering_maturity: int = Field(
        ge=0,
        le=100,
        description="AI/LLM 工程实践成熟度，0-100。",
    )
    communication_clarity: int = Field(
        ge=0,
        le=100,
        description="简历表达清晰度，0-100。",
    )


class RequirementResult(BaseModel):
    """Per-must-have outcome, derived from rubric + analysis at score time.

    Carries a human `display_label` so the UI never surfaces raw rubric codes
    (UX-014) and the interview-script builder can target unmet must-haves.
    """

    requirement_id: str
    display_label: str
    kind: Literal["must_have"] = "must_have"
    met: bool
    weight: int = Field(ge=0, description="severity_penalty of the requirement")
    jd_evidence_refs: list[EvidenceSpan] = Field(
        default_factory=list,
        description="候选人无关的 JD 原文引用，稳定说明该必备项来自职位描述的哪几行。",
    )


ClaimCredibility = Literal["well_supported", "plausible", "needs_probing", "suspicious"]
ScoreDimensionKey = Literal[
    "required_skills",
    "preferred_skills",
    "experience_relevance",
    "project_depth",
    "ai_engineering_maturity",
    "communication_clarity",
]


class ScoreDimensionExplanation(BaseModel):
    key: ScoreDimensionKey
    score: int = Field(ge=0, le=100)
    band: Literal["strong", "adequate", "weak", "absent"]
    weight: float = Field(ge=0, le=1)
    weighted_points: float = Field(ge=0)
    rationale: str


class ScorePenaltyExplanation(BaseModel):
    kind: str
    points: int = Field(ge=0)
    explanation: str
    requirement_id: str | None = None


class ScoreBreakdownExplanation(BaseModel):
    base_score: float = Field(ge=0, le=100)
    penalties: list[ScorePenaltyExplanation] = Field(default_factory=list)
    capped_by_deal_breaker: bool = False
    final_score: int = Field(ge=0, le=100)
    recommendation_rule: str


class ScoreExplanation(BaseModel):
    verdict_summary: str = ""
    fit_reasons: list[str] = Field(default_factory=list)
    gap_reasons: list[str] = Field(default_factory=list)
    verification_priorities: list[str] = Field(default_factory=list)
    confidence_rationale: str = ""
    dimensions: list[ScoreDimensionExplanation] = Field(default_factory=list)
    breakdown: ScoreBreakdownExplanation | None = None


class ClaimVerification(BaseModel):
    """简历关键声明的可信度核查（评分阶段产出）。

    驱动两件事：评分依据更可解释（声明 ≠ 证据），以及面试题生成器据此
    设计口径拆解/经历复原题。不直接参与分数计算。
    """

    claim: str = Field(min_length=6, description="简历中的关键声明（量化结果或核心技术声明）。")
    credibility: ClaimCredibility = Field(
        description=(
            "可信度评级：well_supported=有过程细节且口径清楚；plausible=合理但细节不足；"
            "needs_probing=结果数字漂亮但口径/基线/测量方式不明；"
            "suspicious=与简历他处矛盾、夸大嫌疑或术语堆砌无实现细节。"
        ),
    )
    reason: str = Field(min_length=8, description="评级依据（有无过程性细节、口径是否可复现）。")
    verification_hint: str = Field(
        min_length=8,
        description="面试中验证该声明的具体方式（问什么口径、要求复原什么细节）。",
    )
    evidence_refs: list[EvidenceSpan] = Field(default_factory=list)


class CandidateScore(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    recommendation: Recommendation
    confidence: float = Field(ge=0, le=1)
    sub_scores: CandidateSubScores
    match_reasons: list[str] = Field(min_length=3)
    risk_flags: list[str] = []
    evidence_refs: list[EvidenceSpan] = Field(min_length=3)
    requirement_results: list[RequirementResult] = Field(
        default_factory=list,
        description="必备要求的逐项满足结果，供看板/脚本使用；旧数据为空。",
    )
    claim_verifications: list[ClaimVerification] = Field(
        default_factory=list,
        description="简历关键声明的可信度核查清单；旧数据为空。",
    )
    score_explanation: ScoreExplanation = Field(
        default_factory=ScoreExplanation,
        description="面向面试官的结构化评分解释；旧数据为空对象。",
    )
    injection_detected: bool = Field(
        default=False,
        description="是否检测到 prompt 注入类风险（用于 hold 核实清单）。",
    )


QuestionArchetype = Literal[
    "experience_probe",  # 经历复原：现场画/写出架构、状态 schema、训练样本、数据流
    "metric_validation",  # 口径核查：指标定义、baseline、测试集、P50/P95、负向指标
    "depth_probe",  # 技术深挖：为什么不用替代方案、底层机制、边界与异常
    "failure_review",  # 失败复盘：现象、日志、定位、根因、修复、指标变化
    "scenario_design",  # 场景设计：贴 JD 业务的现场推演（模糊需求拆解、权衡排序）
    "jd_fit",  # JD 匹配：经验向岗位场景的迁移能力
]


class InterviewQuestion(BaseModel):
    question: str = Field(
        min_length=12,
        description=(
            "主问题。必须是复原/举例/口径/复盘/推演式提问，"
            "禁止「请解释 X 概念」式可背诵的概念题。"
        ),
    )
    archetype: QuestionArchetype = Field(
        default="depth_probe",
        description=(
            "题型：experience_probe=经历复原；metric_validation=指标口径核查；"
            "depth_probe=技术深挖与取舍；failure_review=失败案例复盘；"
            "scenario_design=贴 JD 的现场场景设计；jd_fit=经验向 JD 迁移。"
        ),
    )
    target_claim: str = Field(
        default="",
        description=(
            "该题锚定的简历声明原文（项目、数字或技术选型）；"
            "experience_probe/metric_validation/depth_probe/failure_review 必填，"
            "scenario_design/jd_fit 可为空字符串。"
        ),
    )
    competency: str = Field(
        min_length=3,
        description="该题考察的能力或技能领域。",
    )
    difficulty: Literal["junior", "mid", "senior", "expert"] = Field(
        description="相对岗位职级的预期难度。"
    )
    follow_up_probes: list[str] = Field(
        default_factory=list,
        description=(
            "2-4 条递进追问链，一条比一条深："
            "从整体描述 → 具体字段/数据/样本 → 边界与异常 → trade-off 或重来怎么改。"
            "候选人答得越顺，越要沿链下钻。"
        ),
    )
    scoring_criteria: list[str] = Field(
        min_length=1,
        description="完整回答应覆盖的要点（含追问链的期望深度）。",
    )
    good_answer_signals: list[str] = Field(
        min_length=1,
        description=(
            "「真做过」的信号：能说出具体字段名/表结构/样本/失败案例/口径定义，"
            "能承认局限与未做的部分，能解释取舍。"
        ),
    )
    red_flags: list[str] = Field(
        default_factory=list,
        description=(
            "「背诵/包装」的信号：只复述框架名词与概念、说不清指标口径、"
            "声称一切顺利没有失败、所有问题都答「靠 prompt 优化解决」。"
        ),
    )


class FollowUpQuestion(BaseModel):
    question: str = Field(min_length=12)
    ambiguity: str = Field(min_length=8)
    what_to_listen_for: str = Field(min_length=8)
    evidence_refs: list[EvidenceSpan] = Field(min_length=1)


class ValidationSummary(BaseModel):
    schema_name: str
    node_name: str
    candidate_id: str | None = None
    status: Literal["valid", "repaired", "failed"]
    error_count: int = 0
    repair_attempts: int = 0
    messages: list[str] = []


class DecisionDossier(BaseModel):
    status: Literal["completed"] = "completed"
    candidate_id: str
    candidate_name: str
    candidate_profile: CandidateProfile
    score: CandidateScore
    questions: list[InterviewQuestion] = Field(min_length=8)
    follow_ups: list[FollowUpQuestion] = Field(min_length=3, max_length=5)
    validation_summaries: list[ValidationSummary] = []
    trace_url: str | None = None


class NeedsReviewDossier(BaseModel):
    status: Literal["needs_review"] = "needs_review"
    candidate_id: str
    candidate_name: str | None = None
    partial_profile: CandidateProfile | None = None
    partial_sub_scores: CandidateSubScores | None = None
    validation_summaries: list[ValidationSummary] = []
    repair_attempt_count: int = 0
    missing_fields: list[str] = []
    reviewer_message: str
    trace_url: str | None = None


ConfidenceBand = Literal["high", "medium", "low"]


class HumanOverride(BaseModel):
    recommendation: Recommendation
    rationale: str
    actor: str = "human"
    at: datetime


class CandidateNote(BaseModel):
    id: int | None = None
    candidate_id: str
    run_id: str
    body: str = Field(min_length=1, max_length=4000)
    author: str = "面试官"
    created_at: datetime


class CandidateRunResult(BaseModel):
    candidate_id: str
    candidate_name: str | None = None
    status: Literal["completed", "needs_review", "failed"]
    dossier: DecisionDossier | NeedsReviewDossier | None = None
    errors: list[str] = []
    # Derived board-summary fields (§4.1 / §6.3); populated on read, not persisted.
    decision_summary: str | None = None
    risk_count: int = 0
    verification_count: int = 0
    confidence_band: ConfidenceBand | None = None
    human_override: HumanOverride | None = None


class RunMetrics(BaseModel):
    llm_calls: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cost_estimate_usd: float = 0.0
    duration_s: float = 0.0


class RunSummary(BaseModel):
    run_id: str
    status: RunStatus
    mode: Literal["live", "replay", "eval"]
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    error: str | None = None
    metrics: RunMetrics | None = None


class DocumentSummary(BaseModel):
    document_id: str
    run_id: str
    source_type: SourceType
    filename: str
    parse_status: ParseStatus
    document_hash: str | None = None
    char_count: int = 0
    preview: str = ""


# ---- 1v1 comparison (compare.v1) ------------------------------------------------
# Facts are reused from each dossier; relative verdicts are regenerated against
# the shared run rubric (same JD). Absolute per-candidate scores are kept only as
# a labelled reference anchor — never as the head-to-head verdict.

CompareMargin = Literal["decisive", "clear", "slight", "even"]
ComparePick = Literal["a", "b", "either", "neither"]
CompareConfidence = Literal["clear", "leaning", "too_close"]
CompareWinner = Literal["a", "b", "tie"]
CompareSideRef = Literal["a", "b"]
CompareScoreBand = Literal["strong", "adequate", "weak", "absent"]


class CompareSide(BaseModel):
    candidate_id: str
    candidate_name: str
    overall_score_ref: int = Field(
        ge=0, le=100, description="独立标定的总分，仅作参考锚点，不参与胜负裁决。"
    )
    recommendation_ref: Recommendation
    confidence_ref: float = Field(ge=0, le=1)


class DimensionComparison(BaseModel):
    key: ScoreDimensionKey
    label: str
    weight: float = Field(ge=0, le=1)
    a_score_ref: int = Field(ge=0, le=100)
    b_score_ref: int = Field(ge=0, le=100)
    a_band: CompareScoreBand
    b_band: CompareScoreBand
    winner: CompareWinner
    margin: CompareMargin
    rationale: str = Field(default="", description="该维度的相对裁决理由（A↔B）。")
    a_basis: str = Field(default="", description="复用 A 的独立维度评分依据（事实）。")
    b_basis: str = Field(default="", description="复用 B 的独立维度评分依据（事实）。")


class MustHaveFaceOff(BaseModel):
    requirement_id: str
    display_label: str
    a_met: bool
    b_met: bool


class CompareDifferentiator(BaseModel):
    favors: CompareSideRef
    dimension: ScoreDimensionKey | None = None
    text: str


class ScenarioFit(BaseModel):
    prefer: CompareSideRef
    when: str


class VerificationFocus(BaseModel):
    item: str
    why_it_matters: str = ""
    could_flip: bool = False


class CompareVerdict(BaseModel):
    pick: ComparePick
    confidence: CompareConfidence
    headline: str
    rationale: str = ""
    tie_breaker: str = ""
    would_change_if: str = ""
    overridden_by_rule: str = Field(
        default="", description="若确定性硬规则覆盖了模型选择（如一票否决），记录原因。"
    )


class CandidateComparison(BaseModel):
    schema_version: Literal["compare.v1"] = "compare.v1"
    run_id: str
    role_title: str = ""
    generated_with: Literal["llm", "deterministic"] = "deterministic"
    a: CompareSide
    b: CompareSide
    verdict: CompareVerdict
    differentiators: list[CompareDifferentiator] = Field(default_factory=list)
    dimensions: list[DimensionComparison] = Field(default_factory=list)
    must_haves: list[MustHaveFaceOff] = Field(default_factory=list)
    a_unique_strengths: list[str] = Field(default_factory=list)
    b_unique_strengths: list[str] = Field(default_factory=list)
    a_risks: list[str] = Field(default_factory=list)
    b_risks: list[str] = Field(default_factory=list)
    scenario_fit: list[ScenarioFit] = Field(default_factory=list)
    verification_focus: list[VerificationFocus] = Field(default_factory=list)
