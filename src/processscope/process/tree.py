"""
ProcessScope — Process Tree Builder.

Builds and maintains a process tree structure showing
parent-child relationships for any PID.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import psutil

from processscope.logging import get_logger

logger = get_logger("process.tree")


@dataclass
class ProcessNode:
    """A node in the process tree."""
    pid: int
    ppid: int
    name: str
    exe: str = ""
    username: str = ""
    status: str = ""
    cpu_percent: float = 0.0
    memory_rss: int = 0
    num_threads: int = 0
    children: list[ProcessNode] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to nested dictionary for API/UI consumption."""
        return {
            "pid": self.pid,
            "ppid": self.ppid,
            "name": self.name,
            "exe": self.exe,
            "username": self.username,
            "status": self.status,
            "cpu_percent": round(self.cpu_percent, 2),
            "memory_rss": self.memory_rss,
            "memory_human": _human_bytes(self.memory_rss),
            "num_threads": self.num_threads,
            "children": [c.to_dict() for c in self.children],
            "child_count": self._count_descendants(),
        }

    def _count_descendants(self) -> int:
        """Count total descendants recursively."""
        count = len(self.children)
        for child in self.children:
            count += child._count_descendants()
        return count


@dataclass
class ProcessTree:
    """Complete process tree rooted at a specific PID."""
    root_pid: int
    root: Optional[ProcessNode] = None
    total_nodes: int = 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize the entire tree."""
        return {
            "root_pid": self.root_pid,
            "total_nodes": self.total_nodes,
            "tree": self.root.to_dict() if self.root else None,
        }


def build_process_tree(pid: int) -> ProcessTree:
    """
    Build a complete process tree rooted at the given PID.

    The tree includes the target process and all its descendants.

    Args:
        pid: Root process ID.

    Returns:
        ProcessTree with nested ProcessNode children.
    """
    logger.debug("Building process tree", root_pid=pid)

    tree = ProcessTree(root_pid=pid)

    try:
        root_proc = psutil.Process(pid)
        tree.root = _build_node(root_proc)
        tree.total_nodes = 1 + tree.root._count_descendants()
    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        logger.warning("Cannot build tree for PID", pid=pid, error=str(e))

    logger.debug("Process tree built", root_pid=pid, total_nodes=tree.total_nodes)
    return tree


def build_full_system_tree() -> list[dict[str, Any]]:
    """
    Build a tree of all system processes.

    Returns a list of root-level process trees (processes with no parent or ppid=0).
    """
    all_procs: dict[int, dict] = {}
    child_map: dict[int, list[int]] = {}

    for proc in psutil.process_iter(["pid", "ppid", "name", "username", "status"]):
        try:
            info = proc.info
            pid = info["pid"]
            ppid = info["ppid"] or 0
            all_procs[pid] = {
                "pid": pid,
                "ppid": ppid,
                "name": info.get("name", ""),
                "username": info.get("username", ""),
                "status": info.get("status", ""),
            }
            child_map.setdefault(ppid, []).append(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    def _build_tree_node(pid: int) -> dict[str, Any]:
        proc_info = all_procs.get(pid, {"pid": pid, "ppid": 0, "name": "?"})
        node = {**proc_info, "children": []}
        for child_pid in child_map.get(pid, []):
            node["children"].append(_build_tree_node(child_pid))
        return node

    # Find root processes (ppid not in our process list)
    roots = []
    for pid, info in all_procs.items():
        if info["ppid"] not in all_procs or info["ppid"] == 0:
            roots.append(_build_tree_node(pid))

    return roots


def _build_node(proc: psutil.Process) -> ProcessNode:
    """Build a ProcessNode with children recursively."""
    try:
        node = ProcessNode(
            pid=proc.pid,
            ppid=proc.ppid(),
            name=proc.name(),
            exe=proc.exe() if proc.pid != 0 else "",
            username=proc.username(),
            status=proc.status(),
            cpu_percent=proc.cpu_percent(interval=0),
            memory_rss=proc.memory_info().rss,
            num_threads=proc.num_threads(),
        )

        for child in proc.children(recursive=False):
            try:
                child_node = _build_node(child)
                node.children.append(child_node)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        return node

    except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
        return ProcessNode(pid=proc.pid, ppid=0, name="<access denied>", status="unknown")


def _human_bytes(n: int) -> str:
    """Format bytes into a human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}"
        n = int(n / 1024)
    return f"{n:.1f} TB"
