"""Unified `vlcaption` command-line entry point."""

from __future__ import annotations

import sys
from typing import Callable

from vlcaption import __version__

USAGE = """\
usage: vlcaption <command> [options]

Commands:
  install   Set up the VLC extension and server launcher
  watch     Auto-subtitle whatever VLC is playing (macOS)
  embed     Bake an .srt into a video as a subtitle track
  serve     Run the transcription server (the extension starts this itself)

Run 'vlcaption <command> --help' for options.
"""


def _command_main(name: str) -> Callable[[], None]:
    """Resolve a subcommand to its module main, importing lazily."""
    if name == "install":
        from vlcaption.install import main  # noqa: PLC0415
    elif name == "watch":
        from vlcaption.watcher import main  # noqa: PLC0415
    elif name == "embed":
        from vlcaption.embed import main  # noqa: PLC0415
    elif name in ("serve", "server"):
        from vlcaption.server import main  # noqa: PLC0415
    else:
        print(USAGE, file=sys.stderr)
        raise SystemExit(f"vlcaption: unknown command {name!r}")
    return main


def main() -> None:
    """Entry point for the vlcaption command."""
    argv = sys.argv[1:]
    if not argv or argv[0] in ("-h", "--help"):
        print(USAGE)
        return
    if argv[0] in ("-V", "--version"):
        print(__version__)
        return

    command = argv[0]
    command_main = _command_main(command)
    # The subcommand's own ArgumentParser reads sys.argv; shift it so the
    # command name is consumed and help text reads "vlcaption <command>".
    sys.argv = [f"vlcaption {command}", *argv[1:]]
    command_main()


if __name__ == "__main__":
    main()
