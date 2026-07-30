"""
ProcessScope — Thread Telemetry Collector.

Monitors:
  - Thread creation and exit
  - Per-thread CPU usage
  - Thread states
  - Thread count over time
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import psutil

from processscope.collector.base import (
    BaseCollector, CollectorRegistry, EventCategory, EventSeverity, TelemetryEvent,
)


@CollectorRegistry.register
class ThreadCollector(BaseCollector):
    """Collects thread telemetry for a hooked process."""

    @property
    def name(self) -> str:
        return "thread"

    @property
    def category(self) -> EventCategory:
        return EventCategory.THREAD

    def __init__(self, poll_interval_ms: int = 1000) -> None:
        super().__init__(poll_interval_ms)
        self._known_threads: set[int] = set()
        self._thread_count_history: list[int] = []

    async def _collect(self) -> list[TelemetryEvent]:
        events: list[TelemetryEvent] = []

        try:
            proc = psutil.Process(self._pid)
            threads = proc.threads()
            current_tids = {t.id for t in threads}

            # Detect new threads
            new_threads = current_tids - self._known_threads
            exited_threads = self._known_threads - current_tids

            for tid in new_threads:
                events.append(self.emit_event(
                    title="Thread Created",
                    message=f"Thread {tid} created",
                    data={"tid": tid},
                    tags=["thread_lifecycle"],
                ))

            for tid in exited_threads:
                events.append(self.emit_event(
                    title="Thread Exited",
                    message=f"Thread {tid} exited",
                    data={"tid": tid},
                    tags=["thread_lifecycle"],
                ))

            self._known_threads = current_tids

            # Collect per-thread data
            thread_data: list[dict[str, Any]] = []
            for t in threads:
                thread_info: dict[str, Any] = {
                    "tid": t.id,
                    "user_time": round(t.user_time, 4),
                    "system_time": round(t.system_time, 4),
                }

                # Try to get thread name and state from /proc
                status_info = _read_thread_status(self._pid, t.id)
                if status_info:
                    thread_info.update(status_info)

                thread_data.append(thread_info)

            # Track thread count
            thread_count = len(threads)
            self._thread_count_history.append(thread_count)
            if len(self._thread_count_history) > 300:
                self._thread_count_history.pop(0)

            events.append(self.emit_event(
                title="Thread Sample",
                data={
                    "thread_count": thread_count,
                    "threads": thread_data[:100],  # Cap for API size
                    "new_count": len(new_threads),
                    "exited_count": len(exited_threads),
                },
            ))

            # Alert: rapid thread creation
            if len(new_threads) > 10:
                events.append(self.emit_event(
                    title="Rapid Thread Creation",
                    message=f"{len(new_threads)} threads created in one cycle",
                    severity=EventSeverity.WARNING,
                    data={"new_thread_count": len(new_threads)},
                    tags=["alert"],
                ))

        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            self._logger.warning("Thread collection failed", pid=self._pid, error=str(e))

        return events


def _read_thread_status(pid: int, tid: int) -> dict | None:
    """Read thread name and state from /proc/[pid]/task/[tid]/status."""
    try:
        status_path = Path(f"/proc/{pid}/task/{tid}/status")
        if not status_path.exists():
            return None

        info = {}
        with open(status_path) as f:
            for line in f:
                if line.startswith("Name:"):
                    info["name"] = line.split(":", 1)[1].strip()
                elif line.startswith("State:"):
                    info["state"] = line.split(":", 1)[1].strip()
                elif line.startswith("voluntary_ctxt_switches:"):
                    info["voluntary_ctx_switches"] = int(line.split(":", 1)[1].strip())
                elif line.startswith("nonvoluntary_ctxt_switches:"):
                    info["involuntary_ctx_switches"] = int(line.split(":", 1)[1].strip())
        return info

    except (PermissionError, OSError, ValueError):
        return None
