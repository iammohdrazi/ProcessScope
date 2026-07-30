"""
ProcessScope — Process Metadata Collector.

Collects comprehensive metadata from /proc/[pid]/* and psutil for any running process:
  - PID, PPID, name, executable, command line
  - User, group, capabilities, cgroups
  - Environment variables, scheduling, affinity
  - Process tree, uptime, status, resource limits
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import psutil

from processscope.logging import get_logger

logger = get_logger("process.metadata")


@dataclass
class ProcessMetadata:
    """Complete metadata snapshot for a process."""

    # Identity
    pid: int = 0
    ppid: int = 0
    name: str = ""
    exe: str = ""
    cmdline: list[str] = field(default_factory=list)
    cwd: str = ""
    root: str = "/"

    # User/Group
    username: str = ""
    uid: int = -1
    gid: int = -1
    groups: list[int] = field(default_factory=list)

    # Status
    status: str = ""
    create_time: float = 0.0
    uptime_seconds: float = 0.0

    # Scheduling
    nice: int = 0
    priority: int = 0
    cpu_affinity: list[int] = field(default_factory=list)
    num_threads: int = 0
    scheduling_policy: str = ""

    # Memory summary
    memory_rss: int = 0
    memory_vms: int = 0
    memory_shared: int = 0
    memory_percent: float = 0.0

    # CPU summary
    cpu_percent: float = 0.0
    cpu_user_time: float = 0.0
    cpu_system_time: float = 0.0
    cpu_num: int = 0

    # I/O
    io_read_bytes: int = 0
    io_write_bytes: int = 0
    io_read_count: int = 0
    io_write_count: int = 0

    # File descriptors
    num_fds: int = 0
    open_files: list[str] = field(default_factory=list)

    # Network
    num_connections: int = 0

    # Context
    num_ctx_switches_voluntary: int = 0
    num_ctx_switches_involuntary: int = 0

    # Environment
    environ: dict[str, str] = field(default_factory=dict)

    # Process hierarchy
    parent_name: str = ""
    children_pids: list[int] = field(default_factory=list)
    children_names: list[str] = field(default_factory=list)

    # Linux-specific
    cgroups: list[dict[str, str]] = field(default_factory=list)
    oom_score: int = 0
    oom_score_adj: int = 0

    # Resource limits
    rlimits: dict[str, dict[str, int]] = field(default_factory=dict)

    # Terminal
    terminal: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary for API responses."""
        return {
            "identity": {
                "pid": self.pid,
                "ppid": self.ppid,
                "name": self.name,
                "exe": self.exe,
                "cmdline": self.cmdline,
                "cwd": self.cwd,
                "root": self.root,
            },
            "user": {
                "username": self.username,
                "uid": self.uid,
                "gid": self.gid,
                "groups": self.groups,
            },
            "status": {
                "state": self.status,
                "create_time": self.create_time,
                "uptime_seconds": round(self.uptime_seconds, 2),
                "uptime_human": _format_uptime(self.uptime_seconds),
                "terminal": self.terminal,
            },
            "scheduling": {
                "nice": self.nice,
                "priority": self.priority,
                "cpu_affinity": self.cpu_affinity,
                "num_threads": self.num_threads,
                "policy": self.scheduling_policy,
            },
            "memory": {
                "rss": self.memory_rss,
                "rss_human": _human_bytes(self.memory_rss),
                "vms": self.memory_vms,
                "vms_human": _human_bytes(self.memory_vms),
                "shared": self.memory_shared,
                "shared_human": _human_bytes(self.memory_shared),
                "percent": round(self.memory_percent, 2),
            },
            "cpu": {
                "percent": round(self.cpu_percent, 2),
                "user_time": round(self.cpu_user_time, 3),
                "system_time": round(self.cpu_system_time, 3),
                "current_cpu": self.cpu_num,
            },
            "io": {
                "read_bytes": self.io_read_bytes,
                "read_bytes_human": _human_bytes(self.io_read_bytes),
                "write_bytes": self.io_write_bytes,
                "write_bytes_human": _human_bytes(self.io_write_bytes),
                "read_count": self.io_read_count,
                "write_count": self.io_write_count,
            },
            "files": {
                "num_fds": self.num_fds,
                "open_files": self.open_files[:50],  # Cap for API response size
            },
            "network": {
                "num_connections": self.num_connections,
            },
            "context_switches": {
                "voluntary": self.num_ctx_switches_voluntary,
                "involuntary": self.num_ctx_switches_involuntary,
            },
            "environ": self.environ,
            "hierarchy": {
                "parent_name": self.parent_name,
                "children_pids": self.children_pids,
                "children_names": self.children_names,
            },
            "linux": {
                "cgroups": self.cgroups,
                "oom_score": self.oom_score,
                "oom_score_adj": self.oom_score_adj,
            },
            "resource_limits": self.rlimits,
        }


