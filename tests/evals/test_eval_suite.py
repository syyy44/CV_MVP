from __future__ import annotations

import json

from app.evals.runner import PROTECTED_PATTERN, run_evals
from app.storage import repository

EXPECTED_CHECKS = {
    "demo_run_completed",
    "demo_dossier_count",
    "demo_expected_outcomes",
    "demo_question_minimums",
    "demo_evidence_minimums",
    "demo_ledger_density",
    "demo_audit_export",
    "injection_recommendation",
    "injection_score_delta",
    "injection_no_instruction_echo",
    "proxy_score_delta",
    "proxy_no_protected_terms",
    "jd_protected_requirement_excluded",
}


def test_full_eval_suite_passes(app_env):
    assert run_evals() is True

    results = {r.name: r for r in repository.get_eval_results()}
    assert set(results) == EXPECTED_CHECKS
    assert all(r.status == "pass" for r in results.values())

    assert results["injection_score_delta"].value == 0.0
    assert results["proxy_score_delta"].value == 0.0

    from app.core.config import get_settings

    report = json.loads(
        (get_settings().database_path.parent / "eval-report.json").read_text("utf-8")
    )
    assert report["passed"] is True
    assert len(report["checks"]) == len(EXPECTED_CHECKS)


def test_protected_pattern_avoids_false_positives():
    clean = (
        "Manage trace tooling coverage for the team; managed packages and language models."
    )
    assert PROTECTED_PATTERN.search(clean) is None
    assert PROTECTED_PATTERN.search("candidate is 27 years old") is not None
    assert PROTECTED_PATTERN.search("recently married volunteer") is not None
