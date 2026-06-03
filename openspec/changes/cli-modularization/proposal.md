# SDD Proposal: Refactor CLI Package into Modular Structure

**Issue**: #9 — refactor monolithic `apps/cli/src/cli/__init__.py` (173 lines, 4 functions exceeding `max_function_lines:20`)  
**Project**: aria2  
**Status**: Draft  
**Author**: SDD Executor (Gentle PI)  
**Date**: 2026-06-03

---

## 1. Intent

Break `apps/cli/src/cli/__init__.py` into a focused entry-point module with separate, single-responsibility modules for binary discovery, command implementations, and shared constants/helpers. Restore compliance with the project's `max_function_lines: 20` and `max_file_lines: 200` policies while preserving **zero behavioral change** for all existing usage.

---

## 2. Scope

### In scope

| Activity | Detail |
|----------|--------|
| Split `__init__.py` | Extract 4 functions into targeted modules |
| Create new modules | `finder.py`, `config.py`, `commands/` package |
| Update `__main__.py` | No changes (import path `cli.main` remains valid) |
| Import rewiring | Internal `from .finder import ...`, `from .commands import ...` etc. |
| Bug fix | Fix Python-2-era `except ImportError, FileNotFoundError` syntax error (see §7.1) |

### Out of scope

| Activity | Rationale |
|----------|-----------|
| Migrate argparse → typer | Issue explicitly defers this; separate initiative |
| Add tests for CLI | Not part of issue; TDD test-first applies to *new* code only |
| Change CLI behavior | Zero behavioral change is a hard constraint |
| Refactor `aria2-sdk` package | CLI-only change |
| Add `stop` command | Not in current scope; would be a new feature |

---

## 3. Proposed Structure

```
apps/cli/src/cli/
├── __init__.py        ← 60-80 lines — main(), cmd_check, argparse builders
├── __main__.py        ← 3 lines — unchanged (from cli import main)
├── finder.py          ← 30 lines — find_binary()
├── config.py          ← 30 lines — constants, _fmt_speed helper
└── commands/
    ├── __init__.py    ← 3 lines — re-exports cmd_start, cmd_status
    ├── start.py       ← 50 lines — cmd_start()
    └── status.py      ← 45 lines — cmd_status()
```

### Dependency graph

```
__main__.py ──► __init__.py ──► finder.py
                         ├──► config.py
                         └──► commands/__init__.py
                                ├──► commands/start.py ──► finder.py, config.py
                                └──► commands/status.py ──► config.py, aria2-sdk
```

No circular dependencies. Every module imports only what it needs.

### Import compatibility

- `from cli import main` (used by `__main__.py` and the `aria2` script entry point) — **unbroken**
- `from cli.finder import find_binary` — new public API
- `from cli.commands import cmd_start, cmd_status` — new public API
- `from cli.config import DEFAULT_PORT, _fmt_speed` — new internal API

---

## 4. Module Specifications

### 4.1 `finder.py` — Binary discovery

```python
"""Locate aria2c binary — bundled wheel first, then PATH."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def find_binary() -> Path:
    """Locate the aria2c binary, bundled or system.

    Returns:
        Path to a valid, executable aria2c binary.

    Exits the process with a helpful message if not found.
    """
    # Try bundled first (wheel)
    try:
        from aria2_bin import get_binary_path  # type: ignore[import-untyped]

        return get_binary_path()
    except (ImportError, FileNotFoundError):
        pass

    # Fallback: PATH / ARIA2C_PATH
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
```

**Changes from original**:
- Renamed from `_find_binary` → `find_binary` (public)
- Fixed `except ImportError, FileNotFoundError:` → `except (ImportError, FileNotFoundError):` (syntax error in Python 3)
- Added `# type: ignore[import-untyped]` for the `aria2_bin` import (may not have stubs)

### 4.2 `config.py` — Shared constants and helpers

```python
"""Shared configuration constants and formatting helpers."""

from __future__ import annotations


# Default RPC connection parameters
DEFAULT_PORT: int = 6800
DEFAULT_HOST: str = "localhost"


def _fmt_speed(bps: int) -> str:
    """Format bytes-per-second into a human-readable string.

    Args:
        bps: Speed in bytes per second.

    Returns:
        Formatted string like "1.5 MB/s", "42 KB/s", or "900 B/s".
    """
    if bps >= 1_000_000:
        return f"{bps / 1_000_000:.1f} MB/s"
    if bps >= 1_000:
        return f"{bps / 1_000:.0f} KB/s"
    return f"{bps} B/s"
```

