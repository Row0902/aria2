"""Tests for aria2_bin — binary discovery."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from aria2_bin import get_binary_path, get_binary_version


def test_get_binary_path_system_fallback() -> None:
    """get_binary_path finds aria2c on PATH when not bundled."""
    with (
        patch("aria2_bin._find_wheel_binary", return_value=None),
        patch(
            "aria2_bin._find_system_binary",
            return_value=Path("/usr/bin/aria2c"),
        ),
    ):
        path = get_binary_path()
        assert path == Path("/usr/bin/aria2c")


def test_get_binary_path_not_found() -> None:
    """get_binary_path raises FileNotFoundError when not found anywhere."""
    with (
        patch("aria2_bin._find_wheel_binary", return_value=None),
        patch(
            "aria2_bin._find_system_binary",
            return_value=None,
        ),
        pytest.raises(FileNotFoundError, match="aria2c binary not found"),
    ):
        get_binary_path()


def test_get_binary_version_unknown() -> None:
    """get_binary_version returns 'unknown (source tree)' when no VERSION file."""
    with patch("aria2_bin._find_wheel_version", return_value=None):
        version = get_binary_version()
        assert version == "unknown (source tree)"
