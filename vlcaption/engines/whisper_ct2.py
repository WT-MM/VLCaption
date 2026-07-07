"""Whisper engine via faster-whisper (CTranslate2; CPU-only on macOS)."""

from __future__ import annotations

import logging

from vlcaption.engines.base import ProgressCallback, TranscriptionResult
from vlcaption.srt import Segment

logger = logging.getLogger(__name__)

# faster-whisper resolves these names directly ("turbo" since v1.1.0).
MODEL_NAMES: dict[str, str] = {
    "tiny": "tiny",
    "base": "base",
    "small": "small",
    "medium": "medium",
    "large-v3": "large-v3",
    "turbo": "turbo",
}


class FasterWhisperEngine:
    name = "faster-whisper"

    def __init__(self, size: str, device: str = "auto") -> None:
        from faster_whisper import WhisperModel  # noqa: PLC0415

        model_name = MODEL_NAMES[size]
        logger.info("Loading faster-whisper model: %s (device=%s)", model_name, device)
        self._model = WhisperModel(model_name, device=device, compute_type="auto")
        logger.info("Model loaded: %s", model_name)

    def transcribe(self, file_path: str, language: str | None, on_progress: ProgressCallback) -> TranscriptionResult:
        segments_gen, info = self._model.transcribe(
            file_path,
            beam_size=5,
            language=language,
            condition_on_previous_text=False,
        )
        duration = info.duration if info.duration and info.duration > 0 else 1.0
        detected = info.language or "unknown"
        logger.info("Detected language: %s (duration: %.1fs)", detected, duration)

        segments: list[Segment] = []
        for seg in segments_gen:
            segments.append(Segment(start=seg.start, end=seg.end, text=seg.text))
            on_progress(int((seg.end / duration) * 100))

        return TranscriptionResult(segments=segments, language=detected)
