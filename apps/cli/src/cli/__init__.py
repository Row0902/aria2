"""CLI entry point for the aria2 SDK — manages bundled aria2c binary."""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from .commands import cmd_start, cmd_status
from .config import DEFAULT_HOST, DEFAULT_PORT
from .finder import find_binary


def cmd_check(args: argparse.Namespace) -> None:
    """Check if aria2c binary is available."""
    import subprocess

    try:
        binary = find_binary()
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


def _add_start_parser(sub: argparse._SubParsersAction) -> None:
    """Register the 'start' subcommand."""
    start_p = sub.add_parser("start", help="Start aria2c daemon with RPC enabled")
    start_p.add_argument("-p", "--port", type=int, default=DEFAULT_PORT, help="RPC port")
    start_p.add_argument("-s", "--secret", help="RPC secret token (recommended)")
    start_p.add_argument("--listen-all", action="store_true", help="Listen on all interfaces")
    start_p.add_argument("-d", "--dir", help="Download directory")
    start_p.add_argument("-c", "--conf", type=Path, help="Path to aria2 config file")
    start_p.add_argument("--daemon", action="store_true", help="Run in background")
    start_p.set_defaults(func=cmd_start)


def _add_check_parser(sub: argparse._SubParsersAction) -> None:
    """Register the 'check' subcommand."""
    check_p = sub.add_parser("check", aliases=["version"], help="Check aria2c binary")
    check_p.set_defaults(func=cmd_check)


def _add_status_parser(sub: argparse._SubParsersAction) -> None:
    """Register the 'status' subcommand."""
    status_p = sub.add_parser("status", help="Query running aria2 daemon status")
    status_p.add_argument("--host", default=DEFAULT_HOST, help="RPC host (default: localhost)")
    status_p.add_argument("-p", "--port", type=int, default=DEFAULT_PORT, help="RPC port")
    status_p.add_argument("-s", "--secret", help="RPC secret token")
    status_p.set_defaults(func=lambda a: asyncio.run(cmd_status(a)))


def main() -> None:
    """Entry point for the aria2 CLI."""
    parser = argparse.ArgumentParser(
        prog="aria2",
        description="aria2 download manager — CLI wrapper\n  https://github.com/Row0902/aria2",
    )
    parser.set_defaults(func=lambda _: parser.print_help())

    sub = parser.add_subparsers(title="commands")
    _add_start_parser(sub)
    _add_check_parser(sub)
    _add_status_parser(sub)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
