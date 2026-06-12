from __future__ import annotations

from app.core.redaction import scrub_pii_data, scrub_pii_text


def test_scrub_pii_text_redacts_email_phone_and_address():
    text = (
        "Email: candidate@example.com; phone +86 138 0000 1234; "
        "Address: 88 West Lake Road, Hangzhou"
    )
    scrubbed = scrub_pii_text(text)
    assert "candidate@example.com" not in scrubbed
    assert "138 0000 1234" not in scrubbed
    assert "88 West Lake Road" not in scrubbed
    assert "[邮箱已脱敏]" in scrubbed
    assert "[电话已脱敏]" in scrubbed
    assert "[地址已脱敏]" in scrubbed


def test_scrub_pii_data_recurses():
    payload = {
        "summary": "Contact me at demo@example.com",
        "nested": ["phone: 13912345678"],
    }
    scrubbed = scrub_pii_data(payload)
    assert "demo@example.com" not in str(scrubbed)
    assert "13912345678" not in str(scrubbed)
