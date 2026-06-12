from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import BaseModel, Field

from app.core.errors import RepairExhaustedError
from app.llm.prompts import EXTRACT_JD_RUBRIC
from app.llm.structured import (
    _evidence_repair_source_block,
    extract_json_block,
    generate_structured,
)
from app.storage import repository
from tests.conftest import ScriptedProvider, make_workflow_context

FIXTURES = Path(__file__).resolve().parent.parent.parent / "fixtures"


class TinySchema(BaseModel):
    role_title: str = Field(min_length=3)
    seniority: str


VALID = json.dumps({"role_title": "Backend AI Engineer", "seniority": "senior"})
INVALID_JSON = "Sure! Here is the JSON you asked for: {role_title: oops"
WRONG_SHAPE = json.dumps({"role_title": "x"})


def test_extract_json_block_strips_fences_and_prose():
    wrapped = "Here you go:\n```json\n" + VALID + "\n```\nThanks!"
    assert json.loads(extract_json_block(wrapped)) == json.loads(VALID)


def test_first_attempt_valid(app_env):
    repository.create_run("run-ok", "replay", None)
    ctx = make_workflow_context("run-ok", ScriptedProvider([VALID]))
    parsed, meta = generate_structured(
        ctx, EXTRACT_JD_RUBRIC, TinySchema,
        {"jd_document_id": "d1", "jd_text": "irrelevant"},
        node_name="extract_jd_rubric",
    )
    assert parsed.role_title == "Backend AI Engineer"
    assert meta.attempts == 1 and not meta.repaired


def test_repair_loop_recovers_from_malformed_json(app_env):
    repository.create_run("run-repair", "replay", None)
    provider = ScriptedProvider([INVALID_JSON, VALID])
    ctx = make_workflow_context("run-repair", provider)
    parsed, meta = generate_structured(
        ctx, EXTRACT_JD_RUBRIC, TinySchema,
        {"jd_document_id": "d1", "jd_text": "irrelevant"},
        node_name="extract_jd_rubric",
    )
    assert parsed.seniority == "senior"
    assert meta.attempts == 2 and meta.repaired
    events = {e.event_type for e in repository.get_events("run-repair")}
    assert {"schema_validation_failed", "repair_attempted", "repair_succeeded"} <= events
    summaries = repository.get_validation_summaries("run-repair")
    assert summaries[-1].status == "repaired"


def test_repair_exhaustion_raises_and_records(app_env):
    repository.create_run("run-fail", "replay", None)
    ctx = make_workflow_context("run-fail", ScriptedProvider([WRONG_SHAPE]))
    with pytest.raises(RepairExhaustedError) as excinfo:
        generate_structured(
            ctx, EXTRACT_JD_RUBRIC, TinySchema,
            {"jd_document_id": "d1", "jd_text": "irrelevant"},
            node_name="extract_jd_rubric",
        )
    assert excinfo.value.attempts == 3  # 1 initial + MAX_REPAIR_ATTEMPTS
    events = [e.event_type for e in repository.get_events("run-fail")]
    assert events.count("schema_validation_failed") == 3
    assert "repair_failed" in events
    summaries = repository.get_validation_summaries("run-fail")
    assert summaries[-1].status == "failed"


def test_repair_appends_to_original_messages(app_env):
    repository.create_run("run-append", "replay", None)
    provider = ScriptedProvider([INVALID_JSON, VALID])
    ctx = make_workflow_context("run-append", provider)
    generate_structured(
        ctx,
        EXTRACT_JD_RUBRIC,
        TinySchema,
        {"jd_document_id": "d1", "jd_text": "source text stays visible"},
        node_name="extract_jd_rubric",
    )
    assert provider.calls == 2
    second_call = provider.call_messages[1]
    assert len(second_call) == 4
    assert second_call[0]["content"] == EXTRACT_JD_RUBRIC.system
    assert "source text stays visible" in second_call[1]["content"]
    assert second_call[2]["role"] == "assistant"
    assert second_call[3]["role"] == "user"
    assert "校验错误" in second_call[3]["content"]


def test_post_validate_problems_trigger_repair(app_env):
    repository.create_run("run-post", "replay", None)
    ctx = make_workflow_context("run-post", ScriptedProvider([VALID, VALID]))

    seen: list[int] = []

    def post_validate(_parsed: TinySchema) -> list[str]:
        seen.append(1)
        return ["evidence snippet not found verbatim"] if len(seen) == 1 else []

    parsed, meta = generate_structured(
        ctx, EXTRACT_JD_RUBRIC, TinySchema,
        {"jd_document_id": "d1", "jd_text": "irrelevant"},
        node_name="extract_jd_rubric",
        post_validate=post_validate,
    )
    assert meta.repaired and meta.attempts == 2
    assert parsed.role_title == "Backend AI Engineer"


def test_evidence_repair_source_block_points_to_valid_line_range():
    numbered_resume = "[R1] 南京理工大学 211 双一流\n[R2] 计算机科学与技术 硕士 全日制"
    block = _evidence_repair_source_block(
        {"resume_text": numbered_resume},
        ["证据引用行号无效：source_type=resume 的 line_no=99 不存在（有效范围 1 至 2）。"],
    )
    assert "R1 至 R2" in block
    assert "本对话第一条用户消息" in block
    # the numbered source is not re-embedded (stays in the first user message)
    assert "南京理工大学" not in block


def test_evidence_repair_source_block_empty_when_not_a_line_problem():
    block = _evidence_repair_source_block(
        {"resume_text": "[R1] a sufficiently long resume line here"},
        ["维度「required_skills」的 band=strong 与 score=10 区间不一致"],
    )
    assert block == ""
