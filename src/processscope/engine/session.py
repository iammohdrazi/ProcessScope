"""
ProcessScope — Session Recording & Replay.

Records telemetry sessions to disk for later replay and analysis.
Each session is stored as a compressed JSONL file.
"""

from __future__ import annotations

import gzip
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional, Generator

from processscope.collector.base import TelemetryEvent
from processscope.logging import get_logger

logger = get_logger("engine.session")


@dataclass
class Session:
    """A recording session for one or more PIDs."""
    session_id: str
    pid: int
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    event_count: int = 0
    file_path: str = ""
    is_active: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "pid": self.pid,
            "start_time": self.start_time,
            "start_time_iso": datetime.fromtimestamp(self.start_time, tz=timezone.utc).isoformat(),
            "end_time": self.end_time,
            "duration_seconds": round(self.end_time - self.start_time, 2) if self.end_time else round(time.time() - self.start_time, 2),
            "event_count": self.event_count,
            "file_path": self.file_path,
            "is_active": self.is_active,
        }


class SessionManager:
    """Manages recording and replay of telemetry sessions."""

    def __init__(self, session_dir: str = "/var/lib/processscope/sessions") -> None:
        self._session_dir = Path(session_dir)
        self._active_sessions: dict[int, Session] = {}
        self._file_handles: dict[int, gzip.GzipFile] = {}

    def start_recording(self, pid: int, session_id: str | None = None) -> Session:
        """Start recording events for a PID."""
        if pid in self._active_sessions:
            return self._active_sessions[pid]

        sid = session_id or f"{pid}_{int(time.time())}"
        file_path = self._session_dir / f"{sid}.jsonl.gz"

        try:
            self._session_dir.mkdir(parents=True, exist_ok=True)
            self._file_handles[pid] = gzip.open(file_path, "wt", encoding="utf-8")
        except PermissionError:
            # Fallback to temp directory in dev mode
            fallback = Path(f"/tmp/processscope/sessions")
            fallback.mkdir(parents=True, exist_ok=True)
            file_path = fallback / f"{sid}.jsonl.gz"
            self._file_handles[pid] = gzip.open(file_path, "wt", encoding="utf-8")

        session = Session(
            session_id=sid,
            pid=pid,
            file_path=str(file_path),
        )
        self._active_sessions[pid] = session

        logger.info("Session recording started", session_id=sid, pid=pid, path=str(file_path))
        return session

    def stop_recording(self, pid: int) -> Session | None:
        """Stop recording and close the session file."""
        session = self._active_sessions.pop(pid, None)
        if session:
            session.end_time = time.time()
            session.is_active = False

            fh = self._file_handles.pop(pid, None)
            if fh:
                fh.close()

            logger.info("Session recording stopped",
                        session_id=session.session_id, pid=pid,
                        events=session.event_count)

        return session

    def record_event(self, pid: int, event: TelemetryEvent) -> None:
        """Record an event to the active session for a PID."""
        if pid not in self._active_sessions:
            return

        session = self._active_sessions[pid]
        fh = self._file_handles.get(pid)
        if fh:
            try:
                fh.write(json.dumps(event.to_dict(), default=str) + "\n")
                session.event_count += 1
            except (OSError, ValueError):
                pass

    def list_sessions(self) -> list[dict]:
        """List all recorded sessions (active + saved)."""
        sessions: list[dict] = []

        # Active sessions
        for session in self._active_sessions.values():
            sessions.append(session.to_dict())

        # Saved sessions on disk
        if self._session_dir.exists():
            for f in sorted(self._session_dir.glob("*.jsonl.gz"), reverse=True):
                sid = f.stem.replace(".jsonl", "")
                if not any(s["session_id"] == sid for s in sessions):
                    stat = f.stat()
                    sessions.append({
                        "session_id": sid,
                        "file_path": str(f),
                        "file_size": stat.st_size,
                        "is_active": False,
                    })

        return sessions

    @staticmethod
    def replay_session(file_path: str) -> Generator[dict, None, None]:
        """
        Replay a recorded session by yielding events one by one.

        Args:
            file_path: Path to the .jsonl.gz session file.

        Yields:
            Event dictionaries.
        """
        path = Path(file_path)
        if not path.exists():
            logger.error("Session file not found", path=file_path)
            return

        with gzip.open(path, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        yield json.loads(line)
                    except json.JSONDecodeError:
                        continue

    def stop_all(self) -> None:
        """Stop all active recording sessions."""
        for pid in list(self._active_sessions.keys()):
            self.stop_recording(pid)
