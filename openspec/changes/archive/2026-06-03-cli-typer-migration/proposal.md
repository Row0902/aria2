# SDD Proposal: Migrate CLI from argparse to typer

**Change ID**: `2026-06-03-cli-typer-migration`
**Author**: SDD Executor (generated)
**Date**: 2026-06-03
**Status**: Draft

---

## 1. Intent

Replace the hand-rolled `argparse` CLI framework with `typer` (which builds on Click) to gain:

| Capability | argparse | typer |
|---|---|---|
| Type validation | Manual `type=` on each argument | Automatic from Python type hints |
| Help text | Manual `help=` strings, `add_help=False` footguns | Auto-generated from docstrings + type hints |
| Shell completion | Requires `argcomplete` + manual setup | Built-in `--install-completion` / `--show-completion` |
| Subcommand nesting | Manual `set_defaults(func=…)` dispatch | `app.add_typer()` with proper subcommand trees |
| Error formatting | Raw traceback or manual `sys.exit()` | Rich-formatted errors (pretty_exceptions) |
| Testability | Manual `StringIO` capture | `CliRunner` — full invoke/assert lifecycle |
| Global flags (e.g. `--version`) | Manual eager argument | `@app.callback()` + `is_eager=True` pattern |
| Output channels | `print()` | `typer.echo()` (encoding-safe, testable) |

`typer>=0.26.5` is **already declared** in `apps/cli/pyproject.toml` but currently unused — this migration consumes the existing dependency.

---

## 2. Scope

### In scope

| File | Operation | Rationale |
|---|---|---|
| `apps/cli/src/cli/__init__.py` | **Rewrite** | Replace `argparse.ArgumentParser`, builder helpers, and `main()` with `typer.Typer()`, `@app.callback()`, `@app.command()` for `check`, and `app.add_typer()` |
| `apps/cli/src/cli/commands/__init__.py` | **Update** | Change exports from function references (`cmd_start`, `cmd_status`) to typer app references (`start_app`, `status_app`) |
| `apps/cli/src/cli/commands/start.py` | **Rewrite** | Replace `cmd_start(args: Namespace)` with `@app.command()` using typed `typer.Option()` params; refactor `_build_start_cmd()` and `_run_foreground()` to accept individual parameters |
| `apps/cli/src/cli/commands/status.py` | **Rewrite** | Replace `cmd_status(args: Namespace) -> None` (async) with sync `@app.command()` wrapping `asyncio.run(_async_impl(...))`; typed `typer.Option()` params |
| `apps/cli/tests/test_cli.py` | **Create** | Test suite using `typer.testing.CliRunner` |

### Out of scope

| Item | Reason |
|---|---|
| `apps/cli/src/cli/finder.py` | No behavioural change needed |
| `apps/cli/src/cli/config.py` | No behavioural change needed |
| `apps/cli/pyproject.toml` | `typer>=0.26.5` already present |
| `apps/cli/src/cli/__main__.py` | Entry point `cli.__main__:main` stays unchanged — `main()` still delegates to `cli.main()` |
| Adding integration tests against a live aria2 daemon | CLI tests use CliRunner only; integration tests are future work |
| Refactoring the SDK client (`Aria2Client`) | Not related to CLI migration |
| Rich progress bars / spinners | Out of scope for this migration; can be added later |

---

## 3. Current Architecture

```
apps/cli/src/cli/
├── __init__.py           # Argparse parser, 3 builder helpers, main(), cmd_check
├── commands/
│   ├── __init__.py       # Re-exports cmd_start, cmd_status
│   ├── start.py          # cmd_start(Namespace), _build_start_cmd(Namespace), _run_foreground(Namespace)
│   └── status.py         # async cmd_status(Namespace), _print_version_info(), _try_print_global_stats()
├── finder.py             # find_binary() — UNCHANGED
└── config.py             # DEFAULT_PORT, DEFAULT_HOST, _fmt_speed() — UNCHANGED
```

**Dispatch mechanism**:
1. `cli.main()` builds `argparse.ArgumentParser`, adds subparsers via `_add_*_parser()` helpers.
2. Each helper calls `sub.add_parser(...)` then `set_defaults(func=cmd_*)`.
3. After `parse_args()`, dispatches via `args.func(args)`.
4. `status` uses a lambda wrapper: `lambda a: asyncio.run(cmd_status(a))`.

