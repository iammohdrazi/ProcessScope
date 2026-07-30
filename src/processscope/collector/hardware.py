"""
ProcessScope — Hardware Information Collector.

Collects hardware info relevant to the hooked process:
  - CPU model, cores, cache, frequency
  - Memory installed, NUMA
  - Disk devices, mount points, types
  - GPU info (if nvidia-smi available)
  - Network interfaces
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import psutil

from processscope.collector.base import (
    BaseCollector, CollectorRegistry, EventCategory, TelemetryEvent,
)


@CollectorRegistry.register
class HardwareCollector(BaseCollector):
    """Collects hardware information (low-frequency, mostly static)."""

    @property
    def name(self) -> str:
        return "hardware"

    @property
    def category(self) -> EventCategory:
        return EventCategory.HARDWARE

    def __init__(self, poll_interval_ms: int = 1000) -> None:
        # Hardware info is mostly static; collect every 30 seconds
        super().__init__(poll_interval_ms=max(poll_interval_ms, 30000))
        self._initial_collected = False

    async def _collect(self) -> list[TelemetryEvent]:
        events: list[TelemetryEvent] = []

        data: dict[str, Any] = {}

        # CPU info
        data["cpu"] = _collect_cpu_info()

        # Memory info
        data["memory"] = _collect_memory_info()

        # Disk info
        data["disks"] = _collect_disk_info()

        # GPU info
        data["gpu"] = _collect_gpu_info()

        # Network interfaces
        data["network_interfaces"] = _collect_network_interfaces()

        # System info
        data["system"] = _collect_system_info()

        events.append(self.emit_event(
            title="Hardware Info",
            data=data,
        ))

        return events


def _collect_cpu_info() -> dict[str, Any]:
    """Collect CPU hardware information."""
    info: dict[str, Any] = {
        "physical_cores": psutil.cpu_count(logical=False),
        "logical_cores": psutil.cpu_count(logical=True),
    }

    # CPU frequency
    try:
        freq = psutil.cpu_freq()
        if freq:
            info["frequency_mhz"] = {
                "current": round(freq.current, 2),
                "min": round(freq.min, 2),
                "max": round(freq.max, 2),
            }
    except (AttributeError, FileNotFoundError):
        pass

    # CPU model from /proc/cpuinfo
    try:
        cpuinfo_path = Path("/proc/cpuinfo")
        if cpuinfo_path.exists():
            with open(cpuinfo_path) as f:
                for line in f:
                    if line.startswith("model name"):
                        info["model"] = line.split(":", 1)[1].strip()
                        break
                    elif line.startswith("vendor_id"):
                        info["vendor"] = line.split(":", 1)[1].strip()

            # Cache info
            for line in cpuinfo_path.read_text().split("\n"):
                if "cache size" in line:
                    info["cache_size"] = line.split(":", 1)[1].strip()
                    break
    except (PermissionError, OSError):
        pass

    # CPU temperatures
    try:
        temps = psutil.sensors_temperatures()
        if temps:
            cpu_temps = []
            for name, entries in temps.items():
                if "core" in name.lower() or "cpu" in name.lower() or "coretemp" in name.lower():
                    for entry in entries:
                        cpu_temps.append({
                            "label": entry.label or name,
                            "current": entry.current,
                            "high": entry.high,
                            "critical": entry.critical,
                        })
            if cpu_temps:
                info["temperatures"] = cpu_temps
    except (AttributeError, FileNotFoundError):
        pass

    return info


def _collect_memory_info() -> dict[str, Any]:
    """Collect memory hardware information."""
    vm = psutil.virtual_memory()
    swap = psutil.swap_memory()

    return {
        "total": vm.total,
        "total_human": _human_bytes(vm.total),
        "available": vm.available,
        "available_human": _human_bytes(vm.available),
        "swap_total": swap.total,
        "swap_total_human": _human_bytes(swap.total),
    }


def _collect_disk_info() -> list[dict[str, Any]]:
    """Collect disk hardware information."""
    disks = []
    for part in psutil.disk_partitions(all=False):
        disk: dict[str, Any] = {
            "device": part.device,
            "mountpoint": part.mountpoint,
            "fstype": part.fstype,
            "opts": part.opts,
        }

        try:
            usage = psutil.disk_usage(part.mountpoint)
            disk["total"] = usage.total
            disk["total_human"] = _human_bytes(usage.total)
            disk["used"] = usage.used
            disk["free"] = usage.free
            disk["percent"] = usage.percent
        except (PermissionError, OSError):
            pass

        # Detect disk type (SSD/HDD/NVMe)
        dev_name = part.device.replace("/dev/", "").rstrip("0123456789")
        rotational_path = Path(f"/sys/block/{dev_name}/queue/rotational")
        try:
            if rotational_path.exists():
                is_rotational = rotational_path.read_text().strip() == "1"
                disk["type"] = "HDD" if is_rotational else "SSD"
            if "nvme" in dev_name:
                disk["type"] = "NVMe"
        except (PermissionError, OSError):
            pass

        disks.append(disk)

    return disks


def _collect_gpu_info() -> list[dict[str, Any]]:
    """Collect GPU information via nvidia-smi (if available)."""
    gpus: list[dict[str, Any]] = []

    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,memory.used,memory.free,utilization.gpu,temperature.gpu",
             "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            for i, line in enumerate(result.stdout.strip().split("\n")):
                parts = [p.strip() for p in line.split(",")]
                if len(parts) >= 6:
                    gpus.append({
                        "index": i,
                        "name": parts[0],
                        "memory_total_mb": int(parts[1]),
                        "memory_used_mb": int(parts[2]),
                        "memory_free_mb": int(parts[3]),
                        "utilization_percent": int(parts[4]),
                        "temperature_c": int(parts[5]),
                    })
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError, ValueError):
        pass

    return gpus


def _collect_network_interfaces() -> list[dict[str, Any]]:
    """Collect network interface information."""
    interfaces: list[dict[str, Any]] = []
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()

    for name, addr_list in addrs.items():
        iface: dict[str, Any] = {"name": name, "addresses": []}

        for addr in addr_list:
            iface["addresses"].append({
                "family": str(addr.family.name) if hasattr(addr.family, "name") else str(addr.family),
                "address": addr.address,
                "netmask": addr.netmask,
                "broadcast": addr.broadcast,
            })

        if name in stats:
            s = stats[name]
            iface["is_up"] = s.isup
            iface["speed_mbps"] = s.speed
            iface["mtu"] = s.mtu

        interfaces.append(iface)

    return interfaces


def _collect_system_info() -> dict[str, Any]:
    """Collect general system information."""
    import platform
    info: dict[str, Any] = {
        "hostname": platform.node(),
        "os": platform.system(),
        "os_release": platform.release(),
        "os_version": platform.version(),
        "architecture": platform.machine(),
        "boot_time": psutil.boot_time(),
    }

    # Kernel version
    try:
        info["kernel"] = Path("/proc/version").read_text().strip()
    except (PermissionError, OSError):
        pass

    return info


def _human_bytes(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}"
        n = int(n / 1024)
    return f"{n:.1f} PB"
