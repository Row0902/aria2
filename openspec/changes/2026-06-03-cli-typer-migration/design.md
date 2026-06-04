# SDD Design: CLI Migration — argparse → typer

**Change ID:** `2026-06-03-cli-typer-migration`
**Date:** 2026-06-03
**Status:** Draft
**Quality:** 80% coverage, ≤200 lines/file, ≤20 lines/func body

---

## 1. Architecture

### 1.1 File Structure

```
apps/cli/src/cli/
├── __init__.py              # REWRITE: typer.Typer() root app, @app.callback()
│                            #   @app.command(check), app.add_typer() for start/status
├── __main__.py              # UNCHANGED: delegates to cli.main()
├── finder.py                # UNCHANGED: find_binary()
├── config.py                # UNCHANGED: DEFAULT_PORT, DEFAULT_HOST, _fmt_speed()
└── commands/
    ├── __init__.py          # UPDATE: exports start_app, status_app (Typer apps)
    ├── start.py             # REWRITE: app = typer.Typer(), @app.command(start)
    │                        #   typed params via typer.Option(), refactored helpers
    └── status.py            # REWRITE: app = typer.Typer(), @app.command(status)
                             #   sync wrapper over asyncio.run(_status_impl(...))
```

**New file:**
```
apps/cli/tests/
└── test_cli.py              # NEW: CliRunner test suite (≥80% coverage)
```

### 1.2 Ownership Boundaries

```
cli/__init__.py (~70 lines)
  Owns: typer.Typer() app (root), @app.callback(main), @app.command(check),
        app.add_typer(start_app, name="start"), app.add_typer(status_app, name="status")
  Imports: typer, .commands.start_app, .commands.status_app, .finder.find_binary
  State: app: typer.Typer, __version__: str

cli/commands/__init__.py (~6 lines)
  Owns: re-export start_app, status_app Typer instances
  Imports: .start.app as start_app, .status.app as status_app

cli/commands/start.py (~80 lines)
  Owns: typer.Typer(app), @app.command(start), _build_start_cmd(), _run_foreground()
  Imports: typer, pathlib, signal, subprocess, sys, ..finder.find_binary, ..config.DEFAULT_PORT
  State: app: typer.Typer (no_args_is_help=True)

cli/commands/status.py (~65 lines)
  Owns: typer.Typer(app), @app.command(status), _status_impl(), _print_version_info(),
        _try_print_global_stats()
  Imports: typer, asyncio, ..config (DEFAULT_HOST, DEFAULT_PORT, _fmt_speed)
  State: app: typer.Typer (no_args_is_help=True)

cli/config.py (UNCHANGED)
  Owns: DEFAULT_PORT (6800), DEFAULT_HOST ("localhost"), _fmt_speed()

cli/finder.py (UNCHANGED)
  Owns: find_binary() → Path, NOT_FOUND_MSG

cli/__main__.py (UNCHANGED)
  Owns: if __name__ == "__main__": main()
```

### 1.3 Import Graph (no circular dependencies)

```
cli/__main__.py ──► cli/__init__.py
                         │
                         ├── ► typer
                         ├── ► .finder.find_binary
                         ├── ► .commands (start_app, status_app)
                         │        │
                         │        ├── cli/commands/start.py
                         │        │    ├── typer
                         │        │    ├── ..finder.find_binary
                         │        │    └── ..config.DEFAULT_PORT
                         │        │
                         │        └── cli/commands/status.py
                         │             ├── typer
                         │             ├── ..config (DEFAULT_HOST, DEFAULT_PORT, _fmt_speed)
                         │             └── aria2 (Aria2Client) — runtime import
                         │
                         └── ► config.py, finder.py  (both have zero intra-cli imports)
```

---

## 2. File Specs

### 2.1 `cli/__init__.py` — Root Typer App

**Source:**

```python
"""CLI entry point for the aria2 SDK — typer-based."""

from __future__ import annotations

import typer
from typing import Annotated

from .commands import start_app, status_app

__version__ = "0.1.0"


def _version_callback(value: bool) -> None:
    """Print version and exit when --version flag is set."""
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


app.add_typer(start_app, name="start", help="Start aria2c daemon with RPC enabled")
app.add_typer(status_app, name="status", help="Query running aria2 daemon status")
```

