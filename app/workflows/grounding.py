"""Deterministic grounding guards (residual-hallucination defense).

Indexed quoting (`app.workflows.evidence`) already guarantees that a cited
``line_no`` *exists* and is retrieved verbatim. It does **not** guarantee two
things that still let hallucinations through:

1. **Relevance** — the model can cite a real-but-unrelated line. The line
   resolves fine, so the bogus snippet reaches the dossier as "evidence".
2. **Numeric fidelity** — free-text fields (``quantified_claims``, a claim
   under verification) can contain a fabricated metric that never appears in
   the source document.

This module closes both gaps with **purely lexical, deterministic** checks so
they run identically in live and replay (no embedding service, no extra LLM
call, no nondeterminism, CI-runnable without a key). Each check returns repair
*problem strings*; callers feed them into the existing bounded repair loop, so
a fabricated number or a misattributed citation is bounced back to the model
and, if unfixable, surfaces as ``needs_review`` instead of a confident dossier.

Tokenization is bilingual: ASCII/alphanumeric word tokens plus CJK character
bigrams, which gives a stable overlap signal for the mixed zh/en résumés this
system ingests.
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence

from app.locale import zh_CN as msg
from app.models.contracts import EvidenceSpan

# --- normalization & tokenization ----------------------------------------------

_ASCII_TOKEN_RE = re.compile(r"[a-z0-9]+")
_CJK_RUN_RE = re.compile(r"[\u4e00-\u9fff\u3400-\u4dbf]+")
_MIN_ASCII_TOKEN_LEN = 2


def normalize_for_match(text: str) -> str:
    """NFKC fold (full-width→ASCII, etc.), lowercase, collapse whitespace.

    Keeps CJK characters intact; only used to derive comparison tokens, never
    surfaced to users.
    """
    folded = unicodedata.normalize("NFKC", text or "").lower()
    return " ".join(folded.split())


def lexical_tokens(text: str) -> set[str]:
    """Bag of comparison tokens: ASCII words (len>=2) + CJK character bigrams.

    CJK has no whitespace word boundaries, so contiguous CJK runs are turned
    into overlapping 2-grams (single-char runs kept as unigrams). This is the
    standard cheap-but-robust signal for Chinese fuzzy overlap and avoids
    depending on a segmenter.
    """
    norm = normalize_for_match(text)
    tokens: set[str] = {
        token for token in _ASCII_TOKEN_RE.findall(norm) if len(token) >= _MIN_ASCII_TOKEN_LEN
    }
    for run in _CJK_RUN_RE.findall(norm):
        if len(run) == 1:
            tokens.add(run)
        else:
            tokens.update(run[i : i + 2] for i in range(len(run) - 1))
    return tokens


def relevance(claim: str, line: str) -> float:
    """Szymkiewicz–Simpson overlap coefficient over lexical tokens (0..1).

    Min-based (not Jaccard) so a short claim that is genuinely a subset of a
    long evidence line — or vice versa — still scores high; length asymmetry
    between an analytical claim and a verbatim source line is the norm here.
    """
    a = lexical_tokens(claim)
    b = lexical_tokens(line)
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


# --- numeric grounding ----------------------------------------------------------

# A raw number with the unit/percent context that decides whether it is worth
# grounding. The capture group is the bare numeric core used for comparison.
_NUMBER_RE = re.compile(
    r"(?<![\w.])(\d{1,3}(?:[,，]\d{3})+|\d+(?:\.\d+)?)\s*(%|％|个?百分点|pp|‰|万|亿|千|k|m|b|x|倍)?",
    re.IGNORECASE,
)
_MAGNITUDE_UNITS = {"万", "亿", "千", "k", "m", "b", "x", "倍"}
_PERCENT_UNITS = {"%", "％", "个百分点", "百分点", "pp", "‰"}


def _numeric_core(raw: str) -> str:
    """Canonical comparison form: drop thousands separators, keep decimals."""
    return raw.replace(",", "").replace("，", "")


def numeric_cores(text: str) -> set[str]:
    """All numeric cores present in a text (the grounding lookup set)."""
    norm = unicodedata.normalize("NFKC", text or "")
    return {_numeric_core(match.group(1)) for match in _NUMBER_RE.finditer(norm)}


def significant_numbers(text: str) -> list[str]:
    """Numeric cores worth grounding: decimals, percents, magnitudes, or >=10.

    Bare single-digit integers (0-9) with no unit are excluded — they are too
    common (team sizes, "3 年", list counts) to ground without false positives.
    Returns cores (e.g. ``"63.8"``, ``"5000"``) in document order, de-duplicated.
    """
    norm = unicodedata.normalize("NFKC", text or "")
    cores: list[str] = []
    seen: set[str] = set()
    for match in _NUMBER_RE.finditer(norm):
        core = _numeric_core(match.group(1))
        unit = (match.group(2) or "").lower()
        is_significant = (
            "." in core
            or len(core) >= 2  # integer >= 10
            or unit in _MAGNITUDE_UNITS
            or unit in _PERCENT_UNITS
        )
        if is_significant and core not in seen:
            seen.add(core)
            cores.append(core)
    return cores


def ungrounded_numbers(claim: str, *sources: str) -> list[str]:
    """Significant numbers in ``claim`` that appear in none of ``sources``."""
    source_cores: set[str] = set()
    for source in sources:
        source_cores |= numeric_cores(source)
    return [core for core in significant_numbers(claim) if core not in source_cores]


# --- problem builders (fed into the repair loop) --------------------------------


def quantified_claim_problems(
    projects: Sequence[object], resume_text: str
) -> list[str]:
    """Every number in a project's ``quantified_claims`` must exist in the résumé.

    ``quantified_claims`` are contractually verbatim excerpts (see the extract
    prompt), so a number that is absent from the source is a fabrication, not a
    paraphrase. Grounds against the full résumé text (not just numbered lines)
    so values on short, non-citable lines still count.
    """
    problems: list[str] = []
    for project in projects:
        name = getattr(project, "name", "")
        for claim in getattr(project, "quantified_claims", []) or []:
            missing = ungrounded_numbers(claim, resume_text)
            if missing:
                problems.append(msg.quantified_claim_number_unsupported(name, claim, missing))
    return problems


def claim_number_problems(claims: Sequence[str], *sources: str) -> list[str]:
    """Significant numbers in a verification claim absent from every source.

    Softer than ``quantified_claim_problems`` (the claim text may paraphrase),
    so it only fires when a number is in *neither* the JD nor the résumé —
    a near-certain fabrication.
    """
    problems: list[str] = []
    for claim in claims:
        missing = ungrounded_numbers(claim, *sources)
        if missing:
            problems.append(msg.claim_number_unsupported(claim, missing))
    return problems


def support_relevance_problems(
    units: Sequence[tuple[str, list[EvidenceSpan]]],
    *,
    label: str,
    min_relevance: float,
) -> list[str]:
    """Each claim must have >=1 cited line that lexically overlaps it.

    Only units that already resolved to >=1 span are checked (unresolved
    citations are reported separately by evidence resolution). A unit whose
    *best* cited line falls below ``min_relevance`` is almost certainly a
    misattributed citation and is bounced back for repair.
    """
    problems: list[str] = []
    for index, (claim, spans) in enumerate(units):
        if not spans:
            continue
        best = max(relevance(claim, span.snippet) for span in spans)
        if best < min_relevance:
            problems.append(msg.evidence_irrelevant(label, index, claim, best))
    return problems
