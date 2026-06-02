"""
This module provides access to the bundled aria2c binary.

During build, hatch_build.py downloads the platform-specific aria2c
binary from abcfy2/aria2-static-build releases, and hatchling includes
it in the wheel via force-include.

At runtime, `get_binary_path()` returns the path to the binary.
"""

from __future__ import annotations

import sys
from pathlib import Path


def get_binary_path() -> Path:
    """Return the path to the bundled aria2c binary.

    Raises FileNotFoundError if the binary was not bundled
    (e.g. running from source without building).
    """
    wheel_bin = _find_wheel_binary()
    if wheel_bin and wheel_bin.exists():
        return wheel_bin
    # Fallback: check PATH (for development / manual install)
    system_bin = _find_system_binary()
    if system_bin:
        return system_bin
    msg = (
        "aria2c binary not found. If running from source, build the"
        " package first (`uv build`) or install aria2 system-wide."
    )
    raise FileNotFoundError(msg)


def get_binary_version() -> str:
    """Return the aria2 release version bundled with this package."""
    wheel_ver = _find_wheel_version()
    if wheel_ver:
        return wheel_ver.read_text().strip()
    return "unknown (source tree)"


def _find_wheel_binary() -> Path | None:
    """Look for the binary bundled inside the wheel (package data)."""
    import importlib.resources

    try:
        pkg_files = importlib.resources.files("aria2")
    except ModuleNotFoundError, TypeError:
        return None

    import platform

    artifact = _artifact_name(sys.platform, platform.machine())
    if artifact is None:
        return None

    candidate = pkg_files / "bin" / artifact
    # Traversable -> Path via __str__
    p = Path(str(candidate))
    return p if p.exists() else None


def _find_wheel_version() -> Path | None:
    """Look for the VERSION file bundled in the wheel."""
    import importlib.resources

    try:
        pkg_files = importlib.resources.files("aria2")
    except ModuleNotFoundError, TypeError:
        return None
    candidate = pkg_files / "bin" / "VERSION"
    p = Path(str(candidate))
    return p if p.exists() else None


def _find_system_binary() -> Path | None:
    """Search PATH for aria2c."""
    import shutil

    path = shutil.which("aria2c")
    return Path(path) if path else None


def _artifact_name(sysname: str, machine: str) -> str | None:
    _map: dict[tuple[str, str], str] = {
        ("linux", "x86_64"): "aria2c-linux-x86_64",
        ("linux", "aarch64"): "aria2c-linux-aarch64",
        ("linux", "armv7l"): "aria2c-linux-armv7l",
        ("linux", "armv6l"): "aria2c-linux-armv6l",
        ("linux", "i686"): "aria2c-linux-i686",
        ("win32", "AMD64"): "aria2c-windows-amd64.exe",
        ("win32", "i686"): "aria2c-windows-x86.exe",
    }
    return _map.get((sysname, machine))


__all__ = [
    "get_binary_path",
    "get_binary_version",
]
