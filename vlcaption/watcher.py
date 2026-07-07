"""Watch VLC and auto-generate subtitles for whatever is playing.

Polls the running VLC instance for its current media item (macOS
AppleScript). When a new local video with no adjacent .srt starts playing,
transcribes it and pushes the finished subtitles into the running input.
No Lua extension or VLC configuration required.
"""

from __future__ import annotations

import logging
import os
import sys
import time
from argparse import ArgumentParser

from vlcaption import vlc
from vlcaption.embed import can_embed, embed_subtitles
from vlcaption.srt import write_srt_file
from vlcaption.transcriber import Transcriber

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = frozenset(
    {".mp4", ".mkv", ".avi", ".mov", ".m4v", ".webm", ".wmv", ".flv", ".mpg", ".mpeg", ".ts", ".ogv"}
)


class Watcher:
    """Sequentially transcribes each new video VLC starts playing."""

    def __init__(
        self,
        model: str = "auto",
        overwrite: bool = False,
        include_audio: bool = False,
        embed: bool = False,
    ) -> None:
        self._model = model
        self._overwrite = overwrite
        self._include_audio = include_audio
        self._embed = embed
        self._transcriber = Transcriber()
        self._handled: set[str] = set()

    def _should_handle(self, path: str) -> bool:
        if path in self._handled or not os.path.isfile(path):
            return False
        if not self._include_audio and os.path.splitext(path)[1].lower() not in VIDEO_EXTENSIONS:
            return False
        return True

    def poll_once(self) -> None:
        """Check what VLC is playing and transcribe it if it's new."""
        path = vlc.current_item()
        if path is None or not self._should_handle(path):
            return

        # Mark before transcribing so a failure isn't retried every poll.
        self._handled.add(path)

        srt_path = os.path.splitext(path)[0] + ".srt"
        if os.path.exists(srt_path) and not self._overwrite:
            logger.info("Subtitles already exist, skipping: %s", srt_path)
            return

        logger.info("New media playing: %s", path)
        result = self._transcriber.transcribe(path, model=self._model)
        srt_path = write_srt_file(result.segments, path)
        logger.info("Wrote %d segments (language=%s): %s", len(result.segments), result.language, srt_path)

        if not vlc.push_subtitle(srt_path, media_path=path):
            logger.info("Not pushed into the running player; VLC will auto-load it on the next open.")

        if self._embed and can_embed(path):
            # Sidecar copy, never in place: VLC still has the original open.
            embed_subtitles(path, srt_path=srt_path, language=result.language if result.language != "auto" else None)

    def run(self, interval: float = 3.0) -> None:
        """Poll forever, surviving per-file errors."""
        logger.info("Watching VLC (model=%s, every %.0fs). Ctrl-C to stop.", self._model, interval)
        while True:
            try:
                self.poll_once()
            except Exception:
                logger.exception("Watcher iteration failed")
            time.sleep(interval)


def main() -> None:
    """Entry point for the VLCaption watcher."""
    parser = ArgumentParser(description="Auto-generate subtitles for whatever VLC is playing")
    parser.add_argument("--model", default="auto", help="Model choice (default: auto)")
    parser.add_argument("--interval", type=float, default=3.0, help="Poll interval in seconds (default: 3)")
    parser.add_argument("--overwrite", action="store_true", help="Re-transcribe media that already has an .srt")
    parser.add_argument("--include-audio", action="store_true", help="Also transcribe audio-only files")
    parser.add_argument(
        "--embed",
        action="store_true",
        help="Also write a <name>.subbed.<ext> copy with the subtitles embedded as a track",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if sys.platform != "darwin":
        parser.error("watch mode currently supports macOS only (uses VLC's AppleScript interface)")

    watcher = Watcher(model=args.model, overwrite=args.overwrite, include_audio=args.include_audio, embed=args.embed)
    try:
        watcher.run(interval=args.interval)
    except KeyboardInterrupt:
        logger.info("Stopped.")


if __name__ == "__main__":
    main()
