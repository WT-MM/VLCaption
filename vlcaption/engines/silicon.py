"""Engine backed by silicon-asr's CoreML/ANE runners (Apple Silicon).

Runs Parakeet on the Apple Neural Engine via the silicon-asr package —
measured ~1.7x faster than parakeet-mlx at matched quality, at much lower
power. https://github.com/WT-MM/silicon-asr
"""

from __future__ import annotations

import logging

from vlcaption.engines.base import ProgressCallback, TranscriptionResult
from vlcaption.srt import Segment

logger = logging.getLogger(__name__)

RUNNER_FOR_MODEL = {
    "coreml": "parakeet-coreml",
    "coreml-fast": "parakeet-ctc-coreml",
}


class SiliconEngine:
    name = "silicon-asr"

    def __init__(self, model: str = "coreml") -> None:
        from silicon_asr.runners import create_runner  # noqa: PLC0415

        self._runner = create_runner(RUNNER_FOR_MODEL[model])
        logger.info("Loaded silicon-asr runner: %s", self._runner.name)

    def transcribe(self, file_path: str, language: str | None, on_progress: ProgressCallback) -> TranscriptionResult:
        # silicon-asr exposes no incremental progress; jobs are fast enough
        # (~140-1000x realtime) that the status gap is seconds, not minutes.
        result = self._runner.transcribe_file(file_path)
        segments = [Segment(start=s.start, end=s.end, text=s.text) for s in result.segments]
        return TranscriptionResult(segments=segments, language=language or "auto")