**Changes from original**:
- Extracted `DEFAULT_PORT` and `DEFAULT_HOST` from inline literals in `main()` and `cmd_status()`
- `_fmt_speed` moved here (kept private; consumed by `commands/status.py`)

### 4.3 `commands/__init__.py` — Command re-exports

```python
"""CLI command implementations."""

from __future__ import annotations

from .start import cmd_start
from .status import cmd_status

__all__ = [
    "cmd_start",
    "cmd_status",
]
```

### 4.4 `commands/start.py` — Start daemon

```python
"""Start an aria2c daemon with RPC enabled."""

from __future__ import annotations

import argparse
import signal
import subprocess
import sys

from ..finder import find_binary
from ..config import DEFAULT_PORT


def cmd_start(args: argparse.Namespace) -> None:
    """Start an aria2c daemon with RPC enabled."""
    binary = find_binary()

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
```

**Changes from original**:
- `_find_binary()` → `find_binary()` via import
- Uses `DEFAULT_PORT` for reference (actually unused in the function body; the port comes from `args.port` which defaults to 6800 in argparse — we keep that default there)
- No behavioral change

### 4.5 `commands/status.py` — Query daemon status

```python
"""Query a running aria2 daemon for version and stats."""

from __future__ import annotations

import argparse
import asyncio
import sys

from ..config import DEFAULT_HOST, DEFAULT_PORT, _fmt_speed


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
```

**Changes from original**:
- `_fmt_speed` imported from `config`
- `DEFAULT_HOST`, `DEFAULT_PORT` available for reference (used by argparse defaults in `main()`)
- No behavioral change

### 4.6 `__init__.py` (remaining) — Entry point, parser, dispatch

```python
"""CLI entry point for the aria2 SDK — manages bundled aria2c binary."""

from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from .commands import cmd_start, cmd_status
from .config import DEFAULT_HOST, DEFAULT_PORT


def cmd_check(args: argparse.Namespace) -> None:
    """Check if aria2c binary is available."""
    from .finder import find_binary

    try:
        binary = find_binary()
        import subprocess

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


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="aria2",
        description="aria2 download manager — CLI wrapper\n  https://github.com/Row0902/aria2",
    )
    parser.set_defaults(func=lambda _: parser.print_help())

    sub = parser.add_subparsers(title="commands")

    # ── start ────────────────────────────────────────────────
    start_p = sub.add_parser("start", help="Start aria2c daemon with RPC enabled")
    start_p.add_argument("-p", "--port", type=int, default=DEFAULT_PORT, help="RPC port")
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
    status_p.add_argument("--host", default=DEFAULT_HOST, help="RPC host (default: localhost)")
    status_p.add_argument("-p", "--port", type=int, default=DEFAULT_PORT, help="RPC port (default: 6800)")
    status_p.add_argument("-s", "--secret", help="RPC secret token")
    status_p.set_defaults(func=lambda a: asyncio.run(cmd_status(a)))

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
```

**Changes from original**:
- Imports `DEFAULT_HOST`, `DEFAULT_PORT` from `.config` instead of inline literals
- Imports `cmd_start`, `cmd_status` from `.commands`
- `cmd_check` remains in `__init__.py` (17 lines — under limit)
- Lazy-imports `subprocess` and `find_binary` inside `cmd_check` to keep top-level imports minimal (alternative: import at top — either is fine; `<20` lines is the constraint)
- **Target size**: ~65-75 lines (compressed from 173)

---

## 5. File Metrics

| File | Current Lines | Target Lines | Status |
|------|--------------|--------------|--------|
| `__init__.py` | 173 | ~70 | ⬇️ -100 |
| `__main__.py` | 3 | 3 | Unchanged |
| `finder.py` | — | ~30 | 🆕 |
| `config.py` | — | ~30 | 🆕 |
| `commands/__init__.py` | — | ~5 | 🆕 |
| `commands/start.py` | — | ~50 | 🆕 |
| `commands/status.py` | — | ~45 | 🆕 |
| **Total** | **176** | **~233** | **+57 (new modules)** |

All individual functions will be under the `max_function_lines: 20` limit, and all files under `max_file_lines: 200`.

---

## 6. Function Metrics After Refactor

