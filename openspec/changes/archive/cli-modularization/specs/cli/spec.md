# CLI Specification

## Purpose

The CLI package provides a command-line interface for managing a local aria2c daemon. It offers
subcommands for starting the daemon (`start`), checking binary availability (`check`), and querying
daemon status via the aria2 SDK (`status`). The package is the primary user-facing entry point for
the aria2 Python distribution.

## Requirements

### Requirement: Package Structure

The CLI SHALL be implemented as a modular package with the following files, each under 200 lines
and every function body at most 20 lines:

| File | Purpose | Max Lines |
|---|---|---|
| `apps/cli/src/cli/__init__.py` | Entry point — `main()`, `cmd_check`, argparse builders | ≤ 80 |
| `apps/cli/src/cli/__main__.py` | `python -m cli` trampoline (unchanged) | 3 |
| `apps/cli/src/cli/finder.py` | `find_binary()` — locate aria2c binary | ≤ 40 |
| `apps/cli/src/cli/config.py` | `DEFAULT_PORT`, `DEFAULT_HOST`, `_fmt_speed()` | ≤ 30 |
| `apps/cli/src/cli/commands/__init__.py` | Re-exports `cmd_start`, `cmd_status` | ≤ 10 |
| `apps/cli/src/cli/commands/start.py` | `cmd_start()` — start aria2c daemon | ≤ 60 |
| `apps/cli/src/cli/commands/status.py` | `cmd_status()` — query daemon status | ≤ 50 |

The dependency graph SHALL contain no circular imports:

```
__main__.py ──► __init__.py ──► finder.py
                         ├──► config.py
                         └──► commands/__init__.py
                                ├──► commands/start.py ──► finder.py, config.py
                                └──► commands/status.py ──► config.py, aria2-sdk
```

#### Scenario: Package installable by hatchling

- GIVEN a build with `packages = ["src/cli"]` in `pyproject.toml`
- WHEN `uv build` is executed
- THEN the resulting wheel MUST contain all seven source files
- AND `commands/` MUST be auto-discovered as a subpackage

#### Scenario: All files under 200 lines

- GIVEN the refactored CLI package
- WHEN each `.py` file is measured with `wc -l`
- THEN no file SHALL exceed 200 physical lines
- AND `__init__.py` SHALL be at most 80 lines

#### Scenario: All functions under 20 lines

- GIVEN the refactored CLI package
- WHEN each function body is measured (from `def` to next top-level token)
- THEN no function body SHALL exceed 20 lines

### Requirement: Entry Point

The entry point `main()` SHALL remain accessible through the following paths, all of which MUST
resolve to the same callable:

- `from cli import main` (package root)
- `python -m cli` (via `__main__.py`)
- The `aria2` console script (if registered in `pyproject.toml` `[project.scripts]`)

#### Scenario: Programmatic import

- GIVEN the CLI package is installed
- WHEN user code executes `from cli import main`
- THEN `main` resolves to a callable function in `cli/__init__.py`
- AND `main()` with no arguments or `--help` prints the top-level help text

#### Scenario: Python -m invocation

- GIVEN the CLI package is installed
- WHEN the command `python -m cli --help` is executed in a shell
- THEN the CLI prints the top-level argparse help text
- AND exits with code 0

#### Scenario: Console script entry point

- GIVEN the CLI wheel is installed
- WHEN the `aria2` command is invoked with `--help`
- THEN the CLI prints the top-level argparse help text
- AND exits with code 0

### Requirement: Binary Discovery

The function `find_binary()` in `finder.py` SHALL locate the aria2c binary and return its
absolute `Path`. It MUST try the bundled binary (via `aria2_bin`) first, then fall back to
searching the system `PATH` or the `ARIA2C_PATH` environment variable.

The function SHALL be public (no leading underscore), replacing the old private `_find_binary`.

The `except ImportError, FileNotFoundError:` syntax bug (Python-2-era tuple-unpacking form) MUST be
fixed to `except (ImportError, FileNotFoundError):`, preserving identical catch semantics.

#### Scenario: Bundled binary found

- GIVEN `aria2_bin` is importable and `aria2_bin.get_binary_path()` returns a valid path
- WHEN `find_binary()` is called
- THEN the bundled path is returned
- AND no PATH search is attempted

#### Scenario: Bundled binary not available, PATH found

- GIVEN `aria2_bin` is not importable (or `get_binary_path()` raises `FileNotFoundError`)
- AND a system `aria2c` is available in `PATH`
- WHEN `find_binary()` is called
- THEN the system `aria2c` path is returned
- AND no error is raised

