from __future__ import annotations

from app.core.errors import LLMProviderError, LLMRateLimitError, LLMTimeoutError
from app.locale import zh_CN as msg
from app.workflows.nodes import _halt


def test_llm_timeout_halts_as_needs_review():
    state = {"repair_attempts": 0}
    out = _halt(state, LLMTimeoutError(msg.llm_timeout(120)))
    assert out["halt_kind"] == "needs_review"
    assert "LLM 调用超时" in out["halt_reason"]


def test_llm_rate_limit_halts_as_needs_review():
    state = {"repair_attempts": 1}
    out = _halt(state, LLMRateLimitError(msg.llm_rate_limit()))
    assert out["halt_kind"] == "needs_review"
    assert out["repair_attempts"] == 1


def test_other_domain_errors_still_fail():
    state = {"repair_attempts": 0}
    out = _halt(state, LLMProviderError(msg.llm_provider_error("boom")))
    assert out["halt_kind"] == "failed"
