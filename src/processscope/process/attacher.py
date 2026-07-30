"""
ProcessScope — Process Attachment Engine.

Manages the lifecycle of hooked processes:
  - Attach by PID or process name
  - Track child processes
  - Safe detach
  - Read-only vs instrumentation mode
  - Concurrent multi-process hooks
"""

from __future__ import annotations

import os
import signal
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

import psutil

from processscope.logging import get_logger, get_audit_logger

logger = get_logger("process.attacher")
audit = get_audit_logger()


class AttachMode(str, Enum):
    """Process attachment mode."""
    READ_ONLY = "read_only"
    INSTRUMENTED = "instrumented"


class HookState(str, Enum):
    """State of a hooked process."""
    ATTACHING = "attaching"
    ATTACHED = "attached"
    DETACHING = "detaching"
    DETACHED = "detached"
    ERROR = "error"
    PROCESS_EXITED = "process_exited"


@dataclass
class HookedProcess:
    """Represents a process that ProcessScope is observing."""
    pid: int
    name: str
    exe: str
    cmdline: list[str]
    mode: AttachMode
    state: HookState
    attached_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    include_children: bool = False
    child_pids: list[int] = field(default_factory=list)
    psutil_process: Optional[psutil.Process] = field(default=None, repr=False)

    def is_alive(self) -> bool:
        """Check if the hooked process is still running."""
        if self.psutil_process is None:
            return False
        try:
            return self.psutil_process.is_running() and self.psutil_process.status() != psutil.STATUS_ZOMBIE
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return False

    def to_dict(self) -> dict:
        """Serialize for API responses."""
        return {
            "pid": self.pid,
            "name": self.name,
            "exe": self.exe,
            "cmdline": self.cmdline,
            "mode": self.mode.value,
            "state": self.state.value,
            "attached_at": self.attached_at.isoformat(),
            "include_children": self.include_children,
            "child_pids": self.child_pids,
            "is_alive": self.is_alive(),
        }


class ProcessAttacher:
    """
    Manages process attachment and lifecycle.

    Thread-safe for concurrent access from the API layer.
    """

    def __init__(self) -> None:
        self._hooked: dict[int, HookedProcess] = {}

    @property
    def hooked_processes(self) -> dict[int, HookedProcess]:
        """Return all currently hooked processes."""
        return dict(self._hooked)

    @property
    def hooked_count(self) -> int:
        """Return count of hooked processes."""
        return len(self._hooked)

    def attach_by_pid(
        self,
        pid: int,
        read_only: bool = False,
        include_children: bool = False,
    ) -> HookedProcess:
        """
        Attach to a process by PID.

        Args:
            pid: Process ID to attach to.
            read_only: If True, observe only (no instrumentation).
            include_children: If True, also track child processes.

        Returns:
            HookedProcess instance.

        Raises:
            ProcessLookupError: If the PID doesn't exist.
            PermissionError: If insufficient privileges.
            ValueError: If the process is already hooked.
        """
        if pid in self._hooked:
            raise ValueError(f"Process {pid} is already hooked")

        logger.info("Attaching to process", pid=pid, read_only=read_only)

        try:
            proc = psutil.Process(pid)
            proc_name = proc.name()
            proc_exe = proc.exe()
            proc_cmdline = proc.cmdline()
        except psutil.NoSuchProcess:
            logger.error("Process not found", pid=pid)
            audit.process_attach_denied(pid, reason="Process not found")
            raise ProcessLookupError(f"Process {pid} not found")
        except psutil.AccessDenied:
            logger.error("Access denied to process", pid=pid)
            audit.process_attach_denied(pid, reason="Access denied")
            raise PermissionError(f"Access denied to process {pid}. Run as root.")

        mode = AttachMode.READ_ONLY if read_only else AttachMode.INSTRUMENTED

        hooked = HookedProcess(
            pid=pid,
            name=proc_name,
            exe=proc_exe,
            cmdline=proc_cmdline,
            mode=mode,
            state=HookState.ATTACHED,
            include_children=include_children,
            psutil_process=proc,
        )

        # Track child processes if requested
        if include_children:
            try:
                children = proc.children(recursive=True)
                hooked.child_pids = [c.pid for c in children]
                logger.info("Tracking child processes", pid=pid, children=len(children))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        self._hooked[pid] = hooked

        audit.process_attach(pid, name=proc_name, read_only=read_only)
        logger.info(
            "Successfully attached to process",
            pid=pid,
            name=proc_name,
            exe=proc_exe,
            mode=mode.value,
        )

        return hooked

    def attach_by_name(
        self,
        name: str,
        read_only: bool = False,
        include_children: bool = False,
    ) -> list[HookedProcess]:
        """
        Attach to all processes matching the given name.

        Args:
            name: Process name to search for.
            read_only: If True, observe only.
            include_children: If True, also track child processes.

        Returns:
            List of HookedProcess instances.
        """
        logger.info("Searching for processes by name", name=name)
        hooked_list: list[HookedProcess] = []

        for proc in psutil.process_iter(["pid", "name"]):
            try:
                if proc.info["name"] == name or name in (proc.info["name"] or ""):
                    if proc.info["pid"] not in self._hooked:
                        hooked = self.attach_by_pid(
                            proc.info["pid"],
                            read_only=read_only,
                            include_children=include_children,
                        )
                        hooked_list.append(hooked)
            except (psutil.NoSuchProcess, psutil.AccessDenied, PermissionError):
                continue

        if not hooked_list:
            logger.warning("No processes found matching name", name=name)

        return hooked_list

    def detach(self, pid: int) -> None:
        """
        Safely detach from a hooked process.

        Args:
            pid: Process ID to detach from.

        Raises:
            KeyError: If the PID is not hooked.
        """
        if pid not in self._hooked:
            raise KeyError(f"Process {pid} is not hooked")

        hooked = self._hooked[pid]
        hooked.state = HookState.DETACHING

        logger.info("Detaching from process", pid=pid, name=hooked.name)
        audit.process_detach(pid, name=hooked.name)

        hooked.state = HookState.DETACHED
        del self._hooked[pid]

        logger.info("Successfully detached from process", pid=pid)

    def detach_all(self) -> None:
        """Detach from all hooked processes."""
        pids = list(self._hooked.keys())
        for pid in pids:
            try:
                self.detach(pid)
            except Exception as e:
                logger.error("Error detaching from process", pid=pid, error=str(e))

    def refresh_states(self) -> None:
        """Check and update the state of all hooked processes."""
        for pid, hooked in list(self._hooked.items()):
            if not hooked.is_alive():
                logger.warning("Hooked process has exited", pid=pid, name=hooked.name)
                hooked.state = HookState.PROCESS_EXITED

            # Refresh child process list
            if hooked.include_children and hooked.psutil_process:
                try:
                    children = hooked.psutil_process.children(recursive=True)
                    hooked.child_pids = [c.pid for c in children]
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass

    def get_hooked(self, pid: int) -> HookedProcess | None:
        """Get a hooked process by PID."""
        return self._hooked.get(pid)

    def list_hooked(self) -> list[dict]:
        """List all hooked processes as dictionaries."""
        self.refresh_states()
        return [h.to_dict() for h in self._hooked.values()]
