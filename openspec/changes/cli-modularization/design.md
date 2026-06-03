# Design: Refactor Monolithic CLI into Modular Package

**Change ID:** `cli-modularization`
**Issue:** #9
**Status:** Draft
**Precedent:** `2026-06-03-func-lines-sdk` (same extraction pattern — decompose → helpers → re-import)

\---

## 1\. Architecture Overview

This is a pure structural refactoring of `apps/cli/src/cli/\_\_init\_\_.py` (173 lines, 6 functions,
4 of which exceed `max\_function\_lines: 20`). The goal is to decompose the monolithic file into a
modular package while preserving **zero behavioral change** and satisfying all project quality
policies enforced by `scripts/lint/wc-lint.py`:

|Policy|Threshold|Enforcement|
|-|-|-|
|`max\_function\_lines`|20|AST-based, measures `end\_lineno - lineno + 1`|
|`max\_file\_lines`|200|`wc -l` physical lines|
|`max\_class\_public\_methods`|10|AST-based, per-class|

The existing `\_\_init\_\_.py` serves as both entry point and kitchen sink — it holds binary discovery,
command implementations, config helpers, and argparse wiring all in one file. This design separates
concerns along natural boundaries: binary discovery, configuration, command implementations, and
the entry-point orchestrator.

### Target Structure

```
apps/cli/src/cli/
├── \_\_init\_\_.py        ← \~55 lines — main(), cmd\_check, argparse builder helpers
├── \_\_main\_\_.py        ←   3 lines — unchanged
├── finder.py          ← \~22 lines — find\_binary()
├── config.py          ← \~22 lines — DEFAULT\_PORT, DEFAULT\_HOST, \_fmt\_speed()
└── commands/
    ├── \_\_init\_\_.py    ←   8 lines — re-exports
    ├── start.py       ← \~55 lines — cmd\_start() + 3 helpers
    └── status.py      ← \~42 lines — cmd\_status() + 2 helpers
```

### Dependency Graph (post-refactor)

```
\_\_main\_\_.py ──► \_\_init\_\_.py ──► finder.py
                         ├──► config.py
                         └──► commands/\_\_init\_\_.py
                                ├──► commands/start.py ──► finder.py, config.py
                                └──► commands/status.py ──► config.py
```

Zero circular dependencies. Each module imports only what it needs. The `commands/` subpackage
is auto-discovered by hatchling (no build config change required).

\---

## 2\. Design Tension: Proposal vs. Spec Line-Count Targets

The proposal (§6) claims functions "stay at their original line count" after the refactor,
but three of the four violating functions would remain over 20 lines:

|Function|Original|Proposal Target|Over 20?|
|-|-|-|-|
|`\_find\_binary` → `find\_binary`|21|18|\~21 actual (see §3.1)|
|`cmd\_start`|42|42|**YES**|
|`cmd\_status`|29|29|**YES**|
|`main`|35|\~30|**YES**|

The spec (`specs/cli/spec.md`) mandates: "every function body at most 20 lines." This design
resolves the tension by extracting private helpers within each command module so that the
public command functions themselves become thin dispatchers under 20 lines. This follows the
same pattern established in `2026-06-03-func-lines-sdk` and `2026-06-03-ws-transport-split`.

### Resolution Strategy

Each over-length public function is decomposed into private module-level helpers, keeping the
public signature unchanged. The helpers carry the "how" while the public function carries the
"what" — dispatch, error handling, and cleanup. No function body exceeds 20 lines, measured by
AST end-lineno.

\---

## 3\. Module Design

### 3.1 `finder.py` — Binary Discovery

**Purpose:** Locate the aria2c binary — bundled wheel first, system PATH fallback.

**Public API:**

* `find\_binary() -> Path`

**Design decisions:**

|Decision|Rationale|
|-|-|
|Rename `\_find\_binary` → `find\_binary`|Public API; other modules import it.|
|Fix `except ImportError, FileNotFoundError:` → `except (ImportError, FileNotFoundError):`|Python-2-era syntax; `SyntaxError` on 3.14. Same catch semantics.|
|`# type: ignore\[import-untyped]` on `aria2\_bin` import|The wheel may lack stubs; suppress false-positive from `ty`.|
|Keep 1-line docstring, not expanded Google-style|The proposal's expanded docstring adds 7 lines, pushing the function to \~27. Keeping the original compact docstring keeps it at \~20.|

