#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

echo "=== VLCaption Installer ==="
echo ""

# 1. Install Python package (always in a venv)
# On Apple Silicon, include the MLX engines (Parakeet + mlx-whisper) —
# they are ~10-30x faster than the CPU faster-whisper fallback.
# (plain strings, not arrays: macOS bash 3.2 + set -u chokes on empty arrays)
EXTRA_ARGS=""
PIP_EXTRAS=""
if [ "$(uname -s)" = "Darwin" ] && [ "$(uname -m)" = "arm64" ]; then
    EXTRA_ARGS="--extra mlx"
    PIP_EXTRAS="[mlx]"
fi

echo "Installing Python package..."
if command -v uv &> /dev/null; then
    # shellcheck disable=SC2086
    (cd "$SCRIPT_DIR" && uv sync $EXTRA_ARGS)
    echo "  Done (uv sync)."
else
    echo "  uv not found, using pip with venv..."
    if [ ! -d "$SCRIPT_DIR/.venv" ]; then
        python3 -m venv "$SCRIPT_DIR/.venv"
        echo "  Created venv at $SCRIPT_DIR/.venv"
    fi
    "$SCRIPT_DIR/.venv/bin/pip" install -e "$SCRIPT_DIR$PIP_EXTRAS"
    echo "  Done (pip install in venv)."
fi
echo ""

# 2. Install the VLC extension + server launcher
"$SCRIPT_DIR/.venv/bin/vlcaption-install"
echo ""

echo "=== Installation complete ==="
echo ""
echo "Usage (VLC extension):"
echo "  1. Open VLC and play a media file"
echo "  2. Go to VLC > Extensions > VLCaption - Auto Subtitles"
echo "  3. Select a model and click 'Generate Subtitles'"
echo ""
echo "Usage (watch mode, no clicking):"
echo "  $SCRIPT_DIR/.venv/bin/vlcaption watch"
echo "  Then play any video in VLC - subtitles appear automatically."
echo ""
echo "The server starts on demand and exits a couple of minutes after"
echo "VLC quits (or after 30 idle minutes)."
