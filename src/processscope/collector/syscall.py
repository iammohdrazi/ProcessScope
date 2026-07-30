"""
ProcessScope — System Call Collector.

Monitors system calls made by the hooked process by reading /proc/[pid]/syscall
and tracking syscall statistics from /proc/[pid]/status.

Note: Full syscall tracing (with arguments) requires eBPF or strace integration,
which is available in Phase 2. This collector provides syscall summary data.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import psutil

from processscope.collector.base import (
    BaseCollector, CollectorRegistry, EventCategory, TelemetryEvent,
)


# Standard Linux syscall number → name mapping (x86_64, subset)
SYSCALL_NAMES: dict[int, str] = {
    0: "read", 1: "write", 2: "open", 3: "close", 4: "stat", 5: "fstat",
    6: "lstat", 7: "poll", 8: "lseek", 9: "mmap", 10: "mprotect",
    11: "munmap", 12: "brk", 13: "rt_sigaction", 14: "rt_sigprocmask",
    17: "pread64", 18: "pwrite64", 19: "readv", 20: "writev",
    21: "access", 22: "pipe", 23: "select", 32: "dup", 33: "dup2",
    35: "nanosleep", 39: "getpid", 41: "socket", 42: "connect",
    43: "accept", 44: "sendto", 45: "recvfrom", 46: "sendmsg",
    47: "recvmsg", 49: "bind", 50: "listen", 56: "clone",
    57: "fork", 58: "vfork", 59: "execve", 60: "exit",
    62: "kill", 72: "fcntl", 78: "getdents", 79: "getcwd",
    80: "chdir", 82: "rename", 83: "mkdir", 84: "rmdir",
    85: "creat", 87: "unlink", 89: "readlink", 90: "chmod",
    92: "chown", 96: "gettimeofday", 102: "getuid", 104: "getgid",
    110: "getppid", 157: "prctl", 186: "gettid",
    202: "futex", 217: "getdents64", 228: "clock_gettime",
    231: "exit_group", 232: "epoll_wait", 233: "epoll_ctl",
    257: "openat", 262: "newfstatat", 288: "accept4",
    291: "epoll_create1", 292: "pipe2", 293: "inotify_init1",
    302: "prlimit64", 318: "getrandom", 332: "statx",
}


@CollectorRegistry.register
class SyscallCollector(BaseCollector):
    """Collects system call telemetry for a hooked process."""

    @property
    def name(self) -> str:
        return "syscall"

    @property
    def category(self) -> EventCategory:
        return EventCategory.SYSCALL

    def __init__(self, poll_interval_ms: int = 1000) -> None:
        super().__init__(poll_interval_ms)
        self._prev_voluntary_cs: int = 0
        self._prev_involuntary_cs: int = 0

    async def _collect(self) -> list[TelemetryEvent]:
        events: list[TelemetryEvent] = []

        try:
            # Current syscall from /proc/[pid]/syscall
            current_syscall = _read_current_syscall(self._pid)

            # Syscall-related stats from /proc/[pid]/status
            proc = psutil.Process(self._pid)
            ctx = proc.num_ctx_switches()

            vol_rate = ctx.voluntary - self._prev_voluntary_cs if self._prev_voluntary_cs > 0 else 0
            invol_rate = ctx.involuntary - self._prev_involuntary_cs if self._prev_involuntary_cs > 0 else 0
            self._prev_voluntary_cs = ctx.voluntary
            self._prev_involuntary_cs = ctx.involuntary

            # Collect /proc/[pid]/io for syscall-related I/O
            io_stats = _read_proc_io(self._pid)

            data: dict[str, Any] = {
                "current_syscall": current_syscall,
                "context_switches": {
                    "voluntary": ctx.voluntary,
                    "involuntary": ctx.involuntary,
                    "voluntary_rate": vol_rate,
                    "involuntary_rate": invol_rate,
                },
            }

            if io_stats:
                data["io"] = io_stats

            # Read /proc/[pid]/wchan (what the process is waiting on)
            wchan = _read_wchan(self._pid)
            if wchan:
                data["wchan"] = wchan

            events.append(self.emit_event(
                title="Syscall Sample",
                data=data,
            ))

        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            self._logger.warning("Syscall collection failed", pid=self._pid, error=str(e))

        return events


def _read_current_syscall(pid: int) -> dict | None:
    """Read the current syscall from /proc/[pid]/syscall."""
    try:
        path = Path(f"/proc/{pid}/syscall")
        if not path.exists():
            return None

        content = path.read_text().strip()
        if content == "running":
            return {"state": "running", "syscall_nr": -1, "syscall_name": "running"}

        parts = content.split()
        if parts:
            syscall_nr = int(parts[0])
            syscall_name = SYSCALL_NAMES.get(syscall_nr, f"syscall_{syscall_nr}")
            result: dict[str, Any] = {
                "state": "in_syscall",
                "syscall_nr": syscall_nr,
                "syscall_name": syscall_name,
            }
            # Parse arguments (up to 6)
            if len(parts) > 1:
                result["args"] = parts[1:7]
            # Stack pointer and instruction pointer
            if len(parts) > 7:
                result["stack_pointer"] = parts[-2]
                result["instruction_pointer"] = parts[-1]
            return result

    except (PermissionError, OSError, ValueError):
        pass
    return None


def _read_proc_io(pid: int) -> dict | None:
    """Read I/O stats from /proc/[pid]/io."""
    try:
        path = Path(f"/proc/{pid}/io")
        if not path.exists():
            return None

        result = {}
        with open(path) as f:
            for line in f:
                if ":" in line:
                    key, val = line.split(":", 1)
                    result[key.strip()] = int(val.strip())
        return result

    except (PermissionError, OSError, ValueError):
        return None


def _read_wchan(pid: int) -> str | None:
    """Read the wait channel from /proc/[pid]/wchan."""
    try:
        path = Path(f"/proc/{pid}/wchan")
        if path.exists():
            content = path.read_text().strip()
            if content and content != "0":
                return content
    except (PermissionError, OSError):
        pass
    return None
