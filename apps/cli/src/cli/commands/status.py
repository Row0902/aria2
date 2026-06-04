"""Query a running aria2 daemon for version and stats."""

from __future__ import annotations

import asyncio
from typing import Annotated

import typer

from ..config import _fmt_speed

app = typer.Typer()


@app.command()
def status(
    host: Annotated[str, typer.Option("--host")] = "localhost",
    port: Annotated[int, typer.Option("--port", "-p", min=1024, max=65535)] = 6800,
    secret: Annotated[str | None, typer.Option("--secret", "-s")] = None,
) -> None:
    """Query a running aria2 daemon for version and stats."""
    asyncio.run(_status_impl(host, port, secret))


async def _status_impl(host: str, port: int, secret: str | None) -> None:
    """Async implementation of the status command."""
    try:
        from aria2 import Aria2Client  # type: ignore[import-untyped]
    except ImportError:
        typer.echo("aria2 SDK not installed", err=True)
        raise typer.Exit(code=1) from None
    try:
        async with Aria2Client(host=host, port=port, secret=secret, timeout=5.0) as client:
            version = await client.system.get_version()
            _print_version_info(version)
            await _try_print_global_stats(client)
    except ConnectionRefusedError:
        typer.echo(f"✗ aria2 not running on {host}:{port}\n  Start it: aria2 start", err=True)
        raise typer.Exit(code=1) from None
    except Exception as e:
        typer.echo(f"✗ Error: {e}", err=True)
        raise typer.Exit(code=1) from None


def _print_version_info(version: object) -> None:
    """Print aria2 version and enabled features."""
    typer.echo(f"aria2 {version.version}")
    typer.echo(f"  Features: {', '.join(version.enabled_features)}")


async def _try_print_global_stats(client: object) -> None:
    """Print download statistics if supported by the daemon."""
    try:
        stat = await client.status.get_global_stat()
        typer.echo(f"  Downloading: {stat.num_active}")
        typer.echo(f"  Waiting: {stat.num_waiting}")
        typer.echo(f"  Stopped: {stat.num_stopped}")
        speed_down = int(stat.download_speed)
        speed_up = int(stat.upload_speed)
        typer.echo(f"  Speed: ↓ {_fmt_speed(speed_down)}  ↑ {_fmt_speed(speed_up)}")
    except Exception:
        pass  # stat not always supported
