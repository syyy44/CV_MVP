from __future__ import annotations

from app.models.contracts import InterviewQuestion
from app.workflows.steps import pack_quality_problems


def _question(
    archetype: str,
    target_claim: str,
    *,
    text: str = "请复原该项目的完整链路、关键字段和异常处理过程？",
) -> InterviewQuestion:
    return InterviewQuestion(
        question=text,
        archetype=archetype,  # type: ignore[arg-type]
        target_claim=target_claim,
        competency="声明核查",
        difficulty="senior",
        follow_up_probes=["请给出具体字段。", "异常情况怎么处理？"],
        scoring_criteria=["能复原关键字段", "能解释异常处理"],
        good_answer_signals=["能给出可交叉验证的细节"],
        red_flags=["只复述概念"],
    )


def test_pack_quality_requires_high_priority_claim_coverage():
    questions = [
        _question("experience_probe", "新增调用 LLM API 的聊天机器人功能"),
        _question("metric_validation", "新增调用 LLM API 的聊天机器人功能"),
        _question("depth_probe", "新增调用 LLM API 的聊天机器人功能"),
        _question("failure_review", "新增调用 LLM API 的聊天机器人功能"),
        _question("experience_probe", "新增调用 LLM API 的聊天机器人功能"),
        _question("scenario_design", ""),
        _question("jd_fit", ""),
        _question("depth_probe", "新增调用 LLM API 的聊天机器人功能"),
    ]

    problems = pack_quality_problems(
        questions,
        required_claims=["独立将推荐平台扩展至 5000 万用户规模"],
    )

    assert any("没有被任何 questions.target_claim 覆盖" in p for p in problems)


def test_pack_quality_accepts_matching_high_priority_claim():
    questions = [
        _question("experience_probe", "新增调用 LLM API 的聊天机器人功能"),
        _question("metric_validation", "独立将推荐平台扩展至 5000 万用户规模"),
        _question("depth_probe", "新增调用 LLM API 的聊天机器人功能"),
        _question("failure_review", "新增调用 LLM API 的聊天机器人功能"),
        _question("experience_probe", "新增调用 LLM API 的聊天机器人功能"),
        _question("scenario_design", ""),
        _question("jd_fit", ""),
        _question("depth_probe", "新增调用 LLM API 的聊天机器人功能"),
    ]

    problems = pack_quality_problems(
        questions,
        required_claims=["独立将推荐平台扩展至 5000 万用户规模"],
    )

    assert not any("没有被任何 questions.target_claim 覆盖" in p for p in problems)
