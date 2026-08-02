# ProcessScope

**Linux Process Observability Platform**

> Attach, inspect, and analyze any running Linux process in real time.

[![Version](https://img.shields.io/badge/version-0.1.4-blue.svg)]()
[![Python](https://img.shields.io/badge/python-3.10+-green.svg)]()
[![License](https://img.shields.io/badge/license-Apache%202.0-orange.svg)]()
[![Platform](https://img.shields.io/badge/platform-Linux-lightgrey.svg)]()

---

## Overview

ProcessScope is a professional Linux-native process observability platform that hooks into any running process and collects every observable piece of runtime information in real time. It provides developers, DevOps engineers, security researchers, and system administrators with a unified environment to inspect, debug, profile, trace, monitor, and analyze running processes through a modern web dashboard.

## Features

- **Process Hooking** — Attach to any process by PID or name
- **CPU Telemetry** — Usage, per-core, context switches, scheduling
- **Memory Monitoring** — Heap, stack, VMA, RSS, page faults, leak detection
- **Thread Inspector** — Creation, states, CPU usage, locks
- **Network Monitor** — TCP/UDP connections, bandwidth, latency
- **File System Tracker** — Open files, reads, writes, FD tracking
- **System Call Tracing** — Captured syscalls with arguments and timing
- **Hardware Info** — CPU, memory, disk, GPU detection
- **Unified Timeline** — Correlated events across all telemetry sources
- **Live Web Dashboard** — Real-time graphs, process tree, flame graphs
- **Dual Logging** — journald/syslog + structured application log files
- **Session Recording** — Record and replay process sessions
- **Full Packaging** — tar.gz, .deb, .rpm with systemd service

## Quick Start

### From Source (Development)

```bash
# Clone
git clone https://github.com/processscope/processscope.git
cd processscope

# Install in development mode
make install

# Run
sudo .venv/bin/processscope start

# Open dashboard
# http://localhost:9876
```

### From Package (Production)

```bash
# Install from tar.gz
tar -xzf processscope-0.1.0-linux-x86_64.tar.gz
cd processscope-0.1.0
sudo ./install.sh

# Or install from .deb
sudo dpkg -i processscope_0.1.0-1_amd64.deb

# Or install from .rpm
sudo rpm -i processscope-0.1.0-1.x86_64.rpm

# Service management
sudo systemctl status processscope
sudo systemctl start processscope
sudo systemctl stop processscope

# View logs
journalctl -u processscope -f
cat /var/log/processscope/processscope.log
```

### Attach to a Process

```bash
# Attach by PID
processscope attach --pid 1234

# Attach by name
processscope attach --name nginx

# View status
processscope status

# Open dashboard
# http://localhost:9876
```

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Web Dashboard                      │
│              React + Vite (port 9876)                │
├──────────────┬──────────────────┬────────────────────┤
│   REST API   │   WebSocket      │   Static Assets    │
├──────────────┴──────────────────┴────────────────────┤
│                  FastAPI Server                       │
├──────────────────────────────────────────────────────┤
│               Telemetry Engine                        │
│         (Correlation · Timeline · Sessions)           │
├──────┬──────┬──────┬──────┬──────┬──────┬────────────┤
│ CPU  │ Mem  │ Thr  │ Net  │  FS  │ Sys  │  HW Info   │
│Coll. │Coll. │Coll. │Coll. │Coll. │Call  │  Coll.     │
├──────┴──────┴──────┴──────┴──────┴──────┴────────────┤
│              Process Hooking Layer                    │
│        (Attach · Metadata · ELF · Tree)               │
├──────────────────────────────────────────────────────┤
│          Linux Kernel (/proc · psutil · ptrace)       │
└──────────────────────────────────────────────────────┘
```

## Installation Paths (FHS)

| Path | Purpose |
|:-----|:--------|
| `/opt/processscope/` | Application files |
| `/opt/processscope/bin/` | Main binary / wrapper |
| `/opt/processscope/venv/` | Python virtual environment |
| `/etc/processscope/` | Configuration |
| `/var/log/processscope/` | Application logs |
| `/var/lib/processscope/` | Data (SQLite, sessions) |
| `/usr/lib/systemd/system/` | Service file |
| `/usr/bin/processscope` | CLI symlink |

## Logging

### System Logs (journald / syslog)
```bash
# View via journalctl
journalctl -u processscope -f

# In /var/log/messages or /var/log/syslog
grep processscope /var/log/messages
```

### Application Logs
```bash
# Main log
tail -f /var/log/processscope/processscope.log

# Telemetry log
tail -f /var/log/processscope/telemetry.log

# Audit log
tail -f /var/log/processscope/audit.log
```

## Build

```bash
make help          # Show all targets
make version       # Print version info
make build         # Build production package
make test          # Run tests
make package-tar   # Create tar.gz
make package-deb   # Create .deb
make all           # Full pipeline
make clean         # Clean artifacts
```

## Release Workflow

ProcessScope includes a GitHub Actions workflow for automated release builds with multi-distribution testing.

### Creating a Release

1. Go to **Actions** → **ProcessScope Release Build**
2. Click **Run workflow**
3. Select version bump type (patch/minor/major)
4. Enable release creation
5. Click **Run workflow**

The workflow will:
- Automatically bump the version in `pyproject.toml`
- Build release packages
- Test installation across 8 Linux distributions (Ubuntu, Debian, RHEL, Fedora, SLES)
- Verify install/uninstall cycles on each distribution
- Create a GitHub release with artifacts if all tests pass

### Tested Distributions

- ✅ Ubuntu 22.04 & 24.04
- ✅ Debian 11 & 12
- ✅ Fedora 39
- ✅ Rocky Linux 8

**Note**: Docker-based testing runs in container mode without systemd. For complete systemd integration testing, install on actual VMs or bare metal systems.

See [scripts/README.md](scripts/README.md) for workflow details and manual testing instructions.

## Requirements

- **OS**: Linux (Ubuntu 20.04+, Debian 11+, RHEL 8+, Fedora 36+)
- **Kernel**: 5.8+ (for eBPF features; graceful degradation on older kernels)
- **Python**: 3.10+
- **Node.js**: 18+ (for dashboard build only)
- **Privileges**: Root or CAP_SYS_PTRACE for process attachment

## License

Apache License 2.0 — See [LICENSE](LICENSE) for details.
