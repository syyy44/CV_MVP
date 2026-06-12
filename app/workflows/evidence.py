"""Evidence grounding via deterministic indexed quoting.

The model never reproduces source text. Instead, every quotable source line is
deterministically numbered (`R*` for resume, `J*` for JD), the numbered source
is shown to the model, and the model only emits a `line_no`. Code then looks up
the verbatim line by number and builds a trusted `EvidenceSpan`. Because the
quote text is retrieved by code (not round-tripped through the LLM), punctuation,
full/half-width, spacing, ellipsis, and cross-line drift can no longer cause
false "not found" failures, and the snippet shown downstream is always verbatim.

A `line_no` that does not exist for the cited source is a validation problem and
goes back through the repair loop — an uncited claim never reaches a dossier.
"""

from __future__ import annotations

from app.locale import zh_CN as msg
from app.models.contracts import EVIDENCE_SNIPPET_MIN_LENGTH, EvidenceSpan
from app.models.drafts import EvidenceSpanDraft
from app.workflows.parsing import normalize_text

# Line-id prefix per source; the model cites e.g. [R12] (resume) or [J3] (JD).
SOURCE_PREFIX = {"resume": "R", "jd": "J"}


def number_lines(
    text: str,
    *,
    min_len: int = EVIDENCE_SNIPPET_MIN_LENGTH,
) -> list[tuple[int, str, int]]:
    """Deterministically number quotable source lines.

    Returns ``(line_no, verbatim_line, char_start)`` tuples where ``line_no`` is
    1-based and stable for a given text, ``verbatim_line`` is the stripped source
    line, and ``char_start`` indexes the stripped content inside ``text``. Lines
    shorter than ``min_len`` or that look like markup are skipped so every citable
    line is long enough to satisfy the ``EvidenceSpan`` snippet contract.

    This is the single source of truth: both the prompt rendering and the
    resolution lookup call it, guaranteeing the model and the code agree on what
    each number refers to.
    """
    numbered: list[tuple[int, str, int]] = []
    line_no = 0
    cursor = 0
    for raw_line in text.splitlines(keepends=True):
        body = raw_line.rstrip("\n").rstrip("\r")
        stripped = body.strip()
        if (
            stripped
            and len(stripped) >= min_len
            and not stripped.startswith("<!--")
            and not stripped.startswith("<")
        ):
            offset = raw_line.find(stripped)
            char_start = cursor + (offset if offset != -1 else 0)
            line_no += 1
            numbered.append((line_no, stripped, char_start))
        cursor += len(raw_line)
    return numbered


def render_numbered_source(text: str, source_type: str) -> str:
    """Render source text as numbered lines for prompt injection.

    Example output line: ``[R12] 技术栈：Python、FastAPI、LangGraph``.
    """
    prefix = SOURCE_PREFIX.get(source_type, "L")
    return "\n".join(
        f"[{prefix}{line_no}] {line}" for line_no, line, _ in number_lines(text)
    )


def _line_index(text: str) -> dict[int, tuple[str, int]]:
    return {line_no: (line, start) for line_no, line, start in number_lines(text)}


def build_line_index(
    documents_by_type: dict[str, dict],
) -> dict[str, dict[int, tuple[str, int]]]:
    """Map each source type to its ``{line_no: (verbatim_line, char_start)}``."""
    return {
        source_type: _line_index(doc.get("text", ""))
        for source_type, doc in documents_by_type.items()
    }


def quotable_lines(
    text: str,
    *,
    min_len: int = EVIDENCE_SNIPPET_MIN_LENGTH,
    limit: int = 40,
) -> list[str]:
    """Distinct non-trivial source lines (used for diagnostics)."""
    seen: list[str] = []
    for _line_no, line, _start in number_lines(text, min_len=min_len):
        if line not in seen:
            seen.append(line)
        if len(seen) >= limit:
            break
    return seen


def resolve_draft(
    draft: EvidenceSpanDraft, documents_by_type: dict[str, dict]
) -> EvidenceSpan | str:
    """Look up a cited line number, returning a span or a repair problem string."""
    doc = documents_by_type.get(draft.source_type)
    if doc is None:
        return msg.evidence_source_missing(draft.source_type)

    index = _line_index(doc.get("text", ""))
    entry = index.get(draft.line_no)
    if entry is None:
        valid_max = max(index) if index else 0
        return msg.evidence_line_not_found(draft.source_type, draft.line_no, valid_max)

    verbatim, char_start = entry
    return EvidenceSpan(
        document_id=doc["document_id"],
        document_hash=doc["document_hash"],
        source_type=draft.source_type,
        snippet=verbatim,
        section=draft.section,
        line_no=draft.line_no,
        char_start=char_start,
        char_end=char_start + len(verbatim),
        offset_status="verified",
        requirement_id=draft.requirement_id,
    )


def resolve_drafts(
    drafts: list[EvidenceSpanDraft], documents_by_type: dict[str, dict]
) -> tuple[list[EvidenceSpan], list[str]]:
    spans: list[EvidenceSpan] = []
    problems: list[str] = []
    for draft in drafts:
        outcome = resolve_draft(draft, documents_by_type)
        if isinstance(outcome, EvidenceSpan):
            spans.append(outcome)
        else:
            problems.append(outcome)
    return spans, problems


def dedupe_spans(spans: list[EvidenceSpan]) -> list[EvidenceSpan]:
    seen: set[tuple[str, str]] = set()
    unique: list[EvidenceSpan] = []
    for span in spans:
        key = (span.document_id, normalize_text(span.snippet))
        if key not in seen:
            seen.add(key)
            unique.append(span)
    return unique
