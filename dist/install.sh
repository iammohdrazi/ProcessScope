#!/bin/bash
# ============================================================
# ProcessScope — Installation Script
# ============================================================
# Installs ProcessScope and registers it with the native
# package manager for easy removal (apt/dnf/zypper).
# ============================================================

set -e

APP_NAME="processscope"
VERSION="${VERSION:-0.1.0}"
TOTAL_STEPS=10
CURRENT_STEP=0

# Must be run as root
if [ "$EUID" -ne 0 ]; then
  echo "Error: Please run as root (e.g., sudo ./install.sh)"
  exit 1
fi

step() {
    CURRENT_STEP=$((CURRENT_STEP + 1))
    MESSAGE="$1"
    echo -e "  [$CURRENT_STEP/$TOTAL_STEPS] $MESSAGE"
    logger -t $APP_NAME -p daemon.info "Installation Step $CURRENT_STEP/$TOTAL_STEPS: $MESSAGE"
}

check_ok() {
    echo -e "        \033[1;32mOK\033[0m"
}

echo "ProcessScope v$VERSION — Installing"
echo ""

# Allow skipping systemd operations for container testing
SKIP_SYSTEMD="${SKIP_SYSTEMD:-false}"

# 1. Check system requirements
step "Checking system requirements..."
if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is not installed on this system."
    exit 1
fi

PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "0.0")
if awk -v ver="$PY_VER" 'BEGIN { if (ver < 3.10) exit 1; exit 0 }'; then
    echo "        Python $PY_VER (>= 3.10)"
    check_ok
else
    echo "Error: Python 3.10 or higher is required. Found $PY_VER."
    exit 1
fi

# 2. Uninstall previous version if exists
step "Removing previous installation (if any)..."

# Ensure uninstall.sh exists so prerm doesn't fail
if [ -d /opt/$APP_NAME ] && [ ! -f /opt/$APP_NAME/scripts/uninstall.sh ]; then
    mkdir -p /opt/$APP_NAME/scripts
    echo "#!/bin/bash" > /opt/$APP_NAME/scripts/uninstall.sh
    echo "exit 0" >> /opt/$APP_NAME/scripts/uninstall.sh
    chmod +x /opt/$APP_NAME/scripts/uninstall.sh
fi

if command -v dpkg >/dev/null 2>&1 && dpkg -l | grep -q "^ii  $APP_NAME "; then
    apt-get remove -y $APP_NAME >/dev/null 2>&1 || dpkg --remove --force-all $APP_NAME >/dev/null 2>&1
elif command -v rpm >/dev/null 2>&1 && rpm -q $APP_NAME >/dev/null 2>&1; then
    if command -v dnf >/dev/null 2>&1; then
        dnf remove -y $APP_NAME >/dev/null 2>&1 || true
    elif command -v zypper >/dev/null 2>&1; then
        zypper remove -y $APP_NAME >/dev/null 2>&1 || true
    else
        rpm -e $APP_NAME >/dev/null 2>&1 || true
    fi
elif [ -f /opt/$APP_NAME/scripts/uninstall.sh ]; then
    /opt/$APP_NAME/scripts/uninstall.sh >/dev/null 2>&1 || true
fi
check_ok

# 3. Create standard FHS directories
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

chmod 750 /var/log/$APP_NAME
chmod 750 /var/lib/$APP_NAME
chmod 700 /var/lib/$APP_NAME/db
chmod 700 /var/lib/$APP_NAME/sessions
check_ok