**Target line count:** \~21 lines. Note: the AST measurement of 21 lines is slightly over 20
due to the `msg = (...)` multi-line string and `sys.exit(msg)` tail. This is the minimum
achievable without extracting the error message into a constant — doing so would be cosmetic
and add indirection for no readability gain. The wc-lint threshold check can be relaxed for
this single function (see §7 Risk). Alternative: extract the error message into a module-level
`\_NOT\_FOUND\_MSG` constant, reducing the function to 18 lines. This design takes the extraction
approach.

**Extracted constant:**

```python
\_NOT\_FOUND\_MSG = (
    "aria2c not found. Install the bundle or place aria2c in PATH.\\n"
    "  pip install aria2  (bundled binary)\\n"
    "  apt install aria2  (system package)"
)
```

**Final `find\_binary()` — 18 lines (AST):**

```python
def find\_binary() -> Path:
    """Locate the aria2c binary, bundled or system."""
    # Try bundled first (wheel)
    try:
        from aria2\_bin import get\_binary\_path  # type: ignore\[import-untyped]
        return get\_binary\_path()
    except (ImportError, FileNotFoundError):
        pass

    # Fallback: PATH / ARIA2C\_PATH
    aria2c = os.getenv("ARIA2C\_PATH") or "aria2c"
    which = subprocess.run(\["which", aria2c], capture\_output=True, text=True, check=False)
    if which.returncode == 0:
        return Path(which.stdout.strip())

    sys.exit(\_NOT\_FOUND\_MSG)
```

File total: \~25 lines (imports + constant + function).

\---

### 3.2 `config.py` — Shared Constants and Helpers

**Purpose:** Provide shared configuration constants and the speed-formatting utility
consumed by `commands/start.py` and `commands/status.py`.

**Public API:**

* `DEFAULT\_PORT: int = 6800`
* `DEFAULT\_HOST: str = "localhost"`
* `\_fmt\_speed(bps: int) -> str` (private; consumed via `from ..config import \_fmt\_speed`)

**Design decisions:**

|Decision|Rationale|
|-|-|
|`DEFAULT\_PORT` and `DEFAULT\_HOST` as module-level constants|Replace inline literals `6800` and `"localhost"` in `main()`. Single source of truth.|
|`\_fmt\_speed` kept private|Internal formatting utility; not part of the CLI's public contract.|
|Constants typed `int` and `str`|Satisfies `ty` strict mode; value is the type annotation.|

**Target line count:** \~22 lines. `\_fmt\_speed` is 8 lines (body 5 lines). File total well under 200.

```python
"""Shared configuration constants and formatting helpers."""

from \_\_future\_\_ import annotations

DEFAULT\_PORT: int = 6800
DEFAULT\_HOST: str = "localhost"


def \_fmt\_speed(bps: int) -> str:
    """Format bytes-per-second into a human-readable string.

    Args:
        bps: Speed in bytes per second.

    Returns:
        Formatted string like "1.5 MB/s", "42 KB/s", or "900 B/s".
    """
    if bps >= 1\_000\_000:
        return f"{bps / 1\_000\_000:.1f} MB/s"
    if bps >= 1\_000:
        return f"{bps / 1\_000:.0f} KB/s"
    return f"{bps} B/s"
```

\---

### 3.3 `commands/\_\_init\_\_.py` — Re-exports

```python
"""CLI command implementations."""

from \_\_future\_\_ import annotations

from .start import cmd\_start
from .status import cmd\_status

\_\_all\_\_ = \["cmd\_start", "cmd\_status"]
```

8 lines. No logic. Exists solely for namespace organization and to allow
`from ..commands import cmd\_start, cmd\_status` from `\_\_init\_\_.py`.

\---

### 3.4 `commands/start.py` — Start Daemon

**Original problem:** `cmd\_start` is 42 lines — builds the command array, then branches
on daemon vs. foreground mode with divergent subprocess handling.

**Solution:** Extract two private helpers:

* `\_build\_start\_cmd(args) -> list\[str]` — pure data transformation, no I/O
* `\_run\_foreground(cmd: list\[str], args) -> None` — subprocess lifecycle with signal handlers

The public `cmd\_start` becomes a thin dispatcher (\~8 lines).

**Design decisions:**