**Current behavioural details**:
- `print()` used for all output.
- `sys.exit()` / `SystemExit` raised for errors and binary-not-found.
- Async `cmd_status()` called via `asyncio.run()` in a lambda — no dedicated wrapper.
- `--version` flag: **not present** in argparse; no version display.
- Shell completion: **not available**.
- No CLI-level tests exist.

---

## 4. Target Architecture

```
apps/cli/src/cli/
├── __init__.py           # typer.Typer() app, @app.callback() with --version,
│                         # @app.command() for check, app.add_typer() for start/status
├── commands/
│   ├── __init__.py       # Re-exports start_app, status_app
│   ├── start.py          # app = typer.Typer(), @app.command() start(), helpers
│   └── status.py         # app = typer.Typer(), @app.command() status(), helpers
├── finder.py             # UNCHANGED
└── config.py             # UNCHANGED
```

**Dispatch mechanism**:
1. `cli.main()` calls `app()` — Typer auto-dispatches to the correct subcommand.
2. `app.add_typer(start_app, name="start")` and `app.add_typer(status_app, name="status")` wire subcommands.
3. `check` is a `@app.command()` on the root `app`.
4. `--version` is handled by `@app.callback()` with an eager option.
5. `status` command wraps the async implementation with `asyncio.run()` in the command function body.

---

## 5. Detailed Design

### 5.1 `cli/__init__.py` — Root Typer App

**Structure**:
```python
from __future__ import annotations

import typer
from typing import Annotated

from .commands import start_app, status_app

__version__ = "0.1.0"


def _version_callback(value: bool) -> None:
    if value:
        typer.echo(f"aria2-cli v{__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="aria2",
    no_args_is_help=True,
    add_completion=True,
    pretty_exceptions_enable=True,
    pretty_exceptions_show_locals=False,
    pretty_exceptions_short=True,
    rich_markup_mode="rich",
    context_settings={"help_option_names": ["--help", "-h"]},
    epilog="See https://aria2.github.io/ for more info.",
)


@app.callback()
def main(
    ctx: typer.Context,
    version: Annotated[bool, typer.Option(
        "--version", "-V",
        is_eager=True,
        callback=_version_callback,
        help="Show version and exit.",
    )] = False,
) -> None:
    """aria2 download manager — CLI wrapper."""
    ctx.ensure_object(dict)


@app.command()
def check() -> None:
    """Check if aria2c binary is available."""
    import subprocess

    from .finder import find_binary

    try:
        binary = find_binary()
        result = subprocess.run(
            [str(binary), "--version"], capture_output=True, text=True, check=False
        )
        if result.returncode == 0:
            typer.echo(f"✓ aria2c found: {binary}")
            typer.echo(result.stdout.splitlines()[0])
        else:
            typer.echo(f"✗ aria2c at {binary} but execution failed", err=True)
            raise typer.Exit(code=1)
    except typer.Exit:
        raise
    except Exception as e:
        typer.echo(f"✗ {e}", err=True)
        raise typer.Exit(code=1)


# Register subcommand groups
app.add_typer(start_app, name="start", help="Start aria2c daemon with RPC enabled")
app.add_typer(status_app, name="status", help="Query running aria2 daemon status")


def main() -> None:
    """Entry point for the aria2 CLI."""
    app()
```

**Key decisions**:
- `check` stays as a root `@app.command()` (not a separate sub-typer) because it has no sub-subcommands. This matches the current flat `check` subcommand.
- `--version` is added via `@app.callback()` — it appears in the help header and works before any subcommand. Currently there is no `--version` flag; this is a **new feature**.
- `main()` is both the `@app.callback()` function AND the entry point function. The callback stores context; the module-level `main()` just calls `app()`.

### 5.2 `cli/commands/start.py` — Start Subcommand

