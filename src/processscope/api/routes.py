"""
ProcessScope — API Route Definitions.

All REST API endpoints under /api/v1/*.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from processscope.api.state import app_state
from processscope.process.metadata import collect_metadata
from processscope.process.binary import analyze_binary
from processscope.process.tree import build_process_tree, build_full_system_tree
from processscope.version import get_build_info
from processscope.logging import get_logger

logger = get_logger("api.routes")

router = APIRouter()


# ── Request/Response Models ───────────────────────────────────────────

class AttachRequest(BaseModel):
    pid: Optional[int] = None
    name: Optional[str] = None
    include_children: bool = False
    read_only: bool = False


class AttachResponse(BaseModel):
    pid: int
    name: str
    status: str
    message: str


class StatusResponse(BaseModel):
    status: str
    version: str
    build_number: str
    uptime: str
    hooked_count: int
    hooked_processes: list[dict[str, Any]]
    engine: dict[str, Any]


# ── Version & Health ──────────────────────────────────────────────────

@router.get("/version")
async def get_version() -> dict:
    """Get version and build information."""
    return get_build_info().to_dict()


@router.get("/health")
async def health_check() -> dict:
    """Health check endpoint."""
    return {"status": "healthy", "timestamp": time.time()}


@router.get("/status")
async def get_status() -> dict:
    """Get full agent status."""
    build = get_build_info()
    engine = app_state.engine

    uptime = engine.uptime_seconds
    if uptime < 60:
        uptime_str = f"{uptime:.0f}s"
    elif uptime < 3600:
        uptime_str = f"{uptime / 60:.0f}m"
    else:
        uptime_str = f"{uptime / 3600:.1f}h"

    return {
        "status": "running",
        "version": build.version,
        "build_number": build.build_number,
        "uptime": uptime_str,
        "hooked_count": app_state.attacher.hooked_count,
        "hooked_processes": app_state.attacher.list_hooked(),
        "engine": engine.status_dict(),
        "collectors": engine.get_collector_status(),
        "storage": app_state.store.get_stats(),
    }


# ── Process Attachment ────────────────────────────────────────────────

@router.post("/processes/attach")
async def attach_process(req: AttachRequest) -> dict:
    """Attach to a running process."""
    if not req.pid and not req.name:
        raise HTTPException(status_code=400, detail="Specify either pid or name")

    try:
        if req.pid:
            hooked = app_state.attacher.attach_by_pid(
                req.pid,
                read_only=req.read_only,
                include_children=req.include_children,
            )
            # Start telemetry collection
            await app_state.engine.start_collectors(req.pid)
            # Start session recording
            app_state.engine.session_manager.start_recording(req.pid)

            return {
                "pid": hooked.pid,
                "name": hooked.name,
                "status": "attached",
                "message": f"Attached to {hooked.name} (PID {hooked.pid})",
            }
        else:
            hooked_list = app_state.attacher.attach_by_name(
                req.name,  # type: ignore
                read_only=req.read_only,
                include_children=req.include_children,
            )
            for h in hooked_list:
                await app_state.engine.start_collectors(h.pid)
                app_state.engine.session_manager.start_recording(h.pid)

            return {
                "count": len(hooked_list),
                "processes": [h.to_dict() for h in hooked_list],
                "status": "attached",
                "message": f"Attached to {len(hooked_list)} process(es)",
            }

    except ProcessLookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))


@router.get("/processes")
async def list_processes() -> dict:
    """List all hooked processes."""
    return {
        "count": app_state.attacher.hooked_count,
        "processes": app_state.attacher.list_hooked(),
    }


@router.delete("/processes/{pid}")
async def detach_process(pid: int) -> dict:
    """Detach from a hooked process."""
    try:
        # Stop collectors
        await app_state.engine.stop_collectors(pid)
        # Stop recording
        app_state.engine.session_manager.stop_recording(pid)
        # Detach
        app_state.attacher.detach(pid)
        return {"pid": pid, "status": "detached", "message": f"Detached from PID {pid}"}
    except KeyError:
        raise HTTPException(status_code=404, detail=f"PID {pid} is not hooked")


# ── Process Metadata ─────────────────────────────────────────────────

@router.get("/processes/{pid}/metadata")
async def get_process_metadata(pid: int) -> dict:
    """Get comprehensive metadata for a hooked process."""
    hooked = app_state.attacher.get_hooked(pid)
    if not hooked:
        raise HTTPException(status_code=404, detail=f"PID {pid} is not hooked")

    try:
        metadata = collect_metadata(pid)
        return metadata.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/processes/{pid}/binary")
async def get_binary_info(pid: int) -> dict:
    """Get binary/ELF analysis for a hooked process."""
    hooked = app_state.attacher.get_hooked(pid)
    if not hooked:
        raise HTTPException(status_code=404, detail=f"PID {pid} is not hooked")

    info = analyze_binary(hooked.exe)
    return info.to_dict()


@router.get("/processes/{pid}/tree")
async def get_process_tree(pid: int) -> dict:
    """Get process tree rooted at a PID."""
    tree = build_process_tree(pid)
    return tree.to_dict()


# ── Telemetry Data ───────────────────────────────────────────────────

@router.get("/processes/{pid}/telemetry")
async def get_telemetry(
    pid: int,
    category: Optional[str] = None,
    limit: int = Query(default=100, le=1000),
    since: Optional[float] = None,
) -> dict:
    """Get recent telemetry events for a process."""
    events = app_state.engine.get_recent_events(
        pid=pid, limit=limit, category=category,
    )
    return {"pid": pid, "count": len(events), "events": events}


@router.get("/processes/{pid}/timeline")
async def get_timeline(
    pid: int,
    limit: int = Query(default=200, le=2000),
    category: Optional[str] = None,
    search: Optional[str] = None,
) -> dict:
    """Get timeline events for a process."""
    events = app_state.engine.timeline.get_events(
        pid=pid, limit=limit, category=category, search=search,
    )
    return {"pid": pid, "count": len(events), "events": events}


@router.get("/timeline/summary")
async def get_timeline_summary(
    pid: Optional[int] = None,
    bucket_seconds: int = Query(default=60, ge=10, le=3600),
) -> dict:
    """Get timeline summary bucketed by time."""
    summary = app_state.engine.timeline.get_timeline_summary(
        pid=pid, bucket_seconds=bucket_seconds,
    )
    return {"buckets": summary, "bucket_seconds": bucket_seconds}


# ── Search ────────────────────────────────────────────────────────────

@router.get("/search")
async def search_events(
    q: str = Query(..., min_length=1),
    pid: Optional[int] = None,
    category: Optional[str] = None,
    limit: int = Query(default=50, le=500),
) -> dict:
    """Search across all telemetry events."""
    events = app_state.engine.timeline.get_events(
        pid=pid, limit=limit, category=category, search=q,
    )
    return {"query": q, "count": len(events), "results": events}


# ── System ───────────────────────────────────────────────────────────

@router.get("/system/tree")
async def get_system_tree() -> dict:
    """Get full system process tree."""
    tree = build_full_system_tree()
    return {"tree": tree}


@router.get("/collectors")
async def get_collectors(pid: Optional[int] = None) -> dict:
    """Get status of all active collectors."""
    statuses = app_state.engine.get_collector_status(pid=pid)
    return {"collectors": statuses}


# ── Sessions ─────────────────────────────────────────────────────────

@router.get("/sessions")
async def list_sessions() -> dict:
    """List all recorded sessions."""
    sessions = app_state.engine.session_manager.list_sessions()
    return {"sessions": sessions}
