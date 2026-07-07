"""Tests for GUI-environment PATH fixes."""

import os

import pytest

from vlcaption.env import _TOOL_DIRS, ensure_tool_paths


def test_prepends_missing_tool_dirs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/usr/bin:/bin")
    ensure_tool_paths()
    parts = os.environ["PATH"].split(os.pathsep)
    for tool_dir in _TOOL_DIRS:
        if os.path.isdir(tool_dir):
            assert tool_dir in parts
    assert "/usr/bin" in parts


def test_idempotent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PATH", "/usr/bin")
    ensure_tool_paths()
    first = os.environ["PATH"]
    ensure_tool_paths()
    assert os.environ["PATH"] == first
