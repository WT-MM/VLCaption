"""Transcription orchestration and thread-safe progress state."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

from vlcaption.engines import create_engine, normalize_model
from vlcaption.engines.base import Engine, TranscriptionResult

logger = logging.getLogger(__name__)

BUSY_STATUSES = frozenset({"loading_model", "transcribing"})


@dataclass
class TranscriptionProgress:
    """Thread-safe transcription progress state.

    Status is one of: idle, loading_model, transcribing, complete, error.
    """

    status: str = "idle"
    percent: int = 0
    srt_path: str = ""
    language: str = ""
    error: str = ""
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def set_loading_model(self) -> None:
        with self._lock:
            self.status = "loading_model"
            self.percent = 0
            self.srt_path = ""
            self.language = ""
            self.error = ""

    def set_started(self) -> None:
        with self._lock:
            self.status = "transcribing"
            self.percent = 0

    def set_progress(self, percent: int) -> None:
        with self._lock:
            self.percent = min(percent, 99)

    def set_language(self, language: str) -> None:
        with self._lock:
            self.language = language

    def set_complete(self, srt_path: str) -> None:
        with self._lock:
            self.status = "complete"
            self.percent = 100
            self.srt_path = srt_path

    def set_error(self, message: str) -> None:
        with self._lock:
            self.status = "error"
            self.error = message

    def set_idle(self) -> None:
        with self._lock:
            self.status = "idle"
            self.percent = 0

    def snapshot(self) -> dict[str, str | int]:
        with self._lock:
            result: dict[str, str | int] = {"status": self.status}
            if self.status == "transcribing":
                result["percent"] = self.percent
            elif self.status == "complete":
                result["srt_path"] = self.srt_path
                result["language"] = self.language
            elif self.status == "error":
                result["message"] = self.error
            return result


class Transcriber:
    """Owns a cached engine and runs transcription jobs one at a time."""

    def __init__(self) -> None:
        self._engine: Engine | None = None
        self._engine_key: str = ""
        self._device: str = "auto"
        self._lock = threading.Lock()
        self.progress = TranscriptionProgress()

    def _get_engine(self, model: str) -> Engine:
        """Create or reuse the engine serving a model choice."""
        key = f"{normalize_model(model)}:{self._device}"
        if self._engine is None or self._engine_key != key:
            self._engine = create_engine(model, device=self._device)
            self._engine_key = key
        return self._engine

    def set_device(self, device: str) -> None:
        """Set the compute device for the faster-whisper fallback (auto, cpu, cuda)."""
        self._device = device

    def is_busy(self) -> bool:
        """Check if a transcription (or its model load) is currently running."""
        return self.progress.status in BUSY_STATUSES

    def transcribe(self, file_path: str, model: str = "auto", language: str | None = None) -> TranscriptionResult:
        """Run transcription and return the result.

        This method is meant to be called from a background thread.

        Args:
            file_path: Path to the media file.
            model: Model choice (see vlcaption.engines.MODEL_CHOICES).
            language: ISO 639-1 language code, or None for auto-detect.

        Returns:
            The transcription result.
        """
        with self._lock:
            self.progress.set_loading_model()
            try:
                engine = self._get_engine(model)
                self.progress.set_started()
                result = engine.transcribe(file_path, language, self.progress.set_progress)
                self.progress.set_language(result.language)
                return result
            except Exception as e:
                logger.exception("Transcription failed")
                self.progress.set_error(str(e))
                raise
