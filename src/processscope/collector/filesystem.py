"""
ProcessScope — File System Telemetry Collector.

Monitors:
  - Open file descriptors
  - File opens, reads, writes (via /proc/[pid]/fdinfo)
  - File paths being accessed
  - File descriptor count over time
  - Disk I/O counters
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import psutil

from processscope.collector.base import (
    BaseCollector, CollectorRegistry, EventCategory, EventSeverity, TelemetryEvent,
)


@CollectorRegistry.register
class FilesystemCollector(BaseCollector):
    """Collects file system telemetry for a hooked process."""

    @property
    def name(self) -> str:
        return "filesystem"

    @property
    def category(self) -> EventCategory:
        return EventCategory.FILESYSTEM

    def __init__(self, poll_interval_ms: int = 1000) -> None:
        super().__init__(poll_interval_ms)
        self._known_fds: set[str] = set()
        self._prev_io_read: int = 0
        self._prev_io_write: int = 0

    async def _collect(self) -> list[TelemetryEvent]:
        events: list[TelemetryEvent] = []

        try:
            proc = self._proc
            if proc is None:
                return events

            # Open files
            open_files: list[dict[str, Any]] = []
            try:
                for f in proc.open_files():
                    open_files.append({
                        "path": f.path,
                        "fd": f.fd,
                        "mode": getattr(f, "mode", ""),
                    })
            except (psutil.AccessDenied, psutil.NoSuchProcess):
                pass

            current_fds = {f["path"] for f in open_files}
            new_files = current_fds - self._known_fds
            closed_files = self._known_fds - current_fds
            self._known_fds = current_fds

            # File lifecycle events
            for path in new_files:
                events.append(self.emit_event(
                    title="File Opened",
                    message=path,
                    data={"path": path},
                    tags=["file_lifecycle"],
                ))

            for path in closed_files:
                events.append(self.emit_event(
                    title="File Closed",
                    message=path,
                    data={"path": path},
                    tags=["file_lifecycle"],
                ))

            # FD count
            try:
                num_fds = proc.num_fds()
            except (psutil.AccessDenied, AttributeError):
                num_fds = len(open_files)

            # I/O counters
            io_data: dict[str, Any] = {}
            try:
                io = proc.io_counters()
                read_rate = io.read_bytes - self._prev_io_read if self._prev_io_read > 0 else 0
                write_rate = io.write_bytes - self._prev_io_write if self._prev_io_write > 0 else 0
                self._prev_io_read = io.read_bytes
                self._prev_io_write = io.write_bytes

                io_data = {
                    "read_bytes": io.read_bytes,
                    "read_bytes_human": _human_bytes(io.read_bytes),
                    "write_bytes": io.write_bytes,
                    "write_bytes_human": _human_bytes(io.write_bytes),
                    "read_count": io.read_count,
                    "write_count": io.write_count,
                    "read_rate": read_rate,
                    "read_rate_human": _human_bytes(read_rate) + "/s",
                    "write_rate": write_rate,
                    "write_rate_human": _human_bytes(write_rate) + "/s",
                }
            except (psutil.AccessDenied, psutil.NoSuchProcess, AttributeError):
                pass

            # Categorize files
            categories: dict[str, int] = {}
            for f in open_files:
                cat = _categorize_file(f["path"])
                categories[cat] = categories.get(cat, 0) + 1

            # Disk partitions used by the process
            disk_info = _get_disk_info_for_files([f["path"] for f in open_files])

            events.append(self.emit_event(
                title="Filesystem Sample",
                data={
                    "num_fds": num_fds,
                    "open_files": open_files[:100],
                    "file_categories": categories,
                    "io": io_data,
                    "new_files": len(new_files),
                    "closed_files": len(closed_files),
                    "disk_info": disk_info,
                },
            ))

            # FD leak alert
            if num_fds > 1000:
                events.append(self.emit_event(
                    title="High FD Count",
                    message=f"Process has {num_fds} open file descriptors",
                    severity=EventSeverity.WARNING,
                    data={"num_fds": num_fds},
                    tags=["alert", "fd_leak"],
                ))

        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            self._logger.warning("Filesystem collection failed", pid=self._pid, error=str(e))

        return events


def _categorize_file(path: str) -> str:
    """Categorize a file path."""
    if path.startswith("/proc"):
        return "proc"
    elif path.startswith("/dev"):
        return "device"
    elif path.startswith("/tmp") or path.startswith("/var/tmp"):
        return "temporary"
    elif path.endswith((".so", ".so.*")) or "/lib/" in path:
        return "shared_library"
    elif path.endswith((".log",)):
        return "log"
    elif path.endswith((".conf", ".cfg", ".yaml", ".yml", ".json", ".toml", ".ini")):
        return "config"
    elif path.endswith((".db", ".sqlite", ".sqlite3")):
        return "database"
    elif path.startswith("/sys"):
        return "sysfs"
    elif "/socket" in path.lower() or path.startswith("socket:"):
        return "socket"
    else:
        return "regular"


def _get_disk_info_for_files(paths: list[str]) -> list[dict]:
    """Get disk partition info for file paths."""
    partitions = psutil.disk_partitions(all=False)
    result: dict[str, dict] = {}

    for path in paths:
        for part in sorted(partitions, key=lambda p: len(p.mountpoint), reverse=True):
            if path.startswith(part.mountpoint):
                if part.mountpoint not in result:
                    try:
                        usage = psutil.disk_usage(part.mountpoint)
                        result[part.mountpoint] = {
                            "device": part.device,
                            "mountpoint": part.mountpoint,
                            "fstype": part.fstype,
                            "total": usage.total,
                            "used": usage.used,
                            "free": usage.free,
                            "percent": usage.percent,
                        }
                    except (PermissionError, OSError):
                        pass
                break

    return list(result.values())


def _human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}"
        n = int(n / 1024)
    return f"{n:.1f} TB"
