#!/bin/bash
# ============================================================
# ProcessScope — Uninstallation Script
# ============================================================

set -e

if [ "$EUID" -ne 0 ]; then
  echo "❌ Error: Please run as root (e.g., sudo ./uninstall.sh)"
  exit 1
fi

APP_NAME="processscope"
echo "━━━ Uninstalling $APP_NAME ━━━"

# 1. Stop and disable service
if systemctl is-active --quiet processscope; then
    echo "Stopping service..."
    systemctl stop processscope
fi

if systemctl is-enabled --quiet processscope 2>/dev/null; then
    echo "Disabling service..."
    systemctl disable processscope
fi

# 2. Remove systemd service file
echo "Removing systemd integration..."
rm -f /usr/lib/systemd/system/processscope.service
rm -f /etc/systemd/system/processscope.service
systemctl daemon-reload
systemctl reset-failed processscope >/dev/null 2>&1 || true

# 3. Remove logrotate config
rm -f /etc/logrotate.d/$APP_NAME

# 4. Remove CLI symlink
rm -f /usr/local/bin/processscope

# 5. Remove application files
echo "Removing application files..."
rm -rf /opt/$APP_NAME
rm -rf /etc/$APP_NAME
rm -rf /run/$APP_NAME

# 6. Ask before removing data and logs
read -p "Do you want to remove all collected logs and telemetry data? [y/N] " remove_data
if [[ "$remove_data" =~ ^[Yy]$ ]]; then
    echo "Removing data and logs..."
    rm -rf /var/log/$APP_NAME
    rm -rf /var/lib/$APP_NAME
else
    echo "Data and logs preserved in /var/lib/$APP_NAME and /var/log/$APP_NAME."
fi

echo "━━━ Uninstallation Complete ━━━"