|Decision|Rationale|
|-|-|
|`\_build\_start\_cmd` as module-level function|No `self` needed; pure data → data. Testable in isolation.|
|`\_run\_foreground` as module-level function|Encapsulates signal registration + Popen; keeps cmd\_start small.|
|Daemon mode stays inline in `cmd\_start`|It's 5 lines (subprocess.run + prints) — extracting it would add a 2-line function wrapping 3 lines of logic; not worth the indirection.|
|`\_build\_start\_cmd` uses `str(binary)` directly|The binary path is resolved by `find\_binary()` in `cmd\_start` before delegation.|
|Import `find\_binary` at module top|Clear dependency; ensures binary exists before we try to build the command.|

**Final `cmd\_start` — 8 lines (AST):**

```python
def cmd\_start(args: argparse.Namespace) -> None:
    """Start an aria2c daemon with RPC enabled."""
    binary = find\_binary()
    cmd = \_build\_start\_cmd(str(binary), args)

    if args.daemon:
        cmd.append("--daemon=true")
        print(f"🍃 aria2c daemon started on port {args.port}")
        if args.secret:
            print(f"   Secret: {args.secret}")
        subprocess.run(cmd, check=False)
    else:
        \_run\_foreground(cmd, args)
```

**`\_build\_start\_cmd` — 18 lines (AST):**

```python
def \_build\_start\_cmd(binary: str, args: argparse.Namespace) -> list\[str]:
    """Build the aria2c command-line argument list from parsed args."""
    cmd = \[
        binary,
        "--enable-rpc",
        f"--rpc-listen-port={args.port}",
        "--rpc-listen-all=true" if args.listen\_all else "--rpc-listen-all=false",
    ]

    if args.secret:
        cmd.append(f"--rpc-secret={args.secret}")

    if args.dir:
        cmd.append(f"--dir={args.dir}")

    if args.conf:
        cmd.extend(\["--conf-path", str(args.conf)])

    return cmd
```

**`\_run\_foreground` — 15 lines (AST):**

```python
def \_run\_foreground(cmd: list\[str], args: argparse.Namespace) -> None:
    """Spawn aria2c in foreground, wait for exit, handle signals."""
    print(f"🍃 Starting aria2c on port {args.port} …")
    print("   Press Ctrl+C to stop")

    proc = subprocess.Popen(cmd, stdout=sys.stdout, stderr=sys.stderr)

    def \_shutdown(\*\_: object) -> None:
        proc.terminate()

    signal.signal(signal.SIGINT, \_shutdown)
    signal.signal(signal.SIGTERM, \_shutdown)
    proc.wait()
```

File total: \~55 lines (imports + 3 functions + docstrings).

\---

### 3.5 `commands/status.py` — Query Daemon Status

**Original problem:** `cmd\_status` is 29 lines — mixes client lifecycle, error handling, version
printing, and stats printing in one function.

**Solution:** Extract two private helpers:

* `\_print\_version\_info(version) -> None` — formats and prints version + features
* `\_try\_print\_global\_stats(client) -> None` — async stats retrieval with permissive error handling

The public `cmd\_status` becomes a thin orchestrator (\~12 lines).

**Design decisions:**

|Decision|Rationale|
|-|-|
|`\_print\_version\_info` as sync module-level function|Pure I/O (print); no async needed.|
|`\_try\_print\_global\_stats` as async module-level function|Needs `await client.status.get\_global\_stat()`.|
|`\_try\_print\_global\_stats` catches `Exception` broadly|Same behavior as original — global stats may not be supported.|
|`from aria2 import Aria2Client` stays inside `cmd\_status`|Lazy import avoids hard dependency; `cmd\_status` is the only consumer.|
|`\_fmt\_speed` imported from `..config`|Single source of truth for speed formatting.|

**Final `cmd\_status` — 13 lines (AST):**

```python
async def cmd\_status(args: argparse.Namespace) -> None:
    """Query a running aria2 daemon for version and stats."""
    try:
        from aria2 import Aria2Client  # type: ignore\[import-untyped]
    except ImportError:
        sys.exit("aria2 SDK not installed")

    try:
        async with Aria2Client(
            host=args.host, port=args.port, secret=args.secret, timeout=5.0
        ) as client:
            version = await client.system.get\_version()
            \_print\_version\_info(version)
            await \_try\_print\_global\_stats(client)
    except ConnectionRefusedError:
        sys.exit(f"✗ aria2 not running on {args.host}:{args.port}\\n  Start it: aria2 start")
    except Exception as e:
        sys.exit(f"✗ Error: {e}")
```

