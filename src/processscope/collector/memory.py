"""
ProcessScope — Memory Telemetry Collector.

Monitors:
  - RSS, VMS, shared, private memory
  - Memory maps (from /proc/[pid]/smaps_rollup)
  - Page faults (major + minor)
  - Memory growth tracking
  - Swap usage
"""

from __future__ import annotations

from pathlib import Path

import psutil

from processscope.collector.base import (
    BaseCollector, CollectorRegistry, EventCategory, EventSeverity, TelemetryEvent,
)


@CollectorRegistry.register
class MemoryCollector(BaseCollector):
    """Collects memory telemetry for a hooked process."""

    @property
    def name(self) -> str:
        return "memory"

    @property
    def category(self) -> EventCategory:
        return EventCategory.MEMORY

    def __init__(self, poll_interval_ms: int = 1000) -> None:
        super().__init__(poll_interval_ms)
        self._prev_rss: int = 0
        self._rss_history: list[int] = []
        self._max_history = 300  # 5 minutes at 1s interval

    async def _collect(self) -> list[TelemetryEvent]:
        events: list[TelemetryEvent] = []

        try:
            proc = psutil.Process(self._pid)
            mem = proc.memory_info()
            mem_full = proc.memory_full_info() if hasattr(proc, "memory_full_info") else None
            mem_percent = proc.memory_percent()
            mem_maps = None

            # Track memory growth
            rss = mem.rss
            growth = rss - self._prev_rss if self._prev_rss > 0 else 0
            self._prev_rss = rss

            self._rss_history.append(rss)
            if len(self._rss_history) > self._max_history:
                self._rss_history.pop(0)

            # System memory
            sys_mem = psutil.virtual_memory()
            swap = psutil.swap_memory()

            data = {
                "process": {
                    "rss": rss,
                    "rss_human": _human_bytes(rss),
                    "vms": mem.vms,
                    "vms_human": _human_bytes(mem.vms),
                    "shared": getattr(mem, "shared", 0),
                    "text": getattr(mem, "text", 0),
                    "data": getattr(mem, "data", 0),
                    "percent": round(mem_percent, 2),
                    "growth_bytes": growth,
                    "growth_human": _human_bytes(abs(growth)),
                    "growth_direction": "up" if growth > 0 else "down" if growth < 0 else "stable",
                },
                "system": {
                    "total": sys_mem.total,
                    "total_human": _human_bytes(sys_mem.total),
                    "available": sys_mem.available,
                    "available_human": _human_bytes(sys_mem.available),
                    "used": sys_mem.used,
                    "used_human": _human_bytes(sys_mem.used),
                    "percent": sys_mem.percent,
                    "swap_total": swap.total,
                    "swap_used": swap.used,
                    "swap_percent": swap.percent,
                },
            }

            # Extended memory info if available
            if mem_full:
                data["process"]["uss"] = getattr(mem_full, "uss", 0)
                data["process"]["pss"] = getattr(mem_full, "pss", 0)
                data["process"]["swap"] = getattr(mem_full, "swap", 0)

            # Read page faults from /proc
            page_faults = _read_page_faults(self._pid)
            if page_faults:
                data["page_faults"] = page_faults

            # Memory maps summary from /proc/[pid]/smaps_rollup
            smaps = _read_smaps_rollup(self._pid)
            if smaps:
                data["smaps"] = smaps

            events.append(self.emit_event(
                title="Memory Sample",
                data=data,
            ))

            # Alert on continuous growth
            if len(self._rss_history) >= 60:
                recent = self._rss_history[-60:]
                if all(recent[i] <= recent[i + 1] for i in range(len(recent) - 1)):
                    growth_total = recent[-1] - recent[0]
                    if growth_total > 10 * 1024 * 1024:  # 10 MB growth in 60 seconds
                        events.append(self.emit_event(
                            title="Possible Memory Leak Detected",
                            message=f"RSS grew {_human_bytes(growth_total)} in the last 60 seconds",
                            severity=EventSeverity.WARNING,
                            data={"growth_bytes": growth_total},
                            tags=["alert", "memory_leak"],
                        ))

        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            self._logger.warning("Memory collection failed", pid=self._pid, error=str(e))

        return events


def _read_page_faults(pid: int) -> dict | None:
    """Read page fault stats from /proc/[pid]/stat."""
    try:
        stat_path = Path(f"/proc/{pid}/stat")
        if stat_path.exists():
            content = stat_path.read_text().strip()
            # Fields in /proc/[pid]/stat (after the comm field)
            # Index 9: minflt, 10: cminflt, 11: majflt, 12: cmajflt
            parts = content.split(") ")
            if len(parts) > 1:
                fields = parts[1].split()
                if len(fields) > 10:
                    return {
                        "minor": int(fields[7]),
                        "minor_children": int(fields[8]),
                        "major": int(fields[9]),
                        "major_children": int(fields[10]),
                    }
    except (PermissionError, OSError, ValueError, IndexError):
        pass
    return None


def _read_smaps_rollup(pid: int) -> dict | None:
    """Read memory map summary from /proc/[pid]/smaps_rollup."""
    try:
        smaps_path = Path(f"/proc/{pid}/smaps_rollup")
        if smaps_path.exists():
            result = {}
            with open(smaps_path) as f:
                for line in f:
                    if ":" in line:
                        key, val = line.split(":", 1)
                        key = key.strip()
                        val = val.strip().replace(" kB", "")
                        try:
                            result[key] = int(val) * 1024  # Convert kB to bytes
                        except ValueError:
                            result[key] = val
            return result
    except (PermissionError, OSError):
        pass
    return None


def _human_bytes(n: int) -> str:
    """Format bytes into a human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}"
        n = int(n / 1024)
    return f"{n:.1f} TB"
