"""Shared configuration constants and formatting helpers."""

from __future__ import annotations

DEFAULT_PORT: int = 6800
DEFAULT_HOST: str = "localhost"


def _fmt_speed(bps: int) -> str:
    """Format bytes-per-second into a human-readable string.

    Args:
        bps: Speed in bytes per second.

    Returns:
        Formatted string like "1.5 MB/s", "42 KB/s", or "900 B/s".

    """
    if bps >= 1_000_000:
        return f"{bps / 1_000_000:.1f} MB/s"
    if bps >= 1_000:
        return f"{bps / 1_000:.0f} KB/s"
    return f"{bps} B/s"
