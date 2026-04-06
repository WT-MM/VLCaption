"""SRT subtitle file generation."""

import os
import tempfile
from dataclasses import dataclass


@dataclass
class Segment:
    """A single transcription segment with timing."""

    start: float
    end: float
    text: str


def _format_timestamp(seconds: float) -> str:
    """Format seconds as SRT timestamp (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"


def segments_to_srt(segments: list[Segment]) -> str:
    """Convert a list of segments to SRT formatted string."""
    lines: list[str] = []
    for i, seg in enumerate(segments, start=1):
        lines.append(str(i))
        lines.append(f"{_format_timestamp(seg.start)} --> {_format_timestamp(seg.end)}")
        lines.append(seg.text.strip())
        lines.append("")
    return "\n".join(lines)


def write_srt_file(segments: list[Segment], media_path: str) -> str:
    """Write SRT file next to the media file, falling back to a temp directory.

    Args:
        segments: List of transcription segments.
        media_path: Absolute path to the source media file.

    Returns:
        Absolute path to the written SRT file.
    """
    base, _ = os.path.splitext(media_path)
    srt_path = base + ".srt"

    srt_content = segments_to_srt(segments)

    try:
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)
    except OSError:
        # Fall back to temp directory if we can't write next to the media file.
        tmp_dir = tempfile.mkdtemp(prefix="vlcaption_")
        filename = os.path.basename(base) + ".srt"
        srt_path = os.path.join(tmp_dir, filename)
        with open(srt_path, "w", encoding="utf-8") as f:
            f.write(srt_content)

    return srt_path
