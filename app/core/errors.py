"""Typed domain exceptions with a rescue mapping.

Every failure mode has a name, an HTTP status (when it crosses the API
boundary), and a stable machine code used in error envelopes, the decision
ledger, and tests. Catch-all `except Exception` is reserved for the final
candidate-level rescue that converts unknown failures into visible
`failed` results instead of silent drops.
"""

from __future__ import annotations


class DomainError(Exception):
    code: str = "domain_error"
    http_status: int = 500

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


# ---- Upload & Privacy Contract (request boundary) ---------------------------


class UnsupportedFileTypeError(DomainError):
    code = "unsupported_file_type"
    http_status = 400


class FileTooLargeError(DomainError):
    code = "file_too_large"
    http_status = 413


class TooManyResumesError(DomainError):
    code = "too_many_resumes"
    http_status = 400


class MissingDocumentError(DomainError):
    code = "missing_document"
    http_status = 400


class ConfigurationError(DomainError):
    code = "configuration_error"
    http_status = 422


# ---- Lookup ------------------------------------------------------------------


class RunNotFoundError(DomainError):
    code = "run_not_found"
    http_status = 404


class RunNotCancellableError(DomainError):
    code = "run_not_cancellable"
    http_status = 409


class CandidateNotFoundError(DomainError):
    code = "candidate_not_found"
    http_status = 404


class CandidateNotCompletedError(DomainError):
    code = "candidate_not_completed"
    http_status = 409


class CompareNotComparableError(DomainError):
    """Two candidates cannot be compared (e.g. not from the same run/JD)."""

    code = "compare_not_comparable"
    http_status = 400


# ---- Audit export -------------------------------------------------------------


class RunNotExportableError(DomainError):
    code = "run_not_exportable"
    http_status = 409


class AuditExportIncompleteError(DomainError):
    code = "audit_export_incomplete"
    http_status = 422


# ---- Replay -------------------------------------------------------------------


class ReplayFixtureMissingError(DomainError):
    code = "replay_fixture_missing"
    http_status = 422


# ---- Parsing (also expressed as document parse statuses) ------------------------


class ParseFailedError(DomainError):
    code = "parse_failed"
    http_status = 422


class RunCancelledError(DomainError):
    code = "run_cancelled"


# ---- LLM / structured output (workflow-internal; rescued per candidate) --------


class LLMProviderError(DomainError):
    code = "llm_provider_error"


class LLMTimeoutError(DomainError):
    code = "llm_timeout"


class LLMRateLimitError(DomainError):
    code = "llm_rate_limit"


class LLMRefusalError(DomainError):
    code = "llm_refusal"


class StructuredOutputParseError(DomainError):
    code = "structured_output_parse_error"


class StructuredOutputValidationError(DomainError):
    code = "structured_output_validation_error"


class RepairExhaustedError(DomainError):
    code = "repair_exhausted"

    def __init__(self, message: str, attempts: int):
        super().__init__(message)
        self.attempts = attempts


class EvidenceMissingError(DomainError):
    code = "evidence_missing"
