"""
ProcessScope — Dual Logging Implementation.

Two parallel logging channels:

1. **System Logging (journald/syslog)**
   - Writes to stdout/stderr → captured by systemd → journald
   - Also writes to syslog via SysLogHandler → appears in /var/log/messages
   - Contains: service lifecycle, critical errors, security events
   - Facility: LOG_DAEMON, identifier: "processscope"
   - Format: processscope[PS100]: message (key=value, ...)

2. **Application File Logging**
   - Writes structured JSON to /var/log/processscope/*.log
   - processscope.log — main application log
   - telemetry.log — telemetry pipeline events
   - audit.log — security audit trail (managed by AuditLogger)
   - Managed by logrotate for rotation
"""

from __future__ import annotations

import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from processscope.config import LoggingConfig


# ── Custom JSON Formatter ─────────────────────────────────────────────

class StructuredJSONFormatter(logging.Formatter):
    """
    Formats log records as single-line JSON objects for machine parsing.

    Output format:
    {"timestamp":"...","level":"INFO","logger":"main","message":"...","extra":{}}
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "pid": record.process,
            "thread": record.threadName,
        }

        # Include PS code if present
        if hasattr(record, "_ps_code"):
            log_entry["code"] = record._ps_code  # type: ignore[attr-defined]

        # Add any extra structured fields
        if hasattr(record, "_extra"):
            log_entry["extra"] = record._extra  # type: ignore[attr-defined]

        # Add exception info if present
        if record.exc_info and record.exc_info[1]:
            log_entry["exception"] = {
                "type": type(record.exc_info[1]).__name__,
                "message": str(record.exc_info[1]),
                "traceback": self.formatException(record.exc_info),
            }

        return json.dumps(log_entry, default=str)


class PSCodeConsoleFormatter(logging.Formatter):
    """
    Plain-text console formatter for production mode (journald/syslog).

    Produces clean, parseable output:
        processscope[PS100]: ProcessScope service started (version=0.1.0)
        processscope: Telemetry event collected

    When no PS code is attached, uses the standard format:
        processscope: <message> (key=value, ...)
    """

    def format(self, record: logging.LogRecord) -> str:
        msg = record.getMessage()

        # Append extra fields if present
        if hasattr(record, "_extra") and record._extra:  # type: ignore[attr-defined]
            pairs = ", ".join(f"{k}={v}" for k, v in record._extra.items())  # type: ignore[attr-defined]
            msg = f"{msg} ({pairs})"

        # Use PS code if present
        if hasattr(record, "_ps_code") and record._ps_code:  # type: ignore[attr-defined]
            output = f"processscope[{record._ps_code}]: {msg}"  # type: ignore[attr-defined]
        else:
            output = f"processscope: {msg}"

        if record.exc_info and record.exc_info[1]:
            output += f"\n{self.formatException(record.exc_info)}"

        return output


class ConsoleFormatter(logging.Formatter):
    """
    Pretty console formatter with colors for development mode.
    """

    COLORS = {
        "DEBUG": "\033[36m",     # Cyan
        "INFO": "\033[32m",      # Green
        "WARNING": "\033[33m",   # Yellow
        "ERROR": "\033[31m",     # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"
    DIM = "\033[2m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelname, "")
        ts = datetime.fromtimestamp(record.created).strftime("%H:%M:%S.%f")[:-3]
        level = f"{color}{record.levelname:<8}{self.RESET}"

        msg = f"{self.DIM}{ts}{self.RESET} {level} [{record.name}] {record.getMessage()}"

        # Append extra fields if present
        if hasattr(record, "_extra") and record._extra:  # type: ignore[attr-defined]
            extras = " ".join(f"{k}={v}" for k, v in record._extra.items())  # type: ignore[attr-defined]
            msg += f" {self.DIM}| {extras}{self.RESET}"

        # Show PS code in dev mode too
        if hasattr(record, "_ps_code") and record._ps_code:  # type: ignore[attr-defined]
            msg += f" {self.DIM}[{record._ps_code}]{self.RESET}"  # type: ignore[attr-defined]

        if record.exc_info and record.exc_info[1]:
            msg += f"\n{self.formatException(record.exc_info)}"

        return msg


# ── Structured Logger Adapter ─────────────────────────────────────────

class StructuredLogger:
    """
    Logger wrapper that supports structured key-value logging.

    Usage:
        logger = get_logger("collector.cpu")
        logger.info("CPU sample collected", pid=1234, usage=45.2)

    With PS codes:
        from processscope.logging.error_codes import PS100
        logger.info(PS100, version="0.1.0")
    """

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger

    def _log(self, level: int, msg: object, exc_info: bool = False, **kwargs: Any) -> None:
        if self._logger.isEnabledFor(level):
            # Support PSCode objects
            ps_code = None
            from processscope.logging.error_codes import PSCode
            if isinstance(msg, PSCode):
                ps_code = msg.code
                msg_str = msg.message
            else:
                msg_str = str(msg)

            record = self._logger.makeRecord(
                self._logger.name, level, "processscope", 0, msg_str, (), None
            )
            record._extra = kwargs  # type: ignore[attr-defined]
            record._ps_code = ps_code  # type: ignore[attr-defined]
            if exc_info:
                record.exc_info = sys.exc_info()
            self._logger.handle(record)

    def debug(self, msg: object, **kwargs: Any) -> None:
        self._log(logging.DEBUG, msg, **kwargs)

    def info(self, msg: object, **kwargs: Any) -> None:
        self._log(logging.INFO, msg, **kwargs)

    def warning(self, msg: object, **kwargs: Any) -> None:
        self._log(logging.WARNING, msg, **kwargs)

    def error(self, msg: object, exc_info: bool = False, **kwargs: Any) -> None:
        self._log(logging.ERROR, msg, exc_info=exc_info, **kwargs)

    def critical(self, msg: object, exc_info: bool = False, **kwargs: Any) -> None:
        self._log(logging.CRITICAL, msg, exc_info=exc_info, **kwargs)


# ── Module-Level State ────────────────────────────────────────────────

_initialized = False
_loggers: dict[str, StructuredLogger] = {}


# ── Public API ────────────────────────────────────────────────────────

def setup_logging(config: LoggingConfig, dev_mode: bool = False) -> None:
    """
    Initialize the dual logging system.

    This sets up:
    1. Console handler (stdout) → captured by systemd → journald
       - Production: PSCodeConsoleFormatter (plain text with PS codes)
       - Development: ConsoleFormatter (colored, human-friendly)
    2. Syslog handler → /var/log/messages via rsyslog
    3. File handler → /var/log/processscope/processscope.log (JSON)
    4. Telemetry file handler → /var/log/processscope/telemetry.log (JSON)
    """
    global _initialized

    if _initialized:
        return

    root_logger = logging.getLogger("processscope")
    root_logger.setLevel(getattr(logging, config.level.upper(), logging.INFO))
    root_logger.handlers.clear()

    # ── 1. Console Handler (stdout → journald via systemd) ────────
    console_handler = logging.StreamHandler(sys.stdout)
    if dev_mode:
        console_handler.setFormatter(ConsoleFormatter())
    else:
        console_handler.setFormatter(PSCodeConsoleFormatter())
    console_handler.setLevel(logging.DEBUG if dev_mode else logging.WARNING)
    root_logger.addHandler(console_handler)

    # ── 2. Syslog Handler (→ /var/log/messages) ──────────────────
    if config.syslog_enabled and sys.platform == "linux":
        try:
            syslog_handler = logging.handlers.SysLogHandler(
                address="/dev/log",
                facility=logging.handlers.SysLogHandler.facility_names.get(
                    config.syslog_facility, logging.handlers.SysLogHandler.LOG_DAEMON
                ),
            )
            syslog_formatter = logging.Formatter(
                f"{config.syslog_identifier}[%(process)d]: %(levelname)s %(name)s — %(message)s"
            )
            syslog_handler.setFormatter(syslog_formatter)
            syslog_handler.setLevel(logging.INFO)
            root_logger.addHandler(syslog_handler)
        except (OSError, ConnectionError):
            # Syslog not available (e.g., container without /dev/log)
            pass

    # ── 3. Application File Handler ──────────────────────────────
    log_dir = Path(config.file_path)
    try:
        log_dir.mkdir(parents=True, exist_ok=True)

        # Main application log
        main_log = log_dir / "processscope.log"
        file_handler = logging.handlers.RotatingFileHandler(
            main_log,
            maxBytes=config.max_file_size_mb * 1024 * 1024,
            backupCount=config.backup_count,
            encoding="utf-8",
        )
        file_handler.setFormatter(StructuredJSONFormatter())
        file_handler.setLevel(logging.DEBUG)
        root_logger.addHandler(file_handler)

        # Telemetry log (separate file for collector events)
        telemetry_log = log_dir / "telemetry.log"
        telemetry_logger = logging.getLogger("processscope.telemetry")
        telemetry_handler = logging.handlers.RotatingFileHandler(
            telemetry_log,
            maxBytes=config.max_file_size_mb * 1024 * 1024,
            backupCount=config.backup_count,
            encoding="utf-8",
        )
        telemetry_handler.setFormatter(StructuredJSONFormatter())
        telemetry_handler.setLevel(logging.DEBUG)
        telemetry_logger.addHandler(telemetry_handler)

    except PermissionError:
        # Running without root — skip file logging
        console_handler.setFormatter(ConsoleFormatter())
        root_logger.warning(
            f"Cannot write to {log_dir} — file logging disabled. Run as root or use --dev."
        )

    _initialized = True


def get_logger(name: str) -> StructuredLogger:
    """
    Get a named structured logger.

    Args:
        name: Logger name (e.g., "collector.cpu", "api.server", "engine")

    Returns:
        StructuredLogger instance with structured key-value logging support.
    """
    full_name = f"processscope.{name}" if not name.startswith("processscope.") else name

    if full_name not in _loggers:
        _loggers[full_name] = StructuredLogger(logging.getLogger(full_name))

    return _loggers[full_name]
