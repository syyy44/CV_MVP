from __future__ import annotations

from app.models.contracts import EvidenceSpan
from app.models.drafts import EvidenceSpanDraft
from app.workflows.evidence import (
    build_line_index,
    dedupe_spans,
    number_lines,
    render_numbered_source,
    resolve_draft,
    resolve_drafts,
)

RESUME_TEXT = (
    "Li Wei built and operated FastAPI services in production\n"
    "designed a LangGraph document screening workflow with repair nodes\n"
    "x\n"  # too short -> not numbered
    "handling 40k requests per day for three years straight"
)
DOC = {
    "document_id": "doc-resume",
    "document_hash": "hash-resume",
    "text": RESUME_TEXT,
    "page_texts": [RESUME_TEXT],
}
DOCS = {"resume": DOC}


def draft(line_no: int, source_type: str = "resume") -> EvidenceSpanDraft:
    return EvidenceSpanDraft(source_type=source_type, line_no=line_no)


def test_number_lines_skips_short_lines_and_is_stable():
    numbered = number_lines(RESUME_TEXT)
    # the "x" line is below min length and is skipped
    assert [n for n, _, _ in numbered] == [1, 2, 3]
    line_nos = {n: line for n, line, _ in numbered}
    assert line_nos[1].startswith("Li Wei built")
    assert line_nos[2].startswith("designed a LangGraph")
    assert line_nos[3].startswith("handling 40k")


def test_char_start_points_at_verbatim_line():
    for _line_no, line, start in number_lines(RESUME_TEXT):
        assert RESUME_TEXT[start : start + len(line)] == line


def test_render_numbered_source_uses_prefix():
    rendered = render_numbered_source(RESUME_TEXT, "resume")
    assert rendered.splitlines()[0].startswith("[R1] Li Wei built")
    assert "[R3] handling 40k" in rendered
    jd_rendered = render_numbered_source("a sufficiently long jd line here", "jd")
    assert jd_rendered.startswith("[J1] ")


def test_resolve_draft_returns_verbatim_line_as_verified():
    span = resolve_draft(draft(1), DOCS)
    assert isinstance(span, EvidenceSpan)
    assert span.offset_status == "verified"
    assert span.line_no == 1
    assert span.snippet == "Li Wei built and operated FastAPI services in production"
    assert DOC["text"][span.char_start : span.char_end] == span.snippet


def test_resolve_draft_out_of_range_line_is_a_problem():
    outcome = resolve_draft(draft(99), DOCS)
    assert isinstance(outcome, str)
    assert "行号无效" in outcome


def test_unknown_source_type_is_a_problem():
    outcome = resolve_draft(draft(1, source_type="jd"), DOCS)
    assert isinstance(outcome, str)
    assert "不存在的来源类型" in outcome


def test_resolve_drafts_separates_spans_and_problems():
    spans, problems = resolve_drafts([draft(1), draft(99)], DOCS)
    assert len(spans) == 1
    assert len(problems) == 1


def test_build_line_index_maps_numbers_to_verbatim_lines():
    index = build_line_index(DOCS)
    assert index["resume"][1][0] == "Li Wei built and operated FastAPI services in production"
    assert 99 not in index["resume"]


def test_dedupe_spans_by_document_and_normalized_snippet():
    first = resolve_draft(draft(1), DOCS)
    second = resolve_draft(draft(1), DOCS)
    assert isinstance(first, EvidenceSpan) and isinstance(second, EvidenceSpan)
    assert len(dedupe_spans([first, second])) == 1
