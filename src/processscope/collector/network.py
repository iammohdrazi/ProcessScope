"""
ProcessScope — Network Telemetry Collector.

Monitors:
  - TCP/UDP connections (active, listening)
  - Per-connection state and remote endpoints
  - Network I/O (bytes sent/received)
  - Connection creation/closure detection
"""

from __future__ import annotations

import psutil

from processscope.collector.base import (
    BaseCollector, CollectorRegistry, EventCategory, EventSeverity, TelemetryEvent,
)


@CollectorRegistry.register
class NetworkCollector(BaseCollector):
    """Collects network telemetry for a hooked process."""

    @property
    def name(self) -> str:
        return "network"

    @property
    def category(self) -> EventCategory:
        return EventCategory.NETWORK

    def __init__(self, poll_interval_ms: int = 1000) -> None:
        super().__init__(poll_interval_ms)
        self._known_connections: set[str] = set()
        self._prev_io: dict[str, int] = {"bytes_sent": 0, "bytes_recv": 0}

    async def _collect(self) -> list[TelemetryEvent]:
        events: list[TelemetryEvent] = []

        try:
            proc = self._proc
            if proc is None:
                return events
            connections = proc.connections(kind="all")

            # Build connection data
            conn_data = []
            current_keys: set[str] = set()

            for conn in connections:
                laddr = ""
                if conn.laddr:
                    laddr = f"{conn.laddr.ip}:{conn.laddr.port}" if hasattr(conn.laddr, "ip") else str(conn.laddr)
                raddr = ""
                if conn.raddr:
                    raddr = f"{conn.raddr.ip}:{conn.raddr.port}" if hasattr(conn.raddr, "ip") else str(conn.raddr)
                conn_key = f"{conn.type}:{laddr}->{raddr}:{conn.status}"
                current_keys.add(conn_key)

                conn_data.append({
                    "fd": conn.fd,
                    "family": str(conn.family.name) if hasattr(conn.family, "name") else str(conn.family),
                    "type": str(conn.type.name) if hasattr(conn.type, "name") else str(conn.type),
                    "local_address": laddr,
                    "remote_address": raddr,
                    "status": conn.status,
                })

            # Detect new/closed connections
            new_conns = current_keys - self._known_connections
            closed_conns = self._known_connections - current_keys
            self._known_connections = current_keys

            for conn_key in new_conns:
                events.append(self.emit_event(
                    title="Connection Opened",
                    message=conn_key,
                    tags=["connection_lifecycle"],
                ))

            for conn_key in closed_conns:
                events.append(self.emit_event(
                    title="Connection Closed",
                    message=conn_key,
                    tags=["connection_lifecycle"],
                ))

            # System-wide network I/O (process-level I/O requires eBPF or /proc/net)
            net_io = psutil.net_io_counters()
            io_data = {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv,
                "errin": net_io.errin,
                "errout": net_io.errout,
                "dropin": net_io.dropin,
                "dropout": net_io.dropout,
            }

            # Calculate rates
            if self._prev_io["bytes_sent"] > 0:
                io_data["send_rate"] = net_io.bytes_sent - self._prev_io["bytes_sent"]
                io_data["recv_rate"] = net_io.bytes_recv - self._prev_io["bytes_recv"]
                io_data["send_rate_human"] = _human_bytes(io_data["send_rate"]) + "/s"
                io_data["recv_rate_human"] = _human_bytes(io_data["recv_rate"]) + "/s"

            self._prev_io = {"bytes_sent": net_io.bytes_sent, "bytes_recv": net_io.bytes_recv}

            # Summary by status
            status_counts: dict[str, int] = {}
            for conn in conn_data:
                st = conn["status"]
                status_counts[st] = status_counts.get(st, 0) + 1

            events.append(self.emit_event(
                title="Network Sample",
                data={
                    "connections": conn_data[:50],  # Cap
                    "connection_count": len(connections),
                    "status_summary": status_counts,
                    "io": io_data,
                    "new_connections": len(new_conns),
                    "closed_connections": len(closed_conns),
                },
            ))

        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            self._logger.warning("Network collection failed", pid=self._pid, error=str(e))

        return events


def _human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}"
        n = int(n / 1024)
    return f"{n:.1f} TB"