**Line count:** ~55. All functions ≤10 body lines. ✅

**Key points:**
- `main()` is both the `@app.callback()` function AND the entry point (called by `__main__.py` and `pyproject.toml` scripts entry)
- `check()` is a root `@app.command()` — no sub-typer needed (no sub-subcommands)
- `--version` via `@app.callback()` with `is_eager=True` — works before subcommands
- `check` alias `version` removed — `aria2 --version` replaces it (BREAKING)
- `print()` → `typer.echo()`, `sys.exit()` → `raise typer.Exit(code=1)`

### 2.2 `cli/commands/__init__.py` — Export Change

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

**Line count:** ~6. ✅

### 2.3 `cli/commands/start.py` — Start Subcommand

**Source:**

```python
"""Start an aria2c daemon with RPC enabled."""

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
        help="Path to aria2 config file (must exist)",
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

**Function line counts:**

| Function | Body lines | Limit | Status |
|---|---|---|---|
| `start()` | 10 | 20 | ✅ |
| `_build_start_cmd()` | 12 | 20 | ✅ |
| `_run_foreground()` | 9 | 20 | ✅ |

Total file: ~80 lines ≤200. ✅

**Key changes from argparse:**
- `cmd_start(args: Namespace)` → `start(port, secret, listen_all, dir, conf, daemon)` with typed params
- Helpers accept individual params instead of `Namespace`
- `port` validated `min=1024, max=65535` by typer (was unchecked)
- `conf` validated `exists=True, dir_okay=False` (was raw string)
- `dir` typed `pathlib.Path` with `dir_okay=True` (was raw string)
- `print()` → `typer.echo()` throughout

### 2.4 `cli/commands/status.py` — Status Subcommand

**Source:**

```python
"""Query a running aria2 daemon for version and stats."""

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

**Function line counts:**

| Function | Body lines | Limit | Status |
|---|---|---|---|
| `status()` | 2 | 20 | ✅ |
| `_status_impl()` | 17 | 20 | ✅ |
| `_print_version_info()` | 3 | 20 | ✅ |
| `_try_print_global_stats()` | 10 | 20 | ✅ |

Total file: ~65 lines ≤200. ✅

**Key changes from argparse:**
- `async def cmd_status(args: Namespace)` → sync `status()` wrapping `_status_impl()` via `asyncio.run()`
- No more lambda dispatch (`lambda a: asyncio.run(cmd_status(a))`) — Typer auto-dispatches
- `sys.exit("msg")` → `typer.echo("msg", err=True)` + `raise typer.Exit(code=1)`
- `print()` → `typer.echo()` throughout

---

## 3. Data Flow

### 3.1 Subcommand Dispatch (typer auto vs argparse manual)

**Before (argparse):**
```
__main__.py  → main()  → ArgumentParser.parse_args()
                        → args.func(args)          # cmd_start(args) | cmd_check(args) | lambda a: asyncio.run(cmd_status(a))
```

**After (typer):**
```
__main__.py  → main()  → app()                     # typer.Typer() auto-dispatches:
                        │
                        ├─ "check"  → @app.command() check()
                        ├─ "start"  → start_app() → start.@app.command() start()
                        └─ "status" → status_app() → status.@app.command() status() → asyncio.run(_status_impl())
```

### 3.2 Global Flags (--version)

```
user runs: aria2 --version
  │
  ▼
typer.Typer().__call__()
  │
  ├─ Parses --version before subcommands (is_eager=True)
  ├─ Calls _version_callback(True)
  │    ├─ typer.echo("aria2-cli v0.1.0")
  │    └─ raise typer.Exit()            ← exits 0, no subcommand runs
  └─ Done

user runs: aria2 start --port 6801
  │
  ▼
typer.Typer().__call__()
  │
  ├─ --version not present → _version_callback not called
  ├─ @app.callback() main() runs → ctx.ensure_object(dict)
  ├─ Routes "start" to start_app (typer.Typer)
  └─ start_app dispatches to @app.command() start(port=6801)
```

### 3.3 Async Wrapping (status)

