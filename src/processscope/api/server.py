"""
ProcessScope — FastAPI Application Server.

Creates and configures the FastAPI application with:
  - REST API at /api/v1/*
  - WebSocket at /ws/*
  - Embedded dashboard static files at /
  - CORS, lifecycle events, graceful shutdown
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from processscope.api.routes import router as api_router
from processscope.api.websocket_handler import router as ws_router
from processscope.config import AppConfig
from processscope.engine import TelemetryEngine
from processscope.logging import get_logger, get_audit_logger
from processscope.process.attacher import ProcessAttacher
from processscope.storage import TelemetryStore
from processscope.version import get_build_info

logger = get_logger("api.server")


from processscope.api.state import app_state

# ── Lifespan ──────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan: startup and shutdown."""
    config = app_state.config

    # ── Startup ──────────────────────────────────────────
    logger.info("API server starting", host=config.server.host, port=config.server.port)

    # Initialize storage
    app_state.store = TelemetryStore(db_path=config.storage.db_path)
    app_state.store.open()

    # Initialize process attacher
    app_state.attacher = ProcessAttacher()

    # Initialize telemetry engine
    app_state.engine = TelemetryEngine(
        collector_names=config.telemetry.collectors,
        poll_interval_ms=config.telemetry.poll_interval_ms,
        buffer_size=config.telemetry.buffer_size,
    )
    await app_state.engine.start()

    # Audit: service start
    audit = get_audit_logger(config.logging.file_path)
    build = get_build_info()
    audit.service_start(build.version, build.build_number)

    logger.info("API server ready",
                dashboard=f"http://{config.server.host}:{config.server.port}")

    yield

    # ── Shutdown ─────────────────────────────────────────
    logger.info("API server shutting down")

    # Stop engine
    await app_state.engine.stop()

    # Detach all processes
    app_state.attacher.detach_all()

    # Close storage
    app_state.store.close()

    # Audit: service stop
    audit.service_stop(reason="shutdown")

    logger.info("API server stopped")


# ── App Factory ───────────────────────────────────────────────────────

def create_app(config: AppConfig, serve_dashboard: bool = True) -> FastAPI:
    """Create and configure the FastAPI application."""

    app_state.config = config
    build = get_build_info()

    app = FastAPI(
        title="ProcessScope",
        description="Linux Process Observability Platform — REST & WebSocket API",
        version=build.version,
        docs_url="/api/docs",
        redoc_url="/api/redoc",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=config.server.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # API routes
    app.include_router(api_router, prefix="/api/v1")

    # WebSocket routes
    app.include_router(ws_router)

    # Serve embedded dashboard
    if serve_dashboard:
        dashboard_dir = Path(__file__).parent.parent / "dashboard"
        if dashboard_dir.exists():
            app.mount("/", StaticFiles(directory=str(dashboard_dir), html=True), name="dashboard")
            logger.info("Dashboard served from embedded files")
        else:
            logger.info("No embedded dashboard found; API-only mode")

    return app


# ── Server Runner ─────────────────────────────────────────────────────

def run_server(config: AppConfig, serve_dashboard: bool = True) -> None:
    """Create the app and run it with uvicorn."""
    app = create_app(config, serve_dashboard=serve_dashboard)

    uvicorn.run(
        app,
        host=config.server.host,
        port=config.server.port,
        workers=config.server.workers,
        log_level="info" if not config.dev_mode else "debug",
        access_log=config.dev_mode,
    )
