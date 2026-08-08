"""
ProcessScope — Build-time version and metadata.

Build metadata is injected by the Makefile into _build_meta.json during `make build`.
At runtime, this module reads that file; if missing, it falls back to development defaults.
"""

from __future__ import annotations

import json
import platform
import sys
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class BuildInfo:
    """Immutable container for all version and build metadata."""

    name: str = "processscope"
    display_name: str = "ProcessScope"
    version: str = "0.1.0"
    build_number: str = "local"
    build_type: str = "local"  # "local" | "release"
    git_commit: str = "unknown"
    git_branch: str = "unknown"
    build_date: str = "unknown"
    python_version: str = field(default_factory=lambda: platform.python_version())
    platform_info: str = field(default_factory=lambda: f"{sys.platform}/{platform.machine()}")
    min_kernel: str = "5.8+"

    def to_dict(self) -> dict:
        """Serialize to dictionary for API responses."""
        return {
            "name": self.name,
            "display_name": self.display_name,
            "version": self.version,
            "build_number": self.build_number,
            "build_type": self.build_type,
            "git_commit": self.git_commit,
            "git_branch": self.git_branch,
            "build_date": self.build_date,
            "python_version": self.python_version,
            "platform": self.platform_info,
            "min_kernel": self.min_kernel,
        }

    def format_banner(self) -> str:
        """Return a multi-line version banner for CLI output."""
        return (
            f"ProcessScope — Linux Process Observability Platform\n"
            f"  Version:      {self.version}\n"
            f"  Build:        {self.build_number}  ({self.build_type})\n"
            f"  Git Commit:   {self.git_commit}\n"
            f"  Git Branch:   {self.git_branch}\n"
            f"  Build Date:   {self.build_date}\n"
            f"  Python:       {self.python_version}\n"
            f"  Platform:     {self.platform_info}\n"
            f"  Min Kernel:   {self.min_kernel}"
        )


def get_build_info() -> BuildInfo:
    """
    Load build metadata from _build_meta.json (injected at build time).
    Falls back to development defaults if the file doesn't exist.
    """
    meta_path = Path(__file__).parent / "_build_meta.json"

    if meta_path.exists():
        try:
            with open(meta_path) as f:
                data = json.load(f)
            return BuildInfo(
                version=data.get("version", "0.1.0"),
                build_number=data.get("build_number", "local"),
                build_type=data.get("build_type", "local"),
                git_commit=data.get("git_commit", "unknown"),
                git_branch=data.get("git_branch", "unknown"),
                build_date=data.get("build_date", "unknown"),
            )
        except (json.JSONDecodeError, KeyError):
            pass

    return BuildInfo()
