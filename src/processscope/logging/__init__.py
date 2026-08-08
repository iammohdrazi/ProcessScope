"""
ProcessScope — Dual Logging System.

Provides:
  - setup_logging(): Initialize the dual logging pipeline
  - get_logger(): Get a named logger instance
  - enable_debug_logging(): Dynamically enable verbose /tmp debug log
  - PS codes: Structured error/status codes for consistent logging
"""

from processscope.logging.logger import setup_logging, get_logger, enable_debug_logging
from processscope.logging.audit import AuditLogger, get_audit_logger

__all__ = ["setup_logging", "get_logger", "enable_debug_logging", "AuditLogger", "get_audit_logger"]