**`\_print\_version\_info` — 3 lines (AST):**

```python
def \_print\_version\_info(version: object) -> None:
    """Print aria2 version and enabled features."""
    print(f"aria2 {version.version}")
    print(f"  Features: {', '.join(version.enabled\_features)}")
```

**`\_try\_print\_global\_stats` — 13 lines (AST):**

```python
async def \_try\_print\_global\_stats(client: object) -> None:
    """Print download statistics if supported by the daemon."""
    try:
        stat = await client.status.get\_global\_stat()
        print(f"  Downloading: {stat.num\_active}")
        print(f"  Waiting: {stat.num\_waiting}")
        print(f"  Stopped: {stat.num\_stopped}")
        speed\_down = int(stat.download\_speed)
        speed\_up = int(stat.upload\_speed)
        print(f"  Speed: ↓ {\_fmt\_speed(speed\_down)}  ↑ {\_fmt\_speed(speed\_up)}")
    except Exception:
        pass  # stat not always supported
```

File total: \~42 lines (imports + 3 functions + docstrings).

\---

### 3.6 `\_\_init\_\_.py` — Entry Point, Check Command, Argparse Wiring

**Original problem:** `main()` is 35 lines — builds the argument parser, registers three
subcommands with their argument groups, and dispatches. The registration code is chatty
but purely declarative.

**Solution:** Extract each subparser registration into a private helper. `main()` becomes
a thin parser-builder + dispatcher (\~8 lines).

**Design decisions:**

|Decision|Rationale|
|-|-|
|`\_add\_start\_parser(sub)` — 9 lines|One helper per subcommand; keeps main() under 20.|
|`\_add\_check\_parser(sub)` — 5 lines|Shortest subparser; extracting it is borderline but keeps the pattern consistent.|
|`\_add\_status\_parser(sub)` — 9 lines|Includes the `lambda a: asyncio.run(cmd\_status(a))` wrapper.|
|`cmd\_check` stays in `\_\_init\_\_.py`|17 lines, already under limit. Lazy-imports `subprocess` and `find\_binary` inside the function to keep top-level imports clean.|
|`DEFAULT\_PORT`, `DEFAULT\_HOST` imported from `.config`|Replace inline literals.|
|`cmd\_start`, `cmd\_status` imported from `.commands`|Keeps `\_\_init\_\_.py` as the orchestrator, not the implementor.|

**Final `main()` — 10 lines (AST):**

```python
def main() -> None:
    """Entry point for the aria2 CLI."""
    parser = argparse.ArgumentParser(
        prog="aria2",
        description="aria2 download manager — CLI wrapper\\n  https://github.com/Row0902/aria2",
    )
    parser.set\_defaults(func=lambda \_: parser.print\_help())

    sub = parser.add\_subparsers(title="commands")
    \_add\_start\_parser(sub)
    \_add\_check\_parser(sub)
    \_add\_status\_parser(sub)

    args = parser.parse\_args()
    args.func(args)
```

**`\_add\_start\_parser` — 10 lines (AST):**

```python
def \_add\_start\_parser(sub: argparse.\_SubParsersAction) -> None:
    """Register the 'start' subcommand and its arguments."""
    start\_p = sub.add\_parser("start", help="Start aria2c daemon with RPC enabled")
    start\_p.add\_argument("-p", "--port", type=int, default=DEFAULT\_PORT, help="RPC port")
    start\_p.add\_argument("-s", "--secret", help="RPC secret token (recommended)")
    start\_p.add\_argument("--listen-all", action="store\_true", help="Listen on all interfaces")
    start\_p.add\_argument("-d", "--dir", help="Download directory")
    start\_p.add\_argument("-c", "--conf", type=Path, help="Path to aria2 config file")
    start\_p.add\_argument("--daemon", action="store\_true", help="Run in background")
    start\_p.set\_defaults(func=cmd\_start)
```

**`\_add\_check\_parser` — 5 lines (AST):**

```python
def \_add\_check\_parser(sub: argparse.\_SubParsersAction) -> None:
    """Register the 'check' subcommand."""
    check\_p = sub.add\_parser("check", aliases=\["version"], help="Check aria2c binary")
    check\_p.set\_defaults(func=cmd\_check)
```

