"""Pydantic domain contracts.

These models are the hard boundary for LLM output and the shape of every
persisted/exported artifact. LLM-facing draft models live in `drafts.py`;
this module holds the resolved, trusted contracts.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.locale import zh_CN as msg

ParseStatus = Literal[
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
    technologies: list[str] = []


class CandidateProfile(BaseModel):
    candidate_name: str = Field(min_length=2)
    summary: str = Field(min_length=20)
    skills: list[str] = Field(min_length=1)
    work_experiences: list[WorkExperience] = []
    projects: list[ProjectItem] = []
    education: list[str] = []
    certifications: list[str] = []
    evidence_spans: list[EvidenceSpan] = Field(min_length=1)
    missing_or_ambiguous_claims: list[str] = []


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


class CandidateScore(BaseModel):
    overall_score: int = Field(ge=0, le=100)
    recommendation: Recommendation
    confidence: float = Field(ge=0, le=1)
    sub_scores: CandidateSubScores
    match_reasons: list[str] = Field(min_length=3)
    risk_flags: list[str] = []
    evidence_refs: list[EvidenceSpan] = Field(min_length=3)


class InterviewQuestion(BaseModel):
    question: str = Field(
        min_length=12,
        description="针对评分标准与候选人背景的面试题。",
    )
    competency: str = Field(
        min_length=3,
        description="该题考察的能力或技能领域。",
    )
    difficulty: Literal["junior", "mid", "senior", "expert"] = Field(
        description="相对岗位职级的预期难度。"
    )
    scoring_criteria: list[str] = Field(
        min_length=1,
        description="完整回答应覆盖的要点。",
    )
    good_answer_signals: list[str] = Field(
        min_length=1,
        description="优秀回答应呈现的信号。",
    )
    red_flags: list[str] = Field(
        default_factory=list,
        description="薄弱或回避性回答的警示信号。",
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
    questions: list[InterviewQuestion] = Field(min_length=10)
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


class CandidateRunResult(BaseModel):
    candidate_id: str
    candidate_name: str | None = None
    status: Literal["completed", "needs_review", "failed"]
    dossier: DecisionDossier | NeedsReviewDossier | None = None
    errors: list[str] = []


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