#### Scenario: ARIA2C_PATH override

- GIVEN the environment variable `ARIA2C_PATH` is set to `/custom/path/aria2c`
- AND that path exists in `PATH`
- WHEN `find_binary()` is called (and bundled is not available)
- THEN `/custom/path/aria2c` takes precedence over plain `aria2c`
- AND the resolved Path is returned

#### Scenario: No binary found

- GIVEN `aria2_bin` is not importable
- AND `which aria2c` fails
- WHEN `find_binary()` is called
- THEN the process SHALL exit with a descriptive error message
- AND the exit code SHALL be nonzero

#### Scenario: Syntax bug fixed

- GIVEN `aria2_bin` raises `FileNotFoundError` from `get_binary_path()`
- WHEN `find_binary()` is called
- THEN `FileNotFoundError` is caught by the except clause
- AND execution falls through to the PATH fallback
- AND no `SyntaxError` is raised on Python 3

### Requirement: Configuration Constants

The module `config.py` SHALL provide shared constants and formatting helpers consumed by the CLI
commands:

- `DEFAULT_PORT: int = 6800`
- `DEFAULT_HOST: str = "localhost"`
- `_fmt_speed(bps: int) -> str`

The `_fmt_speed` function SHALL remain private (underscore-prefixed) and SHALL format bytes-per-second
as a human-readable string:

- ≥ 1,000,000 B/s → `"X.X MB/s"` (one decimal)
- ≥ 1,000 B/s → `"X KB/s"` (zero decimals)
- < 1,000 B/s → `"X B/s"`

#### Scenario: Constants used by argparse defaults

- GIVEN `main()` builds argparse subcommands
- WHEN the `start` subcommand is added
- THEN its `--port` argument SHALL default to `DEFAULT_PORT` (6800)
- WHEN the `status` subcommand is added
- THEN its `--host` argument SHALL default to `DEFAULT_HOST` ("localhost")
- AND its `--port` argument SHALL default to `DEFAULT_PORT` (6800)

#### Scenario: Speed formatting

- GIVEN `_fmt_speed(2_500_000)` is called
- THEN it returns `"2.5 MB/s"`
- GIVEN `_fmt_speed(42_000)` is called
- THEN it returns `"42 KB/s"`
- GIVEN `_fmt_speed(900)` is called
- THEN it returns `"900 B/s"`

### Requirement: Start Command

The function `cmd_start(args: argparse.Namespace)` in `commands/start.py` SHALL spawn an aria2c
daemon process with RPC enabled on the specified port.

It MUST support two modes:

- **Daemon mode** (`--daemon`): launches aria2c with `--daemon=true`, prints a confirmation, and
  returns immediately.
- **Foreground mode** (default): launches aria2c as a subprocess, registers SIGINT/SIGTERM handlers,
  and waits for the child to exit.

It SHALL accept the following arguments via the `args` namespace:
`port`, `secret`, `listen_all`, `dir`, `conf`, `daemon`.

#### Scenario: Foreground start

- GIVEN aria2c binary is available
- WHEN `cmd_start(args)` is called with `args.daemon` falsy
- THEN aria2c is spawned via `subprocess.Popen` with `--enable-rpc` and `--rpc-listen-port={args.port}`
- AND `SIGINT` and `SIGTERM` handlers are registered that call `proc.terminate()`
- AND the process blocks on `proc.wait()`

#### Scenario: Daemon start

- GIVEN aria2c binary is available
- WHEN `cmd_start(args)` is called with `args.daemon` truthy
- THEN aria2c is launched via `subprocess.run` with `--daemon=true`
- AND a confirmation message is printed including the port
- AND if `args.secret` is set, the secret is printed
- AND the function returns without blocking

#### Scenario: Start with all optional arguments

- GIVEN aria2c binary is available
- WHEN `cmd_start(args)` is called with `args.secret`, `args.dir`, `args.conf`, and `args.listen_all` all set
- THEN the subprocess command includes `--rpc-secret`, `--dir`, `--conf-path`, and `--rpc-listen-all=true`

#### Scenario: Binary not found during start

- GIVEN aria2c binary is not available
- WHEN `cmd_start(args)` is called
- THEN `find_binary()` SHALL exit the process with an error message
- AND `cmd_start()` never reaches the subprocess launch

### Requirement: Check Command

The function `cmd_check(args: argparse.Namespace)` in `__init__.py` SHALL verify that the aria2c
binary exists and can execute `--version`. It MUST remain defined in `__init__.py`.

#### Scenario: Binary found and working

