"""Talk to a running VLC instance.

macOS-only for now: uses VLC's AppleScript support. `OpenURL` on a subtitle
file hits VLC's tryAsSubtitle path, which attaches the file to the current
input as a subtitle slave AND auto-selects it — no extension involved.
"""

from __future__ import annotations

import logging
import pathlib
import subprocess
import sys

logger = logging.getLogger(__name__)

_OSASCRIPT_TIMEOUT = 5.0


def _osascript(script: str) -> str | None:
    """Run an AppleScript line, returning stdout or None on any failure."""
    if sys.platform != "darwin":
        return None
    try:
        proc = subprocess.run(
            ["osascript", "-e", script],
            check=False,
            capture_output=True,
            text=True,
            timeout=_OSASCRIPT_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    if proc.returncode != 0:
        logger.debug("osascript failed: %s", proc.stderr.strip())
        return None
    return proc.stdout.strip()


def is_running() -> bool:
    """Check whether VLC is currently running (never launches it)."""
    if sys.platform != "darwin":
        return False
    try:
        return subprocess.run(["pgrep", "-xq", "VLC"], check=False, timeout=_OSASCRIPT_TIMEOUT).returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        return False


def current_item() -> str | None:
    """Absolute path of the media currently playing in VLC, or None."""
    if not is_running():
        return None
    out = _osascript('tell application "VLC" to get path of current item')
    return out or None


def push_subtitle(srt_path: str, media_path: str | None = None) -> bool:
    """Load an SRT into the running VLC input and auto-select it.

    Args:
        srt_path: Path to the subtitle file.
        media_path: If given, push only while this file is still the current
            item, so a subtitle never lands on the wrong video.

    Returns:
        True if the subtitle was pushed.
    """
    if not is_running():
        logger.info("VLC is not running; skipping subtitle push")
        return False
    if media_path is not None and current_item() != media_path:
        logger.info("Current VLC item changed; skipping subtitle push for %s", media_path)
        return False
    uri = pathlib.Path(srt_path).resolve().as_uri()
    ok = _osascript(f'tell application "VLC" to OpenURL "{uri}"') is not None
    if ok:
        logger.info("Pushed subtitles into VLC: %s", srt_path)
    else:
        logger.warning("Failed to push subtitles into VLC: %s", srt_path)
    return ok
