"""
ProcessScope — Status and Error Code Registry.

Defines a centralized set of codes used in all log output.
Console logs (journald/syslog) use the format:
    processscope[PS100]: ProcessScope service started

Code ranges:
    PS1xx — INFO     (normal operations)
    PS2xx — WARNING  (degraded but recoverable)
    PS3xx — ERROR    (failures requiring attention)
    PS4xx — CRITICAL (unrecoverable failures)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class Severity(str, Enum):
    """Log severity matching standard syslog levels."""
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True)
class PSCode:
    """A single ProcessScope status/error code."""
    code: str
    severity: Severity
    message: str

    def format(self, **kwargs: object) -> str:
        """Format the log line: processscope[PS100]: message (key=value, ...)."""
        msg = self.message
        if kwargs:
            pairs = ", ".join(f"{k}={v}" for k, v in kwargs.items())
            msg = f"{msg} ({pairs})"
        return f"processscope[{self.code}]: {msg}"

    def __str__(self) -> str:
        return self.format()


# ── INFO (PS1xx) — Normal Operations ─────────────────────────────────

PS100 = PSCode("PS100", Severity.INFO, "ProcessScope service started")
PS101 = PSCode("PS101", Severity.INFO, "ProcessScope service stopped")
PS102 = PSCode("PS102", Severity.INFO, "ProcessScope service reloading configuration")

PS110 = PSCode("PS110", Severity.INFO, "Process attached")
PS111 = PSCode("PS111", Severity.INFO, "Process detached")
PS112 = PSCode("PS112", Severity.INFO, "Process exited")

PS120 = PSCode("PS120", Severity.INFO, "Telemetry engine started")
PS121 = PSCode("PS121", Severity.INFO, "Telemetry engine stopped")

PS130 = PSCode("PS130", Severity.INFO, "Collector started")
PS131 = PSCode("PS131", Severity.INFO, "Collector stopped")

PS140 = PSCode("PS140", Severity.INFO, "WebSocket client connected")
PS141 = PSCode("PS141", Severity.INFO, "WebSocket client disconnected")

PS150 = PSCode("PS150", Severity.INFO, "API server ready")
PS151 = PSCode("PS151", Severity.INFO, "Dashboard available")

PS160 = PSCode("PS160", Severity.INFO, "Session recording started")
PS161 = PSCode("PS161", Severity.INFO, "Session recording stopped")

PS170 = PSCode("PS170", Severity.INFO, "Audit event recorded")

# ── WARNING (PS2xx) — Degraded / Recoverable ─────────────────────────

PS200 = PSCode("PS200", Severity.WARNING, "Process not found")
PS201 = PSCode("PS201", Severity.WARNING, "Access denied to process")
PS202 = PSCode("PS202", Severity.WARNING, "Collector error (recoverable)")
PS203 = PSCode("PS203", Severity.WARNING, "Syslog unavailable")
PS204 = PSCode("PS204", Severity.WARNING, "File logging unavailable")
PS205 = PSCode("PS205", Severity.WARNING, "Process already hooked")
PS206 = PSCode("PS206", Severity.WARNING, "Configuration file not found, using defaults")
PS207 = PSCode("PS207", Severity.WARNING, "Hooked process has exited")

# ── ERROR (PS3xx) — Failures ─────────────────────────────────────────

PS300 = PSCode("PS300", Severity.ERROR, "Fatal startup error")
PS301 = PSCode("PS301", Severity.ERROR, "Database connection failed")
PS302 = PSCode("PS302", Severity.ERROR, "Collector failed permanently")
PS303 = PSCode("PS303", Severity.ERROR, "Configuration invalid")
PS304 = PSCode("PS304", Severity.ERROR, "WebSocket error")
PS305 = PSCode("PS305", Severity.ERROR, "API request failed")
PS306 = PSCode("PS306", Severity.ERROR, "Event consumer error")

# ── CRITICAL (PS4xx) — Unrecoverable ─────────────────────────────────

PS400 = PSCode("PS400", Severity.CRITICAL, "Out of memory")
PS401 = PSCode("PS401", Severity.CRITICAL, "Unrecoverable engine failure")
PS402 = PSCode("PS402", Severity.CRITICAL, "Too many collector errors, collector disabled")
