"""
ProcessScope — Central Telemetry Engine.

Orchestrates all telemetry collection:
  - Manages collector lifecycle (start/stop per PID)
  - Consumes events from collector queues
  - Feeds events to Timeline and Storage
  - Provides streaming interface for WebSocket API
  - Auto-detects process exits and cleans up collectors
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Callable, Optional

from processscope.collector.base import BaseCollector, CollectorRegistry, CollectorStatus, TelemetryEvent
from processscope.engine.timeline import Timeline
from processscope.engine.session import SessionManager
from processscope.logging import get_logger
from processscope.logging.error_codes import PS112

logger = get_logger("engine")


class TelemetryEngine:
    """
    Central telemetry engine that orchestrates collection,
    correlation, storage, and streaming of all telemetry data.

    Includes a background monitor that detects when hooked processes
    exit and automatically stops their collectors — emitting a single
    structured log line rather than per-collector warning spam.
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
        self._monitor_task: Optional[asyncio.Task] = None

        # Callback invoked when a process exits (set by the API layer)
        self.on_process_exited: Optional[Callable[[int, str], None]] = None

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
        logger.info(
            "Starting telemetry engine",
            collectors=self._collector_names,
            poll_interval_ms=self._poll_interval_ms,
        )
        self._running = True
        self._start_time = datetime.now(timezone.utc)

        # Start the background process exit monitor
        self._monitor_task = asyncio.create_task(self._monitor_processes())

    async def stop(self) -> None:
        """Stop the engine and all active collectors."""
        logger.info("Stopping telemetry engine")
        self._running = False

        # Stop monitor task first
        if self._monitor_task:
            self._monitor_task.cancel()
            try:
                await self._monitor_task
            except asyncio.CancelledError:
                pass

        # Stop all collectors for all PIDs
        for pid in list(self._pid_collectors.keys()):
            await self.stop_collectors(pid)

        logger.info("Telemetry engine stopped", total_events=self._total_events)

    async def _monitor_processes(self) -> None:
        """
        Background task: checks every second if any hooked process has exited.

        When all collectors for a PID have stopped themselves (because the
        process is gone), this monitor calls stop_collectors() to clean up
        the remaining infrastructure and emits a single structured log line.
        """
        while self._running:
            try:
                await asyncio.sleep(1.0)

                for pid, collectors in list(self._pid_collectors.items()):
                    if not collectors:
                        continue

                    # Check if the process exited (any collector flagged it)
                    exited = any(c.process_exited for c in collectors)
                    all_stopped = all(
                        c.status in (CollectorStatus.STOPPED, CollectorStatus.ERROR)
                        for c in collectors
                    )

                    if exited or all_stopped:
                        # Determine the process name from any available collector
                        pid_name = f"pid={pid}"
                        if collectors:
                            pid_name = f"pid={pid}"

                        # Emit a single clean log line for the process exit
                        logger.info(PS112, pid=pid)

                        # Clean up all infrastructure for this PID
                        await self.stop_collectors(pid)

                        # Notify the attacher/API layer to update state
                        if self.on_process_exited:
                            try:
                                self.on_process_exited(pid, "")
                            except Exception:
                                pass

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error("Process monitor error", error=str(e))

    async def start_collectors(self, pid: int) -> None:
        """
        Start all configured collectors for a specific PID.

        Args:
            pid: Process ID to collect telemetry for.
        """
        if pid in self._pid_collectors:
            return

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
        started = []
        for collector in collectors:
            try:
                await collector.start(pid, queue)
                started.append(collector)
            except Exception as e:
                logger.error(
                    "Failed to start collector",
                    collector=collector.name,
                    pid=pid,
                    error=str(e),
                )

        self._pid_collectors[pid] = started

        # Start event consumer task
        self._consumer_tasks[pid] = asyncio.create_task(self._consume_events(pid, queue))

    async def stop_collectors(self, pid: int) -> None:
        """Stop all collectors for a specific PID."""
        if pid not in self._pid_collectors:
            return

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
                logger.error(
                    "Error stopping collector",
                    collector=collector.name,
                    pid=pid,
                    error=str(e),
                )

        del self._pid_collectors[pid]
        if pid in self._pid_queues:
            del self._pid_queues[pid]

    async def _consume_events(self, pid: int, queue: asyncio.Queue[TelemetryEvent]) -> None:
        """Consume events from a PID's collector queue and distribute them."""
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

    def subscribe(self, subscriber_id: str, callback: Callable[[TelemetryEvent], Any]) -> None:
        """Subscribe to receive all telemetry events."""
        self._subscribers[subscriber_id] = callback

    def unsubscribe(self, subscriber_id: str) -> None:
        """Remove a subscriber."""
        self._subscribers.pop(subscriber_id, None)

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
