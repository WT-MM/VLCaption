#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LUA_SRC="$SCRIPT_DIR/extension/vlcaption.lua"

echo "=== VLCaption Installer ==="
echo ""

# 1. Detect OS and set VLC extensions directory
case "$(uname -s)" in
    Darwin)
        VLC_EXT_DIR="$HOME/Library/Application Support/org.videolan.vlc/lua/extensions"
        ;;
    Linux)
        VLC_EXT_DIR="$HOME/.local/share/vlc/lua/extensions"
        ;;
    MINGW*|MSYS*|CYGWIN*)
        VLC_EXT_DIR="$APPDATA/vlc/lua/extensions"
        ;;
    *)
        echo "Warning: Unknown OS. Please manually copy vlcaption.lua to your VLC extensions directory."
        VLC_EXT_DIR=""
        ;;
esac

# 2. Install Python package
echo "Installing Python package..."
if command -v uv &> /dev/null; then
    uv sync
    echo "  Done (uv sync)."
else
    echo "  uv not found. Install it: https://docs.astral.sh/uv/getting-started/installation/"
    echo "  Falling back to pip..."
    pip install -e .
    echo "  Done (pip install)."
fi
echo ""

# 3. Install Lua extension
if [ -n "$VLC_EXT_DIR" ]; then
    echo "Installing VLC Lua extension..."
    mkdir -p "$VLC_EXT_DIR"
    cp "$LUA_SRC" "$VLC_EXT_DIR/vlcaption.lua"
    echo "  Installed to: $VLC_EXT_DIR/vlcaption.lua"
else
    echo "Skipping VLC extension install (unknown OS)."
    echo "Please copy extension/vlcaption.lua to your VLC extensions directory."
fi
echo ""

echo "=== Installation complete ==="
echo ""
echo "Usage:"
echo "  1. Open VLC and play a media file"
echo "  2. Go to View > VLCaption - Auto Subtitles"
echo "  3. Select a model and click 'Generate Subtitles'"
echo ""
echo "The server starts automatically when you generate subtitles."
echo "It shuts down when you close VLC."