**Structure**:
```python
from __future__ import annotations

import pathlib
import signal
import subprocess
import sys
from typing import Annotated

import typer

from ..config import DEFAULT_PORT
from ..finder import find_binary

app = typer.Typer(
    name="start",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@app.command()
def start(
    port: Annotated[int, typer.Option("--port", "-p",
        min=1024, max=65535,
        help="RPC listen port",
        show_default=True,
    )] = DEFAULT_PORT,
    secret: Annotated[str | None, typer.Option("--secret", "-s",
        help="RPC secret token (recommended)",
        show_envvar=True,
    )] = None,
    listen_all: Annotated[bool, typer.Option("--listen-all",
        help="Listen on all network interfaces",
    )] = False,
    dir: Annotated[pathlib.Path | None, typer.Option("--dir", "-d",
        dir_okay=True, file_okay=False,
        help="Download directory",
    )] = None,
    conf: Annotated[pathlib.Path | None, typer.Option("--conf", "-c",
        exists=True, dir_okay=False,
        help="Path to aria2 config file",
    )] = None,
    daemon: Annotated[bool, typer.Option("--daemon",
        help="Run aria2c in background (daemon mode)",
    )] = False,
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
    dir: pathlib.Path | None,
    conf: pathlib.Path | None,
) -> list[str]:
    """Build the aria2c command-line argument list."""
    cmd = [
        binary,
        "--enable-rpc",
        f"--rpc-listen-port={port}",
        "--rpc-listen-all=true" if listen_all else "--rpc-listen-all=false",
    ]

    if secret:
        cmd.append(f"--rpc-secret={secret}")
    if dir:
        cmd.append(f"--dir={str(dir)}")
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
```

**Key decisions**:
- Helper functions `_build_start_cmd()` and `_run_foreground()` now accept individual typed parameters instead of `args: argparse.Namespace`.
- `pathlib.Path` used for `dir` and `conf` instead of raw strings — Typer auto-resolves.
- `dir_okay=True, file_okay=False` for `dir` (a directory); `exists=True, dir_okay=False` for `conf` (a file that must exist).
- `port` gets `min=1024, max=65535` validation via Typer.
- `print()` → `typer.echo()` everywhere.
- The typer app is named `start` but the function inside is `start()` — Typer infers the subcommand name from the function name, which matches.

### 5.3 `cli/commands/status.py` — Status Subcommand

**Structure**:
```python
from __future__ import annotations

import asyncio
from typing import Annotated

import typer

from ..config import DEFAULT_HOST, DEFAULT_PORT, _fmt_speed

app = typer.Typer(
    name="status",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@app.command()
def status(
    host: Annotated[str, typer.Option("--host",
        help="RPC host address",
        show_default=True,
    )] = DEFAULT_HOST,
    port: Annotated[int, typer.Option("--port", "-p",
        min=1024, max=65535,
        help="RPC port",
        show_default=True,
    )] = DEFAULT_PORT,
    secret: Annotated[str | None, typer.Option("--secret", "-s",
        help="RPC secret token",
        show_envvar=True,
    )] = None,
) -> None:
    """Query a running aria2 daemon for version and download statistics."""
    asyncio.run(_status_impl(host, port, secret))


async def _status_impl(host: str, port: int, secret: str | None) -> None:
    """Async implementation of status query."""
    try:
        from aria2 import Aria2Client  # type: ignore[import-untyped]
    except ImportError:
        typer.echo("✗ aria2 SDK not installed", err=True)
        raise typer.Exit(code=1)

    try:
        async with Aria2Client(
            host=host, port=port, secret=secret, timeout=5.0
        ) as client:
            version = await client.system.get_version()
            _print_version_info(version)
            await _try_print_global_stats(client)
    except ConnectionRefusedError:
        typer.echo(
            f"✗ aria2 not running on {host}:{port}\n  Start it: aria2 start",
            err=True,
        )
        raise typer.Exit(code=1)
    except Exception as e:
        typer.echo(f"✗ Error: {e}", err=True)
        raise typer.Exit(code=1)


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
```

**Key decisions**:
- `@app.command()` is **sync** — it immediately calls `asyncio.run(_status_impl(…))` to wrap the async implementation.
- The async implementation is renamed `_status_impl()` to clearly indicate it's a private helper, not the command entry point.
- `sys.exit()` replaced with `typer.echo(…, err=True) + raise typer.Exit(code=1)`.
- `typer.echo()` used for all output — enables CliRunner testing.
- No changes to the import-error handling: it uses `try/except ImportError` rather than declaring `aria2` as a hard dependency, preserving the optional-SDK pattern.

### 5.4 `cli/commands/__init__.py` — Updated Exports

```python
"""CLI subcommand Typer apps."""

from __future__ import annotations

from .start import app as start_app
from .status import app as status_app

__all__ = [
    "start_app",
    "status_app",
]
```

