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
from vlcaption.env import ensure_tool_paths
from vlcaption.media import extract_audio_segment, media_duration
from vlcaption.srt import Segment, write_srt_file
from vlcaption.transcriber import Transcriber

logger = logging.getLogger(__name__)

VIDEO_EXTENSIONS = frozenset(
    {".mp4", ".mkv", ".avi", ".mov", ".m4v", ".webm", ".wmv", ".flv", ".mpg", ".mpeg", ".ts", ".ogv"}
)

# Progressive mode: for long files, transcribe a window around the playhead
# first so subtitles appear within seconds, then do the full pass.
QUICK_WINDOW_SECONDS = 300.0
QUICK_LEAD_SECONDS = 15.0  # start slightly behind the playhead
PROGRESSIVE_MIN_DURATION = 600.0  # under this, one full pass is fast enough


def quick_pass_window(
    duration: float | None,
    playhead: float | None,
    window: float = QUICK_WINDOW_SECONDS,
) -> tuple[float, float] | None:
    """(start, length) for a quick-start pass, or None to go straight to full."""
    if duration is None or duration < PROGRESSIVE_MIN_DURATION:
        return None
    start = max(0.0, (playhead or 0.0) - QUICK_LEAD_SECONDS)
    if start >= duration:
        return None
    return start, min(window, duration - start)


class Watcher:
    """Sequentially transcribes each new video VLC starts playing."""

    def __init__(
        self,
        model: str = "auto",
        overwrite: bool = False,
        include_audio: bool = False,
        embed: bool = False,
        progressive: bool = True,
        quick_window: float = QUICK_WINDOW_SECONDS,
    ) -> None:
        self._model = model
        self._overwrite = overwrite
        self._include_audio = include_audio
        self._embed = embed
        self._progressive = progressive
        self._quick_window = quick_window
        self._transcriber = Transcriber()
        self._handled: set[str] = set()

    def _quick_pass(self, path: str, window: tuple[float, float]) -> None:
        """Subtitle a window around the playhead and push it immediately."""
        start, length = window
        logger.info("Quick-start pass: %.0fs of audio from %.0fs in", length, start)
        wav = extract_audio_segment(path, start, length)
        try:
            result = self._transcriber.transcribe(wav, model=self._model)
            segments = [Segment(start=s.start + start, end=s.end + start, text=s.text) for s in result.segments]
            srt_path = write_srt_file(segments, path)
            vlc.push_subtitle(srt_path, media_path=path)
            logger.info("Quick-start subtitles up (%d cues); full pass next", len(segments))
        finally:
            os.unlink(wav)

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
        if self._progressive:
            window = quick_pass_window(media_duration(path), vlc.playhead(), self._quick_window)
            if window:
                try:
                    self._quick_pass(path, window)
                except Exception:
                    logger.exception("Quick-start pass failed; falling back to the full pass")

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
    parser.add_argument(
        "--no-progressive",
        action="store_true",
        help="Skip the quick-start pass on long files; always do one full pass",
    )
    parser.add_argument(
        "--quick-window",
        type=float,
        default=QUICK_WINDOW_SECONDS,
        help=f"Seconds of audio around the playhead for the quick-start pass (default: {QUICK_WINDOW_SECONDS:.0f})",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    if sys.platform != "darwin":
        parser.error("watch mode currently supports macOS only (uses VLC's AppleScript interface)")

    ensure_tool_paths()
    watcher = Watcher(
        model=args.model,
        overwrite=args.overwrite,
        include_audio=args.include_audio,
        embed=args.embed,
        progressive=not args.no_progressive,
        quick_window=args.quick_window,
    )
    try:
        watcher.run(interval=args.interval)
    except KeyboardInterrupt:
        logger.info("Stopped.")


if __name__ == "__main__":
    main()
