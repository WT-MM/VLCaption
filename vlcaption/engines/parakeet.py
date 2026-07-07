"""NVIDIA Parakeet TDT engine via parakeet-mlx (Apple Silicon only)."""

from __future__ import annotations

import logging

from vlcaption.engines.base import ProgressCallback, TranscriptionResult
from vlcaption.srt import Segment

logger = logging.getLogger(__name__)

MODEL_ID = "mlx-community/parakeet-tdt-0.6b-v3"

# Chunked decoding keeps memory flat on movie-length files; 15s overlap is
# the parakeet-mlx default merge window.
CHUNK_SECONDS = 120.0
OVERLAP_SECONDS = 15.0


class ParakeetEngine:
    name = "parakeet"

    def __init__(self) -> None:
        from parakeet_mlx import from_pretrained  # noqa: PLC0415

        logger.info("Loading Parakeet model: %s", MODEL_ID)
        self._model = from_pretrained(MODEL_ID)
        logger.info("Model loaded: %s", MODEL_ID)

    def transcribe(self, file_path: str, language: str | None, on_progress: ProgressCallback) -> TranscriptionResult:
        # Parakeet v3 language-IDs among its 25 languages internally; there is
        # no way to force a language, so a hint is only echoed back.
        def chunk_callback(current: float, total: float) -> None:
            if total > 0:
                on_progress(int(current / total * 100))

        result = self._model.transcribe(
            file_path,
            chunk_duration=CHUNK_SECONDS,
            overlap_duration=OVERLAP_SECONDS,
            chunk_callback=chunk_callback,
        )
        segments = [Segment(start=s.start, end=s.end, text=s.text) for s in result.sentences]
        return TranscriptionResult(segments=segments, language=language or "auto")
