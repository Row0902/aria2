"""Start an aria2c daemon with RPC enabled."""

from __future__ import annotations

import signal
import subprocess
import sys
from pathlib import Path
from typing import Annotated

import typer

from ..finder import find_binary

app = typer.Typer()


@app.command()
def start(
    port: Annotated[int, typer.Option("--port", "-p")] = 6800,
    secret: Annotated[str | None, typer.Option("--secret", "-s")] = None,
    listen_all: Annotated[bool, typer.Option("--listen-all")] = False,
    dir: Annotated[Path | None, typer.Option("--dir", "-d")] = None,
    conf: Annotated[Path | None, typer.Option("--conf", "-c")] = None,
    daemon: Annotated[bool, typer.Option("--daemon")] = False,
) -> None:
    """Start an aria2c daemon with RPC enabled."""
    binary = find_binary()
    cmd = _build_start_cmd(str(binary), port, secret, listen_all, dir, conf)
    if daemon:
        cmd.append("--daemon=true")
        typer.echo(f"🍃 aria2c daemon started on port {port}")
        if secret:
            typer.echo(f"   Secret: {secret}")
        subprocess.run(cmd, check=False)
    else:
        _run_foreground(cmd, port)


def _build_start_cmd(
    binary: str,
    port: int,
    secret: str | None,
    listen_all: bool,
    dir: Path | None,
    conf: Path | None,
) -> list[str]:
    """Build the aria2c command-line argument list."""
    flag = "--rpc-listen-all=true" if listen_all else "--rpc-listen-all=false"
    cmd = [binary, "--enable-rpc", f"--rpc-listen-port={port}", flag]
    if secret:
        cmd.append(f"--rpc-secret={secret}")
    if dir:
        cmd.append(f"--dir={dir}")
    if conf:
        cmd.extend(["--conf-path", str(conf)])
    return cmd


def _run_foreground(cmd: list[str], port: int) -> None:
    """Spawn aria2c in foreground, wait for exit, handle signals."""
    typer.echo(f"🍃 Starting aria2c on port {port} …")
    typer.echo("   Press Ctrl+C to stop")
    proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)

    def _shutdown(*_: object) -> None:
        proc.terminate()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)
    proc.wait()
