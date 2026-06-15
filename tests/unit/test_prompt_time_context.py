from __future__ import annotations

from app.llm.prompts import EXTRACT_CANDIDATE_PROFILE, GENERATE_INTERVIEW_PACK


def _user_content(messages: list[dict]) -> str:
    return next(message["content"] for message in messages if message["role"] == "user")


def test_profile_prompt_includes_evaluation_date():
    content = _user_content(
        EXTRACT_CANDIDATE_PROFILE.render(
            current_date="2026-06-15",
            resume_document_id="resume-1",
            filename="resume.txt",
            resume_text="[R1] 项目时间：2025-07 至 2026-03",
        )
    )

    assert "评估基准日期：2026-06-15" in content
    assert "不要依赖模型内置日期" in content


def test_interview_pack_prompt_includes_evaluation_date():
    content = _user_content(
        GENERATE_INTERVIEW_PACK.render(
            current_date="2026-06-15",
            rubric_json="{}",
            profile_json="{}",
            analysis_json="{}",
            jd_document_id="jd-1",
            jd_text="[J1] 岗位要求",
            resume_document_id="resume-1",
            resume_text="[R1] 项目时间：2025-07 至 2026-03",
        )
    )

    assert "评估基准日期：2026-06-15" in content
    assert "不要依赖模型内置日期" in content

