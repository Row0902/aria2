"""CLI entry point for the aria2 SDK — manages bundled aria2c binary."""

from __future__ import annotations

import argparse
import asyncio
import os
import signal
import subprocess
import sys
from pathlib import Path


def _find_binary() -> Path:
    """Locate the aria2c binary, bundled or system."""
    # Try bundled first (wheel)
    try:
        from aria2_bin import get_binary_path

        return get_binary_path()
    except ImportError, FileNotFoundError:
        pass

    # Fallback: PATH
    aria2c = os.getenv("ARIA2C_PATH") or "aria2c"
    which = subprocess.run(["which", aria2c], capture_output=True, text=True, check=False)
    if which.returncode == 0:
        return Path(which.stdout.strip())

    msg = (
        "aria2c not found. Install the bundle or place aria2c in PATH.\n"
        "  pip install aria2  (bundled binary)\n"
        "  apt install aria2  (system package)"
    )
    sys.exit(msg)


def cmd_start(args: argparse.Namespace) -> None:
    """Start an aria2c daemon with RPC enabled."""
    binary = _find_binary()

    cmd = [
        str(binary),
        "--enable-rpc",
        f"--rpc-listen-port={args.port}",
        "--rpc-listen-all=true" if args.listen_all else "--rpc-listen-all=false",
    ]

    if args.secret:
        cmd.append(f"--rpc-secret={args.secret}")

    if args.dir:
        cmd.append(f"--dir={args.dir}")

    if args.conf:
        cmd.extend(["--conf-path", str(args.conf)])

    if args.daemon:
        cmd.append("--daemon=true")
        print(f"🍃 aria2c daemon started on port {args.port}")
        if args.secret:
            print(f"   Secret: {args.secret}")
        subprocess.run(cmd, check=False)
    else:
        print(f"🍃 Starting aria2c on port {args.port} …")
        print("   Press Ctrl+C to stop")

        proc = subprocess.Popen(
            cmd,
            stdout=sys.stdout,
            stderr=sys.stderr,
        )

        def _shutdown(*_: object) -> None:
            proc.terminate()

        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)
        proc.wait()


def cmd_check(args: argparse.Namespace) -> None:
    """Check if aria2c binary is available."""
    try:
        binary = _find_binary()
        result = subprocess.run(
            [str(binary), "--version"], capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            print(f"✓ aria2c found: {binary}")
            print(result.stdout.splitlines()[0])
        else:
            print(f"✗ aria2c at {binary} but execution failed")
            sys.exit(1)
    except SystemExit:
        sys.exit(1)


async def cmd_status(args: argparse.Namespace) -> None:
    """Query a running aria2 daemon for version and stats."""
    try:
        from aria2 import Aria2Client
    except ImportError:
        sys.exit("aria2 SDK not installed")

    try:
        async with Aria2Client(
            host=args.host, port=args.port, secret=args.secret, timeout=5.0
        ) as client:
            version = await client.system.get_version()
            print(f"aria2 {version.version}")
            print(f"  Features: {', '.join(version.enabled_features)}")

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
    except ConnectionRefusedError:
        sys.exit(f"✗ aria2 not running on {args.host}:{args.port}\n  Start it: aria2 start")
    except Exception as e:
        sys.exit(f"✗ Error: {e}")


def _fmt_speed(bps: int) -> str:
    if bps >= 1_000_000:
        return f"{bps / 1_000_000:.1f} MB/s"
    if bps >= 1_000:
        return f"{bps / 1_000:.0f} KB/s"
    return f"{bps} B/s"


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="aria2",
        description="aria2 download manager — CLI wrapper\n  https://github.com/Row0902/aria2",
    )
    parser.set_defaults(func=lambda _: parser.print_help())

    sub = parser.add_subparsers(title="commands")

    # ── start ────────────────────────────────────────────────
    start_p = sub.add_parser("start", help="Start aria2c daemon with RPC enabled")
    start_p.add_argument("-p", "--port", type=int, default=6800, help="RPC port")
    start_p.add_argument("-s", "--secret", help="RPC secret token (recommended)")
    start_p.add_argument("--listen-all", action="store_true", help="Listen on all interfaces")
    start_p.add_argument("-d", "--dir", help="Download directory")
    start_p.add_argument("-c", "--conf", type=Path, help="Path to aria2 config file")
    start_p.add_argument("--daemon", action="store_true", help="Run in background")
    start_p.set_defaults(func=cmd_start)

    # ── check ────────────────────────────────────────────────
    check_p = sub.add_parser("check", aliases=["version"], help="Check aria2c binary")
    check_p.set_defaults(func=cmd_check)

    # ── status ───────────────────────────────────────────────
    status_p = sub.add_parser("status", help="Query running aria2 daemon status")
    status_p.add_argument("--host", default="localhost", help="RPC host (default: localhost)")
    status_p.add_argument("-p", "--port", type=int, default=6800, help="RPC port (default: 6800)")
    status_p.add_argument("-s", "--secret", help="RPC secret token")
    status_p.set_defaults(func=lambda a: asyncio.run(cmd_status(a)))

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
