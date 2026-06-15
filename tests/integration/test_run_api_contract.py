from __future__ import annotations

import uuid

from app.workflows.test_data import list_test_data_files


def test_idempotency_key_returns_existing_run(client):
    key = uuid.uuid4().hex
    first = client.post("/api/runs?mode=replay", files={"idempotency_key": (None, key)})
    assert first.status_code == 202
    second = client.post("/api/runs?mode=replay", files={"idempotency_key": (None, key)})
    assert second.status_code == 202
    assert second.json()["run_id"] == first.json()["run_id"]
    assert second.json()["existing"] is True

    other = client.post(
        "/api/runs?mode=replay", files={"idempotency_key": (None, uuid.uuid4().hex)}
    )
    assert other.json()["run_id"] != first.json()["run_id"]


def test_replay_mode_rejects_uploads(client):
    response = client.post(
        "/api/runs?mode=replay",
        files={"jd": ("jd.txt", b"some jd content", "text/plain")},
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "missing_document"


def test_live_mode_without_key_is_configuration_error(client, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "")
    from app.core.config import reset_settings_cache

    reset_settings_cache()
    response = client.post(
        "/api/runs?mode=live",
        files={
            "jd": ("jd.txt", b"a job description", "text/plain"),
            "resumes": ("resume.txt", b"a resume body", "text/plain"),
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "configuration_error"


def test_live_mode_upload_contract(client, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key-not-used")
    from app.core.config import reset_settings_cache

    reset_settings_cache()

    bad_ext = client.post(
        "/api/runs?mode=live",
        files={"jd": ("jd.exe", b"binary", "application/octet-stream")},
    )
    assert bad_ext.status_code == 400
    assert bad_ext.json()["error"]["code"] == "unsupported_file_type"

    no_resumes = client.post(
        "/api/runs?mode=live",
        files={"jd": ("jd.txt", b"a job description", "text/plain")},
    )
    assert no_resumes.status_code == 400
    assert no_resumes.json()["error"]["code"] == "missing_document"

    too_many = client.post(
        "/api/runs?mode=live",
        files=[("jd", ("jd.txt", b"a job description", "text/plain"))]
        + [("resumes", (f"r{i}.txt", b"resume body", "text/plain")) for i in range(6)],
    )
    assert too_many.status_code == 400
    assert too_many.json()["error"]["code"] == "too_many_resumes"

    monkeypatch.setenv("MAX_FILE_MB", "0")
    reset_settings_cache()
    too_large = client.post(
        "/api/runs?mode=live",
        files={
            "jd": ("jd.txt", b"x" * 10, "text/plain"),
            "resumes": ("resume.txt", b"resume body", "text/plain"),
        },
    )
    assert too_large.status_code == 413
    assert too_large.json()["error"]["code"] == "file_too_large"


def test_list_runs_returns_history(replay_run, client):
    run_id, status = replay_run
    response = client.get("/api/runs")
    assert response.status_code == 200
    items = response.json()
    assert len(items) >= 1
    first = items[0]
    assert first["run"]["run_id"] == run_id
    assert first["run"]["status"] == "completed"
    assert first["candidate_count"] == len(status["candidates"])
    assert first["resume_count"] >= 1
    assert first["jd_filename"]


def test_list_runs_respects_limit(replay_run, client):
    response = client.get("/api/runs?limit=1")
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_unknown_run_returns_404_envelope(client):
    response = client.get("/api/runs/does-not-exist")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "run_not_found"

    response = client.get("/api/candidates/none/dossier")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "candidate_not_found"


def test_test_data_manifest(client):
    expected = list_test_data_files()

    response = client.get("/api/test-data")
    assert response.status_code == 200
    body = response.json()
    assert body["jd"]["filename"] == expected.jd.name
    assert [r["filename"] for r in body["resumes"]] == [p.name for p in expected.resumes]

    file_resp = client.get(body["resumes"][0]["url"])
    assert file_resp.status_code == 200
    assert file_resp.content
    if expected.resumes[0].suffix.lower() == ".pdf":
        assert file_resp.content[:4] == b"%PDF"


def test_live_mode_source_test(client, monkeypatch):
    expected = list_test_data_files()

    monkeypatch.setenv("LLM_API_KEY", "test-key-not-used")
    from app.core.config import reset_settings_cache

    reset_settings_cache()
    response = client.post(
        "/api/runs?mode=live&source=test",
        files={"idempotency_key": (None, uuid.uuid4().hex)},
    )
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    status = client.get(f"/api/runs/{run_id}").json()
    filenames = {doc["filename"] for doc in status["documents"]}
    assert expected.jd.name in filenames
    assert {p.name for p in expected.resumes}.issubset(filenames)


def test_live_mode_jd_text(client, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key-not-used")
    from app.core.config import reset_settings_cache

    reset_settings_cache()
    response = client.post(
        "/api/runs?mode=live",
        data={"jd_text": "a pasted job description"},
        files={"resumes": ("resume.txt", b"a resume body", "text/plain")},
    )
    assert response.status_code == 202
    run_id = response.json()["run_id"]
    status = client.get(f"/api/runs/{run_id}").json()
    assert any(doc["filename"] == "jd.txt" for doc in status["documents"])


def test_live_mode_jd_upload_and_text_conflict(client, monkeypatch):
    monkeypatch.setenv("LLM_API_KEY", "test-key-not-used")
    from app.core.config import reset_settings_cache

    reset_settings_cache()
    response = client.post(
        "/api/runs?mode=live",
        data={"jd_text": "pasted text"},
        files={
            "jd": ("jd.txt", b"uploaded jd", "text/plain"),
            "resumes": ("resume.txt", b"a resume body", "text/plain"),
        },
    )
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "missing_document"


def test_health_reports_mode(client):
    payload = client.get("/health").json()
    assert payload["status"] == "ok"
    assert payload["mode"] == "replay"
    assert payload["langfuse_enabled"] is False
    assert payload["langfuse_verified"] is False