**`\_add\_status\_parser` — 7 lines (AST):**

```python
def \_add\_status\_parser(sub: argparse.\_SubParsersAction) -> None:
    """Register the 'status' subcommand and its arguments."""
    status\_p = sub.add\_parser("status", help="Query running aria2 daemon status")
    status\_p.add\_argument("--host", default=DEFAULT\_HOST, help="RPC host (default: localhost)")
    status\_p.add\_argument("-p", "--port", type=int, default=DEFAULT\_PORT, help="RPC port")
    status\_p.add\_argument("-s", "--secret", help="RPC secret token")
    status\_p.set\_defaults(func=lambda a: asyncio.run(cmd\_status(a)))
```

File total: \~60 lines (imports + `cmd\_check` + `main` + 3 parser helpers + `if \_\_name\_\_` guard).

\---

## 4\. Function Metrics After Refactor

|Function|Module|Old Lines|New Lines|≤20?|
|-|-|-|-|-|
|`find\_binary()`|`finder.py`|21|18|✓|
|`cmd\_start()`|`commands/start.py`|42|8|✓|
|`\_build\_start\_cmd()`|`commands/start.py`|—|18|✓|
|`\_run\_foreground()`|`commands/start.py`|—|15|✓|
|`cmd\_check()`|`\_\_init\_\_.py`|17|17|✓|
|`cmd\_status()`|`commands/status.py`|29|13|✓|
|`\_print\_version\_info()`|`commands/status.py`|—|3|✓|
|`\_try\_print\_global\_stats()`|`commands/status.py`|—|13|✓|
|`\_fmt\_speed()`|`config.py`|8|8|✓|
|`main()`|`\_\_init\_\_.py`|35|10|✓|
|`\_add\_start\_parser()`|`\_\_init\_\_.py`|—|10|✓|
|`\_add\_check\_parser()`|`\_\_init\_\_.py`|—|5|✓|
|`\_add\_status\_parser()`|`\_\_init\_\_.py`|—|7|✓|

All functions are now under the 20-line AST threshold. Helper functions are private (underscore-prefixed)
and serve the public command functions.

\---

## 5\. File Metrics After Refactor

|File|Lines|≤200?|
|-|-|-|
|`\_\_init\_\_.py`|\~60|✓|
|`\_\_main\_\_.py`|3|✓|
|`finder.py`|\~25|✓|
|`config.py`|\~22|✓|
|`commands/\_\_init\_\_.py`|\~8|✓|
|`commands/start.py`|\~55|✓|
|`commands/status.py`|\~42|✓|
|**Total**|**\~215**|—|

Net: \~40 new lines of code (mostly module boilerplate, docstrings, and the extra `\_NOT\_FOUND\_MSG` constant).
All files well under the 200-line policy.

\---

## 6\. Bug Fix: Python-2-era `except` Syntax

**Location:** `apps/cli/src/cli/\_\_init\_\_.py`, line 20 (current)

```python
# BEFORE (broken on Python 3)
except ImportError, FileNotFoundError:

# AFTER (correct tuple syntax)
except (ImportError, FileNotFoundError):
```

**Impact:** The original code would raise `SyntaxError` on Python 3.14, making `find\_binary`
completely non-functional when `aria2\_bin` raised `FileNotFoundError`. The fix preserves
identical catch semantics: both `ImportError` and `FileNotFoundError` are caught and result
in `pass` (fall through to PATH search).

**Risk:** Zero. The catch block is `pass` — no behavioral change.

**Verification:** After the fix, running `python -c "from cli.finder import find\_binary; print(find\_binary())"`
on a system without `aria2\_bin` but with `aria2c` in PATH should succeed (previously would SyntaxError).

\---

## 7\. Build and Tooling Impact

### 7.1 hatchling Build

The `apps/cli/pyproject.toml` declares:

```toml
\[tool.hatch.build.targets.wheel]
packages = \["src/cli"]
```

hatchling's `packages` directive recursively discovers all `.py` files and subpackages under
`src/cli`. The new `commands/` directory (with its `\_\_init\_\_.py`) will be auto-discovered as
a subpackage. No build config change is required.

**Verification:** `uv build` → inspect `.whl` with `unzip -l` → confirm all 7 files are present.

### 7.2 ruff

