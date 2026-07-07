"""Whisper engine via mlx-whisper (Apple Silicon, Metal)."""

from __future__ import annotations

import logging

from vlcaption.engines.base import ProgressCallback, TranscriptionResult
from vlcaption.srt import Segment

logger = logging.getLogger(__name__)

MODEL_REPOS: dict[str, str] = {
    "tiny": "mlx-community/whisper-tiny",
    "base": "mlx-community/whisper-base-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
    "turbo": "mlx-community/whisper-large-v3-turbo",
}


class MlxWhisperEngine:
    name = "mlx-whisper"

    def __init__(self, size: str) -> None:
        self._repo = MODEL_REPOS[size]
        # mlx_whisper loads weights lazily on the first transcribe() call;
        # import here so a missing dependency fails at engine creation.
        import mlx_whisper  # noqa: F401, PLC0415

        logger.info("Using mlx-whisper model: %s", self._repo)

    def transcribe(self, file_path: str, language: str | None, on_progress: ProgressCallback) -> TranscriptionResult:
        import mlx_whisper  # noqa: PLC0415

        # condition_on_previous_text=False avoids Whisper's repetition-loop
        # hallucinations on long stretches of music or silence.
        result = mlx_whisper.transcribe(
            file_path,
            path_or_hf_repo=self._repo,
            language=language,
            condition_on_previous_text=False,
        )
        segments = [
            Segment(start=float(seg["start"]), end=float(seg["end"]), text=str(seg["text"]))
            for seg in result["segments"]
        ]
        detected = str(result.get("language") or language or "unknown")
        return TranscriptionResult(segments=segments, language=detected)
