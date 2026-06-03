"""Query a running aria2 daemon for version and stats."""

from __future__ import annotations

import argparse
import sys

from ..config import _fmt_speed


async def cmd_status(args: argparse.Namespace) -> None:
    """Query a running aria2 daemon for version and stats."""
    try:
        from aria2 import Aria2Client  # type: ignore[import-untyped]
    except ImportError:
        sys.exit("aria2 SDK not installed")

    try:
        async with Aria2Client(
            host=args.host, port=args.port, secret=args.secret, timeout=5.0
        ) as client:
            version = await client.system.get_version()
            _print_version_info(version)
            await _try_print_global_stats(client)
    except ConnectionRefusedError:
        sys.exit(f"✗ aria2 not running on {args.host}:{args.port}\n  Start it: aria2 start")
    except Exception as e:
        sys.exit(f"✗ Error: {e}")


def _print_version_info(version: object) -> None:
    """Print aria2 version and enabled features."""
    print(f"aria2 {version.version}")
    print(f"  Features: {', '.join(version.enabled_features)}")


async def _try_print_global_stats(client: object) -> None:
    """Print download statistics if supported by the daemon."""
    try:
        stat = await client.status.get_global_stat()
        print(f"  Downloading: {stat.num_active}")
        print(f"  Waiting: {stat.num_waiting}")
        print(f"  Stopped: {stat.num_stopped}")
        speed_down = int(stat.download_speed)
        speed_up = int(stat.upload_speed)
        print(f"  Speed: ↓ {_fmt_speed(speed_down)}  ↑ {_fmt_speed(speed_up)}")
    except Exception:
        pass  # stat not always supported
