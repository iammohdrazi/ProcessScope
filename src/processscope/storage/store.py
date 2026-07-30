"""
ProcessScope — SQLite Telemetry Store.

Persists telemetry events, process metadata, and session data to SQLite.
Uses aiosqlite for async operations.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Optional

from processscope.logging import get_logger
from processscope.storage.migrations import run_migrations

logger = get_logger("storage")


class TelemetryStore:
    """
    SQLite-backed telemetry storage with sync API.
    Handles event persistence, querying, and cleanup.
    """

    def __init__(self, db_path: str = "/var/lib/processscope/db/processscope.db") -> None:
        self._db_path = db_path
        self._conn: Optional[sqlite3.Connection] = None

    def open(self) -> None:
        """Open the database connection and run migrations."""
        db_dir = Path(self._db_path).parent
        try:
            db_dir.mkdir(parents=True, exist_ok=True)
        except PermissionError:
            # Fallback for development
            fallback = Path("/tmp/processscope/db")
            fallback.mkdir(parents=True, exist_ok=True)
            self._db_path = str(fallback / "processscope.db")
            logger.warning("Using fallback DB path", path=self._db_path)

        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute("PRAGMA cache_size=-64000")  # 64MB cache

        run_migrations(self._conn)
        logger.info("Database opened", path=self._db_path)

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("Database closed")

    def store_event(self, event: dict[str, Any]) -> None:
        """Store a telemetry event."""
        if not self._conn:
            return

        self._conn.execute(
            """INSERT INTO events (id, timestamp, category, collector, pid, severity, title, message, data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                event.get("id"),
                event.get("timestamp"),
                event.get("category"),
                event.get("collector"),
                event.get("pid"),
                event.get("severity"),
                event.get("title"),
                event.get("message"),
                json.dumps(event.get("data", {})),
            ),
        )
        self._conn.commit()

    def store_events_batch(self, events: list[dict[str, Any]]) -> None:
        """Store a batch of events efficiently."""
        if not self._conn or not events:
            return

        self._conn.executemany(
            """INSERT OR IGNORE INTO events (id, timestamp, category, collector, pid, severity, title, message, data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            [
                (
                    e.get("id"), e.get("timestamp"), e.get("category"),
                    e.get("collector"), e.get("pid"), e.get("severity"),
                    e.get("title"), e.get("message"),
                    json.dumps(e.get("data", {})),
                )
                for e in events
            ],
        )
        self._conn.commit()

    def query_events(
        self,
        pid: int | None = None,
        category: str | None = None,
        limit: int = 100,
        offset: int = 0,
        since: float | None = None,
        search: str | None = None,
    ) -> list[dict]:
        """Query stored events with filters."""
        if not self._conn:
            return []

        query = "SELECT * FROM events WHERE 1=1"
        params: list[Any] = []

        if pid is not None:
            query += " AND pid = ?"
            params.append(pid)
        if category:
            query += " AND category = ?"
            params.append(category)
        if since:
            query += " AND timestamp > ?"
            params.append(since)
        if search:
            query += " AND (title LIKE ? OR message LIKE ?)"
            params.extend([f"%{search}%", f"%{search}%"])

        query += " ORDER BY timestamp DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        cursor = self._conn.execute(query, params)
        rows = cursor.fetchall()

        return [
            {
                "id": row["id"],
                "timestamp": row["timestamp"],
                "category": row["category"],
                "collector": row["collector"],
                "pid": row["pid"],
                "severity": row["severity"],
                "title": row["title"],
                "message": row["message"],
                "data": json.loads(row["data"]) if row["data"] else {},
            }
            for row in rows
        ]

    def cleanup_old_events(self, retention_days: int = 7) -> int:
        """Delete events older than retention period."""
        if not self._conn:
            return 0

        cutoff = time.time() - (retention_days * 86400)
        cursor = self._conn.execute("DELETE FROM events WHERE timestamp < ?", (cutoff,))
        self._conn.commit()
        deleted = cursor.rowcount
        if deleted > 0:
            logger.info("Cleaned up old events", deleted=deleted, retention_days=retention_days)
            self._conn.execute("VACUUM")
        return deleted

    def get_stats(self) -> dict[str, Any]:
        """Get database statistics."""
        if not self._conn:
            return {}

        cursor = self._conn.execute("SELECT COUNT(*) as count FROM events")
        total_events = cursor.fetchone()["count"]

        cursor = self._conn.execute(
            "SELECT category, COUNT(*) as count FROM events GROUP BY category"
        )
        by_category = {row["category"]: row["count"] for row in cursor.fetchall()}

        db_size = Path(self._db_path).stat().st_size if Path(self._db_path).exists() else 0

        return {
            "total_events": total_events,
            "by_category": by_category,
            "db_path": self._db_path,
            "db_size": db_size,
            "db_size_human": _human_bytes(db_size),
        }


def _human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}"
        n = int(n / 1024)
    return f"{n:.1f} TB"
