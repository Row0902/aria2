"""CLI entry point for the aria2 SDK — manages bundled aria2c binary."""

from __future__ import annotations

from typing import Annotated

import typer

from .commands import start_app, status_app
from .finder import find_binary

__version__ = "0.1.0"

app = typer.Typer(no_args_is_help=True)
app.add_typer(start_app, name="start", help="Start aria2c daemon with RPC enabled")
app.add_typer(status_app, name="status", help="Query running aria2 daemon status")


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"aria2-sdk v{__version__}")
        raise typer.Exit()


@app.callback()
def main(
    ctx: typer.Context,
    version: Annotated[
        bool,
        typer.Option(
            "--version",
            "-V",
            is_eager=True,
            callback=_version_callback,
            help="Show version and exit.",
        ),
    ] = False,
) -> None:
    """aria2 download manager — CLI wrapper."""
    ctx.ensure_object(dict)


@app.command()
def check() -> None:
    """Check if aria2c binary is available."""
    import subprocess

    binary = find_binary()
    result = subprocess.run([str(binary), "--version"], capture_output=True, text=True, check=False)
    if result.returncode == 0:
        typer.echo(f"✓ aria2c found: {binary}")
        typer.echo(result.stdout.splitlines()[0])
    else:
        typer.echo(f"✗ aria2c at {binary} but execution failed", err=True)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