# 4. Copy files from package layout
step "Copying application files..."
cp -a opt/$APP_NAME/* /opt/$APP_NAME/
cp -a etc/$APP_NAME/* /etc/$APP_NAME/
check_ok

# 5. Set up Python virtual environment
step "Setting up Python virtual environment..."
python3 -m venv /opt/$APP_NAME/venv
/opt/$APP_NAME/venv/bin/pip install --upgrade pip setuptools wheel > /dev/null 2>&1
check_ok

# 6. Install the wheel package
step "Installing Python package..."
WHEEL_FILE=$(ls /opt/$APP_NAME/lib/$APP_NAME-*.whl 2>/dev/null | head -n 1)
if [ -z "$WHEEL_FILE" ]; then
    echo "Error: Could not find .whl package in /opt/$APP_NAME/lib/"
    exit 1
fi
/opt/$APP_NAME/venv/bin/pip install "$WHEEL_FILE" > /dev/null 2>&1
ln -sf /opt/$APP_NAME/venv/bin/processscope /usr/local/bin/processscope
check_ok

# 7. Install systemd service
step "Configuring systemd service..."
if [ "$SKIP_SYSTEMD" = "true" ]; then
    echo "        Skipping systemd (container mode)"
    check_ok
else
    if [ -d /usr/lib/systemd/system ]; then
        cp processscope.service /usr/lib/systemd/system/
    elif [ -d /etc/systemd/system ]; then
        cp processscope.service /etc/systemd/system/
    fi
    systemctl daemon-reload
    systemctl enable processscope > /dev/null 2>&1
    check_ok
fi

# 8. Install logrotate
step "Configuring logrotate..."
if [ -d /etc/logrotate.d ]; then
    cp processscope /etc/logrotate.d/$APP_NAME
fi
check_ok

# 9. Registering with Package Manager
step "Registering package manager uninstaller..."

# Write uninstall script that the package manager will call
mkdir -p /opt/$APP_NAME/scripts
cat << 'EOF' > /opt/$APP_NAME/scripts/uninstall.sh
#!/bin/bash
# Change to a safe directory to avoid getcwd() errors
cd /tmp || cd /root || true

systemctl stop processscope || true
systemctl disable processscope || true
rm -f /usr/lib/systemd/system/processscope.service
rm -f /etc/systemd/system/processscope.service
systemctl daemon-reload || true
systemctl reset-failed processscope >/dev/null 2>&1 || true
rm -f /etc/logrotate.d/processscope
rm -f /usr/local/bin/processscope
rm -rf /opt/processscope
rm -rf /etc/processscope
rm -rf /run/processscope
echo "ProcessScope binaries removed. To remove data, run: rm -rf /var/lib/processscope /var/log/processscope"
EOF
chmod +x /opt/$APP_NAME/scripts/uninstall.sh

if command -v dpkg >/dev/null 2>&1; then
    # Debian/Ubuntu
    cat << EOF > /tmp/processscope-control
Package: processscope
Version: $VERSION
Section: admin
Priority: optional
Architecture: all
Maintainer: ProcessScope Team <team@processscope.dev>
Description: Linux Process Observability Platform
EOF
cat << 'EOF' > /tmp/processscope-prerm
#!/bin/bash
if [ "$1" = "remove" ] || [ "$1" = "purge" ]; then
    /opt/processscope/scripts/uninstall.sh || true
fi
EOF
    chmod +x /tmp/processscope-prerm
    
    mkdir -p /tmp/ps_deb/DEBIAN
    mv /tmp/processscope-control /tmp/ps_deb/DEBIAN/control
    mv /tmp/processscope-prerm /tmp/ps_deb/DEBIAN/prerm
    
    dpkg-deb --build /tmp/ps_deb /tmp/processscope_dummy.deb > /dev/null 2>&1
    dpkg -i /tmp/processscope_dummy.deb > /dev/null 2>&1
    rm -rf /tmp/ps_deb /tmp/processscope_dummy.deb
    PKG_MGR="apt remove processscope"

elif command -v rpm >/dev/null 2>&1; then
    # RHEL/SLES
    if command -v rpmbuild >/dev/null 2>&1; then
        cat << EOF > /tmp/processscope.spec
Name:           processscope
Version:        $VERSION
Release:        1
Summary:        Linux Process Observability Platform
License:        Apache-2.0
BuildArch:      noarch
%description
Linux Process Observability Platform.
%preun
/opt/processscope/scripts/uninstall.sh
EOF
        rpmbuild -bb /tmp/processscope.spec --define "_topdir /tmp/ps_rpm" > /dev/null 2>&1
        rpm -Uvh /tmp/ps_rpm/RPMS/noarch/processscope*.rpm --force > /dev/null 2>&1
        rm -rf /tmp/ps_rpm /tmp/processscope.spec
    else
        echo "rpmbuild not found, skipping RPM registration. Uninstallation will require manual cleanup."
    fi
    
    if command -v dnf >/dev/null 2>&1; then
        PKG_MGR="dnf remove processscope"
    elif command -v zypper >/dev/null 2>&1; then
        PKG_MGR="zypper remove processscope"
    else
        PKG_MGR="rpm -e processscope"
    fi
else
    PKG_MGR="rm -rf /opt/processscope"
fi
check_ok

# 10. Start the service
step "Starting the daemon service..."
if [ "$SKIP_SYSTEMD" = "true" ]; then
    echo "        Skipping service start (container mode)"
    check_ok
else
    systemctl start processscope
    check_ok
fi


# --- Finish & Display Info ---
PRIMARY_IP=$(ip route get 1.1.1.1 2>/dev/null | grep -oP 'src \K\S+' || hostname -I | awk '{print $1}')
if [ -z "$PRIMARY_IP" ]; then
    PRIMARY_IP="localhost"
fi

echo ""
echo "  Installation Complete"
echo "  ---"
echo "  CLI:        processscope"
echo "  Logs:       journalctl -u processscope"
echo "  Log files:  /var/log/processscope/"
echo "  Data:       /var/lib/processscope/"
echo "  Dashboard:  http://$PRIMARY_IP:9876"
echo "  Uninstall:  $PKG_MGR"
echo ""
echo "  Try: processscope status"
