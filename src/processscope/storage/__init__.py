"""ProcessScope — Data Storage."""

from processscope.storage.store import TelemetryStore
from processscope.storage.migrations import run_migrations

__all__ = ["TelemetryStore", "run_migrations"]
