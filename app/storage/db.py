from __future__ import annotations

import sqlite3

from app.core.config import get_settings

SCHEMA_VERSION = 2
STALE_RUN_RECOVERY_MINUTES = 120

_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    mode TEXT NOT NULL,
    idempotency_key TEXT UNIQUE,
    created_at TEXT NOT NULL,
    started_at TEXT,
    finished_at TEXT,
    error TEXT,
    metrics_json TEXT
);

CREATE TABLE IF NOT EXISTS documents (
    document_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    source_type TEXT NOT NULL,
    filename TEXT NOT NULL,
    slug TEXT NOT NULL,
    parse_status TEXT NOT NULL,
    document_hash TEXT,
    char_count INTEGER NOT NULL DEFAULT 0,
    raw_text TEXT NOT NULL DEFAULT '',
    page_texts_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS candidate_results (
    candidate_id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    candidate_name TEXT,
    status TEXT NOT NULL,
    dossier_json TEXT,
    errors_json TEXT NOT NULL DEFAULT '[]',
    sort_score INTEGER NOT NULL DEFAULT -1,
    created_at TEXT NOT NULL,
    override_recommendation TEXT,
    override_rationale TEXT,
    override_actor TEXT,
    override_at TEXT
);

CREATE TABLE IF NOT EXISTS candidate_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    candidate_id TEXT NOT NULL,
    run_id TEXT NOT NULL,
    body TEXT NOT NULL,
    author TEXT NOT NULL DEFAULT '面试官',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS decision_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    candidate_id TEXT,
    event_type TEXT NOT NULL,
    ts TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'system',
    node_name TEXT NOT NULL,
    model TEXT,
    prompt_name TEXT,
    prompt_version TEXT,
    input_hash TEXT,
    output_hash TEXT,
    schema_name TEXT,
    validation_status TEXT,
    repair_attempt INTEGER,
    latency_ms INTEGER,
    input_tokens INTEGER,
    output_tokens INTEGER,
    metadata_json TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS validation_summaries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    candidate_id TEXT,
    node_name TEXT NOT NULL,
    schema_name TEXT NOT NULL,
    status TEXT NOT NULL,
    error_count INTEGER NOT NULL DEFAULT 0,
    repair_attempts INTEGER NOT NULL DEFAULT 0,
    messages_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS structured_generation_cache (
    cache_key TEXT PRIMARY KEY,
    prompt_name TEXT NOT NULL,
    prompt_version TEXT NOT NULL,
    schema_name TEXT NOT NULL,
    model TEXT NOT NULL,
    input_hash TEXT NOT NULL,
    output_hash TEXT NOT NULL,
    output_text TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS eval_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT,
    name TEXT NOT NULL,
    status TEXT NOT NULL,
    value REAL,
    details TEXT NOT NULL DEFAULT '',
    ts TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_run ON decision_events(run_id);
CREATE INDEX IF NOT EXISTS idx_docs_run ON documents(run_id);
CREATE INDEX IF NOT EXISTS idx_candidates_run ON candidate_results(run_id);
CREATE INDEX IF NOT EXISTS idx_notes_candidate ON candidate_notes(candidate_id);
CREATE INDEX IF NOT EXISTS idx_structured_generation_cache_input
    ON structured_generation_cache(input_hash);
"""


def connect() -> sqlite3.Connection:
    path = get_settings().database_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    with connect() as conn:
        conn.executescript(_SCHEMA)
        columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(documents)").fetchall()
        }
        if "page_texts_json" not in columns:
            conn.execute(
                "ALTER TABLE documents ADD COLUMN page_texts_json TEXT NOT NULL DEFAULT '[]'"
            )
        if "source_bytes" not in columns:
            conn.execute("ALTER TABLE documents ADD COLUMN source_bytes BLOB")
        candidate_columns = {
            row["name"]
            for row in conn.execute("PRAGMA table_info(candidate_results)").fetchall()
        }
        for column in (
            "override_recommendation",
            "override_rationale",
            "override_actor",
            "override_at",
        ):
            if column not in candidate_columns:
                conn.execute(f"ALTER TABLE candidate_results ADD COLUMN {column} TEXT")
        conn.execute(
            "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
            (SCHEMA_VERSION,),
        )
        # BackgroundTasks are in-process, not durable. If the API process dies
        # mid-run, an old `queued`/`running` row would otherwise stay stuck
        # forever. Do not fail fresh rows immediately: dev-server reloads or
        # test processes can initialize the DB while another process is still
        # actively executing the run.
        conn.execute(
            "UPDATE runs SET status = 'failed', finished_at = CURRENT_TIMESTAMP,"
            " error = '启动时恢复了孤立运行；请创建新的运行'"
            " WHERE status IN ('queued', 'running')"
            " AND datetime(COALESCE(started_at, created_at))"
            f" < datetime('now', '-{STALE_RUN_RECOVERY_MINUTES} minutes')"
        )
