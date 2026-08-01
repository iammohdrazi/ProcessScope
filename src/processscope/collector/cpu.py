"""
ProcessScope — CPU Telemetry Collector.

Monitors:
  - Overall CPU usage for the hooked process
  - Per-core usage (system-wide)
  - User / kernel / idle time
  - Context switches (voluntary + involuntary)
  - CPU migrations
"""

from __future__ import annotations

import psutil

from processscope.collector.base import (
    BaseCollector, CollectorRegistry, EventCategory, TelemetryEvent,
)


@CollectorRegistry.register
class CPUCollector(BaseCollector):
    """Collects CPU telemetry for a hooked process."""

    @property
    def name(self) -> str:
        return "cpu"

    @property
    def category(self) -> EventCategory:
        return EventCategory.CPU

    def __init__(self, poll_interval_ms: int = 1000) -> None:
        super().__init__(poll_interval_ms)
        self._prev_ctx_switches = 0

    async def _collect(self) -> list[TelemetryEvent]:
        events: list[TelemetryEvent] = []

        try:
            proc = self._proc
            if proc is None:
                return events

            # Process CPU usage
            cpu_percent = proc.cpu_percent(interval=0)
            cpu_times = proc.cpu_times()
            cpu_num = proc.cpu_num() if hasattr(proc, "cpu_num") else -1

            # Context switches
            ctx = proc.num_ctx_switches()
            ctx_voluntary = ctx.voluntary
            ctx_involuntary = ctx.involuntary

            # System-wide CPU info
            system_percent = psutil.cpu_percent(interval=0, percpu=False)
            per_cpu = psutil.cpu_percent(interval=0, percpu=True)
            system_times = psutil.cpu_times()

            events.append(self.emit_event(
                title="CPU Sample",
                data={
                    "process": {
                        "cpu_percent": round(cpu_percent, 2),
                        "user_time": round(cpu_times.user, 4),
                        "system_time": round(cpu_times.system, 4),
                        "current_cpu": cpu_num,
                        "num_threads": proc.num_threads(),
                    },
                    "context_switches": {
                        "voluntary": ctx_voluntary,
                        "involuntary": ctx_involuntary,
                    },
                    "system": {
                        "total_percent": round(system_percent, 2),
                        "per_cpu_percent": [round(c, 2) for c in per_cpu],
                        "user": round(system_times.user, 2),
                        "system": round(system_times.system, 2),
                        "idle": round(system_times.idle, 2),
                        "iowait": round(getattr(system_times, "iowait", 0), 2),
                        "cpu_count": psutil.cpu_count(),
                        "cpu_count_logical": psutil.cpu_count(logical=True),
                    },
                },
            ))

        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            self._logger.warning("CPU collection failed", pid=self._pid, error=str(e))

        return events
