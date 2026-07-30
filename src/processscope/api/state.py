"""
ProcessScope — Global API State.

Provides the global application state object, decoupled from the server and routes
to prevent circular dependencies.
"""

from __future__ import annotations

from processscope.config import AppConfig
from processscope.engine import TelemetryEngine
from processscope.process.attacher import ProcessAttacher
from processscope.storage import TelemetryStore
from processscope.version import get_build_info


class AppState:
    """Global application state shared between API handlers."""
    config: AppConfig
    attacher: ProcessAttacher
    engine: TelemetryEngine
    store: TelemetryStore
    build_info = get_build_info()


app_state = AppState()
