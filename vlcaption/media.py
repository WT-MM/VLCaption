"""Media probing and audio extraction via ffmpeg/ffprobe."""

from __future__ import annotations

import logging
import os
import subprocess
import tempfile

logger = logging.getLogger(__name__)

_FFMPEG_TIMEOUT = 120.0


def media_duration(path: str) -> float | None:
    """Duration of a media file in seconds, or None if it can't be probed."""
    try:
        proc = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
            check=False,
            capture_output=True,
            text=True,
            timeout=_FFMPEG_TIMEOUT,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    try:
        return float(proc.stdout.strip())
    except ValueError:
        return None


def extract_audio_segment(path: str, start: float, duration: float) -> str:
    """Extract a segment as a 16 kHz mono WAV; caller deletes the temp file.

    Raises:
        RuntimeError: If ffmpeg fails.
    """
    fd, wav_path = tempfile.mkstemp(prefix="vlcaption_", suffix=".wav")
    os.close(fd)
    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-ss",
        f"{start:.3f}",
        "-t",
        f"{duration:.3f}",
        "-i",
        path,
        "-vn",
        "-ac",
        "1",
        "-ar",
        "16000",
        wav_path,
    ]
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True, timeout=_FFMPEG_TIMEOUT)
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as e:
        if os.path.exists(wav_path):
            os.unlink(wav_path)
        stderr = getattr(e, "stderr", "") or ""
        raise RuntimeError(f"ffmpeg segment extraction failed: {stderr.strip()}") from e
    return wav_path
