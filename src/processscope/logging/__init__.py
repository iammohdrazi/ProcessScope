"""
ProcessScope — Dual Logging System.

Provides:
  - setup_logging(): Initialize the dual logging pipeline
  - get_logger(): Get a named logger instance
"""

from processscope.logging.logger import setup_logging, get_logger
from processscope.logging.audit import AuditLogger, get_audit_logger

__all__ = ["setup_logging", "get_logger", "AuditLogger", "get_audit_logger"]
