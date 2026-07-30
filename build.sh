#!/bin/bash
# ============================================================
# ProcessScope — Build Script
# ============================================================
# This script installs required build tools and packages the
# application into a redistributable tar.gz archive.
# ============================================================

set -e

echo "━━━ ProcessScope Build Script ━━━"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# 1. Check and install system requirements (Ubuntu/Debian example)
echo "1. Checking build dependencies..."
MISSING_PKGS=""

if ! command_exists python3; then MISSING_PKGS="$MISSING_PKGS python3"; fi
if ! command_exists npm; then MISSING_PKGS="$MISSING_PKGS npm nodejs"; fi
if ! command_exists make; then MISSING_PKGS="$MISSING_PKGS make"; fi

# Ensure python3-venv and python3-pip are available
if command_exists python3; then
    if ! python3 -c "import venv" 2>/dev/null; then MISSING_PKGS="$MISSING_PKGS python3-venv"; fi
    if ! python3 -m pip --version 2>/dev/null; then MISSING_PKGS="$MISSING_PKGS python3-pip"; fi
fi

if [ -n "$MISSING_PKGS" ]; then
    echo "Missing dependencies:$MISSING_PKGS"
    if command_exists apt-get; then
        echo "Attempting to install with apt-get (requires sudo)..."
        sudo apt-get update
        sudo apt-get install -y $MISSING_PKGS
    elif command_exists dnf; then
        echo "Attempting to install with dnf (requires sudo)..."
        sudo dnf install -y $MISSING_PKGS
    else
        echo "Please install the following manually and re-run: $MISSING_PKGS"
        exit 1
    fi
else
    echo "✓ All system dependencies satisfied."
fi

# 2. Run the make pipeline
echo "2. Starting build pipeline..."
make clean
make package-tar

echo "━━━ Build Complete ━━━"
echo "Your redistributable package is located in:"
ls -lh dist/output/*.tar.gz
echo ""
echo "To install on the server:"
echo "1. Copy the tar.gz file to the server."
echo "2. Extract it: tar -xzf processscope-*.tar.gz"
echo "3. Run the installer: sudo ./processscope-*/install.sh"
