"""
ProcessScope — ELF Binary Analyzer.

Analyzes the executable binary of a hooked process:
  - ELF headers (class, endianness, ABI, type, machine)
  - Sections and segments
  - Shared library dependencies
  - Symbol availability (debug, stripped)
  - Build ID
  - Binary size, architecture
  - Package manager source detection (APT, Snap, Flatpak)
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from processscope.logging import get_logger

logger = get_logger("process.binary")


@dataclass
class BinaryInfo:
    """Complete binary analysis for a process executable."""

    # Basic
    path: str = ""
    size: int = 0
    size_human: str = ""
    exists: bool = False

    # ELF headers
    elf_class: str = ""          # ELF32 or ELF64
    elf_data: str = ""           # Little-endian or Big-endian
    elf_abi: str = ""            # ELFOSABI
    elf_type: str = ""           # ET_EXEC, ET_DYN, etc.
    elf_machine: str = ""        # x86_64, ARM, etc.
    elf_entry: int = 0           # Entry point address

    # Build info
    build_id: str = ""
    has_debug_symbols: bool = False
    is_stripped: bool = True
    compiler_info: str = ""

    # Sections
    sections: list[dict[str, Any]] = field(default_factory=list)

    # Dependencies
    shared_libraries: list[str] = field(default_factory=list)
    interpreter: str = ""

    # Package info
    package_name: str = ""
    package_version: str = ""
    package_source: str = ""     # apt, snap, flatpak, manual

    # Permissions
    owner: str = ""
    permissions: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serialize for API responses."""
        return {
            "path": self.path,
            "size": self.size,
            "size_human": self.size_human,
            "exists": self.exists,
            "elf": {
                "class": self.elf_class,
                "data": self.elf_data,
                "abi": self.elf_abi,
                "type": self.elf_type,
                "machine": self.elf_machine,
                "entry_point": hex(self.elf_entry) if self.elf_entry else "0x0",
            },
            "build": {
                "build_id": self.build_id,
                "has_debug_symbols": self.has_debug_symbols,
                "is_stripped": self.is_stripped,
                "compiler": self.compiler_info,
            },
            "sections": self.sections[:20],  # Limit for API response
            "dependencies": {
                "shared_libraries": self.shared_libraries,
                "interpreter": self.interpreter,
            },
            "package": {
                "name": self.package_name,
                "version": self.package_version,
                "source": self.package_source,
            },
            "permissions": {
                "owner": self.owner,
                "mode": self.permissions,
            },
        }


def analyze_binary(exe_path: str) -> BinaryInfo:
    """
    Analyze a binary executable file.

    Args:
        exe_path: Path to the executable.

    Returns:
        BinaryInfo with all available fields populated.
    """
    info = BinaryInfo(path=exe_path)
    path = Path(exe_path)

    if not path.exists():
        logger.warning("Binary not found", path=exe_path)
        return info

    info.exists = True
    info.size = path.stat().st_size
    info.size_human = _human_bytes(info.size)

    # Permissions
    try:
        stat = path.stat()
        info.permissions = oct(stat.st_mode)[-3:]
        import pwd
        info.owner = pwd.getpwuid(stat.st_uid).pw_name
    except (ImportError, KeyError, OSError):
        pass

    # ELF analysis using pyelftools
    _analyze_elf(path, info)

    # Shared library dependencies via ldd
    _analyze_dependencies(exe_path, info)

    # Package manager source
    _detect_package_source(exe_path, info)

    logger.debug("Binary analysis complete", path=exe_path, elf_class=info.elf_class)
    return info


