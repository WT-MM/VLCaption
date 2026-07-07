"""Embed subtitles into media containers as a soft-subtitle track.

A lossless ffmpeg remux: video and audio streams are copied bit-for-bit and
the SRT becomes a selectable subtitle track inside the container. The .srt
next to the media keeps working for players that prefer external subtitles.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import tempfile
from argparse import ArgumentParser

logger = logging.getLogger(__name__)

# Containers that support embedded soft subtitles, and the codec each needs.
SUBTITLE_CODECS: dict[str, str] = {
    ".mp4": "mov_text",
    ".m4v": "mov_text",
    ".mov": "mov_text",
    ".mkv": "srt",
    ".webm": "webvtt",
}


def can_embed(media_path: str) -> bool:
    """Check whether the media's container supports embedded soft subtitles."""
    return os.path.splitext(media_path)[1].lower() in SUBTITLE_CODECS


def default_output_path(media_path: str) -> str:
    """The default embed target: <name>.subbed.<ext> next to the original."""
    base, ext = os.path.splitext(media_path)
    return f"{base}.subbed{ext}"


def embed_subtitles(
    media_path: str,
    srt_path: str | None = None,
    output_path: str | None = None,
    language: str | None = None,
    replace: bool = False,
) -> str:
    """Remux a subtitle file into the media container.

    Args:
        media_path: The video file to embed into.
        srt_path: Subtitle file; defaults to the .srt next to the media.
        output_path: Where to write the result; defaults to
            <name>.subbed.<ext>. Ignored when replace is True.
        language: Language tag for the subtitle track (e.g. "eng").
        replace: Overwrite the original media file in place (atomically:
            the remux goes to a temp file first, so a failure leaves the
            original untouched).

    Returns:
        Path to the written file.

    Raises:
        ValueError: If the container has no soft-subtitle support, or the
            inputs are missing.
        RuntimeError: If ffmpeg is not installed.
        subprocess.CalledProcessError: If the remux fails.
    """
    ext = os.path.splitext(media_path)[1].lower()
    codec = SUBTITLE_CODECS.get(ext)
    if codec is None:
        supported = ", ".join(sorted(SUBTITLE_CODECS))
        raise ValueError(f"'{ext}' containers cannot hold soft subtitles (supported: {supported}); keep the .srt")
    if shutil.which("ffmpeg") is None:
        raise RuntimeError("ffmpeg not found on PATH; install it to embed subtitles (brew install ffmpeg)")

    if srt_path is None:
        srt_path = os.path.splitext(media_path)[0] + ".srt"
    if not os.path.isfile(media_path):
        raise ValueError(f"Media file not found: {media_path}")
    if not os.path.isfile(srt_path):
        raise ValueError(f"Subtitle file not found: {srt_path}")

    if replace:
        fd, target = tempfile.mkstemp(suffix=ext, dir=os.path.dirname(os.path.abspath(media_path)))
        os.close(fd)
    else:
        target = output_path or default_output_path(media_path)

    cmd = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-i",
        media_path,
        "-i",
        srt_path,
        "-map",
        "0",
        "-map",
        "1:0",
        "-c",
        "copy",
        "-c:s",
        codec,
    ]
    if language:
        # Tags the first subtitle stream; correct whenever the media had no
        # subtitle tracks of its own (the common case for this tool).
        cmd += ["-metadata:s:s:0", f"language={language}"]
    cmd.append(target)

    logger.info("Embedding %s into %s", srt_path, media_path if replace else target)
    try:
        subprocess.run(cmd, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as e:
        if replace and os.path.exists(target):
            os.unlink(target)
        logger.error("ffmpeg failed: %s", e.stderr.strip())
        raise

    if replace:
        os.replace(target, media_path)
        target = media_path
    logger.info("Embedded subtitles: %s", target)
    return target


def main() -> None:
    """Entry point for vlcaption-embed."""
    parser = ArgumentParser(description="Embed an SRT into a video as a soft-subtitle track (lossless remux)")
    parser.add_argument("media", help="Video file (mp4, m4v, mov, mkv, webm)")
    parser.add_argument("--srt", default=None, help="Subtitle file (default: the .srt next to the media)")
    parser.add_argument("--output", default=None, help="Output file (default: <name>.subbed.<ext>)")
    parser.add_argument("--language", default=None, help="Subtitle language tag, e.g. eng")
    parser.add_argument("--replace", action="store_true", help="Overwrite the original media file in place")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    try:
        embed_subtitles(
            args.media,
            srt_path=args.srt,
            output_path=args.output,
            language=args.language,
            replace=args.replace,
        )
    except (ValueError, RuntimeError) as e:
        parser.error(str(e))


if __name__ == "__main__":
    main()