```
user runs: aria2 status --host localhost --port 6800
  │
  ▼
@.app.command() status()  [SYNC]
  │
  ├─ asyncio.run(_status_impl("localhost", 6800, None))
  │    │
  │    ├─ Creates new event loop
  │    └─ Runs _status_impl to completion
  │         │
  │         ├─ import Aria2Client (try/except ImportError)
  │         ├─ async with Aria2Client(...) as client:
  │         │    ├─ await client.system.get_version() → _print_version_info()
  │         │    └─ await _try_print_global_stats(client)
  │         │
  │         └─ on error: typer.echo(err=True) + raise typer.Exit(code=1)
  │
  └─ Event loop closed, process exits
```

### 3.4 Start Subprocess Flow

```
user runs: aria2 start --port 6801 --secret mytoken --daemon
  │
  ▼
@app.command() start(port=6801, secret="mytoken", daemon=True, ...)
  │
  ├─ binary = find_binary()              # Path to aria2c
  ├─ cmd = _build_start_cmd(
  │       binary, port=6801, secret="mytoken",
  │       listen_all=False, dir=None, conf=None
  │   )
  │   → ["aria2c", "--enable-rpc", "--rpc-listen-port=6801",
  │      "--rpc-listen-all=false", "--rpc-secret=mytoken"]
  │
  ├─ daemon=True:
  │    ├─ cmd.append("--daemon=true")
  │    ├─ typer.echo("🍃 aria2c daemon started on port 6801")
  │    ├─ typer.echo("   Secret: mytoken")
  │    └─ subprocess.run(cmd, check=False)    # fire and forget
  │
  └─ daemon=False (foreground):
       └─ _run_foreground(cmd, port=6801)
            ├─ subprocess.Popen(cmd, ...)
            ├─ signal.signal(SIGINT, _shutdown)
            ├─ signal.signal(SIGTERM, _shutdown)
            └─ proc.wait()                    # blocks until Ctrl+C
```

---

## 4. Behavioral Deltas (accepted differences from argparse)

| Aspect | Before (argparse) | After (typer) | Impact |
|---|---|---|---|
| Output | `print()` | `typer.echo()` | Encoding-safe, CliRunner-capturable |
| Error exit | `sys.exit("msg")` / `SystemExit` | `typer.echo("msg", err=True)` + `raise typer.Exit(code=1)` | Same observable effect; testable |
| `--version` | Not present | `@app.callback()` + `--version` / `-V` | New feature |
| Shell completion | Not available | `--install-completion` / `--show-completion` | New feature |
| `check` alias `version` | `aliases=["version"]` | Removed | BREAKING — use `aria2 --version` |
| Port validation | None (raw `int`) | `min=1024, max=65535` | Stricter; catches bad ports early |
| Config path validation | Raw string | `exists=True, dir_okay=False` | File must exist before command runs |
| Download dir type | Raw string | `pathlib.Path` with `dir_okay=True` | Auto-resolved; behavior identical |
| Defaults in help | Not shown | `show_default=True` | Better discoverability |
| Error formatting | Raw traceback | Rich-formatted (short) | Cleaner UX |
| Subcommand dispatch | `args.func(args)` + lambda | Typer auto-dispatches | Internally cleaner |
| `sys.exit()` in finder | `sys.exit(NOT_FOUND_MSG)` | **Unchanged** — finder is not rewritten | No change |

---

## 5. Edge Cases

### 5.1 Nested Event Loop (status)
**Scenario:** `status()` is called from an already-running event loop.
**Resolution:** `asyncio.run()` creates a *new* event loop. It fails with `RuntimeError` if the current thread has a running loop. Since the CLI is always invoked from `__main__` (no existing loop), this cannot happen. The CLI is not designed for programmatic invocation from async code.

### 5.2 `find_binary()` calls `sys.exit()`
**Scenario:** `check()` calls `find_binary()` which calls `sys.exit()` on failure.
**Resolution:** This is `finder.py` behavior, which is unchanged. `sys.exit()` still works and produces the same user-facing error. The design accepts this inconsistency (finder not rewritten) because it's a separate concern. `check()` wraps calls in `try/except typer.Exit` to handle its own error paths cleanly within the typer framework.

