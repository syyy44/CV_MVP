from __future__ import annotations

import sys
import uuid
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

FIXTURES = ROOT / "fixtures"


@pytest.fixture()
def app_env(tmp_path, monkeypatch):
    """Isolated settings: tmp SQLite, replay mode, no live credentials."""
    monkeypatch.chdir(ROOT)
    monkeypatch.setenv("DEMO_MODE", "replay")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{tmp_path}/test.db")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.setenv("ENABLE_LANGFUSE", "false")

    from app.core.config import reset_settings_cache

    reset_settings_cache()
    from app.storage.db import init_db

    init_db()
    yield
    reset_settings_cache()


@pytest.fixture()
def client(app_env):
    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app(), raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture()
def replay_run(client):
    """A completed demo replay run (background task finishes inside TestClient)."""
    key = uuid.uuid4().hex
    response = client.post(
        "/api/runs?mode=replay", files={"idempotency_key": (None, key)}
    )
    assert response.status_code == 202, response.text
    run_id = response.json()["run_id"]
    status = client.get(f"/api/runs/{run_id}").json()
    assert status["run"]["status"] == "completed", status["run"]
    return run_id, status


def make_workflow_context(run_id: str, provider) -> object:
    from app.core.config import get_settings
    from app.ledger.events import LedgerRecorder
    from app.observability.tracing import Tracer
    from app.workflows.context import MetricsCollector, WorkflowContext

    settings = get_settings()
    return WorkflowContext(
        run_id=run_id,
        mode="replay",
        settings=settings,
        provider=provider,
        ledger=LedgerRecorder(run_id),
        tracer=Tracer(settings),
        metrics=MetricsCollector(),
    )


class ScriptedProvider:
    """Returns canned responses in order; repeats the last one when exhausted."""

    name = "scripted"

    def __init__(self, responses: list[str]):
        self.responses = responses
        self.calls = 0
        self.call_messages: list[list] = []

    def complete(
        self,
        messages,
        *,
        fixture_key=None,
        temperature=None,
        response_schema=None,
        response_schema_name=None,
    ):
        from app.llm.client import CompletionResult

        index = min(self.calls, len(self.responses) - 1)
        self.call_messages.append(messages)
        self.calls += 1
        return CompletionResult(text=self.responses[index], model="scripted")
