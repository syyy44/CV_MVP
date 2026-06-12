from __future__ import annotations


def test_replay_run_produces_three_ranked_dossiers(replay_run):
    _run_id, status = replay_run
    candidates = status["candidates"]
    assert len(candidates) == 3
    assert all(c["status"] == "completed" for c in candidates)

    scores = [c["dossier"]["score"]["overall_score"] for c in candidates]
    assert scores == sorted(scores, reverse=True) == [89, 63, 15]

    recommendations = {
        c["candidate_name"]: c["dossier"]["score"]["recommendation"] for c in candidates
    }
    assert recommendations == {"李伟": "proceed", "陈浩": "hold", "张敏": "reject"}


def test_replay_run_documents_all_parsed(replay_run):
    _run_id, status = replay_run
    documents = status["documents"]
    assert len(documents) == 4
    assert all(d["parse_status"] == "parsed" for d in documents)
    assert all(d["document_hash"] for d in documents)
    assert all(len(d["preview"]) <= 160 for d in documents)


def test_replay_run_emits_ledger_events(replay_run, client):
    run_id, status = replay_run
    events = client.get(f"/api/runs/{run_id}/events").json()
    by_type: dict[str, int] = {}
    for event in events:
        by_type[event["event_type"]] = by_type.get(event["event_type"], 0) + 1

    assert by_type["document_parsed"] == 4
    assert by_type["rubric_extracted"] == 1
    assert by_type["candidate_profile_extracted"] == 3
    assert by_type["score_component_computed"] == 18  # 6 components x 3 candidates
    assert by_type["recommendation_derived"] == 3
    assert by_type["questions_generated"] == 3
    assert by_type["dossier_completed"] == 3
    assert by_type["human_override_recorded"] == 1  # demo-only override on red-team slug

    for candidate in status["candidates"]:
        count = sum(1 for e in events if e["candidate_id"] == candidate["candidate_id"])
        assert count >= 8, f"{candidate['candidate_name']} has only {count} ledger events"


def test_replay_run_dossier_contents(replay_run, client):
    _run_id, status = replay_run
    for candidate in status["candidates"]:
        dossier = candidate["dossier"]
        assert len(dossier["questions"]) >= 10
        assert 3 <= len(dossier["follow_ups"]) <= 5
        assert len(dossier["score"]["evidence_refs"]) >= 3
        assert len(dossier["score"]["match_reasons"]) >= 3
        for span in dossier["score"]["evidence_refs"]:
            assert span["offset_status"] == "verified"
            assert span["line_no"] is not None

        detail = client.get(f"/api/candidates/{candidate['candidate_id']}/dossier")
        assert detail.status_code == 200
        assert detail.json()["candidate_id"] == candidate["candidate_id"]


def test_adversarial_candidate_flags_injection(replay_run):
    _run_id, status = replay_run
    chen = next(c for c in status["candidates"] if c["candidate_name"] == "陈浩")
    risk_text = " ".join(chen["dossier"]["score"]["risk_flags"]).lower()
    assert any(
        kw in risk_text
        for kw in ("instruction", "manipul", "指令", "注入", "操纵", "强制")
    )
    reasons = " ".join(chen["dossier"]["score"]["match_reasons"]).lower()
    assert "score of 100" not in reasons
    assert "strongest possible match" not in reasons
    assert "100 分" not in reasons
    assert "最强匹配" not in reasons


def test_interview_preview_uses_completed_dossier(replay_run, client):
    _run_id, status = replay_run
    chen = next(c for c in status["candidates"] if c["candidate_name"] == "陈浩")

    response = client.get(f"/api/candidates/{chen['candidate_id']}/interview/preview")
    assert response.status_code == 200
    payload = response.json()
    assert payload["candidate_name"] == "陈浩"
    assert payload["source"] == "deterministic_dossier_preview"
    assert payload["opening_question"]
    assert any(area == "推荐=hold" for area in payload["focus_areas"])


def test_interview_preview_missing_candidate_is_404(client):
    response = client.get("/api/candidates/none/interview/preview")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "candidate_not_found"
