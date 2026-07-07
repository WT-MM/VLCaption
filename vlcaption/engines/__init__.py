"""Engine registry: maps model-choice strings to loaded engines.

Model choices:
    - "auto": best available engine — Parakeet if installed (Apple Silicon),
      else Whisper turbo on the best available runtime.
    - "parakeet": NVIDIA Parakeet TDT 0.6B v3 via parakeet-mlx.
    - Whisper sizes ("tiny", "base", "small", "medium", "large-v3", "turbo"),
      optionally prefixed "whisper-": served by mlx-whisper when installed,
      falling back to faster-whisper (CPU).
"""

from __future__ import annotations

import importlib.util
import logging
import platform
import sys

from vlcaption.engines.base import Engine, ProgressCallback, TranscriptionResult

logger = logging.getLogger(__name__)

WHISPER_SIZES = ("tiny", "base", "small", "medium", "large-v3", "turbo")

MODEL_CHOICES: frozenset[str] = frozenset(
    ("auto", "coreml", "coreml-fast", "parakeet", *WHISPER_SIZES, *(f"whisper-{size}" for size in WHISPER_SIZES))
)


def _has_module(name: str) -> bool:
    return importlib.util.find_spec(name) is not None


def _is_apple_silicon() -> bool:
    return sys.platform == "darwin" and platform.machine() == "arm64"


def _has_mlx_module(name: str) -> bool:
    """MLX runs only on Apple-Silicon GPUs; never attempt it elsewhere."""
    return _is_apple_silicon() and _has_module(name)


def normalize_model(model: str) -> str:
    """Validate a model choice and strip the optional "whisper-" prefix.

    Raises:
        ValueError: If the choice is not in MODEL_CHOICES.
    """
    if model not in MODEL_CHOICES:
        raise ValueError(f"model must be one of: {', '.join(sorted(MODEL_CHOICES))}")
    return model.removeprefix("whisper-") if model.startswith("whisper-") else model


def create_engine(model: str, device: str = "auto") -> Engine:
    """Create the engine serving a model choice.

    Args:
        model: One of MODEL_CHOICES.
        device: Compute device for the faster-whisper fallback (auto, cpu, cuda).

    Returns:
        A loaded engine.

    Raises:
        ValueError: On an unknown model choice.
        RuntimeError: If the requested engine's dependencies are missing.
    """
    model = normalize_model(model)

    if model == "auto":
        if _is_apple_silicon() and _has_module("silicon_asr"):
            model = "coreml"
        elif _has_mlx_module("parakeet_mlx"):
            model = "parakeet"
        else:
            model = "turbo"

    if model in ("coreml", "coreml-fast"):
        if not (_is_apple_silicon() and _has_module("silicon_asr")):
            raise RuntimeError(
                "coreml engines need Apple Silicon with silicon-asr installed "
                "(pip install 'vlcaption[mlx]'); use a whisper model on this machine"
            )
        from vlcaption.engines.silicon import SiliconEngine  # noqa: PLC0415

        logger.info("Engine: silicon-asr (%s) on the Apple Neural Engine", model)
        return SiliconEngine(model)

    if model == "parakeet":
        if not _has_mlx_module("parakeet_mlx"):
            raise RuntimeError(
                "Parakeet needs Apple Silicon with parakeet-mlx installed "
                "(pip install 'vlcaption[mlx]'); use a whisper model on this machine"
            )
        from vlcaption.engines.parakeet import ParakeetEngine  # noqa: PLC0415

        logger.info("Engine: parakeet-mlx on the Apple GPU")
        return ParakeetEngine()

    if _has_mlx_module("mlx_whisper"):
        from vlcaption.engines.whisper_mlx import MlxWhisperEngine  # noqa: PLC0415

        logger.info("Engine: mlx-whisper (%s) on the Apple GPU", model)
        return MlxWhisperEngine(model)

    if _has_module("faster_whisper"):
        from vlcaption.engines.whisper_ct2 import FasterWhisperEngine  # noqa: PLC0415

        # CTranslate2's device/compute auto-detection picks CUDA + float16
        # on NVIDIA machines and int8 on CPU.
        logger.info("Engine: faster-whisper (%s, device=%s)", model, device)
        return FasterWhisperEngine(model, device=device)

    raise RuntimeError("No transcription engine installed. Install with: pip install 'vlcaption[mlx]'")
