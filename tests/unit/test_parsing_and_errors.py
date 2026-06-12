from __future__ import annotations

import pytest

from app.core import errors
from app.workflows.parsing import parse_upload, slugify


def test_txt_parses_with_hash_and_slug():
    parsed = parse_upload("Strong Fit.TXT", b"hello resume content")
    assert parsed.parse_status == "parsed"
    assert parsed.slug == "strong_fit"
    assert parsed.document_hash is not None
    assert parsed.char_count == len("hello resume content")


def test_unsupported_extension_raises():
    with pytest.raises(errors.UnsupportedFileTypeError):
        parse_upload("resume.exe", b"binary")


def test_empty_text_status():
    parsed = parse_upload("empty.txt", b"   \n  ")
    assert parsed.parse_status == "empty_text"


def test_broken_pdf_is_parse_failed_not_a_crash():
    parsed = parse_upload("broken.pdf", b"not actually a pdf at all")
    assert parsed.parse_status in ("parse_failed", "empty_text")


def test_slugify_normalizes():
    assert slugify("Adversarial Injection (v2).pdf") == "adversarial_injection_v2"


@pytest.mark.parametrize(
    ("exc_class", "status", "code"),
    [
        (errors.UnsupportedFileTypeError, 400, "unsupported_file_type"),
        (errors.FileTooLargeError, 413, "file_too_large"),
        (errors.TooManyResumesError, 400, "too_many_resumes"),
        (errors.MissingDocumentError, 400, "missing_document"),
        (errors.ConfigurationError, 422, "configuration_error"),
        (errors.RunNotFoundError, 404, "run_not_found"),
        (errors.CandidateNotFoundError, 404, "candidate_not_found"),
        (errors.RunNotExportableError, 409, "run_not_exportable"),
        (errors.AuditExportIncompleteError, 422, "audit_export_incomplete"),
        (errors.ReplayFixtureMissingError, 422, "replay_fixture_missing"),
    ],
)
def test_domain_error_rescue_mapping(exc_class, status, code):
    exc = exc_class("boom")
    assert exc.http_status == status
    assert exc.code == code
    assert exc.message == "boom"


def test_repair_exhausted_records_attempts():
    exc = errors.RepairExhaustedError("gave up", attempts=3)
    assert exc.attempts == 3
    assert exc.code == "repair_exhausted"
