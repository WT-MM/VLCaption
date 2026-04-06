"""Tests for SRT subtitle generation."""

import os
import tempfile

from vlcaption.srt import Segment, _format_timestamp, segments_to_srt, write_srt_file


def test_format_timestamp_zero() -> None:
    assert _format_timestamp(0.0) == "00:00:00,000"


def test_format_timestamp_simple() -> None:
    assert _format_timestamp(1.5) == "00:00:01,500"


def test_format_timestamp_minutes() -> None:
    assert _format_timestamp(65.123) == "00:01:05,123"


def test_format_timestamp_hours() -> None:
    assert _format_timestamp(3662.0) == "01:01:02,000"


def test_segments_to_srt_empty() -> None:
    assert segments_to_srt([]) == ""


def test_segments_to_srt_single() -> None:
    segments = [Segment(start=0.0, end=2.5, text="Hello, world.")]
    result = segments_to_srt(segments)
    expected = "1\n00:00:00,000 --> 00:00:02,500\nHello, world.\n"
    assert result == expected


def test_segments_to_srt_multiple() -> None:
    segments = [
        Segment(start=0.0, end=2.0, text="First line."),
        Segment(start=2.5, end=5.0, text="Second line."),
    ]
    result = segments_to_srt(segments)
    assert "1\n" in result
    assert "2\n" in result
    assert "First line." in result
    assert "Second line." in result


def test_write_srt_file() -> None:
    segments = [Segment(start=0.0, end=1.0, text="Test.")]
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as f:
        media_path = f.name

    try:
        srt_path = write_srt_file(segments, media_path)
        assert srt_path.endswith(".srt")
        assert os.path.isfile(srt_path)

        with open(srt_path, encoding="utf-8") as f:
            content = f.read()
        assert "Test." in content
    finally:
        os.unlink(media_path)
        if os.path.exists(srt_path):
            os.unlink(srt_path)
