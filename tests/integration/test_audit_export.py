from __future__ import annotations

import json

from app.models.export import AuditExport
from app.storage import repository


def test_export_returns_409_while_running(client):
    repository.create_run("run-queued", "replay", None)
    response = client.get("/api/runs/run-queued/audit-export")
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "run_not_exportable"

    repository.mark_run_started("run-queued")
    assert client.get("/api/runs/run-queued/audit-export").status_code == 409


def test_export_returns_409_for_failed_run(client):
    repository.create_run("run-failed", "replay", None)
    repository.mark_run_finished("run-failed", "failed", error="boom")
    response = client.get("/api/runs/run-failed/audit-export")
    assert response.status_code == 409


def test_export_returns_422_without_ledger_data(client):
    repository.create_run("run-empty", "replay", None)
    repository.mark_run_finished("run-empty", "completed")
    response = client.get("/api/runs/run-empty/audit-export")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "audit_export_incomplete"


def test_export_missing_run_is_404(client):
    assert client.get("/api/runs/ghost/audit-export").status_code == 404


def test_completed_export_validates_and_redacts(replay_run, client):
    run_id, _status = replay_run
    response = client.get(f"/api/runs/{run_id}/audit-export")
    assert response.status_code == 200

    export = AuditExport.model_validate(response.json())
    assert export.schema_version == "audit-export.v1"
    assert export.export_status == "complete"
    assert len(export.candidate_dossiers) == 3
    assert len(export.decision_events) >= 24
    assert export.run_eval_results == []
    assert all(item.scope == "suite" for item in export.suite_eval_summary)
    assert export.eval_results == export.suite_eval_summary
    assert export.warnings == []

    raw = json.dumps(response.json(), ensure_ascii=False)
    # Redaction (Upload & Privacy Contract): a resume line that no fixture ever
    # quotes or extracts must not leak; contact emails are scrubbed from
    # previews; no provider credential material may appear.
    assert "Introduced Docker based deployment and GitHub Actions CI" not in raw
    assert "@example.com" not in raw
    assert "LLM_API_KEY" not in raw
    assert "Authorization" not in raw
    for document in export.documents:
        assert len(document.preview) <= 160


def test_export_scrubs_pii_inside_dossier_payload(replay_run, client):
    from app.storage import repository

    run_id, status = replay_run
    candidate = status["candidates"][0]
    dossier = candidate["dossier"]
    dossier["candidate_profile"]["summary"] += (
        " Contact: live-candidate@example.com, +86 139 1234 5678. "
        "Address: 100 Candidate Road, Shanghai"
    )
    repository.save_candidate_result(
        run_id,
        repository._row_to_result(  # noqa: SLF001 - focused integration test fixture
            {
                "candidate_id": candidate["candidate_id"],
                "run_id": run_id,
                "candidate_name": candidate["candidate_name"],
                "status": "completed",
                "dossier_json": json.dumps(dossier),
                "errors_json": "[]",
                "sort_score": dossier["score"]["overall_score"],
                "created_at": status["run"]["created_at"],
            }
        ),
    )

    response = client.get(f"/api/runs/{run_id}/audit-export")
    raw = json.dumps(response.json(), ensure_ascii=False)
    assert "live-candidate@example.com" not in raw
    assert "139 1234 5678" not in raw
    assert "100 Candidate Road" not in raw
    assert "[邮箱已脱敏]" in raw
