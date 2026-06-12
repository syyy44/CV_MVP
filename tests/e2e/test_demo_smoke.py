"""E2E smoke: the `make demo` path (default replay mode, no LLM key).

POST without an explicit mode -> settings default (replay) -> three dossiers
-> audit export available. This is the reviewer's one-click walkthrough.
"""

from __future__ import annotations

import uuid


def test_demo_smoke_end_to_end(client):
    created = client.post(
        "/api/runs", files={"idempotency_key": (None, uuid.uuid4().hex)}
    )
    assert created.status_code == 202
    run_id = created.json()["run_id"]

    status = client.get(f"/api/runs/{run_id}").json()
    assert status["run"]["status"] == "completed"
    assert status["run"]["mode"] == "replay"

    completed = [c for c in status["candidates"] if c["status"] == "completed"]
    assert len(completed) >= 3
    for candidate in completed:
        assert len(candidate["dossier"]["questions"]) >= 10
        assert len(candidate["dossier"]["score"]["evidence_refs"]) >= 3

    export = client.get(f"/api/runs/{run_id}/audit-export")
    assert export.status_code == 200
    assert export.json()["schema_version"] == "audit-export.v1"

    events = client.get(f"/api/runs/{run_id}/events").json()
    assert len(events) >= 24
