"""Tests for the pip-install extension installer."""

import os
import sys
from importlib import resources

import pytest

from vlcaption import install


@pytest.mark.skipif(
    sys.platform not in {"darwin", "win32"} and not sys.platform.startswith("linux"), reason="unknown OS"
)
def test_vlc_extensions_dir_known_platforms() -> None:
    path = install.vlc_extensions_dir()
    assert path.endswith(os.path.join("lua", "extensions"))


def test_bundled_lua_is_packaged() -> None:
    lua = resources.files("vlcaption").joinpath("extension/vlcaption.lua").read_text(encoding="utf-8")
    assert "function descriptor()" in lua
    assert "VLCaption" in lua


def test_install_launcher_contents(tmp_path: "os.PathLike[str]", monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(install, "LAUNCHER_DIR", str(tmp_path))
    target = install.install_launcher("/fake/bin/vlcaption-server")
    with open(target, encoding="utf-8") as f:
        content = f.read()
    assert '"/fake/bin/vlcaption-server" --exit-with-vlc' in content
    assert "/opt/homebrew/bin" in content
    assert os.access(target, os.X_OK)