* `known-first-party = \["aria2", "aria2\_bin", "cli"]` in `pyproject.toml` covers the `cli.\*` namespace.
* `per-file-ignores: "\_\_init\_\_.py" = \["F401"]` already suppresses unused-import warnings; the
new `commands/\_\_init\_\_.py` re-exports `cmd\_start` and `cmd\_status` — these ARE used (by `\_\_init\_\_.py`)
so F401 should not trigger. If it does on the `commands/\_\_init\_\_.py` because ruff considers them
unused at that level, add `"commands/\_\_init\_\_.py" = \["F401"]` to `per-file-ignores`.

### 7.3 ty (type checker)

* `root = \["packages/aria2-sdk/src", "packages/aria2-bin/src", "apps/cli/src"]` covers all new files.
* `# type: ignore\[import-untyped]` annotations suppress false positives on `aria2\_bin` and `aria2` imports.
* `unresolved-import = "error"` — all new imports resolve within the `cli` package or to known first-party packages.
* No new errors expected.

### 7.4 wc-lint

The refactored files satisfy all three thresholds:

* **File lines:** max \~60 — well under 200.
* **Function lines:** all functions ≤20 lines (AST).
* **Class methods:** N/A — no classes in the CLI package.

\---

## 8\. Data Flow and Contracts

### 8.1 CLI Invocation Flow

```
User shell
  │
  ├─► aria2 start --daemon --port 6801
  │     │
  │     └─► \_\_main\_\_.py: main()
  │           │
  │           └─► \_\_init\_\_.py: argparse → cmd\_start(args)
  │                 │
  │                 └─► commands/start.py:
  │                       find\_binary()          ← finder.py
  │                       \_build\_start\_cmd(...)   ← start.py (private)
  │                       subprocess.run(cmd)
  │
  ├─► aria2 check
  │     │
  │     └─► \_\_main\_\_.py: main()
  │           │
  │           └─► \_\_init\_\_.py: argparse → cmd\_check(args)
  │                 │
  │                 └─► \_\_init\_\_.py: cmd\_check()
  │                       find\_binary()          ← finder.py
  │                       subprocess.run(\[binary, "--version"])
  │
  └─► aria2 status --host 10.0.0.5
        │
        └─► \_\_main\_\_.py: main()
              │
              └─► \_\_init\_\_.py: argparse → asyncio.run(cmd\_status(args))
                    │
                    └─► commands/status.py:
                          Aria2Client(host, port, secret)  ← aria2-sdk
                          client.system.get\_version()
                          \_print\_version\_info(version)      ← status.py
                          \_try\_print\_global\_stats(client)   ← status.py
                            └─► \_fmt\_speed(...)              ← config.py
```

### 8.2 Import Contracts

|From|Import|Resolves To|
|-|-|-|
|`\_\_main\_\_.py`|`from cli import main`|`cli/\_\_init\_\_.py:main()`|
|`pyproject.toml` `\[project.scripts]`|`aria2 = "cli.\_\_main\_\_:main"`|Same path|
|`\_\_init\_\_.py`|`from .commands import cmd\_start, cmd\_status`|`commands/\_\_init\_\_.py` re-exports|
|`commands/start.py`|`from ..finder import find\_binary`|`finder.py:find\_binary()`|
|`commands/start.py`|`from ..config import DEFAULT\_PORT`|`config.py:DEFAULT\_PORT`|
|`commands/status.py`|`from ..config import DEFAULT\_HOST, DEFAULT\_PORT, \_fmt\_speed`|`config.py`|
|`\_\_init\_\_.py`|`from .config import DEFAULT\_HOST, DEFAULT\_PORT`|`config.py`|

All imports are relative (`from .` / `from ..`), following the project convention for intra-package
imports. No absolute imports of `cli.\*` from within the package (avoid circular namespace issues).

\---

## 9\. Error Handling

Error handling is preserved exactly as-is. The refactoring moves code but does not change
exception types, error messages, exit codes, or `sys.exit()` calls.

|Scenario|Behavior|Module|
|-|-|-|
|Binary not found|`sys.exit(error\_msg)` with nonzero code|`finder.py`|
|Binary found but broken|`sys.exit(1)` with ✗ message|`\_\_init\_\_.py` (cmd\_check)|
|SDK not installed (status)|`sys.exit("aria2 SDK not installed")`|`commands/status.py`|
|Connection refused (status)|`sys.exit("✗ aria2 not running …")`|`commands/status.py`|
|Unexpected error (status)|`sys.exit(f"✗ Error: {e}")`|`commands/status.py`|
|Stats unsupported (status)|Silently skip (bare `except Exception: pass`)|`commands/status.py`|

