from __future__ import annotations


def _candidate(status: dict, name: str) -> dict:
    return next(c for c in status["candidates"] if c["candidate_name"] == name)


def test_board_summary_fields_present(replay_run):
    _run_id, status = replay_run
    li = _candidate(status, "李伟")
    chen = _candidate(status, "陈浩")

    assert li["confidence_band"] in {"high", "medium", "low"}
    assert li["decision_summary"]
    assert li["risk_count"] == 0
    assert li["verification_count"] == 0  # strong proceed: no ambiguous claims

    assert chen["risk_count"] >= 1  # injection risk flagged
    assert chen["verification_count"] >= 1


def test_interview_script_v3(replay_run, client):
    _run_id, status = replay_run
    chen = _candidate(status, "陈浩")
    resp = client.get(f"/api/candidates/{chen['candidate_id']}/interview-script")
    assert resp.status_code == 200, resp.text
    body = resp.json()

    assert body["script_rule_version"] == "v3"
    assert len(body["must_ask"]) == 4
    assert body["suggested_duration_min"] > 0

    # v3 acceptance: suspicious 5000万 claim leads the must-ask via claim_probe.
    reasons_list = [item["selection_reason"] for item in body["must_ask"]]
    assert reasons_list[0] == "claim_probe"
    assert "5000 万" in body["must_ask"][0]["question"]["target_claim"]

    # checklist != plain follow-up count; injection item leads, claim probes follow.
    assert len(body["verification_checklist"]) != len(body["follow_ups"])
    reasons = {item["reason"] for item in body["verification_checklist"]}
    assert "injection" in reasons
    assert "claim_probe" in reasons
    assert body["verification_checklist"][0]["reason"] == "injection"
    assert body["pass_criteria"]


def test_interview_script_rejects_non_completed(replay_run, client):
    # A fabricated id is treated as not found.
    resp = client.get("/api/candidates/does-not-exist/interview-script")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "candidate_not_found"


def test_requirement_results_carry_display_label(replay_run):
    _run_id, status = replay_run
    chen = _candidate(status, "陈浩")
    reqs = chen["dossier"]["score"]["requirement_results"]
    assert len(reqs) == 5  # five must-haves in the demo rubric
    assert all(r["display_label"] and "MH" not in r["display_label"] for r in reqs)
    assert all("requirement_id" in r and "met" in r for r in reqs)


def test_notes_crud_and_ledger(replay_run, client):
    run_id, status = replay_run
    chen = _candidate(status, "陈浩")
    cid = chen["candidate_id"]

    assert client.get(f"/api/candidates/{cid}/notes").json() == []

    created = client.post(
        f"/api/candidates/{cid}/notes",
        json={"body": "电话初筛确认了 LLM 项目细节。", "author": "面试官 A"},
    )
    assert created.status_code == 201, created.text
    assert created.json()["body"].startswith("电话初筛")

    listed = client.get(f"/api/candidates/{cid}/notes").json()
    assert len(listed) == 1
    assert listed[0]["author"] == "面试官 A"

    events = client.get(f"/api/runs/{run_id}/events").json()
    assert any(e["event_type"] == "note_added" for e in events)


def test_decision_override_writes_ledger(replay_run, client):
    run_id, status = replay_run
    chen = _candidate(status, "陈浩")
    cid = chen["candidate_id"]

    resp = client.patch(
        f"/api/candidates/{cid}/decision",
        json={"recommendation": "proceed", "rationale": "面后确认 LLM 经验充分。"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["recommendation"] == "proceed"

    detail = client.get(f"/api/candidates/{cid}/dossier").json()
    assert detail["human_override"]["recommendation"] == "proceed"
    # Original model recommendation is preserved for the audit trail.
    assert detail["dossier"]["score"]["recommendation"] == "reject"

    events = client.get(f"/api/runs/{run_id}/events").json()
    overrides = [e for e in events if e["event_type"] == "human_override_recorded"]
    # demo seed override + this human override
    assert any(e["metadata"].get("to") == "proceed" for e in overrides)
