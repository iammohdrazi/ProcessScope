# Getting Started

ProcessScope can be run from source in development mode or installed natively via system packages.

## Requirements

- **OS**: Linux (Ubuntu 20.04+, Debian 11+, RHEL 8+, Fedora 36+)
- **Kernel**: 5.8+ (for eBPF features; graceful degradation on older kernels)
- **Python**: 3.10+
- **Node.js**: 18+ (for dashboard build only)
- **Privileges**: Root or CAP_SYS_PTRACE for process attachment

## From Source (Development)

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

## From Package (Production)

```bash
# Install from tar.gz
tar -xzf processscope-0.1.0-linux-x86_64.tar.gz
cd processscope-0.1.0
sudo ./install.sh

# Or install from .deb
sudo dpkg -i processscope_0.1.0-1_amd64.deb

# Or install from .rpm
sudo rpm -i processscope-0.1.0-1.x86_64.rpm
```

### Managing the Service

Once installed natively, ProcessScope runs as a systemd service:

```bash
# Service management
sudo systemctl status processscope
sudo systemctl start processscope
sudo systemctl stop processscope

# View logs
journalctl -u processscope -f
cat /var/log/processscope/processscope.log
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
