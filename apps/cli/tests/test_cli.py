"""Tests for the aria2 CLI."""

from __future__ import annotations

from typer.testing import CliRunner

from cli import app

runner = CliRunner()


def test_help() -> None:
    """Root --help prints usage."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "aria2" in result.stdout


def test_start_help() -> None:
    """Start subcommand --help prints start-specific usage."""
    result = runner.invoke(app, ["start", "--help"])
    assert result.exit_code == 0
    assert "Start an aria2c daemon" in result.stdout


def test_status_help() -> None:
    """Status subcommand --help prints status-specific usage."""
    result = runner.invoke(app, ["status", "--help"])
    assert result.exit_code == 0
    assert "Query a running aria2 daemon" in result.stdout


def test_version() -> None:
    """--version prints version string and exits."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "aria2-sdk" in result.stdout


def test_check_no_binary() -> None:
    """Check command exits with 1 when aria2c binary not found."""
    result = runner.invoke(app, ["check"])
    assert result.exit_code == 1
    assert "aria2c not found" in result.stdout


def test_no_args_shows_help() -> None:
    """Running with no args shows help (no_args_is_help=True)."""
    result = runner.invoke(app, [])
    assert result.exit_code == 2
    assert "Usage:" in result.stdout


def test_check_help() -> None:
    """Check subcommand --help mentions check."""
    result = runner.invoke(app, ["check", "--help"])
    assert result.exit_code == 0
    assert "Check if aria2c binary" in result.stdout


def test_unknown_command() -> None:
    """Unknown command exits with 2."""
    result = runner.invoke(app, ["unknown"])
    assert result.exit_code == 2
