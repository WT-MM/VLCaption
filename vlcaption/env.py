"""Runtime environment fixes for GUI-launched processes."""

from __future__ import annotations

import logging
import os
import shutil

logger = logging.getLogger(__name__)

# Directories that GUI-app environments commonly omit from PATH.
_TOOL_DIRS = ("/opt/homebrew/bin", "/usr/local/bin")


def ensure_tool_paths() -> None:
    """Prepend common tool directories that GUI-launched processes lack.

    When VLC launches the server, the process inherits VLC's minimal PATH,
    which on macOS omits Homebrew — so ffmpeg (used by the MLX engines to
    decode audio) looks missing even when installed. Call this at every
    entry point before any engine runs.
    """
    path = os.environ.get("PATH", "")
    parts = path.split(os.pathsep) if path else []
    missing = [d for d in _TOOL_DIRS if d not in parts and os.path.isdir(d)]
    if missing:
        os.environ["PATH"] = os.pathsep.join(missing + parts)
        logger.debug("Prepended to PATH: %s", ", ".join(missing))

    if shutil.which("ffmpeg") is None:
        logger.warning(
            "ffmpeg not found on PATH; the Parakeet and mlx-whisper engines "
            "need it to decode audio (brew install ffmpeg)"
        )
