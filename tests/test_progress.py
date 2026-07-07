"""Tests for the transcription progress state machine."""

from vlcaption.transcriber import TranscriptionProgress


def test_loading_model_then_started_then_complete() -> None:
    progress = TranscriptionProgress()
    assert progress.snapshot() == {"status": "idle"}

    progress.set_loading_model()
    assert progress.snapshot() == {"status": "loading_model"}

    progress.set_started()
    assert progress.snapshot() == {"status": "transcribing", "percent": 0}

    progress.set_progress(42)
    assert progress.snapshot()["percent"] == 42

    progress.set_language("en")
    progress.set_complete("/tmp/movie.srt")
    snap = progress.snapshot()
    assert snap == {"status": "complete", "srt_path": "/tmp/movie.srt", "language": "en"}


def test_language_survives_from_detection_to_completion() -> None:
    progress = TranscriptionProgress()
    progress.set_loading_model()
    progress.set_started()
    progress.set_language("fr")
    progress.set_complete("/tmp/film.srt")
    assert progress.snapshot()["language"] == "fr"


def test_progress_capped_at_99_until_complete() -> None:
    progress = TranscriptionProgress()
    progress.set_started()
    progress.set_progress(150)
    assert progress.snapshot()["percent"] == 99


def test_error_snapshot() -> None:
    progress = TranscriptionProgress()
    progress.set_started()
    progress.set_error("boom")
    assert progress.snapshot() == {"status": "error", "message": "boom"}
