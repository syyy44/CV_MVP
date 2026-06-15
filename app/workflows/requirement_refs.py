from __future__ import annotations

from app.models.contracts import EvidenceContextLine, EvidenceSpan
from app.workflows.evidence import number_lines
from app.workflows.grounding import relevance


def _context_lines(
    numbered: list[tuple[int, str, int]],
    focus_line_no: int,
    *,
    radius: int = 1,
) -> list[EvidenceContextLine]:
    return [
        EvidenceContextLine(line_no=line_no, text=line[:2000], is_focus=line_no == focus_line_no)
        for line_no, line, _start in numbered
        if abs(line_no - focus_line_no) <= radius
    ]


def build_jd_evidence_refs(
    requirement_id: str,
    requirement_text: str,
    jd_doc: dict,
    *,
    limit: int = 2,
) -> list[EvidenceSpan]:
    """Resolve a rubric requirement back to stable JD source lines.

    Rubric extraction does not currently store citations. This deterministic
    fallback finds the JD lines that best overlap the extracted requirement so
    every candidate under the same run gets identical JD requirement evidence.
    """
    numbered = number_lines(jd_doc.get("text", ""))
    query = requirement_text.strip()
    if not numbered or not query:
        return []

    scored: list[tuple[float, int, str, int]] = []
    for line_no, line, start in numbered:
        score = relevance(query, line)
        if query in line:
            score = max(score, 1.0)
        if score > 0:
            scored.append((score, line_no, line, start))
    if not scored:
        return []

    scored.sort(key=lambda item: (-item[0], item[1]))
    best_score = scored[0][0]
    # Keep direct matches plus close secondary lines for synthesized requirements
    # that come from multiple adjacent JD bullets.
    min_score = max(0.35, best_score * 0.6) if best_score >= 0.5 else max(0.25, best_score)
    refs: list[EvidenceSpan] = []
    for score, line_no, line, start in scored:
        if score < min_score:
            continue
        refs.append(
            EvidenceSpan(
                document_id=jd_doc["document_id"],
                document_hash=jd_doc["document_hash"],
                source_type="jd",
                snippet=line,
                line_no=line_no,
                char_start=start,
                char_end=start + len(line),
                offset_status="verified",
                requirement_id=requirement_id,
                context_lines=_context_lines(numbered, line_no),
            )
        )
        if len(refs) >= limit:
            break
    return refs

