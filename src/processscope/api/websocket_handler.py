"""
ProcessScope — WebSocket Handler for Live Telemetry Streaming.

Provides real-time telemetry streaming to connected dashboard clients.
"""

from __future__ import annotations

import asyncio
import json
import time
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from processscope.api.server import app_state
from processscope.collector.base import TelemetryEvent
from processscope.logging import get_logger

logger = get_logger("api.websocket")

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections."""

    def __init__(self) -> None:
        self._connections: dict[str, WebSocket] = {}
        self._subscriptions: dict[str, dict] = {}  # conn_id → {pid, categories}

    async def connect(self, websocket: WebSocket, conn_id: str) -> None:
        await websocket.accept()
        self._connections[conn_id] = websocket
        logger.info("WebSocket connected", conn_id=conn_id)

    def disconnect(self, conn_id: str) -> None:
        self._connections.pop(conn_id, None)
        self._subscriptions.pop(conn_id, None)
        logger.info("WebSocket disconnected", conn_id=conn_id)

    def subscribe(self, conn_id: str, pid: int | None = None,
                  categories: list[str] | None = None) -> None:
        self._subscriptions[conn_id] = {
            "pid": pid,
            "categories": categories or [],
        }

    async def broadcast_event(self, event: TelemetryEvent) -> None:
        """Send an event to all matching subscribers."""
        event_dict = event.to_dict()
        message = json.dumps({"type": "telemetry_event", "data": event_dict})

        disconnected: list[str] = []

        for conn_id, ws in self._connections.items():
            sub = self._subscriptions.get(conn_id, {})

            # Filter by subscription
            if sub.get("pid") is not None and event.pid != sub["pid"]:
                continue
            if sub.get("categories") and event.category.value not in sub["categories"]:
                continue

            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(conn_id)

        for conn_id in disconnected:
            self.disconnect(conn_id)

    @property
    def active_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()


@router.websocket("/ws/telemetry")
async def telemetry_stream(websocket: WebSocket) -> None:
    """
    WebSocket endpoint for live telemetry streaming.

    After connection, client can send JSON messages to control the stream:
      {"action": "subscribe", "pid": 1234, "categories": ["cpu", "memory"]}
      {"action": "unsubscribe"}
      {"action": "ping"}
    """
    conn_id = uuid4().hex[:8]
    await manager.connect(websocket, conn_id)

    # Register with the telemetry engine
    async def _on_event(event: TelemetryEvent) -> None:
        await manager.broadcast_event(event)

    app_state.engine.subscribe(f"ws_{conn_id}", _on_event)

    try:
        # Send initial status
        await websocket.send_json({
            "type": "connected",
            "conn_id": conn_id,
            "timestamp": time.time(),
            "hooked_processes": app_state.attacher.list_hooked(),
        })

        while True:
            # Listen for client control messages
            data = await websocket.receive_text()

            try:
                msg = json.loads(data)
                action = msg.get("action", "")

                if action == "subscribe":
                    pid = msg.get("pid")
                    categories = msg.get("categories", [])
                    manager.subscribe(conn_id, pid=pid, categories=categories)
                    await websocket.send_json({
                        "type": "subscribed",
                        "pid": pid,
                        "categories": categories,
                    })

                elif action == "unsubscribe":
                    manager.subscribe(conn_id)  # Reset to all events
                    await websocket.send_json({"type": "unsubscribed"})

                elif action == "ping":
                    await websocket.send_json({
                        "type": "pong",
                        "timestamp": time.time(),
                    })

                elif action == "get_status":
                    await websocket.send_json({
                        "type": "status",
                        "data": app_state.engine.status_dict(),
                    })

            except json.JSONDecodeError:
                await websocket.send_json({
                    "type": "error",
                    "message": "Invalid JSON",
                })

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("WebSocket error", conn_id=conn_id, error=str(e))
    finally:
        app_state.engine.unsubscribe(f"ws_{conn_id}")
        manager.disconnect(conn_id)


@router.websocket("/ws/telemetry/{pid}")
async def telemetry_stream_pid(websocket: WebSocket, pid: int) -> None:
    """
    WebSocket endpoint for live telemetry streaming for a specific PID.
    Auto-subscribes to the given PID.
    """
    conn_id = uuid4().hex[:8]
    await manager.connect(websocket, conn_id)
    manager.subscribe(conn_id, pid=pid)

    async def _on_event(event: TelemetryEvent) -> None:
        await manager.broadcast_event(event)

    app_state.engine.subscribe(f"ws_{conn_id}", _on_event)

    try:
        await websocket.send_json({
            "type": "connected",
            "conn_id": conn_id,
            "pid": pid,
            "timestamp": time.time(),
        })

        while True:
            data = await websocket.receive_text()
            try:
                msg = json.loads(data)
                if msg.get("action") == "ping":
                    await websocket.send_json({"type": "pong", "timestamp": time.time()})
            except json.JSONDecodeError:
                pass

    except WebSocketDisconnect:
        pass
    except Exception as e:
        logger.error("WebSocket error", conn_id=conn_id, pid=pid, error=str(e))
    finally:
        app_state.engine.unsubscribe(f"ws_{conn_id}")
        manager.disconnect(conn_id)
