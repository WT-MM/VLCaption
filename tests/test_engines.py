"""Tests for the engine registry."""

import pytest

from vlcaption.engines import MODEL_CHOICES, normalize_model


def test_model_choices_include_auto_and_coreml() -> None:
    assert "auto" in MODEL_CHOICES
    assert "coreml" in MODEL_CHOICES
    assert "coreml-fast" in MODEL_CHOICES
    assert "parakeet" in MODEL_CHOICES


def test_model_choices_accept_bare_and_prefixed_whisper_sizes() -> None:
    assert "base" in MODEL_CHOICES
    assert "whisper-base" in MODEL_CHOICES
    assert "turbo" in MODEL_CHOICES
    assert "whisper-large-v3" in MODEL_CHOICES


def test_normalize_model_strips_whisper_prefix() -> None:
    assert normalize_model("whisper-base") == "base"
    assert normalize_model("base") == "base"
    assert normalize_model("auto") == "auto"
    assert normalize_model("parakeet") == "parakeet"


def test_normalize_model_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="model must be one of"):
        normalize_model("large-v2")
