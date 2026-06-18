#!/bin/bash
# Exit on error
set -e

echo "=================================================="
echo "      Building OptiFile Desktop for macOS        "
echo "=================================================="

# Ensure proper PATH is loaded for Homebrew/pip if needed
if [ -f /opt/homebrew/bin/brew ]; then
    eval "$(/opt/homebrew/bin/brew shellenv)"
elif [ -f /usr/local/bin/brew ]; then
    eval "$(/usr/local/bin/brew shellenv)"
fi

# 1. Install dependencies
echo "[1/3] Installing and upgrading required packages..."
python3 -m pip install --upgrade pip
python3 -m pip install Pillow pypdf pyinstaller

# 2. Compile application using PyInstaller
echo "[2/3] Compiling app.py into standalone macOS bundle..."

# Locate PyInstaller binary
if [ -f "/Users/aniketmishra/Library/Python/3.9/bin/pyinstaller" ]; then
    PYI_BIN="/Users/aniketmishra/Library/Python/3.9/bin/pyinstaller"
else
    PYI_BIN=$(which pyinstaller || echo "pyinstaller")
fi

echo "Using PyInstaller at: $PYI_BIN"

# Run PyInstaller
"$PYI_BIN" --noconfirm --onedir --windowed --name="OptiFile" --clean app.py

# 3. Verify output
if [ -d "dist/OptiFile.app" ] || [ -f "dist/OptiFile" ]; then
    echo "=================================================="
    echo "🎉 Build Successful!"
    echo "You can find your standalone app at:"
    echo "👉 dist/OptiFile.app"
    echo "=================================================="
else
    echo "❌ Error: Standalone app bundle was not found in 'dist/'"
    exit 1
fi
