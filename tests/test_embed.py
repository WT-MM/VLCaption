"""Tests for subtitle embedding."""

import os
import shutil
import subprocess

import pytest

from vlcaption.embed import can_embed, default_output_path, embed_subtitles

SRT_CONTENT = """1
00:00:00,000 --> 00:00:01,000
Hello there.
"""


def test_can_embed_by_container() -> None:
    assert can_embed("/x/movie.mp4")
    assert can_embed("/x/movie.MKV")
    assert not can_embed("/x/movie.avi")
    assert not can_embed("/x/song.mp3")


def test_default_output_path() -> None:
    assert default_output_path("/x/movie.mp4") == "/x/movie.subbed.mp4"


def test_rejects_unsupported_container() -> None:
    with pytest.raises(ValueError, match="cannot hold soft subtitles"):
        embed_subtitles("/x/movie.avi")


@pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
def test_rejects_missing_srt(tmp_path: "os.PathLike[str]") -> None:
    media = os.path.join(tmp_path, "clip.mp4")
    open(media, "w").close()
    with pytest.raises(ValueError, match="Subtitle file not found"):
        embed_subtitles(media)


@pytest.mark.slow
@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg not installed",
)
def test_embed_roundtrip(tmp_path: "os.PathLike[str]") -> None:
    media = os.path.join(tmp_path, "clip.mp4")
    srt = os.path.join(tmp_path, "clip.srt")
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=size=64x64:rate=10:duration=1",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-c:v",
            "h264",
            "-c:a",
            "aac",
            media,
        ],
        check=True,
    )
    with open(srt, "w", encoding="utf-8") as f:
        f.write(SRT_CONTENT)

    out = embed_subtitles(media, language="eng")
    assert out == os.path.join(tmp_path, "clip.subbed.mp4")
    assert os.path.isfile(out)

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "s", "-show_entries", "stream=codec_name", "-of", "csv=p=0", out],
        check=True,
        capture_output=True,
        text=True,
    )
    assert probe.stdout.strip() == "mov_text"


@pytest.mark.slow
@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("ffprobe") is None,
    reason="ffmpeg not installed",
)
def test_embed_replace_in_place(tmp_path: "os.PathLike[str]") -> None:
    media = os.path.join(tmp_path, "clip.mkv")
    srt = os.path.join(tmp_path, "clip.srt")
    subprocess.run(
        [
            "ffmpeg",
            "-loglevel",
            "error",
            "-f",
            "lavfi",
            "-i",
            "color=size=64x64:rate=10:duration=1",
            "-c:v",
            "h264",
            media,
        ],
        check=True,
    )
    with open(srt, "w", encoding="utf-8") as f:
        f.write(SRT_CONTENT)

    out = embed_subtitles(media, replace=True)
    assert out == media

    probe = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "s", "-show_entries", "stream=codec_name", "-of", "csv=p=0", out],
        check=True,
        capture_output=True,
        text=True,
    )
    assert probe.stdout.strip() in {"srt", "subrip"}
