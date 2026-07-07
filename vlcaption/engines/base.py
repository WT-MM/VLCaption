"""Shared types for transcription engines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Protocol

from vlcaption.srt import Segment

ProgressCallback = Callable[[int], None]
"""Called with a coarse completion percentage (0-99) as transcription advances."""


@dataclass
class TranscriptionResult:
    """Segments plus the language the engine detected (or was told)."""

    segments: list[Segment]
    language: str


class Engine(Protocol):
    """A loaded speech-to-text engine bound to a specific model."""

    name: str

    def transcribe(self, file_path: str, language: str | None, on_progress: ProgressCallback) -> TranscriptionResult:
        """Transcribe a media file.

        Args:
            file_path: Path to the media file.
            language: ISO 639-1 language hint, or None for auto-detect.
            on_progress: Progress callback; engines that cannot report
                incremental progress may never call it.

        Returns:
            The transcription result.
        """
        ...
