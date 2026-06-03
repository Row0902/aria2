"""Start an aria2c daemon with RPC enabled."""

from __future__ import annotations

import argparse
import signal
import subprocess
import sys

from ..finder import find_binary


def cmd_start(args: argparse.Namespace) -> None:
    """Start an aria2c daemon with RPC enabled."""
    binary = find_binary()
    cmd = _build_start_cmd(str(binary), args)

    if args.daemon:
        cmd.append("--daemon=true")
        print(f"🍃 aria2c daemon started on port {args.port}")
        if args.secret:
            print(f"   Secret: {args.secret}")
        subprocess.run(cmd, check=False)
    else:
        _run_foreground(cmd, args)


def _build_start_cmd(binary: str, args: argparse.Namespace) -> list[str]:
    """Build the aria2c command-line argument list from parsed args."""
    cmd = [
        binary,
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

    return cmd


def _run_foreground(cmd: list[str], args: argparse.Namespace) -> None:
    """Spawn aria2c in foreground, wait for exit, handle signals."""
    print(f"🍃 Starting aria2c on port {args.port} …")
    print("   Press Ctrl+C to stop")

    proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)

    def _shutdown(*_: object) -> None:
        proc.terminate()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    proc.wait()