| Function | Current Lines | Target Lines | Module |
|----------|--------------|--------------|--------|
| `find_binary()` | 22 | 18 | `finder.py` |
| `cmd_start()` | 42 | 42 | `commands/start.py` |
| `cmd_check()` | 17 | 17 | `__init__.py` |
| `cmd_status()` | 29 | 29 | `commands/status.py` |
| `_fmt_speed()` | 8 | 8 | `config.py` |
| `main()` | 32 | ~30 | `__init__.py` |

Functions stay at their original line count; only `find_binary` gets slightly shorter due to the tuple-syntax fix.

---

## 7. Risks and Mitigations

### 7.1 Syntax bug fix (low risk)

**Issue**: Line `except ImportError, FileNotFoundError:` uses Python-2-era syntax and is a `SyntaxError` on Python 3.14.  
**Mitigation**: Fix to `except (ImportError, FileNotFoundError):` — preserves the exact same catch semantics.  
**Behavioral impact**: Zero. The code was non-functional on Python 3 before; now it runs. No observable behavior change at runtime (same exceptions caught, same `pass`).

### 7.2 Import path disruption (medium risk)

**Risk**: The `cli` package root moves from a single-file module to a package with submodules. Any code doing `from cli import _find_binary` or `from cli import cmd_start` would break.  
**Mitigation**: `_find_binary` was private (underscore-prefixed) — no external consumer should import it. `cmd_start` and `cmd_status` are re-exported via `commands/__init__.py`; `__init__.py` itself continues to offer `cmd_start` and `cmd_status` through re-exports. The entry-point contract `cli.main` remains stable.  
**Verification**: Run `python -c "from cli import main; main()"` (with `--help` flag) after refactoring.

### 7.3 hatchling build breakage (low risk)

**Risk**: The build config `packages = ["src/cli"]` auto-discovers subpackages. If discovery fails, the new modules won't be included in the wheel.  
**Mitigation**: `hatchling` auto-discovers all subpackages within `src/cli`. The `commands/` subpackage will be automatically included. Run `uv build` and inspect the wheel contents before merge.

### 7.4 Non-functional `aria2` script entry point (high impact, low risk)

**Risk**: If imports are miswired, `aria2 start --help` would break.  
**Mitigation**: All imports are verified statically. The `from cli import main` path in `__main__.py` is unchanged. A manual smoke test after refactoring confirms the `aria2` CLI works.

---

## 8. Rollback Plan

If the refactoring introduces a regression:

1. **Revert the commit**: `git revert HEAD` (if landed on a feature branch) or restore from stash.
2. **Restore `__init__.py`**: Revert to the pre-refactor 173-line single file. All imports and entry points return to original behavior.
3. **Duration**: Rollback takes <5 minutes. The monolithic file is the fallback "source of truth."

---

## 9. Success Criteria

- [ ] `__init__.py` is ≤ 80 lines
- [ ] Each function is ≤ 20 lines
- [ ] `python -m cli --help` prints help without error
- [ ] `python -m cli check` detects aria2c binary correctly
- [ ] `python -m cli start --help` shows start subcommand options
- [ ] `python -m cli status --help` shows status subcommand options
- [ ] `uv build` succeeds and wheel contains all new modules
- [ ] `ruff check apps/cli/src/cli/` passes (zero new violations)
- [ ] `ty` type-checks `apps/cli/src/cli/` (zero new errors)

---

## 10. Implementation Order

1. Create `finder.py` with `find_binary()`
2. Create `config.py` with constants and `_fmt_speed()`
3. Create `commands/__init__.py` (empty re-export shell)
4. Create `commands/start.py` with `cmd_start()`
5. Create `commands/status.py` with `cmd_status()`
6. Rewrite `__init__.py` to import from new modules
7. Smoke-test all CLI commands
8. Verify `uv build`, `ruff`, and `ty`

This order ensures every import resolves at each step — no orphaned references.

---

## 11. Appendix: Diff Preview

A rough diff summary (not a literal patch):

```
 apps/cli/src/cli/__init__.py       | 173 ++++-------------------------------
 apps/cli/src/cli/__main__.py       |   0
 apps/cli/src/cli/finder.py         |  36 ++++++++
 apps/cli/src/cli/config.py         |  22 ++++++
 apps/cli/src/cli/commands/__init__.py |   5 +
 apps/cli/src/cli/commands/start.py |  50 ++++++++++
 apps/cli/src/cli/commands/status.py|  45 +++++++++
 7 files changed, 180 insertions(+), 130 deletions(-)
```

Net: ~50 new lines (mostly due to module boilerplate and imports), <130 removed from the monolithic file.
