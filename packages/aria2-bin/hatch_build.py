"""
Hatchling build hook — downloads the aria2 static binary for the target platform
from abcfy2/aria2-static-build releases.

Each asset is a .zip containing a single static ``aria2c`` binary (~14 MB).
The zip is downloaded, extracted, and the binary renamed to a canonical name
for inclusion in the wheel.

Supports:
  - linux-x86_64 (musl static, OpenSSL 3.6.2)
  - linux-aarch64 (musl static)
  - linux-armv7l (musl static)
  - linux-arm (softfp, musl static)
  - linux-i686 (musl static)
  - windows-amd64 (MinGW static, WinTLS)
  - windows-x86 (MinGW static, WinTLS)

Source: https://github.com/abcfy2/aria2-static-build
"""

from __future__ import annotations

import platform
import stat
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from hatchling.builders.hooks.plugin.interface import BuildHookInterface

BINARIES_REPO = "abcfy2/aria2-static-build"
RELEASE_TAG = "1.37.0"

# (sysname, machine) -> (zip_asset_name, canonical_binary_name)
PLATFORM_MAP: dict[tuple[str, str], tuple[str, str]] = {
    ("linux", "x86_64"): ("aria2-x86_64-linux-musl_static.zip", "aria2c-linux-x86_64"),
    ("linux", "aarch64"): (
        "aria2-aarch64-linux-musl_static.zip",
        "aria2c-linux-aarch64",
    ),
    ("linux", "armv7l"): (
        "aria2-armv7-linux-musleabihf_static.zip",
        "aria2c-linux-armv7l",
    ),
    ("linux", "armv6l"): (
        "aria2-arm-linux-musleabi_static.zip",
        "aria2c-linux-armv6l",
    ),
    ("linux", "i686"): ("aria2-i686-linux-musl_static.zip", "aria2c-linux-i686"),
    ("win32", "AMD64"): (
        "aria2-x86_64-w64-mingw32_static.zip",
        "aria2c-windows-amd64.exe",
    ),
    ("win32", "i686"): (
        "aria2-i686-w64-mingw32_static.zip",
        "aria2c-windows-x86.exe",
    ),
}


def _detect_platform() -> tuple[str, str]:
    """Detect target platform, or raise if unsupported."""
    key = (sys.platform, platform.machine())
    entry = PLATFORM_MAP.get(key)
    if entry is None:
        supported = ", ".join(f"{s}/{m}" for s, m in PLATFORM_MAP)
        msg = f"Unsupported platform: {sys.platform}/{platform.machine()}. Supported: {supported}"
        raise OSError(msg)
    return entry


def _extract_from_zip(zip_path: Path, canonical_name: str) -> Path:
    """Extract aria2c binary from *zip_path*, then remove the zip.

    Sets the executable bit on Unix platforms.

    Returns:
        Path to the extracted binary.

    """
    inner_name = "aria2c.exe" if canonical_name.endswith(".exe") else "aria2c"
    dest = zip_path.parent / canonical_name

    with zipfile.ZipFile(zip_path) as zf:
        try:
            info = zf.getinfo(inner_name)
        except KeyError:
            msg = f"Expected {inner_name!r} not found inside {zip_path.name}"
            raise OSError(msg) from None

        with zf.open(info) as src, open(dest, "wb") as dst:
            dst.write(src.read())

    zip_path.unlink()

    if not canonical_name.endswith(".exe"):
        _mode = dest.stat().st_mode
        dest.chmod(_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    print(f"     \u2713 {canonical_name} ({dest.stat().st_size / 1024:.0f} KB)")
    return dest


def _download_zip(url: str, dest: Path, timeout: float = 120) -> Path:
    """Download a zip from *url* and write to *dest*.

    Returns:
        Path to the downloaded zip.

    """
    zip_path = dest / Path(url).name
    print(f"  \u2b07  Downloading {url} …")
    req = urllib.request.Request(url, headers={"Accept": "application/octet-stream"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            zip_path.write_bytes(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            msg = f"Binary zip not found at {url}."
            raise OSError(msg) from e
        raise

    print(f"     \u2713 {zip_path.name} ({zip_path.stat().st_size / 1024:.0f} KB)")
    return zip_path


def _download_and_extract_binary(
    zip_asset: str,
    canonical_name: str,
    dest: Path,
    *,
    tag: str = RELEASE_TAG,
    timeout: float = 120,
) -> None:
    """Download a release .zip and extract the ``aria2c`` binary."""
    url = f"https://github.com/{BINARIES_REPO}/releases/download/{tag}/{zip_asset}"
    zip_path = _download_zip(url, dest, timeout=timeout)
    _extract_from_zip(zip_path, canonical_name)


def _get_or_download_binary(
    zip_asset: str,
    canonical_name: str,
    cache_dir: Path,
    tag: str = RELEASE_TAG,
) -> Path:
    """Return cached binary path, or download + extract it."""
    binary_path = cache_dir / canonical_name
    if binary_path.exists() and binary_path.stat().st_size > 0:
        print(f"  \u2713 Using cached {binary_path}")
        return binary_path
    url = f"https://github.com/{BINARIES_REPO}/releases/download/{tag}/{zip_asset}"
    zip_path = _download_zip(url, cache_dir)
    return _extract_from_zip(zip_path, canonical_name)


class Aria2BinaryHook(BuildHookInterface):
    """Hatchling build hook that fetches the aria2 binary from abcfy2 static builds."""

    PLUGIN_NAME = "aria2-binary"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Run during build initialization — download binary if not cached."""
        try:
            zip_asset, canonical_name = _detect_platform()
        except OSError:
            print("  \u26a0  Unsupported platform; skipping binary bundling")
            return

        cache_dir = Path(self.root) / "aria2_bin"
        cache_dir.mkdir(parents=True, exist_ok=True)
        tag: str = self.config.get("tag", RELEASE_TAG)

        try:
            binary_path = _get_or_download_binary(
                zip_asset, canonical_name, cache_dir, tag=tag,
            )
        except OSError:
            print("  \u26a0  Binary fetch failed; continuing without bundling")
            return

        force_include = build_data.setdefault("force_include", {})
        force_include[str(binary_path)] = f"aria2_bin/{canonical_name}"

        version_path = cache_dir / "VERSION"
        version_path.write_text(tag)
        force_include[str(version_path)] = "aria2_bin/VERSION"
