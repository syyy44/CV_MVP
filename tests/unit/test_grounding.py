"""Unit tests for the deterministic grounding guards.

Covers bilingual tokenization, the overlap-coefficient relevance signal, the
significant-number extractor and grounding, and the repair-problem builders.
The thresholds asserted here mirror the calibration over the real fixtures
(claim_verifications overlap their evidence ~1.0; misattributions ~0).
"""

from __future__ import annotations

from app.models.contracts import EvidenceSpan
from app.workflows.grounding import (
    claim_number_problems,
    lexical_tokens,
    numeric_cores,
    quantified_claim_problems,
    relevance,
    significant_numbers,
    support_relevance_problems,
    ungrounded_numbers,
)


def _span(snippet: str) -> EvidenceSpan:
    return EvidenceSpan(
        document_id="d",
        document_hash="h",
        source_type="resume",
        snippet=snippet,
        offset_status="verified",
    )


# --- tokenization & relevance ---------------------------------------------------


def test_lexical_tokens_mixes_ascii_words_and_cjk_bigrams():
    tokens = lexical_tokens("使用 LangGraph 编排")
    assert "langgraph" in tokens  # ascii word, lowercased
    assert "编排" in tokens  # cjk bigram
    assert "a" not in tokens  # single ascii char dropped


def test_relevance_identical_is_one_and_unrelated_is_low():
    line = "设计基于 LangGraph 的文档筛选工作流，包含校验与修复节点"
    assert relevance(line, line) == 1.0
    assert relevance("优化前端结账漏斗的 Core Web Vitals 指标", line) < 0.34


def test_relevance_paraphrase_stays_above_threshold():
    line = "构建并运维日均 40000 次请求的生产级 FastAPI 服务"
    claim = "运维生产级 FastAPI 服务，日均 40000 次请求"
    assert relevance(claim, line) >= 0.34


def test_relevance_handles_english():
    line = "Operates FastAPI services processing shipping documents for clients"
    assert relevance("Operates FastAPI services for shipping documents", line) >= 0.34
    assert relevance("Maintains jQuery and WordPress marketing sites", line) < 0.34


# --- numeric extraction & grounding ---------------------------------------------


def test_significant_numbers_keeps_metrics_drops_bare_single_digits():
    nums = significant_numbers("3 人团队，成功率 63.8% 提升至 81.9%，时延下降 53%")
    assert "63.8" in nums and "81.9" in nums and "53" in nums
    assert "3" not in nums  # bare single digit excluded


def test_significant_numbers_keeps_magnitude_units_and_thousands():
    assert "5000" in significant_numbers("扩展至 5000 万用户")
    assert "50" in significant_numbers("scaled to 50 million users")
    assert "12345" in significant_numbers("处理 12,345 条记录")  # thousands separator


def test_numeric_cores_normalizes_fullwidth_and_separators():
    cores = numeric_cores("营收 １,２３４ 万，占比 12.5%")
    assert "1234" in cores
    assert "12.5" in cores


def test_ungrounded_numbers_flags_only_absent_significant_numbers():
    source = "构建并运维日均 40000 次请求的服务，团队 3 人"
    assert ungrounded_numbers("日均 40000 次请求", source) == []
    assert ungrounded_numbers("成功率提升 88%", source) == ["88"]
    # a fabricated value not anywhere in source
    assert ungrounded_numbers("扩展至 99999 规模", source) == ["99999"]


def test_ungrounded_numbers_searches_all_sources():
    jd = "要求处理日均 40000 次请求"
    resume = "负责后端服务的稳定性"
    assert ungrounded_numbers("日均 40000 次请求", jd, resume) == []


# --- problem builders -----------------------------------------------------------


class _Project:
    def __init__(self, name, quantified_claims):
        self.name = name
        self.quantified_claims = quantified_claims


def test_quantified_claim_problems_flags_fabricated_metric():
    resume = "端到端成功率由 63.8% 提升至 81.9%，时延下降 53%"
    clean = _Project("RAG", ["成功率由 63.8% 提升至 81.9%"])
    assert quantified_claim_problems([clean], resume) == []

    fabricated = _Project("RAG", ["时延下降 73%"])  # 73 not in resume
    problems = quantified_claim_problems([fabricated], resume)
    assert len(problems) == 1
    assert "73" in problems[0]


def test_claim_number_problems_requires_absence_in_all_sources():
    jd = "招聘后端工程师"
    resume = "构建处理日均 40000 次请求的服务"
    assert claim_number_problems(["日均 40000 次请求"], jd, resume) == []
    problems = claim_number_problems(["独立扩展至 5000 万用户"], jd, resume)
    assert len(problems) == 1 and "5000" in problems[0]


def test_support_relevance_problems_flags_misattributed_citation():
    units = [
        ("设计基于 LangGraph 的文档筛选工作流，包含校验与修复节点",
         [_span("优化前端结账漏斗的 Core Web Vitals 指标")]),
    ]
    problems = support_relevance_problems(units, label="claim_verifications", min_relevance=0.34)
    assert len(problems) == 1
    assert "几乎无关" in problems[0]


def test_support_relevance_problems_passes_when_one_cited_line_is_relevant():
    line = "设计基于 LangGraph 的文档筛选工作流，包含校验与修复节点"
    units = [
        (line, [_span("优化前端无关行，长度需要足够长以满足片段约束"), _span(line)]),
    ]
    assert support_relevance_problems(units, label="claim_verifications", min_relevance=0.34) == []


def test_support_relevance_problems_skips_units_without_resolved_spans():
    # No spans resolved -> resolution layer already reported it; do not double-flag.
    units = [("任意声明", [])]
    assert support_relevance_problems(units, label="claim_verifications", min_relevance=0.34) == []