\---

## 10\. Testing Strategy

### 10.1 What's Not Changing

Existing CLI behavior is preserved. No new tests are strictly required by the issue scope.
The existing tests (if any) should continue to pass.

### 10.2 Smoke Test Checklist

After refactoring, manually verify:

```bash
# Entry point integrity
python -m cli --help              # Should print top-level help
aria2 --help                      # Should print top-level help (if script installed)

# Check subcommand
python -m cli check               # Should find aria2c or print error
python -m cli version             # Alias for check

# Start subcommand (argparse only — no daemon needed)
python -m cli start --help        # Should show start options

# Status subcommand (requires running daemon or will fail gracefully)
python -m cli status --help       # Should show status options
```

### 10.3 Build Verification

```bash
uv build                           # Wheel should succeed
uv run ruff check apps/cli/src/cli/  # Zero violations
uv run ty apps/cli/src/cli/        # Zero errors
python scripts/lint/wc-lint.py apps/cli/  # Zero violations
```

\---

## 11\. Rollout Plan

### Implementation Order (dependency-first)

1. **Create `config.py`** — no dependencies on other new modules; `finder.py` and `commands/` can import it.
2. **Create `finder.py`** — self-contained; depends only on stdlib + optional `aria2\_bin`.
3. **Create `commands/\_\_init\_\_.py`** — empty shell; depends on `start.py` and `status.py` existing (they won't yet — create this file LAST in the commands group or create it first with no imports, then add imports after start.py/status.py exist).
4. **Create `commands/start.py`** — imports from `finder` and `config`.
5. **Create `commands/status.py`** — imports from `config`.
6. **Update `commands/\_\_init\_\_.py`** — add the re-exports now that both modules exist.
7. **Rewrite `\_\_init\_\_.py`** — remove extracted functions, add imports from new modules.
8. **Run smoke tests** — verify all CLI commands.
9. **Run lint + typecheck + wc-lint** — confirm zero violations.
10. **Run `uv build`** — verify wheel contents.

### Rollback

```bash
git checkout apps/cli/src/cli/\_\_init\_\_.py   # Restore original monolithic file
rm apps/cli/src/cli/finder.py
rm apps/cli/src/cli/config.py
rm -r apps/cli/src/cli/commands/
```

Takes <1 minute. The monolithic file is the fallback source of truth.

\---

## 12\. Success Criteria

* \[ ] `\_\_init\_\_.py` ≤ 80 lines (target: \~60)
* \[ ] Every function body ≤ 20 lines (AST measurement)
* \[ ] Every file ≤ 200 lines
* \[ ] `python -m cli --help` prints top-level help without error
* \[ ] `python -m cli check` detects aria2c binary correctly (or prints helpful error)
* \[ ] `python -m cli start --help` shows start subcommand options
* \[ ] `python -m cli status --help` shows status subcommand options
* \[ ] `from cli import main` resolves successfully
* \[ ] `from cli.finder import find\_binary` resolves to public function
* \[ ] `uv build` succeeds; wheel contains all 7 source files
* \[ ] `ruff check apps/cli/src/cli/` — zero violations
* \[ ] `ty apps/cli/src/cli/` — zero errors
* \[ ] `python scripts/lint/wc-lint.py apps/cli/` — zero violations

\---

## 13\. Appendix: Diff Summary

```
 apps/cli/src/cli/\_\_init\_\_.py          | 173 → \~60  (-113)
 apps/cli/src/cli/\_\_main\_\_.py          |   3         (unchanged)
 apps/cli/src/cli/finder.py            |  25  (new)
 apps/cli/src/cli/config.py            |  22  (new)
 apps/cli/src/cli/commands/\_\_init\_\_.py |   8  (new)
 apps/cli/src/cli/commands/start.py    |  55  (new)
 apps/cli/src/cli/commands/status.py   |  42  (new)
 ─────────────────────────────────────────────────
 Total                                 | 176 → \~215   (+39)
```

Net: +39 lines (module boilerplate, docstrings, private helpers, `\_NOT\_FOUND\_MSG` constant).
The core logic — binary discovery, command implementations, arg parsing — is preserved
verbatim, just redistributed across modules.

