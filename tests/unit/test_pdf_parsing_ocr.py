from __future__ import annotations

from app.workflows import parsing


def test_pdf_uses_local_when_no_api_key(monkeypatch):
    monkeypatch.setattr(parsing, "get_settings", lambda: type("S", (), {
        "qianfan_api_key": None,
        "paddle_ocr_timeout_seconds": 30.0,
    })())

    called = {"paddle": False, "local": False}

    def fake_paddle(*_a, **_k):
        called["paddle"] = True
        return "parsed", "paddle text here " * 3, ["paddle text here " * 3]

    def fake_local(_data):
        called["local"] = True
        return "parsed", "local text here " * 3, ["local"]

    monkeypatch.setattr(parsing, "_parse_pdf_paddle", fake_paddle)
    monkeypatch.setattr(parsing, "_parse_pdf_local", fake_local)

    parsed = parsing.parse_upload("resume.pdf", b"%PDF-1.4 fake")
    assert called["local"] is True
    assert called["paddle"] is False
    assert "local text" in parsed.text


def test_pdf_prefers_paddle_when_configured(monkeypatch):
    monkeypatch.setattr(parsing, "get_settings", lambda: type("S", (), {
        "qianfan_api_key": "test-key",
        "paddle_ocr_timeout_seconds": 30.0,
    })())

    def fake_paddle(*_a, **_k):
        return "parsed", "paddle ocr extracted content " * 2, ["page1"]

    def fake_local(_data):
        raise AssertionError("local parser should not run when paddle succeeds")

    monkeypatch.setattr(parsing, "_parse_pdf_paddle", fake_paddle)
    monkeypatch.setattr(parsing, "_parse_pdf_local", fake_local)

    parsed = parsing.parse_upload("resume.pdf", b"%PDF-1.4 fake")
    assert parsed.parse_status == "parsed"
    assert "paddle ocr" in parsed.text


def test_pdf_falls_back_to_local_when_paddle_fails(monkeypatch):
    monkeypatch.setattr(parsing, "get_settings", lambda: type("S", (), {
        "qianfan_api_key": "test-key",
        "paddle_ocr_timeout_seconds": 30.0,
    })())

    def fake_paddle(*_a, **_k):
        raise RuntimeError("api down")

    def fake_local(_data):
        return "parsed", "fallback local parser text " * 2, ["local page"]

    monkeypatch.setattr(parsing, "_parse_pdf_paddle", fake_paddle)
    monkeypatch.setattr(parsing, "_parse_pdf_local", fake_local)

    parsed = parsing.parse_upload("resume.pdf", b"%PDF-1.4 fake")
    assert parsed.parse_status == "parsed"
    assert "fallback local" in parsed.text