def collect_metadata(pid: int) -> ProcessMetadata:
    """
    Collect comprehensive metadata for a process.

    Args:
        pid: Process ID to inspect.

    Returns:
        ProcessMetadata with all available fields populated.

    Raises:
        psutil.NoSuchProcess: If the PID doesn't exist.
        psutil.AccessDenied: If insufficient privileges.
    """
    logger.debug("Collecting metadata", pid=pid)

    proc = psutil.Process(pid)
    meta = ProcessMetadata(pid=pid)

    # ── Identity ──────────────────────────────────────────────
    try:
        meta.ppid = proc.ppid()
        meta.name = proc.name()
        meta.exe = proc.exe()
        meta.cmdline = proc.cmdline()
        meta.cwd = proc.cwd()
    except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
        pass

    # ── User/Group ────────────────────────────────────────────
    try:
        uids = proc.uids()
        gids = proc.gids()
        meta.uid = uids.real
        meta.gid = gids.real
        meta.username = proc.username()
    except (psutil.AccessDenied, KeyError):
        pass

    # ── Status & Timing ──────────────────────────────────────
    try:
        meta.status = proc.status()
        meta.create_time = proc.create_time()
        meta.uptime_seconds = datetime.now().timestamp() - meta.create_time
        meta.terminal = proc.terminal() or ""
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        pass

    # ── Scheduling ────────────────────────────────────────────
    try:
        meta.nice = proc.nice()
        meta.cpu_affinity = proc.cpu_affinity() if hasattr(proc, "cpu_affinity") else []
        meta.num_threads = proc.num_threads()
    except (psutil.AccessDenied, psutil.NoSuchProcess, AttributeError):
        pass

    # ── Memory ────────────────────────────────────────────────
    try:
        mem = proc.memory_info()
        meta.memory_rss = mem.rss
        meta.memory_vms = mem.vms
        if hasattr(mem, "shared"):
            meta.memory_shared = mem.shared
        meta.memory_percent = proc.memory_percent()
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        pass

    # ── CPU ───────────────────────────────────────────────────
    try:
        meta.cpu_percent = proc.cpu_percent(interval=0.1)
        times = proc.cpu_times()
        meta.cpu_user_time = times.user
        meta.cpu_system_time = times.system
        meta.cpu_num = proc.cpu_num()
    except (psutil.AccessDenied, psutil.NoSuchProcess, AttributeError):
        pass

    # ── I/O ───────────────────────────────────────────────────
    try:
        io = proc.io_counters()
        meta.io_read_bytes = io.read_bytes
        meta.io_write_bytes = io.write_bytes
        meta.io_read_count = io.read_count
        meta.io_write_count = io.write_count
    except (psutil.AccessDenied, psutil.NoSuchProcess, AttributeError):
        pass

    # ── File Descriptors ──────────────────────────────────────
    try:
        meta.num_fds = proc.num_fds()
        meta.open_files = [f.path for f in proc.open_files()]
    except (psutil.AccessDenied, psutil.NoSuchProcess, AttributeError):
        pass

    # ── Network ───────────────────────────────────────────────
    try:
        conns = proc.connections()
        meta.num_connections = len(conns)
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        pass

    # ── Context Switches ──────────────────────────────────────
    try:
        ctx = proc.num_ctx_switches()
        meta.num_ctx_switches_voluntary = ctx.voluntary
        meta.num_ctx_switches_involuntary = ctx.involuntary
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        pass

    # ── Environment Variables ─────────────────────────────────
    try:
        meta.environ = proc.environ()
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        pass

    # ── Process Hierarchy ─────────────────────────────────────
    try:
        parent = proc.parent()
        if parent:
            meta.parent_name = parent.name()
        children = proc.children(recursive=False)
        meta.children_pids = [c.pid for c in children]
        meta.children_names = [c.name() for c in children]
    except (psutil.AccessDenied, psutil.NoSuchProcess):
        pass

    # ── Linux: cgroups ────────────────────────────────────────
    _collect_cgroups(pid, meta)

    # ── Linux: OOM score ──────────────────────────────────────
    _collect_oom_score(pid, meta)

    # ── Resource Limits ───────────────────────────────────────
    try:
        for limit_name in [
            psutil.RLIMIT_NOFILE, psutil.RLIMIT_AS, psutil.RLIMIT_NPROC,
            psutil.RLIMIT_STACK, psutil.RLIMIT_CORE, psutil.RLIMIT_CPU,
        ]:
            try:
                soft, hard = proc.rlimit(limit_name)
                meta.rlimits[str(limit_name)] = {"soft": soft, "hard": hard}
            except (psutil.AccessDenied, OSError):
                pass
    except AttributeError:
        # rlimit not available on this platform
        pass

    logger.debug("Metadata collection complete", pid=pid, name=meta.name)
    return meta


def _collect_cgroups(pid: int, meta: ProcessMetadata) -> None:
    """Read cgroup information from /proc/[pid]/cgroup."""
    cgroup_path = Path(f"/proc/{pid}/cgroup")
    try:
        if cgroup_path.exists():
            with open(cgroup_path) as f:
                for line in f:
                    parts = line.strip().split(":")
                    if len(parts) == 3:
                        meta.cgroups.append({
                            "hierarchy_id": parts[0],
                            "controllers": parts[1],
                            "path": parts[2],
                        })
    except (PermissionError, OSError):
        pass


def _collect_oom_score(pid: int, meta: ProcessMetadata) -> None:
    """Read OOM score from /proc/[pid]/oom_score."""
    try:
        oom_path = Path(f"/proc/{pid}/oom_score")
        if oom_path.exists():
            meta.oom_score = int(oom_path.read_text().strip())

        oom_adj_path = Path(f"/proc/{pid}/oom_score_adj")
        if oom_adj_path.exists():
            meta.oom_score_adj = int(oom_adj_path.read_text().strip())
    except (PermissionError, OSError, ValueError):
        pass


def _format_uptime(seconds: float) -> str:
    """Format seconds into a human-readable uptime string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        return f"{seconds / 60:.0f}m {seconds % 60:.0f}s"
    elif seconds < 86400:
        hours = int(seconds // 3600)
        mins = int((seconds % 3600) // 60)
        return f"{hours}h {mins}m"
    else:
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        return f"{days}d {hours}h"


def _human_bytes(n: int) -> str:
    """Format bytes into a human-readable string."""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}"
        n = int(n / 1024)
    return f"{n:.1f} PB"
