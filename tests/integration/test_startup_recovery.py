from __future__ import annotations

from app.storage import repository
from app.storage.db import SCHEMA_VERSION, connect, init_db


def test_schema_version_recorded(app_env):
    with connect() as conn:
        row = conn.execute("SELECT max(version) AS version FROM schema_version").fetchone()
    assert row["version"] == SCHEMA_VERSION


def test_startup_marks_stale_orphaned_runs_failed(app_env):
    repository.create_run("run-orphan-queued", "replay", None)
    repository.create_run("run-orphan-running", "replay", "running-key")
    repository.mark_run_started("run-orphan-running")
    with connect() as conn:
        conn.execute(
            "UPDATE runs SET created_at = datetime('now', '-3 hours'),"
            " started_at = datetime('now', '-3 hours')"
            " WHERE run_id IN ('run-orphan-queued', 'run-orphan-running')"
        )

    init_db()

    queued = repository.get_run("run-orphan-queued")
    running = repository.get_run("run-orphan-running")

    assert queued.status == "failed"
    assert "孤立运行" in queued.error
    assert running.status == "failed"
    assert "孤立运行" in running.error


def test_startup_keeps_recent_active_runs(app_env):
    repository.create_run("run-active-queued", "replay", None)
    repository.create_run("run-active-running", "replay", "active-running-key")
    repository.mark_run_started("run-active-running")

    init_db()

    queued = repository.get_run("run-active-queued")
    running = repository.get_run("run-active-running")

    assert queued.status == "queued"
    assert running.status == "running"
