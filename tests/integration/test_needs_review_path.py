from __future__ import annotations

import json
from pathlib import Path

from app.models.contracts import JobRubric
from app.storage import repository
from app.workflows.graph import build_candidate_graph
from tests.conftest import ScriptedProvider, make_workflow_context

FIXTURES = Path(__file__).resolve().parent.parent.parent / "fixtures"


def _docs() -> tuple[dict, dict]:
    jd_text = (FIXTURES / "demo" / "jd.txt").read_text(encoding="utf-8")
    resume_text = (FIXTURES / "demo" / "resumes" / "strong_fit.txt").read_text(encoding="utf-8")
    jd_doc = {
        "document_id": "jd-1",
        "document_hash": "jd-hash",
        "source_type": "jd",
        "filename": "jd.txt",
        "slug": "jd",
        "parse_status": "parsed",
        "char_count": len(jd_text),
        "text": jd_text,
    }
    resume_doc = {**jd_doc, "document_id": "res-1", "document_hash": "res-hash",
                  "source_type": "resume", "filename": "strong_fit.txt",
                  "slug": "strong_fit", "char_count": len(resume_text), "text": resume_text}
    return jd_doc, resume_doc


def test_repair_exhaustion_produces_needs_review_dossier(app_env):
    repository.create_run("run-nr", "replay", None)
    # Profile output is irreparably invalid: every attempt returns wrong shape.
    ctx = make_workflow_context("run-nr", ScriptedProvider([json.dumps({"nope": True})]))
    rubric = JobRubric.model_validate(
        json.loads((FIXTURES / "demo" / "llm_outputs" / "rubric.json").read_text("utf-8"))
    )
    jd_doc, resume_doc = _docs()

    output = build_candidate_graph().invoke(
        {
            "ctx": ctx,
            "rubric": rubric,
            "jd_doc": jd_doc,
            "resume_doc": resume_doc,
            "candidate_id": "cand-nr",
            "slug": "strong_fit",
        }
    )
    result = output["result"]
    assert result.status == "needs_review"
    assert result.dossier is not None
    assert result.dossier.status == "needs_review"
    assert "profile" in result.dossier.missing_fields
    assert result.dossier.repair_attempt_count >= 1
    assert result.dossier.reviewer_message

    saved = repository.get_candidate_results("run-nr")
    assert saved[0].status == "needs_review"

    events = [e.event_type for e in repository.get_events("run-nr")]
    assert "repair_failed" in events
    assert "dossier_completed" in events


def test_needs_review_run_exports_partial(client):
    from app.workflows.runner import derive_run_status

    repository.create_run("run-partial", "replay", None)
    ctx = make_workflow_context("run-partial", ScriptedProvider([json.dumps({"nope": True})]))
    rubric = JobRubric.model_validate(
        json.loads((FIXTURES / "demo" / "llm_outputs" / "rubric.json").read_text("utf-8"))
    )
    jd_doc, resume_doc = _docs()
    output = build_candidate_graph().invoke(
        {
            "ctx": ctx,
            "rubric": rubric,
            "jd_doc": jd_doc,
            "resume_doc": resume_doc,
            "candidate_id": "cand-partial",
            "slug": "strong_fit",
        }
    )
    repository.mark_run_finished(
        "run-partial", derive_run_status([output["result"]])
    )

    response = client.get("/api/runs/run-partial/audit-export")
    assert response.status_code == 200
    payload = response.json()
    assert payload["export_status"] == "partial"
    assert payload["warnings"]
