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


def _download_and_extract_binary(
    zip_asset: str,
    canonical_name: str,
    dest: Path,
    *,
    tag: str = RELEASE_TAG,
    timeout: float = 120,
) -> None:
    """Download a release .zip from abcfy2 and extract the ``aria2c`` binary."""
    url = f"https://github.com/{BINARIES_REPO}/releases/download/{tag}/{zip_asset}"
    zip_path = dest / zip_asset

    print(f"  ⬇  Downloading {url} …")
    req = urllib.request.Request(url, headers={"Accept": "application/octet-stream"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            zip_path.write_bytes(resp.read())
    except urllib.error.HTTPError as e:
        if e.code == 404:
            msg = f"Binary zip not found at {url}."
            raise OSError(msg) from e
        raise

    print(f"     ✓ {zip_path.name} ({zip_path.stat().st_size / 1024:.0f} KB)")

    # The zip always contains a file named "aria2c" (or "aria2c.exe" on Windows)
    inner_name = "aria2c.exe" if canonical_name.endswith(".exe") else "aria2c"

    with zipfile.ZipFile(zip_path) as zf:
        try:
            info = zf.getinfo(inner_name)
        except KeyError:
            msg = f"Expected {inner_name!r} not found inside {zip_asset}"
            raise OSError(msg) from None

        binary_path = dest / canonical_name
        with zf.open(info) as src, open(binary_path, "wb") as dst:
            dst.write(src.read())

    # Remove the zip — no need to keep it around
    zip_path.unlink()

    # Make executable on Unix
    if not canonical_name.endswith(".exe"):
        _mode = binary_path.stat().st_mode
        binary_path.chmod(_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)

    print(f"     ✓ {canonical_name} ({binary_path.stat().st_size / 1024:.0f} KB)")


class Aria2BinaryHook(BuildHookInterface):
    """Hatchling build hook that fetches the aria2 binary from abcfy2 static builds."""

    PLUGIN_NAME = "aria2-binary"

    def initialize(self, version: str, build_data: dict[str, Any]) -> None:
        """Run during build initialization — download binary if not cached."""
        try:
            zip_asset, canonical_name = _detect_platform()
        except OSError:
            print("  ⚠  Unsupported platform; skipping binary bundling")
            return

        cache_dir = Path(self.root) / "aria2_bin"
        cache_dir.mkdir(parents=True, exist_ok=True)

        binary_path = cache_dir / canonical_name
        tag: str = self.config.get("tag", RELEASE_TAG)

        if not (binary_path.exists() and binary_path.stat().st_size > 0):
            try:
                _download_and_extract_binary(
                    zip_asset,
                    canonical_name,
                    cache_dir,
                    tag=tag,
                )
            except OSError:
                print("  ⚠  Binary fetch failed; continuing without bundling")
                return
        else:
            print(f"  ✓ Using cached {binary_path}")

        force_include = build_data.setdefault("force_include", {})
        force_include[str(binary_path)] = f"aria2_bin/{canonical_name}"

        version_path = cache_dir / "VERSION"
        version_path.write_text(tag)
        force_include[str(version_path)] = "aria2_bin/VERSION"