def _analyze_elf(path: Path, info: BinaryInfo) -> None:
    """Parse ELF headers using pyelftools."""
    try:
        from elftools.elf.elffile import ELFFile
        from elftools.elf.sections import NoteSection

        with open(path, "rb") as f:
            try:
                elf = ELFFile(f)
            except Exception:
                logger.debug("Not an ELF binary", path=str(path))
                return

            # ELF header fields
            info.elf_class = elf.elfclass.__class__.__name__ if hasattr(elf, "elfclass") else ""
            info.elf_class = f"ELF{elf.elfclass}"
            info.elf_data = elf.little_endian and "Little-endian" or "Big-endian"
            info.elf_type = elf.header.e_type
            info.elf_machine = elf.header.e_machine
            info.elf_entry = elf.header.e_entry
            info.elf_abi = elf.header.e_ident.EI_OSABI

            # Sections summary
            for section in elf.iter_sections():
                sec_info = {
                    "name": section.name,
                    "type": section["sh_type"],
                    "size": section["sh_size"],
                    "address": hex(section["sh_addr"]),
                }
                info.sections.append(sec_info)

                # Check for debug symbols
                if section.name.startswith(".debug") or section.name == ".symtab":
                    info.has_debug_symbols = True
                    info.is_stripped = False

            # Build ID from .note.gnu.build-id
            for section in elf.iter_sections():
                if isinstance(section, NoteSection):
                    for note in section.iter_notes():
                        if note["n_name"] == "GNU" and note["n_type"] == "NT_GNU_BUILD_ID":
                            info.build_id = note["n_desc"]

            # Check for .comment section (compiler info)
            comment_section = elf.get_section_by_name(".comment")
            if comment_section:
                try:
                    info.compiler_info = comment_section.data().decode("utf-8", errors="ignore").strip("\x00")
                except Exception:
                    pass

    except ImportError:
        logger.debug("pyelftools not available, skipping ELF analysis")
    except Exception as e:
        logger.debug("ELF analysis failed", path=str(path), error=str(e))


def _analyze_dependencies(exe_path: str, info: BinaryInfo) -> None:
    """Get shared library dependencies using ldd."""
    try:
        result = subprocess.run(
            ["ldd", exe_path],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0:
            for line in result.stdout.strip().split("\n"):
                line = line.strip()
                if "=>" in line:
                    parts = line.split("=>")
                    lib_path = parts[1].strip().split("(")[0].strip()
                    if lib_path:
                        info.shared_libraries.append(lib_path)
                elif "ld-linux" in line or "ld.so" in line:
                    info.interpreter = line.split("(")[0].strip()
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass


def _detect_package_source(exe_path: str, info: BinaryInfo) -> None:
    """Detect which package manager installed the binary."""
    # Try dpkg (Debian/Ubuntu)
    try:
        result = subprocess.run(
            ["dpkg", "-S", exe_path],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0 and ":" in result.stdout:
            pkg = result.stdout.strip().split(":")[0]
            info.package_name = pkg
            info.package_source = "apt"

            # Get version
            ver_result = subprocess.run(
                ["dpkg-query", "-W", "-f=${Version}", pkg],
                capture_output=True, text=True, timeout=5,
            )
            if ver_result.returncode == 0:
                info.package_version = ver_result.stdout.strip()
            return
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Try rpm (RHEL/Fedora)
    try:
        result = subprocess.run(
            ["rpm", "-qf", exe_path],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode == 0:
            info.package_name = result.stdout.strip()
            info.package_source = "rpm"
            return
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass

    # Check Snap
    if "/snap/" in exe_path:
        info.package_source = "snap"
        parts = exe_path.split("/snap/")
        if len(parts) > 1:
            info.package_name = parts[1].split("/")[0]
        return

    # Check Flatpak
    if "/flatpak/" in exe_path:
        info.package_source = "flatpak"
        return

    info.package_source = "manual"


def _human_bytes(n: int) -> str:
    """Format bytes into a human-readable string."""
    for unit in ("B", "KB", "MB", "GB"):
        if abs(n) < 1024.0:
            return f"{n:.1f} {unit}"
        n = int(n / 1024)
    return f"{n:.1f} TB"
