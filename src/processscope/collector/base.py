"""
ProcessScope — Base Collector Interface & Event Types.

All telemetry collectors implement the BaseCollector abstract class.
Events flow through an asyncio queue to the telemetry engine.
"""

from __future__ import annotations

import asyncio
import time
import psutil
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

from processscope.logging import get_logger

logger = get_logger("collector.base")


# ── Event Types ───────────────────────────────────────────────────────

class EventCategory(str, Enum):
    """Categories for telemetry events."""
    CPU = "cpu"
    MEMORY = "memory"
    THREAD = "thread"
    NETWORK = "network"
    FILESYSTEM = "filesystem"
    SYSCALL = "syscall"
    HARDWARE = "hardware"
    PROCESS = "process"
    IO = "io"
    RUNTIME = "runtime"


class EventSeverity(str, Enum):
    """Severity levels for events."""
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


@dataclass
class TelemetryEvent:
    """
    A single telemetry event from a collector.

    This is the universal event type that flows through the entire pipeline:
    Collector → Engine → Timeline → Storage → API → Dashboard
    """
    id: str = field(default_factory=lambda: uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)
    category: EventCategory = EventCategory.PROCESS
    collector: str = ""
    pid: int = 0
    severity: EventSeverity = EventSeverity.INFO
    title: str = ""
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API/WebSocket transmission."""
        return {
            "id": self.id,
            "timestamp": self.timestamp,
            "timestamp_iso": datetime.fromtimestamp(self.timestamp, tz=timezone.utc).isoformat(),
            "category": self.category.value,
            "collector": self.collector,
            "pid": self.pid,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "data": self.data,
            "tags": self.tags,
        }


# ── Collector Status ──────────────────────────────────────────────────

class CollectorStatus(str, Enum):
    """Lifecycle states for a collector."""
    IDLE = "idle"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"
    ERROR = "error"


# ── Base Collector ────────────────────────────────────────────────────

class BaseCollector(ABC):
    """
    Abstract base class for all telemetry collectors.

    Subclasses must implement:
      - name: str property
      - category: EventCategory property
      - _collect(): Perform one collection cycle

    The base class handles:
      - Start/stop lifecycle
      - Periodic collection via asyncio
      - Event emission to the engine queue
      - Error handling and status tracking
    """

    def __init__(self, poll_interval_ms: int = 1000) -> None:
        self._poll_interval = poll_interval_ms / 1000.0  # Convert to seconds
        self._status = CollectorStatus.IDLE
        self._event_queue: Optional[asyncio.Queue[TelemetryEvent]] = None
        self._task: Optional[asyncio.Task] = None
        self._pid: int = 0
        self._proc: Optional[psutil.Process] = None
        self._collect_count: int = 0
        self._error_count: int = 0
        self._last_error: str = ""
        self._logger = get_logger(f"collector.{self.name}")

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique name for this collector (e.g., 'cpu', 'memory')."""
        ...

    @property
    @abstractmethod
    def category(self) -> EventCategory:
        """Event category for this collector."""
        ...

    @property
    def status(self) -> CollectorStatus:
        """Current collector status."""
        return self._status

    @abstractmethod
    async def _collect(self) -> list[TelemetryEvent]:
        """
        Perform one collection cycle.

        Returns:
            List of telemetry events collected in this cycle.
        """
        ...

    async def start(self, pid: int, event_queue: asyncio.Queue[TelemetryEvent]) -> None:
        """
        Start the collector for a specific PID.

        Args:
            pid: Process ID to collect telemetry for.
            event_queue: Queue to emit events into (consumed by engine).
        """
        self._pid = pid
        self._proc = psutil.Process(pid)
        self._event_queue = event_queue
        self._status = CollectorStatus.STARTING

        self._logger.info("Starting collector", pid=pid, interval_ms=int(self._poll_interval * 1000))

        self._status = CollectorStatus.RUNNING
        self._task = asyncio.create_task(self._run_loop())

    async def stop(self) -> None:
        """Stop the collector gracefully."""
        self._status = CollectorStatus.STOPPING
        self._logger.info("Stopping collector", pid=self._pid)

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        self._status = CollectorStatus.STOPPED
        self._logger.info("Collector stopped", pid=self._pid, total_collections=self._collect_count)

    async def _run_loop(self) -> None:
        """Main collection loop."""
        while self._status == CollectorStatus.RUNNING:
            try:
                events = await self._collect()
                self._collect_count += 1

                if self._event_queue and events:
                    for event in events:
                        event.pid = self._pid
                        event.collector = self.name
                        event.category = self.category
                        await self._event_queue.put(event)

            except asyncio.CancelledError:
                break
            except Exception as e:
                import psutil
                if isinstance(e, (psutil.NoSuchProcess, ProcessLookupError)) or "process PID not found" in str(e):
                    self._logger.info("Process exited, collector stopping", pid=self._pid)
                    self._status = CollectorStatus.STOPPED
                    break

                self._error_count += 1
                self._last_error = str(e)
                self._logger.error(
                    "Collection error",
                    pid=self._pid,
                    error=str(e),
                    error_count=self._error_count,
                    exc_info=True,
                )
                if self._error_count > 50:
                    self._status = CollectorStatus.ERROR
                    self._logger.critical("Too many errors, collector disabled", pid=self._pid)
                    break

            await asyncio.sleep(self._poll_interval)

    def emit_event(self, title: str, message: str = "", data: dict | None = None,
                   severity: EventSeverity = EventSeverity.INFO,
                   tags: list[str] | None = None) -> TelemetryEvent:
        """Helper to create a properly structured event."""
        return TelemetryEvent(
            category=self.category,
            collector=self.name,
            pid=self._pid,
            severity=severity,
            title=title,
            message=message,
            data=data or {},
            tags=tags or [],
        )

    def status_dict(self) -> dict[str, Any]:
        """Return collector status as a dictionary."""
        return {
            "name": self.name,
            "category": self.category.value,
            "status": self._status.value,
            "pid": self._pid,
            "poll_interval_ms": int(self._poll_interval * 1000),
            "collect_count": self._collect_count,
            "error_count": self._error_count,
            "last_error": self._last_error,
        }


# ── Collector Registry ────────────────────────────────────────────────

class CollectorRegistry:
    """Registry of available collector classes."""

    _collectors: dict[str, type[BaseCollector]] = {}

    @classmethod
    def register(cls, collector_class: type[BaseCollector]) -> type[BaseCollector]:
        """Register a collector class (can be used as a decorator)."""
        # Instantiate temporarily to get the name
        instance = collector_class.__new__(collector_class)
        name = instance.name
        cls._collectors[name] = collector_class
        logger.debug("Registered collector", name=name)
        return collector_class

    @classmethod
    def get(cls, name: str) -> type[BaseCollector] | None:
        """Get a collector class by name."""
        return cls._collectors.get(name)

    @classmethod
    def create_all(cls, names: list[str], poll_interval_ms: int = 1000) -> list[BaseCollector]:
        """Create instances of specified collectors."""
        instances = []
        for name in names:
            collector_class = cls._collectors.get(name)
            if collector_class:
                instances.append(collector_class(poll_interval_ms=poll_interval_ms))
            else:
                logger.warning("Unknown collector", name=name)
        return instances

    @classmethod
    def available(cls) -> list[str]:
        """List all registered collector names."""
        return list(cls._collectors.keys())
