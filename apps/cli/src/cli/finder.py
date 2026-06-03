"""Locate aria2c binary — bundled wheel first, then PATH."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_NOT_FOUND_MSG = (
    "aria2c not found. Install the bundle or place aria2c in PATH.\n"
    "  pip install aria2  (bundled binary)\n"
    "  apt install aria2  (system package)"
)


def find_binary() -> Path:
    """Locate the aria2c binary, bundled or system."""
    # Try bundled first (wheel)
    try:
        from aria2_bin import get_binary_path  # type: ignore[import-untyped]

        return get_binary_path()
    except ImportError, FileNotFoundError:
        pass

    # Fallback: PATH / ARIA2C_PATH
    aria2c = os.getenv("ARIA2C_PATH") or "aria2c"
    which = subprocess.run(["which", aria2c], capture_output=True, text=True, check=False)
    if which.returncode == 0:
        return Path(which.stdout.strip())

    sys.exit(_NOT_FOUND_MSG)