### 5.3 `check` failure vs `typer.Exit` passthrough
**Scenario:** `find_binary()` succeeds but `aria2c --version` fails.
**Resolution:** `subprocess.run` returns non-zero → `typer.echo(err=True)` → `raise typer.Exit(code=1)`. The `try/except typer.Exit: raise` guard ensures this Exit isn't caught by `except Exception`.

### 5.4 Start with nonexistent config file
**Scenario:** `aria2 start --conf /nonexistent/aria2.conf`
**Resolution:** Typer resolves the path and fails before `start()` runs because `exists=True`. The error message is a Rich-formatted validation error. Exit code nonzero.

### 5.5 Port 0 or out-of-range
**Scenario:** `aria2 start --port 0` or `aria2 status --port 99999`
**Resolution:** Typer rejects with `min=1024`/`max=65535` violation. The error is a formatted Rich message, exit code nonzero.

### 5.6 Ctrl+C in foreground mode
**Scenario:** User presses Ctrl+C during `aria2 start` (no `--daemon`).
**Resolution:** `signal.signal(SIGINT, _shutdown)` → `proc.terminate()` → `proc.wait()` unblocks → process exits. This is unchanged behaviour.

### 5.7 `typer.echo()` encoding on Windows
**Scenario:** Non-ASCII characters in status output.
**Resolution:** `typer.echo()` handles encoding portably. The SDK primarily targets Linux/Mac; Windows is untested but likely works.

### 5.8 `rich_markup_mode="rich"` on dumb terminals
**Scenario:** Help output piped to `less` or a dumb terminal.
**Resolution:** Rich auto-detects terminal capabilities and degrades gracefully to plain text.

### 5.9 Double-close of Typer app
**Scenario:** `app()` called twice in one process.
**Resolution:** Not applicable — the CLI is single-invocation. The entry point `main()` calls `app()` once.

### 5.10 `ctx.ensure_object(dict)` is unused by subcommands
**Scenario:** The context dict is created but no subcommand reads it.
**Resolution:** This is intentional — it establishes the pattern for future global options (e.g., `--verbose`). It's zero-cost unless used.

---

## 6. Test Strategy

### 6.1 Test File: `apps/cli/tests/test_cli.py`

```python
"""CLI tests using typer.testing.CliRunner."""

from __future__ import annotations

from typer.testing import CliRunner
from cli import app

runner = CliRunner()
```

### 6.2 Test Matrix