- GIVEN aria2c binary is available
- WHEN `cmd_check(args)` is called
- THEN `find_binary()` locates the binary
- AND `aria2c --version` is executed
- AND the first line of stdout is printed after a checkmark message
- AND the function returns normally (exit code 0)

#### Scenario: Binary found but broken

- GIVEN aria2c binary exists at a path but fails to execute `--version`
- WHEN `cmd_check(args)` is called
- THEN an error message is printed indicating execution failure
- AND `sys.exit(1)` is called

#### Scenario: Binary not found

- GIVEN aria2c binary is not available
- WHEN `cmd_check(args)` is called
- THEN `find_binary()` SHALL call `sys.exit()` with a descriptive message
- AND the `cmd_check` function SHALL catch `SystemExit` and re-raise via `sys.exit(1)`

### Requirement: Status Command

The function `cmd_status(args: argparse.Namespace)` in `commands/status.py` SHALL query a running
aria2 daemon for version information and global download statistics via the aria2 SDK.

It SHALL be an `async` function. It SHALL accept `host`, `port`, and `secret` from the `args`
namespace.

#### Scenario: Successful status query

- GIVEN an aria2c daemon is running on the specified host and port
- WHEN `cmd_status(args)` is called
- THEN an `Aria2Client` is created with the provided host/port/secret and 5-second timeout
- AND `client.system.get_version()` is called
- AND the aria2 version and enabled features are printed
- AND `client.status.get_global_stat()` is called
- AND active, waiting, and stopped download counts are printed
- AND download/upload speeds are formatted via `_fmt_speed` and printed
- AND the client context manager cleans up the connection

#### Scenario: Daemon not running

- GIVEN no service is listening on the specified host and port
- WHEN `cmd_status(args)` is called
- THEN `ConnectionRefusedError` is caught
- AND a message is printed indicating aria2 is not running on that host:port
- AND a hint to run `aria2 start` is shown
- AND the process exits with a nonzero code

#### Scenario: SDK not installed

- GIVEN the `aria2` SDK package is not importable
- WHEN `cmd_status(args)` is called
- THEN the process exits with the message "aria2 SDK not installed"

#### Scenario: Global stats not supported

- GIVEN an aria2c daemon is running but `get_global_stat()` raises an exception
- WHEN `cmd_status(args)` is called
- THEN version info is still printed
- AND the stats section is silently skipped (no crash)

#### Scenario: Unexpected error during status

- GIVEN an unexpected exception is raised during the status query
- WHEN `cmd_status(args)` is called
- THEN the exception is caught and the error message is printed with an ✗ prefix
- AND the process exits with a nonzero code

### Requirement: Zero Behavioral Change

The refactoring SHALL be purely structural. All existing CLI behavior — argument parsing defaults,
output formatting, error messages, exit codes, signal handling, and subprocess invocation —
MUST be preserved exactly.

#### Scenario: Start command output unchanged

- GIVEN the refactored CLI
- WHEN `aria2 start --daemon --port 6800` is executed
- THEN the output matches exactly the output from the pre-refactoring monolithic CLI

#### Scenario: Status output format unchanged

- GIVEN a running aria2c daemon
- WHEN `aria2 status` is executed with both old and new CLI
- THEN the version line, features line, download counts, and speed formatting are identical

#### Scenario: Check output and exit codes unchanged

- GIVEN the same aria2c binary
- WHEN `aria2 check` is executed with both old and new CLI
- THEN the output text and exit codes are identical

#### Scenario: Error messages unchanged

- GIVEN no aria2c binary is available
- WHEN `aria2 start` is executed
- THEN the error message matches exactly the pre-refactoring message

### Requirement: Import Compatibility

The CLI package SHALL maintain backward-compatible import paths for public symbols.

#### Scenario: Commands re-exported from package

- GIVEN the refactored CLI package
- WHEN `from cli.commands import cmd_start, cmd_status` is executed
- THEN both functions resolve to the implementations in `commands/start.py` and `commands/status.py`
- AND `cli.commands.__all__` contains `["cmd_start", "cmd_status"]`

#### Scenario: find_binary accessible

- GIVEN the refactored CLI package
- WHEN `from cli.finder import find_binary` is executed
- THEN `find_binary` resolves to the public function in `finder.py`
- AND the old private `_find_binary` is no longer accessible (removed)

#### Scenario: Configuration accessible

- GIVEN the refactored CLI package
- WHEN `from cli.config import DEFAULT_PORT, DEFAULT_HOST, _fmt_speed` is executed
- THEN all three symbols resolve to the definitions in `config.py`