### 5.5 `cli/__main__.py` — No Change

```python
"""CLI entry point — delegates to aria2.cli.main."""

from __future__ import annotations

from cli import main

if __name__ == "__main__":
    main()
```

The entry point script `aria2 = "cli.__main__:main"` in `pyproject.toml` continues to work unchanged.

### 5.6 `cli/finder.py` and `cli/config.py` — No Changes

These modules are not affected by the CLI framework migration.

---

## 6. Behavioural Changes (Differences from Current)

| Aspect | Current (argparse) | Proposed (typer) | Impact |
|---|---|---|---|
| **Output** | `print()` — raw, encoding-agnostic | `typer.echo()` — encoding-safe, testable | Stderr redirected via `err=True` parameter; stdout captured by CliRunner |
| **Error output** | `sys.exit("msg")` — prints to stderr then exits 1 | `typer.echo("msg", err=True)` + `raise typer.Exit(code=1)` — same effect, testable | No user-visible difference; errors still go to stderr |
| **Help text** | Manual strings in `add_argument(help=…)` and `description=` | Auto-generated from docstrings + type hints + `typer.Option(help=…)` | Richer, more consistent formatting; different text layout |
| **`--version` flag** | Not present | Added via `@app.callback()` + `_version_callback()` | **New feature** — `aria2 --version` / `aria2 -V` works |
| **Shell completion** | Not available | Built-in `--install-completion` / `--show-completion` | **New feature** — works for Bash, Zsh, Fish, PowerShell |
| **Error formatting** | Raw Python traceback | Rich-formatted (short traceback + context) | Cleaner error display for end users |
| **Type validation** | Manual via `type=int` (no range validation) | Auto via type hints + `min`/`max`/`exists` | Port range validation (1024–65535); path existence checks |
| **Subcommand dispatch** | `args.func(args)` plus manual lambda for async | Typer auto-dispatches; no lambda needed | Internally cleaner |
| **Default values in help** | Not shown unless manually added | `show_default=True` by default on `typer.Option()` | Users see defaults in help text |
| **`conf` path validation** | No validation (string only) | `exists=True, dir_okay=False` — file must exist | **Stricter** — nonexistent config path errors early |
| **Start command: `--dir` type** | String | `pathlib.Path` | Typer auto-resolves; no runtime change for valid paths |
| **Check command: `--version` alias** | `aliases=["version"]` on argparse | Removed (typer doesn't support subcommand aliases natively) | `aria2 version` no longer works; user must use `aria2 check` or `aria2 --version` |
| **Testability** | Manual StringIO mocking | `typer.testing.CliRunner` | Full invoke/assert lifecycle |

### Mitigations for the `check` → `version` alias removal

The argparse `check` parser had `aliases=["version"]`, meaning `aria2 version` was equivalent to `aria2 check`. Typer does not natively support subcommand aliases (it's a Click limitation). To avoid breaking users:

- **Option A (recommended)**: Accept the subtle break — the `--version` flag on the root app provides better UX for version queries. Document in the changelog.
- **Option B**: Use a Click `AliasedGroup` or a manual `@app.command("version")` that delegates to `check`. This adds complexity. Not recommended for this migration.

**Decision**: Accept Option A. The `--version` global flag (`aria2 --version`) is the canonical way to check the CLI version; `aria2 check` remains for checking the aria2c binary. The `version` alias was undocumented and likely unused.

---

## 7. Test Plan

### 7.1 Test File: `apps/cli/tests/test_cli.py`

```python
"""CLI tests using typer.testing.CliRunner."""

from __future__ import annotations

from pathlib import Path
from typer.testing import CliRunner
from cli import app


runner = CliRunner()


def test_help() -> None:
    """Running with --help shows usage and subcommands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "aria2" in result.stdout
    assert "start" in result.stdout
    assert "status" in result.stdout
    assert "check" in result.stdout


def test_version() -> None:
    """Running with --version prints version and exits."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "aria2-cli v" in result.stdout


def test_start_help() -> None:
    """start subcommand shows its own help."""
    result = runner.invoke(app, ["start", "--help"])
    assert result.exit_code == 0
    assert "Start an aria2c daemon" in result.stdout
    assert "--port" in result.stdout
    assert "--secret" in result.stdout
    assert "--daemon" in result.stdout


def test_status_help() -> None:
    """status subcommand shows its own help."""
    result = runner.invoke(app, ["status", "--help"])
    assert result.exit_code == 0
    assert "Query a running aria2 daemon" in result.stdout
    assert "--host" in result.stdout
    assert "--port" in result.stdout
    assert "--secret" in result.stdout


def test_check_no_binary(monkeypatch) -> None:
    """check exits with 1 when aria2c is not found."""
    def _not_found() -> Path:
        raise typer.Exit(code=1)  # Simulate find_binary failure
    monkeypatch.setattr("cli.commands.start.find_binary", _not_found)
    # Also patch for the check command which imports find_binary directly
    # ... (test-specific patching strategy TBD during implementation)
    result = runner.invoke(app, ["check"])
    assert result.exit_code == 1


def test_check_binary_found() -> None:
    """check exits 0 when aria2c is available (requires mock)."""
    # Will require subprocess mocking or a test fixture binary
    # Implementation detail left to apply phase
    pass


def test_status_no_daemon() -> None:
    """status exits with 1 when no daemon is running."""
    # Will require mocking Aria2Client; respx for HTTP mock
    pass
```

### 7.2 Test strategy

| Test | Scope | Technique |
|---|---|---|
| Help output | Unit | `CliRunner.invoke(app, ["--help"])` — no mocking needed |
| Version flag | Unit | `CliRunner.invoke(app, ["--version"])` — no mocking needed |
| Subcommand help | Unit | `CliRunner.invoke(app, ["start", "--help"])` — pure typer |
| `check` binary not found | Unit | Monkeypatch `find_binary()` to raise `typer.Exit(1)` |
| `check` binary found | Unit | Mock `subprocess.run` to return success |
| `status` connection refused | Unit | Mock `Aria2Client.__aenter__` to raise `ConnectionRefusedError` |
| `status` success | Unit | Mock `Aria2Client` with fake version/stat responses |
| `start` foreground | Unit | Mock `find_binary()`, capture `subprocess.Popen` call |
| `start` daemon mode | Unit | Mock `find_binary()`, capture `subprocess.run` call |
| `start` with args | Unit | Verify CLI options produce correct cmd list |
| Error formatting | Unit | Verify `typer.echo(err=True)` calls produce exit code 1 |

### 7.3 Coverage target

- **80%** line coverage on `apps/cli/src/cli/` files (matching project standard in `openspec/config.yaml`).
- For `commands/start.py`, this means testing both daemon and foreground paths, with and without optional args.
- For `commands/status.py`, this means testing success, connection refused, SDK not installed, and stats-unavailable paths.

---

## 8. Risks and Mitigations

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| **`check` alias `version` removed** | Certain | Low — undocumented | Document in CHANGELOG under BREAKING; add `aria2 --version` as replacement |
| **Nested event loop in status** | Low (CLI is single-threaded) | Medium — `asyncio.run()` fails from running loop | Wrap in `asyncio.run()` at the sync boundary; never call `status()` from within an async context |
| **`_build_start_cmd()` refactoring breaks cmd order** | Medium | Medium — aria2c may misparse args | Verify all flag positions in tests; `--enable-rpc` must precede `--rpc-*` flags |
| **testability of `_run_foreground()` with signal handlers** | Medium | Low — tested via integration | Monkeypatch `signal.signal` in unit tests or skip signal tests in CI |
| **`pathlib.Path` `--dir` / `--conf` with spaces** | Low | Low — aria2c handles quoted paths | Typer passes string from `str(path)`; same as before |
| **`typer.echo()` encoding on Windows** | Low | Low — SDK targets Linux/Mac primarily | Typer handles encoding portably |
| **`rich_markup_mode="rich"` in help may cause issues in dumb terminals** | Low | Low — Rich degrades gracefully | Can switch to `"markdown"` or remove if issues arise |

---

## 9. Rollback Plan

If the migration introduces regressions:

1. **Revert all changes** to the four source files (`__init__.py`, `commands/__init__.py`, `commands/start.py`, `commands/status.py`) from git:
   ```bash
   git checkout HEAD -- apps/cli/src/cli/__init__.py \
       apps/cli/src/cli/commands/__init__.py \
       apps/cli/src/cli/commands/start.py \
       apps/cli/src/cli/commands/status.py
   ```
2. **Delete test file**:
   ```bash
   git rm apps/cli/tests/test_cli.py
   ```
3. **Remove unused import** (if `typer` not used elsewhere):
   The `typer>=0.26.5` dependency in `pyproject.toml` was already present before migration — **no rollback needed** for it.

Rollback restores the exact pre-migration behaviour including the `version` alias.

---

## 10. Success Criteria

The migration is complete when:

1. [ ] `aria2 --help` displays subcommands `start`, `status`, `check` with proper help text.
2. [ ] `aria2 --version` prints version and exits 0.
3. [ ] `aria2 start --help` shows all 6 start options with correct defaults.
4. [ ] `aria2 status --help` shows all 3 status options with correct defaults.
5. [ ] `aria2 check` works identically to pre-migration (output format preserved).
6. [ ] `aria2 start --port 6801 --daemon` spawns a daemon aria2c process on port 6801.
7. [ ] `aria2 status --port 6801` queries running daemon (requires running daemon).
8. [ ] `aria2 status` without a daemon prints a friendly error message.
9. [ ] `aria2 check` with no binary prints a friendly error message and exits 1.
10. [ ] `--install-completion` and `--show-completion` work.
11. [ ] All tests pass with `pytest` (coverage ≥ 80%).
12. [ ] `typer` import is actually used (not just a dead dependency).

---

## 11. Affected Areas

| Area | Impact |
|---|---|
| `apps/cli/src/cli/__init__.py` | Complete rewrite — argparse → typer; adds `--version`, `check` command, `app.add_typer()` |
| `apps/cli/src/cli/commands/__init__.py` | Export change: `cmd_start`/`cmd_status` → `start_app`/`status_app` |
| `apps/cli/src/cli/commands/start.py` | Rewrite — replaces `argparse.Namespace` with typed `typer.Option()`; refactors helpers |
| `apps/cli/src/cli/commands/status.py` | Rewrite — replaces `argparse.Namespace` with typed `typer.Option()`; adds sync wrapper |
| `apps/cli/tests/test_cli.py` | New file — CliRunner test suite |
| `CHANGELOG.md` | Must document: migration, `version` alias removal, new `--version` flag |
| `pyproject.toml` | **Already has** `typer>=0.26.5` — no change needed |

---

## 12. Implementation Order

1. **`cli/commands/status.py`** — Rewrite with typed params + async wrapper (no dependencies on other files).
2. **`cli/commands/start.py`** — Rewrite with typed params + refactored helpers (no dependencies on other files).
3. **`cli/commands/__init__.py`** — Update exports to expose `start_app`, `status_app`.
4. **`cli/__init__.py`** — Replace entire file with typer app, callback, check command, and `app.add_typer()` calls.
5. **`apps/cli/tests/test_cli.py`** — Create test suite.
6. **Run `pytest`** — Fix any issues.
7. **Manual smoke test** — Run `aria2 --help`, `aria2 start --help`, `aria2 status --help`, `aria2 check`, `aria2 --version`.

---

## Appendix: Option Comparison

### Current argparse for `start`:

```python
start_p.add_argument("-p", "--port", type=int, default=DEFAULT_PORT, help="RPC port")
start_p.add_argument("-s", "--secret", help="RPC secret token (recommended)")
start_p.add_argument("--listen-all", action="store_true", help="Listen on all interfaces")
start_p.add_argument("-d", "--dir", help="Download directory")
start_p.add_argument("-c", "--conf", type=Path, help="Path to aria2 config file")
start_p.add_argument("--daemon", action="store_true", help="Run in background")
```

### Proposed typer for `start`:

```python
port: Annotated[int, typer.Option("--port", "-p", min=1024, max=65535, help="RPC listen port")] = DEFAULT_PORT,
secret: Annotated[str | None, typer.Option("--secret", "-s", help="RPC secret token (recommended)")] = None,
listen_all: Annotated[bool, typer.Option("--listen-all", help="Listen on all network interfaces")] = False,
dir: Annotated[pathlib.Path | None, typer.Option("--dir", "-d", dir_okay=True, file_okay=False, help="Download directory")] = None,
conf: Annotated[pathlib.Path | None, typer.Option("--conf", "-c", exists=True, dir_okay=False, help="Path to aria2 config file")] = None,
daemon: Annotated[bool, typer.Option("--daemon", help="Run aria2c in background (daemon mode)")] = False,
```

**Benefits**: Type-safe, validated, self-documenting, testable.