| Category | Test | Mocking Required | Assertions |
|---|---|---|---|
| **Help** | `test_root_help` | None | `exit_code == 0`, stdout contains "aria2", "start", "status", "check" |
| | `test_start_help` | None | `exit_code == 0`, stdout contains "Start an aria2c daemon", "--port", "--secret", "--daemon" |
| | `test_status_help` | None | `exit_code == 0`, stdout contains "Query a running", "--host", "--port", "--secret" |
| | `test_no_args_shows_help` | None | `exit_code == 0`, stdout contains "start", "status", "check" |
| **Version** | `test_version_flag` | None | `exit_code == 0`, stdout contains "aria2-cli v" |
| | `test_version_short_flag` | None | `exit_code == 0`, stdout contains "aria2-cli v" |
| | `test_version_before_subcommand` | None | `exit_code == 0`, stdout contains version, no start output |
| **Check** | `test_check_ok` | Mock `subprocess.run` | `exit_code == 0`, stdout contains "✓ aria2c found" |
| | `test_check_broken` | Mock `subprocess.run` returncode=1 | `exit_code == 1`, stderr contains "✗" |
| **Start** | `test_start_daemon` | Mock `find_binary`, `subprocess.run` | `exit_code == 0`, stdout "🍃 aria2c daemon started" |
| | `test_start_foreground` | Mock `find_binary`, `subprocess.Popen` (side effect) | Cmd built correctly, `subprocess.Popen` called |
| | `test_start_cmd_contents` | Mock `find_binary` | Verify `_build_start_cmd` output for each arg combination |
| | `test_start_port_out_of_range` | None | `exit_code != 0`, validation error |
| | `test_start_conf_not_found` | None | `exit_code != 0`, validation error (path doesn't exist) |
| | `test_start_dir_is_file_not_dir` | None (create temp file) | `exit_code != 0`, validation error |
| **Status** | `test_status_success` | Mock `Aria2Client` | `exit_code == 0`, stdout "aria2", "Downloading" |
| | `test_status_connection_refused` | Mock `Aria2Client` raise `ConnectionRefusedError` | `exit_code == 1`, stderr "not running" |
| | `test_status_sdk_not_installed` | Patch `import` to fail | `exit_code == 1`, stderr "SKD not installed" |
| | `test_status_stats_unavailable` | Mock `get_global_stat` raise | `exit_code == 0`, version printed, stats skipped |
| | `test_status_unexpected_error` | Mock `Aria2Client` raise generic | `exit_code == 1`, stderr "✗ Error:" |
| | `test_status_port_out_of_range` | None | `exit_code != 0`, validation error |
| **Completion** | `test_completion` | None | `exit_code == 0` for `--show-completion` |

### 6.3 Coverage Target

- **80%** line coverage on `apps/cli/src/cli/` (per `openspec/config.yaml`)
- `apps/cli/tests` already in `testpaths` and `apps/cli/src` in coverage `source`
- All source files ≤200 lines, all functions ≤20 body lines

### 6.4 Running Tests

```bash
# Full CLI test suite
uv run pytest apps/cli/tests/test_cli.py -v

# With coverage
uv run pytest --cov=apps/cli/src/cli --cov-report=term apps/cli/tests/

# With coverage threshold check
uv run pytest --cov=apps/cli/src/cli --cov-report=term --cov-fail-under=80 apps/cli/tests/
```

---

## 7. Rollout Plan

### 7.1 Implementation Order (dependency-respecting)

| Step | File | Action | Depends On |
|---|---|---|---|
| 1 | `commands/status.py` | Rewrite | Nothing (only imports typer + config) |
| 2 | `commands/start.py` | Rewrite | Nothing (only imports typer + finder + config) |
| 3 | `commands/__init__.py` | Update exports | Steps 1-2 complete |
| 4 | `__init__.py` | Rewrite | Step 3 complete (imports `start_app`, `status_app`) |
| 5 | `test_cli.py` | Create | Steps 1-4 complete |
| 6 | Verify | Run pytest + lint | All steps complete |

### 7.2 Verification Checklist

```
[ ] ruff check apps/cli/src/cli/                          # Zero errors
[ ] ty --strict apps/cli/src/cli/                          # Zero errors (typer is typed)
[ ] uv run pytest apps/cli/tests/test_cli.py -v            # All pass
[ ] uv run pytest --cov=apps/cli/src/cli --cov-fail-under=80 apps/cli/tests/  # ≥80%
[ ] uv run aria2 --help                                    # Shows start, status, check
[ ] uv run aria2 --version                                 # Prints version
[ ] uv run aria2 check                                     # Binary check (if aria2c in PATH)
[ ] uv run aria2 start --help                              # Shows all 6 options
[ ] uv run aria2 status --help                             # Shows all 3 options
```

### 7.3 Rollback

```bash
git checkout HEAD -- \
    apps/cli/src/cli/__init__.py \
    apps/cli/src/cli/commands/__init__.py \
    apps/cli/src/cli/commands/start.py \
    apps/cli/src/cli/commands/status.py
git rm apps/cli/tests/test_cli.py
```

No dependency changes needed — `typer>=0.26.5` was already present pre-migration.

---

## 8. Design Decisions Log

| Decision | Rationale | Alternatives Rejected |
|---|---|---|
| `check` as root `@app.command()` not sub-typer | No sub-subcommands; flat `check` command matches current UX | Separate `check_app = typer.Typer()` — overkill for one command |
| `@app.callback()` stores `ctx.ensure_object(dict)` | Establishes pattern for future global options (`--verbose`) | Skip context setup — adds friction when global options are added |
| `asyncio.run()` wrapper in status (no `AsyncTyper`) | Avoids dependency on `asyncer` package; simple 2-line wrapper | Custom `AsyncTyper` class — adds maintenance burden for 1 async command |
| `_status_impl()` as private coroutine | Clear separation: typer command = sync boundary, impl = async core | Keep async function named `status` — name collision with sync wrapper |
| Remove `version` alias for `check` | Typer/Click don't natively support subcommand aliases; `--version` is better UX | Manual Click `AliasedGroup` — complex, fragile, poor discoverability |
| `find_binary()` unchanged (still uses `sys.exit()`) | Out of scope; `finder.py` is not CLI framework code | Rewrite finder to raise exceptions — increases scope unnecessarily |
| `show_envvar=True` not on start options | `ARIA2_SECRET` would be nice but port/dir from envvar is unusual for a start command | Add envvar for all options — over-configures; secrets are the natural envvar use case |
| `Annotated[T, typer.Option(...)]` syntax | Compatible with both Python ≤3.9 and ≥3.10; explicit about Option vs Argument | Direct `port: int = typer.Option(6800, ...)` — less explicit about whether it's an Option or Argument |
| No `help` on `typer.Typer()` instances | Help comes from function docstrings; explicit `help=` on `add_typer()` | Duplicate help strings — violates DRY |
| `pretty_exceptions_short=True` | Short tracebacks are sufficient for CLI users; full tracebacks are overwhelming | Full tracebacks — useful for developers but hostile for end users |
| Keep `__main__.py` unchanged | Entry point contract preserved; `pyproject.toml` `[project.scripts]` continues working | Rewrite __main__.py — unnecessary risk |
| Single PR (no chain) | ~200 changed lines fits 400-line review budget; files are cohesive | Multi-PR chain — overhead for tightly-coupled files |

---

## Appendix A: Option Mapping — argparse → typer

### Start command

| Argparse | Typer |
|---|---|
| `-p`/`--port`, `type=int`, `default=DEFAULT_PORT` | `port: Annotated[int, Option("--port", "-p", min=1024, max=65535)] = DEFAULT_PORT` |
| `-s`/`--secret`, `help="RPC secret token"` | `secret: Annotated[str \| None, Option("--secret", "-s")] = None` |
| `--listen-all`, `action="store_true"` | `listen_all: Annotated[bool, Option("--listen-all")] = False` |
| `-d`/`--dir`, `help="Download directory"` | `dir: Annotated[Path \| None, Option("--dir", "-d", dir_okay=True, file_okay=False)] = None` |
| `-c`/`--conf`, `type=Path` | `conf: Annotated[Path \| None, Option("--conf", "-c", exists=True, dir_okay=False)] = None` |
| `--daemon`, `action="store_true"` | `daemon: Annotated[bool, Option("--daemon")] = False` |

### Status command

| Argparse | Typer |
|---|---|
| `--host`, `default=DEFAULT_HOST` | `host: Annotated[str, Option("--host")] = DEFAULT_HOST` |
| `-p`/`--port`, `type=int`, `default=DEFAULT_PORT` | `port: Annotated[int, Option("--port", "-p", min=1024, max=65535)] = DEFAULT_PORT` |
| `-s`/`--secret` | `secret: Annotated[str \| None, Option("--secret", "-s")] = None` |

---

## Appendix B: Deleted Code

The following are removed entirely:

| Item | Location | Reason |
|---|---|---|
| `_add_start_parser()` | `__init__.py` | Replaced by `app.add_typer(start_app, name="start")` |
| `_add_check_parser()` | `__init__.py` | Replaced by `@app.command() def check()` |
| `_add_status_parser()` | `__init__.py` | Replaced by `app.add_typer(status_app, name="status")` |
| `argparse` import | `__init__.py` | Replaced by `typer` |
| `asyncio` import | `__init__.py` | No longer needed (was for lambda wrapper) |
| `sys` import | `__init__.py` | Replaced by `typer.Exit` |
| `cmd_start` export | `commands/__init__.py` | Replaced by `start_app` |
| `cmd_status` export | `commands/__init__.py` | Replaced by `status_app` |
| `args: argparse.Namespace` pattern | `commands/start.py`, `commands/status.py` | Replaced by typed parameters |
| `print()` calls | All CLI files | Replaced by `typer.echo()` |
| `sys.exit("msg")` calls | `commands/status.py` | Replaced by `typer.echo(err=True)` + `raise typer.Exit(code=1)` |
| `aliases=["version"]` on check parser | `__init__.py` | Removed — use `aria2 --version` instead |
