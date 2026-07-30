"""
ProcessScope — Database Schema Migrations.

Manages the SQLite schema with versioned migrations.
"""

from __future__ import annotations

import sqlite3

from processscope.logging import get_logger

logger = get_logger("storage.migrations")

MIGRATIONS: list[tuple[int, str, str]] = [
    (1, "Create events table", """
        CREATE TABLE IF NOT EXISTS events (
            id TEXT PRIMARY KEY,
            timestamp REAL NOT NULL,
            category TEXT NOT NULL,
            collector TEXT NOT NULL,
            pid INTEGER NOT NULL,
            severity TEXT DEFAULT 'info',
            title TEXT NOT NULL,
            message TEXT DEFAULT '',
            data TEXT DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
        CREATE INDEX IF NOT EXISTS idx_events_pid ON events(pid);
        CREATE INDEX IF NOT EXISTS idx_events_category ON events(category);
        CREATE INDEX IF NOT EXISTS idx_events_pid_category ON events(pid, category);
    """),
    (2, "Create processes table", """
        CREATE TABLE IF NOT EXISTS processes (
            pid INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            exe TEXT DEFAULT '',
            cmdline TEXT DEFAULT '',
            attached_at REAL NOT NULL,
            detached_at REAL,
            mode TEXT DEFAULT 'read_only',
            metadata TEXT DEFAULT '{}'
        );
    """),
    (3, "Create sessions table", """
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            pid INTEGER NOT NULL,
            start_time REAL NOT NULL,
            end_time REAL,
            event_count INTEGER DEFAULT 0,
            file_path TEXT DEFAULT '',
            metadata TEXT DEFAULT '{}'
        );
        CREATE INDEX IF NOT EXISTS idx_sessions_pid ON sessions(pid);
    """),
    (4, "Create schema_version table", """
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at REAL NOT NULL,
            description TEXT DEFAULT ''
        );
    """),
]


def run_migrations(conn: sqlite3.Connection) -> None:
    """Run all pending database migrations."""
    # Ensure schema_version table exists
    conn.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at REAL NOT NULL,
            description TEXT DEFAULT ''
        )
    """)

    # Get current version
    cursor = conn.execute("SELECT MAX(version) FROM schema_version")
    row = cursor.fetchone()
    current_version = row[0] if row[0] is not None else 0

    # Apply pending migrations
    import time
    for version, description, sql in MIGRATIONS:
        if version > current_version:
            logger.info("Applying migration", version=version, description=description)
            try:
                conn.executescript(sql)
                conn.execute(
                    "INSERT INTO schema_version (version, applied_at, description) VALUES (?, ?, ?)",
                    (version, time.time(), description),
                )
                conn.commit()
                logger.info("Migration applied", version=version)
            except sqlite3.Error as e:
                logger.error("Migration failed", version=version, error=str(e))
                raise

    final_cursor = conn.execute("SELECT MAX(version) FROM schema_version")
    final_row = final_cursor.fetchone()
    final_version = final_row[0] if final_row[0] else 0
    logger.info("Database schema up to date", version=final_version)
