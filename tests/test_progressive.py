"""Tests for progressive-mode planning and media helpers."""

import os
import shutil
import subprocess

import pytest

from vlcaption.media import extract_audio_segment, media_duration
from vlcaption.watcher import quick_pass_window


def test_short_files_skip_quick_pass() -> None:
    assert quick_pass_window(120.0, playhead=0.0) is None
    assert quick_pass_window(599.0, playhead=50.0) is None


def test_unknown_duration_skips_quick_pass() -> None:
    assert quick_pass_window(None, playhead=0.0) is None


def test_long_file_from_start() -> None:
    assert quick_pass_window(7200.0, playhead=0.0) == (0.0, 300.0)


def test_window_starts_behind_playhead() -> None:
    start, length = quick_pass_window(7200.0, playhead=1000.0)  # type: ignore[misc]
    assert start == 985.0  # 15s lead
    assert length == 300.0


def test_window_clamped_to_file_end() -> None:
    start, length = quick_pass_window(1100.0, playhead=1000.0)  # type: ignore[misc]
    assert start == 985.0
    assert start + length == 1100.0


def test_playhead_past_end_skips() -> None:
    assert quick_pass_window(1000.0, playhead=1500.0) is None


def test_none_playhead_treated_as_start() -> None:
    assert quick_pass_window(7200.0, playhead=None) == (0.0, 300.0)


@pytest.mark.slow
@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_media_duration_and_segment_extraction(tmp_path: "os.PathLike[str]") -> None:
    clip = os.path.join(tmp_path, "clip.mp4")
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=4",
            "-c:a",
            "aac",
            clip,
        ],
        check=True,
    )

    duration = media_duration(clip)
    assert duration is not None and 3.5 < duration < 4.5

    wav = extract_audio_segment(clip, start=1.0, duration=2.0)
    try:
        wav_duration = media_duration(wav)
        assert wav_duration is not None and 1.8 < wav_duration < 2.2
    finally:
        os.unlink(wav)


def test_media_duration_missing_file() -> None:
    assert media_duration("/nonexistent/movie.mp4") is None
