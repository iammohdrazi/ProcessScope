#!/bin/bash
# ============================================================
# ProcessScope — Installation Script
# ============================================================
# Installs the packaged tar.gz onto a target Linux system.
# ============================================================

set -e

# Must be run as root
if [ "$EUID" -ne 0 ]; then
  echo "❌ Error: Please run as root (e.g., sudo ./install.sh)"
  exit 1
fi

APP_NAME="processscope"
echo "━━━ Installing $APP_NAME ━━━"

# 1. Create standard FHS directories
echo "Creating system directories..."
mkdir -p /opt/$APP_NAME/bin
mkdir -p /opt/$APP_NAME/lib
mkdir -p /opt/$APP_NAME/share/doc
mkdir -p /opt/$APP_NAME/plugins
mkdir -p /etc/$APP_NAME
mkdir -p /var/log/$APP_NAME
mkdir -p /var/lib/$APP_NAME/db
mkdir -p /var/lib/$APP_NAME/sessions
mkdir -p /run/$APP_NAME

# Set specific permissions for secure directories
chmod 750 /var/log/$APP_NAME
chmod 750 /var/lib/$APP_NAME
chmod 700 /var/lib/$APP_NAME/db
chmod 700 /var/lib/$APP_NAME/sessions

# 2. Copy files from package layout
echo "Copying application files..."
cp -a opt/$APP_NAME/* /opt/$APP_NAME/
cp -a etc/$APP_NAME/* /etc/$APP_NAME/

# 3. Set up Python virtual environment
echo "Setting up Python virtual environment..."
python3 -m venv /opt/$APP_NAME/venv
/opt/$APP_NAME/venv/bin/pip install --upgrade pip setuptools wheel

# 4. Install the wheel package
echo "Installing Python package..."
WHEEL_FILE=$(ls /opt/$APP_NAME/lib/$APP_NAME-*.whl 2>/dev/null | head -n 1)
if [ -z "$WHEEL_FILE" ]; then
    echo "❌ Error: Could not find .whl package in /opt/$APP_NAME/lib/"
    exit 1
fi
/opt/$APP_NAME/venv/bin/pip install "$WHEEL_FILE"

# 5. Create CLI symlink
ln -sf /opt/$APP_NAME/venv/bin/processscope /usr/local/bin/processscope

# 6. Install systemd service
echo "Configuring systemd service..."
if [ -d /usr/lib/systemd/system ]; then
    cp processscope.service /usr/lib/systemd/system/
elif [ -d /etc/systemd/system ]; then
    cp processscope.service /etc/systemd/system/
else
    echo "⚠️ Warning: systemd unit directory not found. Service not installed."
fi

systemctl daemon-reload
systemctl enable processscope

# 7. Install logrotate
if [ -d /etc/logrotate.d ]; then
    echo "Configuring logrotate..."
    cp processscope /etc/logrotate.d/$APP_NAME
fi

# 8. Start the service
echo "Starting service..."
systemctl start processscope

echo "━━━ Installation Complete ━━━"
echo "✓ $APP_NAME has been installed and started."
echo "✓ CLI is available as: processscope"
echo "✓ Logs are available via: journalctl -u processscope"
echo "✓ Dashboard is running on port 9876 (if configured)"
echo ""
echo "Try running: processscope status"
