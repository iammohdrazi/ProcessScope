"""
ProcessScope — Unified Event Timeline.

Maintains a synchronized historical timeline of all telemetry events
across all collectors and PIDs, supporting search, filtering, and replay.
"""

from __future__ import annotations

import threading
from collections import deque
from typing import Any, Optional

from processscope.collector.base import TelemetryEvent


class Timeline:
    """
    Thread-safe circular buffer of telemetry events
    with filtering and search capabilities.
    """

    def __init__(self, max_events: int = 10000) -> None:
        self._events: deque[TelemetryEvent] = deque(maxlen=max_events)
        self._lock = threading.Lock()

    @property
    def size(self) -> int:
        return len(self._events)

    def add_event(self, event: TelemetryEvent) -> None:
        """Add an event to the timeline (thread-safe)."""
        with self._lock:
            self._events.append(event)

    def get_events(
        self,
        pid: int | None = None,
        limit: int = 100,
        category: str | None = None,
        severity: str | None = None,
        since_timestamp: float | None = None,
        search: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Get filtered events from the timeline.

        Args:
            pid: Filter by process ID.
            limit: Maximum number of events to return.
            category: Filter by event category (e.g., "cpu", "memory").
            severity: Filter by severity ("info", "warning", "critical").
            since_timestamp: Only events after this Unix timestamp.
            search: Full-text search in title and message.

        Returns:
            List of event dictionaries, newest first.
        """
        with self._lock:
            results: list[dict[str, Any]] = []

            for event in reversed(self._events):
                if len(results) >= limit:
                    break

                # Apply filters
                if pid is not None and event.pid != pid:
                    continue
                if category and event.category.value != category:
                    continue
                if severity and event.severity.value != severity:
                    continue
                if since_timestamp and event.timestamp < since_timestamp:
                    continue
                if search:
                    search_lower = search.lower()
                    if (search_lower not in event.title.lower() and
                            search_lower not in event.message.lower() and
                            search_lower not in str(event.data).lower()):
                        continue

                results.append(event.to_dict())

            return results

    def get_timeline_summary(self, pid: int | None = None, bucket_seconds: int = 60) -> list[dict]:
        """
        Get a summary of events bucketed by time intervals.

        Returns a list of time buckets with event counts per category.
        """
        with self._lock:
            buckets: dict[int, dict[str, int]] = {}

            for event in self._events:
                if pid is not None and event.pid != pid:
                    continue

                bucket_ts = int(event.timestamp // bucket_seconds) * bucket_seconds
                if bucket_ts not in buckets:
                    buckets[bucket_ts] = {"total": 0}

                buckets[bucket_ts]["total"] += 1
                cat = event.category.value
                buckets[bucket_ts][cat] = buckets[bucket_ts].get(cat, 0) + 1

            return [
                {"timestamp": ts, **counts}
                for ts, counts in sorted(buckets.items())
            ]

    def clear(self, pid: int | None = None) -> None:
        """Clear timeline events."""
        with self._lock:
            if pid is None:
                self._events.clear()
            else:
                self._events = deque(
                    (e for e in self._events if e.pid != pid),
                    maxlen=self._events.maxlen,
                )
