#!/bin/bash
# ============================================================
# ProcessScope — Installation Script
# ============================================================
# Installs the packaged tar.gz onto a target Linux system.
# ============================================================

set -e

APP_NAME="processscope"
TOTAL_STEPS=8
CURRENT_STEP=0

# Must be run as root
if [ "$EUID" -ne 0 ]; then
  echo "❌ Error: Please run as root (e.g., sudo ./install.sh)"
  exit 1
fi

# Function to show progress and log to journalctl
step() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    MESSAGE="$1"
    
    # Calculate percentage
    PERCENT=$((CURRENT_STEP * 100 / TOTAL_STEPS))
    
    # Create progress bar string [#####     ]
    FILLED=$((PERCENT / 5))
    EMPTY=$((20 - FILLED))
    BAR=$(printf "%${FILLED}s" | tr ' ' '#')
    SPACE=$(printf "%${EMPTY}s" | tr ' ' '-')
    
    # Print to console
    echo -e "\n\033[1;36m[$BAR$SPACE] ${PERCENT}%\033[0m — \033[1m$MESSAGE\033[0m"
    
    # Log to systemd journal
    logger -t $APP_NAME -p daemon.info "Installation Step $CURRENT_STEP/$TOTAL_STEPS: $MESSAGE"
}

echo "━━━ Installing $APP_NAME ━━━"

# 1. Check system requirements
step "Checking system requirements..."
if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Error: python3 is not installed on this system."
    exit 1
fi

PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
if awk -v ver="$PY_VER" 'BEGIN { if (ver < 3.10) exit 1; exit 0 }'; then
    echo "  ✓ Python version is $PY_VER (>= 3.10)"
else
    echo "❌ Error: Python 3.10 or higher is required. Found $PY_VER."
    exit 1
fi

# 2. Create standard FHS directories
step "Creating system directories..."
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

# 3. Copy files from package layout
step "Copying application files..."
cp -a opt/$APP_NAME/* /opt/$APP_NAME/
cp -a etc/$APP_NAME/* /etc/$APP_NAME/

# 4. Set up Python virtual environment
step "Setting up Python virtual environment..."
python3 -m venv /opt/$APP_NAME/venv
/opt/$APP_NAME/venv/bin/pip install --upgrade pip setuptools wheel > /dev/null

# 5. Install the wheel package
step "Installing Python package..."
WHEEL_FILE=$(ls /opt/$APP_NAME/lib/$APP_NAME-*.whl 2>/dev/null | head -n 1)
if [ -z "$WHEEL_FILE" ]; then
    echo "❌ Error: Could not find .whl package in /opt/$APP_NAME/lib/"
    exit 1
fi
/opt/$APP_NAME/venv/bin/pip install "$WHEEL_FILE" > /dev/null

# Create CLI symlink
ln -sf /opt/$APP_NAME/venv/bin/processscope /usr/local/bin/processscope

# 6. Install systemd service
step "Configuring systemd service..."
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
step "Configuring logrotate..."
if [ -d /etc/logrotate.d ]; then
    cp processscope /etc/logrotate.d/$APP_NAME
fi

# 8. Start the service
step "Starting the daemon service..."
systemctl start processscope
logger -t $APP_NAME -p daemon.info "Installation completed successfully. Service started."


# --- Finish & Display Info ---
echo -e "\n\033[1;32m━━━ Installation Complete ━━━\033[0m"

# Dynamically determine the primary IP address (ignoring localhosts, finding default route)
PRIMARY_IP=$(ip route get 1.1.1.1 2>/dev/null | grep -oP 'src \K\S+' || hostname -I | awk '{print $1}')
if [ -z "$PRIMARY_IP" ]; then
    PRIMARY_IP="localhost"
fi

echo "✓ $APP_NAME has been installed and started."
echo "✓ CLI is available as: processscope"
echo "✓ Logs are available via: journalctl -u processscope"
echo "✓ Application Logs stored at: /var/log/$APP_NAME/"
echo "✓ Telemetry Database stored at: /var/lib/$APP_NAME/"
echo ""
echo -e "\033[1;35m🌐 Access the Dashboard at:\033[0m \033[4;34mhttp://$PRIMARY_IP:9876\033[0m"
echo ""
echo "Try running: processscope status"
