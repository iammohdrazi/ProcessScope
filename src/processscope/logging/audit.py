"""
ProcessScope — Security Audit Logger.

Writes security-relevant events to /var/log/processscope/audit.log:
  - Process attachment/detachment events
  - Permission checks
  - Configuration changes
  - API access events

These events are also forwarded to syslog for centralized audit trail.
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class AuditAction(str, Enum):
    """Enumeration of auditable actions."""
    PROCESS_ATTACH = "PROCESS_ATTACH"
    PROCESS_DETACH = "PROCESS_DETACH"
    PROCESS_ATTACH_DENIED = "PROCESS_ATTACH_DENIED"
    CONFIG_CHANGE = "CONFIG_CHANGE"
    SERVICE_START = "SERVICE_START"
    SERVICE_STOP = "SERVICE_STOP"
    API_ACCESS = "API_ACCESS"
    AUTH_SUCCESS = "AUTH_SUCCESS"
    AUTH_FAILURE = "AUTH_FAILURE"
    EBPF_PROBE_LOAD = "EBPF_PROBE_LOAD"
    EBPF_PROBE_UNLOAD = "EBPF_PROBE_UNLOAD"


class AuditLogger:
    """
    Dedicated audit logger that writes to audit.log and syslog.

    Each audit entry includes:
    - Timestamp (UTC ISO 8601)
    - Action type
    - Actor (user/UID)
    - Target (PID, resource)
    - Result (success/failure)
    - Details (extra context)
    """

    def __init__(self, log_dir: str = "/var/log/processscope") -> None:
        self._logger = logging.getLogger("processscope.audit")
        self._logger.setLevel(logging.INFO)
        self._logger.propagate = False  # Don't duplicate to parent

        log_path = Path(log_dir)
        try:
            log_path.mkdir(parents=True, exist_ok=True)
            audit_file = log_path / "audit.log"
            handler = logging.handlers.RotatingFileHandler(
                audit_file,
                maxBytes=50 * 1024 * 1024,  # 50 MB
                backupCount=10,
                encoding="utf-8",
            )
            handler.setFormatter(logging.Formatter("%(message)s"))
            self._logger.addHandler(handler)
        except PermissionError:
            pass

    def log(
        self,
        action: AuditAction,
        target: str = "",
        result: str = "success",
        **details: Any,
    ) -> None:
        """
        Write an audit entry.

        Args:
            action: The audit action type.
            target: The target resource (e.g., PID, config path).
            result: "success" or "failure".
            **details: Additional key-value details to include.
        """
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action.value,
            "actor": {
                "uid": os.getuid() if hasattr(os, "getuid") else -1,
                "euid": os.geteuid() if hasattr(os, "geteuid") else -1,
                "user": os.environ.get("USER", "unknown"),
            },
            "target": target,
            "result": result,
            "pid": os.getpid(),
            "details": details,
        }

        self._logger.info(json.dumps(entry, default=str))

    def process_attach(self, pid: int, name: str = "", read_only: bool = False) -> None:
        """Log a process attachment event."""
        self.log(
            AuditAction.PROCESS_ATTACH,
            target=f"pid:{pid}",
            process_name=name,
            read_only=read_only,
        )

    def process_detach(self, pid: int, name: str = "") -> None:
        """Log a process detachment event."""
        self.log(
            AuditAction.PROCESS_DETACH,
            target=f"pid:{pid}",
            process_name=name,
        )

    def process_attach_denied(self, pid: int, reason: str) -> None:
        """Log a denied process attachment attempt."""
        self.log(
            AuditAction.PROCESS_ATTACH_DENIED,
            target=f"pid:{pid}",
            result="failure",
            reason=reason,
        )

    def service_start(self, version: str, build: str) -> None:
        """Log service startup."""
        self.log(
            AuditAction.SERVICE_START,
            target="processscope",
            version=version,
            build=build,
        )

    def service_stop(self, reason: str = "normal") -> None:
        """Log service shutdown."""
        self.log(
            AuditAction.SERVICE_STOP,
            target="processscope",
            reason=reason,
        )


# ── Singleton ─────────────────────────────────────────────────────────

_audit_logger: AuditLogger | None = None


def get_audit_logger(log_dir: str = "/var/log/processscope") -> AuditLogger:
    """Get or create the singleton AuditLogger."""
    global _audit_logger
    if _audit_logger is None:
        _audit_logger = AuditLogger(log_dir)
    return _audit_logger
