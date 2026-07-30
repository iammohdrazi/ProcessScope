"""
ProcessScope — Central Telemetry Engine.

Orchestrates all telemetry collection:
  - Manages collector lifecycle (start/stop per PID)
  - Consumes events from collector queues
  - Feeds events to Timeline and Storage
  - Provides streaming interface for WebSocket API
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from processscope.collector.base import BaseCollector, CollectorRegistry, TelemetryEvent
from processscope.engine.timeline import Timeline
from processscope.engine.session import SessionManager
from processscope.logging import get_logger

logger = get_logger("engine")


class TelemetryEngine:
    """
    Central telemetry engine that orchestrates collection,
    correlation, storage, and streaming of all telemetry data.
    """

    def __init__(
        self,
        collector_names: list[str],
        poll_interval_ms: int = 1000,
        buffer_size: int = 10000,
    ) -> None:
        self._collector_names = collector_names
        self._poll_interval_ms = poll_interval_ms
        self._buffer_size = buffer_size

        # Per-PID collector sets
        self._pid_collectors: dict[int, list[BaseCollector]] = {}
        self._pid_queues: dict[int, asyncio.Queue[TelemetryEvent]] = {}
        self._consumer_tasks: dict[int, asyncio.Task] = {}

        # Unified timeline
        self.timeline = Timeline(max_events=buffer_size)

        # Session manager
        self.session_manager = SessionManager()

        # WebSocket subscribers: callback functions that receive events
        self._subscribers: dict[str, Callable[[TelemetryEvent], Any]] = {}

        # Engine state
        self._running = False
        self._total_events: int = 0
        self._start_time: Optional[datetime] = None

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def total_events(self) -> int:
        return self._total_events

    @property
    def uptime_seconds(self) -> float:
        if self._start_time:
            return (datetime.now(timezone.utc) - self._start_time).total_seconds()
        return 0.0

    async def start(self) -> None:
        """Start the telemetry engine."""
        logger.info("Starting telemetry engine",
                     collectors=self._collector_names,
                     poll_interval_ms=self._poll_interval_ms)
        self._running = True
        self._start_time = datetime.now(timezone.utc)

    async def stop(self) -> None:
        """Stop the engine and all active collectors."""
        logger.info("Stopping telemetry engine")
        self._running = False

        # Stop all collectors for all PIDs
        for pid in list(self._pid_collectors.keys()):
            await self.stop_collectors(pid)

        logger.info("Telemetry engine stopped", total_events=self._total_events)

    async def start_collectors(self, pid: int) -> None:
        """
        Start all configured collectors for a specific PID.

        Args:
            pid: Process ID to collect telemetry for.
        """
        if pid in self._pid_collectors:
            logger.warning("Collectors already running for PID", pid=pid)
            return

        logger.info("Starting collectors for PID", pid=pid, collectors=self._collector_names)

        # Import all collector modules to trigger registration
        _import_collectors()

        # Create collector instances
        collectors = CollectorRegistry.create_all(
            self._collector_names,
            poll_interval_ms=self._poll_interval_ms,
        )

        if not collectors:
            logger.warning("No collectors created", pid=pid)
            return

        # Create event queue for this PID
        queue: asyncio.Queue[TelemetryEvent] = asyncio.Queue(maxsize=self._buffer_size)
        self._pid_queues[pid] = queue

        # Start all collectors
        for collector in collectors:
            try:
                await collector.start(pid, queue)
                logger.info("Collector started", collector=collector.name, pid=pid)
            except Exception as e:
                logger.error("Failed to start collector",
                             collector=collector.name, pid=pid, error=str(e))

        self._pid_collectors[pid] = collectors

        # Start event consumer task
        self._consumer_tasks[pid] = asyncio.create_task(self._consume_events(pid, queue))

    async def stop_collectors(self, pid: int) -> None:
        """Stop all collectors for a specific PID."""
        if pid not in self._pid_collectors:
            return

        logger.info("Stopping collectors for PID", pid=pid)

        # Cancel consumer task
        if pid in self._consumer_tasks:
            self._consumer_tasks[pid].cancel()
            try:
                await self._consumer_tasks[pid]
            except asyncio.CancelledError:
                pass
            del self._consumer_tasks[pid]

        # Stop each collector
        for collector in self._pid_collectors[pid]:
            try:
                await collector.stop()
            except Exception as e:
                logger.error("Error stopping collector",
                             collector=collector.name, pid=pid, error=str(e))

        del self._pid_collectors[pid]
        del self._pid_queues[pid]

    async def _consume_events(self, pid: int, queue: asyncio.Queue[TelemetryEvent]) -> None:
        """Consume events from a PID's collector queue and distribute them."""
        logger.debug("Event consumer started", pid=pid)

        while self._running:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=1.0)
                self._total_events += 1

                # Add to unified timeline
                self.timeline.add_event(event)

                # Record in session if active
                self.session_manager.record_event(pid, event)

                # Notify all subscribers (WebSocket connections)
                for sub_id, callback in list(self._subscribers.items()):
                    try:
                        result = callback(event)
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception:
                        pass

            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Event consumer error", pid=pid, error=str(e))

        logger.debug("Event consumer stopped", pid=pid)

    def subscribe(self, subscriber_id: str, callback: Callable[[TelemetryEvent], Any]) -> None:
        """Subscribe to receive all telemetry events."""
        self._subscribers[subscriber_id] = callback
        logger.debug("Subscriber added", subscriber_id=subscriber_id)

    def unsubscribe(self, subscriber_id: str) -> None:
        """Remove a subscriber."""
        self._subscribers.pop(subscriber_id, None)
        logger.debug("Subscriber removed", subscriber_id=subscriber_id)

    def get_collector_status(self, pid: int | None = None) -> list[dict[str, Any]]:
        """Get status of all active collectors."""
        statuses = []
        targets = {pid: self._pid_collectors[pid]} if pid and pid in self._pid_collectors else self._pid_collectors

        for target_pid, collectors in targets.items():
            for c in collectors:
                status = c.status_dict()
                status["pid"] = target_pid
                statuses.append(status)

        return statuses

    def get_recent_events(self, pid: int | None = None, limit: int = 100,
                          category: str | None = None) -> list[dict]:
        """Get recent events from the timeline."""
        return self.timeline.get_events(pid=pid, limit=limit, category=category)

    def status_dict(self) -> dict[str, Any]:
        """Return engine status as a dictionary."""
        return {
            "running": self._running,
            "total_events": self._total_events,
            "uptime_seconds": round(self.uptime_seconds, 1),
            "active_pids": list(self._pid_collectors.keys()),
            "active_collectors": sum(len(c) for c in self._pid_collectors.values()),
            "subscriber_count": len(self._subscribers),
            "timeline_size": self.timeline.size,
        }


def _import_collectors() -> None:
    """Import all collector modules to trigger @CollectorRegistry.register decorators."""
    # These imports trigger the @CollectorRegistry.register decorator on each class
    import processscope.collector.cpu       # noqa: F401
    import processscope.collector.memory    # noqa: F401
    import processscope.collector.thread    # noqa: F401
    import processscope.collector.network   # noqa: F401
    import processscope.collector.filesystem  # noqa: F401
    import processscope.collector.syscall   # noqa: F401
    import processscope.collector.hardware  # noqa: F401
