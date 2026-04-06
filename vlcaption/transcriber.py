"""Whisper transcription engine wrapping faster-whisper."""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field

from faster_whisper import WhisperModel  # type: ignore[import-untyped]

from vlcaption.srt import Segment

logger = logging.getLogger(__name__)


@dataclass
class TranscriptionProgress:
    """Thread-safe transcription progress state."""

    status: str = "idle"
    percent: int = 0
    srt_path: str = ""
    language: str = ""
    error: str = ""
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def set_started(self) -> None:
        with self._lock:
            self.status = "transcribing"
            self.percent = 0
            self.srt_path = ""
            self.language = ""
            self.error = ""

    def set_progress(self, percent: int) -> None:
        with self._lock:
            self.percent = min(percent, 99)

    def set_complete(self, srt_path: str, language: str) -> None:
        with self._lock:
            self.status = "complete"
            self.percent = 100
            self.srt_path = srt_path
            self.language = language

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
    """Manages Whisper model and transcription jobs."""

    def __init__(self) -> None:
        self._model: WhisperModel | None = None
        self._model_size: str = ""
        self._device: str = "auto"
        self._lock = threading.Lock()
        self.progress = TranscriptionProgress()

    def _load_model(self, model_size: str) -> None:
        """Load or reload the Whisper model if the size changed."""
        if self._model is not None and self._model_size == model_size:
            return

        logger.info("Loading Whisper model: %s (device=%s)", model_size, self._device)
        self._model = WhisperModel(model_size, device=self._device, compute_type="auto")
        self._model_size = model_size
        logger.info("Model loaded: %s", model_size)

    def set_device(self, device: str) -> None:
        """Set the compute device (auto, cpu, cuda)."""
        self._device = device

    def is_busy(self) -> bool:
        """Check if a transcription is currently running."""
        return self.progress.status == "transcribing"

    def transcribe(self, file_path: str, model_size: str = "base", language: str | None = None) -> list[Segment]:
        """Run transcription and return segments.

        This method is meant to be called from a background thread.

        Args:
            file_path: Path to the media file.
            model_size: Whisper model size (tiny, base, small, medium, large-v3).
            language: ISO 639-1 language code, or None for auto-detect.

        Returns:
            List of transcription segments.
        """
        with self._lock:
            self._load_model(model_size)

            self.progress.set_started()

            try:
                assert self._model is not None
                segments_gen, info = self._model.transcribe(
                    file_path,
                    beam_size=5,
                    language=language,
                )
                duration = info.duration if info.duration and info.duration > 0 else 1.0

                detected_language = info.language or "unknown"
                logger.info("Detected language: %s (duration: %.1fs)", detected_language, duration)

                segments: list[Segment] = []
                for seg in segments_gen:
                    segments.append(Segment(start=seg.start, end=seg.end, text=seg.text))
                    percent = int((seg.end / duration) * 100)
                    self.progress.set_progress(percent)

                return segments

            except Exception as e:
                logger.exception("Transcription failed")
                self.progress.set_error(str(e))
                raise
