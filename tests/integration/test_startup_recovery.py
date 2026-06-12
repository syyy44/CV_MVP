from __future__ import annotations

from app.storage import repository
from app.storage.db import SCHEMA_VERSION, connect, init_db


def test_schema_version_recorded(app_env):
    with connect() as conn:
        row = conn.execute("SELECT max(version) AS version FROM schema_version").fetchone()
    assert row["version"] == SCHEMA_VERSION


def test_startup_marks_orphaned_runs_failed(app_env):
    repository.create_run("run-orphan-queued", "replay", None)
    repository.create_run("run-orphan-running", "replay", "running-key")
    repository.mark_run_started("run-orphan-running")

    init_db()

    queued = repository.get_run("run-orphan-queued")
    running = repository.get_run("run-orphan-running")

    assert queued.status == "failed"
    assert "孤立运行" in queued.error
    assert running.status == "failed"
    assert "孤立运行" in running.error
