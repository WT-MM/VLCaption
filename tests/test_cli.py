"""Tests for the unified vlcaption CLI."""

import sys

import pytest

from vlcaption import __version__, cli
from vlcaption.embed import main as embed_main
from vlcaption.install import main as install_main
from vlcaption.server import main as server_main
from vlcaption.watcher import main as watcher_main


def test_no_args_prints_usage(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["vlcaption"])
    cli.main()
    assert "Commands:" in capsys.readouterr().out


def test_version(capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "argv", ["vlcaption", "--version"])
    cli.main()
    assert capsys.readouterr().out.strip() == __version__


def test_unknown_command_exits(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit, match="unknown command"):
        cli._command_main("dance")


def test_dispatch_table() -> None:
    assert cli._command_main("install") is install_main
    assert cli._command_main("watch") is watcher_main
    assert cli._command_main("embed") is embed_main
    assert cli._command_main("serve") is server_main
    assert cli._command_main("server") is server_main


def test_subcommand_argv_shift(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    # Dispatching to a real subcommand parser: embed rejects .avi via
    # parser.error, proving argv reached the module with the right prog.
    monkeypatch.setattr(sys, "argv", ["vlcaption", "embed", "/x/movie.avi"])
    with pytest.raises(SystemExit):
        cli.main()
    err = capsys.readouterr().err
    assert "vlcaption embed" in err
    assert "cannot hold soft subtitles" in err
